import pandas as pd
import pytest

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.core_grid import parameter_combinations, run_core_grid
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


def test_parameter_combinations_requires_lists():
    with pytest.raises(ValueError, match="must be a list"):
        parameter_combinations({"entry.params.reclaim_window_bars": 3})


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
