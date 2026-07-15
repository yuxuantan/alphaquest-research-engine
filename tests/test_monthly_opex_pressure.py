from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.monthly_opex_pressure import MonthlyOpexPressureEntry
from tools.build_nyse_monthly_opex_calendar import monthly_opex_rows


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
    path = tmp_path / "monthly_opex.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_calendar_builder_marks_nonquarterly_and_quarterly_months():
    rows = monthly_opex_rows(pd.Timestamp("2024-01-01").date(), pd.Timestamp("2024-04-30").date())

    nonquarterly = [
        row
        for row in rows
        if row["signal_type"] == "opex_session" and row["is_quarterly_month"] == "false"
    ]
    quarterly = [
        row
        for row in rows
        if row["signal_type"] == "opex_session" and row["is_quarterly_month"] == "true"
    ]

    assert {row["signal_date"] for row in nonquarterly} == {"2024-01-19", "2024-02-16", "2024-04-19"}
    assert {row["signal_date"] for row in quarterly} == {"2024-03-15"}


def test_nonquarterly_opex_signal_on_completed_bar_close(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-01-19",
                "opex_date": "2024-01-19",
                "calendar_month": "2024-01",
                "signal_type": "opex_session",
                "is_quarterly_month": "false",
            }
        ],
    )
    entry = MonthlyOpexPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "signal_type": "opex_session",
            "signal_time": "10:00:00",
            "bar_interval_minutes": 1,
            "direction": "short",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-19 09:58:00")) is None
    signal = entry.on_bar_close(_bar("2024-01-19 09:59:00"))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["monthly_opex_date"] == "2024-01-19"
    assert signal.report_fields["monthly_opex_quarterly_month_excluded"] is True


def test_quarterly_month_is_excluded_by_default(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-03-15",
                "opex_date": "2024-03-15",
                "calendar_month": "2024-03",
                "signal_type": "opex_session",
                "is_quarterly_month": "true",
            }
        ],
    )
    entry = MonthlyOpexPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "signal_type": "opex_session",
            "signal_time": "10:00:00",
            "direction": "long",
        }
    )

    assert entry.on_bar_close(_bar("2024-03-15 09:59:00")) is None


def test_next_regular_session_signal_type(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-01-22",
                "opex_date": "2024-01-19",
                "calendar_month": "2024-01",
                "signal_type": "next_regular_session",
                "is_quarterly_month": "false",
            }
        ],
    )
    entry = MonthlyOpexPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "signal_type": "next_regular_session",
            "signal_time": "10:00:00",
            "direction": "long",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-22 09:59:00"))

    assert signal is not None
    assert signal.report_fields["monthly_opex_signal_type"] == "next_regular_session"


def test_non_rth_rejects(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            {
                "signal_date": "2024-01-19",
                "opex_date": "2024-01-19",
                "calendar_month": "2024-01",
                "signal_type": "opex_session",
                "is_quarterly_month": "false",
            }
        ],
    )
    entry = MonthlyOpexPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "signal_type": "opex_session",
            "signal_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-19 09:59:00", is_rth=False)) is None
