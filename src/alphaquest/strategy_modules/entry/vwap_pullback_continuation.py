from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class VwapPullbackContinuationEntry:
    name = "vwap_pullback_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "trend_reclaim")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "09:30:00"))
        self.end_time = parse_time(params.get("end_time", "13:30:00"))
        self.bar_minutes = float(params.get("bar_interval_minutes", 1))
        self.opening_drive_minutes = float(params.get("opening_drive_minutes", 30))
        self.required_trend_closes = int(params.get("required_trend_closes", 3))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.trend_vwap_buffer = self.tick_size * int(params.get("trend_vwap_buffer_ticks", 0))
        self.min_drive_points = float(params.get("min_drive_points", 2.0))
        self.pullback_tolerance = self.tick_size * int(params.get("pullback_tolerance_ticks", 0))
        self.reclaim_buffer = self.tick_size * int(params.get("reclaim_buffer_ticks", 0))
        self.reclaim_window_bars = int(params.get("reclaim_window_bars", 3))
        self.failed_break = self.setup_mode == "failed_vwap_break"
        self.failed_break_min = self.tick_size * int(params.get("failed_break_min_ticks", 1))
        self.min_drive_close_location = float(params.get("min_drive_close_location", 0.65))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "opening_bar": None,
                "drive_bars": [],
                "opening_drive": None,
                "long_trend_count": 0,
                "short_trend_count": 0,
                "long_pullback": None,
                "short_pullback": None,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_time = timestamp.time()
        if bar_time < self.start_time:
            return None
        if bar_time > self.end_time:
            return None

        vwap = _finite_float(bar.get("vwap"))
        if vwap is None:
            return None

        state = self._state(bar["session_date"])
        if state["opening_bar"] is None:
            state["opening_bar"] = {
                "timestamp": timestamp,
                "open": float(bar["open"]),
                "close": float(bar["close"]),
            }

        self._update_opening_drive(bar, state, timestamp)

        signal = self._existing_pullback_signal(bar, state, vwap)
        if signal is not None:
            self._update_trend_counts(bar, state, vwap)
            return signal

        self._record_new_pullbacks(bar, state, vwap)
        signal = self._existing_pullback_signal(bar, state, vwap)
        self._update_trend_counts(bar, state, vwap)
        return signal

    def _update_opening_drive(self, bar: pd.Series, state: dict, timestamp: pd.Timestamp) -> None:
        if state["opening_drive"] is not None:
            return
        start = timestamp.replace(
            hour=self.rth_start.hour,
            minute=self.rth_start.minute,
            second=self.rth_start.second,
            microsecond=0,
        )
        elapsed_minutes = (timestamp - start).total_seconds() / 60.0
        if elapsed_minutes < 0:
            return
        if elapsed_minutes < self.opening_drive_minutes:
            state["drive_bars"].append(
                {
                    "timestamp": timestamp,
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                }
            )
            return
        if not state["drive_bars"]:
            state["opening_drive"] = {}
            return
        bars = state["drive_bars"]
        drive_open = bars[0]["open"]
        drive_high = max(item["high"] for item in bars)
        drive_low = min(item["low"] for item in bars)
        drive_close = bars[-1]["close"]
        drive_range = drive_high - drive_low
        close_location = (drive_close - drive_low) / drive_range if drive_range > 0 else 0.5
        state["opening_drive"] = {
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": bars[-1]["timestamp"] + pd.Timedelta(minutes=self.bar_minutes),
            "open": drive_open,
            "high": drive_high,
            "low": drive_low,
            "close": drive_close,
            "range": drive_range,
            "close_location": close_location,
        }

    def _update_trend_counts(self, bar: pd.Series, state: dict, vwap: float) -> None:
        close = float(bar["close"])
        if close >= vwap + self.trend_vwap_buffer:
            state["long_trend_count"] += 1
        else:
            state["long_trend_count"] = 0
        if close <= vwap - self.trend_vwap_buffer:
            state["short_trend_count"] += 1
        else:
            state["short_trend_count"] = 0

    def _existing_pullback_signal(self, bar: pd.Series, state: dict, vwap: float) -> Signal | None:
        idx = int(bar.name) if bar.name is not None else 0

        long_pullback = state.get("long_pullback")
        if long_pullback:
            long_pullback["pullback_low"] = min(long_pullback["pullback_low"], float(bar["low"]))
            long_pullback["pullback_high"] = max(long_pullback["pullback_high"], float(bar["high"]))
            if self._expired(idx, long_pullback):
                state["long_pullback"] = None
            elif self.allow_long and self._long_reclaimed(bar, vwap):
                state["long_pullback"] = None
                return self._signal("long", bar, long_pullback, vwap, state)

        short_pullback = state.get("short_pullback")
        if short_pullback:
            short_pullback["pullback_low"] = min(short_pullback["pullback_low"], float(bar["low"]))
            short_pullback["pullback_high"] = max(short_pullback["pullback_high"], float(bar["high"]))
            if self._expired(idx, short_pullback):
                state["short_pullback"] = None
            elif self.allow_short and self._short_reclaimed(bar, vwap):
                state["short_pullback"] = None
                return self._signal("short", bar, short_pullback, vwap, state)
        return None

    def _record_new_pullbacks(self, bar: pd.Series, state: dict, vwap: float) -> None:
        idx = int(bar.name) if bar.name is not None else 0

        if self.allow_long and state.get("long_pullback") is None and self._long_context(bar, state, vwap):
            long_touched = float(bar["low"]) <= (vwap - self.failed_break_min if self.failed_break else vwap + self.pullback_tolerance)
            if long_touched:
                state["long_pullback"] = self._pullback_state(idx, bar, vwap)

        if self.allow_short and state.get("short_pullback") is None and self._short_context(bar, state, vwap):
            short_touched = float(bar["high"]) >= (vwap + self.failed_break_min if self.failed_break else vwap - self.pullback_tolerance)
            if short_touched:
                state["short_pullback"] = self._pullback_state(idx, bar, vwap)

    def _long_context(self, bar: pd.Series, state: dict, vwap: float) -> bool:
        session_open = _opening_price(state)
        close = float(bar["close"])
        if session_open is None or close < session_open + self.min_drive_points:
            return False
        if self.setup_mode == "opening_drive_pullback":
            return self._opening_drive_direction(state) == "long"
        return state["long_trend_count"] >= self.required_trend_closes

    def _short_context(self, bar: pd.Series, state: dict, vwap: float) -> bool:
        session_open = _opening_price(state)
        close = float(bar["close"])
        if session_open is None or close > session_open - self.min_drive_points:
            return False
        if self.setup_mode == "opening_drive_pullback":
            return self._opening_drive_direction(state) == "short"
        return state["short_trend_count"] >= self.required_trend_closes

    def _opening_drive_direction(self, state: dict) -> str | None:
        drive = state.get("opening_drive")
        if not drive:
            return None
        if drive["close"] >= drive["open"] + self.min_drive_points and drive["close_location"] >= self.min_drive_close_location:
            return "long"
        if drive["close"] <= drive["open"] - self.min_drive_points and drive["close_location"] <= 1.0 - self.min_drive_close_location:
            return "short"
        return None

    def _long_reclaimed(self, bar: pd.Series, vwap: float) -> bool:
        return float(bar["close"]) >= vwap + self.reclaim_buffer

    def _short_reclaimed(self, bar: pd.Series, vwap: float) -> bool:
        return float(bar["close"]) <= vwap - self.reclaim_buffer

    def _pullback_state(self, idx: int, bar: pd.Series, vwap: float) -> dict:
        return {
            "idx": idx,
            "timestamp": bar["timestamp"],
            "pullback_low": float(bar["low"]),
            "pullback_high": float(bar["high"]),
            "vwap_at_pullback": vwap,
        }

    def _expired(self, idx: int, pullback: dict) -> bool:
        bars_between = max(0, idx - int(pullback["idx"]) - 1)
        return bars_between > self.reclaim_window_bars

    def _signal(self, direction: str, bar: pd.Series, pullback: dict, vwap: float, state: dict) -> Signal:
        confirmation_end = pd.Timestamp(bar["timestamp"]) + pd.Timedelta(minutes=self.bar_minutes)
        drive = state.get("opening_drive") or {}
        opening = state.get("opening_bar") or {}
        report_fields = {
            "vwap_pullback_timestamp": pullback["timestamp"],
            "vwap_reclaim_timestamp": bar["timestamp"],
            "vwap_at_pullback": pullback["vwap_at_pullback"],
            "vwap_at_signal": vwap,
            "pullback_high": pullback["pullback_high"],
            "pullback_low": pullback["pullback_low"],
            "confirmation_close": float(bar["close"]),
            "confirmation_high": float(bar["high"]),
            "confirmation_low": float(bar["low"]),
            "confirmation_end_timestamp": confirmation_end,
            "session_open": opening.get("open"),
            "long_trend_count": state.get("long_trend_count", 0),
            "short_trend_count": state.get("short_trend_count", 0),
            "opening_drive_start_timestamp": drive.get("start_timestamp"),
            "opening_drive_end_timestamp": drive.get("end_timestamp"),
            "opening_drive_open": drive.get("open"),
            "opening_drive_high": drive.get("high"),
            "opening_drive_low": drive.get("low"),
            "opening_drive_close": drive.get("close"),
            "opening_drive_close_location": drive.get("close_location"),
        }
        return Signal(
            direction=direction,
            level_type="vwap_pullback_continuation",
            swept_level=vwap,
            sweep_timestamp=pullback["timestamp"],
            sweep_high=pullback["pullback_high"],
            sweep_low=pullback["pullback_low"],
            reclaim_timestamp=bar["timestamp"],
            metadata={
                "confirmation_close": float(bar["close"]),
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_end_timestamp": confirmation_end,
                "vwap_at_signal": vwap,
            },
            report_fields=report_fields,
        )


def _opening_price(state: dict) -> float | None:
    opening = state.get("opening_bar")
    if not opening:
        return None
    return _finite_float(opening.get("open"))


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
