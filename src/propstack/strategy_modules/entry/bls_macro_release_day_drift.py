from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class BlsMacroReleaseDayDriftEntry:
    name = "bls_macro_release_day_drift"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "unconditional_long")).lower()
        self.event_calendar_csv = str(
            params.get(
                "event_calendar_csv",
                "data/external/bls_macro_release_dates_20110103_20260609.csv",
            )
        )
        self.release_types = _release_types(params.get("release_types", ["employment_situation", "cpi"]))
        self.event_dates = _load_event_dates(self.event_calendar_csv, self.release_types)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.min_session_return_bps = float(params.get("min_session_return_bps", -1000000.0))
        self.max_session_range_bps = float(params.get("max_session_range_bps", 1000000.0))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
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
        release_types = self.event_dates.get(session_date)
        if not release_types:
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
        release_type_text = ",".join(sorted(release_types))
        return Signal(
            direction="long",
            level_type=f"bls_macro_release_day_drift_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(state["high"]),
            sweep_low=float(state["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "release_types": release_type_text,
                "session_return_bps": session_return_bps,
                "session_range_bps": session_range_bps,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "academic_source_key": "kurov_sancetta_strasser_wolfe_2019_macro_news_drift",
                "setup_mode": self.setup_mode,
                "event_calendar_csv": self.event_calendar_csv,
                "configured_release_types": ",".join(sorted(self.release_types)),
                "bls_release_types": release_type_text,
                "bls_signal_session_date": session_date.isoformat(),
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
        if self.setup_mode == "unconditional_long":
            return True
        if self.setup_mode == "momentum_confirmed_long":
            return math.isfinite(session_return_bps) and session_return_bps >= self.min_session_return_bps
        if self.setup_mode == "low_range_long":
            return math.isfinite(session_range_bps) and session_range_bps <= self.max_session_range_bps
        raise ValueError(f"Unsupported setup_mode for bls_macro_release_day_drift: {self.setup_mode}")

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "first_open": None,
                "high": None,
                "low": None,
            },
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


def _load_event_dates(path: str, release_types: set[str]) -> dict[date, set[str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"BLS macro release calendar not found: {path}")
    out: dict[date, set[str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("scheduled", "true")).lower() != "true":
                continue
            release_type = str(row["release_type"]).strip().lower()
            if release_type not in release_types:
                continue
            release_date = date.fromisoformat(str(row["release_date"]))
            out.setdefault(release_date, set()).add(release_type)
    return out


def _release_types(value) -> set[str]:
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    else:
        raw = [str(part).strip() for part in value]
    out = {part.lower() for part in raw if part}
    if not out:
        raise ValueError("release_types must include at least one BLS release type.")
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
