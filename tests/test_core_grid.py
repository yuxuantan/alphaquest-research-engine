import pandas as pd
import pytest

from alphaquest.data.clean import clean_data
from alphaquest.data.features import build_features
import alphaquest.research.core_grid as core_grid_module
from alphaquest.research.core_grid import parameter_combinations, run_core_grid
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


def test_parameter_combinations_uses_full_cartesian_product():
    combos = parameter_combinations(
        {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0, 1.5, 2.0],
            "entry.params.allow_long": [True, False],
        }
    )

    assert len(combos) == 12
    assert combos[0] == {
        "entry.params.reclaim_window_bars": 2,
        "tp.params.target_r_multiple": 1.0,
        "entry.params.allow_long": True,
    }
    assert combos[-1] == {
        "entry.params.reclaim_window_bars": 3,
        "tp.params.target_r_multiple": 2.0,
        "entry.params.allow_long": False,
    }


def test_empty_parameter_grid_is_one_fixed_configuration():
    assert parameter_combinations({}) == [{}]


def test_parameter_combinations_requires_lists():
    with pytest.raises(ValueError, match="must be a list"):
        parameter_combinations({"entry.params.reclaim_window_bars": 3})


def test_parameter_combinations_rejects_target_r_multiple_below_one():
    with pytest.raises(ValueError, match="target_r_multiple must be >= 1.0"):
        parameter_combinations({"tp.params.target_r_multiple": [0.75, 1.0]})


def test_core_grid_pass_percentage():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    grid_cfg = {
        "parameters": {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0],
        }
    }
    results, summary = run_core_grid(data, BASE_CFG, grid_cfg, {"min_trade_count": 1, "max_drawdown": 99999})
    assert len(results) == 2
    assert "percentage_passing_benchmark" in summary
    assert "percentage_profitable_iterations" in summary
    assert {"signals_generated", "entries_opened", "trades_closed"}.issubset(results.columns)
    assert summary["signal_density"]["total_combinations"] == 2
    assert summary["signal_density"]["combinations_with_trades"] == 2


def test_core_grid_labels_empty_grid_as_fixed_config():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)

    results, summary = run_core_grid(
        data,
        BASE_CFG,
        {"parameters": {}},
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert len(results) == 1
    assert summary["parameter_mode"] == "fixed_config"
    assert summary["expected_combinations"] == 1


def test_core_grid_summary_and_iteration_audit_reports(tmp_path):
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    grid_cfg = {
        "min_profitable_iteration_rate": 0.75,
        "parameters": {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0, 1.5],
            "sl.params.stop_offset_ticks": [1, 2],
        },
    }

    results, summary = run_core_grid(
        data,
        BASE_CFG,
        grid_cfg,
        {"min_trade_count": 0, "max_drawdown": 99999},
        report_dir=tmp_path,
    )

    assert len(results) == 8
    assert summary["parameter_value_counts"] == {
        "entry.params.reclaim_window_bars": 2,
        "tp.params.target_r_multiple": 2,
        "sl.params.stop_offset_ticks": 2,
    }
    assert summary["expected_combinations"] == 8
    assert summary["total_combinations_tested"] == 8
    assert summary["profitable_iterations"] == 8
    assert summary["percentage_profitable_iterations"] == 1.0
    assert summary["profitable_iteration_threshold"] == 0.75
    assert summary["meets_profitable_iteration_threshold"] is True
    assert summary["iteration_reports_retained"] is True

    trades = pd.read_csv(tmp_path / "core_grid_iteration_trades.csv")
    daily = pd.read_csv(tmp_path / "core_grid_iteration_daily.csv")
    assert sorted(trades["run_id"].unique().tolist()) == list(range(1, 9))
    assert "entry.params.reclaim_window_bars" in trades.columns
    assert "tp.params.target_r_multiple" in daily.columns

    audit_pnl = trades.groupby("run_id")["net_pnl"].sum()
    for _, row in results.iterrows():
        assert round(audit_pnl[int(row["run_id"])], 8) == round(row["net_profit"], 8)


def test_core_grid_signal_density_flags_zero_signal_parameter_space():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    cfg = {
        **BASE_CFG,
        "strategy": {
            **BASE_CFG["strategy"],
            "entry": {
                **BASE_CFG["strategy"]["entry"],
                "params": {
                    **BASE_CFG["strategy"]["entry"]["params"],
                    "start_time": "18:00:00",
                    "end_time": "18:01:00",
                },
            },
        },
    }
    results, summary = run_core_grid(
        data,
        cfg,
        {"parameters": {"entry.params.reclaim_window_bars": [2, 3], "tp.params.target_r_multiple": [1.0]}},
        {"min_trade_count": 1},
    )

    assert results["signals_generated"].sum() == 0
    assert results["entries_opened"].sum() == 0
    assert summary["signal_density"]["all_combinations_zero_signals"] is True
    assert summary["signal_density"]["all_combinations_zero_trades"] is True
    assert summary["signal_density"]["combinations_meeting_50_trades_per_year"] == 0


def test_core_grid_parallel_branch_is_configurable(monkeypatch):
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    calls = []

    def fake_run_parallel_core_grid(data, detail_data, base_config, benchmarks, combos, workers, include_reports=False):
        calls.append({"combos": combos, "workers": workers, "include_reports": include_reports})
        results = []
        for idx, combo in enumerate(combos, start=1):
            row, _, _ = core_grid_module._evaluate_core_grid_combo(
                data,
                base_config,
                benchmarks,
                idx,
                combo,
            )
            results.append((row, pd.DataFrame(), pd.DataFrame()))
        return results

    monkeypatch.setattr(core_grid_module.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(core_grid_module, "_run_parallel_core_grid", fake_run_parallel_core_grid)
    grid_cfg = {
        "parallel": {"enabled": True, "workers": 2, "scope": "grid"},
        "parameters": {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0],
        },
    }

    results, summary = run_core_grid(
        data,
        BASE_CFG,
        grid_cfg,
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert len(results) == 2
    assert calls == [
        {
            "combos": [
                {"entry.params.reclaim_window_bars": 2, "tp.params.target_r_multiple": 1.0},
                {"entry.params.reclaim_window_bars": 3, "tp.params.target_r_multiple": 1.0},
            ],
            "workers": 2,
            "include_reports": False,
        }
    ]
    assert summary["parallel"] == {"enabled": True, "workers": 2, "scope": "grid"}


def test_core_grid_parallel_can_retain_iteration_reports(tmp_path, monkeypatch):
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    monkeypatch.setattr(core_grid_module.os, "cpu_count", lambda: 8)

    def fake_run_parallel_core_grid(data, detail_data, base_config, benchmarks, combos, workers, include_reports=False):
        results = []
        for idx, combo in enumerate(combos, start=1):
            results.append(
                core_grid_module._evaluate_core_grid_combo(
                    data,
                    base_config,
                    benchmarks,
                    idx,
                    combo,
                    include_reports=include_reports,
                )
            )
        return results

    monkeypatch.setattr(core_grid_module, "_run_parallel_core_grid", fake_run_parallel_core_grid)
    results, summary = run_core_grid(
        data,
        BASE_CFG,
        {
            "parallel": {"enabled": True, "workers": 2},
            "parameters": {"entry.params.reclaim_window_bars": [2, 3]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
        report_dir=tmp_path,
    )

    assert len(results) == 2
    assert summary["iteration_reports_retained"] is True
    assert summary["parallel"] == {"enabled": True, "workers": 2, "scope": "grid"}
    assert (tmp_path / "core_grid_iteration_trades.csv").exists()
    assert (tmp_path / "core_grid_iteration_daily.csv").exists()
