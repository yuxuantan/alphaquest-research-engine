from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TrueVapAoiBreakoutContinuationEntry:
    name = "true_vap_aoi_breakout_continuation"

    _MODES = {
        "prior_high_vap_breakout_long",
        "prior_low_vap_breakdown_short",
        "prior_extreme_vap_two_sided_breakout",
        "overnight_high_vap_breakout_long",
        "overnight_low_vap_breakdown_short",
        "overnight_extreme_vap_two_sided_breakout",
        "opening_range_vap_two_sided_breakout",
        "combined_vap_aoi_two_sided_breakout",
    }
    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "signed": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "combined_vap_aoi_two_sided_breakout")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.max_profile_distance_ticks = int(params.get("max_profile_distance_ticks", 8))
        self.min_breakout_ticks = float(params.get("min_breakout_ticks", 1))
        self.close_buffer_ticks = float(params.get("close_buffer_ticks", 0))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.min_footprint_imbalance_volume = float(params.get("min_footprint_imbalance_volume", 20))
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.signaled_sessions: set = set()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = bar.get("session_date")
        signal = None
        if session_date not in self.signaled_sessions and trades_today < self.max_trades_per_day:
            signal = self._signal_from_completed_bar(bar)
            if signal is not None:
                self.signaled_sessions.add(session_date)
        self.current_session_bars.append(bar.copy())
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.current_session = session_date
        self.current_session_bars = []

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if None in {high, low, open_price, close}:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None

        for direction, aoi_type, aoi_level in self._candidate_aois(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            profile_match = self._nearest_profile_level(aoi_level, bar)
            if profile_match is None:
                continue
            if direction == "long":
                if self._long_breakout_confirms(bar, aoi_level, open_price, high, close, imbalance):
                    return self._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp, imbalance)
            else:
                if self._short_breakout_confirms(bar, aoi_level, open_price, low, close, imbalance):
                    return self._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp, imbalance)
        return None

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float]]:
        candidates: list[tuple[str, str, float]] = []
        if self.setup_mode in {"prior_high_vap_breakout_long", "prior_extreme_vap_two_sided_breakout", "combined_vap_aoi_two_sided_breakout"}:
            level = _finite_float(bar.get("prev_rth_high"))
            if level is not None:
                candidates.append(("long", "prior_rth_high", level))
        if self.setup_mode in {"prior_low_vap_breakdown_short", "prior_extreme_vap_two_sided_breakout", "combined_vap_aoi_two_sided_breakout"}:
            level = _finite_float(bar.get("prev_rth_low"))
            if level is not None:
                candidates.append(("short", "prior_rth_low", level))
        if self.setup_mode in {"overnight_high_vap_breakout_long", "overnight_extreme_vap_two_sided_breakout"}:
            level = _finite_float(bar.get("overnight_high"))
            if level is not None:
                candidates.append(("long", "overnight_high", level))
        if self.setup_mode in {"overnight_low_vap_breakdown_short", "overnight_extreme_vap_two_sided_breakout"}:
            level = _finite_float(bar.get("overnight_low"))
            if level is not None:
                candidates.append(("short", "overnight_low", level))
        if self.setup_mode in {"opening_range_vap_two_sided_breakout", "combined_vap_aoi_two_sided_breakout"}:
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("long", "opening_range_high", opening["high"]))
                candidates.append(("short", "opening_range_low", opening["low"]))
        return candidates

    def _opening_range(self) -> dict | None:
        if len(self.current_session_bars) < self.opening_range_minutes:
            return None
        first = self.current_session_bars[0]
        session_start = pd.Timestamp(first["timestamp"])
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        opening_bars = [bar for bar in self.current_session_bars if pd.Timestamp(bar["timestamp"]) < opening_end]
        if len(opening_bars) < self.opening_range_minutes:
            return None
        return {
            "high": max(float(bar["high"]) for bar in opening_bars),
            "low": min(float(bar["low"]) for bar in opening_bars),
        }

    def _nearest_profile_level(self, aoi_level: float, bar: pd.Series) -> dict | None:
        levels = self._cached_profile_levels(bar)
        if not levels:
            return None
        max_distance = self.max_profile_distance_ticks * self.tick_size
        best = min(levels, key=lambda item: abs(float(item["price"]) - aoi_level))
        distance = abs(float(best["price"]) - aoi_level)
        if distance > max_distance:
            return None
        prefix = self.cached_profile_prefix
        return {
            "profile_level_type": best["type"],
            "profile_level_price": float(best["price"]),
            "profile_distance_ticks": distance / self.tick_size,
            "prior_profile_session": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "prior_profile_total_volume": _finite_float(bar.get(f"{prefix}_total_volume")),
            "prior_profile_price_levels": _finite_float(bar.get(f"{prefix}_price_levels")),
        }

    def _cached_profile_levels(self, bar: pd.Series) -> list[dict]:
        prefix = self.cached_profile_prefix
        level_specs = [
            ("poc", f"{prefix}_poc"),
            ("vah", f"{prefix}_vah"),
            ("val", f"{prefix}_val"),
            ("lvn_near_high", f"{prefix}_lvn_near_high"),
            ("lvn_near_low", f"{prefix}_lvn_near_low"),
        ]
        levels = []
        seen: set[tuple[str, int]] = set()
        for level_type, column in level_specs:
            price = _finite_float(bar.get(column))
            if price is None or price <= 0:
                continue
            key = (level_type, int(round(price / self.tick_size)))
            if key in seen:
                continue
            seen.add(key)
            levels.append({"type": level_type, "price": price})
        return levels

    def _long_breakout_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        close: float,
        imbalance: float,
    ) -> bool:
        breakout = self.min_breakout_ticks * self.tick_size
        buffer = self.close_buffer_ticks * self.tick_size
        footprint_volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        return (
            high >= level + breakout
            and close >= level + buffer
            and close > open_price
            and imbalance >= self.min_orderflow_imbalance
            and footprint_volume >= self.min_footprint_imbalance_volume
        )

    def _short_breakout_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        low: float,
        close: float,
        imbalance: float,
    ) -> bool:
        breakout = self.min_breakout_ticks * self.tick_size
        buffer = self.close_buffer_ticks * self.tick_size
        footprint_volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
        return (
            low <= level - breakout
            and close <= level - buffer
            and close < open_price
            and imbalance <= -self.min_orderflow_imbalance
            and footprint_volume >= self.min_footprint_imbalance_volume
        )

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

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
        volume_col = "footprint_max_buy_imbalance_volume" if direction == "long" else "footprint_max_sell_imbalance_volume"
        fields = {
            "setup_mode": self.setup_mode,
            "aoi_type": aoi_type,
            "aoi_level": aoi_level,
            **profile_match,
            "min_breakout_ticks": self.min_breakout_ticks,
            "close_buffer_ticks": self.close_buffer_ticks,
            "flow_mode": self.flow_mode,
            "orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "footprint_imbalance_volume": _finite_float(bar.get(volume_col)) or 0.0,
            "min_footprint_imbalance_volume": self.min_footprint_imbalance_volume,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{aoi_type}_{profile_match['profile_level_type']}_vap_breakout",
            swept_level=aoi_level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=aoi_level,
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
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


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
