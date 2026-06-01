from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.monkey import run_monkey
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


def test_monkey_summary():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    cfg = {
        "runs": 3,
        "seed": 1,
        "parameter_ranges": {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0, 1.5],
        },
        "stress": {},
    }
    results, summary = run_monkey(data, BASE_CFG, cfg, {"min_trade_count": 1, "max_drawdown": 99999})
    assert len(results) == 3
    assert "median_net_profit" in summary
