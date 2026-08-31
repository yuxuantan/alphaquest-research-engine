from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from alphaquest.data.source import data_source_hash
from alphaquest.research import campaign_stages
from alphaquest import run_core
from alphaquest.validation.promotion_gate import (
    APPROVAL_SCHEMA,
    LEGACY_REQUIRED_SAMPLE_CATEGORIES,
    REQUIRED_AUTOMATED_CATEGORIES,
    REQUIRED_AUTOMATED_CHECK_NAMES,
    REQUIRED_SAMPLE_CATEGORIES,
    SAMPLING_POLICY_SHA256,
    SAMPLING_POLICY_VERSION,
    inspect_historical_validation_approval,
    inspect_validation_gate,
    require_prior_variant_approvals,
    require_validation_approval,
)
from alphaquest.validation.schema import VALIDATION_SCHEMA_VERSION


def _fixture(tmp_path, *, lane="bar"):
    data = tmp_path / "bars.csv"
    data.write_text("timestamp,open,high,low,close,volume\n2024-01-02T14:30:00Z,1,2,0,1,10\n", encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    approval_path = evidence / "approval.json"
    config_path = tmp_path / "config.yaml"
    cfg = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "data": {"source": "csv", "raw_csv": str(data), "timezone": "America/New_York"},
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": lane,
                "evidence_dir": str(evidence),
                "approval_path": str(approval_path),
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
                "validation_lane": lane,
                "config_hash": config_hash,
                "input_data_hash": input_hash,
            }
        ),
        encoding="utf-8",
    )
    checks = [
        {"check_id": f"required.{name}", "check_name": name, "category": "reconciliation", "status": "pass", "severity": "error"}
        for name in sorted(REQUIRED_AUTOMATED_CHECK_NAMES)
    ]
    checks.extend(
        {"check_id": f"category.{category}", "check_name": f"{category}_coverage", "category": category, "status": "pass", "severity": "error"}
        for category in sorted(REQUIRED_AUTOMATED_CATEGORIES - {"reconciliation"})
    )
    pd.DataFrame(checks).to_parquet(
        evidence / "validation_checks.parquet", index=False
    )
    pd.DataFrame([{"trade_id": 1}]).to_parquet(evidence / "trades.parquet", index=False)
    filename = "event_transitions.parquet" if lane == "event_replay" else "bar_windows.parquet"
    pd.DataFrame([{"trade_id": 1, "timestamp": "2024-01-02T14:30:00Z"}]).to_parquet(
        evidence / filename, index=False
    )
    approval_path.write_text(
        json.dumps(
            {
                "schema": APPROVAL_SCHEMA,
                "status": "approved_for_testing",
                "reviewer": "skeptical-reviewer",
                "reviewed_at": "2026-07-15T12:00:00+08:00",
                "notes": "Deterministic risk-based sample reconciled to exported evidence.",
                "lane": lane,
                "config_hash": config_hash,
                "input_data_hash": input_hash,
                "validation_schema_version": VALIDATION_SCHEMA_VERSION,
                "sampled_trade_ids": [1],
                "sampling_categories": {name: [1] for name in REQUIRED_SAMPLE_CATEGORIES},
                "sampling_policy_version": SAMPLING_POLICY_VERSION,
                "sampling_policy_sha256": SAMPLING_POLICY_SHA256,
            }
        ),
        encoding="utf-8",
    )
    return cfg, config_path, evidence, approval_path


def test_hash_bound_manual_approval_passes(tmp_path):
    cfg, config_path, _, _ = _fixture(tmp_path)

    report = inspect_validation_gate(cfg, config_path)

    assert report["status"] == "APPROVED_FOR_TESTING"
    assert report["verdict"] == "PASS"
    assert report["errors"] == []


