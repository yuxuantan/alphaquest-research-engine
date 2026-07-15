from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.calendar_session_bias import CalendarSessionBiasEntry


def test_calendar_session_bias_emits_configured_weekday_direction_on_completed_bar():
    entry = CalendarSessionBiasEntry(
        {
            "weekday_directions": {0: "short", 4: "long"},
            "signal_time": "10:00:00",
            "bar_interval_minutes": 5,
        }
    )

    monday = entry.on_bar_close(_bar("2024-01-08 09:55", close=100.0))
    assert monday is not None
    assert monday.direction == "short"
    assert monday.reclaim_timestamp == pd.Timestamp("2024-01-08 10:00")

    friday = entry.on_bar_close(_bar("2024-01-12 09:55", close=100.0))
    assert friday is not None
    assert friday.direction == "long"


def test_calendar_session_bias_rejects_unconfigured_and_non_rth_sessions():
    entry = CalendarSessionBiasEntry(
        {
            "weekday_directions": {4: "long"},
            "signal_time": "10:00:00",
            "bar_interval_minutes": 5,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-10 09:55", close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-12 09:55", close=100.0, is_rth=False)) is None


def _bar(timestamp: str, *, close: float, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        }
    )
