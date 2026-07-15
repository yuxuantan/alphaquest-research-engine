from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class VixExpirationPressureEntry:
    name = "vix_expiration_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "vix_expiration_pressure")).lower()
        self.signal_type = str(params.get("signal_type", "vix_expiration_session")).lower()
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.direction = _direction(params.get("direction", "long"))
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
            "academic_source_key": "griffin_shams_2018_vix_settlement_pressure",
            "setup_mode": self.setup_mode,
            "vix_expiration_signal_timestamp": signal_timestamp,
            "vix_expiration_session_date": session_date.isoformat(),
            "vix_expiration_date": event_row["vix_expiration_date"],
            "spx_reference_expiration_date": event_row["spx_reference_expiration_date"],
            "vix_expiration_calendar_month": event_row["calendar_month"],
            "vix_expiration_signal_type": event_row["signal_type"],
            "vix_expiration_direction": self.direction,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=self.direction,
            level_type=f"vix_expiration_pressure_{self.setup_mode}_{self.signal_type}",
            swept_level=float(bar["open"]),
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "signal_type": self.signal_type,
                "vix_expiration_date": event_row["vix_expiration_date"],
                "spx_reference_expiration_date": event_row["spx_reference_expiration_date"],
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
            raise FileNotFoundError(f"VIX expiration calendar does not exist: {path}")

        df = pd.read_csv(path)
        required = {
            "signal_date",
            "vix_expiration_date",
            "spx_reference_expiration_date",
            "calendar_month",
            "signal_type",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"VIX expiration calendar missing column(s): {sorted(missing)}")

        df["signal_type"] = df["signal_type"].astype(str).str.lower()
        df = df[df["signal_type"] == self.signal_type]

        calendar: dict[date, dict] = {}
        for row in df.to_dict("records"):
            signal_date = pd.Timestamp(row["signal_date"]).date()
            if signal_date in calendar:
                raise ValueError(f"Duplicate VIX expiration signal date after filtering: {signal_date}")
            calendar[signal_date] = {
                "signal_date": signal_date.isoformat(),
                "vix_expiration_date": str(row["vix_expiration_date"]),
                "spx_reference_expiration_date": str(row["spx_reference_expiration_date"]),
                "calendar_month": str(row["calendar_month"]),
                "signal_type": str(row["signal_type"]),
            }
        return calendar

    def _validate(self) -> None:
        if self.signal_type not in {"previous_regular_session", "vix_expiration_session", "next_regular_session"}:
            raise ValueError(
                "signal_type must be one of previous_regular_session, vix_expiration_session, or next_regular_session."
            )
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")


def _direction(value) -> str:
    out = str(value).lower()
    if out not in {"long", "short"}:
        raise ValueError("direction must be long or short.")
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()
