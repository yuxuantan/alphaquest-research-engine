from __future__ import annotations

from datetime import date

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class HalloweenSeasonalPremiumEntry:
    name = "halloween_seasonal_premium"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "winter_long")).lower()
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.active_months = _months(params.get("active_months", _default_months(self.setup_mode)))
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
        if session_date.month not in self.active_months:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "bouman_jacobsen_2002_halloween_indicator",
            "setup_mode": self.setup_mode,
            "seasonal_signal_timestamp": signal_timestamp,
            "seasonal_session_date": session_date.isoformat(),
            "seasonal_month": session_date.month,
            "seasonal_active_months": list(self.active_months),
            "seasonal_direction": self.direction,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=self.direction,
            level_type=f"halloween_seasonal_premium_{self.setup_mode}",
            swept_level=float(bar["open"]),
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "seasonal_month": session_date.month,
                "active_months": list(self.active_months),
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


def _default_months(setup_mode: str) -> list[int]:
    if setup_mode.startswith("winter"):
        return [11, 12, 1, 2, 3, 4]
    if setup_mode.startswith("summer"):
        return [5, 6, 7, 8, 9, 10]
    raise ValueError(f"Unsupported setup_mode for halloween_seasonal_premium: {setup_mode}")


def _default_direction(setup_mode: str) -> str:
    if setup_mode.startswith("winter"):
        return "long"
    if setup_mode.startswith("summer"):
        return "short"
    raise ValueError(f"Unsupported setup_mode for halloween_seasonal_premium: {setup_mode}")


def _months(value) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("active_months must be a non-empty list of month numbers.")
    out = []
    for item in value:
        month = int(item)
        if month < 1 or month > 12:
            raise ValueError("active_months values must be in 1..12.")
        out.append(month)
    return tuple(out)


def _direction(value) -> str:
    out = str(value).lower()
    if out not in {"long", "short"}:
        raise ValueError("direction must be long or short.")
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()
