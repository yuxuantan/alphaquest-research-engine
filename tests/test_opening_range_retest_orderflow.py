from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.opening_range_retest_orderflow import OpeningRangeRetestOrderflowEntry
from propstack.strategy_modules.sl.opening_range_retest_boundary import OpeningRangeRetestBoundaryStop


def test_upside_retest_long_requires_absorbed_selling_flow():
    entry = OpeningRangeRetestOrderflowEntry(_params(flow_confirmation="absorbed", min_orderflow_imbalance=0.20))
    for bar in _bars("2024-01-03", [100.0, 100.1, 100.2, 100.1, 100.0]):
        assert entry.on_bar_close(bar) is None

    assert entry.on_bar_close(_bar("2024-01-03 09:35", close=100.75, high=101.0, signed_volume=500)) is None
    weak = _bar("2024-01-03 09:36", close=100.35, high=100.6, low=100.15, signed_volume=-100)
    assert entry.on_bar_close(weak) is None

    entry = OpeningRangeRetestOrderflowEntry(_params(flow_confirmation="absorbed", min_orderflow_imbalance=0.20))
    for bar in _bars("2024-01-03", [100.0, 100.1, 100.2, 100.1, 100.0]):
        entry.on_bar_close(bar)
    entry.on_bar_close(_bar("2024-01-03 09:35", close=100.75, high=101.0, signed_volume=500))
    signal = entry.on_bar_close(_bar("2024-01-03 09:36", close=100.35, high=100.6, low=100.15, signed_volume=-350))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.breakout_level == 100.2
    assert signal.report_fields["flow_confirmation"] == "absorbed"
    assert signal.report_fields["retest_orderflow_imbalance"] == -0.35


def test_downside_retest_short_requires_aligned_selling_flow():
    entry = OpeningRangeRetestOrderflowEntry(
        _params(flow_confirmation="aligned", min_orderflow_imbalance=0.20, allow_long=False, allow_short=True)
    )
    for bar in _bars("2024-01-03", [100.0, 100.1, 100.2, 100.1, 100.0]):
        entry.on_bar_close(bar)

    assert entry.on_bar_close(_bar("2024-01-03 09:35", close=99.4, low=99.25, signed_volume=-500)) is None
    signal = entry.on_bar_close(_bar("2024-01-03 09:36", close=99.75, high=100.05, low=99.7, signed_volume=-300))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.breakout_level == 99.8
    assert signal.report_fields["flow_confirmation"] == "aligned"
    assert signal.report_fields["retest_orderflow_imbalance"] == -0.3


def test_retest_boundary_stop_uses_broken_level():
    entry = OpeningRangeRetestOrderflowEntry(_params(flow_confirmation="absorbed", min_orderflow_imbalance=0.20))
    for bar in _bars("2024-01-03", [100.0, 100.1, 100.2, 100.1, 100.0]):
        entry.on_bar_close(bar)
    entry.on_bar_close(_bar("2024-01-03 09:35", close=100.75, high=101.0, signed_volume=500))
    signal = entry.on_bar_close(_bar("2024-01-03 09:36", close=100.35, high=100.6, low=100.15, signed_volume=-350))

    stop = OpeningRangeRetestBoundaryStop({"stop_offset_ticks": 2, "max_stop_points": 5}).price(
        signal,
        "long",
        0.25,
        entry_price=100.5,
    )

    assert stop == 99.7


def test_engine_enters_retest_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=9, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100, 100, 100, 100, 100, 100.8, 100.4, 100.5, 100.7],
            "high": [100.2, 100.1, 100.2, 100.1, 100.0, 101.0, 100.6, 100.8, 100.9],
            "low": [99.8, 99.9, 99.9, 99.9, 99.9, 100.7, 100.15, 100.45, 100.6],
            "close": [100.0, 100.1, 100.2, 100.1, 100.0, 100.75, 100.35, 100.7, 100.8],
            "volume": [1000] * len(timestamps),
            "signed_volume": [0, 0, 0, 0, 0, 500, -350, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_or_retest_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "opening_range_retest_orderflow",
                "params": _params(flow_confirmation="absorbed", min_orderflow_imbalance=0.20),
            },
            "sl": {"module": "opening_range_retest_boundary", "params": {"stop_offset_ticks": 2, "max_stop_points": 10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:39:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:39:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["signal_timestamp"]) == "2024-01-03 09:37:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:37:00-05:00"


def _params(**overrides):
    params = {
        "rth_start": "09:30:00",
        "opening_range_minutes": 5,
        "bar_interval_minutes": 1,
        "last_entry_time": "10:00:00",
        "breakout_buffer_ticks": 1,
        "retest_tolerance_ticks": 4,
        "hold_buffer_ticks": 0,
        "max_retest_bars": 3,
        "flow_lookback_bars": 1,
        "min_orderflow_imbalance": 0.20,
        "flow_mode": "signed_volume",
        "flow_confirmation": "absorbed",
        "tick_size": 0.25,
        "max_trades_per_day": 1,
        "allow_long": True,
        "allow_short": True,
    }
    params.update(overrides)
    return params


def _bars(session_date: str, closes: list[float]):
    out = []
    timestamps = pd.date_range(f"{session_date} 09:30:00", periods=len(closes), freq="1min")
    for ts, close in zip(timestamps, closes):
        out.append(_bar(str(ts), close=close, high=max(close, 100.2), low=min(close, 99.8)))
    return out


def _bar(
    timestamp: str,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    signed_volume: float = 0,
    volume: float = 1000,
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
            "large20_signed_volume": 0,
            "large20_volume": 0,
        }
    )
