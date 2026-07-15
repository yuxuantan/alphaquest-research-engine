from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.halloween_seasonal_premium import HalloweenSeasonalPremiumEntry


def _bar(timestamp: str = "2024-11-04 09:59:00", *, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 5000.0,
            "high": 5004.0,
            "low": 4998.0,
            "close": 5002.0,
        }
    )


def test_winter_long_emits_on_completed_signal_time():
    entry = HalloweenSeasonalPremiumEntry(
        {"setup_mode": "winter_long", "signal_time": "10:00:00", "bar_interval_minutes": 1}
    )

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-11-04 10:00:00")
    assert signal.report_fields["seasonal_month"] == 11


def test_winter_long_rejects_summer_month():
    entry = HalloweenSeasonalPremiumEntry({"setup_mode": "winter_long", "signal_time": "10:00:00"})

    assert entry.on_bar_close(_bar("2024-07-01 09:59:00")) is None


def test_summer_short_emits_in_summer_month():
    entry = HalloweenSeasonalPremiumEntry({"setup_mode": "summer_short", "signal_time": "10:00:00"})

    signal = entry.on_bar_close(_bar("2024-07-01 09:59:00"))

    assert signal is not None
    assert signal.direction == "short"


def test_non_rth_rejects():
    entry = HalloweenSeasonalPremiumEntry({"setup_mode": "winter_long", "signal_time": "10:00:00"})

    assert entry.on_bar_close(_bar(is_rth=False)) is None


def test_invalid_active_month_fails():
    with pytest.raises(ValueError):
        HalloweenSeasonalPremiumEntry({"setup_mode": "winter_long", "active_months": [0, 11]})
