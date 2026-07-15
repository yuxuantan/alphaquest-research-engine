from __future__ import annotations

from collections import deque
import math

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_trend_81 import YushTrend81Entry


class YushTrend82Entry(YushTrend81Entry):
    name = "yush_trend_82"

    def __init__(self, params: dict):
        super().__init__(params)
        self.compression_lookback_bars = int(params.get("compression_lookback_bars", 30))
        self.min_compression_history = int(params.get("min_compression_history", 12))
        self.max_value_area_width_rank = float(params.get("max_value_area_width_rank", 0.35))
        self._value_area_width_history: deque[float] = deque(maxlen=max(self.compression_lookback_bars, 1))
        self._latest_value_area_width: float | None = None
        self._latest_value_area_width_rank: float | None = None
        self._validate_trend82_params()

    def _roll_session(self, bar):
        previous = self._session_key
        super()._roll_session(bar)
        if self._session_key != previous:
            self._value_area_width_history = deque(maxlen=max(self.compression_lookback_bars, 1))
            self._latest_value_area_width = None
            self._latest_value_area_width_rank = None

    def _profile_is_balanced(self, profile: dict) -> bool:
        width = float(profile["vah"]) - float(profile["val"])
        self._latest_value_area_width = width if width > 0 else None
        self._latest_value_area_width_rank = None
        try:
            if width <= 0:
                return False
            history = [value for value in self._value_area_width_history if math.isfinite(value)]
            if len(history) < self.min_compression_history:
                return False
            rank = sum(1 for value in history if value <= width) / len(history)
            self._latest_value_area_width_rank = rank
            return rank <= self.max_value_area_width_rank
        finally:
            if width > 0 and math.isfinite(width):
                self._value_area_width_history.append(width)

    def _signal(self, **kwargs) -> Signal | None:
        signal = super()._signal(**kwargs)
        if signal is None:
            return None
        fields = {
            "compression_branch": True,
            "compression_lookback_bars": self.compression_lookback_bars,
            "min_compression_history": self.min_compression_history,
            "value_area_width": self._latest_value_area_width,
            "value_area_width_rank": self._latest_value_area_width_rank,
            "max_value_area_width_rank": self.max_value_area_width_rank,
            "target_reference": "fixed_dollar_negative_rr_compression_breakout",
        }
        signal.metadata.update(fields)
        signal.report_fields.update(fields)
        return signal

    def _validate_trend82_params(self) -> None:
        if self.compression_lookback_bars < 2:
            raise ValueError("entry.params.compression_lookback_bars must be at least 2.")
        if self.min_compression_history < 1 or self.min_compression_history > self.compression_lookback_bars:
            raise ValueError("entry.params.min_compression_history must be between 1 and compression_lookback_bars.")
        if not math.isfinite(self.max_value_area_width_rank) or not 0 <= self.max_value_area_width_rank <= 1:
            raise ValueError("entry.params.max_value_area_width_rank must be between 0 and 1.")
