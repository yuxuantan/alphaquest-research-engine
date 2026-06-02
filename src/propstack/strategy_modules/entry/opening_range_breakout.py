from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OpeningRangeBreakoutEntry:
    name = "opening_range_breakout"

    def __init__(self, params: dict):
        self.params = params
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "or_bars": [],
                "confirmation_bars": [],
                "opening_range": None,
                "completed": False,
                "skip_day": False,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bar.get("is_rth", False):
            return None
        if trades_today >= int(self.params.get("max_trades_per_day", 1)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        rth_start = parse_time(self.params.get("rth_start", "09:30:00"))
        if timestamp.time() < rth_start:
            return None

        state = self._state(bar["session_date"])
        if state["completed"] or state["skip_day"]:
            return None

        elapsed_minutes = self._elapsed_minutes(timestamp, rth_start)
        if elapsed_minutes < 0:
            return None

        opening_minutes = float(self.params.get("opening_range_minutes", 5))
        confirmation_minutes = float(self.params.get("confirmation_minutes", 5))
        opening_bar_count = self._bar_count(opening_minutes)
        confirmation_bar_count = self._bar_count(confirmation_minutes)

        if elapsed_minutes < opening_minutes:
            self._append_limited(state["or_bars"], bar, opening_bar_count)
            if len(state["or_bars"]) == opening_bar_count:
                state["opening_range"] = self._build_opening_range(state)
            return None

        if state["opening_range"] is None:
            if len(state["or_bars"]) == opening_bar_count:
                state["opening_range"] = self._build_opening_range(state)
            else:
                state["completed"] = True
                return None

        if state["skip_day"]:
            return None

        if timestamp.time() >= parse_time(self.params.get("last_entry_time", "12:00:00")):
            state["completed"] = True
            return None

        if elapsed_minutes >= opening_minutes:
            self._append_limited(state["confirmation_bars"], bar, confirmation_bar_count)
            if len(state["confirmation_bars"]) < confirmation_bar_count:
                return None
            signal = self._confirmation_signal(bar, state["opening_range"], state["confirmation_bars"])
            if signal is not None:
                state["completed"] = True
                return signal
            state["confirmation_bars"] = []
            return None

        state["completed"] = True
        return None

    def _bar_count(self, minutes: float) -> int:
        interval = float(self.params.get("bar_interval_minutes", 1))
        if interval <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        return max(1, int(math.ceil(minutes / interval)))

    def _elapsed_minutes(self, timestamp: pd.Timestamp, rth_start) -> float:
        start = timestamp.replace(
            hour=rth_start.hour,
            minute=rth_start.minute,
            second=rth_start.second,
            microsecond=0,
        )
        return (timestamp - start).total_seconds() / 60.0

    def _append_limited(self, bars: list[pd.Series], bar: pd.Series, limit: int) -> None:
        if len(bars) < limit:
            bars.append(bar)

    def _build_opening_range(self, state: dict) -> dict | None:
        bars = state["or_bars"]
        try:
            or_open = float(bars[0]["open"])
            or_high = max(float(bar["high"]) for bar in bars)
            or_low = min(float(bar["low"]) for bar in bars)
        except (KeyError, TypeError, ValueError):
            state["skip_day"] = True
            return None

        width = or_high - or_low
        if not all(math.isfinite(value) for value in [or_open, or_high, or_low, width]) or or_open <= 0:
            state["skip_day"] = True
            return None

        max_width_pct = self.params.get("max_opening_range_pct_of_open", 0.0055)
        width_pct = width / or_open
        if max_width_pct is not None and width_pct > float(max_width_pct):
            state["skip_day"] = True

        return {
            "open": or_open,
            "high": or_high,
            "low": or_low,
            "width": width,
            "width_pct_of_open": width_pct,
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": self._bar_close_timestamp(bars[-1]["timestamp"]),
        }

    def _confirmation_signal(
        self,
        bar: pd.Series,
        opening_range: dict | None,
        confirmation_bars: list[pd.Series],
    ) -> Signal | None:
        if opening_range is None:
            return None
        if bar["timestamp"].time() >= parse_time(self.params.get("last_entry_time", "12:00:00")):
            return None

        close = float(bar["close"])
        direction = None
        breakout_level = None
        level_type = None
        if close > opening_range["high"] and self.params.get("allow_long", True):
            if self.params.get("skip_tuesday_longs", True) and self._is_tuesday(bar):
                return None
            direction = "long"
            breakout_level = opening_range["high"]
            level_type = "opening_range_high"
        elif close < opening_range["low"] and self.params.get("allow_short", True):
            direction = "short"
            breakout_level = opening_range["low"]
            level_type = "opening_range_low"

        if direction is None:
            return None

        confirmation_start = confirmation_bars[0]["timestamp"] if confirmation_bars else bar["timestamp"]
        confirmation_end = self._bar_close_timestamp(bar["timestamp"])
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=breakout_level,
            sweep_timestamp=opening_range["start_timestamp"],
            sweep_high=opening_range["high"],
            sweep_low=opening_range["low"],
            reclaim_timestamp=bar["timestamp"],
            opening_range_high=opening_range["high"],
            opening_range_low=opening_range["low"],
            opening_range_open=opening_range["open"],
            opening_range_width=opening_range["width"],
            breakout_level=breakout_level,
            metadata={
                "opening_range_end_timestamp": opening_range["end_timestamp"],
                "opening_range_width_pct_of_open": opening_range["width_pct_of_open"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "breakout_timestamp": confirmation_end,
            },
            report_fields={
                "opening_range_start_timestamp": opening_range["start_timestamp"],
                "opening_range_end_timestamp": opening_range["end_timestamp"],
                "opening_range_high": opening_range["high"],
                "opening_range_low": opening_range["low"],
                "opening_range_open": opening_range["open"],
                "opening_range_width": opening_range["width"],
                "opening_range_width_pct_of_open": opening_range["width_pct_of_open"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "breakout_timestamp": confirmation_end,
                "breakout_level": breakout_level,
            },
        )

    def _bar_close_timestamp(self, timestamp) -> pd.Timestamp:
        return pd.Timestamp(timestamp) + pd.Timedelta(minutes=float(self.params.get("bar_interval_minutes", 1)))

    def _is_tuesday(self, bar: pd.Series) -> bool:
        try:
            return pd.Timestamp(bar["session_date"]).weekday() == 1
        except (KeyError, ValueError, TypeError):
            return pd.Timestamp(bar["timestamp"]).weekday() == 1
