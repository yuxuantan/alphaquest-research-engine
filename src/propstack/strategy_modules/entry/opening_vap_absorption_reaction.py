from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OpeningVapAbsorptionReactionEntry:
    name = "opening_vap_absorption_reaction"

    _MODES = {
        "opening30_value_trap_two_sided",
        "opening60_value_trap_two_sided",
        "opening30_poc_reclaim_two_sided",
        "opening60_poc_reclaim_two_sided",
        "opening30_lvn_trap_two_sided",
        "opening60_lvn_trap_two_sided",
        "opening30_value_acceptance_two_sided",
        "opening60_value_acceptance_two_sided",
    }
    _FLOW_COLUMNS = {
        "signed": ("signed_volume", "volume"),
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "opening30_value_trap_two_sided")).lower()
        self.window_minutes = int(params.get("opening_window_minutes", self._window_from_mode()))
        default_start = "10:05:00" if self.window_minutes == 30 else "10:35:00"
        self.start_time = parse_time(params.get("start_time", default_start))
        self.end_time = parse_time(params.get("end_time", "12:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.opening_vap_prefix = str(params.get("opening_vap_prefix", f"opening{self.window_minutes}_vap"))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.03))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.min_footprint_imbalance_volume = float(params.get("min_footprint_imbalance_volume", 20))
        self.min_profile_total_volume = float(params.get("min_profile_total_volume", 0.0))
        self.min_profile_price_levels = float(params.get("min_profile_price_levels", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.signaled_sessions: set = set()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = bar.get("session_date")
        if session_date in self.signaled_sessions:
            return None

        signal = self._signal_from_completed_bar(bar)
        if signal is not None:
            self.signaled_sessions.add(session_date)
        return signal

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        open_price = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if None in {open_price, high, low, close}:
            return None

        profile = self._opening_profile(bar)
        if profile is None:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None

        for direction, boundary_type, boundary, reaction_type in self._candidates(profile):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            if reaction_type == "trap" and self._trap_confirms(
                direction, boundary, bar, open_price, high, low, close, imbalance
            ):
                return self._signal(
                    direction, boundary_type, boundary, reaction_type, profile, bar, signal_timestamp, imbalance
                )
            if reaction_type == "acceptance" and self._acceptance_confirms(
                direction, boundary, bar, open_price, high, low, close, imbalance
            ):
                return self._signal(
                    direction, boundary_type, boundary, reaction_type, profile, bar, signal_timestamp, imbalance
                )
        return None

    def _candidates(self, profile: dict) -> list[tuple[str, str, float, str]]:
        if self.setup_mode.endswith("value_trap_two_sided"):
            return [
                ("long", "val", profile["val"], "trap"),
                ("short", "vah", profile["vah"], "trap"),
            ]
        if self.setup_mode.endswith("poc_reclaim_two_sided"):
            return [
                ("long", "poc", profile["poc"], "trap"),
                ("short", "poc", profile["poc"], "trap"),
            ]
        if self.setup_mode.endswith("lvn_trap_two_sided"):
            return [
                ("long", "lvn_near_low", profile["lvn_near_low"], "trap"),
                ("short", "lvn_near_high", profile["lvn_near_high"], "trap"),
            ]
        return [
            ("long", "vah", profile["vah"], "acceptance"),
            ("short", "val", profile["val"], "acceptance"),
        ]

    def _opening_profile(self, bar: pd.Series) -> dict | None:
        prefix = self.opening_vap_prefix
        poc = _finite_float(bar.get(f"{prefix}_poc"))
        vah = _finite_float(bar.get(f"{prefix}_vah"))
        val = _finite_float(bar.get(f"{prefix}_val"))
        lvn_high = _finite_float(bar.get(f"{prefix}_lvn_near_high"))
        lvn_low = _finite_float(bar.get(f"{prefix}_lvn_near_low"))
        total_volume = _finite_float(bar.get(f"{prefix}_total_volume"))
        price_levels = _finite_float(bar.get(f"{prefix}_price_levels"))
        if None in {poc, vah, val, lvn_high, lvn_low}:
            return None
        if vah <= val:
            return None
        if total_volume is not None and total_volume < self.min_profile_total_volume:
            return None
        if price_levels is not None and price_levels < self.min_profile_price_levels:
            return None
        return {
            "prefix": prefix,
            "window_minutes": _finite_float(bar.get(f"{prefix}_window_minutes")) or self.window_minutes,
            "session": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "poc": poc,
            "vah": vah,
            "val": val,
            "lvn_near_high": lvn_high,
            "lvn_near_low": lvn_low,
            "lvn_count": _finite_float(bar.get(f"{prefix}_lvn_count")),
            "total_volume": total_volume,
            "price_levels": price_levels,
        }

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
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            return (
                low <= level - probe
                and close >= level + confirm
                and close > open_price
                and imbalance <= -self.min_orderflow_imbalance
                and self._absorption_confirms(bar, direction, close)
            )
        return (
            high >= level + probe
            and close <= level - confirm
            and close < open_price
            and imbalance >= self.min_orderflow_imbalance
            and self._absorption_confirms(bar, direction, close)
        )

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
        breakout = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            return (
                high >= level + breakout
                and close >= level + confirm
                and close > open_price
                and imbalance >= self.min_orderflow_imbalance
                and self._footprint_volume(bar, direction) >= self.min_footprint_imbalance_volume
            )
        return (
            low <= level - breakout
            and close <= level - confirm
            and close < open_price
            and imbalance <= -self.min_orderflow_imbalance
            and self._footprint_volume(bar, direction) >= self.min_footprint_imbalance_volume
        )

    def _absorption_confirms(self, bar: pd.Series, direction: str, close: float) -> bool:
        if direction == "long":
            absorption = _finite_float(bar.get("footprint_absorption_long")) or 0.0
            volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
            price = _finite_float(bar.get("footprint_highest_sell_imbalance_price"))
            return absorption > 0 and volume >= self.min_footprint_imbalance_volume and price is not None and price < close
        absorption = _finite_float(bar.get("footprint_absorption_short")) or 0.0
        volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        price = _finite_float(bar.get("footprint_lowest_buy_imbalance_price"))
        return absorption > 0 and volume >= self.min_footprint_imbalance_volume and price is not None and price > close

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _footprint_volume(self, bar: pd.Series, direction: str) -> float:
        column = "footprint_max_buy_imbalance_volume" if direction == "long" else "footprint_max_sell_imbalance_volume"
        return _finite_float(bar.get(column)) or 0.0

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
        if reaction_type == "trap":
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
            absorption_col = "footprint_absorption_long" if direction == "long" else "footprint_absorption_short"
        else:
            volume_col = (
                "footprint_max_buy_imbalance_volume"
                if direction == "long"
                else "footprint_max_sell_imbalance_volume"
            )
            price_col = (
                "footprint_lowest_buy_imbalance_price"
                if direction == "long"
                else "footprint_highest_sell_imbalance_price"
            )
            absorption_col = ""

        fields = {
            "setup_mode": self.setup_mode,
            "reaction_type": reaction_type,
            "opening_vap_prefix": profile["prefix"],
            "opening_vap_window_minutes": profile["window_minutes"],
            "opening_vap_session": profile["session"],
            "opening_vap_poc": profile["poc"],
            "opening_vap_vah": profile["vah"],
            "opening_vap_val": profile["val"],
            "opening_vap_lvn_near_high": profile["lvn_near_high"],
            "opening_vap_lvn_near_low": profile["lvn_near_low"],
            "opening_vap_lvn_count": profile["lvn_count"],
            "opening_vap_total_volume": profile["total_volume"],
            "opening_vap_price_levels": profile["price_levels"],
            "boundary_type": boundary_type,
            "boundary_level": boundary,
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "flow_mode": self.flow_mode,
            "orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "footprint_imbalance_volume": _finite_float(bar.get(volume_col)) or 0.0,
            "footprint_reference_price": _finite_float(bar.get(price_col)),
            "footprint_absorption_flag": _finite_float(bar.get(absorption_col)) if absorption_col else None,
            "min_footprint_imbalance_volume": self.min_footprint_imbalance_volume,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"opening_vap_{profile['window_minutes']}_{boundary_type}_{reaction_type}",
            swept_level=float(boundary),
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(boundary),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _window_from_mode(self) -> int:
        if self.setup_mode.startswith("opening30"):
            return 30
        if self.setup_mode.startswith("opening60"):
            return 60
        return 30

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.window_minutes not in {30, 60}:
            raise ValueError("entry.params.opening_window_minutes must be 30 or 60.")
        if not self.setup_mode.startswith(f"opening{self.window_minutes}"):
            raise ValueError("entry.params.opening_window_minutes must match setup_mode.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be positive.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be positive.")
        if self.min_probe_ticks < 0 or self.confirmation_ticks < 0:
            raise ValueError("entry.params probe and confirmation ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed, signed_volume, large10, or large20.")
        if self.min_footprint_imbalance_volume < 0:
            raise ValueError("entry.params.min_footprint_imbalance_volume must be non-negative.")
        if self.min_profile_total_volume < 0 or self.min_profile_price_levels < 0:
            raise ValueError("entry.params profile minimums must be non-negative.")
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
