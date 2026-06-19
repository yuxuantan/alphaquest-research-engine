from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.opening_range_failed_breakout_orderflow import (
    OpeningRangeFailedBreakoutOrderflowEntry,
)
from propstack.utils.time import parse_time


class OpeningRangeFailedBreakoutTrendOrderflowEntry(OpeningRangeFailedBreakoutOrderflowEntry):
    name = "opening_range_failed_breakout_trend_orderflow"

    def __init__(self, params: dict):
        super().__init__(params)
        self.short_trend_bars = int(params.get("short_trend_bars", 3))
        self.long_trend_bars = int(params.get("long_trend_bars", 6))
        self.min_trend_move_ticks = float(params.get("min_trend_move_ticks", 0.0))
        if self.short_trend_bars < 2:
            raise ValueError("entry.params.short_trend_bars must be at least 2.")
        if self.long_trend_bars < self.short_trend_bars:
            raise ValueError("entry.params.long_trend_bars must be >= short_trend_bars.")
        if self.min_trend_move_ticks < 0:
            raise ValueError("entry.params.min_trend_move_ticks must be non-negative.")

    def _state(self, session_date):
        state = super()._state(session_date)
        state.setdefault("all_bars", [])
        return state

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0):
        if bool(bar.get("is_rth", False)):
            timestamp = pd.Timestamp(bar["timestamp"])
            rth_start = parse_time(self.params.get("rth_start", "09:30:00"))
            if timestamp.time() >= rth_start:
                state = self._state(bar["session_date"])
                state["all_bars"].append(bar.copy())
        return super().on_bar_close(bar, trades_today=trades_today)

    def _failed_breakout_signal(self, bar: pd.Series, state: dict):
        had_candidate = state.get("failed_breakout") is not None
        signal = super()._failed_breakout_signal(bar, state)
        if signal is None:
            if not had_candidate and state.get("failed_breakout") is not None:
                failed = state["failed_breakout"]
                direction = "short" if failed["side"] == "upside" else "long"
                failed["trend_context"] = self._trend_context(state, direction, exclude_current_bar=True)
            return None

        failed = state.get("failed_breakout") or {}
        trend = failed.get("trend_context")
        if trend is None:
            return None
        signal.metadata.update(trend)
        signal.report_fields.update(trend)
        signal.level_type = f"{signal.level_type}_trend_filtered"
        return signal

    def _trend_context(self, state: dict, direction: str, *, exclude_current_bar: bool = False) -> dict | None:
        bars = state.get("all_bars") or []
        if exclude_current_bar:
            bars = bars[:-1]
        if len(bars) < self.long_trend_bars:
            return None

        short_context = _trend_window(
            bars[-self.short_trend_bars :],
            direction,
            self.tick_size,
            self.min_trend_move_ticks,
        )
        long_context = _trend_window(
            bars[-self.long_trend_bars :],
            direction,
            self.tick_size,
            self.min_trend_move_ticks,
        )
        if short_context is None or long_context is None:
            return None

        return {
            "trend_filter": "hh_hl_lh_ll_reclaim_direction",
            "trend_direction": direction,
            "short_trend_bars": self.short_trend_bars,
            "long_trend_bars": self.long_trend_bars,
            "min_trend_move_ticks": self.min_trend_move_ticks,
            "short_trend_high_move_ticks": short_context["high_move_ticks"],
            "short_trend_low_move_ticks": short_context["low_move_ticks"],
            "long_trend_high_move_ticks": long_context["high_move_ticks"],
            "long_trend_low_move_ticks": long_context["low_move_ticks"],
        }


def _trend_window(
    bars: list[pd.Series],
    direction: str,
    tick_size: float,
    min_move_ticks: float,
) -> dict | None:
    first = bars[0]
    last = bars[-1]
    try:
        high_start = float(first["high"])
        high_end = float(last["high"])
        low_start = float(first["low"])
        low_end = float(last["low"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in [high_start, high_end, low_start, low_end]):
        return None

    if direction == "long":
        high_move = (high_end - high_start) / tick_size
        low_move = (low_end - low_start) / tick_size
    else:
        high_move = (high_start - high_end) / tick_size
        low_move = (low_start - low_end) / tick_size

    if high_move < min_move_ticks or low_move < min_move_ticks:
        return None
    return {"high_move_ticks": high_move, "low_move_ticks": low_move}
