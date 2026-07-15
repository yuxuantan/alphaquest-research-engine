from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.liquidity_inversion_fvg import LiquidityInversionFvgEntry


def _bar(ts: str, open_: float, high: float, low: float, close: float) -> pd.Series:
    timestamp = pd.Timestamp(ts)
    return pd.Series(
        {
            "timestamp": timestamp,
            "session_date": timestamp.date(),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "is_rth": True,
        }
    )


def test_liquidity_inversion_waits_for_completed_gap_inversion():
    entry = LiquidityInversionFvgEntry(
        {
            "setup_mode": "prior_high_short",
            "setup_start_time": "09:30:00",
            "start_time": "09:35:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "min_gap_ticks": 2,
            "max_inversion_bars": 4,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-02 09:30", 95, 100, 90, 95)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:30", 98, 99, 96, 98)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35", 98, 101, 97, 100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:40", 100.5, 102, 100.75, 101.5)) is None

    signal = entry.on_bar_close(_bar("2024-01-03 09:45", 101.5, 101.75, 98.5, 98.75))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:50")
    assert signal.swept_level == 100
    assert signal.sweep_high == 102
    assert signal.metadata["fvg_type"] == "bullish_fvg"
    assert signal.metadata["fvg_bottom"] == 99
    assert signal.metadata["fvg_top"] == 100.75


def test_liquidity_inversion_current_session_reference_uses_prebar_extreme():
    entry = LiquidityInversionFvgEntry(
        {
            "setup_mode": "session_high_short",
            "setup_start_time": "09:30:00",
            "start_time": "09:35:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "min_gap_ticks": 2,
            "max_inversion_bars": 4,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", 98, 100, 97, 99)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35", 99, 99.5, 98, 99)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:40", 99, 101, 100.75, 100.8)) is None
    signal = entry.on_bar_close(_bar("2024-01-03 09:45", 100.8, 101, 98.5, 99))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.metadata["liquidity_reference_type"] == "current_session_high"
    assert signal.metadata["liquidity_reference_level"] == 100
    assert signal.sweep_high == 101


def test_liquidity_inversion_registered_entry_module():
    entry = build_entry_module({"module": "liquidity_inversion_fvg", "params": {"setup_mode": "prior_two_sided"}})
    assert isinstance(entry, LiquidityInversionFvgEntry)
