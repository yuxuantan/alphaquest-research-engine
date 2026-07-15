from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.daily_bollinger_environment import DailyBollingerEnvironmentEntry


def test_daily_bollinger_expansion_long_uses_completed_prior_daily_state():
    entry = DailyBollingerEnvironmentEntry(
        {
            "setup_mode": "expansion_long_breakout",
            "bb_length": 20,
            "width_rank_lookback": 5,
            "width_rank_threshold": 0.5,
            "opening_range_minutes": 15,
            "min_breakout_ticks": 1,
            "tick_size": 0.25,
        }
    )

    for i in range(20):
        assert entry.on_bar_close(_daily_bar(date(2024, 1, 2) + timedelta(days=i), close=100.0)) is None
    assert entry.on_bar_close(_daily_bar(date(2024, 1, 22), close=120.0, high=121.0, low=119.0)) is None

    for bar in [
        _bar("2024-01-23 09:30", open_=120.0, high=120.5, low=119.5, close=120.0),
        _bar("2024-01-23 09:35", open_=120.0, high=120.7, low=119.8, close=120.2),
        _bar("2024-01-23 09:40", open_=120.2, high=120.8, low=119.9, close=120.1),
    ]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(_bar("2024-01-23 09:45", open_=120.1, high=121.5, low=120.0, close=121.25))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "daily_bb_expansion_long_or_breakout"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-23 09:50")
    assert signal.report_fields["bb_state_session_date"] == "2024-01-22"
    assert signal.report_fields["bb_width_rank"] >= 0.5


def test_daily_bollinger_does_not_use_current_session_spike_as_daily_state():
    entry = DailyBollingerEnvironmentEntry(
        {
            "setup_mode": "expansion_long_breakout",
            "bb_length": 20,
            "width_rank_lookback": 5,
            "width_rank_threshold": 0.5,
            "opening_range_minutes": 15,
        }
    )

    for i in range(21):
        assert entry.on_bar_close(_daily_bar(date(2024, 1, 2) + timedelta(days=i), close=100.0)) is None

    for bar in [
        _bar("2024-01-24 09:30", open_=100.0, high=100.5, low=99.5, close=100.0),
        _bar("2024-01-24 09:35", open_=100.0, high=100.5, low=99.5, close=100.2),
        _bar("2024-01-24 09:40", open_=100.2, high=100.6, low=99.8, close=100.1),
        _bar("2024-01-24 09:45", open_=100.1, high=125.0, low=100.0, close=124.0),
    ]:
        assert entry.on_bar_close(bar) is None


def test_daily_bollinger_consolidation_fades_prior_high_probe():
    entry = DailyBollingerEnvironmentEntry(
        {
            "setup_mode": "consolidation_edge_reversion",
            "bb_length": 3,
            "width_rank_lookback": 3,
            "width_rank_threshold": 1.0,
            "start_time": "09:35:00",
            "end_time": "12:00:00",
            "min_breakout_ticks": 1,
            "tick_size": 0.25,
        }
    )
    closes = [100.0, 130.0, 100.0, 100.0, 100.0]
    for i, close in enumerate(closes):
        high = 105.0 if i == len(closes) - 1 else close + 1.0
        low = 95.0 if i == len(closes) - 1 else close - 1.0
        assert entry.on_bar_close(_daily_bar(date(2024, 2, 1) + timedelta(days=i), close=close, high=high, low=low)) is None

    signal = entry.on_bar_close(_bar("2024-02-06 09:35", open_=105.0, high=106.0, low=104.0, close=104.5))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.level_type == "daily_bb_consolidation_prior_high_rejection"
    assert signal.swept_level == 105.0


def test_daily_bollinger_factory_registration_builds_module():
    entry = build_entry_module({"module": "daily_bollinger_environment", "params": {"setup_mode": "mean_reversion_short"}})

    assert isinstance(entry, DailyBollingerEnvironmentEntry)


def _daily_bar(day: date, *, close: float, high: float | None = None, low: float | None = None) -> pd.Series:
    high = close + 1.0 if high is None else high
    low = close - 1.0 if low is None else low
    return pd.Series(
        {
            "timestamp": pd.Timestamp(f"{day.isoformat()} 15:55:00"),
            "session_date": day.isoformat(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "session_label": "RTH",
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )
