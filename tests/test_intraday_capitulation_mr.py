from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.intraday_capitulation_mr import IntradayCapitulationMREntry


def test_capitulation_requires_completed_sell_imbalance():
    blocked = IntradayCapitulationMREntry(_params(min_sell_imbalance=0.20))
    for bar in [
        *_window("2024-01-03 09:30", 100.0, 100.5, 99.5, 100.0, 500, 100.0, -50),
        *_window("2024-01-03 09:35", 100.0, 100.2, 98.0, 98.1, 800, 99.0, -100),
    ]:
        signal = blocked.on_bar_close(bar)
    assert signal is None

    confirmed = IntradayCapitulationMREntry(_params(min_sell_imbalance=0.20))
    for bar in [
        *_window("2024-01-03 09:30", 100.0, 100.5, 99.5, 100.0, 500, 100.0, -50),
        *_window("2024-01-03 09:35", 100.0, 100.2, 98.0, 98.1, 800, 99.0, -240),
    ]:
        signal = confirmed.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["capitulation_signed_imbalance"] == -0.3
    assert signal.report_fields["rsi_scope"] == "session"


def test_capitulation_indicator_history_resets_by_session():
    entry = IntradayCapitulationMREntry(_params(min_sell_imbalance=0.20))
    for bar in [
        *_window("2024-01-03 15:45", 100.0, 100.5, 99.5, 100.0, 500, 100.0, -50),
        *_window("2024-01-03 15:50", 100.0, 100.2, 98.0, 98.1, 800, 99.0, -240),
    ]:
        entry.on_bar_close(bar)

    next_day_signal = None
    for bar in _window("2024-01-04 09:30", 100.0, 100.2, 98.0, 98.1, 800, 99.0, -240):
        next_day_signal = entry.on_bar_close(bar)

    assert next_day_signal is None


def test_engine_enters_capitulation_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=5, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 100.0, 98.0, 98.2, 98.4],
            "high": [100.5, 100.0, 98.2, 98.5, 98.8],
            "low": [99.5, 98.0, 97.8, 98.0, 98.2],
            "close": [100.0, 98.1, 98.2, 98.4, 98.6],
            "volume": [500, 800, 700, 700, 700],
            "signed_volume": [-50, -300, -100, -50, -50],
            "vwap": [100.0, 99.0, 98.9, 98.8, 98.6],
        }
    )
    cfg = {
        "strategy_name": "test_intraday_capitulation_mr",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "intraday_capitulation_mr",
                "params": _params(bar_interval_minutes=5, timeframe_minutes=5, min_sell_imbalance=0.20),
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.005, "round_to_tick": True}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:43:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:43:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["capitulation_bar_end_timestamp"]) == "2024-01-03 09:40:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:40:00-05:00"
    assert trade["entry_price"] == 98.0


def _params(**overrides):
    params = {
        "timeframe_minutes": 5,
        "bar_interval_minutes": 1,
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "last_signal_time": "16:00:00",
        "rsi_period": 1,
        "max_rsi": 35,
        "volume_avg_window": 1,
        "min_volume_avg_bars": 1,
        "min_volume_ratio": 1.5,
        "max_close_location_from_low": 0.25,
        "tick_size": 0.25,
        "min_down_move_ticks": 4,
        "min_sell_imbalance": 0.0,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _window(start, open_, high, low, close, total_volume, vwap, signed_volume):
    start_ts = pd.Timestamp(start, tz="America/New_York")
    rows = []
    for minute in range(5):
        ts = start_ts + pd.Timedelta(minutes=minute)
        rows.append(
            pd.Series(
                {
                    "timestamp": ts,
                    "session_date": ts.date(),
                    "is_rth": True,
                    "open": open_ if minute == 0 else close,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": total_volume / 5,
                    "signed_volume": signed_volume / 5,
                    "vwap": vwap,
                },
                name=ts.hour * 60 + ts.minute,
            )
        )
    return rows
