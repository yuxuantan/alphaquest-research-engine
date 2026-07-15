import hashlib
import json

import pandas as pd
import pytest
import yaml

from alphaquest.data.source import data_source_hash
from alphaquest.research import campaign_stages
from alphaquest import run_core
from alphaquest.validation.promotion_gate import (
    APPROVAL_SCHEMA,
    REQUIRED_AUTOMATED_CATEGORIES,
    REQUIRED_AUTOMATED_CHECK_NAMES,
    REQUIRED_SAMPLE_CATEGORIES,
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
