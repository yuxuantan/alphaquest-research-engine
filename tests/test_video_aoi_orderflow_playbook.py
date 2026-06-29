from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.video_aoi_orderflow_playbook import (
    VideoAoiOrderflowPlaybookEntry,
)


def _bar(
    timestamp: str,
    *,
    session_date: str = "2024-01-03",
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
    **extra,
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
    values.update(extra)
    return pd.Series(values)


def _install_profile_state(
    entry: VideoAoiOrderflowPlaybookEntry,
    opening_bars: int = 0,
    interval_minutes: int = 1,
) -> None:
    entry.current_session = pd.Timestamp("2024-01-03")
    entry.prior_profile = {
        "session_date": pd.Timestamp("2024-01-02"),
        "poc": 101.0,
        "vah": 102.0,
        "val": 100.0,
        "total_volume": 100000.0,
        "bar_count": 390,
        "levels": [
            {"type": "poc", "price": 101.0},
            {"type": "vah", "price": 102.0},
            {"type": "val", "price": 100.0},
            {"type": "lvn", "price": 99.0},
            {"type": "lvn", "price": 103.0},
        ],
    }
    entry.current_session_bars = [
        _bar(
            str(pd.Timestamp("2024-01-03 09:30:00") + pd.Timedelta(minutes=minute * interval_minutes)),
            open_=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            signed_volume=0.0,
        )
        for minute in range(opening_bars)
    ]


def test_range_val_seller_trap_uses_next_bar_timestamp_and_market_aoi_confluence():
    entry = VideoAoiOrderflowPlaybookEntry(
        {
            "setup_mode": "range_val_seller_trap_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_adverse_delta_imbalance": 0.05,
        }
    )
    _install_profile_state(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            open_=99.75,
            high=100.5,
            low=99.5,
            close=100.25,
            signed_volume=-100.0,
            prev_rth_low=100.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:02:00")
    assert signal.report_fields["video_model"] == "range"
    assert signal.report_fields["market_aoi_type"] == "prior_rth_low"


def test_range_value_edge_rejects_without_market_aoi_confluence():
    entry = VideoAoiOrderflowPlaybookEntry(
        {
            "setup_mode": "range_val_seller_trap_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "max_profile_distance_ticks": 2,
            "min_absorption_volume": 20,
        }
    )
    _install_profile_state(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            open_=99.75,
            high=100.5,
            low=99.5,
            close=100.25,
            prev_rth_low=97.0,
        )
    )

    assert signal is None


def test_trend_lvn_seller_trap_waits_for_completed_opening_range():
    base_params = {
        "setup_mode": "trend_lvn_seller_trap_long",
        "start_time": "09:30:00",
        "end_time": "16:00:00",
        "opening_range_minutes": 30,
        "max_profile_distance_ticks": 4,
        "min_absorption_volume": 20,
        "min_trend_move_ticks": 4,
        "require_market_aoi_confluence": False,
    }
    early = VideoAoiOrderflowPlaybookEntry(base_params)
    _install_profile_state(early, opening_bars=29)
    assert (
        early.on_bar_close(
            _bar("2024-01-03 10:00:00", open_=102.75, high=103.5, low=102.75, close=103.25)
        )
        is None
    )

    entry = VideoAoiOrderflowPlaybookEntry(base_params)
    _install_profile_state(entry, opening_bars=30)
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:05:00",
            open_=102.75,
            high=103.5,
            low=102.75,
            close=103.25,
            signed_volume=-150.0,
            sell_absorption_price=102.75,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["video_model"] == "trend"
    assert signal.report_fields["profile_level_type"] == "prior_low_volume_node"


def test_trend_lvn_opening_range_uses_minutes_on_three_minute_bars():
    entry = VideoAoiOrderflowPlaybookEntry(
        {
            "setup_mode": "trend_lvn_seller_trap_long",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 3,
            "opening_range_minutes": 30,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_trend_move_ticks": 4,
            "require_market_aoi_confluence": False,
        }
    )
    _install_profile_state(entry, opening_bars=10, interval_minutes=3)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=102.75,
            high=103.5,
            low=102.75,
            close=103.25,
            signed_volume=-150.0,
            sell_absorption_price=102.75,
        )
    )

    assert signal is not None
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:03:00")


