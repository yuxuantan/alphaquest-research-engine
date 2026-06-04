from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.utils.time import parse_time


class OpeningRangeInverseBreakoutEntry(OpeningRangeBreakoutEntry):
    name = "opening_range_inverse_breakout"

    def _confirmation_signal(
        self,
        bar: pd.Series,
        opening_range: dict | None,
        confirmation_bars: list[pd.Series],
    ) -> Signal | None:
        if opening_range is None:
            return None
        if bar["timestamp"].time() >= parse_time(self.params.get("last_entry_time", "12:00:00")):
            return None

        close = float(bar["close"])
        direction = None
        breakout_level = None
        level_type = None
        if close < opening_range["low"] and self.params.get("allow_long", True):
            if self.params.get("skip_tuesday_longs", True) and self._is_tuesday(bar):
                return None
            direction = "long"
            breakout_level = opening_range["low"]
            level_type = "opening_range_low_inverse"
        elif close > opening_range["high"] and self.params.get("allow_short", True):
            direction = "short"
            breakout_level = opening_range["high"]
            level_type = "opening_range_high_inverse"

        if direction is None:
            return None

        confirmation_start = confirmation_bars[0]["timestamp"] if confirmation_bars else bar["timestamp"]
        confirmation_end = self._bar_close_timestamp(bar["timestamp"])
        if confirmation_end.time() >= parse_time(self.params.get("last_entry_time", "12:00:00")):
            return None
        confirmation_high = max(float(confirmation_bar["high"]) for confirmation_bar in confirmation_bars)
        confirmation_low = min(float(confirmation_bar["low"]) for confirmation_bar in confirmation_bars)
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=breakout_level,
            sweep_timestamp=opening_range["start_timestamp"],
            sweep_high=opening_range["high"],
            sweep_low=opening_range["low"],
            reclaim_timestamp=bar["timestamp"],
            opening_range_high=opening_range["high"],
            opening_range_low=opening_range["low"],
            opening_range_open=opening_range["open"],
            opening_range_width=opening_range["width"],
            breakout_level=breakout_level,
            metadata={
                "opening_range_end_timestamp": opening_range["end_timestamp"],
                "opening_range_width_pct_of_open": opening_range["width_pct_of_open"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "confirmation_high": confirmation_high,
                "confirmation_low": confirmation_low,
                "confirmation_close": close,
                "breakout_timestamp": confirmation_end,
                "inverse_breakout": True,
            },
            report_fields={
                "opening_range_start_timestamp": opening_range["start_timestamp"],
                "opening_range_end_timestamp": opening_range["end_timestamp"],
                "opening_range_high": opening_range["high"],
                "opening_range_low": opening_range["low"],
                "opening_range_open": opening_range["open"],
                "opening_range_width": opening_range["width"],
                "opening_range_width_pct_of_open": opening_range["width_pct_of_open"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "breakout_timestamp": confirmation_end,
                "breakout_level": breakout_level,
            },
        )
