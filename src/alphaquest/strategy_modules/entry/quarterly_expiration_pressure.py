from __future__ import annotations

from datetime import date

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class QuarterlyExpirationPressureEntry:
    name = "quarterly_expiration_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "expiration_friday")).lower()
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.day_offset = int(params.get("day_offset", _default_offset(self.setup_mode)))
        self.direction = _direction(params.get("direction", _default_direction(self.setup_mode)))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False})
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.signal_time.hour,
            minute=self.signal_time.minute,
            second=self.signal_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        expiration_date = _quarterly_expiration_date(session_date.year, session_date.month)
        if expiration_date is None:
            expiration_date = _nearest_relevant_expiration(session_date)
        target_date = expiration_date + pd.Timedelta(days=self.day_offset)
        if session_date != target_date.date():
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "stoll_whaley_1987_expiration_day_effects",
            "setup_mode": self.setup_mode,
            "expiration_signal_timestamp": signal_timestamp,
            "expiration_session_date": session_date.isoformat(),
            "quarterly_expiration_date": expiration_date.date().isoformat(),
            "expiration_day_offset": self.day_offset,
            "expiration_direction": self.direction,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=self.direction,
            level_type=f"quarterly_expiration_pressure_{self.setup_mode}",
            swept_level=float(bar["open"]),
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "quarterly_expiration_date": expiration_date.date().isoformat(),
                "day_offset": self.day_offset,
                "direction": self.direction,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _quarterly_expiration_date(year: int, month: int) -> pd.Timestamp | None:
    if month not in {3, 6, 9, 12}:
        return None
    first = pd.Timestamp(year=year, month=month, day=1)
    days_until_friday = (4 - first.weekday()) % 7
    first_friday = first + pd.Timedelta(days=days_until_friday)
    return first_friday + pd.Timedelta(days=14)


def _nearest_relevant_expiration(session_date: date) -> pd.Timestamp:
    ts = pd.Timestamp(session_date)
    candidates = []
    for year in {ts.year - 1, ts.year, ts.year + 1}:
        for month in (3, 6, 9, 12):
            candidates.append(_quarterly_expiration_date(year, month))
    return min(candidates, key=lambda item: abs((item - ts).days))


def _default_offset(setup_mode: str) -> int:
    if "monday_prior" in setup_mode:
        return -4
    if "thursday_prior" in setup_mode:
        return -1
    if "monday_after" in setup_mode:
        return 3
    return 0


def _default_direction(setup_mode: str) -> str:
    if "short" in setup_mode:
        return "short"
    return "long"


def _direction(value) -> str:
    out = str(value).lower()
    if out not in {"long", "short"}:
        raise ValueError("direction must be long or short.")
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()
