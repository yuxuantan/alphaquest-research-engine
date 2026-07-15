from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.nq_nonconfirming_vap_aoi_trap import (
    NqNonconfirmingVapAoiTrapEntry,
)


def _params(**overrides):
    params = {
        "setup_mode": "prior_low_profile_seller_trap_long",
        "profile_source": "cached_prior_vap",
        "cached_profile_prefix": "prior_vap",
        "start_time": "09:45:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "max_profile_distance_ticks": 4,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_absorption_volume": 50,
        "min_adverse_delta_imbalance": 0.02,
        "relative_value_window_minutes": 30,
        "min_nq_es_return_gap_bps": 2.0,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _bar(**overrides):
    values = {
        "timestamp": pd.Timestamp("2024-01-03 10:00:00"),
        "session_date": "2024-01-03",
        "is_rth": True,
        "open": 99.75,
        "high": 100.50,
        "low": 99.50,
        "close": 100.25,
        "volume": 1000,
        "signed_volume": -80,
        "footprint_absorption_long": 1,
        "footprint_absorption_short": 0,
        "footprint_max_sell_imbalance_volume": 75,
        "footprint_max_buy_imbalance_volume": 20,
        "footprint_highest_sell_imbalance_price": 99.75,
        "footprint_lowest_buy_imbalance_price": 100.50,
        "prev_rth_low": 100.0,
        "prev_rth_high": 101.0,
        "prior_vap_session_yyyymmdd": 20240102,
        "prior_vap_poc": 100.50,
        "prior_vap_vah": 101.0,
        "prior_vap_val": 100.0,
        "prior_vap_lvn_near_high": 101.0,
        "prior_vap_lvn_near_low": 100.0,
        "prior_vap_total_volume": 100000,
        "prior_vap_price_levels": 50,
        "es_return_bps_30": -4.0,
        "nq_return_bps_30": 1.0,
        "nq_minus_es_return_bps_30": 5.0,
        "nq_minus_es_signed_imbalance_30": 0.10,
    }
    values.update(overrides)
    return pd.Series(values)


def test_long_trap_requires_nq_underconfirmation_and_uses_next_bar_timestamp():
    entry = NqNonconfirmingVapAoiTrapEntry(_params())

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:01:00")
    assert signal.report_fields["nq_minus_es_return_bps"] == 5.0
    assert signal.level_type.startswith("nq_nonconfirming_")


def test_long_trap_blocks_when_nq_confirms_es_weakness():
    entry = NqNonconfirmingVapAoiTrapEntry(_params())

    signal = entry.on_bar_close(_bar(nq_minus_es_return_bps_30=-1.0))

    assert signal is None


def test_short_trap_requires_negative_nq_minus_es_spread():
    entry = NqNonconfirmingVapAoiTrapEntry(
        _params(setup_mode="prior_high_profile_buyer_trap_short")
    )
    short_bar = _bar(
        open=101.25,
        high=101.50,
        low=99.75,
        close=100.75,
        signed_volume=90,
        footprint_absorption_long=0,
        footprint_absorption_short=1,
        footprint_max_buy_imbalance_volume=80,
        footprint_lowest_buy_imbalance_price=101.25,
        nq_minus_es_return_bps_30=-4.0,
        nq_minus_es_signed_imbalance_30=-0.07,
    )

    signal = entry.on_bar_close(short_bar)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["nq_minus_es_return_bps"] == -4.0


def test_required_nq_flow_nonconfirmation_blocks_misaligned_flow():
    entry = NqNonconfirmingVapAoiTrapEntry(
        _params(require_nq_flow_nonconfirmation=True, min_nq_es_flow_gap=0.05)
    )

    signal = entry.on_bar_close(_bar(nq_minus_es_signed_imbalance_30=0.01))

    assert signal is None


def test_beyond_poc_context_can_use_delta_reclaim_without_footprint_absorption():
    entry = NqNonconfirmingVapAoiTrapEntry(
        _params(
            profile_context_mode="beyond_poc",
            require_footprint_absorption=False,
            min_adverse_delta_imbalance=0.02,
        )
    )

    signal = entry.on_bar_close(
        _bar(
            footprint_absorption_long=0,
            footprint_max_sell_imbalance_volume=0,
            prior_vap_poc=100.50,
            prior_vap_val=99.50,
        )
    )

    assert signal is not None
    assert signal.report_fields["profile_level_type"] == "beyond_poc"


def test_invalid_relative_value_window_fails_fast():
    with pytest.raises(ValueError, match="relative_value_window_minutes"):
        NqNonconfirmingVapAoiTrapEntry(_params(relative_value_window_minutes=10))


def test_factory_registration_builds_entry_module():
    entry = build_entry_module({"module": "nq_nonconfirming_vap_aoi_trap", "params": _params()})

    assert isinstance(entry, NqNonconfirmingVapAoiTrapEntry)


def test_all_market_mode_accepts_overnight_aoi():
    entry = NqNonconfirmingVapAoiTrapEntry(
        _params(
            setup_mode="all_market_profile_two_sided_trap",
            profile_context_mode="beyond_poc",
            require_footprint_absorption=False,
        )
    )

    signal = entry.on_bar_close(
        _bar(
            prev_rth_low=90.0,
            prev_rth_high=110.0,
            overnight_low=100.0,
            overnight_high=110.0,
            prior_vap_poc=100.50,
        )
    )

    assert signal is not None
    assert signal.report_fields["aoi_type"] == "overnight_low"
