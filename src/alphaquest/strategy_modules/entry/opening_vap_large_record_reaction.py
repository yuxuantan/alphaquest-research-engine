from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.opening_vap_absorption_reaction import (
    OpeningVapAbsorptionReactionEntry,
    _finite_float,
)


class OpeningVapLargeRecordReactionEntry(OpeningVapAbsorptionReactionEntry):
    name = "opening_vap_large_record_reaction"

    _MODES = {
        "opening30_large_record_value_trap_two_sided",
        "opening60_large_record_value_trap_two_sided",
        "opening30_large_record_poc_reclaim_two_sided",
        "opening60_large_record_poc_reclaim_two_sided",
        "opening30_large_record_lvn_trap_two_sided",
        "opening60_large_record_lvn_trap_two_sided",
        "opening30_large_record_value_acceptance_two_sided",
        "opening60_large_record_value_acceptance_two_sided",
        "opening30_large_record_poc_acceptance_two_sided",
        "opening60_large_record_poc_acceptance_two_sided",
        "opening30_large_record_lvn_acceptance_two_sided",
        "opening60_large_record_lvn_acceptance_two_sided",
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_large200_record_volume = float(params.get("min_large200_record_volume", 200))
        self.min_large200_signed_share = float(params.get("min_large200_signed_share", 0.0))
        self.large_record_total_volume_col = str(
            params.get("large_record_total_volume_col", "large200_record_volume")
        )
        self.large_record_signed_volume_col = str(
            params.get("large_record_signed_volume_col", "large200_record_signed_volume")
        )
        self.large_record_max_volume_col = str(
            params.get("large_record_max_volume_col", "large200_record_max_volume")
        )
        self.large_record_count_col = str(params.get("large_record_count_col", "large200_record_count"))
        self._active_large_record: dict | None = None
        self._validate_large_record_params()

    def _candidates(self, profile: dict) -> list[tuple[str, str, float, str]]:
        if self.setup_mode.endswith("poc_acceptance_two_sided"):
            return [
                ("long", "poc", profile["poc"], "acceptance"),
                ("short", "poc", profile["poc"], "acceptance"),
            ]
        if self.setup_mode.endswith("lvn_acceptance_two_sided"):
            return [
                ("long", "lvn_near_high", profile["lvn_near_high"], "acceptance"),
                ("short", "lvn_near_low", profile["lvn_near_low"], "acceptance"),
            ]
        return super()._candidates(profile)

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        self._active_large_record = self._large_record_state(bar)
        try:
            if self._active_large_record is None:
                return None
            return super()._signal_from_completed_bar(bar)
        finally:
            self._active_large_record = None

    def _trap_confirms(
        self,
        direction: str,
        level: float,
        bar: pd.Series,
        open_price: float,
        high: float,
        low: float,
        close: float,
        imbalance: float,
    ) -> bool:
        if not self._large_record_side_confirms(direction, "trap"):
            return False
        return super()._trap_confirms(direction, level, bar, open_price, high, low, close, imbalance)

    def _acceptance_confirms(
        self,
        direction: str,
        level: float,
        bar: pd.Series,
        open_price: float,
        high: float,
        low: float,
        close: float,
        imbalance: float,
    ) -> bool:
        if not self._large_record_side_confirms(direction, "acceptance"):
            return False
        return super()._acceptance_confirms(direction, level, bar, open_price, high, low, close, imbalance)

    def _signal(
        self,
        direction: str,
        boundary_type: str,
        boundary: float,
        reaction_type: str,
        profile: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        imbalance: float,
    ) -> Signal:
        signal = super()._signal(
            direction,
            boundary_type,
            boundary,
            reaction_type,
            profile,
            bar,
            signal_timestamp,
            imbalance,
        )
        large_record = self._active_large_record or {}
        fields = {
            "large_record_reaction_model": reaction_type,
            "min_large200_record_volume": self.min_large200_record_volume,
            "min_large200_signed_share": self.min_large200_signed_share,
            "large200_record_max_volume": large_record.get("max_volume"),
            "large200_record_volume": large_record.get("total_volume"),
            "large200_record_signed_volume": large_record.get("signed_volume"),
            "large200_record_signed_share": large_record.get("signed_share"),
            "large200_record_count": large_record.get("record_count"),
            "large200_record_dominant_side": large_record.get("dominant_side"),
            "source_quality_label": "Sierra SCID large-record proxy; not vendor-equivalent print data",
        }
        signal.level_type = f"{signal.level_type}_large200_record"
        signal.metadata.update(fields)
        signal.report_fields.update(fields)
        return signal

    def _large_record_state(self, bar: pd.Series) -> dict | None:
        max_volume = _finite_float(bar.get(self.large_record_max_volume_col))
        total_volume = _finite_float(bar.get(self.large_record_total_volume_col))
        signed_volume = _finite_float(bar.get(self.large_record_signed_volume_col))
        record_count = _finite_float(bar.get(self.large_record_count_col)) or 0.0
        if (
            max_volume is None
            or total_volume is None
            or signed_volume is None
            or max_volume < self.min_large200_record_volume
            or total_volume <= 0
            or signed_volume == 0
        ):
            return None
        signed_share = abs(signed_volume) / total_volume
        if not math.isfinite(signed_share) or signed_share < self.min_large200_signed_share:
            return None
        return {
            "max_volume": max_volume,
            "total_volume": total_volume,
            "signed_volume": signed_volume,
            "signed_share": signed_share,
            "record_count": record_count,
            "dominant_side": "buy" if signed_volume > 0 else "sell",
        }

    def _large_record_side_confirms(self, direction: str, reaction_type: str) -> bool:
        large_record = self._active_large_record
        if large_record is None:
            return False
        signed_volume = float(large_record["signed_volume"])
        if reaction_type == "trap":
            return signed_volume < 0 if direction == "long" else signed_volume > 0
        return signed_volume > 0 if direction == "long" else signed_volume < 0

    def _validate_large_record_params(self) -> None:
        if not math.isfinite(self.min_large200_record_volume) or self.min_large200_record_volume < 200:
            raise ValueError("entry.params.min_large200_record_volume must be at least 200.")
        if not math.isfinite(self.min_large200_signed_share) or not 0 <= self.min_large200_signed_share <= 1:
            raise ValueError("entry.params.min_large200_signed_share must be between 0 and 1.")
