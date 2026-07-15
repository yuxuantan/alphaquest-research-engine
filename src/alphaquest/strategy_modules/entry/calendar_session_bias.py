from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class CalendarSessionBiasEntry:
    name = "calendar_session_bias"
    required_columns = frozenset({"is_rth"})
    decision_timing = "bar_close"
    warmup_bars = 0

    def __init__(self, params: dict):
        self.params = params
        self.signal_time = parse_time(params.get("signal_time", "09:35:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.weekday_directions = _weekday_directions(params.get("weekday_directions", {2: "long", 3: "long"}))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() != self.signal_time:
            return None

        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        weekday = int(timestamp.weekday())
        direction = self.weekday_directions.get(weekday)
        if direction not in {"long", "short"}:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "floros_salvador_2014_calendar_anomalies_stock_index_futures",
            "calendar_signal_timestamp": bar_close,
            "calendar_weekday": weekday,
            "calendar_direction": direction,
            "calendar_weekday_directions": dict(self.weekday_directions),
            "setup_mode": self.params.get("setup_mode", "weekday_session_bias"),
        }
        return Signal(
            direction=direction,
            level_type=f"calendar_session_bias_{weekday}_{direction}",
            swept_level=float(bar["open"]),
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "calendar_weekday": weekday,
            },
            report_fields=report_fields,
        )


def _weekday_directions(value) -> dict[int, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("weekday_directions must be a mapping of weekday number to long/short.")
    out = {}
    for key, direction in value.items():
        weekday = int(key)
        normalized = str(direction).lower()
        if weekday < 0 or weekday > 4:
            raise ValueError("weekday_directions keys must be Monday=0 through Friday=4.")
        if normalized not in {"long", "short"}:
            raise ValueError("weekday_directions values must be long or short.")
        out[weekday] = normalized
    return out
