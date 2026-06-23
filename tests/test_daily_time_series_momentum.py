from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.daily_time_series_momentum import DailyTimeSeriesMomentumEntry


def test_daily_time_series_momentum_uses_only_recorded_prior_closes():
    entry = DailyTimeSeriesMomentumEntry(
        {
            "setup_mode": "close_to_close_trend",
            "lookback_sessions": 3,
            "min_abs_trend_return_pct": 0.01,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-02 15:55", close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 15:55", close=101.0)) is None
    assert entry.on_bar_close(_bar("2024-01-04 15:55", close=103.0)) is None

    signal = entry.on_bar_close(_bar("2024-01-05 09:55", close=99.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-05 10:00")
    assert signal.report_fields["trend_anchor_session_date"] == pd.Timestamp("2024-01-02").date()
    assert signal.report_fields["trend_recent_session_date"] == pd.Timestamp("2024-01-04").date()


def test_daily_time_series_momentum_short_term_alignment_rejects_disagreement():
    entry = DailyTimeSeriesMomentumEntry(
        {
            "setup_mode": "short_term_alignment",
            "lookback_sessions": 4,
            "confirmation_sessions": 1,
            "min_abs_trend_return_pct": 0.01,
            "signal_time": "10:00:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
        }
    )

    for timestamp, close in [
        ("2024-01-02 15:55", 100.0),
        ("2024-01-03 15:55", 105.0),
        ("2024-01-04 15:55", 106.0),
        ("2024-01-05 15:55", 104.0),
    ]:
        assert entry.on_bar_close(_bar(timestamp, close=close)) is None

    assert entry.on_bar_close(_bar("2024-01-08 09:55", close=104.5)) is None


def _bar(timestamp: str, *, close: float, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        }
    )
