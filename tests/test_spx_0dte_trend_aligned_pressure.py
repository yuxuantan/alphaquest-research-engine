from __future__ import annotations

from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.spx_0dte_trend_aligned_pressure import (
    Spx0dteTrendAlignedPressureEntry,
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


def _bars(session_date: str, *, end_time: str = "13:29:00", slope: float = 0.05) -> list[pd.Series]:
    start = pd.Timestamp(f"{session_date} 09:30:00")
    end = pd.Timestamp(f"{session_date} {end_time}")
    rows = []
    for idx, ts in enumerate(pd.date_range(start, end, freq="1min")):
        base = 5000.0 + idx * slope
        rows.append(
            pd.Series(
                {
                    "timestamp": ts,
                    "session_date": ts.date(),
                    "is_rth": True,
                    "open": base,
                    "high": base + 0.20,
                    "low": base - 0.20,
                    "close": base + (0.10 if slope >= 0 else -0.10),
                }
            )
        )
    return rows


def _entry(calendar_csv: str, **params) -> Spx0dteTrendAlignedPressureEntry:
    base = {
        "event_calendar_csv": calendar_csv,
        "calendar_bucket": "full_week",
        "trigger_mode": "calendar_only",
        "direction": "two_sided",
        "signal_time": "13:30:00",
        "bar_interval_minutes": 1,
        "trend_short_minutes": 30,
        "trend_long_minutes": 120,
        "tick_size": 0.25,
        "max_trades_per_day": 1,
    }
    base.update(params)
    return Spx0dteTrendAlignedPressureEntry(base)


def _feed(entry: Spx0dteTrendAlignedPressureEntry, bars: list[pd.Series]):
    signal = None
    for bar in bars:
        maybe = entry.on_bar_close(bar)
        if maybe is not None:
            signal = maybe
    return signal


def test_calendar_only_two_sided_returns_long_when_30m_and_120m_trends_are_up(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-11")])
    entry = _entry(calendar_csv)

    signal = _feed(entry, _bars("2024-06-11", slope=0.05))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["trend_aligned_direction"] == "long"
    assert signal.report_fields["trend_short_state"] == "up"
    assert signal.report_fields["trend_long_state"] == "up"
    assert signal.report_fields["spx_0dte_signal_timestamp"] == pd.Timestamp("2024-06-11 13:30:00")


def test_calendar_only_two_sided_returns_short_when_30m_and_120m_trends_are_down(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-13", weekday=3, weekday_name="Thursday")])
    entry = _entry(calendar_csv)

    signal = _feed(entry, _bars("2024-06-13", slope=-0.05))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["trend_aligned_direction"] == "short"
    assert signal.report_fields["trend_short_state"] == "down"
    assert signal.report_fields["trend_long_state"] == "down"


def test_returns_none_when_long_trend_window_has_insufficient_completed_history(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-11")])
    entry = _entry(calendar_csv, signal_time="11:30:00")

    signal = _feed(entry, _bars("2024-06-11", end_time="11:29:00", slope=0.05))

    assert signal is None


def test_continue_move_requires_open_to_signal_move_in_same_direction_as_trend(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-11")])
    entry = _entry(
        calendar_csv,
        trigger_mode="continue_move",
        min_abs_move_ticks=10000,
    )

    signal = _feed(entry, _bars("2024-06-11", slope=0.05))

    assert signal is None


def test_continue_move_accepts_downtrend_when_open_to_signal_move_is_negative(tmp_path):
    calendar_csv = _calendar(tmp_path, [_calendar_row("2024-06-13", weekday=3, weekday_name="Thursday")])
    entry = _entry(
        calendar_csv,
        trigger_mode="continue_move",
        min_abs_move_ticks=16,
    )

    signal = _feed(entry, _bars("2024-06-13", slope=-0.05))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["spx_0dte_open_to_signal_ticks"] < -16
