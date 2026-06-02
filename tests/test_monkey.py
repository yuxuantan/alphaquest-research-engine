import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.monkey import run_monkey
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


def test_monkey_summary():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    cfg = {
        "runs": 5,
        "seed": 1,
        "constraints": {
            "trade_count_tolerance_pct": 0.0,
            "trade_count_tolerance": 0,
            "long_short_ratio_tolerance": 0.0,
            "average_bars_tolerance_pct": 0.0,
        },
    }
    results, summary = run_monkey(data, BASE_CFG, cfg, {"min_trade_count": 1, "max_drawdown": 99999})
    assert len(results) == 5
    assert "median_net_profit" in summary
    assert "core_beats_monkey_net_profit_rate" in summary
    assert "core_beats_monkey_max_drawdown_rate" in summary
    assert "meets_monkey_goal" in summary
    assert summary["core_metrics"]["total_trades"] >= 1
    assert set(["total_trades", "long_ratio", "average_bars_in_trade"]).issubset(results.columns)
    assert (results["total_trades"] == summary["core_metrics"]["total_trades"]).all()


def test_monkey_retains_iteration_reports(tmp_path):
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    cfg = {
        "runs": 2,
        "seed": 1,
        "constraints": {
            "trade_count_tolerance_pct": 0.0,
            "trade_count_tolerance": 0,
            "long_short_ratio_tolerance": 0.0,
            "average_bars_tolerance_pct": 0.0,
        },
    }

    _, summary = run_monkey(
        data,
        BASE_CFG,
        cfg,
        {"min_trade_count": 1, "max_drawdown": 99999},
        report_dir=tmp_path,
    )

    trades_path = tmp_path / "monkey_iteration_trades.csv"
    daily_path = tmp_path / "monkey_iteration_daily.csv"
    assert summary["iteration_reports_retained"]
    assert str(trades_path) in summary["iteration_report_files"]
    assert str(daily_path) in summary["iteration_report_files"]
    assert trades_path.exists()
    assert daily_path.exists()

    trades = pd.read_csv(trades_path)
    assert set(["run_id", "entry_timestamp", "exit_timestamp", "net_pnl"]).issubset(trades.columns)
    assert sorted(trades["run_id"].unique().tolist()) == [1, 2]
