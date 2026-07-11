from __future__ import annotations

import math

from propstack.strategy_modules.entry.yush_trend_47 import YushTrend47Entry


class YushTrend48Entry(YushTrend47Entry):
    name = "yush_trend_48"

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_signal_risk_points = float(params.get("min_signal_risk_points", 3.0))
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

    def _intrabar_video_signal(self, *args, **kwargs):
        signal = super()._intrabar_video_signal(*args, **kwargs)
        signal.metadata["min_signal_risk_points"] = self.min_signal_risk_points
        signal.report_fields["min_signal_risk_points"] = self.min_signal_risk_points
        return signal
