from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.round_number_barrier import RoundNumberBarrierEntry


class RoundNumberOrderflowBarrierEntry(RoundNumberBarrierEntry):
    name = "round_number_orderflow_barrier"

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

        self.flow_confirmation = str(params.get("flow_confirmation", "aligned")).lower()
        if self.flow_confirmation not in {"aligned", "absorbed"}:
            raise ValueError("entry.params.flow_confirmation must be 'aligned' or 'absorbed'.")

        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")

        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")

    def _signal(self, direction: str, bar: pd.Series, barrier: float, level_type: str) -> Signal | None:
        flow = self._confirmation_flow(bar)
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None
        if not self._flow_confirms(direction, imbalance):
            return None

        signal = super()._signal(direction, bar, barrier, level_type)
        signal.level_type = f"round_number_orderflow_{level_type}"
        flow_fields = {
            "flow_mode": self.flow_mode,
            "flow_confirmation": self.flow_confirmation,
            "confirmation_signed_volume": signed_volume,
            "confirmation_flow_volume": total_volume,
            "confirmation_orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_flow_volume": self.min_flow_volume,
        }
        signal.metadata.update(flow_fields)
        signal.report_fields.update(flow_fields)
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
