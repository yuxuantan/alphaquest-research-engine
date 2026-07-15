from __future__ import annotations

from datetime import date

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.weekly_stage_analysis import WeeklyStageAnalysisEntry


def _seed_weekly_sessions(entry: WeeklyStageAnalysisEntry, *, start: str, weeks: int, rising: bool) -> list[date]:
    dates = [ts.date() for ts in pd.date_range(start=start, periods=weeks, freq="W-FRI")]
    for idx, session_date in enumerate(dates):
        price = 100.0 + idx if rising else 200.0 - idx
        entry.session_stats[session_date] = {
            "session_date": session_date,
            "open": price - 0.5,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
        }
    return dates


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> pd.Series:
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "is_rth": True,
        }
    )


def test_weekly_stage_excludes_current_incomplete_week() -> None:
    entry = WeeklyStageAnalysisEntry(
        {
            "setup_mode": "stage2_opening_range_breakout",
            "stage_strength_threshold": 5,
        }
    )
    dates = _seed_weekly_sessions(entry, start="2024-01-05", weeks=45, rising=False)
    current_monday = dates[-1] + pd.Timedelta(days=3)
    session_date = dates[-1] + pd.Timedelta(days=4)
    entry.session_stats[current_monday] = {
        "session_date": current_monday,
        "open": 500.0,
        "high": 520.0,
        "low": 495.0,
        "close": 520.0,
    }

    stage = entry._stage_for_session(session_date)

    assert stage is not None
    assert stage.week_end == dates[-1]
    assert stage.stage2_score < entry.stage_strength_threshold


def test_opening_range_breakout_waits_for_completed_opening_range() -> None:
    entry = WeeklyStageAnalysisEntry(
        {
            "setup_mode": "stage2_opening_range_breakout",
            "stage_strength_threshold": 5,
            "opening_range_minutes": 10,
            "bar_interval_minutes": 5,
            "start_time": "09:40:00",
            "end_time": "10:30:00",
            "min_breakout_ticks": 0,
        }
    )
    _seed_weekly_sessions(entry, start="2024-01-05", weeks=45, rising=True)

    assert entry.on_bar_close(_bar("2024-11-12 09:30", open_=145, high=146, low=144, close=145), 0) is None
    assert entry.on_bar_close(_bar("2024-11-12 09:35", open_=145, high=147, low=144, close=146), 0) is None

    signal = entry.on_bar_close(_bar("2024-11-12 09:40", open_=146, high=148, low=145, close=148), 0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "stage2_opening_range_breakout"
    assert signal.swept_level == 147
    assert signal.sweep_timestamp == pd.Timestamp("2024-11-12 09:45", tz="America/New_York")


def test_weekly_stage_analysis_registered_entry_module() -> None:
    entry = build_entry_module(
        {
            "module": "weekly_stage_analysis",
            "params": {"setup_mode": "stage2_prior_high_reclaim"},
        }
    )

    assert isinstance(entry, WeeklyStageAnalysisEntry)
