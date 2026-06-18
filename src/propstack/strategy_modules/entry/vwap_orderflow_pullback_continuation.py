from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.vwap_pullback_continuation import VwapPullbackContinuationEntry


class VwapOrderflowPullbackContinuationEntry(VwapPullbackContinuationEntry):
    name = "vwap_orderflow_pullback_continuation"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")

    def _signal(self, direction: str, bar: pd.Series, pullback: dict, vwap: float, state: dict) -> Signal | None:
        flow = self._confirmation_flow(bar)
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        signal = super()._signal(direction, bar, pullback, vwap, state)
        signal.level_type = f"vwap_orderflow_{self.setup_mode}"
        flow_fields = {
            "flow_mode": self.flow_mode,
            "confirmation_signed_volume": signed_volume,
            "confirmation_flow_volume": total_volume,
            "confirmation_orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_flow_volume": self.min_flow_volume,
        }
        signal.metadata.update(flow_fields)
        signal.report_fields.update(flow_fields)
        return signal

    def _confirmation_flow(self, bar: pd.Series) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_volume = _finite_float(bar.get(signed_col))
        total_volume = _finite_float(bar.get(total_col))
        if signed_volume is None or total_volume is None or total_volume <= 0:
            return None
        imbalance = signed_volume / total_volume
        if not math.isfinite(imbalance):
            return None
        return signed_volume, total_volume, imbalance


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
