from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.profile_aoi_footprint_trap import (
    ProfileAoiFootprintTrapEntry,
    _finite_float,
)


class VideoExactOrderflowPlaybookEntry(ProfileAoiFootprintTrapEntry):
    name = "video_exact_orderflow_playbook"

    _MODES = {
        "model1_range_value_edge_two_sided",
        "model1_range_value_edge_long",
        "model1_range_value_edge_short",
        "model2_trend_lvn_two_sided",
        "model2_trend_lvn_long",
        "model2_trend_lvn_short",
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_aoi_confluences = int(params.get("min_aoi_confluences", 2))
        self.market_aoi_max_distance_ticks = float(
            params.get("market_aoi_max_distance_ticks", self.max_profile_distance_ticks)
        )
        self.aoi_reach_tolerance_ticks = float(params.get("aoi_reach_tolerance_ticks", 4))
        self.min_large200_record_volume = float(params.get("min_large200_record_volume", 200))
        self.min_delta_activity_imbalance = float(params.get("min_delta_activity_imbalance", 0.03))
        self.min_directional_delta_imbalance = float(params.get("min_directional_delta_imbalance", 0.0))
        self.min_structure_bars = int(params.get("min_structure_bars", 10))
        self.min_trend_move_ticks = float(params.get("min_trend_move_ticks", 8))
        self.allow_opening_range_proxy = bool(params.get("allow_opening_range_proxy", False))
        self.target_reference = str(params.get("target_reference", "structural_or_midpoint")).lower()
        self._validate_exact_video_params()

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

        profile = self._active_profile(bar) or {}
        if not profile:
            return None

        for direction, model, level_type, level in self._candidate_setups(bar, profile, close):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            confluence = self._aoi_confluence(bar, profile, direction, model, level)
            if len(confluence["criteria"]) < self.min_aoi_confluences:
                continue
            if model == "range":
                confirms = self._range_trap_confirms(direction, bar, level, open_price, high, low, close)
            else:
                confirms = self._trend_pullback_confirms(direction, bar, level, open_price, high, low, close)
            if not confirms:
                continue
            return self._video_signal(
                direction=direction,
                model=model,
                level_type=level_type,
                level=level,
                profile=profile,
                confluence=confluence,
                bar=bar,
                signal_timestamp=signal_timestamp,
            )
        return None

    def _candidate_setups(
        self,
        bar: pd.Series,
        profile: dict,
        close: float,
    ) -> list[tuple[str, str, str, float]]:
        mode = self.setup_mode
        candidates: list[tuple[str, str, str, float]] = []
        if mode in {"model1_range_value_edge_two_sided", "model1_range_value_edge_long"}:
            val = _finite_float(profile.get("val"))
            if val is not None:
                candidates.append(("long", "range", "developing_value_area_low", val))
        if mode in {"model1_range_value_edge_two_sided", "model1_range_value_edge_short"}:
            vah = _finite_float(profile.get("vah"))
            if vah is not None:
                candidates.append(("short", "range", "developing_value_area_high", vah))
        if mode in {"model2_trend_lvn_two_sided", "model2_trend_lvn_long"}:
            if self._trend_state_confirms("long", close, profile):
                lvn = self._directional_lvn(profile, "long", close)
                if lvn is not None:
                    candidates.append(("long", "trend", lvn["type"], lvn["price"]))
        if mode in {"model2_trend_lvn_two_sided", "model2_trend_lvn_short"}:
            if self._trend_state_confirms("short", close, profile):
                lvn = self._directional_lvn(profile, "short", close)
                if lvn is not None:
                    candidates.append(("short", "trend", lvn["type"], lvn["price"]))
        return candidates

    def _trend_state_confirms(self, direction: str, close: float, profile: dict) -> bool:
        if len(self.current_session_bars) + 1 < self.min_structure_bars:
            return False
        if not self.current_session_bars:
            return False
        session_open = _finite_float(self.current_session_bars[0].get("open"))
        vah = _finite_float(profile.get("vah"))
        val = _finite_float(profile.get("val"))
        if session_open is None or vah is None or val is None:
            return False
        min_move = self.min_trend_move_ticks * self.tick_size
        if direction == "long":
            return close >= session_open + min_move and close >= vah
        return close <= session_open - min_move and close <= val

    def _directional_lvn(self, profile: dict, direction: str, close: float) -> dict | None:
        raw_levels = profile.get("levels") or []
        candidates = []
        for item in raw_levels:
            level_type = str(item.get("type", ""))
            if "lvn" not in level_type:
                continue
            price = _finite_float(item.get("price"))
            if price is None:
                continue
            if direction == "long" and price > close + self.aoi_reach_tolerance_ticks * self.tick_size:
                continue
            if direction == "short" and price < close - self.aoi_reach_tolerance_ticks * self.tick_size:
                continue
            candidates.append({"type": level_type, "price": price})
        if not candidates:
            return None
        best = min(candidates, key=lambda item: abs(item["price"] - close))
        if abs(best["price"] - close) > self.max_profile_distance_ticks * self.tick_size:
            return None
        return best

    def _aoi_confluence(
        self,
        bar: pd.Series,
        profile: dict,
        direction: str,
        model: str,
        level: float,
    ) -> dict:
        criteria = ["volume_profile"]
        details = {
            "aoi_volume_profile_level": float(level),
            "aoi_volume_profile_source": self.profile_source,
        }
        market = self._nearest_market_level(bar, level)
        if market is not None:
            criteria.append("market_level")
            details.update(market)
        large_record = self._large_record_state(bar)
        if large_record is not None and self._flow_side_confirms(direction, model, large_record["signed_volume"]):
            criteria.append("big_trades")
            details.update(
                {
                    "large200_record_max_volume": large_record["max_volume"],
                    "large200_record_volume": large_record["total_volume"],
                    "large200_record_signed_volume": large_record["signed_volume"],
                    "large200_record_count": large_record["record_count"],
                    "large200_record_dominant_side": large_record["dominant_side"],
                }
            )
        delta = self._delta_imbalance(bar)
        if delta is not None and abs(delta) >= self.min_delta_activity_imbalance:
            if self._flow_side_confirms(direction, model, delta):
                criteria.append("delta_activity")
                details["aoi_delta_imbalance"] = delta
        return {
            "criteria": criteria,
            "details": details,
        }

    def _nearest_market_level(self, bar: pd.Series, level: float) -> dict | None:
        candidates: list[tuple[str, float]] = []
        for label, column in [
            ("prior_rth_high", "prev_rth_high"),
            ("prior_rth_low", "prev_rth_low"),
            ("overnight_high", "overnight_high"),
            ("overnight_low", "overnight_low"),
            ("orb_30s_high", "orb_30s_high"),
            ("orb_30s_low", "orb_30s_low"),
        ]:
            value = _finite_float(bar.get(column))
            if value is not None:
                candidates.append((label, value))
        if self.allow_opening_range_proxy:
            opening = self._opening_range()
            if opening is not None:
                candidates.extend(
                    [
                        ("opening_range_high_proxy", opening["high"]),
                        ("opening_range_low_proxy", opening["low"]),
                    ]
                )
        if not candidates:
            return None
        max_distance = self.market_aoi_max_distance_ticks * self.tick_size
        label, price = min(candidates, key=lambda item: abs(item[1] - level))
        distance = abs(price - level)
        if distance > max_distance:
            return None
        return {
            "market_aoi_type": label,
            "market_aoi_level": float(price),
            "market_aoi_distance_ticks": distance / self.tick_size,
        }

    def _range_trap_confirms(
        self,
        direction: str,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> bool:
        if not self._bar_reaches_aoi(high, low, level):
            return False
        if direction == "long":
            return self._long_trap_confirms(bar, level, open_price, low, close)
        return self._short_trap_confirms(bar, level, open_price, high, close)

    def _trend_pullback_confirms(
        self,
        direction: str,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> bool:
        if not self._bar_reaches_aoi(high, low, level):
            return False
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            absorption = _finite_float(bar.get("footprint_absorption_long")) or 0.0
            absorption_volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
            absorption_price = _finite_float(bar.get("footprint_highest_sell_imbalance_price"))
            return (
                absorption > 0
                and absorption_volume >= self.min_absorption_volume
                and absorption_price is not None
                and absorption_price < close
                and self._directional_delta_imbalance(bar, "long")
                and close >= level + confirm
                and close > open_price
            )
        absorption = _finite_float(bar.get("footprint_absorption_short")) or 0.0
        absorption_volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        absorption_price = _finite_float(bar.get("footprint_lowest_buy_imbalance_price"))
        return (
            absorption > 0
            and absorption_volume >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price > close
            and self._directional_delta_imbalance(bar, "short")
            and close <= level - confirm
            and close < open_price
        )

    def _bar_reaches_aoi(self, high: float, low: float, level: float) -> bool:
        tolerance = self.aoi_reach_tolerance_ticks * self.tick_size
        return low <= level + tolerance and high >= level - tolerance

    def _large_record_state(self, bar: pd.Series) -> dict | None:
        max_volume = _finite_float(bar.get("large200_record_max_volume"))
        total_volume = _finite_float(bar.get("large200_record_volume"))
        signed_volume = _finite_float(bar.get("large200_record_signed_volume"))
        record_count = _finite_float(bar.get("large200_record_count")) or 0.0
        if (
            max_volume is None
            or total_volume is None
            or signed_volume is None
            or max_volume < self.min_large200_record_volume
            or total_volume <= 0
            or signed_volume == 0
        ):
            return None
        return {
            "max_volume": max_volume,
            "total_volume": total_volume,
            "signed_volume": signed_volume,
            "record_count": record_count,
            "dominant_side": "buy" if signed_volume > 0 else "sell",
        }

    def _flow_side_confirms(self, direction: str, model: str, signed_value: float) -> bool:
        if signed_value == 0:
            return False
        if model == "range":
            return signed_value < 0 if direction == "long" else signed_value > 0
        return signed_value > 0 if direction == "long" else signed_value < 0

    def _directional_delta_imbalance(self, bar: pd.Series, direction: str) -> bool:
        if self.min_directional_delta_imbalance <= 0:
            return True
        delta = self._delta_imbalance(bar)
        if delta is None:
            return False
        if direction == "long":
            return delta >= self.min_directional_delta_imbalance
        return delta <= -self.min_directional_delta_imbalance

    def _delta_imbalance(self, bar: pd.Series) -> float | None:
        signed = _finite_float(bar.get("signed_volume"))
        volume = _finite_float(bar.get("volume"))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _video_signal(
        self,
        *,
        direction: str,
        model: str,
        level_type: str,
        level: float,
        profile: dict,
        confluence: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        fields = {
            "setup_mode": self.setup_mode,
            "video_model": "model1_range" if model == "range" else "model2_trend",
            "profile_level_type": level_type,
            "profile_level_price": float(level),
            "profile_source": self.profile_source,
            "profile_session": profile.get("session_date"),
            "profile_total_volume": profile.get("total_volume"),
            "profile_bars": profile.get("bar_count"),
            "aoi_min_confluences": self.min_aoi_confluences,
            "aoi_confluence_count": len(confluence["criteria"]),
            "aoi_confluence_criteria": ",".join(confluence["criteria"]),
            "aoi_reach_tolerance_ticks": self.aoi_reach_tolerance_ticks,
            "market_aoi_max_distance_ticks": self.market_aoi_max_distance_ticks,
            "min_large200_record_volume": self.min_large200_record_volume,
            "min_delta_activity_imbalance": self.min_delta_activity_imbalance,
            "min_absorption_volume": self.min_absorption_volume,
            "min_structure_bars": self.min_structure_bars,
            "min_trend_move_ticks": self.min_trend_move_ticks,
            "delta_imbalance": self._delta_imbalance(bar) or 0.0,
            "signed_volume": _finite_float(bar.get("signed_volume")) or 0.0,
            "confirmation_high": float(bar["high"]),
            "confirmation_low": float(bar["low"]),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "video_mechanics_not_simulated": "partials_and_dynamic_trailing_stop",
        }
        fields.update(confluence["details"])
        target = self._target_price(direction, model, profile)
        if target is not None:
            fields["signal_target_price"] = target
            fields["signal_target_reference"] = self.target_reference
        return Signal(
            direction=direction,
            level_type=f"{model}_{level_type}_{direction}_video_exact_orderflow",
            swept_level=float(level),
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(level),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _target_price(self, direction: str, model: str, profile: dict) -> float | None:
        vah = _finite_float(profile.get("vah"))
        val = _finite_float(profile.get("val"))
        if model == "range":
            if vah is None or val is None:
                return None
            if self.target_reference == "value_opposite_edge":
                return vah if direction == "long" else val
            return (vah + val) / 2.0
        if self.target_reference in {"value_opposite_edge", "value_midpoint"} and vah is not None and val is not None:
            return vah if direction == "long" else val
        if not self.current_session_bars:
            return None
        if direction == "long":
            return max(float(bar["high"]) for bar in self.current_session_bars)
        return min(float(bar["low"]) for bar in self.current_session_bars)

    def _validate_exact_video_params(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.min_aoi_confluences < 2:
            raise ValueError("entry.params.min_aoi_confluences must be at least 2 for the video playbook.")
        if self.aoi_reach_tolerance_ticks < 0:
            raise ValueError("entry.params.aoi_reach_tolerance_ticks must be non-negative.")
        if self.min_large200_record_volume < 200:
            raise ValueError("entry.params.min_large200_record_volume must be at least 200 for ES.")
        if self.min_delta_activity_imbalance < 0 or self.min_directional_delta_imbalance < 0:
            raise ValueError("delta imbalance thresholds must be non-negative.")
        if self.min_structure_bars < 1:
            raise ValueError("entry.params.min_structure_bars must be positive.")
