from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.quarterly_expiration_pressure import (
    QuarterlyExpirationPressureEntry,
)


def _bar(timestamp: str, *, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 5000.0,
            "high": 5005.0,
            "low": 4995.0,
            "close": 5001.0,
        }
    )


def test_expiration_friday_signal_on_third_friday():
    entry = QuarterlyExpirationPressureEntry(
        {"setup_mode": "expiration_friday_long", "signal_time": "10:00:00", "bar_interval_minutes": 1}
    )

    signal = entry.on_bar_close(_bar("2024-03-15 09:59:00"))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["quarterly_expiration_date"] == "2024-03-15"


def test_non_expiration_friday_rejects():
    entry = QuarterlyExpirationPressureEntry(
        {"setup_mode": "expiration_friday_long", "signal_time": "10:00:00"}
    )

    assert entry.on_bar_close(_bar("2024-03-22 09:59:00")) is None


def test_monday_prior_offset_signal():
    entry = QuarterlyExpirationPressureEntry(
        {"setup_mode": "monday_prior_long", "signal_time": "10:00:00", "day_offset": -4}
    )

    signal = entry.on_bar_close(_bar("2024-03-11 09:59:00"))

    assert signal is not None
    assert signal.report_fields["expiration_day_offset"] == -4


def test_monday_after_offset_signal():
    entry = QuarterlyExpirationPressureEntry(
        {"setup_mode": "monday_after_short", "direction": "short", "signal_time": "10:00:00", "day_offset": 3}
    )

    signal = entry.on_bar_close(_bar("2024-03-18 09:59:00"))

    assert signal is not None
    assert signal.direction == "short"


def test_non_rth_rejects():
    entry = QuarterlyExpirationPressureEntry(
        {"setup_mode": "expiration_friday_long", "signal_time": "10:00:00"}
    )

    assert entry.on_bar_close(_bar("2024-03-15 09:59:00", is_rth=False)) is None
