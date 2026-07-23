import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from alphaquest.research.campaign_stages import evaluate_criteria
from alphaquest.research import campaign_stages


def _mechanics_review_yaml() -> list[str]:
    return [
        "research_metadata:",
        "  mechanics_review_required: true",
        "  mechanics_review:",
        "    mechanic_expresses_edge: The variant maps the stated edge into a deterministic staged-test entry using only information available before the order can be placed.",
        "    entry_logic_rationale: The entry is fixed before testing and waits for the configured signal condition, so the run cannot choose direction or timing after seeing results.",
        "    stop_loss_rationale: The stop is a predeclared risk bound attached to the entry and does not depend on future highs, lows, or realized trade path information.",
        "    target_exit_rationale: The target is predeclared with the strategy configuration and links reward to the risk module instead of optimizing an observed exit level.",
        "    profitability_rationale: The variant is allowed to enter staged testing because the hypothesized behavior could repeat often enough to overcome costs under realistic fills.",
        "    known_failure_modes: The idea should be rejected if costs erase the effect, if profits concentrate in a few trades, or if robustness tests expose fragile timing.",
        "    pre_test_decision: approve_for_testing",
    ]


def test_stage_criteria_reports_pass_and_fail():
    payload = {
        "summary": {"percentage_profitable_iterations": 0.75},
        "metrics": {"profit_factor": 1.1},
    }

    results = evaluate_criteria(
        payload,
        [
            {"metric": "summary.percentage_profitable_iterations", "min": 0.70},
            {"metric": "metrics.profit_factor", "min": 1.20},
        ],
    )

    assert results[0]["passed"] is True
    assert results[1]["passed"] is False
    assert results[1]["actual"] == 1.1


def test_stage_criteria_support_exclusive_min():
    results = evaluate_criteria(
        {"metrics": {"profit_factor": 1.2, "mar": 1.2001}},
        [
            {"metric": "metrics.profit_factor", "exclusive_min": 1.2},
            {"metric": "metrics.mar", "exclusive_min": 1.2},
        ],
    )

    assert results[0]["passed"] is False
    assert results[0]["expected"] == {"exclusive_min": 1.2}
    assert results[1]["passed"] is True


def test_stage_criteria_allow_fixed_or_declared_grid_size():
    criteria = [{"metric": "summary.total_combinations_tested", "valid_parameter_combination_count": True}]

    assert evaluate_criteria({"summary": {"total_combinations_tested": 1}}, criteria)[0]["passed"] is True
    assert evaluate_criteria({"summary": {"total_combinations_tested": 8}}, criteria)[0]["passed"] is True
    assert evaluate_criteria({"summary": {"total_combinations_tested": 120}}, criteria)[0]["passed"] is True
    assert evaluate_criteria({"summary": {"total_combinations_tested": 2}}, criteria)[0]["passed"] is False
    assert evaluate_criteria({"summary": {"total_combinations_tested": 121}}, criteria)[0]["passed"] is False


def test_limited_core_grid_does_not_require_benchmark_passing_combo():
    criteria = campaign_stages._criteria_for_stage("limited_core_grid_test", {})
    results = evaluate_criteria(
        {
            "summary": {
                "total_combinations_tested": 81,
                "percentage_profitable_iterations": 0.90,
                "number_passing_benchmark": 0,
                "apex_rule_violating_iterations": 0,
            }
        },
        criteria,
    )

    by_metric = {item["metric"]: item for item in results}
    assert by_metric["summary.percentage_profitable_iterations"]["passed"] is True
    assert "summary.number_passing_benchmark" not in by_metric
    assert all(item["passed"] for item in results)


def test_limited_monkey_separates_random_placebo_from_trade_path_stress():
    criteria = campaign_stages._criteria_for_stage("limited_monkey_test", {})
    criteria_metrics = {item["metric"] for item in criteria}
    payload = {
        "summary": {
            "percentage_profitable": 0.10,
            "median_net_profit": -1000.0,
            "core_beats_monkey_net_profit_rate": 0.95,
            "core_beats_monkey_max_drawdown_rate": 0.91,
            "core_metrics": {"apex_rule_violations": 0},
            "trade_path_stress": {
                "enabled": True,
                "percentage_profitable": 0.80,
                "median_net_profit": 25.0,
                "apex_rule_violating_iterations": 0,
                "one_tick_worse": {"profitable": True},
            },
        },
    }

    assert criteria_metrics == {
        "summary.core_beats_monkey_net_profit_rate",
        "summary.core_beats_monkey_max_drawdown_rate",
        "summary.core_metrics.apex_rule_violations",
    }
    assert "summary.trade_path_stress.percentage_profitable" not in criteria_metrics
    assert all(item["passed"] for item in evaluate_criteria(payload, criteria))


def test_default_stage_criteria_fail_apex_rule_violations():
    criteria = campaign_stages._criteria_for_stage("simulated_incubation_core", {})
    results = evaluate_criteria(
        {
            "metrics": {
                "profit_factor": 2.0,
                "mar": 2.0,
                "expectancy_r": 0.3,
                "total_trades": 100,
                "win_rate": 0.5,
                "apex_rule_violations": 1,
            }
        },
        criteria,
    )

    apex = [item for item in results if item["metric"] == "metrics.apex_rule_violations"]
    assert apex
    assert apex[0]["passed"] is False


def test_length_adjusted_mar_requirement_anchors_and_clamps():
    assert campaign_stages.length_adjusted_mar_requirement(2.0) == 1.5
    assert campaign_stages.length_adjusted_mar_requirement(3.0) == 1.5
    assert round(campaign_stages.length_adjusted_mar_requirement(5.0), 2) == 1.06
    assert round(campaign_stages.length_adjusted_mar_requirement(10.0), 2) == 0.66
    assert campaign_stages.length_adjusted_mar_requirement(15.0) == 0.5
    assert campaign_stages.length_adjusted_mar_requirement(20.0) == 0.5


def test_prepare_stage_data_reuses_cache_when_validation_is_skipped(tmp_path, monkeypatch):
    calls = []
    market = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-02"], utc=True)})
    execution = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-02"], utc=True)})

    def fake_prepare_data(data_config, output_dir, subset, timeframe=None, include_execution_data=False, show_progress=False):
        calls.append((output_dir, subset, timeframe))
        return market, {"rows": 1}, execution

    monkeypatch.setattr(campaign_stages, "prepare_data", fake_prepare_data)
    monkeypatch.setattr(campaign_stages, "data_source_hash", lambda data_config, subset: "hash-1")
    cache = {}
    cfg = {"timeframe": "5m", "data": {"source": "csv", "raw_csv": "sample.csv"}}
    subset = {"start_date": "2024-01-01", "end_date": "2024-01-31"}

    first = campaign_stages._prepare_stage_data(cfg, subset, tmp_path / "one", True, data_cache=cache)
    second = campaign_stages._prepare_stage_data(cfg, subset, tmp_path / "two", True, data_cache=cache)

    assert len(calls) == 1
    assert first[0] is second[0]
    assert first[1] is second[1]
    assert first[3] == second[3] == "hash-1"
    assert first[2]["prepared_data_cache"]["hit"] is False
    assert second[2]["prepared_data_cache"]["hit"] is True


def test_limited_core_summary_records_resolved_data_period(tmp_path, monkeypatch):
    base_subset = {"start_date": "2011-01-03", "end_date": "2026-06-09", "session_labels": ["RTH"]}
    expected_resolved_subset = {"start_date": "2011-02-22", "end_date": "2012-09-06", "session_labels": ["RTH"]}
    quality = {
        "rows": 141570,
        "strategy_rows": 28314,
        "first_timestamp": "2011-02-22 09:30:00-05:00",
        "last_timestamp": "2012-09-06 15:59:00-04:00",
        "timeframe": "5m",
        "source_timeframe": "1m",
    }
    market = pd.DataFrame({"timestamp": pd.to_datetime(["2011-01-03 14:30:00"], utc=True)})
    detail = pd.DataFrame({"timestamp": pd.to_datetime(["2011-01-03 14:30:00"], utc=True)})
    seen = {}

    def fake_prepare_stage_data_cached(cfg, subset, stage_dir, skip_validation, data_cache=None):
        seen["subset"] = subset
        return market, detail, quality, "input-hash"

    def fake_run_core_grid(data, cfg, grid_cfg, benchmarks, report_dir=None, detail_data=None):
        seen["benchmarks"] = dict(benchmarks)
        return (
            pd.DataFrame([{"run_id": 1, "net_profit": 10.0}]),
            {"total_combinations_tested": 1, "data_subset": dict(grid_cfg.get("data_subset") or {})},
        )

    def fake_write_fixed_config_core_artifacts(cfg, market_data, detail_data, stage_dir, subset, quality_report):
        seen["fixed_config_core_subset"] = subset
        return {
            "purpose": "fixed_config_mechanics_cross_check",
            "trade_log_csv": str(stage_dir / "fixed_config_core_trade_log.csv"),
        }

    monkeypatch.setattr(campaign_stages, "_prepare_stage_data_cached", fake_prepare_stage_data_cached)
    monkeypatch.setattr(campaign_stages, "run_core_grid", fake_run_core_grid)
    monkeypatch.setattr(campaign_stages, "_write_fixed_config_core_artifacts", fake_write_fixed_config_core_artifacts)

    payload = campaign_stages._run_limited_core_grid(
        {
            "timeframe": "5m",
            "data": {"timezone": "America/New_York"},
            "core": {"data_subset": base_subset},
            "benchmarks": {
                "min_trades_per_year": 50,
                "preferred_min_total_trades": 500,
                "min_profit_factor": 1.3,
                "min_expectancy_r": 0.05,
                "min_mar": 0.5,
                "max_best_day_concentration": 0.4,
            },
            "core_grid": {"data_subset": base_subset, "parameters": {"entry.params.threshold": [1]}},
        },
        {"data_window": campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW},
        tmp_path,
        skip_validation=True,
        context={},
    )

    written_summary = json.loads((tmp_path / "core_grid_summary.json").read_text(encoding="utf-8"))
    assert seen["subset"] == expected_resolved_subset
    assert payload["summary"]["configured_data_subset"] == base_subset
    assert payload["summary"]["resolved_data_subset"] == expected_resolved_subset
    assert payload["summary"]["data_subset"] == expected_resolved_subset
    assert payload["summary"]["actual_data_period"] == quality
    assert seen["fixed_config_core_subset"] == expected_resolved_subset
    assert payload["summary"]["fixed_config_core"]["purpose"] == "fixed_config_mechanics_cross_check"
    assert seen["benchmarks"]["preferred_min_total_trades"] == 78
    assert seen["benchmarks"]["max_best_day_concentration"] == 0.4
    assert "min_profit_factor" not in seen["benchmarks"]
    assert "min_expectancy_r" not in seen["benchmarks"]
    assert "min_mar" not in seen["benchmarks"]
    assert written_summary["benchmark_thresholds"]["preferred_min_total_trades"] == 78
    assert written_summary["fixed_config_core"]["trade_log_csv"].endswith("fixed_config_core_trade_log.csv")
    assert written_summary["actual_data_period"] == quality