def test_legacy_sampling_approval_remains_valid_historical_proof(tmp_path):
    cfg, config_path, _evidence, approval_path = _fixture(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval.pop("sampling_policy_version")
    approval.pop("sampling_policy_sha256")
    approval["sampling_categories"] = {
        name: [1] for name in LEGACY_REQUIRED_SAMPLE_CATEGORIES
    }
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    assert inspect_validation_gate(cfg, config_path)["status"] == "APPROVED_FOR_TESTING"


def test_current_sampling_approval_is_bound_to_policy_hash(tmp_path):
    cfg, config_path, _evidence, approval_path = _fixture(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["sampling_policy_sha256"] = "0" * 64
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    report = inspect_validation_gate(cfg, config_path)

    assert report["status"] == "BLOCKED"
    assert any("sampling policy hash" in error for error in report["errors"])


def test_missing_validation_gate_cannot_opt_out_of_manual_approval(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("campaign_id: demo\nvariant_id: v01\n", encoding="utf-8")

    report = inspect_validation_gate({}, config_path)

    assert report["required"] is True
    assert report["status"] == "BLOCKED"
    with pytest.raises(ValueError, match="validation_gate is required"):
        require_validation_approval({}, config_path)


def test_stale_config_hash_blocks_promotion(tmp_path):
    cfg, config_path, _, approval_path = _fixture(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["config_hash"] = "stale"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(ValueError, match="config hash is stale or mismatched"):
        require_validation_approval(cfg, config_path)


def test_event_replay_never_accepts_bar_only_validation(tmp_path):
    cfg, config_path, evidence, _ = _fixture(tmp_path, lane="event_replay")
    (evidence / "event_transitions.parquet").unlink()
    pd.DataFrame([{"trade_id": 1, "timestamp": "2024-01-02T14:30:00Z"}]).to_parquet(
        evidence / "bar_windows.parquet", index=False
    )

    report = inspect_validation_gate(cfg, config_path)

    assert report["status"] == "BLOCKED"
    assert any("event_transitions.parquet" in item for item in report["errors"])


def test_certified_event_approval_is_bound_to_implementation_identity(tmp_path, monkeypatch):
    cfg, config_path, evidence, approval_path = _fixture(tmp_path, lane="event_replay")
    cfg["engine_lane"] = "canonical_event_replay"
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    identity = SimpleNamespace(
        implementation_version=3,
        implementation_sha256="a" * 64,
        manifest_sha256="b" * 64,
    )
    monkeypatch.setattr(
        "alphaquest.validation.promotion_gate.strategy_identity_for_config",
        lambda *_args, **_kwargs: identity,
    )
    metadata = json.loads((evidence / "metadata.json").read_text(encoding="utf-8"))
    metadata["config_hash"] = config_hash
    (evidence / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["config_hash"] = config_hash
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    blocked = inspect_validation_gate(cfg, config_path)
    assert blocked["status"] == "BLOCKED"
    assert any("implementation hash" in item for item in blocked["errors"])

    metadata.update(
        {
            "strategy_implementation_version": 3,
            "strategy_implementation_sha256": "a" * 64,
            "strategy_certification_manifest_sha256": "b" * 64,
        }
    )
    approval.update(
        {
            "strategy_implementation_version": 3,
            "strategy_implementation_sha256": "a" * 64,
            "strategy_certification_manifest_sha256": "b" * 64,
        }
    )
    (evidence / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    assert inspect_validation_gate(cfg, config_path)["status"] == "APPROVED_FOR_TESTING"


def test_historical_approval_uses_frozen_declared_certification_identity(tmp_path):
    cfg, config_path, evidence, approval_path = _fixture(
        tmp_path,
        lane="event_replay",
    )
    cfg["engine_lane"] = "canonical_event_replay"
    cfg["strategy_certification"] = {
        "strategy_id": "retired_strategy",
        "implementation_version": 7,
        "implementation_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    metadata = json.loads((evidence / "metadata.json").read_text(encoding="utf-8"))
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    identity = {
        "strategy_implementation_version": 7,
        "strategy_implementation_sha256": "a" * 64,
        "strategy_certification_manifest_sha256": "b" * 64,
    }
    metadata.update({"config_hash": config_hash, **identity})
    approval.update({"config_hash": config_hash, **identity})
    metadata["schema_version"] = "1.4"
    approval["validation_schema_version"] = "1.4"
    (evidence / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    report = inspect_historical_validation_approval(cfg, config_path)

    assert report["status"] == "APPROVED_FOR_TESTING"
    assert report["historical"] is True
    assert "older than the current generator" in report["warnings"][0]


def test_historical_approval_rebases_missing_absolute_governed_paths(tmp_path):
    project_root = tmp_path / "current-project"
    (project_root / "config").mkdir(parents=True)
    (project_root / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "evidence_roots": ["research/evidence/runs"],
                "research_artifact_root": "research_artifacts",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    cfg, config_path, original_evidence, original_approval = _fixture(
        project_root,
        lane="bar",
    )
    evidence = project_root / "research/evidence/runs/demo/v01/validation/core"
    evidence.parent.mkdir(parents=True)
    original_evidence.rename(evidence)
    approval_path = (
        project_root
        / "research_artifacts/validation_approvals/demo/original/v01/approval.json"
    )
    approval_path.parent.mkdir(parents=True)
    (evidence / original_approval.name).rename(approval_path)

    gate = cfg["research_metadata"]["validation_gate"]
    gate["evidence_dir"] = (
        "/former/workspace/alphaquest-research-engine/"
        "research/evidence/runs/demo/v01/validation/core"
    )
    gate["approval_path"] = (
        "/former/workspace/alphaquest-research-engine/"
        "research_artifacts/validation_approvals/demo/original/v01/approval.json"
    )
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    metadata = json.loads((evidence / "metadata.json").read_text(encoding="utf-8"))
    metadata["config_hash"] = config_hash
    (evidence / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["config_hash"] = config_hash
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    report = inspect_historical_validation_approval(cfg, config_path)

    assert report["status"] == "APPROVED_FOR_TESTING"
    assert report["evidence_dir"] == str(evidence)
    assert report["approval_path"] == str(approval_path)


def test_staged_performance_run_blocks_before_missing_validation_approval(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "campaigns/demo/variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    rationale = "This predeclared rationale is deliberately longer than eighty characters and uses only causal information."
    cfg = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "timeframe": "1m",
        "research_metadata": {
            "mechanics_review_required": True,
            "mechanics_review": {
                "mechanic_expresses_edge": rationale,
                "entry_logic_rationale": rationale,
                "stop_loss_rationale": rationale,
                "target_exit_rationale": rationale,
                "profitability_rationale": rationale,
                "known_failure_modes": rationale,
                "pre_test_decision": "approve_for_testing",
            },
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "evidence_dir": "campaigns/demo/variants/v01/validation/evidence",
                "approval_path": "campaigns/demo/variants/v01/validation/approval.json",
            },
        },
        "data": {"source": "csv", "raw_csv": "missing.csv", "timezone": "America/New_York"},
    }
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    with pytest.raises(ValueError, match="Mechanics validation promotion gate failed"):
        campaign_stages.run_campaign_stage_tests(config_path, include_acceptance=False)


def test_later_variant_blocks_until_prior_mechanics_approval(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = tmp_path / "campaigns/demo"
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        yaml.safe_dump({"campaign_id": "demo", "governance_contract_version": 2, "variants": ["v01", "v02"]}),
        encoding="utf-8",
    )
    current_cfg = None
    current_path = None
    for variant in ("v01", "v02"):
        path = campaign / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        cfg = {
            "campaign_id": "demo",
            "variant_id": variant,
            "research_metadata": {
                "validation_gate": {
                    "required": True,
                    "lane": "bar",
                    "evidence_dir": f"campaigns/demo/variants/{variant}/validation/evidence",
                    "approval_path": f"campaigns/demo/variants/{variant}/validation/approval.json",
                }
            },
            "data": {"source": "csv", "raw_csv": "missing.csv"},
        }
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        if variant == "v02":
            current_cfg, current_path = cfg, path

    with pytest.raises(ValueError, match="prior variants require completed mechanics approval"):
        require_prior_variant_approvals(current_cfg, current_path)


def test_follow_up_variant_sequencing_checks_prior_config_in_same_attempt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = tmp_path / "research/campaigns/active/demo"
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        yaml.safe_dump(
            {"campaign_id": "demo", "governance_contract_version": 2, "variants": ["v01", "v02"]}
        ),
        encoding="utf-8",
    )
    attempt = campaign / "follow_up_attempts/replication_20260715"
    current_cfg = None
    current_path = None
    for variant in ("v01", "v02"):
        path = attempt / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        cfg = {
            "campaign_id": "demo",
            "variant_id": variant,
            "attempt_id": "replication_20260715",
            "research_metadata": {
                "validation_gate": {
                    "required": True,
                    "lane": "bar",
                    "evidence_dir": str(attempt / variant / "validation/evidence"),
                    "approval_path": str(attempt / variant / "validation/approval.json"),
                }
            },
            "data": {"source": "csv", "raw_csv": "missing.csv"},
        }
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        if variant == "v02":
            current_cfg, current_path = cfg, path

    with pytest.raises(ValueError, match="v01: BLOCKED"):
        require_prior_variant_approvals(current_cfg, current_path)


def test_bar_mechanics_command_contract_uses_small_dedicated_generated_run():
    cfg = {
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "test_run_id": "performance_run",
        "core": {},
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "selection_mode": "latest_eligible_sessions",
                "session_count": 10,
                "parameter_mode": "declared_defaults",
                "manual_review_random_sample_size": 5,
                "manual_review_seed": 7,
                "minimum_trade_samples": 5,
                "data_subset": {"start_date": "2026-07-01", "end_date": "2026-07-10"},
                "evidence_dir": "backtest-campaigns/demo/v01/ES/mechanics_validation/validation_runs/core",
            }
        },
    }

    run_core._apply_mechanics_validation_contract(cfg)

    assert cfg["test_run_id"].startswith("mechanics_validation_")
    assert cfg["attempt_id"].startswith("original__mechanics_")
    assert cfg["attempt_kind"] == "mechanics_validation"
    assert cfg["attempt_provenance"] == "generated_validation"
    assert cfg["core"]["data_subset"] == {"start_date": "2026-07-01", "end_date": "2026-07-10"}
    assert cfg["core"]["validation_export"]["max_trades"] == 30
    assert cfg["core"]["validation_export"]["output_dir"].startswith("backtest-campaigns/")


def test_mechanics_command_requires_repository_wide_ten_session_contract():
    cfg = {
        "attempt_id": "methodology_rerun_demo",
        "attempt_kind": "methodology_rerun",
        "attempt_provenance": "authored",
        "core": {},
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "selection_mode": "latest_eligible_sessions",
                "session_count": 10,
                "parameter_mode": "declared_defaults",
                "manual_review_random_sample_size": 5,
                "manual_review_seed": 7,
                "minimum_trade_samples": 5,
                "data_subset": {
                    "start_date": "2026-05-14",
                    "end_date": "2026-05-29",
                },
                "evidence_dir": "evidence/recent",
            }
        },
    }

    run_core._apply_mechanics_validation_contract(cfg)

    assert cfg["core"]["data_subset"] == {
        "start_date": "2026-05-14",
        "end_date": "2026-05-29",
    }


def test_event_mechanics_command_preserves_exact_session_allowlist():
    session_dates = [
        "2026-05-14",
        "2026-05-15",
        "2026-05-19",
        "2026-05-20",
        "2026-05-21",
        "2026-05-22",
        "2026-05-26",
        "2026-05-27",
        "2026-05-28",
        "2026-05-29",
    ]
    cfg = {
        "engine_lane": "canonical_event_replay",
        "core": {},
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "event_replay",
                "selection_mode": "latest_eligible_sessions",
                "session_count": 10,
                "parameter_mode": "declared_defaults",
                "manual_review_random_sample_size": 5,
                "manual_review_seed": 7,
                "minimum_trade_samples": 5,
                "data_subset": {
                    "start_date": session_dates[0],
                    "end_date": session_dates[-1],
                    "session_dates": session_dates,
                },
                "evidence_dir": "evidence/recent",
            }
        },
    }

    run_core._apply_mechanics_validation_contract(cfg)

    assert cfg["core"]["data_subset"]["session_dates"] == session_dates

    invalid = deepcopy(cfg)
    invalid["research_metadata"]["validation_gate"]["session_count"] = 200
    with pytest.raises(ValueError, match="session_count must match repository methodology"):
        run_core._apply_mechanics_validation_contract(invalid)

    unbounded = {
        "core": {},
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "selection_mode": "latest_eligible_sessions",
                "session_count": 10,
                "parameter_mode": "declared_defaults",
                "manual_review_random_sample_size": 5,
                "manual_review_seed": 7,
                "minimum_trade_samples": 5,
                "data_subset": {
                    "start_date": "2019-05-06",
                    "end_date": "2020-02-24",
                },
                "evidence_dir": "evidence/unbounded",
            }
        },
    }
    with pytest.raises(ValueError, match="60 calendar days"):
        run_core._apply_mechanics_validation_contract(unbounded)
