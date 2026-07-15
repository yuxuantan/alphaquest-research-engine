from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.profile_aoi_footprint_trap import (
    ProfileAoiFootprintTrapEntry,
)


class NqNonconfirmingVapAoiTrapEntry(ProfileAoiFootprintTrapEntry):
    name = "nq_nonconfirming_vap_aoi_trap"
    _MODES = ProfileAoiFootprintTrapEntry._MODES | {"all_market_profile_two_sided_trap"}

    def __init__(self, params: dict):
        super().__init__(params)
        self.relative_value_window_minutes = int(params.get("relative_value_window_minutes", 30))
        self.min_nq_es_return_gap_bps = float(params.get("min_nq_es_return_gap_bps", 2.0))
        self.require_nq_flow_nonconfirmation = bool(params.get("require_nq_flow_nonconfirmation", False))
        self.min_nq_es_flow_gap = float(params.get("min_nq_es_flow_gap", 0.0))
        self.profile_context_mode = str(params.get("profile_context_mode", "level_confluence")).lower()
        self.require_footprint_absorption = bool(params.get("require_footprint_absorption", True))
        self._validate_nq_params()

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float]]:
        if self.setup_mode != "all_market_profile_two_sided_trap":
            return super()._candidate_aois(bar)
        candidates = super()._candidate_aois(bar)
        low = _finite_float(bar.get("overnight_low"))
        high = _finite_float(bar.get("overnight_high"))
        if low is not None:
            candidates.append(("long", "overnight_low", low))
        if high is not None:
            candidates.append(("short", "overnight_high", high))
        return candidates

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        volume = _finite_float(bar.get("volume"))
        if None in {high, low, open_price, close} or volume is None or volume <= 0:
            return None

        for direction, aoi_type, aoi_level in self._candidate_aois(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            profile_match = self._profile_context(direction, aoi_level, bar)
            if profile_match is None:
                continue
            if direction == "long":
                if self._long_trap_confirms(bar, aoi_level, open_price, low, close):
                    return self._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp)
            else:
                if self._short_trap_confirms(bar, aoi_level, open_price, high, close):
                    return self._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp)
        return None

    def _long_trap_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        low: float,
        close: float,
    ) -> bool:
        if not self._basic_long_reclaim_confirms(bar, level, open_price, low, close):
            return False
        if self.require_footprint_absorption and not super()._long_trap_confirms(bar, level, open_price, low, close):
            return False
        return self._nq_nonconfirms(bar, "long")

    def _short_trap_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        close: float,
    ) -> bool:
        if not self._basic_short_reclaim_confirms(bar, level, open_price, high, close):
            return False
        if self.require_footprint_absorption and not super()._short_trap_confirms(bar, level, open_price, high, close):
            return False
        return self._nq_nonconfirms(bar, "short")

    def _signal(
        self,
        direction: str,
        aoi_type: str,
        aoi_level: float,
        profile_match: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        signal = super()._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp)
        context = self._nq_context(bar)
        signal.level_type = f"nq_nonconfirming_{signal.level_type}"
        signal.metadata.update(context)
        signal.report_fields.update(context)
        return signal

    def _profile_context(self, direction: str, aoi_level: float, bar: pd.Series) -> dict | None:
        if self.profile_context_mode == "level_confluence":
            return super()._nearest_profile_level(aoi_level, bar)

        if self.profile_source == "cached_prior_vap":
            prefix = self.cached_profile_prefix
            poc = _finite_float(bar.get(f"{prefix}_poc"))
            vah = _finite_float(bar.get(f"{prefix}_vah"))
            val = _finite_float(bar.get(f"{prefix}_val"))
            profile_session = _finite_float(bar.get(f"{prefix}_session_yyyymmdd"))
            profile_total_volume = _finite_float(bar.get(f"{prefix}_total_volume"))
            profile_bars = _finite_float(bar.get(f"{prefix}_price_levels"))
        else:
            profile = self.prior_profile
            if profile is None:
                return None
            poc = _finite_float(profile.get("poc"))
            vah = _finite_float(profile.get("vah"))
            val = _finite_float(profile.get("val"))
            profile_session = profile.get("session_date")
            profile_total_volume = profile.get("total_volume")
            profile_bars = profile.get("bar_count")
        if poc is None or vah is None or val is None:
            return None

        distance_reference = poc
        if direction == "long":
            if self.profile_context_mode == "beyond_poc" and aoi_level > poc:
                return None
            if self.profile_context_mode == "outside_value" and aoi_level > val:
                return None
            if self.profile_context_mode == "near_side_value" and aoi_level > val + self.max_profile_distance_ticks * self.tick_size:
                return None
            distance_reference = val
        else:
            if self.profile_context_mode == "beyond_poc" and aoi_level < poc:
                return None
            if self.profile_context_mode == "outside_value" and aoi_level < vah:
                return None
            if self.profile_context_mode == "near_side_value" and aoi_level < vah - self.max_profile_distance_ticks * self.tick_size:
                return None
            distance_reference = vah

        return {
            "profile_level_type": self.profile_context_mode,
            "profile_level_price": distance_reference,
            "profile_distance_ticks": abs(aoi_level - distance_reference) / self.tick_size,
            "prior_profile_session": profile_session,
            "prior_profile_total_volume": profile_total_volume,
            "prior_profile_bars": profile_bars,
        }

    def _basic_long_reclaim_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        low: float,
        close: float,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        return (
            self._adverse_delta_imbalance(bar, "long")
            and low <= level - probe
            and close >= level + confirm
            and close > open_price
        )

    def _basic_short_reclaim_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        close: float,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        return (
            self._adverse_delta_imbalance(bar, "short")
            and high >= level + probe
            and close <= level - confirm
            and close < open_price
        )

    def _nq_nonconfirms(self, bar: pd.Series, direction: str) -> bool:
        context = self._nq_context(bar)
        spread = context["nq_minus_es_return_bps"]
        if spread is None:
            return False
        if direction == "long":
            return_ok = spread >= self.min_nq_es_return_gap_bps
        elif direction == "short":
            return_ok = spread <= -self.min_nq_es_return_gap_bps
        else:
            return False
        if not return_ok:
            return False
        if not self.require_nq_flow_nonconfirmation:
            return True
        flow_gap = context["nq_minus_es_signed_imbalance"]
        if flow_gap is None:
            return False
        if direction == "long":
            return flow_gap >= self.min_nq_es_flow_gap
        return flow_gap <= -self.min_nq_es_flow_gap

    def _nq_context(self, bar: pd.Series) -> dict:
        window = self.relative_value_window_minutes
        return {
            "relative_value_filter": "nq_nonconfirmation_of_es_aoi_extension",
            "relative_value_window_minutes": window,
            "es_return_bps": _finite_float(bar.get(f"es_return_bps_{window}")),
            "nq_return_bps": _finite_float(bar.get(f"nq_return_bps_{window}")),
            "nq_minus_es_return_bps": _finite_float(bar.get(f"nq_minus_es_return_bps_{window}")),
            "min_nq_es_return_gap_bps": self.min_nq_es_return_gap_bps,
            "require_nq_flow_nonconfirmation": self.require_nq_flow_nonconfirmation,
            "nq_minus_es_signed_imbalance": _finite_float(
                bar.get(f"nq_minus_es_signed_imbalance_{window}")
            ),
            "min_nq_es_flow_gap": self.min_nq_es_flow_gap,
        }

    def _validate_nq_params(self) -> None:
        if self.relative_value_window_minutes not in {5, 15, 30, 60}:
            raise ValueError("entry.params.relative_value_window_minutes must be one of 5, 15, 30, or 60.")
        if self.min_nq_es_return_gap_bps < 0:
            raise ValueError("entry.params.min_nq_es_return_gap_bps must be non-negative.")
        if self.min_nq_es_flow_gap < 0:
            raise ValueError("entry.params.min_nq_es_flow_gap must be non-negative.")
        allowed_context = {"level_confluence", "beyond_poc", "outside_value", "near_side_value"}
        if self.profile_context_mode not in allowed_context:
            raise ValueError(f"entry.params.profile_context_mode must be one of {sorted(allowed_context)}.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
