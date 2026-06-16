from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.bls_macro_release_day_drift import BlsMacroReleaseDayDriftEntry
from tools.build_bls_macro_release_calendar import _parse_release_dates


def test_bls_entry_emits_on_allowed_release_type_completed_bar(tmp_path):
    calendar = _calendar(tmp_path)
    entry = BlsMacroReleaseDayDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "release_types": ["employment_situation"],
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-06-07 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-06-07 10:00")
    assert signal.report_fields["bls_signal_session_date"] == "2024-06-07"
    assert signal.report_fields["bls_release_types"] == "employment_situation"


def test_bls_entry_rejects_unconfigured_release_type(tmp_path):
    calendar = _calendar(tmp_path)
    entry = BlsMacroReleaseDayDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "release_types": ["cpi"],
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-06-07 09:59", close=100.5)) is None


def test_bls_entry_rejects_non_release_session(tmp_path):
    calendar = _calendar(tmp_path)
    entry = BlsMacroReleaseDayDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "release_types": ["employment_situation", "cpi"],
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-06-10 09:59", close=100.5)) is None


def test_bls_entry_rejects_non_rth_bar(tmp_path):
    calendar = _calendar(tmp_path)
    entry = BlsMacroReleaseDayDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "release_types": ["cpi"],
            "setup_mode": "unconditional_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-06-12 09:59", close=100.5, is_rth=False)) is None


def test_bls_entry_momentum_filter_uses_completed_session_state(tmp_path):
    calendar = _calendar(tmp_path)
    entry = BlsMacroReleaseDayDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "release_types": ["cpi"],
            "setup_mode": "momentum_confirmed_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_session_return_bps": 20,
        }
    )

    assert entry.on_bar_close(_bar("2024-06-12 09:30", close=100.05)) is None
    assert entry.on_bar_close(_bar("2024-06-12 09:59", close=100.10)) is None


def test_bls_entry_low_range_filter_uses_completed_session_state(tmp_path):
    calendar = _calendar(tmp_path)
    entry = BlsMacroReleaseDayDriftEntry(
        {
            "event_calendar_csv": str(calendar),
            "release_types": ["cpi"],
            "setup_mode": "low_range_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "max_session_range_bps": 20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-06-12 09:59", close=100.5, high=100.6, low=100.45))

    assert signal is not None
    assert signal.report_fields["session_range_bps"] <= 20


def test_bls_release_date_parser_uses_date_only_lines():
    text = """
    Header 1955-05-06 2026-06-05
    2024-06-07
    2024-06-12
    ----------
    """

    assert _parse_release_dates(text) == [pd.Timestamp("2024-06-07").date(), pd.Timestamp("2024-06-12").date()]


def _calendar(tmp_path):
    path = tmp_path / "bls.csv"
    path.write_text(
        "release_date,release_time,release_type,release_name,scheduled,source,source_url,notes\n"
        "2024-06-07,08:30:00,employment_situation,Employment Situation,true,unit_test,https://example.test,known before RTH\n"
        "2024-06-12,08:30:00,cpi,Consumer Price Index,true,unit_test,https://example.test,known before RTH\n",
        encoding="utf-8",
    )
    return path


def _bar(
    timestamp,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    is_rth: bool = True,
):
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
