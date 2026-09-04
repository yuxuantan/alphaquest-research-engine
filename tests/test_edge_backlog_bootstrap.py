from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from alphaquest.cli import main
from alphaquest.research.edge_backlog import (
    DuplicateCandidateV1,
    EdgeBacklogIntegrityError,
    EdgeBacklogStore,
    canonical_json_bytes,
    record_sha256,
)
from alphaquest.research.edge_backlog_bootstrap import (
    HistoricalEdgeIndexRecordV1,
    build_historical_edge_index,
    validate_historical_edge_index,
)


def _fixture(root: Path) -> dict[str, bytes]:
    current = root / "research/campaigns/active/current_auction_edge/campaign.yaml"
    current.parent.mkdir(parents=True)
    current.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "current_auction_edge",
                "title": "Current auction edge",
                "instrument": "ES",
                "timeframe": "1m",
                "hypothesis": "Opening auction pressure persists because dealers hedge slowly.",
                "edge_family": "auction_pressure",
                "economic_edge_fingerprint": {
                    "market_behavior": "opening auction pressure persists",
                    "causal_mechanism": "dealers hedge slowly",
                    "signal_inputs": ["opening pressure"],
                    "market_context": "regular trading hours",
                    "holding_period": "intraday minutes",
                },
                "decision": "ACTIVE",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    configured_archive = root / "research/campaigns/archive/configured_archive_edge/campaign.yaml"
    configured_archive.parent.mkdir(parents=True)
    configured_archive.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "configured_archive_edge",
                "title": "Configured archive edge",
                "instrument": "ES",
                "timeframe": "intraday minutes",
                "edge": "Opening auction pressure persists",
                "hypothesis": "Dealers hedge slowly after price discovery",
                "counterparty_transfer_rationale": "Late hedgers pay patient liquidity providers",
                "information_availability": "After the completed opening interval",
                "expected_effect": "Continuation after opening pressure",
                "economic_edge_fingerprint": {
                    "market_behavior": "opening auction pressure persists",
                    "causal_mechanism": "dealers hedge slowly",
                    "signal_inputs": ["opening pressure"],
                    "market_context": "regular trading hours",
                    "holding_period": "intraday minutes",
                },
                "decision": "ARCHIVED",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    archived = (
        root / "research/archived_generations/clean_slate_fixture/campaigns/archive/failed_auction_edge/campaign.yaml"
    )
    archived.parent.mkdir(parents=True)
    archived.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "failed_auction_edge",
                "title": "Renamed opening pressure strategy",
                "symbol": "ES",
                "timeframe": "1m",
                "hypothesis": "Auction pressure continues while market makers complete delayed hedging.",
                "edge_family": "abandoned_auction_pressure",
                "decision": "ABANDONED",
                "result_summary": {
                    "verdict": "FAIL",
                    "failure_reason": "The economic expression did not survive the historical robustness gates.",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    root_ledger = root / "research_ledger.csv"
    root_ledger.write_text(
        "campaign_id,variant_id,instrument,timeframe,edge,result,failure_reason\n"
        "current_auction_edge,v01,ES,1m,Opening auction pressure persistence,FAIL,Failed current fixture\n",
        encoding="utf-8",
    )
    archive_ledger = root / "research/archived_generations/clean_slate_fixture/research_ledger.csv"
    archive_ledger.write_text(
        "campaign_id,variant_id,instrument,timeframe,edge,result,failure_reason\n"
        "failed_auction_edge,v01,ES,1m,Opening auction pressure continuation,FAIL,Failed archived fixture\n",
        encoding="utf-8",
    )
    governance = root / "research_artifacts/governance"
    governance.mkdir(parents=True)
    experiment = governance / "experiment_registry.jsonl"
    experiment.write_text(
        json.dumps(
            {
                "campaign_id": "failed_auction_edge",
                "variant_id": "v01",
                "attempt_id": "original",
                "economic_edge_fingerprint_sha256": "a" * 64,
                "status": "FAILED",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reset = governance / "research_reset_fixture.json"
    reset.write_text('{"status":"COMPLETE"}\n', encoding="utf-8")
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in (current, configured_archive, archived, root_ledger, archive_ledger, experiment, reset)
    }


def _canonical_entry(store: EdgeBacklogStore) -> None:
    observation = store.capture_observation(
        {
            "observation_id": "obs.bootstrap",
            "statement": "Opening-auction pressure was observed to persist after the interval.",
            "evidence_refs": [
                {
                    "source_id": "source.bootstrap",
                    "source_kind": "PAPER",
                    "locator": "doi:10/bootstrap",
                    "claim_locator": "result-one",
                    "evidence_time": "2026-09-01T00:00:00Z",
                    "integrity": "LOCATOR_ONLY",
                    "content_sha256": None,
                }
            ],
            "known_conflicts": [],
        },
        actor_id="codex",
    )
    store.create_entry(
        {
            "entry_id": "edge.bootstrap",
            "title": "Another name for auction continuation",
            "instruments": ["ES"],
            "market_behavior": "Opening auction pressure persists",
            "causal_mechanism": "Liquidity providers complete delayed hedging",
            "counterparty_transfer_rationale": "Late hedgers transfer returns to patient liquidity",
            "information_inputs": ["opening pressure"],
            "information_availability": "Available after the opening interval completes",
            "expected_effect": "Continuation",
            "holding_horizon": "Intraday minutes",
            "market_context": "Regular trading hours",
            "observation_refs": [
                {
                    "observation_id": observation.observation_id,
                    "observation_revision_sha256": observation.record_sha256,
                    "role": "MOTIVATING",
                }
            ],
            "open_questions": [],
        },
        actor_id="codex",
    )


def _index_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_index_rows(path: Path, rows: list[dict]) -> None:
    path.write_bytes(b"".join(canonical_json_bytes(row) + b"\n" for row in rows))


def _reseal_index_row(row: dict) -> None:
    row["record_sha256"] = record_sha256(row)


def test_bootstrap_is_byte_stable_read_only_and_preserves_generation(tmp_path: Path) -> None:
    source_bytes = _fixture(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _canonical_entry(store)
    canonical_before = {str(path.relative_to(tmp_path)): path.read_bytes() for path in store.root.rglob("*.json")}

    first = build_historical_edge_index(tmp_path)
    index = tmp_path / "catalogs/edge_backlog_history.jsonl"
    first_bytes = index.read_bytes()
    second = build_historical_edge_index(tmp_path)

    assert first == second
    assert index.read_bytes() == first_bytes
    assert first["output_sha256"] == hashlib.sha256(first_bytes).hexdigest()
    assert first["records"] == 7
    assert first["historical_ineligible"] == 3
    assert first["not_current_p1_evidence"] == 7
    assert first["duplicate_recall_only"] == 7
    assert first["needs_manual_review"] == 7
    assert first["source_generation_counts"] == {
        "CURRENT": 4,
        "CONFIGURED_ARCHIVE": 1,
        "CLEAN_SLATE_ARCHIVE": 2,
    }
    assert validate_historical_edge_index(index)["status"] == "PASS"
    assert canonical_before == {
        str(path.relative_to(tmp_path)): path.read_bytes() for path in store.root.rglob("*.json")
    }
    assert source_bytes == {relative: (tmp_path / relative).read_bytes() for relative in source_bytes}

    records = [HistoricalEdgeIndexRecordV1.model_validate_json(line) for line in first_bytes.splitlines()]
    assert all(record.source_path and len(record.source_sha256) == 64 for record in records)
    archived = next(
        record
        for record in records
        if record.source_kind == "CAMPAIGN_DEFINITION" and record.campaign_id == "failed_auction_edge"
    )
    current = next(
        record
        for record in records
        if record.source_kind == "CAMPAIGN_DEFINITION" and record.campaign_id == "current_auction_edge"
    )
    assert archived.archive_generation == "clean_slate_fixture"
    assert archived.source_generation == "CLEAN_SLATE_ARCHIVE"
    assert archived.p1_evidence_eligibility == "NOT_CURRENT_P1_EVIDENCE"
    assert archived.derived_index_use == "DUPLICATE_RECALL_ONLY"
    assert archived.raw_outcome == "FAIL"
    assert archived.raw_scientific_verdict == "FAIL"
    assert archived.raw_disposition == "ABANDONED"
    assert archived.raw_failure_reason.startswith("The economic expression")
    assert archived.raw_counterparty_transfer_rationale is None
    assert archived.semantic_resolution == "NEEDS_MANUAL_REVIEW"
    configured = next(record for record in records if record.campaign_id == "configured_archive_edge")
    assert configured.source_generation == "CONFIGURED_ARCHIVE"
    assert configured.archive_generation == "research/campaigns/archive"
    assert configured.extraction_completeness == "COMPLETE"
    assert configured.semantic_resolution == "NEEDS_MANUAL_REVIEW"
    assert current.archive_generation == "CURRENT"
    assert current.source_generation == "CURRENT"
    assert current.p1_evidence_eligibility == "NOT_CURRENT_P1_EVIDENCE"
    assert current.derived_index_use == "DUPLICATE_RECALL_ONLY"
    assert current.legacy_fingerprint == {
        "market_behavior": "opening auction pressure persists",
        "causal_mechanism": "dealers hedge slowly",
        "signal_inputs": ["opening pressure"],
        "market_context": "regular trading hours",
        "holding_period": "intraday minutes",
    }


def test_failed_and_abandoned_history_participates_in_duplicate_recall(tmp_path: Path) -> None:
    _fixture(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _canonical_entry(store)
    build_historical_edge_index(tmp_path)

    candidates = store.duplicate_candidates("edge.bootstrap")
    historical = [item for item in candidates if item["candidate_kind"] == "DERIVED_HISTORICAL_RECORD"]

    assert any(item["state"] == "FAIL" for item in historical)
    assert any(item["historical_disposition"] == "ABANDONED" for item in historical)
    assert any(item["archive_generation"] == "clean_slate_fixture" for item in historical)
    assert all(item["semantic_resolution"] == "NEEDS_MANUAL_REVIEW" for item in historical)
    assert all(item["candidate_id"] == f"history:{item['candidate_record_sha256']}" for item in historical)
    assert all(len(item["candidate_record_sha256"]) == 64 for item in historical)
    assert all(item["p1_evidence_eligibility"] == "NOT_CURRENT_P1_EVIDENCE" for item in historical)
    assert all(item["derived_index_use"] == "DUPLICATE_RECALL_ONLY" for item in historical)
    assert all(
        item["exact_fingerprint"] is False for item in historical if item["archive_generation"] == "clean_slate_fixture"
    )


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_schema",
        "unknown_field",
        "invalid_record_hash",
        "invalid_source_hash",
        "duplicate_id",
        "noncanonical_order",
        "noncanonical_json",
        "p1_evidence_value",
        "derived_use_value",
        "semantic_resolution_value",
    ],
)
def test_shared_historical_index_contract_rejects_every_malformed_row(
    tmp_path: Path,
    defect: str,
) -> None:
    _fixture(tmp_path)
    build_historical_edge_index(tmp_path)
    index = tmp_path / "catalogs/edge_backlog_history.jsonl"
    rows = _index_rows(index)

    if defect == "wrong_schema":
        rows[0]["schema"] = "alphaquest.edge-backlog-history-index-record/v999"
        _reseal_index_row(rows[0])
    elif defect == "unknown_field":
        rows[0]["unreviewed_authority"] = True
        _reseal_index_row(rows[0])
    elif defect == "invalid_record_hash":
        rows[0]["record_sha256"] = "f" * 64
    elif defect == "invalid_source_hash":
        rows[0]["source_sha256"] = "not-a-sha256"
        _reseal_index_row(rows[0])
    elif defect == "duplicate_id":
        rows.append(dict(rows[0]))
    elif defect == "noncanonical_order":
        rows[0], rows[1] = rows[1], rows[0]
    elif defect == "noncanonical_json":
        index.write_text(json.dumps(rows[0], indent=2) + "\n", encoding="utf-8")
    elif defect == "p1_evidence_value":
        rows[0]["p1_evidence_eligibility"] = "CURRENT_P1_EVIDENCE"
        _reseal_index_row(rows[0])
    elif defect == "derived_use_value":
        rows[0]["derived_index_use"] = "SCIENTIFIC_EVIDENCE"
        _reseal_index_row(rows[0])
    elif defect == "semantic_resolution_value":
        rows[0]["semantic_resolution"] = "APPROVED"
        _reseal_index_row(rows[0])
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(defect)
    if defect != "noncanonical_json":
        _write_index_rows(index, rows)

    with pytest.raises(ValueError):
        validate_historical_edge_index(index)


def test_configured_history_is_strictly_validated_before_every_store_consumer(tmp_path: Path) -> None:
    _fixture(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _canonical_entry(store)
    build_historical_edge_index(tmp_path)
    snapshot = store.duplicate_snapshot("edge.bootstrap")
    index = tmp_path / "catalogs/edge_backlog_history.jsonl"
    rows = _index_rows(index)
    rows[0]["forged_semantic_promotion"] = "PASS"
    _reseal_index_row(rows[0])
    _write_index_rows(index, rows)

    with pytest.raises(EdgeBacklogIntegrityError, match="invalid configured historical"):
        store.search("auction")
    with pytest.raises(EdgeBacklogIntegrityError, match="invalid configured historical"):
        store.duplicate_snapshot("edge.bootstrap")
    with pytest.raises(EdgeBacklogIntegrityError, match="invalid configured historical"):
        store.validate()
    with pytest.raises(EdgeBacklogIntegrityError, match="invalid configured historical"):
        store.record_human_decision(
            "edge.bootstrap",
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=snapshot["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="A malformed configured history index must block decision persistence.",
            reviewer_id="owner",
        )
    assert not (store.root / "entries/edge.bootstrap/decisions/000001.json").exists()


def test_historical_duplicate_candidate_contract_is_literal_and_cross_field_bound(tmp_path: Path) -> None:
    _fixture(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _canonical_entry(store)
    build_historical_edge_index(tmp_path)
    historical = next(
        item
        for item in store.duplicate_candidates("edge.bootstrap")
        if item["candidate_kind"] == "DERIVED_HISTORICAL_RECORD"
    )

    for field, invalid in (
        ("p1_evidence_eligibility", "CURRENT_P1_EVIDENCE"),
        ("derived_index_use", "SCIENTIFIC_EVIDENCE"),
        ("semantic_resolution", "APPROVED"),
    ):
        with pytest.raises(ValueError):
            DuplicateCandidateV1.model_validate({**historical, field: invalid})
    with pytest.raises(ValueError, match="complete record_sha256"):
        DuplicateCandidateV1.model_validate(
            {**historical, "candidate_id": f"history:{historical['candidate_record_sha256'][:24]}"}
        )
    with pytest.raises(ValueError, match="canonical backlog candidates cannot carry"):
        DuplicateCandidateV1.model_validate(
            {**historical, "candidate_kind": "CANONICAL_BACKLOG_ENTRY", "candidate_id": "edge.canonical"}
        )


def test_persisted_historical_candidate_is_self_contained_after_index_rebuild(tmp_path: Path) -> None:
    _fixture(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _canonical_entry(store)
    build_historical_edge_index(tmp_path)
    snapshot = store.duplicate_snapshot("edge.bootstrap")
    historical = [
        item for item in snapshot["candidates"] if item["candidate_kind"] == "DERIVED_HISTORICAL_RECORD"
    ]
    assert historical
    assert all(item["historical_record"]["record_sha256"] == item["candidate_record_sha256"] for item in historical)
    store.record_human_decision(
        "edge.bootstrap",
        disposition="REVIEWED_CONTINUE",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["OTHER"],
        rationale="The historical candidates remain advisory and manually resolved.",
        reviewer_id="owner",
    )

    (tmp_path / "catalogs/edge_backlog_history.jsonl").write_bytes(b"")
    assert store.validate()["status"] == "PASS"


def test_bootstrap_cli_writes_only_the_configured_derived_path(tmp_path: Path, capsys) -> None:
    source_bytes = _fixture(tmp_path)

    assert main(["edge-backlog", "bootstrap-index", "--project-root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "PASS"
    assert payload["output_path"] == "catalogs/edge_backlog_history.jsonl"
    assert source_bytes == {relative: (tmp_path / relative).read_bytes() for relative in source_bytes}
    assert not (tmp_path / "research/edge_backlog/observations").exists()
    assert not (tmp_path / "research/edge_backlog/entries").exists()


def test_bootstrap_rejects_arbitrary_output_before_writing(tmp_path: Path) -> None:
    source_bytes = _fixture(tmp_path)
    arbitrary = tmp_path / "arbitrary/history.jsonl"

    with pytest.raises(ValueError, match="must equal the configured"):
        build_historical_edge_index(tmp_path, output_path=arbitrary)

    assert not arbitrary.exists()
    assert source_bytes == {relative: (tmp_path / relative).read_bytes() for relative in source_bytes}


def test_bootstrap_migrates_only_hash_valid_prior_derived_index(tmp_path: Path) -> None:
    _fixture(tmp_path)
    build_historical_edge_index(tmp_path)
    index = tmp_path / "catalogs/edge_backlog_history.jsonl"
    prior = json.loads(index.read_text(encoding="utf-8").splitlines()[0])
    prior.pop("source_generation")
    prior.pop("p1_evidence_eligibility")
    prior.pop("derived_index_use")
    prior["evidence_eligibility"] = (
        "CURRENT_SCOPE" if prior["archive_generation"] == "CURRENT" else "HISTORICAL_INELIGIBLE"
    )
    prior["semantic_resolution"] = (
        "LEGACY_CANDIDATE" if prior["extraction_completeness"] == "COMPLETE" else "NEEDS_MANUAL_REVIEW"
    )
    prior["record_sha256"] = record_sha256(prior)
    prior_bytes = json.dumps(prior, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    index.write_bytes(prior_bytes)

    result = build_historical_edge_index(tmp_path)

    assert result["status"] == "PASS"
    assert index.read_bytes() != prior_bytes
    assert validate_historical_edge_index(index)["status"] == "PASS"


@pytest.mark.parametrize("defect", ["missing_provenance", "unknown_authority_field"])
def test_bootstrap_rejects_arbitrary_self_hashed_prior_payload(
    tmp_path: Path,
    defect: str,
) -> None:
    _fixture(tmp_path)
    build_historical_edge_index(tmp_path)
    index = tmp_path / "catalogs/edge_backlog_history.jsonl"
    row = _index_rows(index)[0]
    row.pop("source_generation")
    row.pop("p1_evidence_eligibility")
    row.pop("derived_index_use")
    row["evidence_eligibility"] = (
        "CURRENT_SCOPE" if row["archive_generation"] == "CURRENT" else "HISTORICAL_INELIGIBLE"
    )
    row["semantic_resolution"] = (
        "LEGACY_CANDIDATE" if row["extraction_completeness"] == "COMPLETE" else "NEEDS_MANUAL_REVIEW"
    )
    if defect == "missing_provenance":
        row.pop("source_sha256")
    else:
        row["authority"] = "PROMOTE"
    _reseal_index_row(row)
    original = canonical_json_bytes(row) + b"\n"
    index.write_bytes(original)

    with pytest.raises(ValueError, match="not a valid derived index"):
        build_historical_edge_index(tmp_path)
    assert index.read_bytes() == original


def test_bootstrap_cannot_replace_a_source_file_or_canonical_backlog_path(tmp_path: Path) -> None:
    source_root = tmp_path / "source-target"
    source_bytes = _fixture(source_root)
    config = source_root / "config/storage_layout.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "schema: alphaquest.storage-layout/v1\n"
        "catalog_root: .\n"
        "edge_backlog_history_index: research_ledger.csv\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot replace a bootstrap source file"):
        build_historical_edge_index(source_root)
    assert source_bytes["research_ledger.csv"] == (source_root / "research_ledger.csv").read_bytes()

    canonical_root = tmp_path / "canonical-target"
    canonical_config = canonical_root / "config/storage_layout.yaml"
    canonical_config.parent.mkdir(parents=True)
    canonical_config.write_text(
        "schema: alphaquest.storage-layout/v1\n"
        "catalog_root: research\n"
        "edge_backlog_root: research/edge_backlog\n"
        "edge_backlog_history_index: research/edge_backlog/history.jsonl\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="protected canonical or research storage"):
        build_historical_edge_index(canonical_root)
    assert not (canonical_root / "research/edge_backlog/history.jsonl").exists()

    generic_source_root = tmp_path / "generic-source-target"
    generic_source = generic_source_root / "notes.txt"
    generic_source_root.mkdir()
    generic_source.write_text("human-authored research notes\n", encoding="utf-8")
    generic_config = generic_source_root / "config/storage_layout.yaml"
    generic_config.parent.mkdir(parents=True)
    generic_config.write_text(
        "schema: alphaquest.storage-layout/v1\n" "catalog_root: .\n" "edge_backlog_history_index: notes.txt\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not a valid derived index"):
        build_historical_edge_index(generic_source_root)
    assert generic_source.read_text(encoding="utf-8") == "human-authored research notes\n"


def test_configured_archive_root_takes_precedence_over_path_shape(tmp_path: Path) -> None:
    campaign = tmp_path / "research/archived_generations/custom/campaigns/archive/configured/campaign.yaml"
    campaign.parent.mkdir(parents=True)
    campaign.write_text(
        "campaign_id: configured\n"
        "title: Configured archive campaign\n"
        "edge: A previously evaluated economic edge\n",
        encoding="utf-8",
    )
    config = tmp_path / "config/storage_layout.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "schema: alphaquest.storage-layout/v1\n"
        "archive_campaign_roots:\n"
        "  - research/archived_generations/custom/campaigns/archive\n",
        encoding="utf-8",
    )

    build_historical_edge_index(tmp_path)
    records = [
        HistoricalEdgeIndexRecordV1.model_validate_json(line)
        for line in (tmp_path / "catalogs/edge_backlog_history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    configured = next(record for record in records if record.campaign_id == "configured")
    assert configured.source_generation == "CONFIGURED_ARCHIVE"
    assert configured.archive_generation == "research/archived_generations/custom/campaigns/archive"
