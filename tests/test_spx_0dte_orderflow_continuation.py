from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.spx_0dte_orderflow_continuation import (
    Spx0dteOrderflowContinuationEntry,
)


def test_0dte_orderflow_continuation_requires_completed_aligned_flow(tmp_path):
    entry = Spx0dteOrderflowContinuationEntry(
        _params(tmp_path, bar_interval_minutes=15, flow_mode="large20_imbalance")
    )

    assert entry.on_bar_close(_bar("2024-06-11 09:30", open_=5000.0, close=5002.0, large20_signed=300)) is None
    signal = entry.on_bar_close(
        _bar("2024-06-11 09:45", open_=5002.0, close=5004.0, large20_signed=300)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["source_window_return_ticks"] == 16.0
    assert signal.report_fields["primary_orderflow_imbalance"] == 0.3


def test_0dte_orderflow_continuation_rejects_non_0dte_and_misaligned_flow(tmp_path):
    non_0dte = Spx0dteOrderflowContinuationEntry(
        _params(
            tmp_path,
            rows=[_calendar_row("2024-06-11", is_spx_0dte="false", is_full_week_0dte="false")],
            bar_interval_minutes=15,
        )
    )
    non_0dte.on_bar_close(_bar("2024-06-11 09:30", open_=5000.0, close=5002.0, large20_signed=300))
    assert (
        non_0dte.on_bar_close(_bar("2024-06-11 09:45", open_=5002.0, close=5004.0, large20_signed=300))
        is None
    )

    opposing = Spx0dteOrderflowContinuationEntry(
        _params(tmp_path, bar_interval_minutes=15, flow_mode="large20_imbalance")
    )
    opposing.on_bar_close(_bar("2024-06-11 09:30", open_=5000.0, close=5002.0, large20_signed=-300))
    assert (
        opposing.on_bar_close(_bar("2024-06-11 09:45", open_=5002.0, close=5004.0, large20_signed=-300))
        is None
    )


def test_0dte_orderflow_continuation_excludes_standard_monthly_by_default(tmp_path):
    entry = Spx0dteOrderflowContinuationEntry(
        _params(
            tmp_path,
            rows=[
                _calendar_row(
                    "2024-06-21",
                    weekday=4,
                    weekday_name="Friday",
                    is_mwf_0dte="true",
                    is_new_tue_thu_0dte="false",
                    is_standard_monthly="true",
                    is_quarterly_month="true",
                )
            ],
            bar_interval_minutes=15,
        )
    )
    entry.on_bar_close(_bar("2024-06-21 09:30", open_=5000.0, close=5002.0, large20_signed=300))
    assert entry.on_bar_close(_bar("2024-06-21 09:45", open_=5002.0, close=5004.0, large20_signed=300)) is None


def test_engine_enters_0dte_orderflow_continuation_on_next_bar_open(tmp_path):
    timestamps = pd.date_range("2024-06-11 09:30:00", periods=8, freq="5min", tz="America/New_York")
    closes = [5000.5, 5001.0, 5001.5, 5002.0, 5002.5, 5003.0, 5003.25, 5003.5]
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [5000.0, 5000.5, 5001.0, 5001.5, 5002.0, 5002.5, 5003.0, 5003.25],
            "high": [close + 0.5 for close in closes],
            "low": [close - 0.75 for close in closes],
            "close": closes,
            "volume": [1000] * len(timestamps),
            "signed_volume": [200] * len(timestamps),
            "large10_signed_volume": [250] * len(timestamps),
            "large10_volume": [500] * len(timestamps),
            "large20_signed_volume": [300] * len(timestamps),
            "large20_volume": [500] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_spx_0dte_orderflow_continuation",
        "timeframe": "5m",
        "strategy": {
            "entry": {"module": "spx_0dte_orderflow_continuation", "params": _params(tmp_path, bar_interval_minutes=5)},
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01, "round_to_tick": True}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:10:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:10:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["spx_0dte_signal_timestamp"]) == "2024-06-11 10:00:00-04:00"
    assert str(trade["entry_timestamp"]) == "2024-06-11 10:00:00-04:00"


def _params(tmp_path: Path, *, rows: list[dict] | None = None, **overrides):
    calendar_csv = _calendar(tmp_path, rows or [_calendar_row("2024-06-11")])
    params = {
        "setup_mode": "unit_0dte_orderflow_continuation",
        "calendar_bucket": "all_available",
        "direction_mode": "two_sided_continuation",
        "flow_mode": "large20_imbalance",
        "source_start": "09:30:00",
        "signal_time": "10:00:00",
        "flatten_time": "10:10:00",
        "bar_interval_minutes": 5,
        "tick_size": 0.25,
        "min_abs_move_ticks": 8,
        "min_orderflow_imbalance": 0.20,
        "event_calendar_csv": calendar_csv,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


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


def _bar(
    timestamp: str,
    *,
    open_: float,
    close: float,
    large20_signed: float,
    volume: float = 1000,
    large20_volume: float = 1000,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": open_,
            "high": max(open_, close) + 0.5,
            "low": min(open_, close) - 0.5,
            "close": close,
            "volume": volume,
            "signed_volume": large20_signed,
            "large10_signed_volume": large20_signed,
            "large10_volume": large20_volume,
            "large20_signed_volume": large20_signed,
            "large20_volume": large20_volume,
        }
    )
