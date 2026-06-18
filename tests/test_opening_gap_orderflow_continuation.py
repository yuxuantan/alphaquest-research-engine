from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.opening_gap_orderflow_continuation import (
    OpeningGapOrderflowContinuationEntry,
)


def test_opening_gap_continuation_requires_gap_hold_and_aligned_flow():
    entry = OpeningGapOrderflowContinuationEntry(_params(min_orderflow_imbalance=0.20))
    assert entry.on_bar_close(_bar("2024-01-03 09:30", open_=102.0, high=102.5, low=101.5, close=102.2)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:45", open_=102.1, high=102.5, low=101.5, close=102.3, signed_volume=300)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:50", open_=102.3, high=102.7, low=101.6, close=102.4, signed_volume=250)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:55", open_=102.4, high=102.9, low=101.7, close=102.8, signed_volume=300)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["opening_gap_ticks"] == 8.0
    assert signal.report_fields["primary_orderflow_imbalance"] == 0.2833333333333333


def test_opening_gap_continuation_rejects_gap_fill_and_opposing_flow():
    filled = OpeningGapOrderflowContinuationEntry(_params(min_orderflow_imbalance=0.20))
    filled.on_bar_close(_bar("2024-01-03 09:30", open_=102.0, high=102.5, low=101.5, close=102.2))
    filled.on_bar_close(_bar("2024-01-03 09:45", open_=102.1, high=102.5, low=99.75, close=102.3, signed_volume=300))
    filled.on_bar_close(_bar("2024-01-03 09:50", open_=102.3, high=102.7, low=101.6, close=102.4, signed_volume=250))
    assert (
        filled.on_bar_close(
            _bar("2024-01-03 09:55", open_=102.4, high=102.9, low=101.7, close=102.8, signed_volume=300)
        )
        is None
    )

    opposing = OpeningGapOrderflowContinuationEntry(_params(min_orderflow_imbalance=0.20))
    opposing.on_bar_close(_bar("2024-01-03 09:30", open_=102.0, high=102.5, low=101.5, close=102.2))
    opposing.on_bar_close(_bar("2024-01-03 09:45", open_=102.1, high=102.5, low=101.5, close=102.3, signed_volume=-300))
    opposing.on_bar_close(_bar("2024-01-03 09:50", open_=102.3, high=102.7, low=101.6, close=102.4, signed_volume=-250))
    assert (
        opposing.on_bar_close(
            _bar("2024-01-03 09:55", open_=102.4, high=102.9, low=101.7, close=102.8, signed_volume=-300)
        )
        is None
    )


def test_engine_enters_opening_gap_continuation_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=8, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [102.0, 102.2, 102.1, 102.1, 102.3, 102.4, 102.8, 103.0],
            "high": [102.5, 102.4, 102.3, 102.5, 102.7, 102.9, 103.2, 103.4],
            "low": [101.5, 101.7, 101.6, 101.5, 101.6, 101.7, 102.6, 102.8],
            "close": [102.2, 102.1, 102.2, 102.3, 102.4, 102.8, 103.0, 103.2],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
            "signed_volume": [0, 0, 0, 300, 250, 300, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
            "prev_rth_close": [100.0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_opening_gap_continuation",
        "timeframe": "5m",
        "strategy": {
            "entry": {"module": "opening_gap_orderflow_continuation", "params": _params(min_orderflow_imbalance=0.20)},
            "sl": {"module": "opening_gap_boundary", "params": {"stop_offset_ticks": 4, "max_stop_points": 10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:10:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:10:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["opening_gap_orderflow_signal_timestamp"]) == "2024-01-03 10:00:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 10:00:00-05:00"


def _params(**overrides):
    params = {
        "setup_mode": "unit_gap_continuation",
        "direction_mode": "two_sided_continuation",
        "flow_mode": "signed_imbalance",
        "rth_start": "09:30:00",
        "source_start": "09:45:00",
        "signal_time": "10:00:00",
        "flatten_time": "10:10:00",
        "bar_interval_minutes": 5,
        "tick_size": 0.25,
        "min_opening_gap_ticks": 4,
        "min_orderflow_imbalance": 0.20,
        "hold_buffer_ticks": 0,
        "min_source_return_ticks": 0,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _bar(
    timestamp: str,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
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
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": 0,
            "large20_volume": 0,
            "prev_rth_close": 100.0,
        }
    )
