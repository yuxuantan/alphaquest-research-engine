from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.true_vap_aoi_breakout_continuation import (
    TrueVapAoiBreakoutContinuationEntry,
)


def _bar(
    timestamp: str,
    session_date: str,
    *,
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.75,
    close: float = 100.75,
    volume: float = 1000.0,
    signed_volume: float = 100.0,
    large10_signed_volume: float = 100.0,
    large10_volume: float = 500.0,
    large20_signed_volume: float = 100.0,
    large20_volume: float = 400.0,
    prev_rth_high: float = 100.5,
    prev_rth_low: float = 99.5,
    buy_imbalance_volume: float = 30.0,
    sell_imbalance_volume: float = 30.0,
    prior_vap_poc: float = 100.5,
    prior_vap_vah: float = 101.5,
    prior_vap_val: float = 99.0,
    prior_vap_lvn_near_high: float = 100.5,
    prior_vap_lvn_near_low: float = 99.5,
    overnight_high: float | None = 100.5,
    overnight_low: float | None = 99.5,
) -> pd.Series:
    values = {
            "timestamp": pd.Timestamp(timestamp),
            "session_date": pd.Timestamp(session_date),
            "session_label": "RTH",
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": large10_signed_volume,
            "large10_volume": large10_volume,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
            "prev_rth_high": prev_rth_high,
            "prev_rth_low": prev_rth_low,
            "footprint_max_buy_imbalance_volume": buy_imbalance_volume,
            "footprint_max_sell_imbalance_volume": sell_imbalance_volume,
            "prior_vap_session_yyyymmdd": 20240102,
            "prior_vap_poc": prior_vap_poc,
            "prior_vap_vah": prior_vap_vah,
            "prior_vap_val": prior_vap_val,
            "prior_vap_lvn_near_high": prior_vap_lvn_near_high,
            "prior_vap_lvn_near_low": prior_vap_lvn_near_low,
            "prior_vap_lvn_count": 2,
            "prior_vap_total_volume": 100000,
            "prior_vap_price_levels": 12,
        }
    if overnight_high is not None:
        values["overnight_high"] = overnight_high
    if overnight_low is not None:
        values["overnight_low"] = overnight_low
    return pd.Series(values)


def test_prior_high_true_vap_breakout_emits_long_next_bar() -> None:
    entry = TrueVapAoiBreakoutContinuationEntry(
        {
            "setup_mode": "prior_high_vap_breakout_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 2,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:45:00",
            "2024-01-03",
            open_=100.25,
            high=101.0,
            close=100.75,
            signed_volume=100.0,
            prev_rth_high=100.5,
            prior_vap_lvn_near_high=100.5,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:00")
    assert signal.report_fields["aoi_type"] == "prior_rth_high"
    assert signal.report_fields["profile_level_type"] in {"poc", "lvn_near_high"}


def test_true_vap_breakout_rejects_without_profile_confluence() -> None:
    entry = TrueVapAoiBreakoutContinuationEntry(
        {
            "setup_mode": "prior_high_vap_breakout_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 2,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:45:00",
            "2024-01-03",
            open_=100.25,
            high=101.0,
            close=100.75,
            signed_volume=100.0,
            prev_rth_high=100.5,
            prior_vap_poc=90.0,
            prior_vap_vah=91.0,
            prior_vap_val=89.0,
            prior_vap_lvn_near_high=90.5,
            prior_vap_lvn_near_low=89.5,
        )
    )

    assert signal is None


def test_opening_range_true_vap_breakout_waits_until_range_complete() -> None:
    entry = TrueVapAoiBreakoutContinuationEntry(
        {
            "setup_mode": "opening_range_vap_two_sided_breakout",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "opening_range_minutes": 3,
            "max_profile_distance_ticks": 2,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", "2024-01-03", high=100.25, close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", "2024-01-03", high=100.50, close=100.25)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:32:00", "2024-01-03", high=100.50, close=100.25)) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:33:00",
            "2024-01-03",
            open_=100.25,
            high=101.0,
            close=100.75,
            signed_volume=100.0,
            prior_vap_poc=100.5,
            prior_vap_lvn_near_high=100.5,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["aoi_type"] == "opening_range_high"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:34:00")


def test_overnight_high_true_vap_breakout_emits_long_next_bar() -> None:
    entry = TrueVapAoiBreakoutContinuationEntry(
        {
            "setup_mode": "overnight_high_vap_breakout_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 2,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:45:00",
            "2024-01-03",
            open_=100.25,
            high=101.0,
            close=100.75,
            signed_volume=100.0,
            overnight_high=100.5,
            prior_vap_lvn_near_high=100.5,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["aoi_type"] == "overnight_high"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:00")


def test_overnight_low_true_vap_breakdown_emits_short_next_bar() -> None:
    entry = TrueVapAoiBreakoutContinuationEntry(
        {
            "setup_mode": "overnight_low_vap_breakdown_short",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 2,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:45:00",
            "2024-01-03",
            open_=99.75,
            low=99.0,
            close=99.25,
            signed_volume=-100.0,
            overnight_low=99.5,
            prior_vap_lvn_near_low=99.5,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["aoi_type"] == "overnight_low"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:00")


def test_overnight_true_vap_breakout_rejects_when_completed_level_missing() -> None:
    entry = TrueVapAoiBreakoutContinuationEntry(
        {
            "setup_mode": "overnight_high_vap_breakout_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 2,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:45:00",
            "2024-01-03",
            open_=100.25,
            high=101.0,
            close=100.75,
            signed_volume=100.0,
            overnight_high=None,
        )
    )

    assert signal is None
