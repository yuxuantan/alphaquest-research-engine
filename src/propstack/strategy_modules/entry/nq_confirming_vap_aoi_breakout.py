from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.true_vap_aoi_breakout_continuation import (
    TrueVapAoiBreakoutContinuationEntry,
)


class NqConfirmingVapAoiBreakoutEntry(TrueVapAoiBreakoutContinuationEntry):
    name = "nq_confirming_vap_aoi_breakout"

    _MODES = TrueVapAoiBreakoutContinuationEntry._MODES | {
        "all_market_vap_two_sided_breakout",
        "value_area_vap_two_sided_breakout",
        "lvn_vap_two_sided_breakout",
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.relative_value_window_minutes = int(params.get("relative_value_window_minutes", 30))
        self.min_nq_return_bps = float(params.get("min_nq_return_bps", 0.5))
        self.min_nq_signed_imbalance = float(params.get("min_nq_signed_imbalance", 0.01))
        self.max_nq_lag_bps = float(params.get("max_nq_lag_bps", 5.0))
        self.require_nq_flow_confirmation = bool(params.get("require_nq_flow_confirmation", True))
        self._validate_nq_confirmation_params()

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float]]:
        if self.setup_mode == "all_market_vap_two_sided_breakout":
            candidates = []
            for column, direction, aoi_type in [
                ("prev_rth_high", "long", "prior_rth_high"),
                ("prev_rth_low", "short", "prior_rth_low"),
                ("overnight_high", "long", "overnight_high"),
                ("overnight_low", "short", "overnight_low"),
            ]:
                level = _finite_float(bar.get(column))
                if level is not None:
                    candidates.append((direction, aoi_type, level))
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("long", "opening_range_high", opening["high"]))
                candidates.append(("short", "opening_range_low", opening["low"]))
            return candidates

        if self.setup_mode == "value_area_vap_two_sided_breakout":
            return self._profile_level_candidates(
                bar,
                [
                    ("prior_vap_vah", "long", "prior_vap_vah"),
                    ("prior_vap_val", "short", "prior_vap_val"),
                ],
            )

        if self.setup_mode == "lvn_vap_two_sided_breakout":
            return self._profile_level_candidates(
                bar,
                [
                    ("prior_vap_lvn_near_high", "long", "prior_vap_lvn_near_high"),
                    ("prior_vap_lvn_near_low", "short", "prior_vap_lvn_near_low"),
                ],
            )

        return super()._candidate_aois(bar)

    def _profile_level_candidates(
        self,
        bar: pd.Series,
        specs: list[tuple[str, str, str]],
    ) -> list[tuple[str, str, float]]:
        candidates = []
        for column, direction, aoi_type in specs:
            level = _finite_float(bar.get(column))
            if level is not None:
                candidates.append((direction, aoi_type, level))
        return candidates

    def _long_breakout_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        close: float,
        imbalance: float,
    ) -> bool:
        return super()._long_breakout_confirms(
            bar, level, open_price, high, close, imbalance
        ) and self._nq_confirms(bar, "long")

    def _short_breakout_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        low: float,
        close: float,
        imbalance: float,
    ) -> bool:
        return super()._short_breakout_confirms(
            bar, level, open_price, low, close, imbalance
        ) and self._nq_confirms(bar, "short")

    def _signal(
        self,
        direction: str,
        aoi_type: str,
        aoi_level: float,
        profile_match: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        imbalance: float,
    ) -> Signal:
        signal = super()._signal(
            direction,
            aoi_type,
            aoi_level,
            profile_match,
            bar,
            signal_timestamp,
            imbalance,
        )
        context = self._nq_context(bar)
        signal.level_type = f"nq_confirming_{signal.level_type}"
        signal.metadata.update(context)
        signal.report_fields.update(context)
        return signal

    def _nq_confirms(self, bar: pd.Series, direction: str) -> bool:
        context = self._nq_context(bar)
        nq_return = context["nq_return_bps"]
        nq_signed = context["nq_signed_imbalance"]
        lag = context["nq_minus_es_return_bps"]
        if nq_return is None or lag is None:
            return False
        if self.require_nq_flow_confirmation and nq_signed is None:
            return False

        if direction == "long":
            return_ok = nq_return >= self.min_nq_return_bps and lag >= -self.max_nq_lag_bps
            flow_ok = (
                not self.require_nq_flow_confirmation
                or nq_signed >= self.min_nq_signed_imbalance
            )
        elif direction == "short":
            return_ok = nq_return <= -self.min_nq_return_bps and lag <= self.max_nq_lag_bps
            flow_ok = (
                not self.require_nq_flow_confirmation
                or nq_signed <= -self.min_nq_signed_imbalance
            )
        else:
            return False
        return return_ok and flow_ok

    def _nq_context(self, bar: pd.Series) -> dict:
        window = self.relative_value_window_minutes
        return {
            "relative_value_filter": "nq_confirmation_of_es_vap_aoi_breakout",
            "relative_value_window_minutes": window,
            "es_return_bps": _finite_float(bar.get(f"es_return_bps_{window}")),
            "nq_return_bps": _finite_float(bar.get(f"nq_return_bps_{window}")),
            "nq_minus_es_return_bps": _finite_float(bar.get(f"nq_minus_es_return_bps_{window}")),
            "nq_signed_imbalance": _finite_float(bar.get(f"nq_signed_imbalance_{window}")),
            "min_nq_return_bps": self.min_nq_return_bps,
            "min_nq_signed_imbalance": self.min_nq_signed_imbalance,
            "max_nq_lag_bps": self.max_nq_lag_bps,
            "require_nq_flow_confirmation": self.require_nq_flow_confirmation,
        }

    def _validate(self) -> None:
        allowed_modes = self._MODES
        if self.setup_mode not in allowed_modes:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(allowed_modes)}.")
        original_modes = TrueVapAoiBreakoutContinuationEntry._MODES
        if self.setup_mode in original_modes:
            return super()._validate()

        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be positive.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be positive.")
        if self.opening_range_minutes < 1:
            raise ValueError("entry.params.opening_range_minutes must be at least one.")
        if self.max_profile_distance_ticks < 0:
            raise ValueError("entry.params.max_profile_distance_ticks must be non-negative.")
        if self.min_breakout_ticks < 0 or self.close_buffer_ticks < 0:
            raise ValueError("entry.params breakout ticks must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed_volume, signed, large10, or large20.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.min_footprint_imbalance_volume < 0:
            raise ValueError("entry.params.min_footprint_imbalance_volume must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")

    def _validate_nq_confirmation_params(self) -> None:
        if self.relative_value_window_minutes not in {5, 15, 30, 60}:
            raise ValueError("entry.params.relative_value_window_minutes must be one of 5, 15, 30, or 60.")
        if self.min_nq_return_bps < 0:
            raise ValueError("entry.params.min_nq_return_bps must be non-negative.")
        if self.min_nq_signed_imbalance < 0:
            raise ValueError("entry.params.min_nq_signed_imbalance must be non-negative.")
        if self.max_nq_lag_bps < 0:
            raise ValueError("entry.params.max_nq_lag_bps must be non-negative.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
