from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.london_trident_fvg_continuation import (
    LondonTridentFvgContinuationEntry,
)


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
            "is_eth": True,
        }
    )


def _entry(**overrides) -> LondonTridentFvgContinuationEntry:
    params = {
        "setup_mode": "long",
        "fvg_start_time": "12:00:00",
        "fvg_end_time": "12:00:00",
        "start_time": "12:00:00",
        "end_time": "13:30:00",
        "bar_interval_minutes": 30,
        "tick_size": 0.25,
        "min_gap_ticks": 4,
        "max_doji_body_ratio": 0.35,
        "mid_ema_period": 13,
        "confirmation_buffer_ticks": 0,
        "require_200_ema_bias": False,
    }
    params.update(overrides)
    return LondonTridentFvgContinuationEntry(params)


def test_london_trident_fvg_waits_for_confirmation_bar_close():
    entry = _entry()
    for index, timestamp in enumerate(pd.date_range("2024-01-03 00:00", periods=22, freq="30min")):
        close = 100.0 + index * 0.4
        assert entry.on_bar_close(_bar(str(timestamp), close - 0.1, close + 0.4, close - 0.4, close)) is None

    assert entry.on_bar_close(_bar("2024-01-03 11:00", 109.0, 110.0, 108.0, 109.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 11:30", 109.0, 111.0, 108.75, 110.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 12:00", 111.5, 113.0, 112.0, 112.75)) is None
    assert entry.on_bar_close(_bar("2024-01-03 12:30", 111.4, 112.5, 111.0, 111.5)) is None

    signal = entry.on_bar_close(_bar("2024-01-03 13:00", 111.6, 113.0, 111.5, 112.75))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 13:30")
    assert signal.metadata["fvg_bottom"] == 110.0
    assert signal.metadata["fvg_top"] == 112.0
    assert signal.metadata["fvg_midpoint"] == 111.0
    assert signal.breakout_level == 112.5
    assert signal.sweep_low == 111.0


def test_london_trident_fvg_rejects_unconfirmed_doji():
    entry = _entry()
    for index, timestamp in enumerate(pd.date_range("2024-01-03 00:00", periods=22, freq="30min")):
        close = 100.0 + index * 0.4
        entry.on_bar_close(_bar(str(timestamp), close - 0.1, close + 0.4, close - 0.4, close))

    entry.on_bar_close(_bar("2024-01-03 11:00", 109.0, 110.0, 108.0, 109.0))
    entry.on_bar_close(_bar("2024-01-03 11:30", 109.0, 111.0, 108.75, 110.5))
    entry.on_bar_close(_bar("2024-01-03 12:00", 111.5, 113.0, 112.0, 112.75))
    entry.on_bar_close(_bar("2024-01-03 12:30", 111.4, 112.5, 111.0, 111.5))

    assert entry.on_bar_close(_bar("2024-01-03 13:00", 111.6, 112.25, 111.5, 112.0)) is None


def test_london_trident_fvg_registered_entry_module():
    entry = build_entry_module({"module": "london_trident_fvg_continuation", "params": {"setup_mode": "two_sided"}})
    assert isinstance(entry, LondonTridentFvgContinuationEntry)
