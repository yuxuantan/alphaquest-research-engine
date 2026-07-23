from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from alphaquest.dashboard.validation_app import save_manual_review_annotation
from alphaquest.data.source import data_source_hash
from alphaquest.studio.approvals import APPROVAL_REVIEW_SCOPE, MechanicsApprovalService
from alphaquest.studio.candidate_review import CandidateReviewService
from alphaquest.studio.results import ResultBundleBuilder
from alphaquest.validation.promotion_gate import (
    REQUIRED_AUTOMATED_CATEGORIES,
    REQUIRED_AUTOMATED_CHECK_NAMES,
    REQUIRED_SAMPLE_CATEGORIES,
    inspect_validation_gate,
)
from alphaquest.validation.schema import VALIDATION_SCHEMA_VERSION


def test_promotion_gate_resolves_missing_paths_through_configured_storage_roots(
    tmp_path: Path,
) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "custom-source/active",
                "archive_campaign_roots": ["custom-source/archive"],
                "evidence_roots": ["custom-evidence/runs"],
                "research_artifact_root": "custom-artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "custom-source/active/demo/variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    cfg = {
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "evidence_dir": "custom-evidence/runs/demo/v01/mechanics",
                "approval_path": "custom-artifacts/validation_approvals/demo/v01/approval.json",
            }
        }
    }
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    report = inspect_validation_gate(cfg, config_path, compute_input_hash=False)

    assert report["evidence_dir"] == str(tmp_path / "custom-evidence/runs/demo/v01/mechanics")
    assert report["approval_path"] == str(
        tmp_path / "custom-artifacts/validation_approvals/demo/v01/approval.json"
    )


def _validation_fixture(tmp_path):
    data = tmp_path / "bars.csv"
    data.write_text(
        "timestamp,open,high,low,close,volume\n2025-01-02T14:30:00Z,100,101,99,100.5,10\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "validation" / "evidence"
    evidence.mkdir(parents=True)
    approval = tmp_path / "validation" / "approval.json"
    config_path = tmp_path / "config.yaml"
    cfg = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "data": {"source": "csv", "raw_csv": str(data), "timezone": "America/New_York"},
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "evidence_dir": str(evidence),
                "approval_path": str(approval),
            }
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    input_hash = data_source_hash(cfg["data"])
    (evidence / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": VALIDATION_SCHEMA_VERSION,
                "validation_lane": "bar",
                "config_hash": config_hash,
                "input_data_hash": input_hash,
                "tick_size": 0.25,
            }
        ),
        encoding="utf-8",
    )
    checks = [
        {
            "check_id": f"required.{name}",
            "check_name": name,
            "category": "reconciliation",
            "status": "PASS",
            "severity": "error",
        }
        for name in sorted(REQUIRED_AUTOMATED_CHECK_NAMES)
    ]
    checks.extend(
        {
            "check_id": f"category.{category}",
            "check_name": f"{category}_coverage",
            "category": category,
            "status": "PASS",
            "severity": "error",
        }
        for category in sorted(REQUIRED_AUTOMATED_CATEGORIES - {"reconciliation"})
    )
    pd.DataFrame(checks).to_parquet(evidence / "validation_checks.parquet", index=False)
    pd.DataFrame(
        [
            {
                "trade_id": 1,
                "entry_time": "2025-01-02T14:30:00Z",
                "exit_time": "2025-01-02T14:35:00Z",
                "direction": "long",
                "r_multiple": 1.0,
                "pnl_ticks": 4,
                "was_forced_flatten": False,
            },
            {
                "trade_id": 2,
                "entry_time": "2025-01-03T14:30:00Z",
                "exit_time": "2025-01-03T14:35:00Z",
                "direction": "short",
                "r_multiple": -1.0,
                "pnl_ticks": -4,
                "was_forced_flatten": False,
            },
            {
                "trade_id": 3,
                "entry_time": "2025-01-04T14:30:00Z",
                "exit_time": "2025-01-04T14:35:00Z",
                "direction": "long",
                "r_multiple": 0.5,
                "pnl_ticks": 2,
                "was_forced_flatten": True,
            },
        ]
    ).to_parquet(evidence / "trades.parquet", index=False)
    pd.DataFrame(
        [
            {"trade_id": trade_id, "timestamp": f"2025-01-0{trade_id + 1}T14:30:00Z"}
            for trade_id in (1, 2, 3)
        ]
    ).to_parquet(evidence / "bar_windows.parquet", index=False)
    return config_path, evidence, approval


