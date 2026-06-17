from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.round_number_barrier import RoundNumberBarrierEntry


def test_round_number_barrier_support_reclaim_uses_completed_bar_close():
    entry = RoundNumberBarrierEntry(
        {
            "setup_mode": "support_reclaim_long",
            "start_time": "09:35:00",
            "end_time": "12:00:00",
            "barrier_interval_points": 50,
            "buffer_ticks": 1,
            "max_close_distance_ticks": 12,
            "bar_interval_minutes": 5,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55", low=4999.75, close=5000.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 5000
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["round_number_barrier"] == 5000


def test_round_number_barrier_resistance_reject_short():
    entry = RoundNumberBarrierEntry(
        {
            "setup_mode": "resistance_reject_short",
            "barrier_interval_points": 50,
            "buffer_ticks": 1,
            "max_close_distance_ticks": 12,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:10", high=5050.25, close=5049.5))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 5050


def test_round_number_barrier_breakout_waits_for_prior_completed_close():
    entry = RoundNumberBarrierEntry(
        {
            "setup_mode": "upside_breakout_long",
            "barrier_interval_points": 50,
            "buffer_ticks": 1,
            "max_close_distance_ticks": 12,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:35", low=4998.0, close=4999.5)) is None
    signal = entry.on_bar_close(_bar("2024-01-03 09:40", high=5001.0, low=4999.25, close=5000.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "round_number_upside_breakout"


def test_round_number_barrier_rejects_non_rth_and_one_trade_per_day():
    entry = RoundNumberBarrierEntry({"setup_mode": "two_sided_reclaim"})

    assert entry.on_bar_close(_bar("2024-01-03 10:00", low=4999.75, close=5000.5, is_rth=False)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:05", low=4999.75, close=5000.5)) is not None
    assert entry.on_bar_close(_bar("2024-01-03 10:10", low=5049.75, close=5050.5)) is None


def _bar(timestamp: str, *, low: float | None = None, high: float | None = None, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    low = close - 1.0 if low is None else low
    high = close + 1.0 if high is None else high
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.25,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )
