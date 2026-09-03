from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import multiprocessing
from pathlib import Path

import pytest
from pydantic import ValidationError

from alphaquest.research import duplicate_matching as duplicate_core
from alphaquest.research.edge_backlog import (
    EdgeBacklogAuthorityError,
    EdgeBacklogConflictError,
    EdgeBacklogDecisionV1,
    EdgeBacklogEntryRevisionV1,
    EdgeBacklogIntegrityError,
    EdgeBacklogLinkV1,
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


def _record_duplicate(store: EdgeBacklogStore, source_id: str, target_id: str):
    snapshot = store.duplicate_snapshot(source_id)
    return store.record_human_decision(
        source_id,
        disposition="DUPLICATE",
        duplicate_resolution="SAME_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        canonical_entry_id=target_id,
        reason_codes=["DUPLICATE_EDGE"],
        rationale="The exact economic edge is already represented by the canonical target.",
        reviewer_id="owner",
        recorded_at=NOW,
    )


def _forge_duplicate_decision(store: EdgeBacklogStore, source_id: str, target_id: str) -> Path:
    entry = store.latest_entry(source_id)
    snapshot = store.duplicate_snapshot(source_id)
    payload = {
        "schema": "alphaquest.edge-backlog-decision/v1",
        "record_id": f"decision.forged.{source_id}",
        "decision_id": f"decision.forged.{source_id}",
        "entry_id": source_id,
        "entry_revision_sha256": entry.record_sha256,
        "entry_link_chain_sha256": snapshot["entry_link_chain_sha256"],
        "sequence": 1,
        "previous_decision_sha256": None,
        "disposition": "DUPLICATE",
        "duplicate_resolution": "SAME_EDGE",
        "candidate_snapshot": snapshot["candidates"],
        "candidate_snapshot_sha256": snapshot["snapshot_sha256"],
        "canonical_entry_id": target_id,
        "related_edge_family_ids": [],
        "reason_codes": ["DUPLICATE_EDGE"],
        "rationale": "Adversarial fixture bypasses the append API to exercise full validation.",
        "revisit_conditions": [],
        "recorded_at": NOW.isoformat().replace("+00:00", "Z"),
        "actor": {
            "actor_class": "HUMAN_OWNER_RESEARCHER",
            "actor_id": "owner",
            "task_id": None,
        },
    }
    payload["record_sha256"] = record_sha256(payload)
    record = EdgeBacklogDecisionV1.model_validate(payload)
    path = store.root / "entries" / source_id / "decisions/000001.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(record) + b"\n")
    return path


def _locked_process_action(
    project_root: str,
    barrier,
    results,
    action: str,
    arguments: dict,
) -> None:
    """Run one mutation only after holding the real cross-process lock."""

    store = EdgeBacklogStore(project_root)
    try:
        with store._transaction(exclusive=True):
            barrier.wait(timeout=20)
            if action == "revise_entry":
                record = store.revise_entry(**arguments)
            elif action == "record_decision":
                record = store.record_human_decision(**arguments)
            elif action == "record_proposal_link":
                record = store.record_hypothesis_proposal_link(**arguments)
            else:  # pragma: no cover - fixture misuse guard
                raise AssertionError(f"unsupported concurrent action: {action}")
        results.put(("PASS", record.record_sha256))
    except Exception as exc:  # pragma: no cover - surfaced in the parent assertion
        results.put(("ERROR", f"{type(exc).__name__}: {exc}"))


def _start_locked_process(tmp_path: Path, action: str, arguments: dict):
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    process = context.Process(
        target=_locked_process_action,
        args=(str(tmp_path), barrier, results, action, arguments),
    )
    process.start()
    barrier.wait(timeout=20)
    return process, results


def _assert_process_passed(process, results) -> str:
    process.join(timeout=20)
    assert not process.is_alive()
    assert process.exitcode == 0
    status, detail = results.get(timeout=5)
    assert status == "PASS", detail
    results.close()
    results.join_thread()
    return detail


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


def test_locator_only_hash_upgrade_is_retained_and_conflict_is_prewrite(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    locator = "doi:10/source-upgrade"
    store.capture_observation(
        _observation_payload("obs.source.locator", source_id="source.upgrade", locator=locator),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    store.capture_observation(
        _observation_payload(
            "obs.source.hash-a",
            source_id="source.upgrade",
            locator=locator,
            integrity="HASH_BOUND",
            content_sha256="a" * 64,
            claim_locator="table-hash-a",
        ),
        actor_id="codex-task-runner",
        recorded_at=NOW + timedelta(minutes=1),
    )

    rejected_path = store.root / "observations/obs.source.hash-b/revisions/000001.json"
    with pytest.raises(EdgeBacklogIntegrityError, match="conflicting content hash"):
        store.capture_observation(
            _observation_payload(
                "obs.source.hash-b",
                source_id="source.upgrade",
                locator=locator,
                integrity="HASH_BOUND",
                content_sha256="b" * 64,
                claim_locator="table-hash-b",
            ),
            actor_id="codex-task-runner",
            recorded_at=NOW + timedelta(minutes=2),
        )
    assert not rejected_path.exists()

    downgrade_path = store.root / "observations/obs.source.downgrade/revisions/000001.json"
    with pytest.raises(EdgeBacklogIntegrityError, match="conflicting content hash"):
        store.capture_observation(
            _observation_payload(
                "obs.source.downgrade",
                source_id="source.upgrade",
                locator=locator,
                claim_locator="table-downgrade",
            ),
            actor_id="codex-task-runner",
            recorded_at=NOW + timedelta(minutes=2),
        )
    assert not downgrade_path.exists()
    assert store.validate()["status"] == "PASS"


def test_full_validation_rejects_forged_source_hash_downgrade(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    locator = "doi:10/source-downgrade"
    store.capture_observation(
        _observation_payload(
            "obs.source.bound",
            source_id="source.bound",
            locator=locator,
            integrity="HASH_BOUND",
            content_sha256="a" * 64,
        ),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    forged = store.capture_observation(
        _observation_payload("obs.source.forged", source_id="source.other"),
        actor_id="codex-task-runner",
        recorded_at=NOW + timedelta(minutes=1),
    )
    path = store.root / f"observations/{forged.observation_id}/revisions/000001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence_refs"][0].update(
        {
            "source_id": "source.bound",
            "locator": locator,
            "integrity": "LOCATOR_ONLY",
            "content_sha256": None,
        }
    )
    _rewrite_record(path, payload)

    with pytest.raises(EdgeBacklogIntegrityError, match="not strictly earlier"):
        store.validate()


def test_full_validation_rejects_same_timestamp_downgrade_in_one_observation_chain(
    tmp_path: Path,
) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation_id = "obs.source.same-chain"
    source_id = "source.same-chain"
    locator = "doi:10/source-same-chain"
    store.capture_observation(
        _observation_payload(observation_id, source_id=source_id, locator=locator),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    store.revise_observation(
        observation_id,
        _observation_payload(
            observation_id,
            source_id=source_id,
            locator=locator,
            integrity="HASH_BOUND",
            content_sha256="a" * 64,
        ),
        actor_id="codex-task-runner",
        recorded_at=NOW + timedelta(minutes=1),
    )
    store.revise_observation(
        observation_id,
        _observation_payload(
            observation_id,
            source_id=source_id,
            locator=locator,
            integrity="HASH_BOUND",
            content_sha256="a" * 64,
        ),
        actor_id="codex-task-runner",
        recorded_at=NOW + timedelta(minutes=2),
    )

    second_path = store.root / f"observations/{observation_id}/revisions/000002.json"
    second = json.loads(second_path.read_text(encoding="utf-8"))
    second["recorded_at"] = NOW.isoformat().replace("+00:00", "Z")
    _rewrite_record(second_path, second)

    third_path = store.root / f"observations/{observation_id}/revisions/000003.json"
    third = json.loads(third_path.read_text(encoding="utf-8"))
    third["previous_revision_sha256"] = json.loads(second_path.read_text(encoding="utf-8"))["record_sha256"]
    third["recorded_at"] = NOW.isoformat().replace("+00:00", "Z")
    third["evidence_refs"][0]["integrity"] = "LOCATOR_ONLY"
    third["evidence_refs"][0]["content_sha256"] = None
    _rewrite_record(third_path, third)

    with pytest.raises(EdgeBacklogIntegrityError, match="not strictly earlier"):
        store.validate()


def test_equal_timestamp_source_upgrade_across_observations_fails_closed(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    source_id = "source.equal-time"
    locator = "doi:10/source-equal-time"
    store.capture_observation(
        _observation_payload("obs.source.equal-locator", source_id=source_id, locator=locator),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )

    rejected_path = store.root / "observations/obs.source.equal-hash/revisions/000001.json"
    with pytest.raises(EdgeBacklogIntegrityError, match="not strictly earlier"):
        store.capture_observation(
            _observation_payload(
                "obs.source.equal-hash",
                source_id=source_id,
                locator=locator,
                integrity="HASH_BOUND",
                content_sha256="a" * 64,
            ),
            actor_id="codex-task-runner",
            recorded_at=NOW,
        )
    assert not rejected_path.exists()
    assert store.validate()["status"] == "PASS"

    forged = store.capture_observation(
        _observation_payload(
            "obs.source.equal-forged",
            source_id="source.other-equal-time",
            integrity="HASH_BOUND",
            content_sha256="a" * 64,
        ),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    forged_path = store.root / f"observations/{forged.observation_id}/revisions/000001.json"
    payload = json.loads(forged_path.read_text(encoding="utf-8"))
    payload["evidence_refs"][0]["source_id"] = source_id
    payload["evidence_refs"][0]["locator"] = locator
    _rewrite_record(forged_path, payload)

    with pytest.raises(EdgeBacklogIntegrityError, match="not strictly earlier"):
        store.validate()


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


def test_duplicate_canonical_target_accepts_only_a_direct_live_entry(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observations = [_capture(store, f"obs.duplicate.direct.{index}") for index in range(3)]
    canonical = _create(store, "edge.duplicate.direct.canonical", observations[0])
    direct = _create(store, "edge.duplicate.direct.source", observations[1])
    rejected = _create(store, "edge.duplicate.direct.rejected", observations[2])

    decision = _record_duplicate(store, direct.entry_id, canonical.entry_id)
    assert decision.canonical_entry_id == canonical.entry_id

    rejected_snapshot = store.duplicate_snapshot(rejected.entry_id)
    store.record_human_decision(
        rejected.entry_id,
        disposition="REJECTED",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=rejected_snapshot["snapshot_sha256"],
        reason_codes=["CAUSAL_WEAKNESS"],
        rationale="The owner rejected this edge without granting scientific validity.",
        reviewer_id="owner",
        recorded_at=NOW,
    )
    new_observation = _capture(store, "obs.duplicate.direct.new")
    new_source = _create(store, "edge.duplicate.direct.new", new_observation)
    with pytest.raises(EdgeBacklogConflictError, match="terminally rejected"):
        _record_duplicate(store, new_source.entry_id, rejected.entry_id)
    assert not (store.root / f"entries/{new_source.entry_id}/decisions/000001.json").exists()
    assert store.validate()["status"] == "PASS"


def test_duplicate_canonicalization_rejects_multi_hop_and_cycle_appends(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observations = [_capture(store, f"obs.duplicate.graph.{index}") for index in range(4)]
    first = _create(store, "edge.duplicate.graph.first", observations[0])
    second = _create(store, "edge.duplicate.graph.second", observations[1])
    third = _create(store, "edge.duplicate.graph.third", observations[2])
    fourth = _create(store, "edge.duplicate.graph.fourth", observations[3])

    _record_duplicate(store, first.entry_id, second.entry_id)
    with pytest.raises(EdgeBacklogConflictError, match="chains are not allowed"):
        _record_duplicate(store, second.entry_id, third.entry_id)
    assert not (store.root / f"entries/{second.entry_id}/decisions/000001.json").exists()

    _record_duplicate(store, third.entry_id, fourth.entry_id)
    with pytest.raises(EdgeBacklogConflictError, match="already duplicate"):
        _record_duplicate(store, second.entry_id, third.entry_id)
    with pytest.raises(EdgeBacklogConflictError, match="canonicalization cycle"):
        _record_duplicate(store, second.entry_id, first.entry_id)
    assert store.validate()["status"] == "PASS"


def test_full_validation_rejects_forged_duplicate_multi_hop_and_cycle(tmp_path: Path) -> None:
    chain_store = EdgeBacklogStore(tmp_path / "chain")
    chain_observations = [_capture(chain_store, f"obs.forged.chain.{index}") for index in range(3)]
    chain_first = _create(chain_store, "edge.forged.chain.first", chain_observations[0])
    chain_second = _create(chain_store, "edge.forged.chain.second", chain_observations[1])
    chain_third = _create(chain_store, "edge.forged.chain.third", chain_observations[2])
    _record_duplicate(chain_store, chain_first.entry_id, chain_second.entry_id)
    _forge_duplicate_decision(chain_store, chain_second.entry_id, chain_third.entry_id)
    with pytest.raises(EdgeBacklogIntegrityError, match="already duplicate|multi-hop"):
        chain_store.validate()

    cycle_store = EdgeBacklogStore(tmp_path / "cycle")
    cycle_observations = [_capture(cycle_store, f"obs.forged.cycle.{index}") for index in range(2)]
    cycle_first = _create(cycle_store, "edge.forged.cycle.first", cycle_observations[0])
    cycle_second = _create(cycle_store, "edge.forged.cycle.second", cycle_observations[1])
    _record_duplicate(cycle_store, cycle_first.entry_id, cycle_second.entry_id)
    _forge_duplicate_decision(cycle_store, cycle_second.entry_id, cycle_first.entry_id)
    with pytest.raises(EdgeBacklogIntegrityError, match="canonicalization contains a cycle"):
        cycle_store.validate()


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


def test_snapshot_rejects_candidate_contradicting_evidence_added_after_capture(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    candidate_observation = _capture(store, "obs.snapshot.candidate")
    query_observation = _capture(store, "obs.snapshot.adversarial-query")
    candidate = _create(store, "edge.snapshot.candidate", candidate_observation)
    query = _create(store, "edge.snapshot.adversarial-query", query_observation)
    stale = store.duplicate_snapshot(query.entry_id)
    stale_candidate = next(item for item in stale["candidates"] if item["candidate_id"] == candidate.entry_id)
    assert stale_candidate["candidate_record_sha256"] == candidate.record_sha256

    contradiction = _capture(
        store,
        "obs.snapshot.contradiction",
        statement="A later source contradicts persistence after the opening interval.",
    )
    revised = store.revise_entry(
        candidate.entry_id,
        _entry_payload(
            candidate.entry_id,
            candidate_observation,
            observation_refs=[
                {
                    "observation_id": candidate_observation.observation_id,
                    "observation_revision_sha256": candidate_observation.record_sha256,
                    "role": "MOTIVATING",
                },
                {
                    "observation_id": contradiction.observation_id,
                    "observation_revision_sha256": contradiction.record_sha256,
                    "role": "CONTRADICTING",
                },
            ],
        ),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    current = store.duplicate_snapshot(query.entry_id)
    current_candidate = next(item for item in current["candidates"] if item["candidate_id"] == candidate.entry_id)
    assert current_candidate["candidate_record_sha256"] == revised.record_sha256
    assert current_candidate["candidate_record_sha256"] != stale_candidate["candidate_record_sha256"]

    with pytest.raises(EdgeBacklogConflictError, match="snapshot is stale"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=stale["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="This stale review predates newly captured contradicting evidence.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    assert store.validate()["status"] == "PASS"


def test_snapshot_binds_candidate_disposition_and_link_chain(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    candidate_observation = _capture(store, "obs.snapshot.binding-candidate")
    query_observation = _capture(store, "obs.snapshot.binding-query")
    candidate = _create(store, "edge.snapshot.binding-candidate", candidate_observation)
    query = _create(store, "edge.snapshot.binding-query", query_observation)

    before_decision = store.duplicate_snapshot(query.entry_id)
    candidate_snapshot = store.duplicate_snapshot(candidate.entry_id)
    decision = store.record_human_decision(
        candidate.entry_id,
        disposition="REVIEWED_CONTINUE",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=candidate_snapshot["snapshot_sha256"],
        reason_codes=["OTHER"],
        rationale="The owner recorded non-scientific curation for snapshot binding coverage.",
        reviewer_id="owner",
        recorded_at=NOW,
    )
    after_decision = store.duplicate_snapshot(query.entry_id)
    bound = next(item for item in after_decision["candidates"] if item["candidate_id"] == candidate.entry_id)
    assert before_decision["snapshot_sha256"] != after_decision["snapshot_sha256"]
    assert bound["candidate_decision_sha256"] == decision.record_sha256

    proposal = tmp_path / "research/proposals/hypothesis.snapshot-binding.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")
    store.record_hypothesis_proposal_link(
        candidate.entry_id,
        hypothesis_id="hypothesis.snapshot-binding",
        target_locator=proposal,
        actor_id="edge-backlog-linker",
        recorded_at=NOW,
    )
    after_link = store.duplicate_snapshot(query.entry_id)
    linked = next(item for item in after_link["candidates"] if item["candidate_id"] == candidate.entry_id)
    assert after_link["snapshot_sha256"] != after_decision["snapshot_sha256"]
    assert linked["candidate_link_chain_sha256"] != bound["candidate_link_chain_sha256"]


def test_cross_process_candidate_revision_stales_snapshot_under_transaction(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    candidate_observation = _capture(store, "obs.concurrent.candidate-revision")
    query_observation = _capture(store, "obs.concurrent.query-revision")
    candidate = _create(store, "edge.concurrent.candidate-revision", candidate_observation)
    query = _create(store, "edge.concurrent.query-revision", query_observation)
    stale = store.duplicate_snapshot(query.entry_id)
    process, results = _start_locked_process(
        tmp_path,
        "revise_entry",
        {
            "entry_id": candidate.entry_id,
            "payload": _entry_payload(candidate.entry_id, candidate_observation, title="Concurrent revision"),
            "actor_id": "concurrent-codex",
            "recorded_at": NOW,
        },
    )

    with pytest.raises(EdgeBacklogConflictError, match="snapshot is stale"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=stale["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="The concurrent candidate revision must invalidate this captured snapshot.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    _assert_process_passed(process, results)
    assert store.latest_entry(candidate.entry_id).revision == 2
    assert not (store.root / f"entries/{query.entry_id}/decisions/000001.json").exists()


def test_cross_process_contradicting_evidence_stales_snapshot_under_transaction(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    candidate_observation = _capture(store, "obs.concurrent.candidate-contradiction")
    contradiction = _capture(
        store,
        "obs.concurrent.contradiction",
        statement="A later sample contradicts the persistence claim.",
    )
    query_observation = _capture(store, "obs.concurrent.query-contradiction")
    candidate = _create(store, "edge.concurrent.candidate-contradiction", candidate_observation)
    query = _create(store, "edge.concurrent.query-contradiction", query_observation)
    stale = store.duplicate_snapshot(query.entry_id)
    process, results = _start_locked_process(
        tmp_path,
        "revise_entry",
        {
            "entry_id": candidate.entry_id,
            "payload": _entry_payload(
                candidate.entry_id,
                candidate_observation,
                observation_refs=[
                    {
                        "observation_id": candidate_observation.observation_id,
                        "observation_revision_sha256": candidate_observation.record_sha256,
                        "role": "MOTIVATING",
                    },
                    {
                        "observation_id": contradiction.observation_id,
                        "observation_revision_sha256": contradiction.record_sha256,
                        "role": "CONTRADICTING",
                    },
                ],
            ),
            "actor_id": "concurrent-codex",
            "recorded_at": NOW,
        },
    )

    with pytest.raises(EdgeBacklogConflictError, match="snapshot is stale"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=stale["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="Concurrent contradicting evidence invalidates this captured snapshot.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    _assert_process_passed(process, results)
    assert not (store.root / f"entries/{query.entry_id}/decisions/000001.json").exists()


def test_cross_process_candidate_decision_stales_snapshot_under_transaction(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    candidate_observation = _capture(store, "obs.concurrent.candidate-decision")
    query_observation = _capture(store, "obs.concurrent.query-decision")
    candidate = _create(store, "edge.concurrent.candidate-decision", candidate_observation)
    query = _create(store, "edge.concurrent.query-decision", query_observation)
    stale = store.duplicate_snapshot(query.entry_id)
    candidate_snapshot = store.duplicate_snapshot(candidate.entry_id)
    process, results = _start_locked_process(
        tmp_path,
        "record_decision",
        {
            "entry_id": candidate.entry_id,
            "disposition": "REVIEWED_CONTINUE",
            "duplicate_resolution": "DISTINCT_EDGE",
            "candidate_snapshot_sha256": candidate_snapshot["snapshot_sha256"],
            "reason_codes": ["OTHER"],
            "rationale": "Concurrent human curation changes the candidate revision identity.",
            "reviewer_id": "owner",
            "recorded_at": NOW,
        },
    )

    with pytest.raises(EdgeBacklogConflictError, match="snapshot is stale"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=stale["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="The concurrent candidate decision must invalidate this snapshot.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    _assert_process_passed(process, results)
    assert len(store.decisions(candidate.entry_id)) == 1


def test_cross_process_candidate_link_stales_snapshot_under_transaction(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    candidate_observation = _capture(store, "obs.concurrent.candidate-link")
    query_observation = _capture(store, "obs.concurrent.query-link")
    candidate = _create(store, "edge.concurrent.candidate-link", candidate_observation)
    query = _create(store, "edge.concurrent.query-link", query_observation)
    proposal = tmp_path / "research/proposals/hypothesis.concurrent-link.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")
    stale = store.duplicate_snapshot(query.entry_id)
    process, results = _start_locked_process(
        tmp_path,
        "record_proposal_link",
        {
            "entry_id": candidate.entry_id,
            "hypothesis_id": "hypothesis.concurrent-link",
            "target_locator": proposal,
            "actor_id": "concurrent-linker",
            "recorded_at": NOW,
        },
    )

    with pytest.raises(EdgeBacklogConflictError, match="snapshot is stale"):
        store.record_human_decision(
            query.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=stale["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="The concurrent candidate link must invalidate this snapshot.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    _assert_process_passed(process, results)
    assert len(store.links(candidate.entry_id)) == 1


def test_cross_process_competing_entry_appends_allocate_one_linear_chain(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.concurrent.appends")
    entry = _create(store, "edge.concurrent.appends", observation)
    process, results = _start_locked_process(
        tmp_path,
        "revise_entry",
        {
            "entry_id": entry.entry_id,
            "payload": _entry_payload(entry.entry_id, observation, title="Child append"),
            "actor_id": "child-codex",
            "recorded_at": NOW,
        },
    )

    parent = store.revise_entry(
        entry.entry_id,
        _entry_payload(entry.entry_id, observation, title="Parent append"),
        actor_id="parent-codex",
        recorded_at=NOW,
    )
    child_sha256 = _assert_process_passed(process, results)
    revisions = store._all_entry_revisions(entry.entry_id)
    assert [item.revision for item in revisions] == [1, 2, 3]
    assert revisions[1].record_sha256 == child_sha256
    assert parent.revision == 3
    assert parent.previous_revision_sha256 == child_sha256
    assert store.validate()["status"] == "PASS"


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


@pytest.mark.parametrize("disposition", ["REJECTED", "DUPLICATE"])
def test_terminal_source_entry_is_fully_sealed_against_links_and_forged_suffix(
    tmp_path: Path,
    disposition: str,
) -> None:
    store = EdgeBacklogStore(tmp_path)
    source_observation = _capture(store, f"obs.lifecycle.{disposition.lower()}.source")
    target_observation = _capture(store, f"obs.lifecycle.{disposition.lower()}.target")
    source = _create(store, f"edge.lifecycle.{disposition.lower()}.source", source_observation)
    target = _create(store, f"edge.lifecycle.{disposition.lower()}.target", target_observation)
    snapshot = store.duplicate_snapshot(source.entry_id)
    decision = store.record_human_decision(
        source.entry_id,
        disposition=disposition,
        duplicate_resolution="SAME_EDGE" if disposition == "DUPLICATE" else "DISTINCT_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        canonical_entry_id=target.entry_id if disposition == "DUPLICATE" else None,
        reason_codes=["DUPLICATE_EDGE" if disposition == "DUPLICATE" else "CAUSAL_WEAKNESS"],
        rationale="The terminal source entry must be completely immutable.",
        reviewer_id="owner",
        recorded_at=NOW,
    )
    proposal = tmp_path / f"research/proposals/hypothesis.{disposition.lower()}.json"
    proposal.parent.mkdir(parents=True, exist_ok=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")

    with pytest.raises(EdgeBacklogConflictError, match=f"while {disposition}"):
        store.record_hypothesis_proposal_link(
            source.entry_id,
            hypothesis_id=f"hypothesis.{disposition.lower()}",
            target_locator=proposal,
            actor_id="linker",
            recorded_at=NOW + timedelta(minutes=1),
        )
    with pytest.raises(EdgeBacklogConflictError, match="cannot append a link"):
        store.record_revisit_link(
            source.entry_id,
            prior_entry_id=target.entry_id,
            rationale="A terminal entry cannot acquire later revisit lineage.",
            reviewer_id="owner",
            recorded_at=NOW + timedelta(minutes=1),
        )

    target_bytes = proposal.read_bytes()
    forged_payload = {
        "schema": "alphaquest.edge-backlog-link/v1",
        "record_id": f"link.forged.{disposition.lower()}",
        "link_id": f"link.forged.{disposition.lower()}",
        "entry_id": source.entry_id,
        "entry_revision_sha256": source.record_sha256,
        "sequence": 1,
        "previous_link_sha256": None,
        "relationship": "HYPOTHESIS_PROPOSAL",
        "target_kind": "HYPOTHESIS",
        "target_id": f"hypothesis.{disposition.lower()}",
        "target_locator": str(proposal.relative_to(tmp_path)),
        "target_payload_sha256": hashlib.sha256(target_bytes).hexdigest(),
        "authorizing_decision_id": None,
        "rationale": None,
        "recorded_at": (NOW + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "actor": {
            "actor_class": "ALPHAQUEST_DETERMINISTIC_ENGINE",
            "actor_id": "forger",
            "task_id": None,
        },
    }
    forged_payload["record_sha256"] = record_sha256(forged_payload)
    forged = EdgeBacklogLinkV1.model_validate(forged_payload)
    forged_path = store.root / f"entries/{source.entry_id}/links/000001.json"
    forged_path.parent.mkdir(parents=True)
    forged_path.write_bytes(canonical_json_bytes(forged) + b"\n")

    assert decision.entry_link_chain_sha256 != forged.record_sha256
    with pytest.raises(EdgeBacklogIntegrityError, match="terminal decision does not seal the complete link history"):
        store.validate()


def test_suspended_source_accepts_only_resume_until_resume_is_persisted(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    source_observation = _capture(store, "obs.lifecycle.suspended.source")
    prior_observation = _capture(store, "obs.lifecycle.suspended.prior")
    source = _create(store, "edge.lifecycle.suspended.source", source_observation)
    prior = _create(store, "edge.lifecycle.suspended.prior", prior_observation)
    snapshot = store.duplicate_snapshot(source.entry_id)
    suspension = store.record_human_decision(
        source.entry_id,
        disposition="SUSPENDED",
        duplicate_resolution="UNRESOLVED",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["TEMPORARY_BLOCKER"],
        rationale="The source entry is sealed until an explicit human resume.",
        revisit_conditions=["The blocker is resolved."],
        reviewer_id="owner",
        recorded_at=NOW,
    )
    suspension_path = store.root / f"entries/{source.entry_id}/decisions/000001.json"
    suspension_bytes = suspension_path.read_bytes()
    proposal = tmp_path / "research/proposals/hypothesis.suspended.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")

    with pytest.raises(EdgeBacklogConflictError, match="while SUSPENDED"):
        store.record_hypothesis_proposal_link(
            source.entry_id,
            hypothesis_id="hypothesis.suspended",
            target_locator=proposal,
            actor_id="linker",
            recorded_at=NOW,
        )
    with pytest.raises(EdgeBacklogConflictError, match="cannot append a link while SUSPENDED"):
        store.record_revisit_link(
            source.entry_id,
            prior_entry_id=prior.entry_id,
            rationale="Suspension prohibits this lineage append.",
            reviewer_id="owner",
            recorded_at=NOW,
        )
    with pytest.raises(EdgeBacklogConflictError, match="suspended; resume it"):
        store.record_human_decision(
            source.entry_id,
            disposition="REJECTED",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=snapshot["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="No decision except RESUMED may follow suspension.",
            reviewer_id="owner",
            recorded_at=NOW,
        )

    resumed = store.resume_entry(
        source.entry_id,
        reason_codes=["NEW_INFORMATION"],
        rationale="The owner explicitly resumed the source entry.",
        reviewer_id="owner",
        recorded_at=NOW,
    )
    assert resumed.previous_decision_sha256 == suspension.record_sha256
    assert suspension_path.read_bytes() == suspension_bytes
    assert store.validate()["status"] == "PASS"


def test_full_validation_rejects_entry_and_link_changes_inside_suspended_interval(tmp_path: Path) -> None:
    entry_store = EdgeBacklogStore(tmp_path / "entry")
    observation = _capture(entry_store, "obs.lifecycle.interval.entry")
    entry = _create(entry_store, "edge.lifecycle.interval.entry", observation)
    snapshot = entry_store.duplicate_snapshot(entry.entry_id)
    entry_store.record_human_decision(
        entry.entry_id,
        disposition="SUSPENDED",
        duplicate_resolution="UNRESOLVED",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["TEMPORARY_BLOCKER"],
        rationale="Suspend before the adversarial interval test.",
        revisit_conditions=["The blocker is resolved."],
        reviewer_id="owner",
        recorded_at=NOW,
    )
    entry_store.resume_entry(
        entry.entry_id,
        reason_codes=["NEW_INFORMATION"],
        rationale="Resume before the legitimate later revision.",
        reviewer_id="owner",
        recorded_at=NOW + timedelta(minutes=2),
    )
    entry_store.revise_entry(
        entry.entry_id,
        _entry_payload(entry.entry_id, observation, title="Legitimate post-resume revision"),
        actor_id="codex",
        recorded_at=NOW + timedelta(minutes=3),
    )
    entry_path = entry_store.root / f"entries/{entry.entry_id}/revisions/000002.json"
    entry_payload = json.loads(entry_path.read_text(encoding="utf-8"))
    entry_payload["recorded_at"] = (NOW + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    _rewrite_record(entry_path, entry_payload)
    with pytest.raises(EdgeBacklogIntegrityError, match="later entry revision is backdated"):
        entry_store.validate()

    link_store = EdgeBacklogStore(tmp_path / "link")
    link_observation = _capture(link_store, "obs.lifecycle.interval.link")
    link_entry = _create(link_store, "edge.lifecycle.interval.link", link_observation)
    link_snapshot = link_store.duplicate_snapshot(link_entry.entry_id)
    link_store.record_human_decision(
        link_entry.entry_id,
        disposition="SUSPENDED",
        duplicate_resolution="UNRESOLVED",
        candidate_snapshot_sha256=link_snapshot["snapshot_sha256"],
        reason_codes=["TEMPORARY_BLOCKER"],
        rationale="Suspend before the adversarial link interval test.",
        revisit_conditions=["The blocker is resolved."],
        reviewer_id="owner",
        recorded_at=NOW,
    )
    link_store.resume_entry(
        link_entry.entry_id,
        reason_codes=["NEW_INFORMATION"],
        rationale="Resume before the legitimate later link.",
        reviewer_id="owner",
        recorded_at=NOW + timedelta(minutes=2),
    )
    proposal = link_store.project_root / "research/proposals/hypothesis.interval.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")
    link_store.record_hypothesis_proposal_link(
        link_entry.entry_id,
        hypothesis_id="hypothesis.interval",
        target_locator=proposal,
        actor_id="linker",
        recorded_at=NOW + timedelta(minutes=3),
    )
    link_path = link_store.root / f"entries/{link_entry.entry_id}/links/000001.json"
    link_payload = json.loads(link_path.read_text(encoding="utf-8"))
    link_payload["recorded_at"] = (NOW + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    _rewrite_record(link_path, link_payload)
    with pytest.raises(EdgeBacklogIntegrityError, match="later link is backdated"):
        link_store.validate()


def test_all_append_chains_reject_backdated_records_before_write(tmp_path: Path) -> None:
    earlier = NOW - timedelta(minutes=1)
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.chronology")
    entry = _create(store, "edge.chronology", observation)

    with pytest.raises(EdgeBacklogConflictError, match="observation revision recorded_at"):
        store.revise_observation(
            observation.observation_id,
            _observation_payload(observation.observation_id, statement="Backdated observation revision."),
            actor_id="codex-task-runner",
            recorded_at=earlier,
        )
    assert not (store.root / "observations/obs.chronology/revisions/000002.json").exists()

    with pytest.raises(EdgeBacklogConflictError, match="entry revision recorded_at"):
        store.revise_entry(
            entry.entry_id,
            _entry_payload(entry.entry_id, observation, title="Backdated entry revision"),
            actor_id="codex-task-runner",
            recorded_at=earlier,
        )
    assert not (store.root / "entries/edge.chronology/revisions/000002.json").exists()

    snapshot = store.duplicate_snapshot(entry.entry_id)
    store.record_human_decision(
        entry.entry_id,
        disposition="SUSPENDED",
        duplicate_resolution="UNRESOLVED",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["TEMPORARY_BLOCKER"],
        rationale="A temporary blocker requires a later human resume.",
        revisit_conditions=["The blocker is resolved."],
        reviewer_id="owner",
        recorded_at=NOW,
    )
    with pytest.raises(EdgeBacklogConflictError, match="decision recorded_at"):
        store.resume_entry(
            entry.entry_id,
            reason_codes=["NEW_INFORMATION"],
            rationale="This backdated resume must be rejected.",
            reviewer_id="owner",
            recorded_at=earlier,
        )
    assert not (store.root / "entries/edge.chronology/decisions/000002.json").exists()

    link_store = EdgeBacklogStore(tmp_path / "links")
    link_observation = _capture(link_store, "obs.chronology.links")
    link_entry = _create(link_store, "edge.chronology.links", link_observation)
    for suffix in ("one", "two"):
        target = link_store.project_root / f"research/proposals/hypothesis.chronology.{suffix}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")
    link_store.record_hypothesis_proposal_link(
        link_entry.entry_id,
        hypothesis_id="hypothesis.chronology.one",
        target_locator="research/proposals/hypothesis.chronology.one.json",
        actor_id="edge-backlog-linker",
        recorded_at=NOW,
    )
    with pytest.raises(EdgeBacklogConflictError, match="link recorded_at"):
        link_store.record_hypothesis_proposal_link(
            link_entry.entry_id,
            hypothesis_id="hypothesis.chronology.two",
            target_locator="research/proposals/hypothesis.chronology.two.json",
            actor_id="edge-backlog-linker",
            recorded_at=earlier,
        )
    assert not (link_store.root / "entries/edge.chronology.links/links/000002.json").exists()


def test_full_validation_rejects_backdated_chain_history(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.chronology.tamper")
    store.revise_observation(
        observation.observation_id,
        _observation_payload(observation.observation_id, statement="A valid same-time revision."),
        actor_id="codex-task-runner",
        recorded_at=NOW,
    )
    path = store.root / "observations/obs.chronology.tamper/revisions/000002.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["recorded_at"] = (NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    _rewrite_record(path, payload)
    with pytest.raises(EdgeBacklogIntegrityError, match="chronology moved backward"):
        store.validate()


def test_decision_binds_an_exact_historical_link_chain_prefix(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.link-prefix")
    entry = _create(store, "edge.link-prefix", observation)
    proposals = []
    for suffix in ("before", "after"):
        proposal = tmp_path / f"research/proposals/hypothesis.link-prefix.{suffix}.json"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")
        proposals.append(proposal)
    first_link = store.record_hypothesis_proposal_link(
        entry.entry_id,
        hypothesis_id="hypothesis.link-prefix.before",
        target_locator=proposals[0],
        actor_id="linker",
        recorded_at=NOW,
    )
    snapshot = store.duplicate_snapshot(entry.entry_id)
    decision = store.record_human_decision(
        entry.entry_id,
        disposition="REVIEWED_CONTINUE",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["OTHER"],
        rationale="The decision binds exactly the link prefix visible at review time.",
        reviewer_id="owner",
        recorded_at=NOW,
    )
    store.record_hypothesis_proposal_link(
        entry.entry_id,
        hypothesis_id="hypothesis.link-prefix.after",
        target_locator=proposals[1],
        actor_id="linker",
        recorded_at=NOW,
    )
    assert decision.entry_link_chain_sha256 == hashlib.sha256(
        canonical_json_bytes([first_link.record_sha256])
    ).hexdigest()
    assert store.validate()["status"] == "PASS"

    decision_path = store.root / f"entries/{entry.entry_id}/decisions/000001.json"
    forged = json.loads(decision_path.read_text(encoding="utf-8"))
    forged["entry_link_chain_sha256"] = "f" * 64
    snapshot_core = {
        "schema": "alphaquest.edge-backlog-duplicate-snapshot/v1",
        "entry_id": forged["entry_id"],
        "entry_revision_sha256": forged["entry_revision_sha256"],
        "entry_link_chain_sha256": forged["entry_link_chain_sha256"],
        "candidates": forged["candidate_snapshot"],
    }
    forged["candidate_snapshot_sha256"] = hashlib.sha256(canonical_json_bytes(snapshot_core)).hexdigest()
    _rewrite_record(decision_path, forged)
    with pytest.raises(EdgeBacklogIntegrityError, match="not an exact historical prefix"):
        store.validate()


def test_cross_record_causal_chronology_rejects_backdating_before_write(tmp_path: Path) -> None:
    observation_store = EdgeBacklogStore(tmp_path / "observation")
    observation = observation_store.capture_observation(
        _observation_payload("obs.causal.entry"),
        actor_id="codex",
        recorded_at=NOW + timedelta(minutes=2),
    )
    entry_path = observation_store.root / "entries/edge.causal.entry/revisions/000001.json"
    with pytest.raises(EdgeBacklogIntegrityError, match="entry precedes referenced observation"):
        observation_store.create_entry(
            _entry_payload("edge.causal.entry", observation),
            actor_id="codex",
            recorded_at=NOW + timedelta(minutes=1),
        )
    assert not entry_path.exists()

    decision_store = EdgeBacklogStore(tmp_path / "decision")
    decision_observation = _capture(decision_store, "obs.causal.decision")
    decision_entry = decision_store.create_entry(
        _entry_payload("edge.causal.decision", decision_observation),
        actor_id="codex",
        recorded_at=NOW + timedelta(minutes=2),
    )
    decision_snapshot = decision_store.duplicate_snapshot(decision_entry.entry_id)
    with pytest.raises(EdgeBacklogIntegrityError, match="decision precedes its bound entry revision"):
        decision_store.record_human_decision(
            decision_entry.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=decision_snapshot["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="A decision cannot be recorded before its bound entry revision.",
            reviewer_id="owner",
            recorded_at=NOW + timedelta(minutes=1),
        )
    assert not (decision_store.root / f"entries/{decision_entry.entry_id}/decisions/000001.json").exists()

    link_store = EdgeBacklogStore(tmp_path / "link")
    link_observation = _capture(link_store, "obs.causal.link")
    link_entry = link_store.create_entry(
        _entry_payload("edge.causal.link", link_observation),
        actor_id="codex",
        recorded_at=NOW + timedelta(minutes=2),
    )
    proposal = link_store.project_root / "research/proposals/hypothesis.causal-link.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"schema":"alphaquest.hypothesis-proposal/v1"}\n', encoding="utf-8")
    with pytest.raises(EdgeBacklogIntegrityError, match="link precedes its bound entry revision"):
        link_store.record_hypothesis_proposal_link(
            link_entry.entry_id,
            hypothesis_id="hypothesis.causal-link",
            target_locator=proposal,
            actor_id="linker",
            recorded_at=NOW + timedelta(minutes=1),
        )
    assert not (link_store.root / f"entries/{link_entry.entry_id}/links/000001.json").exists()


def test_authorized_link_and_post_resume_change_cannot_precede_authority(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    prior_observation = _capture(store, "obs.causal.authority.prior")
    source_observation = _capture(store, "obs.causal.authority.source")
    prior = _create(store, "edge.causal.authority.prior", prior_observation)
    source = _create(store, "edge.causal.authority.source", source_observation)
    prior_snapshot = store.duplicate_snapshot(prior.entry_id)
    authorization = store.record_human_decision(
        prior.entry_id,
        disposition="REJECTED",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=prior_snapshot["snapshot_sha256"],
        reason_codes=["CAUSAL_WEAKNESS"],
        rationale="The historical disposition authorizes only a later revisit record.",
        reviewer_id="owner",
        recorded_at=NOW + timedelta(minutes=2),
    )
    with pytest.raises(EdgeBacklogIntegrityError, match="link precedes its authorizing decision"):
        store.record_revisit_link(
            source.entry_id,
            prior_entry_id=prior.entry_id,
            authorizing_decision_id=authorization.decision_id,
            rationale="This backdated authorized revisit must fail closed.",
            reviewer_id="owner",
            recorded_at=NOW + timedelta(minutes=1),
        )
    assert not (store.root / f"entries/{source.entry_id}/links/000001.json").exists()

    resume_store = EdgeBacklogStore(tmp_path / "resume")
    resume_observation = _capture(resume_store, "obs.causal.resume")
    resume_entry = _create(resume_store, "edge.causal.resume", resume_observation)
    resume_snapshot = resume_store.duplicate_snapshot(resume_entry.entry_id)
    resume_store.record_human_decision(
        resume_entry.entry_id,
        disposition="SUSPENDED",
        duplicate_resolution="UNRESOLVED",
        candidate_snapshot_sha256=resume_snapshot["snapshot_sha256"],
        reason_codes=["TEMPORARY_BLOCKER"],
        rationale="Suspend before testing causal resume chronology.",
        revisit_conditions=["The blocker is resolved."],
        reviewer_id="owner",
        recorded_at=NOW,
    )
    resume_store.resume_entry(
        resume_entry.entry_id,
        reason_codes=["NEW_INFORMATION"],
        rationale="Resume at the authoritative later timestamp.",
        reviewer_id="owner",
        recorded_at=NOW + timedelta(minutes=2),
    )
    with pytest.raises(EdgeBacklogConflictError, match="cannot precede the latest decision"):
        resume_store.revise_entry(
            resume_entry.entry_id,
            _entry_payload(resume_entry.entry_id, resume_observation, title="Backdated after resume"),
            actor_id="codex",
            recorded_at=NOW + timedelta(minutes=1),
        )
    assert not (resume_store.root / f"entries/{resume_entry.entry_id}/revisions/000002.json").exists()


def test_full_validation_rejects_entry_forged_before_referenced_observation(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = store.capture_observation(
        _observation_payload("obs.causal.forged-entry"),
        actor_id="codex",
        recorded_at=NOW + timedelta(minutes=1),
    )
    entry = store.create_entry(
        _entry_payload("edge.causal.forged-entry", observation),
        actor_id="codex",
        recorded_at=NOW + timedelta(minutes=2),
    )
    path = store.root / f"entries/{entry.entry_id}/revisions/000001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["recorded_at"] = NOW.isoformat().replace("+00:00", "Z")
    _rewrite_record(path, payload)

    with pytest.raises(EdgeBacklogIntegrityError, match="entry precedes referenced observation"):
        store.validate()


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


@pytest.mark.parametrize(
    "prohibited_content",
    [
        "Use RSI to define the opportunity.",
        "Apply a parameter grid over the observation.",
        "Require a threshold of 2.5 before acting.",
        "Enter when the completed interval closes.",
        "Attach a protective stop to the expression.",
        "Set a profit target at 10 points.",
    ],
)
def test_economic_edge_boundary_rejects_mechanics_hidden_in_accepted_free_text(
    tmp_path: Path,
    prohibited_content: str,
) -> None:
    store = EdgeBacklogStore(tmp_path)
    observation = _capture(store, "obs.semantic-boundary")
    payload = _entry_payload("edge.semantic-boundary", observation, market_behavior=prohibited_content)

    with pytest.raises(ValidationError, match="must remain economic-edge-only"):
        store.create_entry(payload, actor_id="codex", recorded_at=NOW)
    assert not (store.root / "entries/edge.semantic-boundary/revisions/000001.json").exists()


def test_economic_edge_boundary_rejects_forged_mechanics_and_observation_instructions(tmp_path: Path) -> None:
    store = EdgeBacklogStore(tmp_path)
    with pytest.raises(ValidationError, match="must remain economic-edge-only"):
        store.capture_observation(
            _observation_payload(
                "obs.semantic-instruction",
                statement="The researcher should exit when price reaches the profit target.",
            ),
            actor_id="codex",
            recorded_at=NOW,
        )

    observation = _capture(store, "obs.semantic-forgery")
    entry = _create(store, "edge.semantic-forgery", observation)
    path = store.root / f"entries/{entry.entry_id}/revisions/000001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["open_questions"] = ["Should the entry use MACD with a trailing stop?"]
    _rewrite_record(path, payload)
    with pytest.raises(EdgeBacklogIntegrityError, match="must remain economic-edge-only"):
        store.validate()


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


def test_campaign_and_backlog_adapters_use_the_same_matcher_core(tmp_path: Path, monkeypatch) -> None:
    score_schemas: list[str] = []
    rank_identities: list[str] = []
    original_score = duplicate_core.deterministic_duplicate_score
    original_rank = duplicate_core.rank_duplicate_candidates

    def tracked_score(**kwargs):
        score_schemas.append(str(kwargs["taxonomy_schema"]))
        return original_score(**kwargs)

    def tracked_rank(candidates, **kwargs):
        rank_identities.append(str(kwargs["identity_field"]))
        return original_rank(candidates, **kwargs)

    monkeypatch.setattr(duplicate_core, "deterministic_duplicate_score", tracked_score)
    monkeypatch.setattr(duplicate_core, "rank_duplicate_candidates", tracked_rank)

    campaign = tmp_path / "research/campaigns/active/shared_core_prior"
    campaign.mkdir(parents=True)
    campaign.joinpath("campaign.yaml").write_text(
        "campaign_id: shared_core_prior\n"
        "title: Opening range continuation\n"
        "hypothesis: Opening range breakouts persist\n"
        "expected_mechanism: delayed inventory hedging\n",
        encoding="utf-8",
    )
    assert duplicate_matches(
        project_root=tmp_path,
        campaign_id="shared_core_new",
        title="Opening range continuation",
        hypothesis="Opening range breakouts persist",
        expected_mechanism="delayed inventory hedging",
    )

    store = EdgeBacklogStore(tmp_path)
    first_observation = _capture(store, "obs.shared-core.first")
    second_observation = _capture(store, "obs.shared-core.second")
    _create(store, "edge.shared-core.first", first_observation)
    second = _create(store, "edge.shared-core.second", second_observation)
    assert store.duplicate_candidates(second.entry_id)

    assert "alphaquest.duplicate-taxonomy/v1" in score_schemas
    assert "alphaquest.edge-backlog-duplicate-taxonomy/v1" in score_schemas
    assert rank_identities == ["campaign_id", "candidate_id"]


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