def _approve_all_samples(config_path, evidence):
    service = MechanicsApprovalService()
    initial = service.plan(config_path)
    for trade_id in initial.sampled_trade_ids:
        save_manual_review_annotation(
            evidence,
            trade_id,
            "Correct",
            "Implementation matches the frozen mechanics.",
            reviewed_at="2026-07-15T12:00:00+00:00",
        )
    return service.approve(
        config_path,
        reviewer="mechanics-reviewer",
        notes="Reviewed every required deterministic sampling category against exported evidence.",
        reviewed_at="2026-07-15T12:30:00+00:00",
    )


def test_review_plan_reuses_precomputed_gate_without_rehashing_input(tmp_path, monkeypatch):
    config_path, _evidence, _approval = _validation_fixture(tmp_path)
    service = MechanicsApprovalService()
    gate = service.inspect(config_path)
    monkeypatch.setattr(
        "alphaquest.studio.approvals.inspect_validation_gate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("gate should be reused")
        ),
    )

    plan = service.plan(config_path, _gate_report=gate)

    assert plan.input_data_hash == gate["input_data_hash"]


def test_promotion_gate_accepts_request_local_precomputed_input_hash(tmp_path, monkeypatch):
    config_path, _evidence, _approval = _validation_fixture(tmp_path)
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        "alphaquest.validation.promotion_gate.data_source_hash",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("input bytes should not be rehashed")
        ),
    )

    report = inspect_validation_gate(
        cfg,
        config_path,
        precomputed_input_hash="request-local-input-hash",
    )

    assert report["input_data_hash"] == "request-local-input-hash"


