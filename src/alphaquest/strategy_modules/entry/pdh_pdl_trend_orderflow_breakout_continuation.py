from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.pdh_pdl_orderflow_breakout_continuation import (
    PdhPdlOrderflowBreakoutContinuationEntry,
)


class PdhPdlTrendOrderflowBreakoutContinuationEntry(PdhPdlOrderflowBreakoutContinuationEntry):
    name = "pdh_pdl_trend_orderflow_breakout_continuation"

    def __init__(self, params: dict):
        super().__init__(params)
        self.short_trend_bars = int(params.get("short_trend_bars", 3))
        self.long_trend_bars = int(params.get("long_trend_bars", 6))
        self.min_trend_move_ticks = float(params.get("min_trend_move_ticks", 0.0))
        if self.short_trend_bars <= 0 or self.long_trend_bars <= 0:
            raise ValueError("entry.params.short_trend_bars and long_trend_bars must be positive.")
        if self.min_trend_move_ticks < 0:
            raise ValueError("entry.params.min_trend_move_ticks must be non-negative.")
        self.min_trend_move = self.min_trend_move_ticks * self.tick_size
        self.trend_bars_by_day: dict = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if bool(bar.get("is_rth", False)):
            timestamp = pd.Timestamp(bar["timestamp"])
            session_date = bar.get("session_date", timestamp.date())
            bars = self.trend_bars_by_day.setdefault(session_date, [])
            bars.append(self._trend_bar_snapshot(bar))
            bars[:] = bars[-(2 * max(self.short_trend_bars, self.long_trend_bars)) :]
        if self.setup_mode == "trend_level_hold":
            return self._trend_level_hold_signal(bar, trades_today=trades_today)
        return super().on_bar_close(bar, trades_today=trades_today)

    def _trend_level_hold_signal(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_time = timestamp.time()
        if bar_time < self.start_time or bar_time > self.end_time:
            return None

        prev_high = _finite_float(bar.get("prev_rth_high"))
        prev_low = _finite_float(bar.get("prev_rth_low"))
        if prev_high is None or prev_low is None:
            return None

        state = self._state(bar["session_date"])
        if state["completed"]:
            return None
        if state["first_rth_bar"] is None:
            state["first_rth_bar"] = self._bar_snapshot(bar)

        if float(bar.get("volume_ratio", 0.0)) < self.min_volume_ratio:
            return None

        close = float(bar["close"])
        if self.allow_long and close >= prev_high + self.close_buffer:
            signal = self._signal(
                "long",
                bar,
                prev_high,
                "previous_rth_high_trend_hold",
                bar,
                prev_high,
                prev_low,
            )
            if signal is not None:
                state["completed"] = True
            return signal
        if self.allow_short and close <= prev_low - self.close_buffer:
            signal = self._signal(
                "short",
                bar,
                prev_low,
                "previous_rth_low_trend_hold",
                bar,
                prev_high,
                prev_low,
            )
            if signal is not None:
                state["completed"] = True
            return signal
        return None

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        level: float,
        level_type: str,
        sweep_source,
        prev_high: float,
        prev_low: float,
        *,
        breakout: dict | None = None,
        gap: dict | None = None,
    ) -> Signal | None:
        trend = self._trend_filter(direction, bar)
        if trend is None:
            return None

        signal = super()._signal(
            direction,
            bar,
            level,
            level_type,
            sweep_source,
            prev_high,
            prev_low,
            breakout=breakout,
            gap=gap,
        )
        if signal is None:
            return None
        signal.metadata.update(
            {
                "trend_filter": "pdh_pdl_completed_bar_higher_highs_lows",
                "trend_direction": direction,
                "short_trend_bars": self.short_trend_bars,
                "long_trend_bars": self.long_trend_bars,
                "min_trend_move_ticks": self.min_trend_move_ticks,
            }
        )
        signal.report_fields.update(
            {
                "trend_filter": "pdh_pdl_completed_bar_higher_highs_lows",
                "trend_direction": direction,
                "short_trend_bars": self.short_trend_bars,
                "long_trend_bars": self.long_trend_bars,
                "min_trend_move_ticks": self.min_trend_move_ticks,
                **trend,
            }
        )
        return signal

    def _trend_filter(self, direction: str, bar: pd.Series) -> dict | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        bars = self.trend_bars_by_day.get(session_date, [])
        required = 2 * max(self.short_trend_bars, self.long_trend_bars)
        if len(bars) < required:
            return None

        short = self._window_trend(bars, self.short_trend_bars, "short")
        long = self._window_trend(bars, self.long_trend_bars, "long")
        if direction == "long":
            if not (short["long_ok"] and long["long_ok"]):
                return None
        elif direction == "short":
            if not (short["short_ok"] and long["short_ok"]):
                return None
        else:
            return None
        return {**short["report_fields"], **long["report_fields"]}

    def _window_trend(self, bars: list[dict], window_bars: int, label: str) -> dict:
        previous = bars[-(2 * window_bars) : -window_bars]
        current = bars[-window_bars:]
        prev_high = max(_required_float(bar.get("high"), "high") for bar in previous)
        prev_low = min(_required_float(bar.get("low"), "low") for bar in previous)
        current_high = max(_required_float(bar.get("high"), "high") for bar in current)
        current_low = min(_required_float(bar.get("low"), "low") for bar in current)
        long_ok = current_high >= prev_high + self.min_trend_move and current_low >= prev_low + self.min_trend_move
        short_ok = current_high <= prev_high - self.min_trend_move and current_low <= prev_low - self.min_trend_move
        return {
            "long_ok": long_ok,
            "short_ok": short_ok,
            "report_fields": {
                f"{label}_trend_previous_high": prev_high,
                f"{label}_trend_previous_low": prev_low,
                f"{label}_trend_current_high": current_high,
                f"{label}_trend_current_low": current_low,
            },
        }

    def _trend_bar_snapshot(self, bar: pd.Series) -> dict:
        return {
            "timestamp": bar["timestamp"],
            "high": _required_float(bar.get("high"), "high"),
            "low": _required_float(bar.get("low"), "low"),
        }


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _required_float(value, name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"entry bar is missing finite {name}.")
    return out
