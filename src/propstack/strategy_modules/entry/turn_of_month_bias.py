from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TurnOfMonthBiasEntry:
    name = "turn_of_month_bias"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "turn_window")).lower()
        self.signal_time = parse_time(params.get("signal_time", "11:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.first_calendar_days = int(params.get("first_calendar_days", 5))
        self.last_calendar_days = int(params.get("last_calendar_days", 4))
        self.direction = str(params.get("direction", "long")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        if self.direction not in {"long", "short"}:
            raise ValueError("direction must be long or short.")
        if self.first_calendar_days < 0 or self.last_calendar_days < 0:
            raise ValueError("first_calendar_days and last_calendar_days must be non-negative.")

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

        session_date = pd.Timestamp(bar["session_date"])
        calendar_day = int(session_date.day)
        days_to_month_end = int(session_date.days_in_month - session_date.day)
        if not self._eligible(calendar_day, days_to_month_end):
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "carchano_pardo_2011_calendar_anomalies_stock_index_futures",
            "turn_of_month_signal_timestamp": bar_close,
            "turn_of_month_calendar_day": calendar_day,
            "turn_of_month_days_to_month_end": days_to_month_end,
            "turn_of_month_first_calendar_days": self.first_calendar_days,
            "turn_of_month_last_calendar_days": self.last_calendar_days,
            "setup_mode": self.setup_mode,
        }
        return Signal(
            direction=self.direction,
            level_type=f"turn_of_month_bias_{self.setup_mode}_{self.direction}",
            swept_level=float(bar["open"]),
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "calendar_day": calendar_day,
                "days_to_month_end": days_to_month_end,
            },
            report_fields=report_fields,
        )

    def _eligible(self, calendar_day: int, days_to_month_end: int) -> bool:
        in_first = self.first_calendar_days > 0 and calendar_day <= self.first_calendar_days
        in_last = self.last_calendar_days > 0 and days_to_month_end < self.last_calendar_days
        if self.setup_mode in {"turn_window", "expanded_turn_window", "classic_turn_window"}:
            return in_first or in_last
        if self.setup_mode in {"early_month_strength", "first_days_only"}:
            return in_first
        if self.setup_mode in {"month_end_strength", "last_days_only"}:
            return in_last
        raise ValueError(f"Unknown turn-of-month setup_mode: {self.setup_mode}")
