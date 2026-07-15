from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TurnOfYearEffectEntry:
    name = "turn_of_year_effect"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "all_window_long")).lower()
        self.event_calendar_csv = str(
            params.get("event_calendar_csv", "data/external/nyse_turn_of_year_sessions_20110103_20260609.csv")
        )
        self.signal_dates = _load_signal_dates(self.event_calendar_csv, self.setup_mode)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.min_session_return_bps = float(params.get("min_session_return_bps", -1000000.0))
        self.max_session_range_bps = float(params.get("max_session_range_bps", 1000000.0))
        self.stop_pct = float(params.get("stop_pct", 0.002))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self._state(session_date)
        self._update_state(state, bar)
        if state["signaled"]:
            return None
        if session_date not in self.signal_dates:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = self._session_timestamp(timestamp, self.entry_time)
        if bar_close != signal_timestamp:
            return None

        session_return_bps = self._session_return_bps(state, bar)
        session_range_bps = self._session_range_bps(state)
        if not self._passes_setup_filters(session_return_bps, session_range_bps):
            return None

        current_close = float(bar["close"])
        state["signaled"] = True
        return Signal(
            direction="long",
            level_type=f"turn_of_year_effect_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(state["high"]),
            sweep_low=float(state["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "signal_date": session_date.isoformat(),
                "session_return_bps": session_return_bps,
                "session_range_bps": session_range_bps,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "academic_source_key": "szakmary_kiefer_2004_turn_of_year_futures",
                "setup_mode": self.setup_mode,
                "event_calendar_csv": self.event_calendar_csv,
                "turn_of_year_signal_session_date": session_date.isoformat(),
                "session_return_bps": session_return_bps,
                "session_range_bps": session_range_bps,
                "min_session_return_bps": self.min_session_return_bps,
                "max_session_range_bps": self.max_session_range_bps,
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "signal_stop_pct": self.stop_pct,
                "signal_target_r_multiple": self.target_r_multiple,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
                "swept_level": current_close,
                "sweep_timestamp": timestamp,
                "sweep_high": float(state["high"]),
                "sweep_low": float(state["low"]),
                "reclaim_timestamp": signal_timestamp,
            },
        )

    def _passes_setup_filters(self, session_return_bps: float, session_range_bps: float) -> bool:
        if self.setup_mode in {"all_window_long", "december_window_long", "january_window_long"}:
            return True
        if self.setup_mode == "momentum_confirmed_long":
            return math.isfinite(session_return_bps) and session_return_bps >= self.min_session_return_bps
        if self.setup_mode == "low_range_long":
            return math.isfinite(session_range_bps) and session_range_bps <= self.max_session_range_bps
        raise ValueError(f"Unsupported setup_mode for turn_of_year_effect: {self.setup_mode}")

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {"signaled": False, "first_open": None, "high": None, "low": None},
        )

    def _update_state(self, state: dict, bar: pd.Series) -> None:
        open_price = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if open_price is not None and state["first_open"] is None:
            state["first_open"] = open_price
        if high is not None:
            state["high"] = high if state["high"] is None else max(float(state["high"]), high)
        if low is not None:
            state["low"] = low if state["low"] is None else min(float(state["low"]), low)

    def _session_return_bps(self, state: dict, bar: pd.Series) -> float:
        first_open = _finite_float(state.get("first_open"))
        close = _finite_float(bar.get("close"))
        if first_open is None or close is None or first_open <= 0:
            return float("nan")
        return (close / first_open - 1.0) * 10000.0

    def _session_range_bps(self, state: dict) -> float:
        first_open = _finite_float(state.get("first_open"))
        high = _finite_float(state.get("high"))
        low = _finite_float(state.get("low"))
        if first_open is None or high is None or low is None or first_open <= 0:
            return float("nan")
        return (high - low) / first_open * 10000.0

    def _session_timestamp(self, timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
        return timestamp.replace(
            hour=session_time.hour,
            minute=session_time.minute,
            second=session_time.second,
            microsecond=0,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _load_signal_dates(path: str, setup_mode: str) -> set[date]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Turn-of-year calendar not found: {path}")
    out: set[date] = set()
    allowed_periods = {
        "all_window_long": {"december_last5", "january_first2"},
        "december_window_long": {"december_last5"},
        "january_window_long": {"january_first2"},
        "momentum_confirmed_long": {"december_last5", "january_first2"},
        "low_range_long": {"december_last5", "january_first2"},
    }.get(setup_mode)
    if allowed_periods is None:
        allowed_periods = {"december_last5", "january_first2"}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("regular_session", "true")).lower() != "true":
                continue
            if str(row.get("period")) not in allowed_periods:
                continue
            out.add(date.fromisoformat(str(row["signal_date"])))
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
