from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.pdh_pdl_breakout_continuation import (
    PdhPdlBreakoutContinuationEntry,
)


class PdhPdlOrderflowBreakoutContinuationEntry(PdhPdlBreakoutContinuationEntry):
    name = "pdh_pdl_orderflow_breakout_continuation"

    def __init__(self, params: dict):
        super().__init__(params)
        self.orderflow_mode = str(params.get("orderflow_mode", "signed")).lower()
        self.flow_confirmation = str(params.get("flow_confirmation", "aligned")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self._validate_orderflow_mode()

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        level: float,
        level_type: str,
        sweep_source,
        prev_high: float,
        prev_low: float,
        *,
        breakout: dict | None = None,
        gap: dict | None = None,
    ) -> Signal | None:
        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None
        if not self._flow_confirms(direction, imbalance):
            return None

        signal = super()._signal(
            direction,
            bar,
            level,
            level_type,
            sweep_source,
            prev_high,
            prev_low,
            breakout=breakout,
            gap=gap,
        )
        if signal is None:
            return None
        signal.metadata.update(
            {
                "orderflow_mode": self.orderflow_mode,
                "flow_confirmation": self.flow_confirmation,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
            }
        )
        signal.report_fields.update(
            {
                "orderflow_mode": self.orderflow_mode,
                "flow_confirmation": self.flow_confirmation,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
            }
        )
        return signal

    def _flow_confirms(self, direction: str, imbalance: float) -> bool:
        threshold = self.min_orderflow_imbalance
        if self.flow_confirmation == "aligned":
            if direction == "long":
                return imbalance >= threshold
            return imbalance <= -threshold
        if direction == "long":
            return imbalance <= -threshold
        return imbalance >= threshold

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = {
            "signed": ("signed_volume", "volume"),
            "large10": ("large10_signed_volume", "large10_volume"),
            "large20": ("large20_signed_volume", "large20_volume"),
        }[self.orderflow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        return signed / volume

    def _validate_orderflow_mode(self) -> None:
        if self.orderflow_mode not in {"signed", "large10", "large20"}:
            raise ValueError(
                "entry.params.orderflow_mode must be one of: signed, large10, large20."
            )
        if self.flow_confirmation not in {"aligned", "absorbed"}:
            raise ValueError("entry.params.flow_confirmation must be 'aligned' or 'absorbed'.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
