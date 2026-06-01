from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.core_grid import run_core_grid
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


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
