from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.profile_aoi_footprint_trap import (
    ProfileAoiFootprintTrapEntry,
)


def _bar(
    timestamp: str,
    session_date: str,
    *,
    open_: float = 100.0,
    high: float = 100.5,
    low: float = 99.5,
    close: float = 100.25,
    volume: float = 1000.0,
    signed_volume: float = -100.0,
    prev_rth_high: float = 101.0,
    prev_rth_low: float = 100.0,
    absorption_long: float = 1.0,
    absorption_short: float = 0.0,
    sell_absorption_volume: float = 50.0,
    buy_absorption_volume: float = 0.0,
    sell_absorption_price: float = 99.75,
    buy_absorption_price: float = 100.75,
    overnight_high: float | None = 101.0,
    overnight_low: float | None = 100.0,
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
            "prev_rth_high": prev_rth_high,
            "prev_rth_low": prev_rth_low,
            "footprint_absorption_long": absorption_long,
            "footprint_absorption_short": absorption_short,
            "footprint_max_sell_imbalance_volume": sell_absorption_volume,
            "footprint_max_buy_imbalance_volume": buy_absorption_volume,
            "footprint_highest_sell_imbalance_price": sell_absorption_price,
            "footprint_lowest_buy_imbalance_price": buy_absorption_price,
        }
    if overnight_high is not None:
        values["overnight_high"] = overnight_high
    if overnight_low is not None:
        values["overnight_low"] = overnight_low
    return pd.Series(values)


def _seed_prior_profile(entry: ProfileAoiFootprintTrapEntry) -> None:
    for minute in range(3):
        entry.on_bar_close(
            _bar(
                f"2024-01-02 09:3{minute}:00",
                "2024-01-02",
                open_=100.0,
                high=100.25,
                low=99.75,
                close=100.0,
                signed_volume=0.0,
            )
        )
    entry.on_bar_close(
        _bar(
            "2024-01-03 09:30:00",
            "2024-01-03",
            open_=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            signed_volume=0.0,
        )
    )


def _with_cached_vap(bar: pd.Series, *, poc: float = 100.0, vah: float = 101.0, val: float = 99.0) -> pd.Series:
    bar["prior_vap_session_yyyymmdd"] = 20240102
    bar["prior_vap_poc"] = poc
    bar["prior_vap_vah"] = vah
    bar["prior_vap_val"] = val
    bar["prior_vap_lvn_near_high"] = vah
    bar["prior_vap_lvn_near_low"] = poc
    bar["prior_vap_lvn_count"] = 2
    bar["prior_vap_total_volume"] = 100000
    bar["prior_vap_price_levels"] = 9
    return bar


def test_prior_low_profile_seller_trap_uses_completed_bar_and_next_bar_timestamp():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "prior_low_profile_seller_trap_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "min_prior_profile_bars": 3,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_adverse_delta_imbalance": 0.05,
        }
    )
    _seed_prior_profile(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:31:00",
            "2024-01-03",
            open_=99.75,
            high=100.5,
            low=99.5,
            close=100.25,
            volume=1000.0,
            signed_volume=-100.0,
            prev_rth_low=100.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:32:00")
    assert signal.report_fields["aoi_type"] == "prior_rth_low"
    assert signal.report_fields["profile_distance_ticks"] <= 4


def test_cached_prior_vap_profile_can_emit_without_seeded_profile():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "prior_low_profile_seller_trap_long",
            "profile_source": "cached_prior_vap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_adverse_delta_imbalance": 0.05,
        }
    )

    bar = _bar(
        "2024-01-03 09:31:00",
        "2024-01-03",
        open_=99.75,
        high=100.5,
        low=99.5,
        close=100.25,
        volume=1000.0,
        signed_volume=-100.0,
        prev_rth_low=100.0,
    )
    _with_cached_vap(bar)

    signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["prior_profile_session"] == 20240102
    assert signal.report_fields["profile_level_type"] in {"poc", "lvn_near_low"}
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:32:00")


def test_cached_prior_vap_profile_rejects_when_columns_missing():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "prior_low_profile_seller_trap_long",
            "profile_source": "cached_prior_vap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:31:00",
            "2024-01-03",
            open_=99.75,
            high=100.5,
            low=99.5,
            close=100.25,
            prev_rth_low=100.0,
        )
    )

    assert signal is None


def test_profile_confluence_rejects_far_profile_levels():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "prior_low_profile_seller_trap_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "min_prior_profile_bars": 3,
            "max_profile_distance_ticks": 1,
            "min_absorption_volume": 20,
        }
    )
    _seed_prior_profile(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:31:00",
            "2024-01-03",
            open_=97.75,
            high=98.5,
            low=97.5,
            close=98.25,
            prev_rth_low=98.0,
        )
    )

    assert signal is None


