from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from alphaquest.research.campaign_stages import DEFAULT_STAGE_ORDER
from alphaquest.studio.finalization import FinalizationError, RunFinalizer, inspect_finalized_result
from alphaquest.studio.results import load_result_bundle


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _fixture(
    tmp_path: Path,
    *,
    verdict: str = "FAIL",
    include_acceptance_trade: bool = False,
    include_supplemental: bool = False,
):
    config_path = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    cfg = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "attempt_id": "original",
        "attempt_kind": "original",
        "symbol": "ES",
        "timeframe": "1m",
        "strategy_name": "demo-v01",
        "research_metadata": {"edge_thesis": "Causal completed-bar liquidity reversal hypothesis."},
        "data": {"data_subset": {"start_date": "2024-01-01", "end_date": "2025-01-01"}},
        "strategy": {
            "entry": {"module": "safe_bar_rule"},
            "sl": {"module": "points_from_entry"},
            "tp": {"module": "fixed_r"},
        },
        "core": {"initial_balance": 50_000.0},
        "core_grid": {"parameters": {"entry.params.lookback": [5, 10]}},
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    run_dir = tmp_path / "research/evidence/runs/demo/v01/ES/run1"
    run_dir.mkdir(parents=True)
    stages = []
    for index, name in enumerate(DEFAULT_STAGE_ORDER):
        if verdict == "PASS":
            status = "passed"
        else:
            status = "failed" if index == 0 else "skipped"
        criterion = {
            "metric": "summary.metrics.profit_factor",
            "actual": 0.8 if status == "failed" else 1.4,
            "expected": {"min": 1.2},
            "passed": status == "passed",
        }
        stage = {
            "stage": name,
            "label": name.replace("_", " ").title(),
            "status": status,
            "passed": status == "passed",
            "criteria": [criterion] if status != "skipped" else [],
        }
        if status == "skipped":
            stage["skip_reason"] = "prior stage failed"
        else:
            _write_json(run_dir / name / "stage_result.json", stage)
        stages.append(stage)
    summary = {
        "run_uid": "run-uid-1",
        "campaign_id": "demo",
        "variant_id": "v01",
        "test_run_id": "run1",
        "symbol": "ES",
        "timeframe": "1m",
        "output_dir": str(run_dir),
        "research_verdict": verdict,
        "diagnostic_only": False,
        "stages": stages,
    }
    for name in ("campaign_test_summary.json", "variant_test_summary.json"):
        _write_json(run_dir / name, summary)
    _write_json(
        run_dir / "run_manifest.json",
        {"campaign_id": "demo", "variant_id": "v01", "run_uid": "run-uid-1"},
    )
    (run_dir / "effective_config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (run_dir / "source_config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_timestamp": "2025-01-02T14:30:00Z",
                "exit_timestamp": "2025-01-02T14:35:00Z",
                "net_pnl": 100.0,
                "r_multiple": 2.0,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            },
            {
                "trade_id": 2,
                "direction": "short",
                "entry_timestamp": "2025-01-03T14:30:00Z",
                "exit_timestamp": "2025-01-03T14:40:00Z",
                "net_pnl": -50.0,
                "r_multiple": -1.0,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            },
        ]
    )
    fixed = run_dir / "limited_core_grid_test/fixed_config_core_trade_log.csv"
    fixed.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(fixed, index=False)
    pd.DataFrame(
        [
            {
                "run_id": 1,
                "parameter": 5,
                "total_trades": 2,
                "net_profit": 50.0,
                "profit_factor": 2.0,
                "max_drawdown": 50.0,
                "mar": 1.0,
            }
        ]
    ).to_csv(
        run_dir / "limited_core_grid_test/core_grid_results.csv", index=False
    )
    if include_acceptance_trade:
        acceptance = run_dir / "acceptance_oos_test/trade_log.csv"
        acceptance.parent.mkdir(parents=True, exist_ok=True)
        trades.to_csv(acceptance, index=False)
        _write_json(
            run_dir / "acceptance_oos_test/acceptance_oos_summary.json",
            {"test_start": "2025-01-01", "test_end": "2025-01-31"},
        )
        calendar = run_dir / "acceptance_oos_test/validation/tradingview_comparison.csv"
        calendar.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {"session_date": pd.date_range("2025-01-01", "2025-01-31", freq="B").date}
        ).to_csv(calendar, index=False)
    if include_supplemental:
        wfa = run_dir / "walk_forward_analysis/wfa_oos_trade_log.csv"
        wfa.parent.mkdir(parents=True, exist_ok=True)
        wfa_trades = trades.assign(
            wfa_window_id=1,
            wfa_test_start="2025-01-01",
            wfa_test_end="2025-01-31",
        )
        wfa_trades.to_csv(wfa, index=False)
        _write_json(
            run_dir / "wfa_oos_monte_carlo/wfa_oos_monte_carlo_summary.json",
            {"number_of_runs": 300, "p95_max_drawdown": 750.0, "ruin_probability": 0.0},
        )
    return config_path, run_dir, summary


def test_finalization_atomically_publishes_strict_bundle_and_idempotent_ledger(tmp_path):
    config_path, run_dir, summary = _fixture(tmp_path)
    refreshes = []
    published_manifest_hashes = []
    source_index = tmp_path / "research/campaigns/active/demo/results_index.yaml"

    def refresh_source(_path, _cfg, _summary):
        source_index.parent.mkdir(parents=True, exist_ok=True)
        source_index.write_text("runs: []\n", encoding="utf-8")
        return source_index

    def refresh_registry(root):
        refreshes.append(root)
        manifest = run_dir / "reporting_v2/finalization_manifest.json"
        published_manifest_hashes.append(
            hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None
        )
        return {"runs": 1}

    finalizer = RunFinalizer(
        tmp_path,
        registry_refresher=refresh_registry,
        source_index_refresher=refresh_source,
    )
    first = finalizer.finalize(job_id="job-1", config_path=config_path, summary=summary)

    assert first.research_verdict == "FAIL"
    assert first.reporting_dir == run_dir / "reporting_v2"
    assert first.result_bundle_path.is_file()
    assert not list(run_dir.glob(".reporting_v2.*.tmp"))
    bundle = load_result_bundle(first.result_bundle_path)
    assert bundle.verdict == "FAIL"
    assert bundle.stage_criteria[0].actual.value == 0.8
    assert (first.reporting_dir / "parameter_neighbors.csv").is_file()
    assert (first.reporting_dir / "wfa_stitched_oos.csv").is_file()
    assert (first.reporting_dir / "monte_carlo_summary.csv").is_file()
    assert (first.reporting_dir / "methodology_audit.md").read_text(encoding="utf-8").strip().endswith("FAIL")
    assert refreshes == [tmp_path.resolve(), tmp_path.resolve()]
    assert published_manifest_hashes[-1] == hashlib.sha256(
        first.finalization_manifest_path.read_bytes()
    ).hexdigest()
    manifest = json.loads(first.finalization_manifest_path.read_text(encoding="utf-8"))
    assert manifest["transaction_complete"] is True
    assert manifest["registry_published"] is True
    assert manifest["terminal_recovery_phase"] == "FINALIZED"
    assert len(manifest["terminal_recovery_journal_sha256"]) == 64
    assert inspect_finalized_result(first.result_bundle_path)["valid"] is True

    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["result"] == "FAIL"
    assert rows[0]["stage"] == "full_staged_methodology"

    second = finalizer.finalize(job_id="job-1", config_path=config_path, summary=summary)
    assert second.idempotent_reuse is True
    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 1
    journal = json.loads(second.recovery_journal_path.read_text(encoding="utf-8"))
    assert journal["phase"] == "FINALIZED"
    assert journal["terminal"] is True
    assert journal["automatic_replay_permitted"] is False


def test_nonfinite_runner_criterion_becomes_null_with_reason_in_strict_bundle(tmp_path):
    config_path, run_dir, summary = _fixture(tmp_path)
    summary["stages"][0]["criteria"][0]["actual"] = float("inf")
    stage_path = run_dir / DEFAULT_STAGE_ORDER[0] / "stage_result.json"
    persisted = json.loads(stage_path.read_text(encoding="utf-8"))
    persisted["criteria"][0]["actual"] = None
    _write_json(stage_path, persisted)

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(job_id="job-nonfinite-summary", config_path=config_path, summary=summary)

    bundle = load_result_bundle(result.result_bundle_path)
    assert bundle.verdict == "FAIL"
    criterion = bundle.stage_criteria[0]
    assert criterion.actual.value is None
    assert criterion.actual.reason == "criterion actual value is undefined"
    raw = result.result_bundle_path.read_text(encoding="utf-8")
    assert "Infinity" not in raw
    assert "NaN" not in raw


