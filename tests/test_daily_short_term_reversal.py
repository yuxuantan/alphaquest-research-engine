from __future__ import annotations

import pandas as pd
import pytest

from propstack.strategy_modules.entry.daily_short_term_reversal import DailyShortTermReversalEntry


def test_daily_short_term_reversal_fades_completed_prior_loss():
    entry = DailyShortTermReversalEntry(
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
    signal = entry.on_bar_close(_bar("2024-01-04 09:55", close=98.75))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-04 10:00")
    assert signal.report_fields["reversal_return_pct"] == pytest.approx(-0.01)
    assert signal.report_fields["reversal_recent_session_date"] == "2024-01-03"


def test_daily_short_term_reversal_fades_completed_prior_gain():
    entry = DailyShortTermReversalEntry(
        {
            "direction_mode": "gain_short",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-02 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", close=101.0))
    signal = entry.on_bar_close(_bar("2024-01-04 09:55", close=101.25))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["reversal_return_pct"] == pytest.approx(0.01)


def test_daily_short_term_reversal_does_not_use_current_session_close():
    entry = DailyShortTermReversalEntry(
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
    entry.on_bar_close(_bar("2024-01-03 09:55", close=90.0))

    assert entry.on_bar_close(_bar("2024-01-03 10:00", close=89.0)) is None


def test_daily_short_term_reversal_volatility_normalized_gate():
    entry = DailyShortTermReversalEntry(
        {
            "setup_mode": "volatility_normalized_reversal",
            "direction_mode": "two_sided",
            "lookback_sessions": 3,
            "min_abs_reversal_return_pct": 0.0,
            "min_reversal_zscore": 0.5,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    entry.on_bar_close(_bar("2024-01-02 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", close=99.0))
    entry.on_bar_close(_bar("2024-01-04 15:55", close=97.0))
    entry.on_bar_close(_bar("2024-01-05 15:55", close=96.0))
    signal = entry.on_bar_close(_bar("2024-01-08 09:55", close=95.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["reversal_zscore"] < -0.5


def test_daily_short_term_reversal_rejects_non_rth_and_duplicate_day():
    entry = DailyShortTermReversalEntry(
        {
            "direction_mode": "gain_short",
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.005,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-02 15:55", close=100.0, is_rth=False)) is None
    entry.on_bar_close(_bar("2024-01-02 15:55", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", close=101.0))

    first = entry.on_bar_close(_bar("2024-01-04 09:55", close=101.25))
    second = entry.on_bar_close(_bar("2024-01-04 10:00", close=101.5))

    assert first is not None
    assert second is None


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
