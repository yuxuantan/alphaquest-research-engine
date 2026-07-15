from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.nq_es_smt_po3_midpoint_reversion import (
    NqEsSmtPo3MidpointReversionEntry,
)


def _bar(ts: str, open_: float, high: float, low: float, close: float, es_high: float, es_low: float) -> pd.Series:
    timestamp = pd.Timestamp(ts)
    return pd.Series(
        {
            "timestamp": timestamp,
            "session_date": timestamp.date(),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "es_high": es_high,
            "es_low": es_low,
            "is_rth": True,
        }
    )


def test_nq_es_smt_prior_high_nonconfirmation_short_targets_midpoint():
    entry = NqEsSmtPo3MidpointReversionEntry(
        {
            "setup_mode": "prior_high_short",
            "setup_start_time": "09:30:00",
            "start_time": "10:00:00",
            "end_time": "11:30:00",
            "bar_interval_minutes": 1,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "reclaim_buffer_ticks": 0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-02 09:30", 95, 100, 90, 95, 50, 40)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:30", 98, 99, 95, 98, 49, 45)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", 98, 101, 97, 100.5, 49.5, 45)) is None

    signal = entry.on_bar_close(_bar("2024-01-03 10:00", 100.5, 100.75, 98, 99.75, 49.75, 45))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:01")
    assert signal.swept_level == 100
    assert signal.sweep_high == 101
    assert signal.metadata["previous_nq_midpoint"] == 95
    assert signal.metadata["signal_target_price"] == 95
    assert signal.metadata["smt_reference_level"] == 50


def test_nq_es_smt_prior_high_sweep_rejected_when_es_confirms():
    entry = NqEsSmtPo3MidpointReversionEntry(
        {
            "setup_mode": "prior_high_short",
            "setup_start_time": "09:30:00",
            "start_time": "10:00:00",
            "end_time": "11:30:00",
            "bar_interval_minutes": 1,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "reclaim_buffer_ticks": 0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-02 09:30", 95, 100, 90, 95, 50, 40)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", 98, 101, 97, 100.5, 50.25, 45)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:00", 100.5, 100.75, 98, 99.75, 50.5, 45)) is None


def test_nq_es_smt_registered_entry_module():
    entry = build_entry_module(
        {"module": "nq_es_smt_po3_midpoint_reversion", "params": {"setup_mode": "prior_two_sided"}}
    )
    assert isinstance(entry, NqEsSmtPo3MidpointReversionEntry)
