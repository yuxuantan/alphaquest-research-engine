import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.intraday_range_orderflow_breakout import (
    IntradayRangeOrderflowBreakoutEntry,
)


def test_intraday_range_orderflow_breakout_uses_completed_range_and_aligned_flow():
    entry = IntradayRangeOrderflowBreakoutEntry(
        {
            "range_start": "11:30:00",
            "range_end": "13:00:00",
            "last_entry_time": "14:00:00",
            "confirmation_minutes": 5,
            "bar_interval_minutes": 5,
            "breakout_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "max_range_points": 4.0,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )

    for bar in _range_bars():
        assert entry.on_bar_close(bar) is None

    weak_flow = _bar("2024-01-03 13:00:00", close=101.5, high=101.6, signed_volume=100, volume=1000)
    assert entry.on_bar_close(weak_flow) is None

    confirmed = _bar("2024-01-03 13:05:00", close=101.75, high=101.8, signed_volume=400, volume=1000)
    signal = entry.on_bar_close(confirmed)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.breakout_level == 101.0
    assert str(signal.report_fields["intraday_range_end_timestamp"]) == "2024-01-03 13:00:00"
    assert str(signal.report_fields["breakout_timestamp"]) == "2024-01-03 13:10:00"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.4


def test_intraday_range_orderflow_breakout_uses_large_flow_mode_for_shorts():
    entry = IntradayRangeOrderflowBreakoutEntry(
        {
            "range_start": "11:30:00",
            "range_end": "13:00:00",
            "last_entry_time": "14:00:00",
            "confirmation_minutes": 5,
            "bar_interval_minutes": 5,
            "breakout_buffer_ticks": 0,
            "min_orderflow_imbalance": 0.50,
            "max_range_points": 4.0,
            "flow_mode": "large20",
            "tick_size": 0.25,
            "allow_long": False,
            "allow_short": True,
        }
    )

    for bar in _range_bars():
        assert entry.on_bar_close(bar) is None

    confirmed = _bar(
        "2024-01-03 13:00:00",
        close=98.75,
        low=98.7,
        large20_signed_volume=-120,
        large20_volume=200,
    )
    signal = entry.on_bar_close(confirmed)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["flow_mode"] == "large20"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.6


def test_engine_enters_intraday_range_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 11:30:00", periods=22, freq="5min", tz="America/New_York")
    closes = [100.0, 100.2, 100.5, 100.8, 101.0, 100.7, 100.4, 100.2, 99.9, 99.6, 99.3, 99.1, 99.0, 99.4, 99.8, 100.2, 100.6, 100.9, 101.5, 101.7, 101.4, 101.1]
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": closes,
            "high": [value + 0.1 for value in closes],
            "low": [value - 0.1 for value in closes],
            "close": closes,
            "volume": [1000] * len(timestamps),
            "signed_volume": [0] * 18 + [500, 0, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_intraday_range_orderflow",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "intraday_range_orderflow_breakout",
                "params": {
                    "range_start": "11:30:00",
                    "range_end": "13:00:00",
                    "last_entry_time": "14:00:00",
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 5,
                    "breakout_buffer_ticks": 1,
                    "min_orderflow_imbalance": 0.20,
                    "max_range_points": 4.0,
                    "flow_mode": "signed_volume",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "13:20:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "13:20:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["breakout_timestamp"]) == "2024-01-03 13:05:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 13:05:00-05:00"


def _range_bars():
    timestamps = pd.date_range("2024-01-03 11:30:00", periods=18, freq="5min")
    closes = [100.0, 100.2, 100.5, 100.8, 101.0, 100.7, 100.4, 100.2, 99.9, 99.6, 99.3, 99.1, 99.0, 99.4, 99.8, 100.2, 100.6, 100.9]
    return [_bar(str(ts), close=close, high=max(close, 101.0), low=min(close, 99.0)) for ts, close in zip(timestamps, closes)]


def _bar(
    timestamp: str,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    signed_volume: float = 0,
    volume: float = 1000,
    large20_signed_volume: float = 0,
    large20_volume: float = 0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close,
            "high": close if high is None else high,
            "low": close if low is None else low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
        }
    )
