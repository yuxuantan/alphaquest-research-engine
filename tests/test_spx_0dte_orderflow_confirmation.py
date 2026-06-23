from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.spx_0dte_orderflow_confirmation import (
    Spx0dteOrderflowConfirmationEntry,
)


def test_spx_0dte_orderflow_continuation_requires_aligned_completed_flow(tmp_path):
    entry = Spx0dteOrderflowConfirmationEntry(_params(tmp_path))
    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 14:29",
            open_=125.0,
            close=125.0,
            signed_volume=200,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["spx_0dte_open_to_signal_ticks"] == 100.0
    assert signal.report_fields["primary_orderflow_imbalance"] == 0.2
    assert signal.report_fields["signed_directional_orderflow_imbalance"] == 0.2
    assert signal.report_fields["spx_0dte_orderflow_window_end"] == pd.Timestamp("2024-01-03 14:30")


def test_spx_0dte_orderflow_rejects_wrong_signed_flow(tmp_path):
    entry = Spx0dteOrderflowConfirmationEntry(_params(tmp_path))
    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.0))

    signal = entry.on_bar_close(
        _bar("2024-01-03 14:29", open_=125.0, close=125.0, signed_volume=-200, volume=1000)
    )

    assert signal is None


def test_spx_0dte_orderflow_inherits_standard_monthly_exclusion(tmp_path):
    entry = Spx0dteOrderflowConfirmationEntry(
        _params(tmp_path, session_date="2024-01-19", is_standard_monthly=True)
    )
    entry.on_bar_close(_bar("2024-01-19 09:30", open_=100.0, close=100.0))

    signal = entry.on_bar_close(
        _bar("2024-01-19 14:29", open_=125.0, close=125.0, signed_volume=200, volume=1000)
    )

    assert signal is None


def _params(tmp_path: Path, *, session_date="2024-01-03", is_standard_monthly=False) -> dict:
    return {
        "setup_mode": "unit_all_available_1430_signed60_continue",
        "event_calendar_csv": str(_calendar(tmp_path, session_date, is_standard_monthly)),
        "calendar_bucket": "all_available",
        "trigger_mode": "continue_move",
        "direction": "two_sided",
        "signal_time": "14:30:00",
        "flatten_time": "15:55:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "min_abs_move_ticks": 80,
        "exclude_standard_monthly": True,
        "orderflow_window_minutes": 60,
        "flow_mode": "signed_imbalance",
        "min_orderflow_imbalance": 0.05,
    }


def _calendar(tmp_path: Path, session_date: str, is_standard_monthly: bool) -> Path:
    path = tmp_path / "spx_0dte_calendar.csv"
    row = {
        "signal_date": session_date,
        "weekday": pd.Timestamp(session_date).weekday(),
        "weekday_name": pd.Timestamp(session_date).day_name(),
        "is_spx_0dte": True,
        "is_full_week_0dte": True,
        "is_new_tue_thu_0dte": False,
        "is_mwf_0dte": True,
        "is_standard_monthly": is_standard_monthly,
        "is_quarterly_month": False,
    }
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def _bar(timestamp: str, *, open_: float, close: float, signed_volume=0, volume=1000):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": open_,
            "high": max(open_, close),
            "low": min(open_, close),
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large20_volume": 100,
            "large20_signed_volume": signed_volume / 10,
        }
    )
