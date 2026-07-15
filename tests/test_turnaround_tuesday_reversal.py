from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.turnaround_tuesday_reversal import TurnaroundTuesdayReversalEntry


def test_turnaround_tuesday_goes_long_after_completed_monday_loss():
    entry = TurnaroundTuesdayReversalEntry(
        {
            "direction_mode": "loss_long",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-05 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-08 15:55", close=99.0))
    signal = entry.on_bar_close(_bar("2024-01-09 09:55", close=99.25))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-09 10:00")
    assert signal.report_fields["reversal_return_pct"] == pytest.approx(-0.01)
    assert signal.report_fields["reversal_recent_weekday"] == 0


def test_turnaround_tuesday_rejects_non_tuesday_and_non_monday_prior_session():
    entry = TurnaroundTuesdayReversalEntry(
        {
            "direction_mode": "loss_long",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-02 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", close=99.0))
    assert entry.on_bar_close(_bar("2024-01-04 09:55", close=99.25)) is None

    holiday_week = TurnaroundTuesdayReversalEntry(
        {
            "direction_mode": "loss_long",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )
    holiday_week.on_bar_close(_bar("2024-01-11 15:55", close=100.0))
    holiday_week.on_bar_close(_bar("2024-01-12 15:55", close=99.0))
    assert holiday_week.on_bar_close(_bar("2024-01-16 09:55", close=99.25)) is None


def test_turnaround_tuesday_can_short_after_completed_monday_gain():
    entry = TurnaroundTuesdayReversalEntry(
        {
            "direction_mode": "gain_short",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-05 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-08 15:55", close=101.0))
    signal = entry.on_bar_close(_bar("2024-01-09 09:55", close=101.25))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["reversal_return_pct"] == pytest.approx(0.01)


def test_turnaround_tuesday_does_not_use_current_session_close():
    entry = TurnaroundTuesdayReversalEntry(
        {
            "direction_mode": "loss_long",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-05 15:55", close=100.0))
    assert entry.on_bar_close(_bar("2024-01-09 09:55", close=90.0)) is None


def test_turnaround_tuesday_volatility_normalized_gate():
    entry = TurnaroundTuesdayReversalEntry(
        {
            "setup_mode": "volatility_normalized_reversal",
            "direction_mode": "loss_long",
            "lookback_sessions": 3,
            "min_abs_reversal_return_pct": 0.0,
            "min_reversal_zscore": 0.5,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-04 15:55", close=99.5))
    entry.on_bar_close(_bar("2024-01-05 15:55", close=99.0))
    entry.on_bar_close(_bar("2024-01-08 15:55", close=97.0))
    signal = entry.on_bar_close(_bar("2024-01-09 09:55", close=97.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["reversal_zscore"] < -0.5


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000,
        }
    )
