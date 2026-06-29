from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.opening_vap_absorption_reaction import (
    OpeningVapAbsorptionReactionEntry,
)


def _bar(
    timestamp: str,
    *,
    session_date: str = "2024-01-03",
    open_: float = 100.0,
    high: float = 100.75,
    low: float = 99.0,
    close: float = 99.75,
    volume: float = 1000.0,
    signed_volume: float = -80.0,
    prefix: str = "opening60_vap",
    poc: float | None = 100.0,
    vah: float | None = 100.5,
    val: float | None = 99.5,
    lvn_high: float | None = 100.75,
    lvn_low: float | None = 99.25,
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
        "large10_signed_volume": signed_volume,
        "large10_volume": volume,
        "large20_signed_volume": signed_volume,
        "large20_volume": volume,
        "footprint_absorption_long": 1,
        "footprint_absorption_short": 1,
        "footprint_max_sell_imbalance_volume": 30.0,
        "footprint_max_buy_imbalance_volume": 30.0,
        "footprint_highest_sell_imbalance_price": 99.25,
        "footprint_lowest_buy_imbalance_price": 100.25,
        f"{prefix}_session_yyyymmdd": 20240103,
        f"{prefix}_window_minutes": 60 if "60" in prefix else 30,
        f"{prefix}_poc": poc,
        f"{prefix}_vah": vah,
        f"{prefix}_val": val,
        f"{prefix}_lvn_near_high": lvn_high,
        f"{prefix}_lvn_near_low": lvn_low,
        f"{prefix}_lvn_count": 2,
        f"{prefix}_total_volume": 100000.0,
        f"{prefix}_price_levels": 12,
    }
    return pd.Series(values)


def test_opening60_value_trap_emits_long_next_bar() -> None:
    entry = OpeningVapAbsorptionReactionEntry(
        {
            "setup_mode": "opening60_value_trap_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "confirmation_ticks": 0,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:35:00",
            open_=99.25,
            low=99.0,
            close=99.75,
            signed_volume=-80.0,
            val=99.5,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:36:00")
    assert signal.report_fields["boundary_type"] == "val"
    assert signal.report_fields["reaction_type"] == "trap"


def test_opening60_rejects_before_ready_start_time() -> None:
    entry = OpeningVapAbsorptionReactionEntry(
        {
            "setup_mode": "opening60_value_trap_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            open_=99.25,
            low=99.0,
            close=99.75,
            signed_volume=-80.0,
            val=99.5,
        )
    )

    assert signal is None


def test_opening_vap_rejects_when_profile_column_missing() -> None:
    entry = OpeningVapAbsorptionReactionEntry(
        {
            "setup_mode": "opening60_value_trap_two_sided",
            "start_time": "10:35:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:35:00",
            open_=99.25,
            low=99.0,
            close=99.75,
            signed_volume=-80.0,
            val=None,
        )
    )

    assert signal is None


def test_opening30_value_acceptance_emits_short_next_bar() -> None:
    entry = OpeningVapAbsorptionReactionEntry(
        {
            "setup_mode": "opening30_value_acceptance_two_sided",
            "start_time": "10:00:00",
            "end_time": "12:30:00",
            "bar_interval_minutes": 1,
            "min_probe_ticks": 1,
            "confirmation_ticks": 0,
            "min_orderflow_imbalance": 0.05,
            "min_footprint_imbalance_volume": 20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            prefix="opening30_vap",
            open_=99.75,
            high=100.0,
            low=99.0,
            close=99.25,
            signed_volume=-80.0,
            val=99.5,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:02:00")
    assert signal.report_fields["boundary_type"] == "val"
    assert signal.report_fields["reaction_type"] == "acceptance"


def test_opening_vap_entry_factory_registration() -> None:
    entry = build_entry_module(
        {
            "module": "opening_vap_absorption_reaction",
            "params": {"setup_mode": "opening30_value_trap_two_sided"},
        }
    )

    assert isinstance(entry, OpeningVapAbsorptionReactionEntry)
