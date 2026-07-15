import pandas as pd
import pytest

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.true_vap_value_area_orderflow_acceptance import (
    TrueVapValueAreaOrderflowAcceptanceEntry,
)


def _bar(ts: str, **overrides):
    row = {
        "timestamp": pd.Timestamp(ts, tz="America/New_York"),
        "session_date": "2024-01-03",
        "is_rth": True,
        "open": 100.0,
        "high": 101.0,
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
        "prior_vap_session_yyyymmdd": 20240102,
        "prior_vap_poc": 100.0,
        "prior_vap_vah": 101.0,
        "prior_vap_val": 99.0,
        "prior_vap_total_volume": 500000,
        "prior_vap_price_levels": 80,
    }
    row.update(overrides)
    return pd.Series(row)


def _entry(**params):
    base = {
        "setup_mode": "vah_acceptance_long",
        "start_time": "09:30:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "breakout_buffer_ticks": 1,
        "min_orderflow_imbalance": 0.2,
        "flow_mode": "signed_volume",
        "max_trades_per_day": 1,
    }
    base.update(params)
    return TrueVapValueAreaOrderflowAcceptanceEntry(base)


def test_true_vap_value_area_acceptance_uses_cached_vah_and_next_bar_entry():
    entry = _entry()
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35",
            open=100.75,
            high=101.75,
            close=101.5,
            signed_volume=300,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.breakout_level == pytest.approx(101.0)
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:36", tz="America/New_York")
    assert signal.metadata["prior_value_area_high"] == pytest.approx(101.0)
    assert signal.metadata["prior_point_of_control"] == pytest.approx(100.0)
    assert signal.metadata["orderflow_imbalance"] == pytest.approx(0.3)


def test_true_vap_value_area_acceptance_requires_cached_profile_columns():
    entry = _entry()
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35",
            open=100.75,
            high=101.75,
            close=101.5,
            signed_volume=300,
            prior_vap_vah=None,
        )
    )

    assert signal is None


def test_true_vap_value_area_acceptance_short_requires_negative_flow():
    entry = _entry(setup_mode="val_acceptance_short", allow_long=False, allow_short=True)

    no_signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35",
            open=99.25,
            low=98.25,
            close=98.5,
            signed_volume=300,
        )
    )
    assert no_signal is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 09:35",
            session_date="2024-01-04",
            open=99.25,
            low=98.25,
            close=98.5,
            signed_volume=-300,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.breakout_level == pytest.approx(99.0)
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-04 09:36", tz="America/New_York")


def test_true_vap_value_area_acceptance_honors_start_location_filter():
    entry = _entry(start_location_filter="inside_value")

    assert (
        entry.on_bar_close(
            _bar(
                "2024-01-03 09:30",
                open=101.5,
                high=101.75,
                close=101.5,
                signed_volume=300,
            )
        )
        is None
    )


def test_true_vap_value_area_acceptance_can_require_footprint_confirmation():
    entry = _entry(min_footprint_imbalance_volume=50)

    assert (
        entry.on_bar_close(
            _bar(
                "2024-01-03 09:35",
                open=100.75,
                high=101.75,
                close=101.5,
                signed_volume=300,
                footprint_max_buy_imbalance_volume=49,
            )
        )
        is None
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 09:35",
            session_date="2024-01-04",
            open=100.75,
            high=101.75,
            close=101.5,
            signed_volume=300,
            footprint_max_buy_imbalance_volume=50,
        )
    )
    assert signal is not None
    assert signal.metadata["footprint_imbalance_volume"] == pytest.approx(50)


def test_true_vap_value_area_acceptance_registers_with_entry_factory():
    built = build_entry_module({"module": "true_vap_value_area_orderflow_acceptance", "params": {}})

    assert isinstance(built, TrueVapValueAreaOrderflowAcceptanceEntry)