def _write_complete_finalization(result_dir, config_path):
    source_evidence = result_dir.parent / "runner-evidence.json"
    source_evidence.write_text('{"status":"complete"}\n', encoding="utf-8")
    journal_path = result_dir.parent / "candidate-test-job.recovery.json"
    journal_path.write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-recovery-journal/v1",
                "job_id": "candidate-test-job",
                "phase": "FINALIZED",
                "terminal": True,
                "automatic_replay_permitted": False,
                "events": [{"phase": "FINALIZED"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reporting_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in result_dir.iterdir()
        if path.is_file() and path.name != "finalization_manifest.json"
    }
    manifest = {
        "schema": "alphaquest.studio-finalization/v1",
        "job_id": "candidate-test-job",
        "campaign_id": "demo",
        "variant_id": "v01",
        "run_id": "run-1",
        "research_verdict": "PASS",
        "automatic_replay_permitted": False,
        "source_config": str(config_path.resolve()),
        "result_bundle": "result_bundle_v2.json",
        "evidence_issues": [],
        "evidence_artifact_sha256": {
            source_evidence.name: hashlib.sha256(source_evidence.read_bytes()).hexdigest()
        },
        "reporting_artifact_sha256": reporting_hashes,
        "ledger_recorded": True,
        "registry_published": True,
        "registry_counts": {},
        "recovery_journal": str(journal_path.resolve()),
        "terminal_recovery_phase": "FINALIZED",
        "terminal_recovery_journal_sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest(),
        "transaction_complete": True,
    }
    (result_dir / "finalization_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return result_dir / "finalization_manifest.json"


def test_mechanics_service_selects_every_category_and_requires_annotations(tmp_path):
    config_path, evidence, approval_path = _validation_fixture(tmp_path)
    service = MechanicsApprovalService()

    plan = service.plan(config_path)

    assert set(plan.sampling_categories) == set(REQUIRED_SAMPLE_CATEGORIES)
    assert plan.sampled_trade_ids
    assert plan.unreviewed_trade_ids == plan.sampled_trade_ids
    with pytest.raises(ValueError, match="remain unreviewed"):
        service.approve(config_path, reviewer="reviewer", notes="reviewed")

    approval = _approve_all_samples(config_path, evidence)
    report = service.inspect(config_path)

    assert approval_path.is_file()
    assert approval["review_scope"] == APPROVAL_REVIEW_SCOPE
    assert approval["profitability_approval"] is False
    assert report["status"] == "APPROVED_FOR_TESTING"
    assert report["config_hash"] == approval["config_hash"]
    assert report["input_data_hash"] == approval["input_data_hash"]


def test_mechanics_plan_reloads_web_string_trade_id_annotations(tmp_path):
    config_path, evidence, _ = _validation_fixture(tmp_path)
    service = MechanicsApprovalService()
    initial = service.plan(config_path)
    reviewed_trade = initial.sampled_trade_ids[0]

    save_manual_review_annotation(
        evidence,
        str(reviewed_trade),
        "Needs deeper review",
        "saved through the web form",
        reviewed_at="2026-07-15T12:00:00+00:00",
    )
    reloaded = service.plan(config_path)

    assert not any("merge on int64 and object" in blocker for blocker in reloaded.blockers)
    assert reviewed_trade not in reloaded.unreviewed_trade_ids
    assert reviewed_trade in reloaded.non_correct_trade_ids
    assert reloaded.sampled_trade_ids == initial.sampled_trade_ids


def test_mechanics_approval_becomes_stale_after_config_change(tmp_path):
    config_path, evidence, _ = _validation_fixture(tmp_path)
    _approve_all_samples(config_path, evidence)
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cfg["timeframe"] = "5m"
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    report = MechanicsApprovalService().inspect(config_path)

    assert report["status"] == "BLOCKED"
    assert any("config hash" in error for error in report["errors"])


def test_unresolved_automated_check_blocks_generated_approval(tmp_path):
    config_path, evidence, _ = _validation_fixture(tmp_path)
    checks_path = evidence / "validation_checks.parquet"
    checks = pd.read_parquet(checks_path)
    checks.loc[0, "status"] = "ERROR"
    checks.to_parquet(checks_path, index=False)

    plan = MechanicsApprovalService().plan(config_path)

    assert any("unresolved error" in item for item in plan.blockers)


def test_candidate_review_requires_independent_reviewer_and_is_hash_bound(tmp_path):
    config_path, evidence, _ = _validation_fixture(tmp_path)
    _approve_all_samples(config_path, evidence)
    result_dir = tmp_path / "results"
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_timestamp": "2025-01-02T14:30:00Z",
                "exit_timestamp": "2025-01-02T14:35:00Z",
                "net_pnl": 100.0,
                "r_multiple": 2.0,
            },
            {
                "trade_id": 2,
                "direction": "short",
                "entry_timestamp": "2025-01-03T14:30:00Z",
                "exit_timestamp": "2025-01-03T14:35:00Z",
                "net_pnl": -20.0,
                "r_multiple": -1.0,
            },
        ]
    )
    ResultBundleBuilder().build_and_write(
        trades,
        result_dir,
        campaign_id="demo",
        variant_id="v01",
        run_id="run-1",
        verdict="PASS",
        initial_balance=10_000.0,
        prop_rule_outcome="PASS",
        forced_flatten_compliance=True,
    )
    bundle_path = result_dir / "result_bundle_v2.json"
    manifest_path = _write_complete_finalization(result_dir, config_path)
    service = CandidateReviewService()

    with pytest.raises(ValueError, match="different from the mechanics reviewer"):
        service.review(
            result_bundle_path=bundle_path,
            config_path=config_path,
            reviewer="mechanics-reviewer",
            decision="approved_candidate",
            notes="Not independent.",
        )

    review = service.review(
        result_bundle_path=bundle_path,
        config_path=config_path,
        reviewer="independent-reviewer",
        decision="approved_candidate",
        notes="Independent terminal review completed; this remains a candidate strategy only.",
        reviewed_at="2026-07-15T13:00:00+00:00",
    )
    review_path = result_dir / "candidate_review.json"

    assert review.lifecycle_state == "candidate"
    assert service.lifecycle_state(
        candidate_review_path=review_path,
        result_bundle_path=bundle_path,
        config_path=config_path,
    ) == "candidate"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["transaction_complete"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert service.lifecycle_state(
        candidate_review_path=review_path,
        result_bundle_path=bundle_path,
        config_path=config_path,
    ) == "review_required"
    manifest["transaction_complete"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    bundle_path.write_text(bundle_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert service.lifecycle_state(
        candidate_review_path=review_path,
        result_bundle_path=bundle_path,
        config_path=config_path,
    ) == "review_required"
