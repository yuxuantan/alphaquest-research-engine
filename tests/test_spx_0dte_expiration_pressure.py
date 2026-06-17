from __future__ import annotations

from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.spx_0dte_expiration_pressure import Spx0dteExpirationPressureEntry
from tools.build_spx_0dte_calendar import build_spx_0dte_rows


def _bar(timestamp: str, *, open_price: float = 5000.0, close: float = 5001.0, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": max(open_price, close) + 2.0,
            "low": min(open_price, close) - 2.0,
            "close": close,
        }
    )


def _calendar(tmp_path: Path, rows: list[dict]) -> str:
    path = tmp_path / "spx_0dte_calendar.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _calendar_row(
    session_date: str,
    *,
    weekday: int = 1,
    weekday_name: str = "Tuesday",
    is_spx_0dte: str = "true",
    is_full_week_0dte: str = "true",
    is_new_tue_thu_0dte: str = "true",
    is_mwf_0dte: str = "false",
    is_standard_monthly: str = "false",
    is_quarterly_month: str = "false",
) -> dict:
    return {
        "signal_date": session_date,
        "weekday": weekday,
        "weekday_name": weekday_name,
        "is_spx_0dte": is_spx_0dte,
        "is_full_week_0dte": is_full_week_0dte,
        "is_new_tue_thu_0dte": is_new_tue_thu_0dte,
        "is_mwf_0dte": is_mwf_0dte,
        "is_standard_monthly": is_standard_monthly,
        "is_quarterly_month": is_quarterly_month,
    }


def test_calendar_builder_marks_spx_0dte_launch_eras(tmp_path):
    source = tmp_path / "es_sessions.parquet"
    rows = []
    for session_date in [
        "2016-02-22",
        "2016-02-24",
        "2016-08-22",
        "2022-04-19",
        "2022-05-12",
        "2022-05-13",
    ]:
        ts = pd.Timestamp(f"{session_date} 09:30:00")
        rows.append({"timestamp": ts, "session_date": ts.date(), "is_rth": True})
    pd.DataFrame(rows).to_parquet(source, index=False)

    built = {row["signal_date"]: row for row in build_spx_0dte_rows(source)}

    assert built["2016-02-22"]["is_spx_0dte"] == "false"
    assert built["2016-02-24"]["is_mwf_0dte"] == "true"
    assert built["2016-08-22"]["is_mwf_0dte"] == "true"
    assert built["2022-04-19"]["is_new_tue_thu_0dte"] == "true"
    assert built["2022-05-12"]["is_full_week_0dte"] == "true"
    assert built["2022-05-13"]["is_standard_monthly"] == "false"


def test_two_sided_fade_uses_completed_signal_bar(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-11")])
    entry = Spx0dteExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "calendar_bucket": "new_tue_thu",
            "trigger_mode": "fade_move",
            "direction": "two_sided",
            "signal_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_abs_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-06-11 09:30:00", open_price=5000.0, close=5000.0)) is None
    assert entry.on_bar_close(_bar("2024-06-11 09:58:00", open_price=5001.0, close=5002.0)) is None
    signal = entry.on_bar_close(_bar("2024-06-11 09:59:00", open_price=5001.0, close=5002.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["spx_0dte_open_to_signal_ticks"] == 8.0


def test_two_sided_fade_down_move_enters_long(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-13", weekday=3, weekday_name="Thursday")])
    entry = Spx0dteExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "calendar_bucket": "new_tue_thu",
            "trigger_mode": "fade_move",
            "direction": "two_sided",
            "signal_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_abs_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    entry.on_bar_close(_bar("2024-06-13 09:30:00", open_price=5000.0, close=5000.0))
    signal = entry.on_bar_close(_bar("2024-06-13 09:59:00", open_price=4999.0, close=4998.5))

    assert signal is not None
    assert signal.direction == "long"


def test_continue_move_reverses_direction_mapping(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-11")])
    entry = Spx0dteExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "calendar_bucket": "full_week",
            "trigger_mode": "continue_move",
            "direction": "two_sided",
            "signal_time": "10:00:00",
            "bar_interval_minutes": 1,
            "min_abs_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    entry.on_bar_close(_bar("2024-06-11 09:30:00", open_price=5000.0, close=5000.0))
    signal = entry.on_bar_close(_bar("2024-06-11 09:59:00", open_price=5001.0, close=5002.0))

    assert signal is not None
    assert signal.direction == "long"


def test_standard_monthly_excluded_by_default(tmp_path):
    calendar_csv = _calendar(
        tmp_path,
        [
            _calendar_row(
                "2024-06-21",
                weekday=4,
                weekday_name="Friday",
                is_new_tue_thu_0dte="false",
                is_mwf_0dte="true",
                is_standard_monthly="true",
                is_quarterly_month="true",
            )
        ],
    )
    entry = Spx0dteExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "calendar_bucket": "all_available",
            "trigger_mode": "calendar_only",
            "direction": "long",
            "signal_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-06-21 09:59:00")) is None


def test_non_rth_rejects(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-11")])
    entry = Spx0dteExpirationPressureEntry(
        {
            "event_calendar_csv": calendar_csv,
            "calendar_bucket": "full_week",
            "trigger_mode": "calendar_only",
            "direction": "long",
            "signal_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-06-11 09:59:00", is_rth=False)) is None
