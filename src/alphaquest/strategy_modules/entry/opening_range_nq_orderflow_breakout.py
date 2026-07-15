from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.opening_range_orderflow_breakout import (
    OpeningRangeOrderflowBreakoutEntry,
)


class OpeningRangeNqOrderflowBreakoutEntry(OpeningRangeOrderflowBreakoutEntry):
    name = "opening_range_nq_orderflow_breakout"

    def __init__(self, params: dict):
        super().__init__(params)
        self.nq_lookback_minutes = int(params.get("nq_lookback_minutes", 15))
        self.min_nq_return_bps = float(params.get("min_nq_return_bps", 4.0))
        self.min_nq_lead_gap_bps = float(params.get("min_nq_lead_gap_bps", 1.0))
        if self.nq_lookback_minutes <= 0:
            raise ValueError("entry.params.nq_lookback_minutes must be greater than 0.")
        if self.min_nq_return_bps < 0 or self.min_nq_lead_gap_bps < 0:
            raise ValueError("entry.params.min_nq_return_bps and min_nq_lead_gap_bps must be non-negative.")

    def _confirmation_signal(self, bar: pd.Series, opening_range: dict | None, confirmation_bars: list[pd.Series]):
        signal = super()._confirmation_signal(bar, opening_range, confirmation_bars)
        if signal is None:
            return None

        leadership = self._nq_leadership(bar, signal.direction)
        if leadership is None:
            return None

        signal.level_type = f"{signal.level_type}_nq_lead_confirmed"
        signal.metadata.update(leadership)
        signal.report_fields.update(leadership)
        return signal

    def _nq_leadership(self, bar: pd.Series, direction: str) -> dict | None:
        suffix = str(self.nq_lookback_minutes)
        nq_return = _finite_float(bar.get(f"nq_return_bps_{suffix}"))
        es_return = _finite_float(bar.get(f"es_return_bps_{suffix}"))
        if nq_return is None or es_return is None:
            return None

        if direction == "long":
            lead_gap = nq_return - es_return
            if nq_return < self.min_nq_return_bps or lead_gap < self.min_nq_lead_gap_bps:
                return None
        elif direction == "short":
            lead_gap = es_return - nq_return
            if nq_return > -self.min_nq_return_bps or lead_gap < self.min_nq_lead_gap_bps:
                return None
        else:
            return None

        return {
            "cross_index_filter": "nq_leads_es_in_breakout_direction",
            "nq_lookback_minutes": self.nq_lookback_minutes,
            "nq_return_bps": nq_return,
            "es_return_bps": es_return,
            "nq_directional_lead_gap_bps": lead_gap,
            "min_nq_return_bps": self.min_nq_return_bps,
            "min_nq_lead_gap_bps": self.min_nq_lead_gap_bps,
        }


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
