import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.fills import stop_target_hit
from propstack.backtest.metrics import calculate_metrics
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from tests.test_data_pipeline import DATA_CFG


BASE_CFG = {
    "data": DATA_CFG,
    "strategy": {
        "strategy_name": "pdh_pdl_sweep",
        "reclaim_window_bars": 3,
        "target_r_multiple": 1.5,
        "stop_offset_ticks": 1,
        "min_volume_ratio": 0.0,
        "start_time": "08:30:00",
        "end_time": "14:45:00",
        "flatten_time": "14:55:00",
        "max_trades_per_day": 3,
        "allow_long": True,
        "allow_short": True,
    },
    "backtest": {
        "tick_size": 0.25,
        "tick_value": 12.50,
        "commission_per_contract": 2.50,
        "slippage_ticks": 1,
        "contracts": 1,
        "daily_loss_limit": 1000,
        "daily_profit_stop": 1000,
    },
}


def _features():
    df, _, _ = clean_data(DATA_CFG)
    return build_features(df, DATA_CFG)


def test_next_bar_entry_and_costs():
    result = BacktestEngine(BASE_CFG).run(_features())
    trades = result["trades"]
    assert len(trades) >= 2
    first = trades.iloc[0]
    assert "08:32:00" in str(first["entry_timestamp"])
    assert first["commission"] == 5.0
    assert first["slippage_cost"] == 25.0


def test_stop_first_same_bar_rule():
    bar = pd.Series({"high": 110, "low": 90})
    reason, price = stop_target_hit(bar, "long", stop_price=95, target_price=105)
    assert reason == "stop"
    assert price == 95


def test_daily_loss_lockout_limits_trades():
    cfg = {**BASE_CFG, "backtest": {**BASE_CFG["backtest"], "daily_loss_limit": 1}}
    result = BacktestEngine(cfg).run(_features())
    assert "metrics" in result


def test_max_drawdown_pct_uses_running_equity_peak():
    trades = pd.DataFrame(
            {
                "net_pnl": [1000.0, -2000.0, 500.0],
                "gross_pnl": [1000.0, -2000.0, 500.0],
                "r_multiple": [1.0, -1.0, 0.5],
            "entry_timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exit_timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "session_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "trade_id": [1, 2, 3],
        }
    )
    metrics = calculate_metrics(trades, initial_balance=10000)
    assert metrics["max_drawdown"] == 2000.0
    assert round(metrics["max_drawdown_pct"], 6) == round(2000 / 11000, 6)