def test_trend_lvn_can_use_developing_session_profile_on_three_minute_bars():
    entry = VideoAoiOrderflowPlaybookEntry(
        {
            "setup_mode": "trend_lvn_seller_trap_long",
            "profile_source": "developing_session_ohlcv",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 3,
            "opening_range_minutes": 30,
            "min_prior_profile_bars": 120,
            "min_developing_profile_bars": 11,
            "max_profile_distance_ticks": 8,
            "min_absorption_volume": 20,
            "min_trend_move_ticks": 4,
            "require_market_aoi_confluence": False,
        }
    )

    for index in range(10):
        opening_bar = _bar(
            str(pd.Timestamp("2024-01-03 09:30:00") + pd.Timedelta(minutes=index * 3)),
            open_=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            signed_volume=0.0,
            absorption_long=0.0,
            sell_absorption_volume=0.0,
        )
        assert entry.on_bar_close(opening_bar) is None

    assert entry.prior_profile is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=102.75,
            high=103.5,
            low=102.75,
            close=103.25,
            signed_volume=-150.0,
            sell_absorption_price=102.75,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:03:00")
    assert signal.report_fields["profile_source"] == "developing_session_ohlcv"
    assert signal.report_fields["profile_level_type"] == "developing_low_volume_node"
    assert signal.report_fields["profile_bars"] == 11
    assert signal.report_fields["profile_session"] == pd.Timestamp("2024-01-03")


def test_trend_lvn_can_use_cached_sierra_developing_vap_on_three_minute_bars():
    entry = VideoAoiOrderflowPlaybookEntry(
        {
            "setup_mode": "trend_lvn_seller_trap_long",
            "profile_source": "cached_developing_vap",
            "cached_profile_prefix": "developing_vap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 3,
            "opening_range_minutes": 30,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_trend_move_ticks": 4,
            "require_market_aoi_confluence": False,
        }
    )
    entry.current_session = pd.Timestamp("2024-01-03")
    entry.current_session_bars = [
        _bar(
            str(pd.Timestamp("2024-01-03 09:30:00") + pd.Timedelta(minutes=index * 3)),
            open_=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            signed_volume=0.0,
        )
        for index in range(10)
    ]

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=102.75,
            high=103.5,
            low=102.75,
            close=103.25,
            signed_volume=-150.0,
            sell_absorption_price=102.75,
            developing_vap_session_yyyymmdd=20240103,
            developing_vap_poc=101.0,
            developing_vap_vah=102.0,
            developing_vap_val=100.0,
            developing_vap_lvn_near_close=103.0,
            developing_vap_lvn_near_high=103.0,
            developing_vap_lvn_near_low=99.0,
            developing_vap_lvn_count=6,
            developing_vap_total_volume=125000,
            developing_vap_price_levels=40,
            developing_vap_bars=11,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["profile_source"] == "cached_developing_vap"
    assert signal.report_fields["profile_level_type"] == "developing_low_volume_node"
    assert signal.report_fields["profile_session"] == 20240103
    assert signal.report_fields["profile_bars"] == 11


def test_trend_lvn_seller_trap_can_require_directional_delta_shift():
    params = {
        "setup_mode": "trend_lvn_seller_trap_long",
        "start_time": "09:30:00",
        "end_time": "16:00:00",
        "opening_range_minutes": 30,
        "max_profile_distance_ticks": 4,
        "min_absorption_volume": 20,
        "min_trend_move_ticks": 4,
        "min_directional_delta_imbalance": 0.05,
        "require_market_aoi_confluence": False,
    }
    rejected = VideoAoiOrderflowPlaybookEntry(params)
    _install_profile_state(rejected, opening_bars=30)

    assert rejected.on_bar_close(
        _bar(
            "2024-01-03 10:05:00",
            open_=102.75,
            high=103.5,
            low=102.75,
            close=103.25,
            signed_volume=-150.0,
            sell_absorption_price=102.75,
        )
    ) is None

    accepted = VideoAoiOrderflowPlaybookEntry(params)
    _install_profile_state(accepted, opening_bars=30)
    signal = accepted.on_bar_close(
        _bar(
            "2024-01-03 10:05:00",
            open_=102.75,
            high=103.5,
            low=102.75,
            close=103.25,
            signed_volume=80.0,
            sell_absorption_price=102.75,
        )
    )

    assert signal is not None
    assert signal.report_fields["min_directional_delta_imbalance"] == 0.05


def test_trend_lvn_buyer_trap_can_emit_short_continuation():
    entry = VideoAoiOrderflowPlaybookEntry(
        {
            "setup_mode": "trend_lvn_buyer_trap_short",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "opening_range_minutes": 30,
            "max_profile_distance_ticks": 4,
            "min_absorption_volume": 20,
            "min_trend_move_ticks": 4,
            "require_market_aoi_confluence": False,
        }
    )
    _install_profile_state(entry, opening_bars=30)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:05:00",
            open_=99.25,
            high=99.25,
            low=98.5,
            close=98.75,
            signed_volume=150.0,
            absorption_long=0.0,
            absorption_short=1.0,
            sell_absorption_volume=0.0,
            buy_absorption_volume=50.0,
            buy_absorption_price=99.25,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["video_model"] == "trend"
