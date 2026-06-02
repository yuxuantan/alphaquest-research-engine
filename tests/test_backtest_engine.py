import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.fills import stop_target_hit
from propstack.backtest.metrics import calculate_metrics
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from tests.test_data_pipeline import DATA_CFG


BASE_CFG = {
    "data": DATA_CFG,
    "strategy_name": "pdh_pdl_sweep",
    "strategy": {
        "entry": {
            "module": "pdh_pdl_sweep_reclaim",
            "params": {
                "reclaim_window_bars": 3,
                "min_volume_ratio": 0.0,
                "start_time": "08:30:00",
                "end_time": "14:45:00",
                "max_trades_per_day": 3,
                "allow_long": True,
                "allow_short": True,
            },
        },
        "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.5}},
        "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
        "flatten_time": "14:55:00",
    },
    "core": {
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
    assert first["strategy_name"] == "pdh_pdl_sweep"
    assert "08:32:00" in str(first["entry_timestamp"])
    assert first["commission"] == 5.0
    assert first["slippage_cost"] == 25.0


def test_opening_range_trade_log_uses_strategy_specific_report_columns():
    rows = []
    for minute in range(30, 41):
        rows.append(
            {
                "timestamp": pd.Timestamp(f"2024-01-03 09:{minute:02d}", tz="America/New_York"),
                "session_date": pd.Timestamp("2024-01-03").date(),
                "is_rth": True,
                "open": 100.0,
                "high": 100.30,
                "low": 100.00,
                "close": 100.10,
            }
        )
    rows[0].update({"open": 100.0, "high": 100.20, "low": 99.90, "close": 100.10})
    rows[2].update({"high": 100.40})
    rows[9].update({"open": 100.35, "high": 100.55, "low": 100.30, "close": 100.50})
    rows[10].update({"open": 100.55, "high": 100.70, "low": 100.50, "close": 100.65})

    cfg = {
        "strategy_name": "five_min_orb_vol_filter",
        "strategy": {
            "entry": {
                "module": "opening_range_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 1,
                    "max_opening_range_pct_of_open": 0.0055,
                    "skip_tuesday_longs": True,
                    "allow_long": True,
                    "allow_short": True,
                },
            },
            "tp": {"module": "opening_range_extension", "params": {"extension_fraction": 0.5}},
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 14}},
            "flatten_time": "15:45:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.50,
            "commission_per_contract": 2.50,
            "slippage_ticks": 0,
            "contracts": 1,
        },
    }

    trades = BacktestEngine(cfg).run(pd.DataFrame(rows))["trades"]

    assert len(trades) == 1
    assert "opening_range_start_timestamp" in trades.columns
    assert "breakout_timestamp" in trades.columns
    assert "sweep_timestamp" not in trades.columns
    assert "reclaim_timestamp" not in trades.columns
    first = trades.iloc[0]
    assert first["opening_range_start_timestamp"] == pd.Timestamp("2024-01-03 09:30", tz="America/New_York")
    assert first["opening_range_end_timestamp"] == pd.Timestamp("2024-01-03 09:35", tz="America/New_York")
    assert first["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:40", tz="America/New_York")


def test_risk_percent_sizing_uses_entry_stop_distance_per_trade():
    rows = []
    for minute in range(30, 42):
        rows.append(
            {
                "timestamp": pd.Timestamp(f"2024-01-03 09:{minute:02d}", tz="America/New_York"),
                "session_date": pd.Timestamp("2024-01-03").date(),
                "is_rth": True,
                "open": 98.0,
                "high": 99.0,
                "low": 97.0,
                "close": 98.5,
            }
        )
    for idx in range(5):
        rows[idx].update({"high": 99.0, "low": 96.0, "close": 98.0})
    rows[9].update({"open": 99.0, "high": 100.0, "low": 98.5, "close": 100.5})
    rows[10].update({"open": 100.0, "high": 102.25, "low": 99.5, "close": 102.0})

    cfg = {
        "strategy_name": "five_min_orb_vol_filter",
        "strategy": {
            "entry": {
                "module": "opening_range_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 1,
                    "max_opening_range_pct_of_open": 0.05,
                    "skip_tuesday_longs": True,
                    "allow_long": True,
                    "allow_short": True,
                },
            },
            "tp": {"module": "opening_range_extension", "params": {"extension_fraction": 1.0}},
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 14}},
            "flatten_time": "15:45:00",
        },
        "core": {
            "initial_balance": 100000,
            "tick_size": 0.25,
            "tick_value": 12.50,
            "commission_per_contract": 0,
            "slippage_ticks": 0,
            "contracts": 1,
            "position_sizing": {
                "mode": "risk_percent_initial_balance",
                "risk_pct": 0.01,
            },
        },
    }

    trades = BacktestEngine(cfg).run(pd.DataFrame(rows))["trades"]

    assert len(trades) == 1
    first = trades.iloc[0]
    assert first["contracts"] == 5
    assert first["risk_points"] == 4.0
    assert first["target_risk_amount"] == 1000.0
    assert first["dollar_risk_per_contract"] == 200.0
    assert first["planned_dollar_risk"] == 1000.0
    assert first["net_pnl"] == 500.0


def test_opening_range_skips_trade_when_opposite_edge_stop_exceeds_max():
    rows = []
    for minute in range(30, 41):
        rows.append(
            {
                "timestamp": pd.Timestamp(f"2024-01-03 09:{minute:02d}", tz="America/New_York"),
                "session_date": pd.Timestamp("2024-01-03").date(),
                "is_rth": True,
                "open": 100.0,
                "high": 100.30,
                "low": 100.00,
                "close": 100.10,
            }
        )
    rows[0].update({"open": 100.0, "high": 100.20, "low": 99.00, "close": 100.10})
    rows[2].update({"high": 100.40})
    rows[9].update({"open": 100.35, "high": 100.55, "low": 100.30, "close": 100.50})
    rows[10].update({"open": 100.55, "high": 100.70, "low": 100.50, "close": 100.65})

    cfg = {
        "strategy_name": "five_min_orb_vol_filter",
        "strategy": {
            "entry": {
                "module": "opening_range_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 1,
                    "max_opening_range_pct_of_open": 0.05,
                    "skip_tuesday_longs": True,
                    "allow_long": True,
                    "allow_short": True,
                },
            },
            "tp": {"module": "opening_range_extension", "params": {"extension_fraction": 0.5}},
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 1.0}},
            "flatten_time": "15:45:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.50,
            "commission_per_contract": 2.50,
            "slippage_ticks": 0,
            "contracts": 1,
        },
    }

    trades = BacktestEngine(cfg).run(pd.DataFrame(rows))["trades"]

    assert trades.empty


def test_opening_range_stop_out_does_not_reenter_or_reverse():
    rows = []
    for minute in range(30, 46):
        rows.append(
            {
                "timestamp": pd.Timestamp(f"2024-01-03 09:{minute:02d}", tz="America/New_York"),
                "session_date": pd.Timestamp("2024-01-03").date(),
                "is_rth": True,
                "open": 100.0,
                "high": 100.30,
                "low": 100.00,
                "close": 100.10,
            }
        )
    rows[0].update({"open": 100.0, "high": 100.20, "low": 99.90, "close": 100.10})
    rows[2].update({"high": 100.40})
    rows[9].update({"open": 100.35, "high": 100.55, "low": 100.30, "close": 100.50})
    rows[10].update({"open": 100.50, "high": 100.60, "low": 99.80, "close": 100.00})
    for idx in range(11, 16):
        rows[idx].update({"open": 99.95, "high": 100.00, "low": 99.40, "close": 99.50})

    cfg = {
        "strategy_name": "five_min_orb_vol_filter",
        "strategy": {
            "entry": {
                "module": "opening_range_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 1,
                    "max_opening_range_pct_of_open": 0.0055,
                    "max_trades_per_day": 5,
                    "skip_tuesday_longs": True,
                    "allow_long": True,
                    "allow_short": True,
                },
            },
            "tp": {"module": "opening_range_extension", "params": {"extension_fraction": 10.0}},
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 14}},
            "flatten_time": "15:45:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.50,
            "commission_per_contract": 2.50,
            "slippage_ticks": 0,
            "contracts": 1,
        },
    }

    trades = BacktestEngine(cfg).run(pd.DataFrame(rows))["trades"]

    assert len(trades) == 1
    first = trades.iloc[0]
    assert first["direction"] == "long"
    assert first["exit_reason"] == "stop"
    assert first["entry_timestamp"] == pd.Timestamp("2024-01-03 09:40", tz="America/New_York")


def test_stop_first_same_bar_rule():
    bar = pd.Series({"high": 110, "low": 90})
    reason, price = stop_target_hit(bar, "long", stop_price=95, target_price=105)
    assert reason == "stop"
    assert price == 95


def test_daily_loss_lockout_limits_trades():
    cfg = {**BASE_CFG, "core": {**BASE_CFG["core"], "daily_loss_limit": 1}}
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


def test_max_drawdown_includes_starting_balance_peak():
    trades = pd.DataFrame(
        {
            "net_pnl": [-1000.0, -500.0, 200.0],
            "gross_pnl": [-1000.0, -500.0, 200.0],
            "r_multiple": [-1.0, -0.5, 0.2],
            "entry_timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exit_timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "session_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "trade_id": [1, 2, 3],
        }
    )

    metrics = calculate_metrics(trades, initial_balance=10000)

    assert metrics["max_drawdown"] == 1500.0
    assert round(metrics["max_drawdown_pct"], 6) == round(1500 / 10000, 6)


def test_max_drawdown_orders_trades_by_exit_timestamp():
    trades = pd.DataFrame(
        {
            "net_pnl": [1000.0, -2000.0],
            "gross_pnl": [1000.0, -2000.0],
            "r_multiple": [1.0, -2.0],
            "entry_timestamp": ["2024-01-02", "2024-01-01"],
            "exit_timestamp": ["2024-01-02", "2024-01-01"],
            "session_date": ["2024-01-02", "2024-01-01"],
            "trade_id": [2, 1],
        }
    )

    metrics = calculate_metrics(trades, initial_balance=10000)

    assert metrics["max_drawdown"] == 2000.0
    assert round(metrics["max_drawdown_pct"], 6) == round(2000 / 10000, 6)
