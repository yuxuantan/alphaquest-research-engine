from __future__ import annotations

import pandas as pd
import pytest

from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.nq_confirming_vap_aoi_breakout import (
    NqConfirmingVapAoiBreakoutEntry,
)


def _params(**overrides):
    params = {
        "setup_mode": "prior_high_vap_breakout_long",
        "start_time": "09:30:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "opening_range_minutes": 3,
        "max_profile_distance_ticks": 2,
        "min_breakout_ticks": 1,
        "close_buffer_ticks": 0,
        "flow_mode": "signed_volume",
        "min_orderflow_imbalance": 0.05,
        "min_footprint_imbalance_volume": 20,
        "relative_value_window_minutes": 30,
        "min_nq_return_bps": 0.5,
        "min_nq_signed_imbalance": 0.01,
        "max_nq_lag_bps": 5.0,
        "require_nq_flow_confirmation": True,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _bar(**overrides):
    values = {
        "timestamp": pd.Timestamp("2024-01-03 10:00:00"),
        "session_date": pd.Timestamp("2024-01-03"),
        "session_label": "RTH",
        "is_rth": True,
        "open": 100.25,
        "high": 101.00,
        "low": 99.75,
        "close": 100.75,
        "volume": 1000,
        "signed_volume": 100,
        "large10_signed_volume": 100,
        "large10_volume": 500,
        "large20_signed_volume": 100,
        "large20_volume": 400,
        "footprint_max_buy_imbalance_volume": 40,
        "footprint_max_sell_imbalance_volume": 40,
        "prev_rth_high": 100.50,
        "prev_rth_low": 99.50,
        "overnight_high": 100.50,
        "overnight_low": 99.50,
        "prior_vap_session_yyyymmdd": 20240102,
        "prior_vap_poc": 100.50,
        "prior_vap_vah": 100.50,
        "prior_vap_val": 99.50,
        "prior_vap_lvn_near_high": 100.50,
        "prior_vap_lvn_near_low": 99.50,
        "prior_vap_total_volume": 100000,
        "prior_vap_price_levels": 50,
        "es_return_bps_30": 3.0,
        "nq_return_bps_30": 2.0,
        "nq_minus_es_return_bps_30": -1.0,
        "nq_signed_imbalance_30": 0.05,
    }
    values.update(overrides)
    return pd.Series(values)


def test_long_breakout_requires_nq_confirmation_and_uses_next_bar_timestamp():
    entry = NqConfirmingVapAoiBreakoutEntry(_params())

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:01:00")
    assert signal.level_type.startswith("nq_confirming_")
    assert signal.report_fields["nq_return_bps"] == 2.0
    assert signal.report_fields["nq_signed_imbalance"] == 0.05


def test_long_breakout_blocks_when_nq_return_does_not_confirm():
    entry = NqConfirmingVapAoiBreakoutEntry(_params())

    signal = entry.on_bar_close(_bar(nq_return_bps_30=-0.25))

    assert signal is None


def test_long_breakout_blocks_when_required_nq_flow_is_missing():
    entry = NqConfirmingVapAoiBreakoutEntry(_params())
    bar = _bar()
    bar = bar.drop(labels=["nq_signed_imbalance_30"])

    signal = entry.on_bar_close(bar)

    assert signal is None


def test_short_value_area_breakout_requires_negative_nq_confirmation():
    entry = NqConfirmingVapAoiBreakoutEntry(
        _params(setup_mode="value_area_vap_two_sided_breakout")
    )

    signal = entry.on_bar_close(
        _bar(
            open=99.75,
            high=100.25,
            low=99.0,
            close=99.25,
            signed_volume=-100,
            prev_rth_high=101.0,
            prior_vap_poc=99.50,
            prior_vap_vah=100.50,
            prior_vap_val=99.50,
            prior_vap_lvn_near_high=100.50,
            prior_vap_lvn_near_low=99.50,
            es_return_bps_30=-3.0,
            nq_return_bps_30=-2.0,
            nq_minus_es_return_bps_30=1.0,
            nq_signed_imbalance_30=-0.06,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["aoi_type"] == "prior_vap_val"


def test_opening_range_in_all_market_mode_waits_until_complete():
    entry = NqConfirmingVapAoiBreakoutEntry(
        _params(
            setup_mode="all_market_vap_two_sided_breakout",
            max_profile_distance_ticks=4,
        )
    )

    assert entry.on_bar_close(_bar(timestamp=pd.Timestamp("2024-01-03 09:30:00"), high=100.00, close=99.75)) is None
    assert entry.on_bar_close(_bar(timestamp=pd.Timestamp("2024-01-03 09:31:00"), high=100.25, close=100.00)) is None
    assert entry.on_bar_close(_bar(timestamp=pd.Timestamp("2024-01-03 09:32:00"), high=100.50, close=100.25)) is None

    signal = entry.on_bar_close(
        _bar(
            timestamp=pd.Timestamp("2024-01-03 09:33:00"),
            prev_rth_high=110.0,
            prev_rth_low=90.0,
            overnight_high=110.0,
            overnight_low=90.0,
            high=101.0,
            close=100.75,
            prior_vap_poc=100.50,
            prior_vap_vah=100.50,
            prior_vap_lvn_near_high=100.50,
        )
    )

    assert signal is not None
    assert signal.report_fields["aoi_type"] == "opening_range_high"


def test_invalid_relative_value_window_fails_fast():
    with pytest.raises(ValueError, match="relative_value_window_minutes"):
        NqConfirmingVapAoiBreakoutEntry(_params(relative_value_window_minutes=10))


def test_factory_registration_builds_entry_module():
    entry = build_entry_module({"module": "nq_confirming_vap_aoi_breakout", "params": _params()})

    assert isinstance(entry, NqConfirmingVapAoiBreakoutEntry)
