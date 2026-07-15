from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class PdhPdlBreakoutContinuationEntry:
    name = "pdh_pdl_breakout_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "fresh_close_break")).lower()
        self.start_time = parse_time(params.get("start_time", "09:30:00"))
        self.end_time = parse_time(params.get("end_time", "13:30:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.close_buffer = self.tick_size * int(params.get("close_buffer_ticks", 0))
        self.retest_tolerance = self.tick_size * int(params.get("retest_tolerance_ticks", 1))
        self.retest_window_bars = int(params.get("retest_window_bars", 3))
        self.min_volume_ratio = float(params.get("min_volume_ratio", 0.0))
        self.min_gap_points = float(params.get("min_gap_points", 0.0))
        self.gap_hold_bars = int(params.get("gap_hold_bars", 1))
        self.require_fresh_level = bool(params.get("require_fresh_level", True))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "first_rth_bar": None,
                "long_breakout": None,
                "short_breakout": None,
                "gap": None,
                "completed": False,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
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

        if self.setup_mode == "gap_hold_continuation":
            return self._gap_hold_signal(bar, state, prev_high, prev_low)
        if self.setup_mode == "break_retest_hold":
            signal = self._existing_retest_signal(bar, state)
            if signal is not None:
                state["completed"] = True
                return signal
            self._record_retest_breakout(bar, state, prev_high, prev_low)
            return None
        return self._fresh_close_break_signal(bar, state, prev_high, prev_low)

    def _fresh_close_break_signal(self, bar: pd.Series, state: dict, prev_high: float, prev_low: float) -> Signal | None:
        close = float(bar["close"])
        if (
            self.allow_long
            and self._fresh_level(bar, "prev_rth_high_fresh")
            and float(bar["high"]) > prev_high
            and close >= prev_high + self.close_buffer
        ):
            state["completed"] = True
            return self._signal("long", bar, prev_high, "previous_rth_high_breakout", bar, prev_high, prev_low)
        if (
            self.allow_short
            and self._fresh_level(bar, "prev_rth_low_fresh")
            and float(bar["low"]) < prev_low
            and close <= prev_low - self.close_buffer
        ):
            state["completed"] = True
            return self._signal("short", bar, prev_low, "previous_rth_low_breakout", bar, prev_high, prev_low)
        return None

    def _record_retest_breakout(self, bar: pd.Series, state: dict, prev_high: float, prev_low: float) -> None:
        idx = int(bar.name) if bar.name is not None else 0
        close = float(bar["close"])
        if (
            self.allow_long
            and state["long_breakout"] is None
            and self._fresh_level(bar, "prev_rth_high_fresh")
            and float(bar["high"]) > prev_high
            and close >= prev_high + self.close_buffer
        ):
            state["long_breakout"] = self._breakout_state(idx, bar, prev_high, prev_high, prev_low)
        if (
            self.allow_short
            and state["short_breakout"] is None
            and self._fresh_level(bar, "prev_rth_low_fresh")
            and float(bar["low"]) < prev_low
            and close <= prev_low - self.close_buffer
        ):
            state["short_breakout"] = self._breakout_state(idx, bar, prev_low, prev_high, prev_low)

    def _existing_retest_signal(self, bar: pd.Series, state: dict) -> Signal | None:
        idx = int(bar.name) if bar.name is not None else 0
        close = float(bar["close"])

        long_breakout = state.get("long_breakout")
        if long_breakout:
            if self._retest_expired(idx, long_breakout):
                state["long_breakout"] = None
            elif idx > long_breakout["idx"] and float(bar["low"]) <= long_breakout["level"] + self.retest_tolerance:
                if close >= long_breakout["level"] + self.close_buffer:
                    state["long_breakout"] = None
                    return self._signal(
                        "long",
                        bar,
                        long_breakout["level"],
                        "previous_rth_high_retest",
                        bar,
                        long_breakout["prev_high"],
                        long_breakout["prev_low"],
                        breakout=long_breakout,
                    )

        short_breakout = state.get("short_breakout")
        if short_breakout:
            if self._retest_expired(idx, short_breakout):
                state["short_breakout"] = None
            elif idx > short_breakout["idx"] and float(bar["high"]) >= short_breakout["level"] - self.retest_tolerance:
                if close <= short_breakout["level"] - self.close_buffer:
                    state["short_breakout"] = None
                    return self._signal(
                        "short",
                        bar,
                        short_breakout["level"],
                        "previous_rth_low_retest",
                        bar,
                        short_breakout["prev_high"],
                        short_breakout["prev_low"],
                        breakout=short_breakout,
                    )
        return None

    def _gap_hold_signal(self, bar: pd.Series, state: dict, prev_high: float, prev_low: float) -> Signal | None:
        gap = state.get("gap")
        first_bar = state.get("first_rth_bar") or self._bar_snapshot(bar)
        if gap is None:
            if self.allow_long and first_bar["open"] >= prev_high + self.min_gap_points:
                gap = self._gap_state("long", bar, prev_high, prev_high, prev_low, first_bar)
                state["gap"] = gap
            elif self.allow_short and first_bar["open"] <= prev_low - self.min_gap_points:
                gap = self._gap_state("short", bar, prev_low, prev_high, prev_low, first_bar)
                state["gap"] = gap
            else:
                state["completed"] = True
                return None

        gap["sweep_low"] = min(gap["sweep_low"], float(bar["low"]))
        gap["sweep_high"] = max(gap["sweep_high"], float(bar["high"]))
        close = float(bar["close"])
        if gap["direction"] == "long":
            if close < gap["level"]:
                state["completed"] = True
                return None
            if close >= gap["level"] + self.close_buffer:
                gap["hold_count"] += 1
        else:
            if close > gap["level"]:
                state["completed"] = True
                return None
            if close <= gap["level"] - self.close_buffer:
                gap["hold_count"] += 1

        if gap["hold_count"] >= self.gap_hold_bars:
            state["completed"] = True
            return self._signal(
                gap["direction"],
                bar,
                gap["level"],
                f"previous_rth_{'high' if gap['direction'] == 'long' else 'low'}_gap_hold",
                gap,
                gap["prev_high"],
                gap["prev_low"],
                gap=gap,
            )
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
    ) -> Signal:
        sweep_low = float(sweep_source["sweep_low"] if isinstance(sweep_source, dict) else sweep_source["low"])
        sweep_high = float(sweep_source["sweep_high"] if isinstance(sweep_source, dict) else sweep_source["high"])
        breakout_timestamp = (breakout or {}).get("timestamp", bar["timestamp"])
        gap_open = (gap or {}).get("first_open")
        report_fields = {
            "prev_rth_high": prev_high,
            "prev_rth_low": prev_low,
            "breakout_level": level,
            "breakout_timestamp": breakout_timestamp,
            "continuation_timestamp": bar["timestamp"],
            "setup_mode": self.setup_mode,
            "confirmation_close": float(bar["close"]),
            "confirmation_high": float(bar["high"]),
            "confirmation_low": float(bar["low"]),
            "confirmation_volume_ratio": float(bar.get("volume_ratio", 0.0)),
            "gap_open": gap_open,
        }
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=level,
            sweep_timestamp=breakout_timestamp,
            sweep_high=sweep_high,
            sweep_low=sweep_low,
            reclaim_timestamp=bar["timestamp"],
            metadata={
                "confirmation_close": float(bar["close"]),
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_volume_ratio": float(bar.get("volume_ratio", 0.0)),
            },
            report_fields=report_fields,
        )

    def _breakout_state(self, idx: int, bar: pd.Series, level: float, prev_high: float, prev_low: float) -> dict:
        return {
            "idx": idx,
            "timestamp": bar["timestamp"],
            "level": level,
            "sweep_low": float(bar["low"]),
            "sweep_high": float(bar["high"]),
            "prev_high": prev_high,
            "prev_low": prev_low,
        }

    def _gap_state(
        self,
        direction: str,
        bar: pd.Series,
        level: float,
        prev_high: float,
        prev_low: float,
        first_bar: dict,
    ) -> dict:
        return {
            "direction": direction,
            "level": level,
            "timestamp": bar["timestamp"],
            "sweep_low": float(bar["low"]),
            "sweep_high": float(bar["high"]),
            "prev_high": prev_high,
            "prev_low": prev_low,
            "first_open": first_bar["open"],
            "hold_count": 0,
        }

    def _retest_expired(self, idx: int, breakout: dict) -> bool:
        return max(0, idx - int(breakout["idx"]) - 1) > self.retest_window_bars

    def _fresh_level(self, bar: pd.Series, column: str) -> bool:
        if not self.require_fresh_level:
            return True
        if column not in bar:
            return True
        value = bar.get(column)
        if pd.isna(value):
            return False
        return bool(value)

    def _bar_snapshot(self, bar: pd.Series) -> dict:
        return {
            "timestamp": bar["timestamp"],
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
        }


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
