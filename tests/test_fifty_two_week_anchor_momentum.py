from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.fifty_two_week_anchor_momentum import FiftyTwoWeekAnchorMomentumEntry


def test_near_high_opening_drive_long_uses_prior_252_day_anchor() -> None:
    entry = FiftyTwoWeekAnchorMomentumEntry(
        {
            "setup_mode": "near_high_opening_drive_long",
            "start_time": "10:00:00",
            "end_time": "10:00:00",
            "proximity_pct": 0.02,
            "min_session_return_bps": 10,
        }
    )
    _seed_daily_stats(entry, start=date(2023, 1, 2), count=252, base=100.0, step=0.1)

    signal = entry.on_bar_close(_bar("2024-01-02 09:55", open_=125.0, high=126.0, low=124.75, close=125.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-02 10:00")
    assert signal.report_fields["anchor_high_session_date"] != "2024-01-02"
    assert signal.report_fields["nearness_to_high"] >= 0.98


def test_current_session_spike_does_not_create_near_high_state() -> None:
    entry = FiftyTwoWeekAnchorMomentumEntry(
        {
            "setup_mode": "near_high_breakout_long",
            "start_time": "10:00:00",
            "end_time": "10:00:00",
            "proximity_pct": 0.02,
            "breakout_buffer_ticks": 0,
        }
    )
    _seed_daily_stats(entry, start=date(2023, 1, 2), count=252, base=100.0, step=0.0, anchor_high=200.0)

    signal = entry.on_bar_close(_bar("2024-01-02 09:55", open_=100.0, high=205.0, low=99.0, close=205.0))

    assert signal is None


def test_far_from_high_opening_drive_short() -> None:
    entry = FiftyTwoWeekAnchorMomentumEntry(
        {
            "setup_mode": "far_from_high_opening_drive_short",
            "start_time": "10:00:00",
            "end_time": "10:00:00",
            "far_from_high_pct": 0.08,
            "min_session_return_bps": 10,
        }
    )
    _seed_daily_stats(entry, start=date(2023, 1, 2), count=252, base=100.0, step=0.0, anchor_high=125.0)

    signal = entry.on_bar_close(_bar("2024-01-02 09:55", open_=100.0, high=100.25, low=98.5, close=99.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["nearness_to_high"] <= 0.92


def test_near_high_pullback_requires_completed_pullback_and_reclaim() -> None:
    entry = FiftyTwoWeekAnchorMomentumEntry(
        {
            "setup_mode": "near_high_pullback_reclaim_long",
            "start_time": "09:45:00",
            "end_time": "10:00:00",
            "proximity_pct": 0.02,
            "pullback_min_bps": 20,
            "min_session_return_bps": 0,
            "breakout_buffer_ticks": 0,
        }
    )
    _seed_daily_stats(entry, start=date(2023, 1, 2), count=252, base=100.0, step=0.1)

    assert entry.on_bar_close(_bar("2024-01-02 09:40", open_=125.0, high=125.1, low=124.0, close=124.5)) is None
    signal = entry.on_bar_close(_bar("2024-01-02 09:55", open_=124.5, high=125.6, low=124.4, close=125.5))

    assert signal is not None
    assert signal.direction == "long"


def test_near_high_anchor_hold_requires_completed_hold_above_anchor_buffer() -> None:
    entry = FiftyTwoWeekAnchorMomentumEntry(
        {
            "setup_mode": "near_high_anchor_hold_long",
            "start_time": "10:30:00",
            "end_time": "10:30:00",
            "proximity_pct": 0.05,
            "hold_buffer_bps": 25,
            "min_session_return_bps": 0,
        }
    )
    _seed_daily_stats(entry, start=date(2023, 1, 2), count=252, base=100.0, step=0.1)

    signal = entry.on_bar_close(_bar("2024-01-02 10:25", open_=125.0, high=126.0, low=124.9, close=125.5))

    assert signal is not None
    assert signal.direction == "long"


def test_near_high_extension_hold_requires_prior_close_extension() -> None:
    entry = FiftyTwoWeekAnchorMomentumEntry(
        {
            "setup_mode": "near_high_extension_hold_long",
            "start_time": "11:30:00",
            "end_time": "11:30:00",
            "proximity_pct": 0.05,
            "extension_min_bps": 10,
            "min_session_return_bps": 0,
        }
    )
    _seed_daily_stats(entry, start=date(2023, 1, 2), count=252, base=100.0, step=0.1)

    assert entry.on_bar_close(_bar("2024-01-02 11:25", open_=125.0, high=125.05, low=124.8, close=125.0)) is None
    signal = entry.on_bar_close(_bar("2024-01-02 11:25", open_=125.0, high=126.0, low=124.8, close=125.25))

    assert signal is not None
    assert signal.direction == "long"


def test_fifty_two_week_anchor_registered_entry_module() -> None:
    entry = build_entry_module(
        {
            "module": "fifty_two_week_anchor_momentum",
            "params": {"setup_mode": "near_high_opening_drive_long"},
        }
    )

    assert isinstance(entry, FiftyTwoWeekAnchorMomentumEntry)


def _seed_daily_stats(
    entry: FiftyTwoWeekAnchorMomentumEntry,
    *,
    start: date,
    count: int,
    base: float,
    step: float,
    anchor_high: float | None = None,
) -> None:
    for idx in range(count):
        day = start + timedelta(days=idx)
        close = base + idx * step
        high = close + 0.5
        if anchor_high is not None and idx == count // 2:
            high = anchor_high
        entry.on_bar_close(
            _bar(
                f"{day.isoformat()} 15:55",
                open_=close - 0.25,
                high=high,
                low=close - 0.5,
                close=close,
            )
        )


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> pd.Series:
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
            "volume": 1000,
        }
    )
