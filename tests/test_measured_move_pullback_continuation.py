from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.measured_move_pullback_continuation import (
    MeasuredMovePullbackContinuationEntry,
)


def test_measured_move_pullback_long_uses_completed_pivots_and_projects_target():
    entry = MeasuredMovePullbackContinuationEntry(_params("long_continuation"))

    signal = None
    for bar in _long_bars_with_breakout():
        signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 103.0
    assert signal.sweep_low == 99.0
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:20:00")
    assert signal.metadata["signal_target_price"] == 107.0
    assert signal.report_fields["measured_move_distance"] == 4.0


def test_measured_move_pullback_short_uses_completed_pivots_and_projects_target():
    entry = MeasuredMovePullbackContinuationEntry(_params("short_continuation"))

    signal = None
    for bar in _short_bars_with_breakout():
        signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 97.0
    assert signal.sweep_high == 101.0
    assert signal.metadata["signal_target_price"] == 93.0


def test_measured_move_pullback_factory_registration_builds_module():
    entry = build_entry_module({"module": "measured_move_pullback_continuation", "params": _params("two_sided_continuation")})

    assert isinstance(entry, MeasuredMovePullbackContinuationEntry)


def _params(setup_mode: str) -> dict:
    return {
        "setup_mode": setup_mode,
        "start_time": "10:15:00",
        "end_time": "10:30:00",
        "bar_interval_minutes": 5,
        "timeframes_minutes": [5],
        "min_aligned_timeframes": 1,
        "pivot_left_bars": 1,
        "pivot_right_bars": 1,
        "min_pivot_move_ticks": 0,
        "breakout_buffer_ticks": 1,
        "min_measured_move_ticks": 4,
        "target_projection_multiple": 1.0,
    }


def _long_bars_with_breakout() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=10, freq="5min")
    rows = _pivot_rows()
    rows.append({"open": 101.0, "high": 104.0, "low": 100.5, "close": 103.5})
    return [_bar(ts, row) for ts, row in zip(timestamps, rows)]


def _short_bars_with_breakout() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=10, freq="5min")
    rows = []
    for row in _pivot_rows():
        rows.append(
            {
                "open": 200.0 - row["open"],
                "high": 200.0 - row["low"],
                "low": 200.0 - row["high"],
                "close": 200.0 - row["close"],
            }
        )
    rows.append({"open": 99.0, "high": 99.5, "low": 96.0, "close": 96.5})
    return [_bar(ts, row) for ts, row in zip(timestamps, rows)]


def _pivot_rows() -> list[dict]:
    return [
        {"open": 100.0, "high": 100.5, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.5},
        {"open": 101.5, "high": 101.0, "low": 99.5, "close": 100.0},
        {"open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0},
        {"open": 99.0, "high": 100.0, "low": 99.0, "close": 99.5},
        {"open": 99.5, "high": 103.0, "low": 100.0, "close": 102.0},
        {"open": 102.0, "high": 102.0, "low": 99.5, "close": 100.5},
        {"open": 100.5, "high": 101.0, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.0},
    ]


def _bar(timestamp: pd.Timestamp, row: dict) -> pd.Series:
    return pd.Series(
        {
            "timestamp": timestamp,
            "session_date": timestamp.date(),
            "session_label": "RTH",
            "is_rth": True,
            "volume": 1000,
            **row,
        }
    )
