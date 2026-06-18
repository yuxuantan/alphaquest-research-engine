import pandas as pd
import pytest

from propstack.strategy_modules.entry.session_extreme_delta_divergence import (
    SessionExtremeDeltaDivergenceEntry,
)


def _bar(ts, high, low, close, signed_volume, volume=1000):
    timestamp = pd.Timestamp(ts, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": timestamp,
            "session_date": timestamp.date().isoformat(),
            "is_rth": True,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": signed_volume,
            "large10_volume": volume,
            "large20_signed_volume": signed_volume,
            "large20_volume": volume,
        }
    )


def test_session_extreme_delta_divergence_short_at_unconfirmed_fresh_high():
    entry = SessionExtremeDeltaDivergenceEntry(
        {
            "direction_mode": "high_short",
            "start_time": "09:32:00",
            "end_time": "10:00:00",
            "min_bars_since_open": 2,
            "min_extreme_break_ticks": 1,
            "close_reclaim_tolerance_ticks": 2,
            "max_delta_progress_ratio": 0.05,
        }
    )
    entry.on_bar_close(_bar("2024-01-02 09:30", 100.00, 99.50, 99.75, 200))
    entry.on_bar_close(_bar("2024-01-02 09:31", 99.90, 99.40, 99.50, -50))

    signal = entry.on_bar_close(_bar("2024-01-02 09:32", 100.50, 99.75, 100.25, -100))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 100.00
    assert signal.report_fields["price_break_ticks"] == 2.0
    assert signal.report_fields["delta_progress_ratio"] <= 0.05


def test_session_extreme_delta_divergence_rejects_confirmed_high_delta():
    entry = SessionExtremeDeltaDivergenceEntry(
        {
            "direction_mode": "high_short",
            "start_time": "09:32:00",
            "end_time": "10:00:00",
            "min_bars_since_open": 2,
            "min_extreme_break_ticks": 1,
            "close_reclaim_tolerance_ticks": 2,
            "max_delta_progress_ratio": 0.05,
        }
    )
    entry.on_bar_close(_bar("2024-01-02 09:30", 100.00, 99.50, 99.75, 100))
    entry.on_bar_close(_bar("2024-01-02 09:31", 99.90, 99.40, 99.50, 100))

    signal = entry.on_bar_close(_bar("2024-01-02 09:32", 100.50, 99.75, 100.25, 900))

    assert signal is None


def test_session_extreme_delta_divergence_long_at_unconfirmed_fresh_low():
    entry = SessionExtremeDeltaDivergenceEntry(
        {
            "direction_mode": "low_long",
            "start_time": "09:32:00",
            "end_time": "10:00:00",
            "min_bars_since_open": 2,
            "min_extreme_break_ticks": 1,
            "close_reclaim_tolerance_ticks": 2,
            "max_delta_progress_ratio": 0.05,
        }
    )
    entry.on_bar_close(_bar("2024-01-02 09:30", 100.50, 100.00, 100.25, -200))
    entry.on_bar_close(_bar("2024-01-02 09:31", 100.60, 100.10, 100.30, 50))

    signal = entry.on_bar_close(_bar("2024-01-02 09:32", 100.25, 99.50, 99.75, 100))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 100.00
    assert signal.report_fields["price_break_ticks"] == 2.0
    assert signal.report_fields["delta_progress_ratio"] >= -0.05


def test_session_extreme_delta_divergence_validates_direction_mode():
    with pytest.raises(ValueError, match="direction_mode"):
        SessionExtremeDeltaDivergenceEntry({"direction_mode": "sideways"})
