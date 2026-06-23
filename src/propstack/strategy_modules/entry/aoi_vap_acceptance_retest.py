from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class AoiVapAcceptanceRetestEntry:
    name = "aoi_vap_acceptance_retest"

    _MODES = {
        "prior_high_acceptance_long",
        "prior_low_acceptance_short",
        "prior_extreme_two_sided_acceptance",
        "opening_range_acceptance_two_sided",
        "overnight_high_acceptance_long",
        "overnight_low_acceptance_short",
        "overnight_extreme_two_sided_acceptance",
        "combined_market_aoi_acceptance",
    }
    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "signed": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "combined_market_aoi_acceptance")).lower()
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.max_profile_distance_ticks = int(params.get("max_profile_distance_ticks", 8))
        self.min_breakout_ticks = float(params.get("min_breakout_ticks", 1))
        self.retest_tolerance_ticks = float(params.get("retest_tolerance_ticks", 4))
        self.acceptance_buffer_ticks = float(params.get("acceptance_buffer_ticks", 1))
        self.min_retest_delay_bars = int(params.get("min_retest_delay_bars", 1))
        self.max_retest_bars = int(params.get("max_retest_bars", 30))
        self.max_chase_ticks = float(params.get("max_chase_ticks", 20))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.min_footprint_imbalance_volume = float(params.get("min_footprint_imbalance_volume", 50))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.session_states: dict[tuple[str, str], dict] = {}
        self.session_signal_counts: dict[object, int] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = bar.get("session_date")
        signals_today = self.session_signal_counts.get(session_date, 0)
        signal = None
        if signals_today < self.max_trades_per_day and trades_today < self.max_trades_per_day:
            signal = self._signal_from_completed_bar(bar)
            if signal is not None:
                self.session_signal_counts[session_date] = signals_today + 1

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
        self.session_states = {}

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        values = self._bar_values(bar)
        if values is None:
            return None

        signal = self._evaluate_existing_states(bar, values, signal_timestamp)
        self._record_new_breakouts(bar, values)
        return signal

    def _evaluate_existing_states(self, bar: pd.Series, values: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        for key, state in sorted(self.session_states.items(), key=lambda item: item[1]["breakout_index"]):
            if state.get("signaled"):
                continue
            age = len(self.current_session_bars) - int(state["breakout_index"])
            if age > self.max_retest_bars:
                state["expired"] = True
                continue
            if age < self.min_retest_delay_bars:
                continue
            direction = state["direction"]
            if direction == "long":
                if self._long_retest_accepts(bar, values, state):
                    state["signaled"] = True
                    return self._signal(direction, state, bar, values, signal_timestamp)
            elif self._short_retest_accepts(bar, values, state):
                state["signaled"] = True
                return self._signal(direction, state, bar, values, signal_timestamp)
        return None

    def _record_new_breakouts(self, bar: pd.Series, values: dict) -> None:
        for direction, aoi_type, level, profile_match, opening in self._candidate_aois(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            key = (direction, aoi_type)
            state = self.session_states.get(key)
            if state is not None and not state.get("expired"):
                continue
            if direction == "long":
                if not self._long_breakout_confirms(bar, values, level):
                    continue
            elif not self._short_breakout_confirms(bar, values, level):
                continue
            self.session_states[key] = {
                "direction": direction,
                "aoi_type": aoi_type,
                "aoi_level": level,
                "profile_match": profile_match,
                "opening": opening,
                "breakout_index": len(self.current_session_bars),
                "breakout_timestamp": bar["timestamp"],
                "breakout_high": values["high"],
                "breakout_low": values["low"],
                "breakout_close": values["close"],
                "breakout_orderflow_imbalance": self._orderflow_imbalance(bar) or 0.0,
            }

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float, dict, dict | None]]:
        candidates: list[tuple[str, str, float, dict, dict | None]] = []
        mode = self.setup_mode
        if mode in {"prior_high_acceptance_long", "prior_extreme_two_sided_acceptance", "combined_market_aoi_acceptance"}:
            self._append_candidate(candidates, "long", "prior_rth_high", _finite_float(bar.get("prev_rth_high")), bar)
        if mode in {"prior_low_acceptance_short", "prior_extreme_two_sided_acceptance", "combined_market_aoi_acceptance"}:
            self._append_candidate(candidates, "short", "prior_rth_low", _finite_float(bar.get("prev_rth_low")), bar)
        if mode in {
            "opening_range_acceptance_two_sided",
            "combined_market_aoi_acceptance",
        }:
            opening = self._opening_range()
            if opening is not None:
                self._append_candidate(candidates, "long", "opening_range_high", opening["high"], bar, opening)
                self._append_candidate(candidates, "short", "opening_range_low", opening["low"], bar, opening)
        if mode in {
            "overnight_high_acceptance_long",
            "overnight_extreme_two_sided_acceptance",
            "combined_market_aoi_acceptance",
        }:
            self._append_candidate(candidates, "long", "overnight_high", _finite_float(bar.get("overnight_high")), bar)
        if mode in {
            "overnight_low_acceptance_short",
            "overnight_extreme_two_sided_acceptance",
            "combined_market_aoi_acceptance",
        }:
            self._append_candidate(candidates, "short", "overnight_low", _finite_float(bar.get("overnight_low")), bar)
        return candidates

    def _append_candidate(
        self,
        candidates: list[tuple[str, str, float, dict, dict | None]],
        direction: str,
        aoi_type: str,
        level: float | None,
        bar: pd.Series,
        opening: dict | None = None,
    ) -> None:
        if level is None:
            return
        profile_match = self._nearest_profile_level(level, bar)
        if profile_match is None:
            return
        candidates.append((direction, aoi_type, level, profile_match, opening))

    def _opening_range(self) -> dict | None:
        if len(self.current_session_bars) < self.opening_range_minutes:
            return None
        first = self.current_session_bars[0]
        session_start = pd.Timestamp(first["timestamp"])
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        opening_bars = [bar for bar in self.current_session_bars if pd.Timestamp(bar["timestamp"]) < opening_end]
        if len(opening_bars) < self.opening_range_minutes:
            return None
        high = max(float(bar["high"]) for bar in opening_bars)
        low = min(float(bar["low"]) for bar in opening_bars)
        return {
            "high": high,
            "low": low,
            "open": float(opening_bars[0]["open"]),
            "width": high - low,
            "start_timestamp": session_start,
            "end_timestamp": opening_end,
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

    def _long_breakout_confirms(self, bar: pd.Series, values: dict, level: float) -> bool:
        breakout = self.min_breakout_ticks * self.tick_size
        return (
            values["high"] >= level + breakout
            and values["close"] >= level + breakout
            and values["close"] > values["open"]
            and self._same_direction_flow(bar, "long")
        )

    def _short_breakout_confirms(self, bar: pd.Series, values: dict, level: float) -> bool:
        breakout = self.min_breakout_ticks * self.tick_size
        return (
            values["low"] <= level - breakout
            and values["close"] <= level - breakout
            and values["close"] < values["open"]
            and self._same_direction_flow(bar, "short")
        )

    def _long_retest_accepts(self, bar: pd.Series, values: dict, state: dict) -> bool:
        level = float(state["aoi_level"])
        tolerance = self.retest_tolerance_ticks * self.tick_size
        buffer = self.acceptance_buffer_ticks * self.tick_size
        max_chase = self.max_chase_ticks * self.tick_size
        footprint_volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        return (
            values["low"] <= level + tolerance
            and values["close"] >= level + buffer
            and values["close"] <= level + max_chase
            and values["close"] > values["open"]
            and self._same_direction_flow(bar, "long")
            and footprint_volume >= self.min_footprint_imbalance_volume
        )

    def _short_retest_accepts(self, bar: pd.Series, values: dict, state: dict) -> bool:
        level = float(state["aoi_level"])
        tolerance = self.retest_tolerance_ticks * self.tick_size
        buffer = self.acceptance_buffer_ticks * self.tick_size
        max_chase = self.max_chase_ticks * self.tick_size
        footprint_volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
        return (
            values["high"] >= level - tolerance
            and values["close"] <= level - buffer
            and values["close"] >= level - max_chase
            and values["close"] < values["open"]
            and self._same_direction_flow(bar, "short")
            and footprint_volume >= self.min_footprint_imbalance_volume
        )

    def _same_direction_flow(self, bar: pd.Series, direction: str) -> bool:
        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return False
        if direction == "long":
            return imbalance >= self.min_orderflow_imbalance
        return imbalance <= -self.min_orderflow_imbalance

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _bar_values(self, bar: pd.Series) -> dict | None:
        values = {
            "open": _finite_float(bar.get("open")),
            "high": _finite_float(bar.get("high")),
            "low": _finite_float(bar.get("low")),
            "close": _finite_float(bar.get("close")),
        }
        if any(value is None for value in values.values()):
            return None
        return values

    def _signal(
        self,
        direction: str,
        state: dict,
        bar: pd.Series,
        values: dict,
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        opening = state.get("opening") or {}
        profile_match = state["profile_match"]
        current_imbalance = self._orderflow_imbalance(bar) or 0.0
        footprint_col = "footprint_max_buy_imbalance_volume" if direction == "long" else "footprint_max_sell_imbalance_volume"
        level = float(state["aoi_level"])
        fields = {
            "setup_mode": self.setup_mode,
            "aoi_type": state["aoi_type"],
            "aoi_level": level,
            **profile_match,
            "min_breakout_ticks": self.min_breakout_ticks,
            "retest_tolerance_ticks": self.retest_tolerance_ticks,
            "acceptance_buffer_ticks": self.acceptance_buffer_ticks,
            "max_retest_bars": self.max_retest_bars,
            "max_chase_ticks": self.max_chase_ticks,
            "flow_mode": self.flow_mode,
            "breakout_timestamp": state["breakout_timestamp"],
            "breakout_close": state["breakout_close"],
            "breakout_orderflow_imbalance": state["breakout_orderflow_imbalance"],
            "retest_orderflow_imbalance": current_imbalance,
            "footprint_imbalance_volume": _finite_float(bar.get(footprint_col)) or 0.0,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_footprint_imbalance_volume": self.min_footprint_imbalance_volume,
            "confirmation_close": values["close"],
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{state['aoi_type']}_{profile_match['profile_level_type']}_acceptance_retest",
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=values["high"],
            sweep_low=values["low"],
            reclaim_timestamp=signal_timestamp,
            opening_range_high=opening.get("high"),
            opening_range_low=opening.get("low"),
            opening_range_open=opening.get("open"),
            opening_range_width=opening.get("width"),
            breakout_level=level,
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
        if self.min_breakout_ticks < 0 or self.retest_tolerance_ticks < 0 or self.acceptance_buffer_ticks < 0:
            raise ValueError("entry.params breakout, retest, and acceptance ticks must be non-negative.")
        if self.min_retest_delay_bars < 1:
            raise ValueError("entry.params.min_retest_delay_bars must be at least one.")
        if self.max_retest_bars < self.min_retest_delay_bars:
            raise ValueError("entry.params.max_retest_bars must be >= min_retest_delay_bars.")
        if self.max_chase_ticks < 0:
            raise ValueError("entry.params.max_chase_ticks must be non-negative.")
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
