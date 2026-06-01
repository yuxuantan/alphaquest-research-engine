from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.wfa import create_windows, run_wfa
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


def test_wfa_train_test_split():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    windows = list(create_windows(data, 1, 1, 1))
    assert windows


def test_wfa_runs():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    grid_cfg = {
        "parameters": {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0],
        }
    }
    results, summary = run_wfa(
        data,
        BASE_CFG,
        grid_cfg,
        {"train_months": 1, "test_months": 1, "step_months": 1},
        {"min_trade_count": 0, "max_drawdown": 99999},
    )
    assert "windows" in summary
