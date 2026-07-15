from __future__ import annotations

import math

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_trend_26 import YushTrend26Entry


class YushTrend30Entry(YushTrend26Entry):
    name = "yush_trend_30"

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_directional_signed_volume = float(params.get("min_directional_signed_volume", 250.0))
        if not math.isfinite(self.min_directional_signed_volume) or self.min_directional_signed_volume < 0:
            raise ValueError("entry.params.min_directional_signed_volume must be non-negative.")

    def _intrabar_trend_pullback_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not super()._intrabar_trend_pullback_confirms(direction, level, state):
            return False
        signed_volume = float(state.get("signed_volume", 0.0))
        if direction == "long":
            return signed_volume >= self.min_directional_signed_volume
        return signed_volume <= -self.min_directional_signed_volume

    def _intrabar_video_signal(self, *args, **kwargs) -> Signal:
        signal = super()._intrabar_video_signal(*args, **kwargs)
        signal.metadata["min_directional_signed_volume"] = self.min_directional_signed_volume
        signal.report_fields["min_directional_signed_volume"] = self.min_directional_signed_volume
        return signal
