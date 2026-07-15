from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.leveraged_etf_rebalance_pressure import (
    LeveragedEtfRebalancePressureEntry,
)


def test_leveraged_etf_rebalance_pressure_emits_long_after_up_day():
    entry = LeveragedEtfRebalancePressureEntry(
        {
            "setup_mode": "two_sided_rebalance_pressure",
            "signal_time": "15:00:00",
            "bar_interval_minutes": 1,
            "min_abs_day_return_bps": 20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 14:59", close=4020, prev_close=4000))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 15:00")
    assert signal.report_fields["day_return_bps"] == pytest.approx(50.0)


def test_leveraged_etf_rebalance_pressure_emits_short_after_down_day():
    entry = LeveragedEtfRebalancePressureEntry(
        {
            "setup_mode": "two_sided_rebalance_pressure",
            "signal_time": "15:00:00",
            "bar_interval_minutes": 1,
            "min_abs_day_return_bps": 20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 14:59", close=3980, prev_close=4000))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["day_return_bps"] == pytest.approx(-50.0)


def test_leveraged_etf_rebalance_pressure_requires_completed_signal_bar_time():
    entry = LeveragedEtfRebalancePressureEntry(
        {
            "setup_mode": "two_sided_rebalance_pressure",
            "signal_time": "15:00:00",
            "bar_interval_minutes": 1,
            "min_abs_day_return_bps": 20,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 14:58", close=4020, prev_close=4000)) is None


def test_leveraged_etf_rebalance_pressure_honors_one_sided_modes():
    long_entry = LeveragedEtfRebalancePressureEntry(
        {
            "setup_mode": "up_day_rebalance_long",
            "signal_time": "15:00:00",
            "min_abs_day_return_bps": 20,
        }
    )
    short_entry = LeveragedEtfRebalancePressureEntry(
        {
            "setup_mode": "down_day_rebalance_short",
            "signal_time": "15:00:00",
            "min_abs_day_return_bps": 20,
        }
    )

    assert long_entry.on_bar_close(_bar("2024-01-03 14:59", close=3980, prev_close=4000)) is None
    assert short_entry.on_bar_close(_bar("2024-01-03 14:59", close=4020, prev_close=4000)) is None


def test_late_acceleration_requires_recent_return_same_direction():
    entry = LeveragedEtfRebalancePressureEntry(
        {
            "setup_mode": "late_acceleration_two_sided",
            "signal_time": "15:30:00",
            "bar_interval_minutes": 1,
            "recent_lookback_minutes": 3,
            "min_abs_day_return_bps": 20,
            "min_recent_return_bps": 2,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 15:27", open_=4000, close=4001, prev_close=4000))
    entry.on_bar_close(_bar("2024-01-03 15:28", open_=4001, close=4002, prev_close=4000))
    signal = entry.on_bar_close(_bar("2024-01-03 15:29", open_=4002, close=4020, prev_close=4000))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["recent_return_bps"] > 2


def _bar(timestamp, *, close: float, prev_close: float, open_: float | None = None, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    open_value = close - 1 if open_ is None else open_
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": open_value,
            "high": max(open_value, close) + 0.25,
            "low": min(open_value, close) - 0.25,
            "close": close,
            "volume": 1000,
            "prev_rth_close": prev_close,
        }
    )
