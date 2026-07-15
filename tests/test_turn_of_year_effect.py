from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.turn_of_year_effect import TurnOfYearEffectEntry


def test_turn_of_year_entry_emits_on_december_window_date(tmp_path):
    calendar = _calendar(tmp_path)
    entry = TurnOfYearEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "all_window_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-12-24 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-12-24 10:00")
    assert signal.report_fields["turn_of_year_signal_session_date"] == "2024-12-24"


def test_turn_of_year_january_mode_rejects_december_date(tmp_path):
    calendar = _calendar(tmp_path)
    entry = TurnOfYearEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "january_window_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-12-24 09:59", close=100.5)) is None


def test_turn_of_year_january_mode_accepts_january_date(tmp_path):
    calendar = _calendar(tmp_path)
    entry = TurnOfYearEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "january_window_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2025-01-02 09:59", close=100.5))

    assert signal is not None


def test_turn_of_year_momentum_filter_uses_completed_session_state(tmp_path):
    calendar = _calendar(tmp_path)
    entry = TurnOfYearEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "momentum_confirmed_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_session_return_bps": 20,
        }
    )

    assert entry.on_bar_close(_bar("2024-12-24 09:30", close=100.05)) is None
    assert entry.on_bar_close(_bar("2024-12-24 09:59", close=100.10)) is None


def test_turn_of_year_low_range_filter(tmp_path):
    calendar = _calendar(tmp_path)
    entry = TurnOfYearEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "low_range_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "max_session_range_bps": 20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-12-24 09:59", close=100.5, high=100.6, low=100.45))

    assert signal is not None
    assert signal.report_fields["session_range_bps"] <= 20


def _calendar(tmp_path):
    path = tmp_path / "turn_of_year.csv"
    path.write_text(
        "signal_date,window_year,period,rank_in_period,regular_session,source,notes\n"
        "2024-12-24,2025,december_last5,1,true,unit_test,last five regular December sessions\n"
        "2025-01-02,2025,january_first2,1,true,unit_test,first two regular January sessions\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, *, close: float, high: float | None = None, low: float | None = None):
    ts = pd.Timestamp(timestamp)
    high = high if high is not None else close + 0.25
    low = low if low is not None else close - 0.25
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": 100.0,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )
