from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class MonthlyOpexPressureEntry:
    name = "monthly_opex_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "monthly_opex_pressure")).lower()
        self.signal_type = str(params.get("signal_type", "opex_session")).lower()
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.direction = _direction(params.get("direction", "long"))
        self.include_quarterly_months = _bool(params.get("include_quarterly_months", False))
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

        event_row = self.calendar_by_date.get(session_date)
        if event_row is None:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "stoll_whaley_1987_ni_pearson_poteshman_2005_monthly_opex",
            "setup_mode": self.setup_mode,
            "monthly_opex_signal_timestamp": signal_timestamp,
            "monthly_opex_session_date": session_date.isoformat(),
            "monthly_opex_date": event_row["opex_date"],
            "monthly_opex_calendar_month": event_row["calendar_month"],
            "monthly_opex_signal_type": event_row["signal_type"],
            "monthly_opex_quarterly_month_excluded": not self.include_quarterly_months,
            "monthly_opex_is_quarterly_month": event_row["is_quarterly_month"],
            "monthly_opex_direction": self.direction,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=self.direction,
            level_type=f"monthly_opex_pressure_{self.setup_mode}_{self.signal_type}",
            swept_level=float(bar["open"]),
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "signal_type": self.signal_type,
                "monthly_opex_date": event_row["opex_date"],
                "calendar_month": event_row["calendar_month"],
                "direction": self.direction,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _load_calendar(self, path: Path) -> dict[date, dict]:
        if not path:
            raise ValueError("event_calendar_csv is required.")
        if not path.exists():
            raise FileNotFoundError(f"Monthly OPEX calendar does not exist: {path}")

        df = pd.read_csv(path)
        required = {"signal_date", "opex_date", "calendar_month", "signal_type", "is_quarterly_month"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Monthly OPEX calendar missing column(s): {sorted(missing)}")

        df["signal_type"] = df["signal_type"].astype(str).str.lower()
        df["is_quarterly_month"] = df["is_quarterly_month"].map(_bool)
        df = df[df["signal_type"] == self.signal_type]
        if not self.include_quarterly_months:
            df = df[~df["is_quarterly_month"]]

        calendar: dict[date, dict] = {}
        for row in df.to_dict("records"):
            signal_date = pd.Timestamp(row["signal_date"]).date()
            if signal_date in calendar:
                raise ValueError(f"Duplicate monthly OPEX signal date after filtering: {signal_date}")
            calendar[signal_date] = {
                "signal_date": signal_date.isoformat(),
                "opex_date": str(row["opex_date"]),
                "calendar_month": str(row["calendar_month"]),
                "signal_type": str(row["signal_type"]),
                "is_quarterly_month": bool(row["is_quarterly_month"]),
            }
        return calendar

    def _validate(self) -> None:
        if self.signal_type not in {"previous_regular_session", "opex_session", "next_regular_session"}:
            raise ValueError(
                "signal_type must be one of previous_regular_session, opex_session, or next_regular_session."
            )
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")


def _direction(value) -> str:
    out = str(value).lower()
    if out not in {"long", "short"}:
        raise ValueError("direction must be long or short.")
    return out


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()
