from __future__ import annotations

from datetime import date
from pathlib import Path
import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class Spx0dteExpirationPressureEntry:
    name = "spx_0dte_expiration_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "spx_0dte_expiration_pressure")).lower()
        self.calendar_bucket = str(params.get("calendar_bucket", "full_week")).lower()
        self.trigger_mode = str(params.get("trigger_mode", "fade_move")).lower()
        self.direction = str(params.get("direction", "two_sided")).lower()
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_abs_move_ticks = float(params.get("min_abs_move_ticks", 8))
        self.exclude_standard_monthly = _bool(params.get("exclude_standard_monthly", True))
        self.event_calendar_csv = Path(str(params.get("event_calendar_csv", "")))
        self.calendar_by_date = self._load_calendar(self.event_calendar_csv)
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False, "session_open": None})
        if state["session_open"] is None:
            state["session_open"] = _finite_float(bar.get("open"))
        if state["signaled"]:
            return None

        row = self.calendar_by_date.get(session_date)
        if row is None or not self._calendar_row_matches(row):
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

        session_open = _finite_float(state["session_open"])
        signal_close = _finite_float(bar.get("close"))
        if session_open is None or signal_close is None:
            return None

        open_to_signal_ticks = (signal_close - session_open) / self.tick_size
        direction = self._direction_from_move(open_to_signal_ticks)
        if direction is None:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "cboe_spx_0dte_expiration_pressure",
            "setup_mode": self.setup_mode,
            "spx_0dte_signal_timestamp": signal_timestamp,
            "spx_0dte_session_date": session_date.isoformat(),
            "spx_0dte_weekday": row["weekday"],
            "spx_0dte_weekday_name": row["weekday_name"],
            "spx_0dte_calendar_bucket": self.calendar_bucket,
            "spx_0dte_trigger_mode": self.trigger_mode,
            "spx_0dte_direction": direction,
            "spx_0dte_session_open": session_open,
            "spx_0dte_signal_close": signal_close,
            "spx_0dte_open_to_signal_ticks": open_to_signal_ticks,
            "spx_0dte_min_abs_move_ticks": self.min_abs_move_ticks,
            "spx_0dte_exclude_standard_monthly": self.exclude_standard_monthly,
            "spx_0dte_is_standard_monthly": row["is_standard_monthly"],
            "spx_0dte_is_quarterly_month": row["is_quarterly_month"],
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"spx_0dte_{self.calendar_bucket}_{self.trigger_mode}",
            swept_level=session_open,
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "calendar_bucket": self.calendar_bucket,
                "trigger_mode": self.trigger_mode,
                "open_to_signal_ticks": open_to_signal_ticks,
                "direction": direction,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction_from_move(self, open_to_signal_ticks: float) -> str | None:
        if not math.isfinite(open_to_signal_ticks):
            return None
        threshold = self.min_abs_move_ticks
        if self.trigger_mode == "calendar_only":
            return None if self.direction == "two_sided" else self.direction
        if self.trigger_mode == "fade_move":
            if self.direction == "long":
                return "long" if open_to_signal_ticks <= -threshold else None
            if self.direction == "short":
                return "short" if open_to_signal_ticks >= threshold else None
            if open_to_signal_ticks <= -threshold:
                return "long"
            if open_to_signal_ticks >= threshold:
                return "short"
            return None
        if self.trigger_mode == "continue_move":
            if self.direction == "long":
                return "long" if open_to_signal_ticks >= threshold else None
            if self.direction == "short":
                return "short" if open_to_signal_ticks <= -threshold else None
            if open_to_signal_ticks >= threshold:
                return "long"
            if open_to_signal_ticks <= -threshold:
                return "short"
            return None
        raise ValueError("trigger_mode must be calendar_only, fade_move, or continue_move.")

    def _calendar_row_matches(self, row: dict) -> bool:
        if self.exclude_standard_monthly and bool(row["is_standard_monthly"]):
            return False
        if self.calendar_bucket == "full_week":
            return bool(row["is_full_week_0dte"])
        if self.calendar_bucket == "new_tue_thu":
            return bool(row["is_new_tue_thu_0dte"])
        if self.calendar_bucket == "mon_wed_fri":
            return bool(row["is_mwf_0dte"])
        if self.calendar_bucket == "all_available":
            return bool(row["is_spx_0dte"])
        raise ValueError("calendar_bucket must be full_week, new_tue_thu, mon_wed_fri, or all_available.")

    def _load_calendar(self, path: Path) -> dict[date, dict]:
        if not path:
            raise ValueError("event_calendar_csv is required.")
        if not path.exists():
            raise FileNotFoundError(f"SPX 0DTE calendar does not exist: {path}")

        df = pd.read_csv(path)
        required = {
            "signal_date",
            "weekday",
            "weekday_name",
            "is_spx_0dte",
            "is_full_week_0dte",
            "is_new_tue_thu_0dte",
            "is_mwf_0dte",
            "is_standard_monthly",
            "is_quarterly_month",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"SPX 0DTE calendar missing column(s): {sorted(missing)}")

        calendar: dict[date, dict] = {}
        for raw in df.to_dict("records"):
            signal_date = pd.Timestamp(raw["signal_date"]).date()
            if signal_date in calendar:
                raise ValueError(f"Duplicate SPX 0DTE signal date: {signal_date}")
            calendar[signal_date] = {
                "signal_date": signal_date.isoformat(),
                "weekday": int(raw["weekday"]),
                "weekday_name": str(raw["weekday_name"]),
                "is_spx_0dte": _bool(raw["is_spx_0dte"]),
                "is_full_week_0dte": _bool(raw["is_full_week_0dte"]),
                "is_new_tue_thu_0dte": _bool(raw["is_new_tue_thu_0dte"]),
                "is_mwf_0dte": _bool(raw["is_mwf_0dte"]),
                "is_standard_monthly": _bool(raw["is_standard_monthly"]),
                "is_quarterly_month": _bool(raw["is_quarterly_month"]),
            }
        return calendar

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.min_abs_move_ticks < 0:
            raise ValueError("min_abs_move_ticks must be non-negative.")
        if self.direction not in {"long", "short", "two_sided"}:
            raise ValueError("direction must be long, short, or two_sided.")


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


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