def test_prior_two_sided_mode_can_emit_short_trap():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "prior_profile_two_sided_trap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "min_prior_profile_bars": 3,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
        }
    )
    _seed_prior_profile(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:31:00",
            "2024-01-03",
            open_=100.25,
            high=100.5,
            low=99.5,
            close=99.75,
            signed_volume=100.0,
            prev_rth_high=100.0,
            absorption_long=0.0,
            absorption_short=1.0,
            sell_absorption_volume=0.0,
            buy_absorption_volume=50.0,
            buy_absorption_price=100.25,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["aoi_type"] == "prior_rth_high"


def test_opening_range_trap_waits_until_range_is_complete():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "opening_low_profile_seller_trap_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "opening_range_minutes": 30,
            "min_prior_profile_bars": 3,
            "max_profile_distance_ticks": 8,
            "min_absorption_volume": 20,
        }
    )
    _seed_prior_profile(entry)

    for minute in range(1, 30):
        signal = entry.on_bar_close(
            _bar(
                f"2024-01-03 09:{30 + minute:02d}:00",
                "2024-01-03",
                open_=100.0,
                high=100.25,
                low=99.75,
                close=100.0,
                signed_volume=0.0,
            )
        )
    assert signal is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            "2024-01-03",
            open_=99.75,
            high=100.25,
            low=99.25,
            close=100.10,
            signed_volume=-80.0,
        )
    )

    assert signal is not None
    assert signal.report_fields["aoi_type"] == "opening_range_low"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:01:00")


def test_market_profile_two_sided_trap_can_use_opening_aoi_with_cached_vap():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "market_profile_two_sided_trap",
            "profile_source": "cached_prior_vap",
            "start_time": "10:00:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "opening_range_minutes": 30,
            "max_profile_distance_ticks": 8,
            "min_absorption_volume": 20,
            "min_adverse_delta_imbalance": 0.03,
        }
    )

    for minute in range(30):
        entry.on_bar_close(
            _with_cached_vap(
                _bar(
                    f"2024-01-03 09:{30 + minute:02d}:00",
                    "2024-01-03",
                    open_=100.0,
                    high=100.25,
                    low=100.0,
                    close=100.10,
                    signed_volume=0.0,
                    prev_rth_high=150.0,
                    prev_rth_low=50.0,
                )
            )
        )

    signal = entry.on_bar_close(
        _with_cached_vap(
            _bar(
                "2024-01-03 10:00:00",
                "2024-01-03",
                open_=99.75,
                high=100.25,
                low=99.50,
                close=100.10,
                signed_volume=-80.0,
                prev_rth_high=150.0,
                prev_rth_low=50.0,
            )
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["setup_mode"] == "market_profile_two_sided_trap"
    assert signal.report_fields["aoi_type"] == "opening_range_low"


def test_overnight_profile_trap_can_use_completed_overnight_low_with_cached_vap():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "overnight_low_profile_seller_trap_long",
            "profile_source": "cached_prior_vap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_adverse_delta_imbalance": 0.05,
        }
    )

    signal = entry.on_bar_close(
        _with_cached_vap(
            _bar(
                "2024-01-03 09:45:00",
                "2024-01-03",
                open_=99.75,
                high=100.50,
                low=99.50,
                close=100.25,
                volume=1000.0,
                signed_volume=-100.0,
                overnight_low=100.0,
            )
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["aoi_type"] == "overnight_low"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:00")


def test_overnight_profile_trap_can_use_completed_overnight_high_with_cached_vap():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "overnight_high_profile_buyer_trap_short",
            "profile_source": "cached_prior_vap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_adverse_delta_imbalance": 0.05,
        }
    )

    signal = entry.on_bar_close(
        _with_cached_vap(
            _bar(
                "2024-01-03 09:45:00",
                "2024-01-03",
                open_=100.25,
                high=100.50,
                low=99.50,
                close=99.75,
                volume=1000.0,
                signed_volume=100.0,
                overnight_high=100.0,
                absorption_long=0.0,
                absorption_short=1.0,
                sell_absorption_volume=0.0,
                buy_absorption_volume=50.0,
                buy_absorption_price=100.25,
            )
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["aoi_type"] == "overnight_high"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:00")


def test_overnight_profile_trap_rejects_when_completed_overnight_level_missing():
    entry = ProfileAoiFootprintTrapEntry(
        {
            "setup_mode": "overnight_low_profile_seller_trap_long",
            "profile_source": "cached_prior_vap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _with_cached_vap(
            _bar(
                "2024-01-03 09:45:00",
                "2024-01-03",
                open_=99.75,
                high=100.50,
                low=99.50,
                close=100.25,
                overnight_low=None,
            )
        )
    )

    assert signal is None
