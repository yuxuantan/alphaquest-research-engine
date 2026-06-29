from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.video_exact_orderflow_playbook import (
    VideoExactOrderflowPlaybookEntry,
)
from propstack.strategy_modules.tp.signal_price import SignalPriceTarget


def _bar(
    timestamp: str,
    *,
    session_date: str = "2024-01-03",
    open_: float = 100.0,
    high: float = 100.5,
    low: float = 99.5,
    close: float = 100.25,
    volume: float = 1000.0,
    signed_volume: float = 0.0,
    prev_rth_high: float = 102.0,
    prev_rth_low: float = 100.0,
    overnight_high: float = 102.0,
    overnight_low: float = 99.0,
    absorption_long: float = 1.0,
    absorption_short: float = 1.0,
    sell_absorption_volume: float = 50.0,
    buy_absorption_volume: float = 50.0,
    sell_absorption_price: float = 99.75,
    buy_absorption_price: float = 100.75,
    large200_signed_volume: float = 0.0,
    large200_max_volume: float = 0.0,
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
        "overnight_high": overnight_high,
        "overnight_low": overnight_low,
        "footprint_absorption_long": absorption_long,
        "footprint_absorption_short": absorption_short,
        "footprint_max_sell_imbalance_volume": sell_absorption_volume,
        "footprint_max_buy_imbalance_volume": buy_absorption_volume,
        "footprint_highest_sell_imbalance_price": sell_absorption_price,
        "footprint_lowest_buy_imbalance_price": buy_absorption_price,
        "large200_record_volume": abs(large200_signed_volume),
        "large200_record_signed_volume": large200_signed_volume,
        "large200_record_buy_volume": max(0.0, large200_signed_volume),
        "large200_record_sell_volume": max(0.0, -large200_signed_volume),
        "large200_record_count": 1.0 if large200_max_volume else 0.0,
        "large200_record_max_volume": large200_max_volume,
        "developing_vap_session_yyyymmdd": 20240103,
        "developing_vap_poc": 101.0,
        "developing_vap_vah": 102.0,
        "developing_vap_val": 100.0,
        "developing_vap_lvn_near_close": 101.0,
        "developing_vap_lvn_near_high": 102.0,
        "developing_vap_lvn_near_low": 100.0,
        "developing_vap_lvn_count": 5,
        "developing_vap_total_volume": 125000.0,
        "developing_vap_price_levels": 40,
        "developing_vap_bars": 11,
    }
    values.update(extra)
    return pd.Series(values)


def _entry(params: dict) -> VideoExactOrderflowPlaybookEntry:
    defaults = {
        "profile_source": "cached_developing_vap",
        "cached_profile_prefix": "developing_vap",
        "start_time": "09:30:00",
        "end_time": "16:00:00",
        "bar_interval_minutes": 3,
        "opening_range_minutes": 1,
        "min_developing_profile_bars": 10,
        "min_aoi_confluences": 2,
        "min_absorption_volume": 20,
        "min_delta_activity_imbalance": 0.05,
        "aoi_reach_tolerance_ticks": 2,
        "market_aoi_max_distance_ticks": 4,
    }
    defaults.update(params)
    entry = VideoExactOrderflowPlaybookEntry(defaults)
    entry.current_session = pd.Timestamp("2024-01-03")
    return entry


def _install_structure(entry: VideoExactOrderflowPlaybookEntry, *, open_: float = 100.0) -> None:
    entry.current_session_bars = [
        _bar(
            str(pd.Timestamp("2024-01-03 09:30:00") + pd.Timedelta(minutes=index * 3)),
            open_=open_,
            high=open_ + 2.0,
            low=open_ - 1.0,
            close=open_ + 1.0,
            signed_volume=0.0,
            absorption_long=0.0,
            absorption_short=0.0,
        )
        for index in range(10)
    ]


def test_model1_range_short_requires_two_aoi_confluences_and_uses_next_bar_timestamp():
    entry = _entry(
        {
            "setup_mode": "model1_range_value_edge_short",
            "target_reference": "value_midpoint",
        }
    )
    _install_structure(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:03:00",
            open_=102.25,
            high=102.50,
            low=101.50,
            close=101.75,
            signed_volume=125.0,
            prev_rth_high=102.0,
            overnight_high=105.0,
            buy_absorption_price=102.25,
            large200_signed_volume=225.0,
            large200_max_volume=225.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:06:00")
    assert signal.report_fields["video_model"] == "model1_range"
    assert signal.report_fields["aoi_confluence_count"] >= 2
    assert "volume_profile" in signal.report_fields["aoi_confluence_criteria"]
    assert "big_trades" in signal.report_fields["aoi_confluence_criteria"]
    assert signal.report_fields["signal_target_price"] == 101.0


def test_model1_range_rejects_when_lvn_or_value_area_is_the_only_confluence():
    entry = _entry(
        {
            "setup_mode": "model1_range_value_edge_short",
            "target_reference": "value_midpoint",
        }
    )
    _install_structure(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:03:00",
            open_=102.25,
            high=102.50,
            low=101.50,
            close=101.75,
            signed_volume=0.0,
            prev_rth_high=110.0,
            overnight_high=111.0,
            buy_absorption_price=102.25,
            large200_signed_volume=0.0,
            large200_max_volume=0.0,
        )
    )

    assert signal is None


def test_video_exact_entry_defaults_to_one_signal_per_session():
    entry = _entry(
        {
            "setup_mode": "model1_range_value_edge_short",
            "target_reference": "value_midpoint",
        }
    )
    _install_structure(entry)

    first = entry.on_bar_close(
        _bar(
            "2024-01-03 10:03:00",
            open_=102.25,
            high=102.50,
            low=101.50,
            close=101.75,
            signed_volume=125.0,
            prev_rth_high=102.0,
            buy_absorption_price=102.25,
            large200_signed_volume=225.0,
            large200_max_volume=225.0,
        )
    )
    second = entry.on_bar_close(
        _bar(
            "2024-01-03 10:06:00",
            open_=102.25,
            high=102.50,
            low=101.50,
            close=101.75,
            signed_volume=125.0,
            prev_rth_high=102.0,
            buy_absorption_price=102.25,
            large200_signed_volume=225.0,
            large200_max_volume=225.0,
        )
    )

    assert first is not None
    assert second is None


def test_video_exact_entry_can_opt_into_multiple_session_signals():
    entry = _entry(
        {
            "setup_mode": "model1_range_value_edge_short",
            "target_reference": "value_midpoint",
            "max_trades_per_day": 2,
            "max_signals_per_session": 2,
        }
    )
    _install_structure(entry)

    first = entry.on_bar_close(
        _bar(
            "2024-01-03 10:03:00",
            open_=102.25,
            high=102.50,
            low=101.50,
            close=101.75,
            signed_volume=125.0,
            prev_rth_high=102.0,
            buy_absorption_price=102.25,
            large200_signed_volume=225.0,
            large200_max_volume=225.0,
        ),
        trades_today=0,
    )
    second = entry.on_bar_close(
        _bar(
            "2024-01-03 10:06:00",
            open_=102.25,
            high=102.50,
            low=101.50,
            close=101.75,
            signed_volume=125.0,
            prev_rth_high=102.0,
            buy_absorption_price=102.25,
            large200_signed_volume=225.0,
            large200_max_volume=225.0,
        ),
        trades_today=1,
    )

    assert first is not None
    assert second is not None
    assert entry.signals_by_session[pd.Timestamp("2024-01-03")] == 2


def test_model2_trend_lvn_long_uses_pullback_zone_and_structural_high_target():
    entry = _entry(
        {
            "setup_mode": "model2_trend_lvn_long",
            "target_reference": "structural_or_midpoint",
            "min_structure_bars": 10,
            "min_trend_move_ticks": 4,
            "min_directional_delta_imbalance": 0.05,
        }
    )
    _install_structure(entry, open_=100.0)
    entry.current_session_bars[-1]["high"] = 105.0

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:03:00",
            open_=103.25,
            high=104.25,
            low=102.75,
            close=104.0,
            signed_volume=90.0,
            prev_rth_high=103.0,
            overnight_high=103.0,
            sell_absorption_price=103.0,
            large200_signed_volume=250.0,
            large200_max_volume=250.0,
            developing_vap_vah=102.0,
            developing_vap_val=100.0,
            developing_vap_lvn_near_close=103.0,
            developing_vap_lvn_near_high=103.0,
            developing_vap_lvn_near_low=103.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["video_model"] == "model2_trend"
    assert signal.report_fields["profile_level_price"] == 103.0
    assert signal.report_fields["signal_target_price"] == 105.0
    assert "market_level" in signal.report_fields["aoi_confluence_criteria"]


def test_model2_trend_rejects_when_price_does_not_reach_lvn_zone():
    entry = _entry(
        {
            "setup_mode": "model2_trend_lvn_long",
            "min_structure_bars": 10,
            "min_trend_move_ticks": 4,
        }
    )
    _install_structure(entry, open_=100.0)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:03:00",
            open_=104.0,
            high=105.0,
            low=104.0,
            close=104.75,
            signed_volume=90.0,
            prev_rth_high=103.0,
            sell_absorption_price=104.0,
            large200_signed_volume=250.0,
            large200_max_volume=250.0,
            developing_vap_vah=102.0,
            developing_vap_val=100.0,
            developing_vap_lvn_near_close=103.0,
            developing_vap_lvn_near_high=103.0,
            developing_vap_lvn_near_low=103.0,
        )
    )

    assert signal is None


def test_signal_price_target_reads_signal_metadata_and_falls_back_to_fixed_r():
    target = SignalPriceTarget({"tick_size": 0.25, "fallback_target_r_multiple": 2.0})
    signal = type("Sig", (), {"metadata": {"signal_target_price": 105.1}})()

    assert target.price(100.0, 98.0, "long", signal=signal) == 105.25
    assert target.price(100.0, 98.0, "long", signal=type("Sig", (), {"metadata": {}})()) == 104.0


def test_signal_price_target_falls_back_when_signal_target_is_too_close():
    target = SignalPriceTarget(
        {
            "tick_size": 0.25,
            "fallback_target_r_multiple": 3.0,
            "min_signal_target_r_multiple": 1.5,
        }
    )
    close_signal = type("Sig", (), {"metadata": {"signal_target_price": 101.0}})()
    far_signal = type("Sig", (), {"metadata": {"signal_target_price": 103.0}})()

    assert target.price(100.0, 98.0, "long", signal=close_signal) == 106.0
    assert target.price(100.0, 98.0, "long", signal=far_signal) == 103.0
