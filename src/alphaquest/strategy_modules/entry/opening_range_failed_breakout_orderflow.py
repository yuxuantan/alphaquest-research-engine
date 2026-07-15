from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from alphaquest.utils.time import parse_time


class OpeningRangeFailedBreakoutOrderflowEntry(OpeningRangeBreakoutEntry):
    name = "opening_range_failed_breakout_orderflow"

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
        self.reclaim_buffer = self.tick_size * int(params.get("reclaim_buffer_ticks", 0))
        self.max_reclaim_bars = max(1, int(params.get("max_reclaim_bars", 3)))
        self.flow_lookback_bars = max(1, int(params.get("flow_lookback_bars", 1)))
        self.min_reclaim_orderflow_imbalance = float(params.get("min_reclaim_orderflow_imbalance", 0.0))
        if self.min_reclaim_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_reclaim_orderflow_imbalance must be non-negative.")
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")

    def _state(self, session_date):
        state = super()._state(session_date)
        state.setdefault("recent_bars", [])
        state.setdefault("failed_breakout", None)
        return state

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bar.get("is_rth", False):
            return None
        if trades_today >= int(self.params.get("max_trades_per_day", 1)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        rth_start = parse_time(self.params.get("rth_start", "09:30:00"))
        if timestamp.time() < rth_start:
            return None

        state = self._state(bar["session_date"])
        if state["completed"] or state["skip_day"]:
            return None

        elapsed_minutes = self._elapsed_minutes(timestamp, rth_start)
        if elapsed_minutes < 0:
            return None

        opening_minutes = float(self.params.get("opening_range_minutes", 5))
        opening_bar_count = self._bar_count(opening_minutes)

        if elapsed_minutes < opening_minutes:
            self._append_limited(state["or_bars"], bar, opening_bar_count)
            if len(state["or_bars"]) == opening_bar_count:
                state["opening_range"] = self._build_opening_range(state)
            return None

        if state["opening_range"] is None:
            if len(state["or_bars"]) == opening_bar_count:
                state["opening_range"] = self._build_opening_range(state)
            else:
                state["completed"] = True
                return None

        cutoff = parse_time(self.params.get("last_entry_time", "12:00:00"))
        if timestamp.time() >= cutoff:
            state["completed"] = True
            return None

        self._append_recent_bar(state["recent_bars"], bar)
        signal = self._failed_breakout_signal(bar, state)
        if signal is not None:
            state["completed"] = True
            return signal
        return None

    def _failed_breakout_signal(self, bar: pd.Series, state: dict) -> Signal | None:
        opening_range = state["opening_range"]
        close = _finite_float(bar.get("close"))
        if close is None or opening_range is None:
            return None

        failed = state.get("failed_breakout")
        if failed is None:
            state["failed_breakout"] = self._new_failed_breakout_candidate(bar, opening_range, close)
            return None

        failed["bars_since_breakout"] += 1
        failed["extreme_high"] = max(failed["extreme_high"], float(bar["high"]))
        failed["extreme_low"] = min(failed["extreme_low"], float(bar["low"]))
        if failed["bars_since_breakout"] > self.max_reclaim_bars:
            state["failed_breakout"] = self._new_failed_breakout_candidate(bar, opening_range, close)
            return None

        side = failed["side"]
        if side == "upside":
            if close > float(opening_range["high"]) - self.reclaim_buffer:
                return None
            if not self.params.get("allow_short", True):
                return None
            direction = "short"
            required_sign = -1
            level_type = "opening_range_upside_failed_breakout_reclaim"
            breakout_level = float(opening_range["high"])
        else:
            if close < float(opening_range["low"]) + self.reclaim_buffer:
                return None
            if not self.params.get("allow_long", True):
                return None
            direction = "long"
            required_sign = 1
            level_type = "opening_range_downside_failed_breakout_reclaim"
            breakout_level = float(opening_range["low"])

        flow = self._confirmation_flow(state["recent_bars"])
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None
        if required_sign == 1 and imbalance < self.min_reclaim_orderflow_imbalance:
            return None
        if required_sign == -1 and imbalance > -self.min_reclaim_orderflow_imbalance:
            return None

        confirmation_start = state["recent_bars"][0]["timestamp"] if state["recent_bars"] else bar["timestamp"]
        confirmation_end = self._bar_close_timestamp(bar["timestamp"])
        confirmation_high = max(float(item["high"]) for item in state["recent_bars"]) if state["recent_bars"] else float(bar["high"])
        confirmation_low = min(float(item["low"]) for item in state["recent_bars"]) if state["recent_bars"] else float(bar["low"])
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=breakout_level,
            sweep_timestamp=failed["breakout_timestamp"],
            sweep_high=failed["extreme_high"],
            sweep_low=failed["extreme_low"],
            reclaim_timestamp=bar["timestamp"],
            opening_range_high=opening_range["high"],
            opening_range_low=opening_range["low"],
            opening_range_open=opening_range["open"],
            opening_range_width=opening_range["width"],
            breakout_level=breakout_level,
            metadata={
                "opening_range_end_timestamp": opening_range["end_timestamp"],
                "opening_range_width_pct_of_open": opening_range["width_pct_of_open"],
                "failed_breakout_side": side,
                "failed_breakout_timestamp": failed["breakout_timestamp"],
                "bars_to_reclaim": failed["bars_since_breakout"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "confirmation_high": confirmation_high,
                "confirmation_low": confirmation_low,
                "confirmation_close": close,
                "flow_mode": self.flow_mode,
                "reclaim_signed_volume": signed_volume,
                "reclaim_flow_volume": total_volume,
                "reclaim_orderflow_imbalance": imbalance,
            },
            report_fields={
                "opening_range_start_timestamp": opening_range["start_timestamp"],
                "opening_range_end_timestamp": opening_range["end_timestamp"],
                "opening_range_high": opening_range["high"],
                "opening_range_low": opening_range["low"],
                "opening_range_open": opening_range["open"],
                "opening_range_width": opening_range["width"],
                "opening_range_width_pct_of_open": opening_range["width_pct_of_open"],
                "failed_breakout_side": side,
                "failed_breakout_timestamp": failed["breakout_timestamp"],
                "bars_to_reclaim": failed["bars_since_breakout"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "confirmation_high": confirmation_high,
                "confirmation_low": confirmation_low,
                "breakout_level": breakout_level,
                "flow_mode": self.flow_mode,
                "reclaim_signed_volume": signed_volume,
                "reclaim_flow_volume": total_volume,
                "reclaim_orderflow_imbalance": imbalance,
            },
        )

    def _new_failed_breakout_candidate(self, bar: pd.Series, opening_range: dict, close: float) -> dict | None:
        high = float(opening_range["high"])
        low = float(opening_range["low"])
        if close > high + self.breakout_buffer and self.params.get("allow_short", True):
            return {
                "side": "upside",
                "breakout_timestamp": self._bar_close_timestamp(bar["timestamp"]),
                "bars_since_breakout": 0,
                "extreme_high": float(bar["high"]),
                "extreme_low": float(bar["low"]),
            }
        if close < low - self.breakout_buffer and self.params.get("allow_long", True):
            return {
                "side": "downside",
                "breakout_timestamp": self._bar_close_timestamp(bar["timestamp"]),
                "bars_since_breakout": 0,
                "extreme_high": float(bar["high"]),
                "extreme_low": float(bar["low"]),
            }
        return None

    def _confirmation_flow(self, bars: list[pd.Series]) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_values = []
        total_values = []
        for bar in bars[-self.flow_lookback_bars :]:
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

    def _append_recent_bar(self, bars: list[pd.Series], bar: pd.Series) -> None:
        bars.append(bar)
        del bars[: max(0, len(bars) - self.flow_lookback_bars)]


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
