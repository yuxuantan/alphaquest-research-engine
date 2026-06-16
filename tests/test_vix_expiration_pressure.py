from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.vix_expiration_pressure import VixExpirationPressureEntry
from tools.build_vix_expiration_calendar import vix_expiration_rows


def _bar(timestamp: str, *, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 5000.0,
            "high": 5005.0,
            "low": 4995.0,
            "close": 5001.0,
        }
    )


def _calendar(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "vix_expiration.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_calendar_builder_standard_and_good_friday_adjusted_dates():
    rows = vix_expiration_rows(pd.Timestamp("2024-01-01").date(), pd.Timestamp("2025-04-30").date())
    vix_sessions = {
        row["calendar_month"]: row
        for row in rows
        if row["signal_type"] == "vix_expiration_session"
    }

    assert vix_sessions["2024-01"]["signal_date"] == "2024-01-17"
    assert vix_sessions["2024-01"]["spx_reference_expiration_date"] == "2024-02-16"
    assert vix_sessions["2025-03"]["signal_date"] == "2025-03-18"
    assert vix_sessions["2025-03"]["spx_reference_expiration_date"] == "2025-04-17"


def test_vix_expiration_signal_on_completed_bar_close(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-01-17",
                "vix_expiration_date": "2024-01-17",
                "spx_reference_expiration_date": "2024-02-16",
                "calendar_month": "2024-01",
                "signal_type": "vix_expiration_session",
            }
        ],
    )
    entry = VixExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "signal_type": "vix_expiration_session",
            "signal_time": "10:00:00",
            "bar_interval_minutes": 1,
            "direction": "long",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-17 09:58:00")) is None
    signal = entry.on_bar_close(_bar("2024-01-17 09:59:00"))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["vix_expiration_date"] == "2024-01-17"
    assert signal.report_fields["spx_reference_expiration_date"] == "2024-02-16"


def test_previous_regular_session_signal_type(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-01-16",
                "vix_expiration_date": "2024-01-17",
                "spx_reference_expiration_date": "2024-02-16",
                "calendar_month": "2024-01",
                "signal_type": "previous_regular_session",
            }
        ],
    )
    entry = VixExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "signal_type": "previous_regular_session",
            "signal_time": "15:00:00",
            "direction": "short",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-16 14:59:00"))

    assert signal is not None
    assert signal.report_fields["vix_expiration_signal_type"] == "previous_regular_session"
    assert signal.direction == "short"


def test_non_event_and_non_rth_reject(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-01-17",
                "vix_expiration_date": "2024-01-17",
                "spx_reference_expiration_date": "2024-02-16",
                "calendar_month": "2024-01",
                "signal_type": "vix_expiration_session",
            }
        ],
    )
    entry = VixExpirationPressureEntry(
        {"event_calendar_csv": calendar_csv, "signal_type": "vix_expiration_session", "signal_time": "10:00:00"}
    )

    assert entry.on_bar_close(_bar("2024-01-18 09:59:00")) is None
    assert entry.on_bar_close(_bar("2024-01-17 09:59:00", is_rth=False)) is None
