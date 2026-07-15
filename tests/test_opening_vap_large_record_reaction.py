from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.opening_vap_large_record_reaction import (
    OpeningVapLargeRecordReactionEntry,
)
from tests.test_opening_vap_absorption_reaction import _bar


def _large_bar(timestamp: str, **kwargs) -> pd.Series:
    large_record_volume = kwargs.pop("large200_record_volume", 260.0)
    large_record_signed_volume = kwargs.pop("large200_record_signed_volume", -260.0)
    large_record_max_volume = kwargs.pop("large200_record_max_volume", 260.0)
    bar = _bar(timestamp, **kwargs)
    bar["large200_record_volume"] = large_record_volume
    bar["large200_record_signed_volume"] = large_record_signed_volume
    bar["large200_record_buy_volume"] = max(0.0, bar["large200_record_signed_volume"])
    bar["large200_record_sell_volume"] = max(0.0, -bar["large200_record_signed_volume"])
    bar["large200_record_count"] = 1.0
    bar["large200_record_max_volume"] = large_record_max_volume
    return bar


def test_large_record_opening_value_trap_requires_matching_record_side() -> None:
    entry = OpeningVapLargeRecordReactionEntry(
        {
            "setup_mode": "opening60_large_record_value_trap_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _large_bar(
            "2024-01-03 10:35:00",
            open_=99.25,
            low=99.0,
            close=99.75,
            signed_volume=-80.0,
            val=99.5,
            large200_record_signed_volume=-260.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:36:00")
    assert signal.report_fields["large200_record_dominant_side"] == "sell"


def test_large_record_opening_value_trap_rejects_wrong_record_side() -> None:
    entry = OpeningVapLargeRecordReactionEntry(
        {
            "setup_mode": "opening60_large_record_value_trap_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _large_bar(
            "2024-01-03 10:35:00",
            open_=99.25,
            low=99.0,
            close=99.75,
            signed_volume=-80.0,
            val=99.5,
            large200_record_signed_volume=260.0,
        )
    )

    assert signal is None


def test_large_record_opening_acceptance_emits_long_with_buy_record() -> None:
    entry = OpeningVapLargeRecordReactionEntry(
        {
            "setup_mode": "opening30_large_record_value_acceptance_two_sided",
            "start_time": "10:00:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _large_bar(
            "2024-01-03 10:01:00",
            prefix="opening30_vap",
            open_=100.25,
            high=101.0,
            low=100.0,
            close=100.75,
            signed_volume=100.0,
            vah=100.5,
            large200_record_signed_volume=300.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["boundary_type"] == "vah"
    assert signal.report_fields["large200_record_dominant_side"] == "buy"


def test_large_record_poc_acceptance_uses_poc_boundary() -> None:
    entry = OpeningVapLargeRecordReactionEntry(
        {
            "setup_mode": "opening60_large_record_poc_acceptance_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _large_bar(
            "2024-01-03 10:35:00",
            open_=100.0,
            high=100.75,
            low=99.75,
            close=100.5,
            signed_volume=100.0,
            poc=100.25,
            large200_record_signed_volume=300.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["boundary_type"] == "poc"


def test_large_record_lvn_acceptance_uses_lvn_boundary() -> None:
    entry = OpeningVapLargeRecordReactionEntry(
        {
            "setup_mode": "opening30_large_record_lvn_acceptance_two_sided",
            "start_time": "10:00:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _large_bar(
            "2024-01-03 10:01:00",
            prefix="opening30_vap",
            open_=99.75,
            high=100.0,
            low=99.0,
            close=99.25,
            signed_volume=-100.0,
            lvn_low=99.5,
            large200_record_signed_volume=-300.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["boundary_type"] == "lvn_near_low"


def test_large_record_rejects_below_minimum_volume() -> None:
    entry = OpeningVapLargeRecordReactionEntry(
        {
            "setup_mode": "opening60_large_record_value_trap_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _large_bar(
            "2024-01-03 10:35:00",
            open_=99.25,
            low=99.0,
            close=99.75,
            signed_volume=-80.0,
            val=99.5,
            large200_record_max_volume=199.0,
        )
    )

    assert signal is None


def test_large_record_entry_factory_registration() -> None:
    entry = build_entry_module(
        {
            "module": "opening_vap_large_record_reaction",
            "params": {"setup_mode": "opening30_large_record_value_trap_two_sided"},
        }
    )

    assert isinstance(entry, OpeningVapLargeRecordReactionEntry)
