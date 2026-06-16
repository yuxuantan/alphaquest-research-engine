from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.preholiday_effect import PreholidayEffectEntry


def test_preholiday_entry_emits_on_signal_date_completed_bar(tmp_path):
    calendar = _calendar(tmp_path)
    entry = PreholidayEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-07-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-07-03 10:00")
    assert signal.report_fields["preholiday_signal_session_date"] == "2024-07-03"


def test_preholiday_entry_rejects_non_signal_session(tmp_path):
    calendar = _calendar(tmp_path)
    entry = PreholidayEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-07-02 09:59", close=100.5)) is None


def test_preholiday_entry_rejects_non_rth_bar(tmp_path):
    calendar = _calendar(tmp_path)
    entry = PreholidayEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-07-03 09:59", close=100.5, is_rth=False)) is None


def test_preholiday_entry_momentum_filter_uses_completed_session_state(tmp_path):
    calendar = _calendar(tmp_path)
    entry = PreholidayEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "momentum_confirmed_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_session_return_bps": 20,
        }
    )

    assert entry.on_bar_close(_bar("2024-07-03 09:30", close=100.05)) is None
    assert entry.on_bar_close(_bar("2024-07-03 09:59", close=100.10)) is None


def test_preholiday_entry_low_range_filter(tmp_path):
    calendar = _calendar(tmp_path)
    entry = PreholidayEffectEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "low_range_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "max_session_range_bps": 20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-07-03 09:59", close=100.5, high=100.6, low=100.45))

    assert signal is not None
    assert signal.report_fields["session_range_bps"] <= 20


def _calendar(tmp_path):
    path = tmp_path / "preholiday.csv"
    path.write_text(
        "signal_date,holiday_date,holiday_name,regular_session,source,notes\n"
        "2024-07-03,2024-07-04,Independence Day,true,unit_test,last regular session before full holiday\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, *, close: float, high: float | None = None, low: float | None = None, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    high = high if high is not None else close + 0.25
    low = low if low is not None else close - 0.25
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": 100.0,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )
