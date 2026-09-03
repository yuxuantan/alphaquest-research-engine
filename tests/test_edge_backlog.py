from __future__ import annotations

from datetime import datetime, timezone
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from alphaquest.research.edge_backlog import (
    EdgeBacklogAuthorityError,
    EdgeBacklogConflictError,
    EdgeBacklogDecisionV1,
    EdgeBacklogEntryRevisionV1,
    EdgeBacklogIntegrityError,
    EdgeBacklogStore,
    EvidenceReferenceV1,
    ObservationRevisionV1,
    canonical_json_bytes,
    record_sha256,
)
from alphaquest.studio.duplicates import duplicate_matches, edge_fingerprint


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def _observation_payload(
    observation_id: str,
    *,
    source_id: str | None = None,
    locator: str | None = None,
    statement: str = "Completed opening-auction imbalance persisted after the source timestamp.",
    integrity: str = "LOCATOR_ONLY",
    content_sha256: str | None = None,
    known_conflicts: list[str] | None = None,
    claim_locator: str = "table-1",
) -> dict:
    source = source_id or f"source.{observation_id}"
    return {
        "observation_id": observation_id,
        "statement": statement,
        "evidence_refs": [
            {
                "source_id": source,
                "source_kind": "PAPER",
                "locator": locator or f"https://example.test/{source}",
                "claim_locator": claim_locator,
                "evidence_time": "2026-09-01T15:30:00Z",
                "integrity": integrity,
                "content_sha256": content_sha256,
            }
        ],
        "known_conflicts": known_conflicts or [],
    }


def _entry_payload(
    entry_id: str,
    observation: ObservationRevisionV1,
    **overrides: object,
) -> dict:
    payload = {
        "entry_id": entry_id,
        "title": "Opening imbalance continuation",
        "instruments": ["ES"],
        "market_behavior": "Opening auction imbalance persists into early regular trading",
        "causal_mechanism": "Delayed hedging after price discovery",
        "counterparty_transfer_rationale": "Late hedgers cross liquidity supplied by patient participants",
        "information_inputs": ["completed opening imbalance", "completed price response"],
        "information_availability": "Both inputs are available after the opening interval completes",
        "expected_effect": "Continuation in the direction of the completed imbalance",
        "holding_horizon": "Short intraday horizon",
        "market_context": "Liquid equity index futures during regular trading hours",
        "observation_refs": [
            {
                "observation_id": observation.observation_id,
                "observation_revision_sha256": observation.record_sha256,
                "role": "MOTIVATING",
            }
        ],
        "open_questions": ["Does the transfer survive costs?"],
    }
    payload.update(overrides)
    return payload


def _capture(store: EdgeBacklogStore, observation_id: str, **overrides: object) -> ObservationRevisionV1:
    return store.capture_observation(
        _observation_payload(observation_id, **overrides),
        actor_id="codex-task-runner",
        task_id="task.edge.capture",
        recorded_at=NOW,
    )


def _create(store: EdgeBacklogStore, entry_id: str, observation: ObservationRevisionV1, **overrides: object):
    return store.create_entry(
        _entry_payload(entry_id, observation, **overrides),
        actor_id="codex-task-runner",
        task_id="task.edge.create",
        recorded_at=NOW,
    )


def _rewrite_record(path: Path, payload: dict) -> None:
    payload["record_sha256"] = record_sha256(payload)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")


