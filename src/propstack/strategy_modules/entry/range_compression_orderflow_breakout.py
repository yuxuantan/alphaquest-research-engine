from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.range_compression_breakout import RangeCompressionBreakoutEntry


class RangeCompressionOrderflowBreakoutEntry(RangeCompressionBreakoutEntry):
    name = "range_compression_orderflow_breakout"

    def __init__(self, params: dict):
        super().__init__(params)
        self.flow_mode = str(params.get("flow_mode", "signed")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.05))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.min_flow_volume < 0:
            raise ValueError("min_flow_volume must be non-negative.")

    def _signal_from_breakout(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        setup: dict,
        reference: dict,
    ) -> Signal | None:
        signal = super()._signal_from_breakout(bar, bar_close, setup, reference)
        if signal is None:
            return None

        imbalance, flow_volume, signed_volume = self._flow_values(bar)
        if imbalance is None or flow_volume is None or flow_volume < self.min_flow_volume:
            return None
        if signal.direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if signal.direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        signal.level_type = signal.level_type.replace(
            "range_compression_", "range_compression_orderflow_"
        )
        signal.metadata.update(
            {
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "orderflow_volume": flow_volume,
                "orderflow_signed_volume": signed_volume,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
            }
        )
        signal.report_fields.update(
            {
                "feature_method": "range_compression_breakout_with_completed_bar_orderflow",
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "orderflow_volume": flow_volume,
                "orderflow_signed_volume": signed_volume,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "min_flow_volume": self.min_flow_volume,
            }
        )
        return signal

    def _flow_values(self, bar: pd.Series) -> tuple[float | None, float | None, float | None]:
        if self.flow_mode in {"signed", "signed_volume", "all_volume"}:
            signed = _finite_float(bar.get("signed_volume"))
            volume = _finite_float(bar.get("volume"))
        elif self.flow_mode in {"large10", "large10_imbalance"}:
            signed = _finite_float(bar.get("large10_signed_volume"))
            volume = _finite_float(bar.get("large10_volume"))
        elif self.flow_mode in {"large20", "large20_imbalance"}:
            signed = _finite_float(bar.get("large20_signed_volume"))
            volume = _finite_float(bar.get("large20_volume"))
        else:
            raise ValueError(
                "flow_mode must be one of: signed, signed_volume, all_volume, "
                "large10, large10_imbalance, large20, large20_imbalance."
            )
        if signed is None or volume is None or volume <= 0:
            return None, volume, signed
        imbalance = signed / volume
        return (imbalance if math.isfinite(imbalance) else None), volume, signed


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
