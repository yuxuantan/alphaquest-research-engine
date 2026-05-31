from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from propstack.utils.time import parse_time


@dataclass
class Signal:
    direction: str
    level_type: str
    swept_level: float
    sweep_timestamp: object
    sweep_high: float
    sweep_low: float
    reclaim_timestamp: object


class PdhPdlSweepReclaim:
    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("strategy_name", "pdh_pdl_sweep")
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {"long_sweep": None, "short_sweep": None},
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bar.get("is_rth", False):
            return None
        t = bar["timestamp"].time()
        if t < parse_time(self.config.get("start_time", "08:30:00")):
            return None
        if t > parse_time(self.config.get("end_time", "14:45:00")):
            return None
        if trades_today >= int(self.config.get("max_trades_per_day", 999)):
            return None
        if bar.get("volume_ratio", 0) < float(self.config.get("min_volume_ratio", 0)):
            return None

        prev_low = bar.get("prev_rth_low")
        prev_high = bar.get("prev_rth_high")
        if pd.isna(prev_low) or pd.isna(prev_high):
            return None

        state = self._state(bar["session_date"])
        window = int(self.config.get("reclaim_window_bars", 3))
        idx = int(bar.name)

        if self.config.get("allow_long", True) and bar["low"] < prev_low:
            state["long_sweep"] = {
                "idx": idx,
                "timestamp": bar["timestamp"],
                "sweep_low": float(bar["low"]),
                "sweep_high": float(bar["high"]),
                "level": float(prev_low),
            }
        if self.config.get("allow_short", True) and bar["high"] > prev_high:
            state["short_sweep"] = {
                "idx": idx,
                "timestamp": bar["timestamp"],
                "sweep_low": float(bar["low"]),
                "sweep_high": float(bar["high"]),
                "level": float(prev_high),
            }

        long_sweep = state.get("long_sweep")
        if long_sweep and idx - long_sweep["idx"] <= window and bar["close"] > long_sweep["level"]:
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
        if short_sweep and idx - short_sweep["idx"] <= window and bar["close"] < short_sweep["level"]:
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

        if long_sweep and idx - long_sweep["idx"] > window:
            state["long_sweep"] = None
        if short_sweep and idx - short_sweep["idx"] > window:
            state["short_sweep"] = None
        return None
