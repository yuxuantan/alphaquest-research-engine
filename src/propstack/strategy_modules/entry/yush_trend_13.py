from __future__ import annotations

import math

from propstack.strategy_modules.entry.yush_trend_12 import YushTrend12Entry


class YushTrend13Entry(YushTrend12Entry):
    name = "yush_trend_13"

    def __init__(self, params: dict):
        super().__init__(params)
        self.max_signal_risk_points = float(params.get("max_signal_risk_points", 6.0))
        self.stop_offset_ticks = int(params.get("stop_offset_ticks", 2))
        if not math.isfinite(self.max_signal_risk_points) or self.max_signal_risk_points <= 0:
            raise ValueError("entry.params.max_signal_risk_points must be greater than 0.")

    def _intrabar_trend_pullback_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not super()._intrabar_trend_pullback_confirms(direction, level, state):
            return False
        stop_offset = self.stop_offset_ticks * self.tick_size
        if direction == "long":
            risk_points = float(state["price"]) - (float(state["low"]) - stop_offset)
        else:
            risk_points = (float(state["high"]) + stop_offset) - float(state["price"])
        return 0 < risk_points <= self.max_signal_risk_points
