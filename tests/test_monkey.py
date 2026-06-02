import random

import numpy as np
import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.monkey import _sample_durations, run_monkey
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
    assert summary["constraints"]["duration_sampling"] == "core_distribution"
    assert summary["constraints"]["max_duration_bars"] >= 1
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


def test_monkey_duration_sampling_uses_core_distribution_and_cap():
    constraints = {
        "duration_sampling": "core_distribution",
        "average_bars_tolerance_pct": 0.10,
        "max_duration_sample_attempts": 10,
    }

    durations = _sample_durations(
        np_rng=np.random.default_rng(7),
        rng=random.Random(7),
        trade_count=200,
        core_durations=[5, 10, 20, 35, 55, 289],
        target_average=30.0,
        constraints=constraints,
        max_duration=55,
    )

    assert len(durations) == 200
    assert max(durations) <= 55
    assert set(durations).issubset({5, 10, 20, 35, 55})
    assert 27.0 <= np.mean(durations) <= 33.0
