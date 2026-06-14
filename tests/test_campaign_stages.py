import pandas as pd

from propstack.research.campaign_stages import evaluate_criteria
from propstack.research import campaign_stages


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


def test_default_stage_criteria_match_screenshot_benchmarks():
    limited_monkey = campaign_stages._criteria_for_stage("limited_monkey_test", {})
    wfa = campaign_stages._criteria_for_stage("walk_forward_analysis", {})
    incubation = campaign_stages._criteria_for_stage("simulated_incubation_core", {})
    acceptance = campaign_stages._criteria_for_stage(campaign_stages.ACCEPTANCE_STAGE, {})

    def by_metric(criteria):
        return {item["metric"]: item for item in criteria}

    assert by_metric(limited_monkey)["summary.core_beats_monkey_net_profit_rate"]["min"] == 0.90
    assert by_metric(wfa)["stitched_oos_metrics.profit_factor"]["min"] == 1.2
    assert by_metric(wfa)["stitched_oos_metrics.mar"]["min"] == 0.4
    assert by_metric(wfa)["stitched_oos_metrics.total_trades"]["min"] == 500
    assert "stitched_oos_metrics.expectancy_r" not in by_metric(wfa)
    assert "stitched_oos_metrics.win_rate" not in by_metric(wfa)
    assert by_metric(campaign_stages._criteria_for_stage("wfa_oos_monkey_test", {}))[
        "summary.core_beats_monkey_net_profit_rate"
    ]["min"] == 0.80
    assert by_metric(incubation)["metrics.profit_factor"]["min"] == 1.0
    assert by_metric(incubation)["metrics.mar"]["min"] == 1.0
    assert by_metric(incubation)["metrics.total_trades"]["min"] == 75
    assert "metrics.expectancy_r" not in by_metric(incubation)
    assert by_metric(acceptance)["metrics.profit_factor"]["min"] == 1.0
    assert by_metric(acceptance)["metrics.mar"]["min"] == 1.0
    assert by_metric(acceptance)["metrics.total_trades"]["min"] == 25
    assert "metrics.expectancy_r" not in by_metric(acceptance)
    assert "metrics.win_rate" not in by_metric(acceptance)


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
    mc_results = evaluate_criteria({"summary": {"probability_profit_before_drawdown": 0.5}}, mc_criteria)
    assert mc_results[0]["passed"] is False
    assert mc_results[0]["expected"] == {"exclusive_min": 0.5}


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


def test_incubation_train_selection_forces_mar_objective(tmp_path, monkeypatch):
    seen = {}

    def fake_prepare_stage_data(cfg, subset, stage_dir, skip_validation, show_progress=False):
        return pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-02"], utc=True)}), None, {"rows": 1}, "hash"

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


def test_default_stage_order_runs_acceptance_last():
    assert campaign_stages.DEFAULT_STAGE_ORDER[-1] == campaign_stages.ACCEPTANCE_STAGE
    assert campaign_stages._stage_order({})[-1] == campaign_stages.ACCEPTANCE_STAGE


def test_canonicalize_campaign_config_can_exclude_acceptance():
    cfg = campaign_stages.canonicalize_campaign_config({}, include_acceptance=False)
    campaign_tests = cfg["campaign_tests"]

    assert campaign_tests["stage_order"] == campaign_stages.PRE_ACCEPTANCE_STAGE_ORDER
    assert campaign_tests[campaign_stages.ACCEPTANCE_STAGE]["enabled"] is False
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
                        "trades_per_year": 50.0,
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
                        "trades_per_year": 50.0,
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
