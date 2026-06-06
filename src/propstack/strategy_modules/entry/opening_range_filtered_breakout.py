from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.utils.time import parse_time


class OpeningRangeFilteredBreakoutEntry(OpeningRangeBreakoutEntry):
    name = "opening_range_filtered_breakout"

    _CONTINUATION_MODES = {"continuation", "volume_confirmed_breakout", "vwap_aligned_breakout"}
    _INVERSE_MODES = {"inverse_fade", "failed_break_fade"}
    _VWAP_FILTERS = {"none", "trade_aligned", "breakout_side"}

    def __init__(self, params: dict):
        super().__init__(params)
        self.setup_mode = str(params.get("setup_mode", "continuation")).lower()
        if self.setup_mode not in self._CONTINUATION_MODES | self._INVERSE_MODES:
            raise ValueError(
                "entry.params.setup_mode must be one of "
                f"{sorted(self._CONTINUATION_MODES | self._INVERSE_MODES)}."
            )

        self.vwap_filter = str(params.get("vwap_filter", "none")).lower()
        if self.vwap_filter not in self._VWAP_FILTERS:
            raise ValueError(f"entry.params.vwap_filter must be one of {sorted(self._VWAP_FILTERS)}.")

        self.tick_size = float(params.get("tick_size", 0.25))
        self.breakout_buffer = self.tick_size * int(params.get("breakout_buffer_ticks", 0))
        self.vwap_buffer = self.tick_size * int(params.get("vwap_buffer_ticks", 0))
        self.min_volume_ratio = float(params.get("min_volume_ratio", 0.0))

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

        close = _finite_float(bar.get("close"))
        if close is None or not self._passes_volume_filter(bar):
            return None

        direction, breakout_level, level_type, trigger_side = self._trigger(close, opening_range, bar)
        if direction is None:
            return None
        if not self._passes_vwap_filter(direction, trigger_side, close, bar):
            return None

        confirmation_start = confirmation_bars[0]["timestamp"] if confirmation_bars else bar["timestamp"]
        confirmation_end = self._bar_close_timestamp(bar["timestamp"])
        if confirmation_end.time() >= parse_time(self.params.get("last_entry_time", "12:00:00")):
            return None
        confirmation_high = max(float(confirmation_bar["high"]) for confirmation_bar in confirmation_bars)
        confirmation_low = min(float(confirmation_bar["low"]) for confirmation_bar in confirmation_bars)
        volume_ratio = _finite_float(bar.get("volume_ratio"))
        vwap = _finite_float(bar.get("vwap"))
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
                "setup_mode": self.setup_mode,
                "vwap_filter": self.vwap_filter,
                "trigger_side": trigger_side,
                "confirmation_volume_ratio": volume_ratio,
                "confirmation_vwap": vwap,
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
                "setup_mode": self.setup_mode,
                "trigger_side": trigger_side,
                "confirmation_volume_ratio": volume_ratio,
                "confirmation_vwap": vwap,
            },
        )

    def _trigger(self, close: float, opening_range: dict, bar: pd.Series) -> tuple[str | None, float | None, str | None, str | None]:
        high = float(opening_range["high"])
        low = float(opening_range["low"])
        upside_break = close > high + self.breakout_buffer
        downside_break = close < low - self.breakout_buffer
        continuation = self.setup_mode in self._CONTINUATION_MODES

        if continuation and upside_break and self.params.get("allow_long", True):
            if self.params.get("skip_tuesday_longs", True) and self._is_tuesday(bar):
                return None, None, None, None
            return "long", high, "opening_range_high_filtered", "upside"
        if continuation and downside_break and self.params.get("allow_short", True):
            return "short", low, "opening_range_low_filtered", "downside"
        if not continuation and downside_break and self.params.get("allow_long", True):
            if self.params.get("skip_tuesday_longs", True) and self._is_tuesday(bar):
                return None, None, None, None
            return "long", low, "opening_range_low_filtered_inverse", "downside"
        if not continuation and upside_break and self.params.get("allow_short", True):
            return "short", high, "opening_range_high_filtered_inverse", "upside"
        return None, None, None, None

    def _passes_volume_filter(self, bar: pd.Series) -> bool:
        if self.min_volume_ratio <= 0:
            return True
        volume_ratio = _finite_float(bar.get("volume_ratio"))
        return volume_ratio is not None and volume_ratio >= self.min_volume_ratio

    def _passes_vwap_filter(self, direction: str, trigger_side: str | None, close: float, bar: pd.Series) -> bool:
        if self.vwap_filter == "none":
            return True
        vwap = _finite_float(bar.get("vwap"))
        if vwap is None:
            return False
        if self.vwap_filter == "trade_aligned":
            if direction == "long":
                return close >= vwap + self.vwap_buffer
            return close <= vwap - self.vwap_buffer
        if trigger_side == "upside":
            return close >= vwap + self.vwap_buffer
        if trigger_side == "downside":
            return close <= vwap - self.vwap_buffer
        return False


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