def test_persisted_stage_contradiction_downgrades_fail_to_manual_review(tmp_path):
    config_path, run_dir, summary = _fixture(tmp_path)
    stage_path = run_dir / DEFAULT_STAGE_ORDER[0] / "stage_result.json"
    persisted = json.loads(stage_path.read_text(encoding="utf-8"))
    persisted["criteria"][0]["actual"] = 999.0
    _write_json(stage_path, persisted)

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(job_id="job-fail-stage-contradiction", config_path=config_path, summary=summary)

    bundle = load_result_bundle(result.result_bundle_path)
    reason = "persisted stage result contradicts the completed runner summary"
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any(reason in item.reason for item in bundle.stage_criteria)


def test_missing_acceptance_trade_downgrades_pass_and_suppresses_candidate_package(tmp_path):
    config_path, run_dir, summary = _fixture(tmp_path, verdict="PASS", include_acceptance_trade=False)
    for name in ("candidate_strategy_report.md", "manual_due_diligence_checklist.md", "final_config.yaml"):
        (run_dir / name).write_text("must be suppressed\n", encoding="utf-8")
    source_updates = []
    finalizer = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda _path, _cfg, update: source_updates.append(update) or None,
    )

    result = finalizer.finalize(job_id="job-pass-invalid", config_path=config_path, summary=summary)

    assert result.research_verdict == "NEEDS MANUAL REVIEW"
    bundle = load_result_bundle(result.result_bundle_path)
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any("acceptance OOS trade log" in item.reason for item in bundle.stage_criteria)
    assert not (run_dir / "candidate_strategy_report.md").exists()
    assert not (run_dir / "manual_due_diligence_checklist.md").exists()
    assert not (run_dir / "final_config.yaml").exists()
    assert source_updates[0]["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert source_updates[0]["passed"] is False
    assert source_updates[0]["finalization_state"] == "COMPLETE"
    assert source_updates[0]["result_bundle_path"] == str(result.result_bundle_path)
    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle))[-1]["result"] == "NEEDS MANUAL REVIEW"
    assert "ResultBundleV2 verdict: `NEEDS MANUAL REVIEW`" in (
        result.reporting_dir / "methodology_audit.md"
    ).read_text(encoding="utf-8")
    raw = result.result_bundle_path.read_text(encoding="utf-8")
    assert "Infinity" not in raw
    assert "NaN" not in raw


def test_missing_robustness_inputs_downgrade_pass_and_hash_reporting_sources(tmp_path):
    config_path, run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=True,
        include_supplemental=False,
    )

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(job_id="job-pass-missing-robustness", config_path=config_path, summary=summary)

    bundle = load_result_bundle(result.result_bundle_path)
    manifest = json.loads((result.reporting_dir / "finalization_manifest.json").read_text(encoding="utf-8"))
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any("walk-forward OOS" in item.reason for item in bundle.stage_criteria)
    assert any("Monte Carlo" in item.reason for item in bundle.stage_criteria)
    hashes = manifest["evidence_artifact_sha256"]
    assert "acceptance_oos_test/trade_log.csv" in hashes
    assert "limited_core_grid_test/core_grid_results.csv" in hashes


def test_complete_pass_retains_candidate_only_verdict_and_hashes_all_reporting_inputs(tmp_path):
    config_path, _run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=True,
        include_supplemental=True,
    )

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(job_id="job-pass-complete", config_path=config_path, summary=summary)

    bundle = load_result_bundle(result.result_bundle_path)
    manifest = json.loads((result.reporting_dir / "finalization_manifest.json").read_text(encoding="utf-8"))
    assert bundle.verdict == "PASS"
    assert "candidate strategy only" in bundle.verdict_message
    assert bundle.metrics.prop_rule_outcome.value == "PASS"
    assert bundle.metrics.forced_flatten_compliance.value is True
    assert bundle.metrics.trades_per_year.value == pytest.approx(2 / (31 / 365.25))
    assert bundle.metrics.daily_sharpe.value is not None
    assert {
        "acceptance_oos_test/trade_log.csv",
        "acceptance_oos_test/acceptance_oos_summary.json",
        "acceptance_oos_test/validation/tradingview_comparison.csv",
        "limited_core_grid_test/fixed_config_core_trade_log.csv",
        "limited_core_grid_test/core_grid_results.csv",
        "walk_forward_analysis/wfa_oos_trade_log.csv",
        "wfa_oos_monte_carlo/wfa_oos_monte_carlo_summary.json",
    } <= set(manifest["evidence_artifact_sha256"])


@pytest.mark.parametrize(
    ("missing_column", "reason_fragment"),
    [
        ("apex_rule_violation", "prop-rule simulation outcome"),
        ("position_flat_before_deadline", "forced-flatten compliance"),
    ],
)
def test_pass_requires_defined_prop_and_flatten_reporting_evidence(
    tmp_path,
    missing_column,
    reason_fragment,
):
    config_path, run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=True,
        include_supplemental=True,
    )
    acceptance_path = run_dir / "acceptance_oos_test/trade_log.csv"
    acceptance = pd.read_csv(acceptance_path).drop(columns=[missing_column])
    acceptance.to_csv(acceptance_path, index=False)

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(
        job_id=f"job-pass-missing-{missing_column}",
        config_path=config_path,
        summary=summary,
    )

    bundle = load_result_bundle(result.result_bundle_path)
    manifest = json.loads(result.finalization_manifest_path.read_text(encoding="utf-8"))
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any(reason_fragment in item.reason for item in bundle.stage_criteria)
    assert any(reason_fragment in issue for issue in manifest["evidence_issues"])


def test_empty_pass_acceptance_log_is_needs_manual_review(tmp_path):
    config_path, run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=True,
        include_supplemental=True,
    )
    acceptance_path = run_dir / "acceptance_oos_test/trade_log.csv"
    pd.read_csv(acceptance_path).iloc[0:0].to_csv(acceptance_path, index=False)

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(job_id="job-pass-empty-acceptance", config_path=config_path, summary=summary)

    bundle = load_result_bundle(result.result_bundle_path)
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any("acceptance OOS trade log contains no trades" in item.reason for item in bundle.stage_criteria)


@pytest.mark.parametrize("contradiction", ["status", "criterion"])
def test_persisted_stage_result_must_match_pass_summary(tmp_path, contradiction):
    config_path, run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=True,
        include_supplemental=True,
    )
    stage_path = run_dir / DEFAULT_STAGE_ORDER[0] / "stage_result.json"
    persisted = json.loads(stage_path.read_text(encoding="utf-8"))
    if contradiction == "status":
        persisted["status"] = "failed"
        persisted["passed"] = False
        persisted["criteria"][0]["passed"] = False
    else:
        persisted["criteria"][0]["actual"] = 999.0
    _write_json(stage_path, persisted)

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(
        job_id=f"job-stage-contradiction-{contradiction}",
        config_path=config_path,
        summary=summary,
    )

    bundle = load_result_bundle(result.result_bundle_path)
    manifest = json.loads(result.finalization_manifest_path.read_text(encoding="utf-8"))
    reason = "persisted stage result contradicts the completed runner summary"
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any(reason in item.reason for item in bundle.stage_criteria)
    assert any(reason in issue for issue in manifest["evidence_issues"])


def test_nonempty_but_wrong_supplemental_schemas_downgrade_pass(tmp_path):
    config_path, run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=True,
        include_supplemental=True,
    )
    pd.DataFrame([{"parameter": 5, "net_profit": "not-finite-evidence"}]).to_csv(
        run_dir / "limited_core_grid_test/core_grid_results.csv",
        index=False,
    )
    pd.DataFrame([{"trade_id": 1, "net_pnl": 10.0}]).to_csv(
        run_dir / "walk_forward_analysis/wfa_oos_trade_log.csv",
        index=False,
    )
    _write_json(
        run_dir / "wfa_oos_monte_carlo/wfa_oos_monte_carlo_summary.json",
        {"number_of_runs": 0, "p95_drawdown": -1.0, "ruin_probability": 2.0},
    )

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
        source_index_refresher=lambda *_args: None,
    ).finalize(job_id="job-invalid-supplemental", config_path=config_path, summary=summary)

    bundle = load_result_bundle(result.result_bundle_path)
    reasons = [item.reason for item in bundle.stage_criteria]
    assert bundle.verdict == "NEEDS MANUAL REVIEW"
    assert any("parameter-neighbor evidence lacks required columns" in reason for reason in reasons)
    assert any("walk-forward OOS evidence lacks required columns" in reason for reason in reasons)
    assert any("positive integer run count" in reason for reason in reasons)


def test_default_source_results_index_uses_bundle_downgrade_not_runner_pass(tmp_path):
    config_path, _run_dir, summary = _fixture(
        tmp_path,
        verdict="PASS",
        include_acceptance_trade=False,
    )
    campaign_root = config_path.parents[2]
    (campaign_root / "campaign.yaml").write_text(
        "campaign_id: demo\nvariants: [v01]\n",
        encoding="utf-8",
    )
    layout = tmp_path / "config/storage_layout.yaml"
    layout.parent.mkdir(parents=True)
    layout.write_text(
        "schema: alphaquest.storage-layout/v1\n"
        "active_campaign_root: research/campaigns/active\n"
        "evidence_roots: [research/evidence/runs]\n",
        encoding="utf-8",
    )

    result = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: {},
    ).finalize(job_id="job-source-index", config_path=config_path, summary=summary)

    index = yaml.safe_load((campaign_root / "results_index.yaml").read_text(encoding="utf-8"))
    entry = index["runs"][0]
    assert result.research_verdict == "NEEDS MANUAL REVIEW"
    assert entry["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert entry["passed"] is False
    assert entry["finalization_state"] == "COMPLETE"
    assert entry["result_bundle_path"] == str(result.result_bundle_path)


def test_failure_injected_after_atomic_publish_marks_attempt_incomplete_without_replay(tmp_path):
    config_path, run_dir, summary = _fixture(tmp_path)
    broken = RunFinalizer(
        tmp_path,
        registry_refresher=lambda _root: (_ for _ in ()).throw(RuntimeError("injected registry crash")),
        source_index_refresher=lambda *_args: None,
    )

    with pytest.raises(FinalizationError, match="post-publication"):
        broken.finalize(job_id="job-recovery", config_path=config_path, summary=summary)

    reporting = run_dir / "reporting_v2"
    assert reporting.is_dir()
    incomplete = json.loads((reporting / "finalization_manifest.json").read_text(encoding="utf-8"))
    assert incomplete["transaction_complete"] is False
    assert "injected registry crash" in incomplete["transaction_error"]
    marker = json.loads((run_dir / "studio_incomplete_attempt.json").read_text(encoding="utf-8"))
    assert marker["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert marker["attempt_reserved"] is True
    assert marker["automatic_replay_permitted"] is False
    assert "explicit replication" in marker["next_action"]
    failed_journal = json.loads(
        broken.recovery_journal_path("job-recovery").read_text(encoding="utf-8")
    )
    assert failed_journal["phase"] == "FINALIZATION_FAILED"
    assert failed_journal["automatic_replay_permitted"] is False

    with pytest.raises(FinalizationError, match="marked incomplete"):
        RunFinalizer(
            tmp_path,
            registry_refresher=lambda _root: {"runs": 1},
            source_index_refresher=lambda *_args: None,
        ).finalize(job_id="job-recovery", config_path=config_path, summary=summary)
    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[-1]["result"] == "NEEDS MANUAL REVIEW"
    assert rows[-1]["stage"] == "incomplete_studio_attempt"


def test_second_registry_publication_failure_revokes_completed_transaction(tmp_path):
    config_path, run_dir, summary = _fixture(tmp_path)
    calls = 0

    def registry(_root):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected final registry publication crash")
        return {"runs": 1}

    with pytest.raises(FinalizationError, match="post-publication"):
        RunFinalizer(
            tmp_path,
            registry_refresher=registry,
            source_index_refresher=lambda *_args: None,
        ).finalize(job_id="job-final-registry-crash", config_path=config_path, summary=summary)

    manifest = json.loads((run_dir / "reporting_v2/finalization_manifest.json").read_text(encoding="utf-8"))
    assert calls >= 2
    assert manifest["transaction_complete"] is False
    assert (run_dir / "studio_incomplete_attempt.json").is_file()
    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["result"] == "NEEDS MANUAL REVIEW"
    assert rows[0]["stage"] == "incomplete_studio_attempt"
