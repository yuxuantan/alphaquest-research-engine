from __future__ import annotations

import math

from propstack.strategy_modules.entry.yush_trend_26 import YushTrend26Entry


class YushTrend28Entry(YushTrend26Entry):
    name = "yush_trend_28"

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_signal_risk_points = float(params.get("min_signal_risk_points", 0.0))
        if not math.isfinite(self.min_signal_risk_points) or self.min_signal_risk_points < 0:
            raise ValueError("entry.params.min_signal_risk_points must be non-negative.")

    def _intrabar_trend_pullback_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not super()._intrabar_trend_pullback_confirms(direction, level, state):
            return False
        stop_offset = self.stop_offset_ticks * self.tick_size
        if direction == "long":
            risk_points = float(state["price"]) - (float(state["low"]) - stop_offset)
        else:
            risk_points = (float(state["high"]) + stop_offset) - float(state["price"])
        return risk_points >= self.min_signal_risk_points
