import pandas as pd
import pytest

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.aoi_vap_acceptance_retest import AoiVapAcceptanceRetestEntry


def _bar(ts: str, **overrides):
    row = {
        "timestamp": pd.Timestamp(ts, tz="America/New_York"),
        "session_date": "2024-01-03",
        "is_rth": True,
        "open": 100.0,
        "high": 100.5,
        "low": 99.75,
        "close": 100.25,
        "volume": 1000,
        "signed_volume": 0,
        "large10_signed_volume": 0,
        "large10_volume": 0,
        "large20_signed_volume": 0,
        "large20_volume": 0,
        "footprint_max_buy_imbalance_volume": 0,
        "footprint_max_sell_imbalance_volume": 0,
        "prev_rth_high": 101.0,
        "prev_rth_low": 99.0,
        "overnight_high": 101.25,
        "overnight_low": 98.75,
        "prior_vap_session_yyyymmdd": 20240102,
        "prior_vap_poc": 101.0,
        "prior_vap_vah": 102.0,
        "prior_vap_val": 99.0,
        "prior_vap_lvn_near_high": 101.25,
        "prior_vap_lvn_near_low": 98.75,
        "prior_vap_lvn_count": 8,
        "prior_vap_total_volume": 500000,
        "prior_vap_price_levels": 80,
    }
    row.update(overrides)
    return pd.Series(row)


def _entry(**params):
    base = {
        "setup_mode": "prior_high_acceptance_long",
        "start_time": "09:30:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "max_profile_distance_ticks": 4,
        "min_breakout_ticks": 1,
        "retest_tolerance_ticks": 4,
        "acceptance_buffer_ticks": 1,
        "min_retest_delay_bars": 1,
        "max_retest_bars": 5,
        "max_chase_ticks": 20,
        "min_orderflow_imbalance": 0.2,
        "min_footprint_imbalance_volume": 50,
        "max_trades_per_day": 1,
    }
    base.update(params)
    return AoiVapAcceptanceRetestEntry(base)


def test_aoi_vap_acceptance_retest_enters_only_after_later_completed_retest_bar():
    entry = _entry()

    breakout = _bar(
        "2024-01-03 09:30",
        open=100.75,
        high=101.5,
        low=100.5,
        close=101.25,
        signed_volume=350,
        footprint_max_buy_imbalance_volume=90,
    )
    retest = _bar(
        "2024-01-03 09:31",
        open=101.1,
        high=101.75,
        low=101.0,
        close=101.5,
        signed_volume=300,
        footprint_max_buy_imbalance_volume=80,
        prior_vap_poc=110.0,
        prior_vap_vah=111.0,
        prior_vap_val=108.0,
        prior_vap_lvn_near_high=109.5,
        prior_vap_lvn_near_low=108.5,
    )

    assert entry.on_bar_close(breakout) is None

    signal = entry.on_bar_close(retest)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.breakout_level == pytest.approx(101.0)
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:32", tz="America/New_York")
    assert signal.metadata["breakout_timestamp"] == breakout["timestamp"]
    assert signal.metadata["aoi_type"] == "prior_rth_high"
    assert signal.metadata["profile_level_type"] == "poc"


def test_aoi_vap_acceptance_retest_requires_profile_confluence_before_arming_state():
    entry = _entry(max_profile_distance_ticks=2)
    breakout = _bar(
        "2024-01-03 09:30",
        open=100.75,
        high=101.5,
        low=100.5,
        close=101.25,
        signed_volume=350,
        footprint_max_buy_imbalance_volume=90,
        prior_vap_poc=110.0,
        prior_vap_vah=111.0,
        prior_vap_val=108.0,
        prior_vap_lvn_near_high=109.5,
        prior_vap_lvn_near_low=108.5,
    )
    retest = _bar(
        "2024-01-03 09:31",
        open=101.1,
        high=101.75,
        low=101.0,
        close=101.5,
        signed_volume=300,
        footprint_max_buy_imbalance_volume=80,
        prior_vap_poc=110.0,
        prior_vap_vah=111.0,
        prior_vap_val=108.0,
        prior_vap_lvn_near_high=109.5,
        prior_vap_lvn_near_low=108.5,
    )

    assert entry.on_bar_close(breakout) is None
    assert entry.on_bar_close(retest) is None
    assert entry.session_states == {}


def test_aoi_vap_acceptance_retest_short_uses_same_direction_flow_and_next_bar_timestamp():
    entry = _entry(setup_mode="prior_low_acceptance_short")
    breakout = _bar(
        "2024-01-03 09:30",
        open=99.25,
        high=99.5,
        low=98.5,
        close=98.75,
        signed_volume=-350,
        footprint_max_sell_imbalance_volume=90,
    )
    retest = _bar(
        "2024-01-03 09:31",
        open=98.9,
        high=99.0,
        low=98.25,
        close=98.5,
        signed_volume=-300,
        footprint_max_sell_imbalance_volume=80,
    )

    assert entry.on_bar_close(breakout) is None
    signal = entry.on_bar_close(retest)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.breakout_level == pytest.approx(99.0)
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:32", tz="America/New_York")
    assert signal.metadata["profile_level_type"] == "val"


def test_aoi_vap_acceptance_retest_registers_with_entry_factory():
    built = build_entry_module({"module": "aoi_vap_acceptance_retest", "params": {}})

    assert isinstance(built, AoiVapAcceptanceRetestEntry)
