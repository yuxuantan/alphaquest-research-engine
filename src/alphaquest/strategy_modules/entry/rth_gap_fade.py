from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class RthGapFadeEntry:
    name = "rth_gap_fade"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "open_reversal")).lower()
        self.start_time = parse_time(params.get("start_time", "09:30:00"))
        self.end_time = parse_time(params.get("end_time", "11:00:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_gap_points = float(params.get("min_gap_points", 2.0))
        self.confirmation_buffer = self.tick_size * int(params.get("confirmation_buffer_ticks", 0))
        self.min_extension_points = float(params.get("min_extension_points", 1.0))
        self.max_wait_bars = int(params.get("max_wait_bars", 12))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "first_bar": None,
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

        prev_close = _finite_float(bar.get("prev_rth_close"))
        if prev_close is None:
            return None

        state = self._state(bar["session_date"])
        if state["completed"]:
            return None
        if state["first_bar"] is None:
            state["first_bar"] = self._bar_snapshot(bar)
            state["gap"] = self._initial_gap(bar, prev_close)
            if state["gap"] is None:
                state["completed"] = True
                return None

        gap = state["gap"]
        gap["age_bars"] += 1
        gap["sweep_low"] = min(gap["sweep_low"], float(bar["low"]))
        gap["sweep_high"] = max(gap["sweep_high"], float(bar["high"]))
        if gap["direction"] == "short":
            gap["extended"] = gap["extended"] or float(bar["high"]) >= gap["gap_open"] + self.min_extension_points
        else:
            gap["extended"] = gap["extended"] or float(bar["low"]) <= gap["gap_open"] - self.min_extension_points

        if gap["age_bars"] > self.max_wait_bars:
            state["completed"] = True
            return None

        if self._confirmed(bar, gap):
            state["completed"] = True
            return self._signal(bar, gap, prev_close)
        return None

    def _initial_gap(self, bar: pd.Series, prev_close: float) -> dict | None:
        gap_open = float(bar["open"])
        gap_points = gap_open - prev_close
        if gap_points >= self.min_gap_points and self.allow_short:
            direction = "short"
        elif gap_points <= -self.min_gap_points and self.allow_long:
            direction = "long"
        else:
            return None
        return {
            "direction": direction,
            "gap_open": gap_open,
            "gap_points": gap_points,
            "timestamp": bar["timestamp"],
            "sweep_low": float(bar["low"]),
            "sweep_high": float(bar["high"]),
            "age_bars": 0,
            "extended": False,
        }

    def _confirmed(self, bar: pd.Series, gap: dict) -> bool:
        close = float(bar["close"])
        if self.setup_mode == "vwap_reclaim":
            vwap = _finite_float(bar.get("vwap"))
            if vwap is None:
                return False
            if gap["direction"] == "short":
                return close <= vwap - self.confirmation_buffer
            return close >= vwap + self.confirmation_buffer

        if self.setup_mode == "extension_reject" and not gap["extended"]:
            return False

        if gap["direction"] == "short":
            return close <= gap["gap_open"] - self.confirmation_buffer
        return close >= gap["gap_open"] + self.confirmation_buffer

    def _signal(self, bar: pd.Series, gap: dict, prev_close: float) -> Signal:
        level_type = f"rth_gap_{self.setup_mode}"
        report_fields = {
            "prev_rth_close": prev_close,
            "gap_open": gap["gap_open"],
            "gap_points": gap["gap_points"],
            "gap_timestamp": gap["timestamp"],
            "gap_confirmation_timestamp": bar["timestamp"],
            "gap_setup_mode": self.setup_mode,
            "confirmation_close": float(bar["close"]),
            "confirmation_high": float(bar["high"]),
            "confirmation_low": float(bar["low"]),
        }
        return Signal(
            direction=gap["direction"],
            level_type=level_type,
            swept_level=gap["gap_open"],
            sweep_timestamp=gap["timestamp"],
            sweep_high=gap["sweep_high"],
            sweep_low=gap["sweep_low"],
            reclaim_timestamp=bar["timestamp"],
            metadata={
                "prev_rth_close": prev_close,
                "confirmation_close": float(bar["close"]),
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
            },
            report_fields=report_fields,
        )

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
