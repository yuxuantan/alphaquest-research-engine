from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.large_record_delayed_aoi_confirmation import (
    LargeRecordDelayedAoiConfirmationEntry,
)


def _params(**overrides):
    params = {
        "setup_mode": "market_aoi_delayed_trap",
        "profile_context_mode": "beyond_poc",
        "cached_profile_prefix": "prior_vap",
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "opening_range_minutes": 30,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_large200_record_volume": 200,
        "min_confirm_delta_imbalance": 0.02,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _bar(timestamp: str, **overrides):
    values = {
        "timestamp": pd.Timestamp(timestamp),
        "session_date": "2024-01-03",
        "is_rth": True,
        "open": 100.25,
        "high": 100.50,
        "low": 99.50,
        "close": 99.75,
        "volume": 1000,
        "signed_volume": -100,
        "prev_rth_low": 100.0,
        "prev_rth_high": 102.0,
        "prior_vap_poc": 101.0,
        "prior_vap_vah": 102.0,
        "prior_vap_val": 100.0,
        "prior_vap_session_yyyymmdd": 20240102,
        "prior_vap_total_volume": 100000,
        "prior_vap_price_levels": 80,
        "large200_record_max_volume": 225,
        "large200_record_volume": 225,
        "large200_record_signed_volume": -225,
        "large200_record_count": 1,
    }
    values.update(overrides)
    return pd.Series(values)


def test_delayed_trap_signals_on_confirmation_bar_not_event_bar():
    entry = LargeRecordDelayedAoiConfirmationEntry(_params())

    assert entry.on_bar_close(_bar("2024-01-03 10:00:00")) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            open=99.75,
            high=100.50,
            low=99.75,
            close=100.25,
            signed_volume=80,
            large200_record_max_volume=0,
            large200_record_volume=0,
            large200_record_signed_volume=0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:02:00")
    assert signal.report_fields["event_timestamp"] == pd.Timestamp("2024-01-03 10:00:00")


def test_delayed_trap_rejects_wrong_confirmation_delta():
    entry = LargeRecordDelayedAoiConfirmationEntry(_params())

    entry.on_bar_close(_bar("2024-01-03 10:00:00"))
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:01:00", open=99.75, close=100.25, signed_volume=-80)
    )

    assert signal is None


def test_pending_event_is_cleared_on_session_roll():
    entry = LargeRecordDelayedAoiConfirmationEntry(_params())

    entry.on_bar_close(_bar("2024-01-03 10:00:00"))
    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 10:01:00",
            session_date="2024-01-04",
            open=99.75,
            high=100.50,
            low=99.75,
            close=100.25,
            signed_volume=80,
            large200_record_max_volume=0,
            large200_record_volume=0,
            large200_record_signed_volume=0,
        )
    )

    assert signal is None
    assert entry.pending_events == {}


def test_value_area_continuation_short_uses_val_level():
    entry = LargeRecordDelayedAoiConfirmationEntry(
        _params(setup_mode="value_area_delayed_continuation", min_confirm_delta_imbalance=0.0)
    )

    assert (
        entry.on_bar_close(
            _bar(
                "2024-01-03 10:00:00",
                open=100.25,
                high=100.50,
                low=99.50,
                close=99.75,
                large200_record_signed_volume=-225,
            )
        )
        is None
    )
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            open=99.75,
            high=100.0,
            low=99.25,
            close=99.50,
            signed_volume=-50,
            large200_record_max_volume=0,
            large200_record_volume=0,
            large200_record_signed_volume=0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["aoi_type"] == "prior_value_area_low"


def test_factory_registration_builds_module():
    entry = build_entry_module(
        {"module": "large_record_delayed_aoi_confirmation", "params": _params()}
    )

    assert isinstance(entry, LargeRecordDelayedAoiConfirmationEntry)
