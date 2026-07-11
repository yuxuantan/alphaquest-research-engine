from __future__ import annotations

import math

from propstack.strategy_modules.entry.yush_trend_45 import YushTrend45Entry


class YushTrend46Entry(YushTrend45Entry):
    name = "yush_trend_46"

    def __init__(self, params: dict):
        super().__init__(params)
        self.max_directional_signed_volume = float(params.get("max_directional_signed_volume", 800.0))
        if not math.isfinite(self.max_directional_signed_volume) or self.max_directional_signed_volume <= 0:
            raise ValueError("entry.params.max_directional_signed_volume must be greater than 0.")

    def _intrabar_trend_pullback_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not super()._intrabar_trend_pullback_confirms(direction, level, state):
            return False
        signed_volume = float(state.get("signed_volume", 0.0))
        if direction == "long":
            return signed_volume <= self.max_directional_signed_volume
        return signed_volume >= -self.max_directional_signed_volume

    def _intrabar_video_signal(self, *args, **kwargs):
        signal = super()._intrabar_video_signal(*args, **kwargs)
        signal.metadata["max_directional_signed_volume"] = self.max_directional_signed_volume
        signal.report_fields["max_directional_signed_volume"] = self.max_directional_signed_volume
        return signal
