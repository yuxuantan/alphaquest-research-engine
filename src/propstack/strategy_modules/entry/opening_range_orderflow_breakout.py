from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.utils.time import parse_time


class OpeningRangeOrderflowBreakoutEntry(OpeningRangeBreakoutEntry):
    name = "opening_range_orderflow_breakout"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.tick_size = float(params.get("tick_size", 0.25))
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")

        self.breakout_buffer = self.tick_size * int(params.get("breakout_buffer_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")

        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")

        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")

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
        if close is None:
            return None

        direction, breakout_level, level_type = self._breakout_trigger(close, opening_range)
        if direction is None:
            return None

        flow = self._confirmation_flow(confirmation_bars or [bar])
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        confirmation_start = confirmation_bars[0]["timestamp"] if confirmation_bars else bar["timestamp"]
        confirmation_end = self._bar_close_timestamp(bar["timestamp"])
        if confirmation_end.time() >= parse_time(self.params.get("last_entry_time", "12:00:00")):
            return None

        confirmation_high = max(float(confirmation_bar["high"]) for confirmation_bar in confirmation_bars)
        confirmation_low = min(float(confirmation_bar["low"]) for confirmation_bar in confirmation_bars)
        trigger_side = "upside" if direction == "long" else "downside"
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
                "trigger_side": trigger_side,
                "flow_mode": self.flow_mode,
                "confirmation_signed_volume": signed_volume,
                "confirmation_flow_volume": total_volume,
                "confirmation_orderflow_imbalance": imbalance,
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
                "trigger_side": trigger_side,
                "flow_mode": self.flow_mode,
                "confirmation_signed_volume": signed_volume,
                "confirmation_flow_volume": total_volume,
                "confirmation_orderflow_imbalance": imbalance,
            },
        )

    def _breakout_trigger(
        self,
        close: float,
        opening_range: dict,
    ) -> tuple[str | None, float | None, str | None]:
        high = float(opening_range["high"])
        low = float(opening_range["low"])
        if close > high + self.breakout_buffer and self.params.get("allow_long", True):
            return "long", high, "opening_range_high_orderflow_breakout"
        if close < low - self.breakout_buffer and self.params.get("allow_short", True):
            return "short", low, "opening_range_low_orderflow_breakout"
        return None, None, None

    def _confirmation_flow(self, bars: list[pd.Series]) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_values = []
        total_values = []
        for bar in bars:
            signed = _finite_float(bar.get(signed_col))
            total = _finite_float(bar.get(total_col))
            if signed is None or total is None:
                return None
            signed_values.append(signed)
            total_values.append(total)
        signed_sum = float(sum(signed_values))
        total_sum = float(sum(total_values))
        if not math.isfinite(total_sum) or total_sum <= 0:
            return None
        imbalance = signed_sum / total_sum
        if not math.isfinite(imbalance):
            return None
        return signed_sum, total_sum, imbalance


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
