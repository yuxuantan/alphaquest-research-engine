from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.fomc_pre_announcement_drift import FomcPreAnnouncementDriftEntry


def test_fomc_entry_emits_on_scheduled_decision_day_completed_bar(tmp_path):
    calendar = _calendar(tmp_path)
    entry = FomcPreAnnouncementDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "announcement_day_unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-31 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-31 10:00")
    assert signal.report_fields["fomc_signal_session_date"] == "2024-01-31"


def test_fomc_entry_rejects_non_event_session(tmp_path):
    calendar = _calendar(tmp_path)
    entry = FomcPreAnnouncementDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "announcement_day_unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-02-01 09:59", close=100.5)) is None


def test_fomc_entry_prior_day_offset_uses_known_prior_calendar_day(tmp_path):
    calendar = _calendar(tmp_path)
    entry = FomcPreAnnouncementDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "prior_day_unconditional_long",
            "event_day_offset": -1,
            "entry_time": "15:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-30 14:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"


def test_fomc_entry_momentum_filter_uses_only_current_session_state(tmp_path):
    calendar = _calendar(tmp_path)
    entry = FomcPreAnnouncementDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "announcement_day_momentum_confirmed_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_session_return_bps": 20,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-31 09:30", close=100.05)) is None
    assert entry.on_bar_close(_bar("2024-01-31 09:59", close=100.10)) is None


def test_fomc_entry_low_range_filter(tmp_path):
    calendar = _calendar(tmp_path)
    entry = FomcPreAnnouncementDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "setup_mode": "announcement_day_low_range_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "max_session_range_bps": 20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-31 09:59", close=100.5, high=100.6, low=100.45))

    assert signal is not None
    assert signal.report_fields["session_range_bps"] <= 20


def _calendar(tmp_path):
    path = tmp_path / "fomc.csv"
    path.write_text(
        "event_date,event_time,event_type,scheduled,source_year,source_url,source_label,notes\n"
        "2024-01-31,14:00:00,fomc_scheduled_decision,true,2024,https://example.test,January 30-31,test\n",
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