def test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params(tmp_path, monkeypatch):
    quality = {
        "rows": 2,
        "strategy_rows": 2,
        "first_timestamp": "2011-02-22 09:30:00-05:00",
        "last_timestamp": "2011-02-22 09:31:00-05:00",
        "timeframe": "1m",
        "source_timeframe": "1m",
    }
    subset = {"start_date": "2011-02-22", "end_date": "2011-02-22", "session_labels": ["RTH"]}
    market = pd.DataFrame({"timestamp": pd.to_datetime(["2011-02-22 09:30:00-05:00"])})
    seen = {}

    class FakeBacktestEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def run(self, market_data, detail_data=None):
            seen["strategy"] = self.cfg["strategy"]
            return {
                "trades": pd.DataFrame(
                    [
                        {
                            "trade_id": 1,
                            "entry_timestamp": pd.Timestamp("2011-02-22 09:31:00", tz="America/New_York"),
                            "exit_timestamp": pd.Timestamp("2011-02-22 09:35:00", tz="America/New_York"),
                            "direction": "long",
                            "net_pnl": 25.0,
                        }
                    ]
                ),
                "daily": pd.DataFrame([{"session_date": "2011-02-22", "net_pnl": 25.0}]),
                "metrics": {"total_trades": 1, "net_profit": 25.0},
                "diagnostics": {"signals_generated": 1},
            }

    monkeypatch.setattr(campaign_stages, "BacktestEngine", FakeBacktestEngine)
    cfg = {
        "campaign_id": "test_campaign",
        "variant_id": "test_variant",
        "data": {"timezone": "America/New_York"},
        "core": {"initial_balance": 150000},
        "strategy": {
            "entry": {"module": "fixed_entry", "params": {"threshold": 7}},
            "sl": {"module": "fixed_sl", "params": {"stop_offset_ticks": 2}},
            "tp": {"module": "fixed_tp", "params": {"target_r_multiple": 1.0}},
        },
    }

    summary = campaign_stages._write_fixed_config_core_artifacts(cfg, market, None, tmp_path, subset, quality)

    trade_log = tmp_path / "fixed_config_core_trade_log.csv"
    metrics_json = tmp_path / "fixed_config_core_metrics.json"
    assert trade_log.is_file()
    assert (tmp_path / "fixed_config_core_daily_results.csv").is_file()
    assert (tmp_path / "fixed_config_core_equity_curve.csv").is_file()
    assert metrics_json.is_file()
    assert seen["strategy"]["entry"]["params"]["threshold"] == 7
    assert summary["parameter_source"] == "strategy section in effective config"
    assert summary["uses_grid_selected_params"] is False
    assert summary["resolved_data_subset"] == subset
    written = json.loads(metrics_json.read_text(encoding="utf-8"))
    assert written["metrics"]["total_trades"] == 1
    assert written["strategy"]["entry"]["params"]["threshold"] == 7


def test_limited_monkey_summary_records_resolved_data_period(tmp_path, monkeypatch):
    base_subset = {"start_date": "2011-01-03", "end_date": "2026-06-09", "session_labels": ["RTH"]}
    expected_resolved_subset = {"start_date": "2011-02-22", "end_date": "2012-09-06", "session_labels": ["RTH"]}
    quality = {
        "rows": 141570,
        "strategy_rows": 28314,
        "first_timestamp": "2011-02-22 09:30:00-05:00",
        "last_timestamp": "2012-09-06 15:59:00-04:00",
        "timeframe": "5m",
        "source_timeframe": "1m",
    }
    market = pd.DataFrame({"timestamp": pd.to_datetime(["2011-01-03 14:30:00"], utc=True)})
    detail = pd.DataFrame({"timestamp": pd.to_datetime(["2011-01-03 14:30:00"], utc=True)})

    def fake_prepare_stage_data_cached(cfg, subset, stage_dir, skip_validation, data_cache=None):
        return market, detail, quality, "input-hash"

    class FakeBacktestEngine:
        def __init__(self, cfg):
            self.cfg = cfg

        def run(self, market_data, detail_data=None):
            return {"trades": pd.DataFrame([{"net_pnl": 10.0}])}

    def fake_run_monkey(data, cfg, monkey_cfg, benchmarks, report_dir=None, detail_data=None, core_trades=None):
        return pd.DataFrame([{"run_id": 1, "net_profit": 10.0}]), {
            "number_of_runs": 1,
            "data_subset": dict(monkey_cfg.get("data_subset") or {}),
        }

    monkeypatch.setattr(campaign_stages, "_prepare_stage_data_cached", fake_prepare_stage_data_cached)
    monkeypatch.setattr(campaign_stages, "BacktestEngine", FakeBacktestEngine)
    monkeypatch.setattr(campaign_stages, "run_monkey", fake_run_monkey)

    payload = campaign_stages._run_limited_monkey(
        {
            "timeframe": "5m",
            "data": {"timezone": "America/New_York"},
            "monkey": {"data_subset": base_subset},
        },
        {"data_window": campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW},
        tmp_path,
        skip_validation=True,
        context={
            "limited_core_grid_parameters": {"entry.params.threshold": [1]},
            "limited_core_grid_results": pd.DataFrame(
                [{"run_id": 1, "net_profit": 10.0, "profitable": True, "entry.params.threshold": 1}]
            ),
        },
    )

    monkey_summary = json.loads((tmp_path / "monkey_summary.json").read_text(encoding="utf-8"))
    stress_summary = json.loads((tmp_path / "trade_path_stress_summary.json").read_text(encoding="utf-8"))
    assert payload["summary"]["configured_data_subset"] == base_subset
    assert payload["summary"]["resolved_data_subset"] == expected_resolved_subset
    assert payload["summary"]["data_subset"] == expected_resolved_subset
    assert payload["summary"]["actual_data_period"] == quality
    assert monkey_summary["actual_data_period"] == quality
    assert stress_summary["enabled"] is False
    assert stress_summary["skipped"] is True
    assert stress_summary["resolved_data_subset"] == expected_resolved_subset
    assert payload["summary"]["trade_path_stress"]["actual_data_period"] == quality


def test_limited_monkey_selects_median_profitable_row_without_benchmark_preference():
    row = campaign_stages._select_median_profitable_core_grid_row(
        pd.DataFrame(
            [
                {
                    "run_id": 1,
                    "net_profit": 300.0,
                    "profitable": True,
                    "benchmark_passed": False,
                    "entry.params.threshold": 1,
                },
                {
                    "run_id": 2,
                    "net_profit": 100.0,
                    "profitable": True,
                    "benchmark_passed": True,
                    "entry.params.threshold": 2,
                },
                {
                    "run_id": 3,
                    "net_profit": 500.0,
                    "profitable": True,
                    "benchmark_passed": True,
                    "entry.params.threshold": 3,
                },
            ]
        ),
        {"entry.params.threshold": [1, 2, 3]},
    )

    assert row["run_id"] == 1
    assert row["entry.params.threshold"] == 1


def test_fast_runtime_defaults_enable_parallel_sections_without_mutating_input():
    cfg = {
        "core_grid": {"parallel": {"enabled": False, "workers": 1}},
        "monkey": {},
        "wfa": {},
        "monte_carlo": {},
        "campaign_tests": {
            "limited_core_grid_test": {},
            "limited_monkey_test": {},
            "walk_forward_analysis": {},
            "wfa_oos_monkey_test": {},
            "wfa_oos_monte_carlo": {},
            "simulated_incubation_core": {"train_selection": {}},
            "simulated_incubation_monkey": {},
            campaign_stages.ACCEPTANCE_STAGE: {},
        },
    }

    out = campaign_stages.apply_fast_runtime_defaults(cfg, workers=4)

    assert cfg["core_grid"]["parallel"] == {"enabled": False, "workers": 1}
    assert out["core_grid"]["parallel"] == {"enabled": True, "workers": 4, "scope": "grid"}
    assert out["monkey"]["parallel"] == {"enabled": True, "workers": 4, "scope": "runs"}
    assert out["wfa"]["parallel"] == {"enabled": True, "workers": 4, "scope": "window_grid"}
    assert out["monte_carlo"]["parallel"] == {
        "enabled": True,
        "workers": 4,
        "scope": "runs",
    }
    campaign_tests = out["campaign_tests"]
    assert campaign_tests["limited_core_grid_test"]["parallel"]["scope"] == "grid"
    assert campaign_tests["limited_monkey_test"]["parallel"]["scope"] == "runs"
    assert campaign_tests["walk_forward_analysis"]["parallel"]["scope"] == "window_grid"
    assert campaign_tests["wfa_oos_monte_carlo"]["parallel"]["scope"] == "runs"
    assert campaign_tests["simulated_incubation_core"]["train_selection"]["parallel"] == {
        "enabled": True,
        "workers": 4,
        "scope": "grid",
    }


def test_canonicalized_campaign_forces_monkey_runs_to_8000():
    cfg = campaign_stages.canonicalize_campaign_config(
        {
            "monkey": {"runs": 300, "seed": 7},
            "campaign_tests": {
                "limited_monkey_test": {"runs": 300},
                "wfa_oos_monkey_test": {"runs": 300},
                "simulated_incubation_monkey": {"runs": 300},
            },
        }
    )

    assert cfg["monkey"]["runs"] == campaign_stages.DEFAULT_MONKEY_RUNS == 8000
    assert cfg["campaign_tests"]["limited_monkey_test"]["runs"] == 8000
    assert cfg["campaign_tests"]["wfa_oos_monkey_test"]["runs"] == 8000
    assert cfg["campaign_tests"]["simulated_incubation_monkey"]["runs"] == 8000
    assert cfg["monkey"]["seed"] == 7


def test_staged_campaign_writes_directly_to_campaign_test_run_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        campaign_stages,
        "require_validation_approval",
        lambda *args: {"status": "APPROVED_FOR_TESTING"},
    )
    config_path = tmp_path / "research/evidence/runs/demo_campaign/demo_variant/ES/run2/config.yaml"
    config_path.parent.mkdir(parents=True)
    campaign_metadata = tmp_path / "research/evidence/runs/demo_campaign/campaign.yaml"
    campaign_metadata.write_text(
        "\n".join(
            [
                "campaign_id: demo_campaign",
                "edge: demo academic edge",
                "candidate_variants:",
                "  - demo_variant",
            ]
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        "\n".join(
            [
                "campaign_id: demo_campaign",
                "variant_id: demo_variant",
                "strategy_name: demo_strategy",
                "timeframe: 1m",
                *_mechanics_review_yaml(),
                "data:",
                "  symbol: ES",
                "  dataset_id: sample_1m",
                "  raw_csv: data/raw/ES/sample.csv",
                "strategy:",
                "  entry:",
                "    module: demo_entry",
                "    params: {}",
                "  tp:",
                "    module: demo_tp",
                "    params: {}",
                "  sl:",
                "    module: demo_sl",
                "    params: {}",
                "core:",
                "  initial_balance: 50000",
            ]
        ),
        encoding="utf-8",
    )

    def fake_run_stage(stage_name, cfg, source_config, stage_cfg, stage_dir, skip_validation, context):
        return {
            "stage": stage_name,
            "label": stage_name,
            "status": "passed",
            "passed": True,
            "criteria": [],
        }

    monkeypatch.setattr(campaign_stages, "_run_stage", fake_run_stage)

    summary = campaign_stages.run_campaign_stage_tests(
        config_path,
        include_acceptance=False,
        skip_validation=True,
    )

    run_dir = tmp_path / "research/evidence/runs/demo_campaign/demo_variant/ES/run2"
    assert Path(summary["output_dir"]) == Path("research/evidence/runs/demo_campaign/demo_variant/ES/run2")
    assert summary["test_run_id"] == "run2"
    assert (run_dir / "effective_config.yaml").is_file()
    assert (run_dir / "source_config.yaml").is_file()
    assert (run_dir / "limited_core_grid_test/stage_result.json").is_file()
    assert (run_dir / "variant_test_summary.json").is_file()
    assert (run_dir / "campaign_test_summary.json").is_file()
    assert not (run_dir / "campaign_tests").exists()
    assert (run_dir.parent / "runs_index.csv").is_file()
    assert summary["campaign_metadata"]["path"] == "research/evidence/runs/demo_campaign/campaign.yaml"
    assert summary["campaign_metadata"]["hash"]
    assert summary["effective_config_path"] == (
        "research/evidence/runs/demo_campaign/demo_variant/ES/run2/effective_config.yaml"
    )
    assert summary["source_config_snapshot_path"] == "research/evidence/runs/demo_campaign/demo_variant/ES/run2/source_config.yaml"
    assert summary["variant_metadata"]["path"] == "research/evidence/runs/demo_campaign/demo_variant/variant.yaml"
    assert summary["variant_metadata"]["mechanic"]["entry_module"] == "demo_entry"
    assert (tmp_path / "research/evidence/runs/demo_campaign/demo_variant/variant.yaml").is_file()
    assert (tmp_path / "research/evidence/runs/demo_campaign/variants_index.yaml").is_file()
    effective_config = (run_dir / "effective_config.yaml").read_text(encoding="utf-8")
    source_config = (run_dir / "source_config.yaml").read_text(encoding="utf-8")
    assert "stage_order:" in effective_config
    assert "limited_core_grid_test:" in effective_config
    assert "stage_order:" not in source_config


def test_staged_campaign_can_write_external_config_to_explicit_run_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        campaign_stages,
        "require_validation_approval",
        lambda *args: {"status": "APPROVED_FOR_TESTING"},
    )
    config_path = tmp_path / "research_artifacts/demo_config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "campaign_id: demo_campaign",
                "variant_id: demo_variant",
                "strategy_name: demo_strategy",
                "timeframe: 1m",
                *_mechanics_review_yaml(),
                "data:",
                "  symbol: ES",
                "  dataset_id: sample_1m",
                "  raw_csv: data/raw/ES/sample.csv",
                "strategy:",
                "  entry:",
                "    module: demo_entry",
                "    params: {}",
                "  tp:",
                "    module: demo_tp",
                "    params: {}",
                "  sl:",
                "    module: demo_sl",
                "    params: {}",
                "core:",
                "  initial_balance: 50000",
            ]
        ),
        encoding="utf-8",
    )

    def fake_run_stage(stage_name, cfg, source_config, stage_cfg, stage_dir, skip_validation, context):
        return {
            "stage": stage_name,
            "label": stage_name,
            "status": "passed",
            "passed": True,
            "criteria": [],
        }

    monkeypatch.setattr(campaign_stages, "_run_stage", fake_run_stage)

    summary = campaign_stages.run_campaign_stage_tests(
        config_path,
        include_acceptance=False,
        skip_validation=True,
        out_dir=tmp_path / "backtest-campaigns/demo_campaign/demo_variant/ES/run2",
    )

    run_dir = tmp_path / "backtest-campaigns/demo_campaign/demo_variant/ES/run2"
    assert summary["test_run_id"] == "run2"
    assert summary["config_path"] == str(run_dir / "effective_config.yaml")
    assert summary["variant_metadata"]["path"] == str(tmp_path / "backtest-campaigns/demo_campaign/demo_variant/variant.yaml")
    assert (run_dir / "source_config.yaml").read_text(encoding="utf-8") == config_path.read_text(encoding="utf-8")
    assert "stage_order:" in (run_dir / "effective_config.yaml").read_text(encoding="utf-8")


