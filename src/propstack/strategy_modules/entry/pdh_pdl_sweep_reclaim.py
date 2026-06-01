from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class PdhPdlSweepReclaimEntry:
    name = "pdh_pdl_sweep_reclaim"

    def __init__(self, params: dict):
        self.params = params
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {"long_sweep": None, "short_sweep": None},
        )

    def _bars_between(self, idx: int, sweep: dict) -> int:
        return idx - sweep["idx"] - 1

    def _within_reclaim_window(self, idx: int, sweep: dict, window: int) -> bool:
        return idx > sweep["idx"] and self._bars_between(idx, sweep) <= window

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bar.get("is_rth", False):
            return None
        t = bar["timestamp"].time()
        if t < parse_time(self.params.get("start_time", "08:30:00")):
            return None
        if t > parse_time(self.params.get("end_time", "14:45:00")):
            return None
        if trades_today >= int(self.params.get("max_trades_per_day", 999)):
            return None
        if bar.get("volume_ratio", 0) < float(self.params.get("min_volume_ratio", 0)):
            return None

        prev_low = bar.get("prev_rth_low")
        prev_high = bar.get("prev_rth_high")
        if pd.isna(prev_low) or pd.isna(prev_high):
            return None

        state = self._state(bar["session_date"])
        window = int(self.params.get("reclaim_window_bars", 3))
        idx = int(bar.name)

        long_sweep = state.get("long_sweep")
        short_sweep = state.get("short_sweep")
        if long_sweep and self._bars_between(idx, long_sweep) > window:
            state["long_sweep"] = None
            long_sweep = None
        if short_sweep and self._bars_between(idx, short_sweep) > window:
            state["short_sweep"] = None
            short_sweep = None

        if self.params.get("allow_long", True) and long_sweep is None and bar["low"] < prev_low:
            state["long_sweep"] = {
                "idx": idx,
                "timestamp": bar["timestamp"],
                "sweep_low": float(bar["low"]),
                "sweep_high": float(bar["high"]),
                "level": float(prev_low),
            }
        if self.params.get("allow_short", True) and short_sweep is None and bar["high"] > prev_high:
            state["short_sweep"] = {
                "idx": idx,
                "timestamp": bar["timestamp"],
                "sweep_low": float(bar["low"]),
                "sweep_high": float(bar["high"]),
                "level": float(prev_high),
            }

        long_sweep = state.get("long_sweep")
        if long_sweep and bar["low"] < long_sweep["level"]:
            long_sweep["sweep_low"] = min(long_sweep["sweep_low"], float(bar["low"]))
            long_sweep["sweep_high"] = max(long_sweep["sweep_high"], float(bar["high"]))
        if long_sweep and self._within_reclaim_window(idx, long_sweep, window) and bar["close"] > long_sweep["level"]:
            state["long_sweep"] = None
            return Signal(
                direction="long",
                level_type="previous_rth_low",
                swept_level=long_sweep["level"],
                sweep_timestamp=long_sweep["timestamp"],
                sweep_high=long_sweep["sweep_high"],
                sweep_low=long_sweep["sweep_low"],
                reclaim_timestamp=bar["timestamp"],
            )

        short_sweep = state.get("short_sweep")
        if short_sweep and bar["high"] > short_sweep["level"]:
            short_sweep["sweep_low"] = min(short_sweep["sweep_low"], float(bar["low"]))
            short_sweep["sweep_high"] = max(short_sweep["sweep_high"], float(bar["high"]))
        if short_sweep and self._within_reclaim_window(idx, short_sweep, window) and bar["close"] < short_sweep["level"]:
            state["short_sweep"] = None
            return Signal(
                direction="short",
                level_type="previous_rth_high",
                swept_level=short_sweep["level"],
                sweep_timestamp=short_sweep["timestamp"],
                sweep_high=short_sweep["sweep_high"],
                sweep_low=short_sweep["sweep_low"],
                reclaim_timestamp=bar["timestamp"],
            )
        return None
