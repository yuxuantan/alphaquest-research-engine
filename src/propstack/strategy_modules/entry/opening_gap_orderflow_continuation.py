from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.opening_gap_orderflow_fade import (
    OpeningGapOrderflowFadeEntry,
    _finite_float,
    _orderflow_metrics,
)


class OpeningGapOrderflowContinuationEntry(OpeningGapOrderflowFadeEntry):
    name = "opening_gap_orderflow_continuation"

    def __init__(self, params: dict):
        super().__init__(params)
        self.hold_buffer = self.tick_size * int(params.get("hold_buffer_ticks", 0))
        self.min_source_return_ticks = float(params.get("min_source_return_ticks", 0.0))
        if self.min_source_return_ticks < 0:
            raise ValueError("min_source_return_ticks must be non-negative.")

    def _signal(self, state: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        opening = state.get("opening")
        source = state.get("source_window")
        if not opening or not source or not self._window_complete(source):
            return None

        prev_close = float(opening["prev_rth_close"])
        opening_price = float(opening["open"])
        gap_points = opening_price - prev_close
        gap_ticks = gap_points / self.tick_size
        if abs(gap_ticks) < self.min_opening_gap_ticks:
            return None
        if not self._gap_held(gap_ticks, prev_close, source):
            return None

        source_open = float(source["open"])
        source_close = float(source["close"])
        source_return_points = source_close - source_open
        source_return_ticks = source_return_points / self.tick_size
        if gap_ticks > 0 and source_return_ticks < self.min_source_return_ticks:
            return None
        if gap_ticks < 0 and source_return_ticks > -self.min_source_return_ticks:
            return None

        metrics = _orderflow_metrics(source)
        primary, secondary = self._flow_values(metrics)
        if primary is None:
            return None

        direction = self._direction(gap_ticks, primary, secondary)
        if direction is None:
            return None

        report_fields = {
            "academic_source_key": "opening_gap_hold_orderflow_continuation",
            "setup_mode": self.setup_mode,
            "feature_method": "sierra_opening_gap_orderflow_continuation",
            "direction_mode": self.direction_mode,
            "flow_mode": self.flow_mode,
            "prev_rth_close": prev_close,
            "rth_open": opening_price,
            "opening_gap_points": gap_points,
            "opening_gap_ticks": gap_ticks,
            "opening_gap_direction": "up" if gap_ticks > 0 else "down",
            "source_window_start_timestamp": source["start_timestamp"],
            "source_window_end_timestamp": source["end_timestamp"],
            "source_window_open": source_open,
            "source_window_high": float(source["high"]),
            "source_window_low": float(source["low"]),
            "source_window_close": source_close,
            "source_window_return_points": source_return_points,
            "source_window_return_ticks": source_return_ticks,
            "source_window_volume": float(source["volume"]),
            "source_window_signed_volume": float(source["signed_volume"]),
            "source_window_imbalance": metrics["signed_imbalance"],
            "source_window_large10_imbalance": metrics["large10_imbalance"],
            "source_window_large20_imbalance": metrics["large20_imbalance"],
            "primary_orderflow_imbalance": primary,
            "secondary_orderflow_imbalance": secondary,
            "min_opening_gap_ticks": self.min_opening_gap_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "hold_buffer_ticks": int(self.hold_buffer / self.tick_size) if self.tick_size else 0,
            "min_source_return_ticks": self.min_source_return_ticks,
            "opening_gap_orderflow_signal_timestamp": signal_timestamp,
            "opening_gap_orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": prev_close,
            "sweep_timestamp": opening["timestamp"],
            "sweep_high": float(source["high"]),
            "sweep_low": float(source["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"opening_gap_orderflow_continuation_{self.setup_mode}",
            swept_level=prev_close,
            sweep_timestamp=opening["timestamp"],
            sweep_high=float(source["high"]),
            sweep_low=float(source["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "flow_mode": self.flow_mode,
                "opening_gap_ticks": gap_ticks,
                "primary_orderflow_imbalance": primary,
                "secondary_orderflow_imbalance": secondary,
                "hold_buffer_ticks": int(self.hold_buffer / self.tick_size) if self.tick_size else 0,
                "min_source_return_ticks": self.min_source_return_ticks,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, gap_ticks: float, primary: float, secondary: float | None) -> str | None:
        threshold = self.min_orderflow_imbalance
        long_ok = gap_ticks > 0 and primary >= threshold and (
            secondary is None or secondary >= threshold
        )
        short_ok = gap_ticks < 0 and primary <= -threshold and (
            secondary is None or secondary <= -threshold
        )
        if self.direction_mode in {"two_sided_continuation", "two_sided"}:
            if long_ok:
                return "long"
            if short_ok:
                return "short"
            return None
        if self.direction_mode in {"long_only_continuation", "long_only"}:
            return "long" if long_ok else None
        if self.direction_mode in {"short_only_continuation", "short_only"}:
            return "short" if short_ok else None
        raise ValueError(
            "opening_gap_orderflow_continuation direction_mode must be one of: "
            "two_sided_continuation, long_only_continuation, short_only_continuation."
        )

    def _gap_held(self, gap_ticks: float, prev_close: float, source: dict) -> bool:
        if gap_ticks > 0:
            return (_finite_float(source.get("low")) or float("-inf")) >= prev_close + self.hold_buffer
        return (_finite_float(source.get("high")) or float("inf")) <= prev_close - self.hold_buffer