def test_staged_campaign_writes_source_results_index_for_campaign_source_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        campaign_stages,
        "require_validation_approval",
        lambda *args: {"status": "APPROVED_FOR_TESTING"},
    )
    config_path = tmp_path / "research/campaigns/active/demo_campaign/variants/demo_variant/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "campaign_id: demo_campaign",
                "variant_id: demo_variant",
                "strategy_name: demo_strategy",
                "timeframe: 1m",
                *_mechanics_review_yaml(),
                "data:",
                "  symbol: ES",
                "  dataset_id: sample_1m",
                "  raw_csv: data/raw/ES/sample.csv",
                "strategy:",
                "  entry:",
                "    module: demo_entry",
                "    params: {}",
                "  tp:",
                "    module: demo_tp",
                "    params: {}",
                "  sl:",
                "    module: demo_sl",
                "    params: {}",
                "core:",
                "  initial_balance: 50000",
            ]
        ),
        encoding="utf-8",
    )

    def fake_run_stage(stage_name, cfg, source_config, stage_cfg, stage_dir, skip_validation, context):
        return {
            "stage": stage_name,
            "label": stage_name,
            "status": "passed",
            "passed": True,
            "criteria": [],
        }

    monkeypatch.setattr(campaign_stages, "_run_stage", fake_run_stage)

    summary = campaign_stages.run_campaign_stage_tests(
        config_path,
        include_acceptance=False,
        skip_validation=True,
    )

    run_dir = tmp_path / "research/evidence/runs/demo_campaign/demo_variant/ES/run1"
    index_path = tmp_path / "research/campaigns/active/demo_campaign/results_index.yaml"
    assert summary["source_results_index_path"] == str(index_path)
    assert (run_dir / "effective_config.yaml").is_file()
    assert (run_dir / "source_config.yaml").is_file()
    manifest = yaml.safe_load((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["effective_config"] == "research/evidence/runs/demo_campaign/demo_variant/ES/run1/effective_config.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert index["runs"] == [
        {
            "campaign_id": "demo_campaign",
            "variant_id": "demo_variant",
            "symbol": "ES",
            "test_run_id": "run1",
            "attempt_id": None,
            "attempt_kind": None,
            "attempt_provenance": None,
            "parent_attempt_id": None,
            "source_config_path": str(config_path),
            "source_config_snapshot_path": "research/evidence/runs/demo_campaign/demo_variant/ES/run1/source_config.yaml",
            "source_config_hash": summary["source_config_hash"],
            "effective_config_path": "research/evidence/runs/demo_campaign/demo_variant/ES/run1/effective_config.yaml",
            "effective_config_hash": summary["config_hash"],
            "run_dir": "research/evidence/runs/demo_campaign/demo_variant/ES/run1",
            "campaign_test_summary": "research/evidence/runs/demo_campaign/demo_variant/ES/run1/campaign_test_summary.json",
            "variant_test_summary": "research/evidence/runs/demo_campaign/demo_variant/ES/run1/variant_test_summary.json",
                "passed": False,
                "research_verdict": "NEEDS MANUAL REVIEW",
                "finalization_state": None,
                "result_bundle_path": None,
                "incomplete_attempt_marker_path": None,
                "diagnostic_only": True,
            "halted": False,
            "failed_stage": None,
            "updated_at": summary["updated_at"],
        }
    ]
    assert summary["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert summary["diagnostic_only"] is True
    assert summary["passed"] is False
    assert not (run_dir / "candidate_strategy_report.md").exists()


def test_submission_preflight_failure_blocks_before_attempt_or_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("campaign_id: demo\nvariant_id: v01\n", encoding="utf-8")
    attempt_checked = False

    def failed_preflight(**kwargs):
        return {
            "passed": False,
            "configs_checked": [str(config_path)],
            "failures": ["data quality is unresolved"],
            "warnings": [],
            "tests_ran": False,
        }

    def attempt_contract(*args, **kwargs):
        nonlocal attempt_checked
        attempt_checked = True
        return {}

    monkeypatch.setattr(campaign_stages, "run_preflight", failed_preflight)
    monkeypatch.setattr(campaign_stages, "_require_attempt_contract", attempt_contract)

    with pytest.raises(ValueError, match="Staged submission preflight failed before attempt reservation"):
        campaign_stages.run_campaign_stage_tests(
            config_path,
            skip_validation=False,
            include_acceptance=True,
        )

    assert attempt_checked is False
    assert not (tmp_path / "research/evidence/runs/demo").exists()


def test_submission_preflight_and_approval_finish_before_attempt_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("campaign_id: demo\nvariant_id: v01\n", encoding="utf-8")
    events = []

    def passing_preflight(**kwargs):
        events.append(("preflight", kwargs["run_tests"]))
        return {"passed": True, "failures": [], "warnings": [], "tests_ran": False}

    monkeypatch.setattr(campaign_stages, "run_preflight", passing_preflight)
    monkeypatch.setattr(
        campaign_stages,
        "_validate_pre_test_mechanics_review",
        lambda *args: events.append(("mechanics", None)),
    )
    monkeypatch.setattr(
        campaign_stages,
        "require_validation_approval",
        lambda *args: events.append(("approval", None)) or {"status": "APPROVED_FOR_TESTING"},
    )
    monkeypatch.setattr(
        campaign_stages,
        "require_prior_variant_approvals",
        lambda *args: events.append(("prior_approvals", None)),
    )

    def stop_at_attempt(*args, **kwargs):
        events.append(("attempt", None))
        raise RuntimeError("stop after ordering check")

    monkeypatch.setattr(campaign_stages, "_require_attempt_contract", stop_at_attempt)

    with pytest.raises(RuntimeError, match="ordering check"):
        campaign_stages.run_campaign_stage_tests(
            config_path,
            skip_validation=True,
            include_acceptance=False,
        )

    assert events == [
        ("preflight", False),
        ("mechanics", None),
        ("approval", None),
        ("prior_approvals", None),
        ("attempt", None),
    ]


def test_staged_campaign_rejects_symbol_level_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        campaign_stages,
        "require_validation_approval",
        lambda *args: {"status": "APPROVED_FOR_TESTING"},
    )
    config_path = tmp_path / "backtest-campaigns/demo_campaign/demo_variant/ES/run1/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "campaign_id: demo_campaign",
                "variant_id: demo_variant",
                "strategy_name: demo_strategy",
                "timeframe: 1m",
                *_mechanics_review_yaml(),
                "data:",
                "  symbol: ES",
                "  dataset_id: sample_1m",
                "  raw_csv: data/raw/ES/sample.csv",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Campaign run output must"):
        campaign_stages.run_campaign_stage_tests(
            config_path,
            include_acceptance=False,
            skip_validation=True,
            out_dir=tmp_path / "backtest-campaigns/demo_campaign/demo_variant/ES",
        )


def test_staged_campaign_requires_pre_test_mechanics_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "backtest-campaigns/demo_campaign/demo_variant/ES/run1/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "campaign_id: demo_campaign",
                "variant_id: demo_variant",
                "strategy_name: demo_strategy",
                "timeframe: 1m",
                "data:",
                "  symbol: ES",
                "  dataset_id: sample_1m",
                "  raw_csv: data/raw/ES/sample.csv",
                "strategy:",
                "  entry:",
                "    module: demo_entry",
                "    params: {}",
                "  tp:",
                "    module: demo_tp",
                "    params: {}",
                "  sl:",
                "    module: demo_sl",
                "    params: {}",
                "core:",
                "  initial_balance: 50000",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Pre-test mechanics review failed"):
        campaign_stages.run_campaign_stage_tests(
            config_path,
            include_acceptance=False,
            skip_validation=True,
        )


def test_governance_v2_attempt_can_have_at_most_one_staged_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = tmp_path / "research/campaigns/active/demo_campaign"
    config_path = campaign / "variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "campaign_id: demo_campaign\ngovernance_contract_version: 2\n",
        encoding="utf-8",
    )
    cfg = {
        "campaign_id": "demo_campaign",
        "variant_id": "v01",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "test_run_id": "run1",
        "timeframe": "1m",
        "data": {"symbol": "ES", "dataset_id": "fixture"},
    }
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    first = campaign_stages._require_attempt_contract(cfg, config_path, out_dir=None)

    assert first["attempt_id"] == "original"
    run_dir = tmp_path / "research/evidence/runs/demo_campaign/v01/ES/run1"
    run_dir.mkdir(parents=True)
    (run_dir / "campaign_test_summary.json").write_text(
        json.dumps({"campaign_id": "demo_campaign", "variant_id": "v01", "attempt_id": "original"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="already contains evidence|already has immutable evidence"):
        campaign_stages._require_attempt_contract(cfg, config_path, out_dir=None)


def test_default_stage_criteria_match_screenshot_benchmarks():
    limited_core = campaign_stages._criteria_for_stage("limited_core_grid_test", {})
    limited_monkey = campaign_stages._criteria_for_stage("limited_monkey_test", {})
    wfa = campaign_stages._criteria_for_stage("walk_forward_analysis", {})
    incubation = campaign_stages._criteria_for_stage("simulated_incubation_core", {})
    acceptance = campaign_stages._criteria_for_stage(campaign_stages.ACCEPTANCE_STAGE, {})

    def by_metric(criteria):
        return {item["metric"]: item for item in criteria}

    assert by_metric(limited_core)["summary.total_combinations_tested"]["valid_parameter_combination_count"] is True
    assert by_metric(limited_core)["summary.percentage_profitable_iterations"]["min"] == 0.70
    assert "summary.number_passing_benchmark" not in by_metric(limited_core)
    assert by_metric(limited_monkey)["summary.core_beats_monkey_net_profit_rate"]["min"] == 0.90
    assert by_metric(limited_monkey)["summary.core_beats_monkey_max_drawdown_rate"]["min"] == 0.90
    assert "summary.percentage_profitable" not in by_metric(limited_monkey)
    assert "summary.median_net_profit" not in by_metric(limited_monkey)
    assert "summary.trade_path_stress.percentage_profitable" not in by_metric(limited_monkey)
    assert by_metric(wfa)["stitched_oos_metrics.profit_factor"]["min"] == 1.2
    assert by_metric(wfa)["stitched_oos_metrics.mar"]["min"] == 0.4
    assert by_metric(wfa)["stitched_oos_metrics.trades_per_year"]["min"] == 50
    assert "stitched_oos_metrics.expectancy_r" not in by_metric(wfa)
    assert "summary.windows" not in by_metric(wfa)
    assert "stitched_oos_metrics.win_rate" not in by_metric(wfa)
    assert by_metric(campaign_stages._criteria_for_stage("wfa_oos_monkey_test", {}))[
        "summary.core_beats_monkey_net_profit_rate"
    ]["min"] == 0.80
    assert by_metric(campaign_stages._criteria_for_stage("wfa_oos_monkey_test", {}))[
        "summary.core_beats_monkey_max_drawdown_rate"
    ]["min"] == 0.80
    assert "summary.percentage_profitable" not in by_metric(
        campaign_stages._criteria_for_stage("wfa_oos_monkey_test", {})
    )
    assert "summary.trade_path_stress.percentage_profitable" not in by_metric(
        campaign_stages._criteria_for_stage("wfa_oos_monkey_test", {})
    )
    assert by_metric(campaign_stages._criteria_for_stage("simulated_incubation_monkey", {}))[
        "summary.core_beats_monkey_net_profit_rate"
    ]["min"] == 0.80
    assert by_metric(campaign_stages._criteria_for_stage("simulated_incubation_monkey", {}))[
        "summary.core_beats_monkey_max_drawdown_rate"
    ]["min"] == 0.80
    assert by_metric(incubation)["metrics.profit_factor"]["min"] == 1.0
    assert by_metric(incubation)["metrics.mar"]["min"] == 1.0
    assert by_metric(incubation)["metrics.trades_per_year"]["min"] == 50
    assert "metrics.total_trades" not in by_metric(incubation)
    assert "metrics.expectancy_r" not in by_metric(incubation)
    assert by_metric(acceptance)["metrics.profit_factor"]["min"] == 1.0
    assert by_metric(acceptance)["metrics.mar"]["min"] == 1.0
    assert by_metric(acceptance)["metrics.trades_per_year"]["min"] == 50
    assert "metrics.total_trades" not in by_metric(acceptance)
    assert "metrics.expectancy_r" not in by_metric(acceptance)
    assert "metrics.win_rate" not in by_metric(acceptance)


def test_canonicalized_stage_windows_match_shortlist_and_wfa_benchmarks():
    cfg = campaign_stages.canonicalize_campaign_config(
        {
            "campaign_tests": {
                "limited_core_grid_test": {
                    "data_subset": {"start_date": "2024-01-01", "end_date": "2024-12-31"}
                },
                "limited_monkey_test": {
                    "data_subset": {"start_date": "2024-01-01", "end_date": "2024-12-31"}
                },
                "walk_forward_analysis": {
                    "data_subset": {"start_date": "2024-01-01", "end_date": "2024-12-31"}
                },
            }
        }
    )

    limited_core = cfg["campaign_tests"]["limited_core_grid_test"]
    limited_monkey = cfg["campaign_tests"]["limited_monkey_test"]
    wfa = cfg["campaign_tests"]["walk_forward_analysis"]

    for stage_cfg in (limited_core, limited_monkey):
        assert "data_subset" not in stage_cfg
        assert stage_cfg["data_window"] == campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW
        assert stage_cfg["data_window"]["mode"] == "random_fraction"
        assert stage_cfg["data_window"]["fraction"] == 0.10
        assert stage_cfg["data_window"]["avoid_last_fraction"] == 0.10
        assert stage_cfg["data_window"]["avoid_ranges"] == [
            {"start_date": "2020-02-01", "end_date": "2021-06-30"}
        ]

    assert "data_subset" not in wfa
    assert wfa["data_window"] == {
        **campaign_stages.DEFAULT_WFA_DATA_WINDOW,
        "incubation_test_months": 12,
        "acceptance_test_months": 6,
    }


def test_wfa_mar_default_criteria_use_fixed_screenshot_threshold():
    criteria = campaign_stages._criteria_for_stage("walk_forward_analysis", {})
    results = evaluate_criteria(
        {
            "summary": {
                "early_exit": False,
                "windows": 12,
                "oos_evaluation_years": 15.0,
            },
            "stitched_oos_metrics": {
                "profit_factor": 1.2,
                "mar": 0.4,
                "total_trades": 600,
                "trades_per_year": 50,
                "win_rate": 0.50,
                "apex_rule_violations": 0,
            },
        },
        criteria,
    )

    mar = [item for item in results if item["metric"] == "stitched_oos_metrics.mar"][0]
    assert mar["passed"] is True
    assert mar["expected"] == {"min": 0.4}


def test_wfa_monte_carlo_probability_remains_exclusive():
    criteria = campaign_stages._criteria_for_stage("walk_forward_analysis", {})
    results = evaluate_criteria(
        {
            "summary": {
                "early_exit": False,
                "windows": 12,
                "oos_evaluation_years": 3.0,
            },
            "stitched_oos_metrics": {
                "profit_factor": 1.2,
                "mar": 0.4,
                "total_trades": 600,
                "trades_per_year": 50,
                "win_rate": 0.50,
                "apex_rule_violations": 0,
            },
        },
        criteria,
    )

    mar = [item for item in results if item["metric"] == "stitched_oos_metrics.mar"][0]
    assert mar["passed"] is True
    assert mar["expected"] == {"min": 0.4}

    mc_criteria = campaign_stages._criteria_for_stage("wfa_oos_monte_carlo", {})
    mc_results = evaluate_criteria({"summary": {"mean_net_pnl": 0.0}}, mc_criteria)
    assert mc_results[0]["passed"] is False
    assert mc_results[0]["expected"] == {"exclusive_min": 0.0}


def test_wfa_oos_monte_carlo_defaults_to_50k_prop_challenge_lifecycle(tmp_path, monkeypatch):
    trades = pd.DataFrame(
        [{"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 100.0}]
    )
    seen = {}

    def fake_run_monte_carlo_with_audit(source_trades, mc_cfg, rules):
        seen["trades"] = source_trades
        seen["mc_cfg"] = mc_cfg
        seen["rules"] = rules
        return (
            pd.DataFrame([{"run_id": 1, "net_pnl": 100.0}]),
            {"probability_profit_before_drawdown": 0.6},
            pd.DataFrame(),
            pd.DataFrame(),
        )

    monkeypatch.setattr(campaign_stages, "run_monte_carlo_with_audit", fake_run_monte_carlo_with_audit)

    payload = campaign_stages._run_wfa_oos_monte_carlo(
        {
            "data": {"timezone": "America/New_York"},
            "core": {"initial_balance": 100000},
            "monte_carlo": {"cluster_losses": True},
        },
        {},
        tmp_path,
        {"wfa_trades": trades},
    )

    assert seen["trades"].equals(trades)
    assert seen["rules"].account_lifecycle_enabled is True
    assert seen["rules"].starting_balance == 50000.0
    assert seen["rules"].challenge_fee == 98.0
    assert seen["rules"].challenge_profit_target_amount == 3000.0
    assert seen["rules"].challenge_consistency_limit == 0.50
    assert seen["rules"].trailing_drawdown == 2000.0
    assert seen["rules"].trailing_drawdown_lock_balance == 52100.0
    assert seen["rules"].trailing_drawdown_locked_floor == 50100.0
    assert seen["rules"].funded_initial_drawdown_floor == 48000.0
    assert payload["summary"]["prop_rules_used"]["account_lifecycle_enabled"] is True
    assert payload["summary"]["prop_rules_used"]["challenge_profit_target_amount"] == 3000.0
    assert payload["summary"]["prop_rules_used"]["drawdown_limit_amount"] == 2000.0
    assert seen["mc_cfg"]["cluster_losses"] is False
    assert (tmp_path / "wfa_oos_monte_carlo_summary.json").exists()


def test_wfa_oos_monte_carlo_does_not_inherit_tighter_top_level_drawdown_by_default(
    tmp_path,
    monkeypatch,
):
    trades = pd.DataFrame(
        [{"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 100.0}]
    )
    seen = {}

    def fake_run_monte_carlo_with_audit(source_trades, mc_cfg, rules):
        seen["rules"] = rules
        return (
            pd.DataFrame([{"run_id": 1, "net_pnl": 100.0}]),
            {"probability_profit_before_drawdown": 0.6},
            pd.DataFrame(),
            pd.DataFrame(),
        )

    monkeypatch.setattr(campaign_stages, "run_monte_carlo_with_audit", fake_run_monte_carlo_with_audit)

    payload = campaign_stages._run_wfa_oos_monte_carlo(
        {
            "data": {"timezone": "America/New_York"},
            "prop_rules": {
                "starting_balance": 150000,
                "daily_loss_limit": 4000,
                "trailing_drawdown": 4000,
                "max_contracts": 10,
            },
        },
        {},
        tmp_path,
        {"wfa_trades": trades},
    )

    assert seen["rules"].starting_balance == 50000.0
    assert seen["rules"].max_contracts == 10
    assert seen["rules"].daily_loss_limit == 2000.0
    assert seen["rules"].trailing_drawdown == 2000.0
    assert payload["summary"]["prop_rules_used"]["daily_loss_limit"] == 2000.0
    assert payload["summary"]["prop_rules_used"]["trailing_drawdown"] == 2000.0


def test_wfa_oos_monte_carlo_stage_prop_rules_can_tighten_drawdown_defaults(
    tmp_path,
    monkeypatch,
):
    trades = pd.DataFrame(
        [{"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 100.0}]
    )
    seen = {}

    def fake_run_monte_carlo_with_audit(source_trades, mc_cfg, rules):
        seen["rules"] = rules
        return (
            pd.DataFrame([{"run_id": 1, "net_pnl": 100.0}]),
            {"probability_profit_before_drawdown": 0.6},
            pd.DataFrame(),
            pd.DataFrame(),
        )

    monkeypatch.setattr(campaign_stages, "run_monte_carlo_with_audit", fake_run_monte_carlo_with_audit)

    campaign_stages._run_wfa_oos_monte_carlo(
        {
            "data": {"timezone": "America/New_York"},
            "prop_rules": {"daily_loss_limit": 4000, "trailing_drawdown": 4000},
        },
        {"prop_rules": {"daily_loss_limit": 3000, "trailing_drawdown": 3500}},
        tmp_path,
        {"wfa_trades": trades},
    )

    assert seen["rules"].daily_loss_limit == 3000
    assert seen["rules"].trailing_drawdown == 3500


def test_incubation_params_are_selected_from_best_wfa_oos_window():
    wfa_results = pd.DataFrame(
        [
            {
                "selected_params": {"tp.params.target_r_multiple": 1.0},
                "test_profit_factor": 1.5,
                "test_mar": 2.0,
                "test_net_profit": 100.0,
            },
            {
                "selected_params": {"tp.params.target_r_multiple": 2.0},
                "test_profit_factor": 2.0,
                "test_mar": 1.0,
                "test_net_profit": 80.0,
            },
        ]
    )

    assert campaign_stages._select_incubation_params(wfa_results) == {
        "tp.params.target_r_multiple": 2.0
    }


def test_incubation_train_selection_selects_best_core_grid_row():
    results = pd.DataFrame(
        [
            {
                "entry.params.stop_pct": 0.0035,
                "entry.params.target_r_multiple": 1.0,
                "mar": 0.5,
                "profit_factor": 1.2,
                "net_profit": 1000.0,
                "trades_per_year": 80.0,
            },
            {
                "entry.params.stop_pct": 0.005,
                "entry.params.target_r_multiple": 2.5,
                "mar": 1.5,
                "profit_factor": 1.4,
                "net_profit": 800.0,
                "trades_per_year": 90.0,
            },
        ]
    )

    selected = campaign_stages._select_core_grid_params(
        results,
        {
            "entry.params.stop_pct": [0.0035, 0.005],
            "entry.params.target_r_multiple": [1.0, 2.5],
        },
        {"objective": "MAR", "selection_min_trades_per_year": 50},
    )

    assert selected == {
        "entry.params.stop_pct": 0.005,
        "entry.params.target_r_multiple": 2.5,
    }


def test_train_selection_rejects_when_no_row_meets_trade_density_filter():
    results = pd.DataFrame(
        [
            {
                "entry.params.stop_pct": 0.0035,
                "mar": 2.0,
                "profit_factor": 1.5,
                "net_profit": 1000.0,
                "trades_per_year": 50.0,
            },
            {
                "entry.params.stop_pct": 0.005,
                "mar": 1.0,
                "profit_factor": 1.8,
                "net_profit": 1200.0,
                "trades_per_year": 20.0,
            },
        ]
    )

    with pytest.raises(ValueError, match="no parameter rows satisfying"):
        campaign_stages._select_core_grid_params(
            results,
            {"entry.params.stop_pct": [0.0035, 0.005]},
            {"objective": "MAR", "selection_exclusive_min_trades_per_year": 50},
        )


def test_incubation_train_selection_forces_mar_objective(tmp_path, monkeypatch):
    seen = {}
    quality = {
        "rows": 100,
        "strategy_rows": 20,
        "first_timestamp": "2024-01-02 09:30:00-05:00",
        "last_timestamp": "2024-01-31 15:59:00-05:00",
        "timeframe": "5m",
        "source_timeframe": "1m",
    }

    def fake_prepare_stage_data(cfg, subset, stage_dir, skip_validation, show_progress=False):
        return pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-02"], utc=True)}), None, quality, "hash"

    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
        seen["objective"] = grid_config["objective"]
        seen["selection_min_trades_per_year"] = grid_config.get("selection_min_trades_per_year")
        seen["selection_exclusive_min_trades_per_year"] = grid_config.get(
            "selection_exclusive_min_trades_per_year"
        )
        return (
            pd.DataFrame(
                [
                    {
                        "entry.params.stop_pct": 0.0035,
                        "mar": 0.5,
                        "profit_factor": 2.0,
                        "net_profit": 2000.0,
                        "trades_per_year": 100.0,
                    },
                    {
                        "entry.params.stop_pct": 0.005,
                        "mar": 2.0,
                        "profit_factor": 1.2,
                        "net_profit": 1000.0,
                        "trades_per_year": 100.0,
                    },
                ]
            ),
            {},
        )

    monkeypatch.setattr(campaign_stages, "_prepare_stage_data", fake_prepare_stage_data)
    monkeypatch.setattr(campaign_stages, "run_core_grid", fake_run_core_grid)

    selected_params, payload = campaign_stages._run_incubation_train_selection(
        {
            "data": {},
            "core_grid": {"parameters": {"entry.params.stop_pct": [0.0035, 0.005]}},
        },
        {
            "data_subset": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
            "objective": "net_profit",
            "selection_min_trades_per_year": 50,
        },
        tmp_path,
        skip_validation=True,
    )

    assert seen["objective"] == "MAR"
    assert seen.get("selection_min_trades_per_year") is None
    assert seen["selection_exclusive_min_trades_per_year"] == 50
    assert selected_params == {"entry.params.stop_pct": 0.005}
    assert payload["selected_params"] == {"entry.params.stop_pct": 0.005}
    assert payload["summary"]["resolved_data_subset"] == {"start_date": "2024-01-01", "end_date": "2024-01-31"}
    assert payload["summary"]["actual_data_period"] == quality


def test_default_stage_order_runs_acceptance_last():
    assert campaign_stages.DEFAULT_STAGE_ORDER[-1] == campaign_stages.ACCEPTANCE_STAGE
    assert campaign_stages._stage_order({})[-1] == campaign_stages.ACCEPTANCE_STAGE


def test_train_selection_accepts_empty_grid_as_fixed_config(tmp_path, monkeypatch):
    seen = {}

    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
        seen["parameters"] = grid_config["parameters"]
        return (
            pd.DataFrame([{"run_id": 1, "mar": 1.0, "profit_factor": 1.2, "net_profit": 100.0}]),
            {"parameter_mode": "fixed_config", "expected_combinations": 1},
        )

    monkeypatch.setattr(campaign_stages, "run_core_grid", fake_run_core_grid)
    selected, payload = campaign_stages._run_train_selection_grid(
        {"core_grid": {"parameters": {}}},
        {"parameters": {}, "data_subset": {"start_date": "2025-01-01", "end_date": "2025-01-31"}},
        tmp_path,
        skip_validation=True,
        train_data=pd.DataFrame({"timestamp": pd.to_datetime(["2025-01-02"], utc=True)}),
        train_detail=None,
        data_quality={"rows": 1},
        input_hash="fixed-input",
        parameter_label="acceptance_oos_test.parameters",
        result_prefix="acceptance",
    )

    assert seen["parameters"] == {}
    assert selected == {}
    assert payload["summary"]["parameter_mode"] == "fixed_config"
    assert payload["summary"]["selected_params"] == {}


def test_canonicalize_campaign_config_can_exclude_acceptance():
    cfg = campaign_stages.canonicalize_campaign_config({}, include_acceptance=False)
    campaign_tests = cfg["campaign_tests"]

    assert campaign_tests["stage_order"] == campaign_stages.PRE_ACCEPTANCE_STAGE_ORDER
    assert campaign_tests[campaign_stages.ACCEPTANCE_STAGE]["enabled"] is False
    assert campaign_tests["limited_core_grid_test"]["data_window"] == campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW
    assert campaign_tests["limited_monkey_test"]["data_window"] == campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW
    assert campaign_tests["walk_forward_analysis"]["data_window"] == {
        **campaign_stages.DEFAULT_WFA_DATA_WINDOW,
        "incubation_test_months": 12,
        "acceptance_test_months": 6,
    }
    assert campaign_tests["simulated_incubation_core"]["train_months"] == 48
    assert campaign_tests["simulated_incubation_core"]["test_months"] == 12
    assert campaign_tests["simulated_incubation_core"]["holdout_after_test_months"] == 6
    assert campaign_stages._stage_order(campaign_tests) == campaign_stages.PRE_ACCEPTANCE_STAGE_ORDER


def test_explicit_stage_order_appends_acceptance_by_default():
    order = campaign_stages._stage_order(
        {"stage_order": ["limited_core_grid_test", "simulated_incubation_monkey"]}
    )

    assert order == [
        "limited_core_grid_test",
        "simulated_incubation_monkey",
        campaign_stages.ACCEPTANCE_STAGE,
    ]


def test_explicit_stage_order_can_disable_acceptance_append():
    order = campaign_stages._stage_order(
        {
            "stage_order": ["limited_core_grid_test"],
            campaign_stages.ACCEPTANCE_STAGE: {"enabled": False},
        }
    )

    assert order == ["limited_core_grid_test"]


def test_acceptance_stage_does_not_inherit_incubation_core_criteria():
    criteria = [{"metric": "metrics.profit_factor", "min": 1.1}]

    stage_cfg = campaign_stages._stage_config(
        {"simulated_incubation_core": {"criteria": criteria}},
        campaign_stages.ACCEPTANCE_STAGE,
    )

    assert "criteria" not in stage_cfg


def test_acceptance_window_uses_latest_six_months_after_two_year_train():
    subset, window = campaign_stages._planned_acceptance_subset(
        {"start_date": "2011-01-03", "end_date": "2026-05-29", "session_labels": ["RTH"]},
        train_months=24,
        test_months=6,
    )

    assert subset == {
        "start_date": "2023-11-29",
        "end_date": "2026-05-29",
        "session_labels": ["RTH"],
    }
    assert window["train_start"] == pd.Timestamp("2023-11-29")
    assert window["train_end"] == pd.Timestamp("2025-11-28")
    assert window["test_start"] == pd.Timestamp("2025-11-29")
    assert window["test_end"] == pd.Timestamp("2026-05-29")


def test_incubation_window_uses_latest_one_year_after_four_year_train():
    subset, window = campaign_stages._planned_acceptance_subset(
        {"start_date": "2011-01-03", "end_date": "2026-06-09", "session_labels": ["RTH"]},
        train_months=48,
        test_months=12,
        stage_label="simulated_incubation_core",
    )

    assert subset == {
        "start_date": "2021-06-09",
        "end_date": "2026-06-09",
        "session_labels": ["RTH"],
    }
    assert window["train_start"] == pd.Timestamp("2021-06-09")
    assert window["train_end"] == pd.Timestamp("2025-06-08")
    assert window["test_start"] == pd.Timestamp("2025-06-09")
    assert window["test_end"] == pd.Timestamp("2026-06-09")


def test_incubation_window_reserves_final_acceptance_holdout():
    subset, window = campaign_stages._planned_acceptance_subset(
        {"start_date": "2011-08-15", "end_date": "2026-05-29", "session_labels": ["RTH"]},
        train_months=48,
        test_months=12,
        stage_label="simulated_incubation_core",
        holdout_months=6,
    )

    assert subset == {
        "start_date": "2020-11-28",
        "end_date": "2025-11-28",
        "session_labels": ["RTH"],
    }
    assert window["train_start"] == pd.Timestamp("2020-11-28")
    assert window["train_end"] == pd.Timestamp("2024-11-27")
    assert window["test_start"] == pd.Timestamp("2024-11-28")
    assert window["test_end"] == pd.Timestamp("2025-11-28")


def test_campaign_test_window_plan_has_disjoint_wfa_incubation_and_acceptance_oos():
    rows = campaign_stages.campaign_test_data_window_plan(
        {
            "research_metadata": {
                "validation_gate": {
                    "data_subset": {
                        "start_date": "2011-08-15",
                        "end_date": "2011-08-29",
                    }
                }
            },
            "core": {
                "data_subset": {
                    "start_date": "2011-08-15",
                    "end_date": "2026-05-29",
                    "session_labels": ["RTH"],
                }
            },
            "core_grid": {
                "data_subset": {
                    "start_date": "2011-08-15",
                    "end_date": "2026-05-29",
                    "session_labels": ["RTH"],
                }
            },
            "monkey": {
                "data_subset": {
                    "start_date": "2011-08-15",
                    "end_date": "2026-05-29",
                    "session_labels": ["RTH"],
                }
            },
            "wfa": {
                "data_subset": {
                    "start_date": "2011-08-15",
                    "end_date": "2026-05-29",
                    "session_labels": ["RTH"],
                },
                "train_months": 48,
                "test_months": 12,
                "step_months": 12,
            },
            "campaign_tests": {
                "simulated_incubation_core": {
                    "train_months": 48,
                    "test_months": 12,
                },
                "acceptance_oos_test": {
                    "train_months": 24,
                    "test_months": 6,
                },
            },
        }
    )
    by_stage = {row["stage"]: row for row in rows}

    assert by_stage["mechanics_validation"]["planned_start"] == "2011-08-15"
    assert by_stage["walk_forward_analysis"]["planned_end"] == "2024-11-27"
    assert by_stage["simulated_incubation_core"]["test_start"] == "2024-11-28"
    assert by_stage["simulated_incubation_core"]["test_end"] == "2025-11-28"
    assert by_stage["acceptance_oos_test"]["test_start"] == "2025-11-29"
    assert by_stage["acceptance_oos_test"]["test_end"] == "2026-05-29"
    assert (
        pd.Timestamp(by_stage["walk_forward_analysis"]["planned_end"])
        < pd.Timestamp(by_stage["simulated_incubation_core"]["test_start"])
        < pd.Timestamp(by_stage["acceptance_oos_test"]["test_start"])
    )


def test_acceptance_selection_forces_mar_objective():
    cfg = {
        "wfa": {"selection_min_trades_per_year": 50},
        "benchmarks": {"min_trades_per_year": 10},
    }

    selection_cfg = campaign_stages._acceptance_selection_config(
        cfg,
        {"train_selection": {"objective": "profit_factor"}},
        {"entry.params.stop_pct": [0.0035]},
    )

    assert selection_cfg["objective"] == "MAR"
    assert "selection_min_trades_per_year" not in selection_cfg
    assert selection_cfg["selection_exclusive_min_trades_per_year"] == 50


def test_acceptance_mar_selection_prefers_mar_over_profit_factor():
    results = pd.DataFrame(
        [
            {
                "entry.params.stop_pct": 0.0035,
                "profit_factor": 1.3,
                "mar": 3.0,
                "net_profit": 1000.0,
                "trades_per_year": 80.0,
            },
            {
                "entry.params.stop_pct": 0.005,
                "profit_factor": 1.8,
                "mar": 1.0,
                "net_profit": 500.0,
                "trades_per_year": 80.0,
            },
        ]
    )

    selected = campaign_stages._select_core_grid_params(
        results,
        {"entry.params.stop_pct": [0.0035, 0.005]},
        {"objective": "MAR", "selection_min_trades_per_year": 50},
    )

    assert selected == {"entry.params.stop_pct": 0.0035}


def test_median_profitable_core_grid_row_selects_representative_profit():
    results = pd.DataFrame(
        [
            {"run_id": 1, "entry.params.threshold": 1, "net_profit": -100.0, "profitable": False},
            {"run_id": 2, "entry.params.threshold": 2, "net_profit": 100.0, "profitable": True},
            {"run_id": 3, "entry.params.threshold": 3, "net_profit": 300.0, "profitable": True},
            {"run_id": 4, "entry.params.threshold": 4, "net_profit": 1000.0, "profitable": True},
        ]
    )

    row = campaign_stages._select_median_profitable_core_grid_row(
        results,
        {"entry.params.threshold": [1, 2, 3, 4]},
    )

    assert row["run_id"] == 3
    assert campaign_stages._core_grid_params_from_row(
        row,
        {"entry.params.threshold": [1, 2, 3, 4]},
    ) == {"entry.params.threshold": 3}


def test_configured_stale_criteria_are_ignored_for_canonical_stage():
    criteria = campaign_stages._criteria_for_stage(
        "walk_forward_analysis",
        {"criteria": [{"metric": "stitched_oos_metrics.profit_factor", "min": 1.4}]},
    )

    assert {"metric": "stitched_oos_metrics.profit_factor", "min": 1.2} in criteria


def test_incubation_core_stage_uses_four_year_train_latest_one_year_oos(tmp_path, monkeypatch):
    dates = pd.date_range("2021-06-09", "2026-06-09", freq="D", tz="America/New_York")
    market = pd.DataFrame(
        {
            "timestamp": dates,
            "session_date": [ts.date() for ts in dates],
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
        }
    )
    seen = {}

    def fake_prepare_stage_data(cfg, subset, stage_dir, skip_validation, show_progress=False):
        seen["subset"] = subset
        return market, None, {"rows": len(market)}, "incubation-hash"

    def fake_run_core_grid(data, base_config, grid_config, benchmarks, report_dir=None, parameter_label=None, detail_data=None):
        seen["train_start"] = str(data["session_date"].min())
        seen["train_end"] = str(data["session_date"].max())
        seen["parameter_label"] = parameter_label
        seen["objective"] = grid_config["objective"]
        seen["selection_exclusive_min_trades_per_year"] = grid_config["selection_exclusive_min_trades_per_year"]
        return (
            pd.DataFrame(
                [
                    {
                        "run_id": 1,
                        "entry.params.threshold": 1,
                        "total_trades": 300,
                        "trades_per_year": 75.0,
                        "net_profit": 1000.0,
                        "profit_factor": 1.5,
                        "mar": 1.2,
                        "apex_rule_violations": 0,
                    }
                ]
            ),
            {"total_combinations_tested": 1},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            seen["selected_threshold"] = config["strategy"]["entry"]["params"]["threshold"]

        def run(self, data, detail_data=None):
            seen["test_start"] = str(data["session_date"].min())
            seen["test_end"] = str(data["session_date"].max())
            trade_ts = pd.Timestamp("2025-06-10 10:00", tz="America/New_York")
            trades = pd.DataFrame(
                [
                    {
                        "trade_id": 1,
                        "session_date": trade_ts.date(),
                        "entry_timestamp": trade_ts,
                        "exit_timestamp": trade_ts + pd.Timedelta(minutes=5),
                        "net_pnl": 100.0,
                        "gross_pnl": 100.0,
                        "r_multiple": 1.0,
                        "contracts": 1,
                    }
                ]
            )
            return {
                "trades": trades,
                "daily": pd.DataFrame([{"session_date": trade_ts.date(), "net_pnl": 100.0}]),
                "metrics": {
                    "profit_factor": 1.2,
                    "mar": 1.1,
                    "trades_per_year": 55.0,
                    "total_trades": 55,
                    "apex_rule_violations": 0,
                },
                "diagnostics": {"entries_opened": 1},
            }

    monkeypatch.setattr(campaign_stages, "_prepare_stage_data", fake_prepare_stage_data)
    monkeypatch.setattr(campaign_stages, "run_core_grid", fake_run_core_grid)
    monkeypatch.setattr(campaign_stages, "BacktestEngine", FakeBacktestEngine)
    cfg = {
        "campaign_id": "demo",
        "variant_id": "incubation",
        "data": {"timezone": "America/New_York"},
        "core": {
            "initial_balance": 100000,
            "data_subset": {"start_date": "2011-01-03", "end_date": "2026-06-09", "session_labels": ["RTH"]},
        },
        "strategy": {"entry": {"params": {"threshold": 0}}},
        "core_grid": {"parameters": {"entry.params.threshold": [1]}},
    }

    payload = campaign_stages._run_incubation_core(cfg, {}, tmp_path, skip_validation=True, context={})

    assert payload["selected_params"] == {"entry.params.threshold": 1}
    assert seen["subset"]["start_date"] == "2021-06-09"
    assert seen["train_start"] == "2021-06-09"
    assert seen["train_end"] == "2025-06-08"
    assert seen["test_start"] == "2025-06-09"
    assert seen["test_end"] == "2026-06-09"
    assert seen["selected_threshold"] == 1
    assert seen["parameter_label"] == "simulated_incubation_core.parameters"
    assert seen["objective"] == "MAR"
    assert seen["selection_exclusive_min_trades_per_year"] == 50
    assert (tmp_path / "incubation_oos_results.csv").exists()
    assert (tmp_path / "incubation_oos_summary.json").exists()
    assert (tmp_path / "train_selection" / "incubation_train_grid_results.csv").exists()


def test_acceptance_oos_stage_writes_core_like_artifacts(tmp_path, monkeypatch):
    dates = pd.date_range("2023-11-29", "2026-05-29", freq="D", tz="America/New_York")
    market = pd.DataFrame(
        {
            "timestamp": dates,
            "session_date": [ts.date() for ts in dates],
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
        }
    )
    seen = {}

    def fake_prepare_stage_data(cfg, subset, stage_dir, skip_validation, show_progress=False):
        seen["subset"] = subset
        return market, None, {"rows": len(market)}, "acceptance-hash"

    def fake_run_core_grid(data, base_config, grid_config, benchmarks, report_dir=None, parameter_label=None, detail_data=None):
        seen["train_start"] = str(data["session_date"].min())
        seen["train_end"] = str(data["session_date"].max())
        seen["parameter_label"] = parameter_label
        return (
            pd.DataFrame(
                [
                    {
                        "run_id": 1,
                        "entry.params.threshold": 1,
                        "total_trades": 100,
                        "trades_per_year": 75.0,
                        "net_profit": 1000.0,
                        "profit_factor": 1.5,
                        "expectancy_r": 0.2,
                        "max_drawdown": 100.0,
                        "max_drawdown_pct": 0.01,
                        "cagr": 0.1,
                        "mar": 11.0,
                        "win_rate": 0.5,
                        "apex_rule_violations": 0,
                    },
                    {
                        "run_id": 2,
                        "entry.params.threshold": 2,
                        "total_trades": 100,
                        "trades_per_year": 75.0,
                        "net_profit": 900.0,
                        "profit_factor": 2.0,
                        "expectancy_r": 0.2,
                        "max_drawdown": 100.0,
                        "max_drawdown_pct": 0.01,
                        "cagr": 0.1,
                        "mar": 10.0,
                        "win_rate": 0.5,
                        "apex_rule_violations": 0,
                    },
                ]
            ),
            {"total_combinations_tested": 2},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            seen["selected_threshold"] = config["strategy"]["entry"]["params"]["threshold"]

        def run(self, data, detail_data=None):
            seen["test_start"] = str(data["session_date"].min())
            seen["test_end"] = str(data["session_date"].max())
            trade_ts = pd.Timestamp("2026-01-02 10:00", tz="America/New_York")
            trades = pd.DataFrame(
                [
                    {
                        "trade_id": 1,
                        "session_date": trade_ts.date(),
                        "entry_timestamp": trade_ts,
                        "exit_timestamp": trade_ts + pd.Timedelta(minutes=5),
                        "net_pnl": 100.0,
                        "gross_pnl": 100.0,
                        "r_multiple": 1.0,
                        "contracts": 1,
                    }
                ]
            )
            return {
                "trades": trades,
                "daily": pd.DataFrame([{"session_date": trade_ts.date(), "net_pnl": 100.0}]),
                "metrics": {
                    "profit_factor": 1.5,
                    "mar": 1.2,
                    "expectancy_r": 0.2,
                    "total_trades": 75,
                    "win_rate": 0.5,
                    "apex_rule_violations": 0,
                },
                "diagnostics": {"entries_opened": 1},
            }

    monkeypatch.setattr(campaign_stages, "_prepare_stage_data", fake_prepare_stage_data)
    monkeypatch.setattr(campaign_stages, "run_core_grid", fake_run_core_grid)
    monkeypatch.setattr(campaign_stages, "BacktestEngine", FakeBacktestEngine)
    cfg = {
        "campaign_id": "demo",
        "variant_id": "acceptance",
        "data": {"timezone": "America/New_York"},
        "core": {
            "initial_balance": 100000,
            "data_subset": {"start_date": "2011-01-03", "end_date": "2026-05-29", "session_labels": ["RTH"]},
        },
        "strategy": {"entry": {"params": {"threshold": 0}}},
        "core_grid": {"parameters": {"entry.params.threshold": [1, 2]}},
        "wfa": {"selection_min_trades_per_year": 50},
    }

    payload = campaign_stages._run_acceptance_oos(cfg, {}, tmp_path, skip_validation=True)

    assert payload["selected_params"] == {"entry.params.threshold": 1}
    assert seen["subset"]["start_date"] == "2023-11-29"
    assert seen["train_start"] == "2023-11-29"
    assert seen["train_end"] == "2025-11-28"
    assert seen["test_start"] == "2025-11-29"
    assert seen["test_end"] == "2026-05-29"
    assert seen["selected_threshold"] == 1
    assert seen["parameter_label"] == "acceptance_oos_test.parameters"
    assert (tmp_path / "acceptance_oos_results.csv").exists()
    assert (tmp_path / "acceptance_oos_summary.json").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "trade_log.csv").exists()
    assert (tmp_path / "train_selection" / "acceptance_train_grid_results.csv").exists()


def test_last_months_stage_subset_uses_config_end_date():
    subset = campaign_stages._subset_from_window(
        {"start_date": "2021-01-01", "end_date": "2026-06-01"},
        {"mode": "last_months", "months": 18},
    )

    assert subset == {"start_date": "2024-12-01", "end_date": "2026-06-01"}


def test_first_months_stage_subset_uses_config_start_date():
    subset = campaign_stages._subset_from_window(
        {"start_date": "2021-01-01", "end_date": "2026-06-01"},
        {"mode": "first_months", "months": 18},
    )

    assert subset == {"start_date": "2021-01-01", "end_date": "2022-07-01"}


def test_wfa_stage_subset_ends_before_incubation_and_acceptance_holdouts():
    subset = campaign_stages._subset_from_window(
        {"start_date": "2011-01-03", "end_date": "2026-06-09", "session_labels": ["RTH"]},
        {
            **campaign_stages.DEFAULT_WFA_DATA_WINDOW,
            "incubation_test_months": 12,
            "acceptance_test_months": 6,
        },
    )

    assert subset == {"start_date": "2011-01-03", "end_date": "2024-12-07", "session_labels": ["RTH"]}


def test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout():
    subset = campaign_stages._subset_from_window(
        {"start_date": "2011-01-03", "end_date": "2026-06-09", "session_labels": ["RTH"]},
        campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW,
    )

    assert subset == {"start_date": "2011-02-22", "end_date": "2012-09-06", "session_labels": ["RTH"]}
    assert pd.Timestamp(subset["end_date"]) < pd.Timestamp("2026-06-09") - pd.Timedelta(days=365)


def test_stage_subset_data_window_falls_back_to_core_data_subset():
    cfg = {
        "core": {
            "data_subset": {
                "start_date": "2011-01-03",
                "end_date": "2026-06-09",
                "session_labels": ["RTH"],
            }
        },
        "core_grid": {},
        "data": {},
    }

    subset = campaign_stages._stage_subset(
        cfg,
        {"data_window": campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW},
        "core_grid",
    )

    assert subset == {"start_date": "2011-02-22", "end_date": "2012-09-06", "session_labels": ["RTH"]}
