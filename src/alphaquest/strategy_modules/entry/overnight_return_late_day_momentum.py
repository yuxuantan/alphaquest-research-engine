from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class OvernightReturnLateDayMomentumEntry:
    name = "overnight_return_late_day_momentum"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "overnight_sign_close_continuation")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.first_window_minutes = float(params.get("first_window_minutes", 30))
        self.last_window_start = parse_time(params.get("last_window_start", "15:30:00"))
        self.penultimate_window_minutes = float(params.get("penultimate_window_minutes", 30))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_overnight_return_ticks = float(params.get("min_overnight_return_ticks", 0))
        self.min_opening_reversal_ticks = float(params.get("min_opening_reversal_ticks", 0))
        self.min_penultimate_return_ticks = float(params.get("min_penultimate_return_ticks", 0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "first_window": None,
                "penultimate_window": None,
                "signaled": False,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        first_start = self._session_timestamp(timestamp, self.rth_start)
        first_end = first_start + pd.Timedelta(minutes=self.first_window_minutes)
        bar_close = self._bar_close_timestamp(timestamp)
        if timestamp >= first_start and bar_close <= first_end:
            state["first_window"] = self._aggregate_bar(state["first_window"], bar, first_start, first_end)

        last_start = self._session_timestamp(timestamp, self.last_window_start)
        penultimate_start = last_start - pd.Timedelta(minutes=self.penultimate_window_minutes)
        if timestamp >= penultimate_start and bar_close <= last_start:
            state["penultimate_window"] = self._aggregate_bar(
                state["penultimate_window"],
                bar,
                penultimate_start,
                last_start,
            )

        if bar_close != last_start:
            return None

        signal = self._signal(bar, state, last_start)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _signal(self, bar: pd.Series, state: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        first = state.get("first_window")
        if not first or not self._window_complete(first, self.first_window_minutes):
            return None

        prev_close = _finite_float(first.get("prev_rth_close"))
        if prev_close is None:
            return None

        rth_open = float(first["open"])
        first_close = float(first["close"])
        overnight_return_points = rth_open - prev_close
        overnight_return_ticks = overnight_return_points / self.tick_size
        if abs(overnight_return_ticks) < self.min_overnight_return_ticks:
            return None

        direction = "long" if overnight_return_points > 0 else "short" if overnight_return_points < 0 else None
        if direction is None:
            return None
        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None

        first_window_return_points = first_close - rth_open
        first_window_return_ticks = first_window_return_points / self.tick_size
        if self.setup_mode == "opening_reversal_confirmed":
            if abs(first_window_return_ticks) < self.min_opening_reversal_ticks:
                return None
            if (direction == "long" and first_window_return_points >= 0) or (
                direction == "short" and first_window_return_points <= 0
            ):
                return None

        penultimate = state.get("penultimate_window")
        penultimate_return_points = None
        penultimate_return_ticks = None
        if self.setup_mode == "overnight_penultimate_alignment":
            if not penultimate or not self._window_complete(penultimate, self.penultimate_window_minutes):
                return None
            penultimate_return_points = float(penultimate["close"]) - float(penultimate["open"])
            penultimate_return_ticks = penultimate_return_points / self.tick_size
            if abs(penultimate_return_ticks) < self.min_penultimate_return_ticks:
                return None
            if (direction == "long" and penultimate_return_points <= 0) or (
                direction == "short" and penultimate_return_points >= 0
            ):
                return None

        signal_bar_high = float(bar["high"])
        signal_bar_low = float(bar["low"])
        report_fields = {
            "academic_source_key": "liu_tse_2017_overnight_returns_indexes",
            "setup_mode": self.setup_mode,
            "prev_rth_close": prev_close,
            "rth_open": rth_open,
            "overnight_return_points": overnight_return_points,
            "overnight_return_ticks": overnight_return_ticks,
            "first_window_start_timestamp": first["start_timestamp"],
            "first_window_end_timestamp": first["end_timestamp"],
            "first_window_open": rth_open,
            "first_window_high": float(first["high"]),
            "first_window_low": float(first["low"]),
            "first_window_close": first_close,
            "first_window_return_points": first_window_return_points,
            "first_window_return_ticks": first_window_return_ticks,
            "late_day_signal_timestamp": signal_timestamp,
            "late_day_entry_window_start": signal_timestamp,
            "late_day_entry_window_end": signal_timestamp + pd.Timedelta(minutes=30),
            "penultimate_window_return_points": penultimate_return_points,
            "penultimate_window_return_ticks": penultimate_return_ticks,
            "min_overnight_return_ticks": self.min_overnight_return_ticks,
            "min_opening_reversal_ticks": self.min_opening_reversal_ticks,
            "min_penultimate_return_ticks": self.min_penultimate_return_ticks,
        }
        return Signal(
            direction=direction,
            level_type=f"overnight_return_late_day_momentum_{self.setup_mode}",
            swept_level=prev_close,
            sweep_timestamp=first["start_timestamp"],
            sweep_high=float(first["high"]),
            sweep_low=float(first["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": signal_bar_high,
                "confirmation_low": signal_bar_low,
                "confirmation_close": float(bar["close"]),
                "overnight_return_ticks": overnight_return_ticks,
                "first_window_return_ticks": first_window_return_ticks,
                "penultimate_window_return_ticks": penultimate_return_ticks,
                "setup_mode": self.setup_mode,
            },
            report_fields=report_fields,
        )

    def _aggregate_bar(self, aggregate: dict | None, bar: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
        if aggregate is None or aggregate.get("start_timestamp") != start or aggregate.get("end_timestamp") != end:
            return {
                "start_timestamp": start,
                "end_timestamp": end,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "bar_count": 1,
                "prev_rth_close": _finite_float(bar.get("prev_rth_close")),
            }

        aggregate["high"] = max(float(aggregate["high"]), float(bar["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(bar["low"]))
        aggregate["close"] = float(bar["close"])
        aggregate["bar_count"] += 1
        return aggregate

    def _window_complete(self, window: dict, minutes: float) -> bool:
        expected = max(1, int(math.ceil(minutes / self.bar_interval_minutes)))
        return int(window.get("bar_count", 0)) >= expected

    def _bar_close_timestamp(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        return timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

    def _session_timestamp(self, timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
        return timestamp.replace(
            hour=session_time.hour,
            minute=session_time.minute,
            second=session_time.second,
            microsecond=0,
        )


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