def test_closed_models_timezone_and_explicit_source_integrity() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceReferenceV1.model_validate(
            {
                **_observation_payload("obs.closed")["evidence_refs"][0],
                "unexpected": True,
            }
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        EvidenceReferenceV1.model_validate(
            {
                **_observation_payload("obs.naive")["evidence_refs"][0],
                "evidence_time": "2026-09-01T15:30:00",
            }
        )
    with pytest.raises(ValidationError, match="requires content_sha256"):
        EvidenceReferenceV1.model_validate(
            {
                **_observation_payload("obs.hash")["evidence_refs"][0],
                "integrity": "HASH_BOUND",
            }
        )
    with pytest.raises(ValidationError, match="must not claim content_sha256"):
        EvidenceReferenceV1.model_validate(
            {
                **_observation_payload("obs.locator")["evidence_refs"][0],
                "content_sha256": "a" * 64,
            }
        )


def test_canonical_serialization_and_hash_are_stable(tmp_path: Path) -> None:
    roots = [tmp_path / "one", tmp_path / "two"]
    records = []
    for root in roots:
        store = EdgeBacklogStore(root)
        observation = _capture(store, "obs.stable")
        records.append(_create(store, "edge.stable", observation))

    assert records[0].record_sha256 == records[1].record_sha256
    assert records[0].fingerprint_sha256 == records[1].fingerprint_sha256
    assert records[0].fingerprint_sha256 == ("248e3d4401679a6296c64e8517dee981eb640342d5598231970433e1f8930e9d")
    assert records[0].record_sha256 == ("d05f95a04081986b950425859dc26b67225c89d5918704a23a168e1f12949859")
    assert (roots[0] / "research/edge_backlog/entries/edge.stable/revisions/000001.json").read_bytes() == (
        roots[1] / "research/edge_backlog/entries/edge.stable/revisions/000001.json"
    ).read_bytes()


def test_append_is_exclusive_and_no_delete_api_exists(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    _capture(store, "obs.exclusive")

    with pytest.raises(EdgeBacklogConflictError, match="already exists"):
        _capture(store, "obs.exclusive")

    assert not hasattr(store, "delete")
    assert "delete" not in inspect.signature(EdgeBacklogStore).parameters


def test_broken_revision_hash_and_branching_fail_closed(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.chain")
    store.revise_observation(
        observation.observation_id,
        _observation_payload("obs.chain", statement="A second sourced description preserves the observation."),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    second = tmp_path / "research/edge_backlog/observations/obs.chain/revisions/000002.json"
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["previous_revision_sha256"] = "b" * 64
    _rewrite_record(second, payload)
    with pytest.raises(EdgeBacklogIntegrityError, match="broken observation revision chain"):
        store.validate()

    clean = EdgeBacklogStore(tmp_path / "branch")
    first = _capture(clean, "obs.branch")
    clean.revise_observation(
        first.observation_id,
        _observation_payload("obs.branch", statement="The legitimate second revision remains source bound."),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    source = tmp_path / "branch/research/edge_backlog/observations/obs.branch/revisions/000002.json"
    branch = source.with_name("000003.json")
    branch.write_bytes(source.read_bytes())
    with pytest.raises(EdgeBacklogIntegrityError, match="path identity mismatch"):
        clean.validate()


def test_missing_observation_and_conflicting_source_identity_are_rejected(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.source", source_id="source.shared", locator="doi:10/example")
    with pytest.raises(EdgeBacklogIntegrityError, match="conflicting identity"):
        _capture(store, "obs.conflict", source_id="source.shared", locator="doi:10/different")

    payload = _entry_payload("edge.missing", observation)
    payload["observation_refs"][0]["observation_revision_sha256"] = "f" * 64
    with pytest.raises(EdgeBacklogIntegrityError, match="missing observation revision"):
        store.create_entry(payload, actor_id="codex-task-runner", recorded_at=NOW)


def test_contradicting_evidence_cannot_silently_disappear(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    support = _capture(store, "obs.support")
    conflict = _capture(
        store,
        "obs.conflict",
        statement="A separate sample contradicts persistence after the opening imbalance.",
    )
    entry = _create(
        store,
        "edge.contradiction",
        support,
        observation_refs=[
            {
                "observation_id": support.observation_id,
                "observation_revision_sha256": support.record_sha256,
                "role": "SUPPORTING",
            },
            {
                "observation_id": conflict.observation_id,
                "observation_revision_sha256": conflict.record_sha256,
                "role": "CONTRADICTING",
            },
        ],
    )
    revised = _entry_payload("edge.contradiction", support, title="Renamed edge")
    with pytest.raises(EdgeBacklogConflictError, match="cannot disappear"):
        store.revise_entry(entry.entry_id, revised, actor_id="codex-task-runner", recorded_at=NOW)


def test_terminal_decision_seals_exact_revision_and_snapshot(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    first_obs = _capture(store, "obs.first")
    duplicate_obs = _capture(store, "obs.duplicate")
    first = _create(store, "edge.first", first_obs)
    duplicate = _create(store, "edge.duplicate", duplicate_obs, title="Different wording")
    snapshot = store.duplicate_snapshot(duplicate.entry_id)
    decision = store.record_human_decision(
        duplicate.entry_id,
        disposition="DUPLICATE",
        duplicate_resolution="SAME_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        canonical_entry_id=first.entry_id,
        reason_codes=["DUPLICATE_EDGE"],
        rationale="The economic mechanism, timing, and transfer rationale are the same.",
        reviewer_id="owner",
        decision_id="decision.duplicate",
        recorded_at=NOW,
    )

    assert decision.entry_revision_sha256 == duplicate.record_sha256
    assert decision.candidate_snapshot_sha256 == snapshot["snapshot_sha256"]
    assert decision.actor.actor_class == "HUMAN_OWNER_RESEARCHER"
    with pytest.raises(EdgeBacklogConflictError, match="terminally sealed"):
        store.revise_entry(
            duplicate.entry_id,
            _entry_payload(duplicate.entry_id, duplicate_obs, title="Cannot reopen"),
            actor_id="codex-task-runner",
            recorded_at=NOW,
        )


def test_candidate_snapshot_staleness_and_unresolved_continue_fail_closed(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    first_obs = _capture(store, "obs.snapshot.first")
    query_obs = _capture(store, "obs.snapshot.query")
    query = _create(store, "edge.snapshot.query", query_obs)
    stale = store.duplicate_snapshot(query.entry_id)
    _create(store, "edge.snapshot.new", first_obs)

    with pytest.raises(EdgeBacklogConflictError, match="snapshot is stale"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=stale["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="This uses a materially different transfer mechanism.",
            reviewer_id="owner",
            recorded_at=NOW,
        )

    current = store.duplicate_snapshot(query.entry_id)
    with pytest.raises(ValidationError, match="UNRESOLVED cannot become"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="UNRESOLVED",
            candidate_snapshot_sha256=current["snapshot_sha256"],
            reason_codes=["AMBIGUOUS_DUPLICATE"],
            rationale="The duplicate relationship remains unresolved.",
            reviewer_id="owner",
            recorded_at=NOW,
        )


def test_suspend_resume_is_append_only_and_allows_later_revision(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.suspend")
    entry = _create(store, "edge.suspend", observation)
    snapshot = store.duplicate_snapshot(entry.entry_id)
    suspension = store.record_human_decision(
        entry.entry_id,
        disposition="SUSPENDED",
        duplicate_resolution="UNRESOLVED",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["DATA_UNAVAILABLE"],
        rationale="Required causal-timing data is not currently available.",
        revisit_conditions=["A source with timestamped input availability is captured."],
        reviewer_id="owner",
        decision_id="decision.suspend",
        recorded_at=NOW,
    )
    suspension_path = tmp_path / "research/edge_backlog/entries/edge.suspend/decisions/000001.json"
    suspension_bytes = suspension_path.read_bytes()
    with pytest.raises(EdgeBacklogConflictError, match="is suspended"):
        store.revise_entry(
            entry.entry_id,
            _entry_payload(entry.entry_id, observation),
            actor_id="codex-task-runner",
            recorded_at=NOW,
        )

    resumed = store.resume_entry(
        entry.entry_id,
        reason_codes=["NEW_INFORMATION"],
        rationale="New timestamped source evidence is now available for review.",
        reviewer_id="owner",
        decision_id="decision.resume",
        recorded_at=NOW,
    )
    revised = store.revise_entry(
        entry.entry_id,
        _entry_payload(entry.entry_id, observation, title="Clarified after resume"),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )

    assert suspension.record_sha256 == resumed.previous_decision_sha256
    assert revised.revision == 2
    assert store.entry_state(entry.entry_id) == "UNREVIEWED"
    assert suspension_path.read_bytes() == suspension_bytes
    assert store.validate()["status"] == "PASS"


def test_actor_authority_and_proposal_link_without_positive_disposition(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.authority")
    entry = _create(store, "edge.authority", observation)
    proposal = tmp_path / "research/proposals/hypothesis.authority.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")

    link = store.record_hypothesis_proposal_link(
        entry.entry_id,
        hypothesis_id="hypothesis.authority",
        target_locator=proposal,
        actor_id="edge-backlog-linker",
        task_id="task.hypothesis.proposal",
        link_id="link.hypothesis.proposal",
        recorded_at=NOW,
    )

    assert store.entry_state(entry.entry_id) == "UNREVIEWED"
    assert link.relationship == "HYPOTHESIS_PROPOSAL"
    assert link.authorizing_decision_id is None
    assert link.actor.actor_class == "ALPHAQUEST_DETERMINISTIC_ENGINE"
    with pytest.raises(EdgeBacklogAuthorityError, match="reserved for P3-P5"):
        store.record_reserved_downstream_link()
    assert "actor_class" not in inspect.signature(store.capture_observation).parameters
    assert store.validate()["links"] == 1


def test_decision_model_rejects_codex_as_human_resolution(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.actor")
    entry = _create(store, "edge.actor", observation)
    snapshot = store.duplicate_snapshot(entry.entry_id)
    decision = store.record_human_decision(
        entry.entry_id,
        disposition="REVIEWED_CONTINUE",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["OTHER"],
        rationale="Human curation found no identity collision in the reviewed snapshot.",
        reviewer_id="owner",
        decision_id="decision.actor",
        recorded_at=NOW,
    )
    forged = decision.model_dump(mode="json", by_alias=True)
    forged["actor"]["actor_class"] = "CODEX"
    forged["record_sha256"] = record_sha256(forged)
    with pytest.raises(ValidationError, match="HUMAN_OWNER_RESEARCHER"):
        EdgeBacklogDecisionV1.model_validate(forged)


def test_revisit_lineage_preserves_prior_identity_and_rejects_cycles(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    old_obs = _capture(store, "obs.revisit.old")
    new_obs = _capture(store, "obs.revisit.new")
    old = _create(store, "edge.revisit.old", old_obs)
    new = _create(
        store,
        "edge.revisit.new",
        new_obs,
        causal_mechanism="New participant-classification data identifies a different causal transfer",
    )
    link = store.record_revisit_link(
        new.entry_id,
        prior_entry_id=old.entry_id,
        rationale="New participant-classification data materially changes the causal mechanism.",
        reviewer_id="owner",
        link_id="link.revisit",
        recorded_at=NOW,
    )

    assert link.target_id == old.entry_id
    assert link.target_payload_sha256 == old.record_sha256
    with pytest.raises(EdgeBacklogConflictError, match="lineage cycle"):
        store.record_revisit_link(
            old.entry_id,
            prior_entry_id=new.entry_id,
            rationale="This reverse relation would create an invalid history cycle.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    assert store.validate()["status"] == "PASS"


def test_fingerprint_excludes_title_and_rejects_mechanical_fields(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    first_obs = _capture(store, "obs.title.first")
    second_obs = _capture(store, "obs.title.second")
    first = _create(store, "edge.title.first", first_obs, title="First campaign-style name")
    second = _create(store, "edge.title.second", second_obs, title="Entirely different title wording")

    assert first.fingerprint_sha256 == second.fingerprint_sha256
    match = next(item for item in store.duplicate_candidates(second.entry_id) if item["candidate_id"] == first.entry_id)
    assert match["exact_fingerprint"] is True

    mechanical = _entry_payload("edge.mechanic", first_obs)
    mechanical["entry_threshold"] = 2.5
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        store.create_entry(mechanical, actor_id="codex-task-runner", recorded_at=NOW)


def test_dedup_surfaces_synonyms_source_relationships_and_instrument_transfers(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    shared_source = _capture(
        store,
        "obs.shared.one",
        source_id="source.shared.paper",
        locator="doi:10/shared",
        claim_locator="claim-one",
    )
    same_source = _capture(
        store,
        "obs.shared.two",
        source_id="source.shared.paper",
        locator="doi:10/shared",
        statement="The same paper separately reports inventory reversion after forced flow.",
        claim_locator="claim-two",
    )
    maker = _create(
        store,
        "edge.synonym.maker",
        shared_source,
        causal_mechanism="Market makers use slow hedging after the auction",
        counterparty_transfer_rationale="Market makers transfer returns to patient liquidity",
    )
    dealer = _create(
        store,
        "edge.synonym.dealer",
        same_source,
        causal_mechanism="Dealers use delayed hedging after the auction",
        counterparty_transfer_rationale="Dealers transfer returns to patient liquidity",
    )
    unrelated = _create(
        store,
        "edge.same.source.distinct",
        same_source,
        market_behavior="Late-session forced flow mean reverts",
        causal_mechanism="Constrained liquidation temporarily exhausts the order book",
        counterparty_transfer_rationale="Forced sellers transfer returns to unconstrained buyers",
        information_inputs=["late-session signed flow"],
        information_availability="After completed liquidation bursts",
        expected_effect="Reversion after forced flow ends",
        holding_horizon="Minutes",
        market_context="Late-session stress",
    )
    transferred_obs = _capture(store, "obs.transfer")
    transferred = _create(store, "edge.transfer", transferred_obs, instruments=["NQ"])

    dealer_match = next(
        item for item in store.duplicate_candidates(dealer.entry_id) if item["candidate_id"] == maker.entry_id
    )
    unrelated_match = next(
        item for item in store.duplicate_candidates(unrelated.entry_id) if item["candidate_id"] == maker.entry_id
    )
    transfer_match = next(
        item for item in store.duplicate_candidates(transferred.entry_id) if item["candidate_id"] == maker.entry_id
    )
    assert dealer_match["taxonomy_score"] >= 0.6
    assert dealer_match["source_overlap"] == ["source.shared.paper"]
    assert unrelated_match["source_overlap"] == ["source.shared.paper"]
    assert unrelated_match["exact_fingerprint"] is False
    assert transfer_match["exact_fingerprint"] is False
    assert transfer_match["taxonomy_score"] >= 0.7


def test_legacy_campaign_duplicate_behavior_has_golden_output(tmp_path: Path) -> None:
    campaign = tmp_path / "research/campaigns/active/es_prior"
    campaign.mkdir(parents=True)
    campaign.joinpath("campaign.yaml").write_text(
        "campaign_id: es_prior\n"
        "title: Opening range continuation\n"
        "hypothesis: Opening range breakouts persist after high volume\n"
        "expected_mechanism: price discovery and delayed hedging\n",
        encoding="utf-8",
    )
    matches = duplicate_matches(
        project_root=tmp_path,
        campaign_id="es_new",
        title="Opening range continuation",
        hypothesis="Opening range breakouts persist",
        expected_mechanism="price discovery and delayed hedging",
    )

    assert edge_fingerprint("Price discovery delayed hedging") == (
        "caa04f84136db1976fd1fe372130dcbd3e890a51a9d8465e01bf314c6e396efd"
    )
    assert matches == [
        {
            "campaign_id": "es_prior",
            "title": "Opening range continuation",
            "source": "definition",
            "path": "research/campaigns/active/es_prior/campaign.yaml",
            "exact_fingerprint": False,
            "similarity": 0.7692,
            "taxonomy_schema": "alphaquest.duplicate-taxonomy/v1",
            "taxonomy_score": 0.0,
            "matched_dimensions": [],
            "dimension_scores": {},
            "verdict": None,
            "match_band": "POSSIBLE_RELATED_EDGE",
        }
    ]


def test_manual_record_tampering_and_unknown_entry_fields_fail_validation(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.tamper")
    entry = _create(store, "edge.tamper", observation)
    path = tmp_path / "research/edge_backlog/entries/edge.tamper/revisions/000001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["title"] = "Hand-edited title"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EdgeBacklogIntegrityError, match="record_sha256"):
        store.validate()

    valid = entry.model_dump(mode="json", by_alias=True)
    valid["unknown"] = "not allowed"
    valid["record_sha256"] = record_sha256(valid)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EdgeBacklogEntryRevisionV1.model_validate(valid)
