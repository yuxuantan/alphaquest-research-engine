from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.profile_aoi_footprint_trap import (
    ProfileAoiFootprintTrapEntry,
    _finite_float,
)


class VideoAoiOrderflowPlaybookEntry(ProfileAoiFootprintTrapEntry):
    name = "video_aoi_orderflow_playbook"

    _MODES = {
        "range_val_seller_trap_long",
        "range_vah_buyer_trap_short",
        "range_value_edge_two_sided_reentry",
        "trend_lvn_seller_trap_long",
        "trend_lvn_buyer_trap_short",
        "trend_lvn_two_sided_continuation",
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_trend_move_ticks = float(params.get("min_trend_move_ticks", 20))
        self.min_directional_delta_imbalance = float(params.get("min_directional_delta_imbalance", 0.0))
        self.require_market_aoi_confluence = bool(params.get("require_market_aoi_confluence", True))
        self._validate_playbook_params()

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

        for direction, model, level_type, level in self._candidate_setups(bar, close, profile):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            market_match = self._nearest_market_aoi(bar, level, direction)
            if self.require_market_aoi_confluence and market_match is None:
                continue
            if model == "range":
                confirms = (
                    self._long_trap_confirms(bar, level, open_price, low, close)
                    if direction == "long"
                    else self._short_trap_confirms(bar, level, open_price, high, close)
                )
            else:
                confirms = (
                    self._long_trend_pullback_confirms(bar, level, open_price, low, close)
                    if direction == "long"
                    else self._short_trend_pullback_confirms(bar, level, open_price, high, close)
                )
            if confirms:
                return self._playbook_signal(
                    direction,
                    model,
                    level_type,
                    level,
                    profile,
                    market_match,
                    bar,
                    signal_timestamp,
                )
        return None

    def _candidate_setups(
        self,
        bar: pd.Series,
        close: float,
        profile: dict,
    ) -> list[tuple[str, str, str, float]]:
        candidates: list[tuple[str, str, str, float]] = []
        mode = self.setup_mode
        profile_label = (
            "developing"
            if self.profile_source in {"developing_session_ohlcv", "cached_developing_vap"}
            or self.cached_profile_prefix.startswith("developing")
            else "prior"
        )
        if mode in {"range_val_seller_trap_long", "range_value_edge_two_sided_reentry"}:
            val = _finite_float(profile.get("val"))
            if val is not None:
                candidates.append(("long", "range", f"{profile_label}_value_area_low", val))
        if mode in {"range_vah_buyer_trap_short", "range_value_edge_two_sided_reentry"}:
            vah = _finite_float(profile.get("vah"))
            if vah is not None:
                candidates.append(("short", "range", f"{profile_label}_value_area_high", vah))
        if mode in {"trend_lvn_seller_trap_long", "trend_lvn_two_sided_continuation"}:
            if self._trend_state_confirms(bar, "long", close, profile):
                lvn = self._nearest_lvn(profile, close)
                if lvn is not None:
                    candidates.append(("long", "trend", f"{profile_label}_low_volume_node", lvn["profile_level_price"]))
        if mode in {"trend_lvn_buyer_trap_short", "trend_lvn_two_sided_continuation"}:
            if self._trend_state_confirms(bar, "short", close, profile):
                lvn = self._nearest_lvn(profile, close)
                if lvn is not None:
                    candidates.append(("short", "trend", f"{profile_label}_low_volume_node", lvn["profile_level_price"]))
        return candidates

    def _nearest_lvn(self, profile: dict, reference_price: float) -> dict | None:
        lvns = [item for item in profile.get("levels", []) if item.get("type") == "lvn"]
        if not lvns:
            return None
        max_distance = self.max_profile_distance_ticks * self.tick_size
        best = min(lvns, key=lambda item: abs(float(item["price"]) - reference_price))
        distance = abs(float(best["price"]) - reference_price)
        if distance > max_distance:
            return None
        return {
            "profile_level_type": "lvn",
            "profile_level_price": float(best["price"]),
            "profile_distance_ticks": distance / self.tick_size,
            "profile_source": self.profile_source,
            "profile_session": profile.get("session_date"),
            "profile_total_volume": profile.get("total_volume"),
            "profile_bars": profile.get("bar_count"),
            "prior_profile_session": profile.get("session_date"),
            "prior_profile_total_volume": profile.get("total_volume"),
            "prior_profile_bars": profile.get("bar_count"),
        }

    def _nearest_market_aoi(self, bar: pd.Series, level: float, direction: str) -> dict | None:
        candidates: list[tuple[str, float]] = []
        if direction == "long":
            low = _finite_float(bar.get("prev_rth_low"))
            if low is not None:
                candidates.append(("prior_rth_low", low))
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("opening_range_low", opening["low"]))
        else:
            high = _finite_float(bar.get("prev_rth_high"))
            if high is not None:
                candidates.append(("prior_rth_high", high))
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("opening_range_high", opening["high"]))
        if not candidates:
            return None
        max_distance = self.max_profile_distance_ticks * self.tick_size
        best_type, best_price = min(candidates, key=lambda item: abs(float(item[1]) - level))
        distance = abs(float(best_price) - level)
        if distance > max_distance:
            return None
        return {
            "market_aoi_type": best_type,
            "market_aoi_level": float(best_price),
            "market_aoi_distance_ticks": distance / self.tick_size,
        }

    def _trend_state_confirms(
        self,
        bar: pd.Series,
        direction: str,
        close: float,
        profile: dict,
    ) -> bool:
        opening = self._opening_range()
        if opening is None or not self.current_session_bars:
            return False
        session_open = _finite_float(self.current_session_bars[0].get("open"))
        if session_open is None:
            return False
        min_move = self.min_trend_move_ticks * self.tick_size
        vah = _finite_float(profile.get("vah"))
        val = _finite_float(profile.get("val"))
        if direction == "long":
            return (
                vah is not None
                and close >= session_open + min_move
                and close >= opening["high"]
                and close >= vah
            )
        return (
            val is not None
            and close <= session_open - min_move
            and close <= opening["low"]
            and close <= val
        )

    def _long_trend_pullback_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        low: float,
        close: float,
    ) -> bool:
        confirm = self.confirmation_ticks * self.tick_size
        absorption = _finite_float(bar.get("footprint_absorption_long")) or 0.0
        absorption_volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
        absorption_price = _finite_float(bar.get("footprint_highest_sell_imbalance_price"))
        return (
            absorption > 0
            and absorption_volume >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price < close
            and self._adverse_delta_imbalance(bar, "long")
            and self._directional_delta_imbalance(bar, "long")
            and low <= level + self.max_profile_distance_ticks * self.tick_size
            and close >= level + confirm
            and close > open_price
        )

    def _short_trend_pullback_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        close: float,
    ) -> bool:
        confirm = self.confirmation_ticks * self.tick_size
        absorption = _finite_float(bar.get("footprint_absorption_short")) or 0.0
        absorption_volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        absorption_price = _finite_float(bar.get("footprint_lowest_buy_imbalance_price"))
        return (
            absorption > 0
            and absorption_volume >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price > close
            and self._adverse_delta_imbalance(bar, "short")
            and self._directional_delta_imbalance(bar, "short")
            and high >= level - self.max_profile_distance_ticks * self.tick_size
            and close <= level - confirm
            and close < open_price
        )

    def _directional_delta_imbalance(self, bar: pd.Series, direction: str) -> bool:
        if self.min_directional_delta_imbalance <= 0:
            return True
        signed = _finite_float(bar.get("signed_volume"))
        volume = _finite_float(bar.get("volume"))
        if signed is None or volume is None or volume <= 0:
            return False
        imbalance = signed / volume
        if not math.isfinite(imbalance):
            return False
        if direction == "long":
            return imbalance >= self.min_directional_delta_imbalance
        return imbalance <= -self.min_directional_delta_imbalance

    def _playbook_signal(
        self,
        direction: str,
        model: str,
        level_type: str,
        level: float,
        profile: dict,
        market_match: dict | None,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        signed = _finite_float(bar.get("signed_volume")) or 0.0
        volume = _finite_float(bar.get("volume")) or 0.0
        delta_imbalance = signed / volume if volume > 0 else 0.0
        volume_col = (
            "footprint_max_sell_imbalance_volume"
            if direction == "long"
            else "footprint_max_buy_imbalance_volume"
        )
        price_col = (
            "footprint_highest_sell_imbalance_price"
            if direction == "long"
            else "footprint_lowest_buy_imbalance_price"
        )
        profile_distance = abs(float(level) - float(profile.get("poc", level))) / self.tick_size
        fields = {
            "setup_mode": self.setup_mode,
            "video_model": model,
            "profile_level_type": level_type,
            "profile_level_price": float(level),
            "profile_distance_from_poc_ticks": profile_distance if math.isfinite(profile_distance) else 0.0,
            "profile_source": self.profile_source,
            "profile_session": profile.get("session_date"),
            "profile_total_volume": profile.get("total_volume"),
            "profile_bars": profile.get("bar_count"),
            "prior_profile_session": profile.get("session_date"),
            "prior_profile_total_volume": profile.get("total_volume"),
            "prior_profile_bars": profile.get("bar_count"),
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "max_profile_distance_ticks": self.max_profile_distance_ticks,
            "min_absorption_volume": self.min_absorption_volume,
            "min_adverse_delta_imbalance": self.min_adverse_delta_imbalance,
            "min_directional_delta_imbalance": self.min_directional_delta_imbalance,
            "min_trend_move_ticks": self.min_trend_move_ticks,
            "footprint_absorption_volume": _finite_float(bar.get(volume_col)) or 0.0,
            "footprint_absorption_price": _finite_float(bar.get(price_col)) or 0.0,
            "signed_volume": signed,
            "delta_imbalance": delta_imbalance,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        if market_match:
            fields.update(market_match)
        return Signal(
            direction=direction,
            level_type=f"{model}_{level_type}_{direction}_video_orderflow",
            swept_level=float(level),
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(level),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate_playbook_params(self) -> None:
        if self.min_trend_move_ticks < 0:
            raise ValueError("entry.params.min_trend_move_ticks must be non-negative.")
        if self.min_directional_delta_imbalance < 0:
            raise ValueError("entry.params.min_directional_delta_imbalance must be non-negative.")
