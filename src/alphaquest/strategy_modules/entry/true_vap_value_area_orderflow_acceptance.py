from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TrueVapValueAreaOrderflowAcceptanceEntry:
    name = "true_vap_value_area_orderflow_acceptance"

    _MODES = {"vah_acceptance_long", "val_acceptance_short", "two_sided_acceptance"}
    _FLOW_COLUMNS = {
        "signed": ("signed_volume", "volume"),
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }
    _START_LOCATION_FILTERS = {
        "any",
        "inside_value",
        "above_vah",
        "below_val",
        "outside_value",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_acceptance")).lower()
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.breakout_buffer_ticks = int(params.get("breakout_buffer_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.start_location_filter = str(params.get("start_location_filter", "any")).lower()
        self.cross_from_inside = bool(params.get("cross_from_inside", False))
        self.min_profile_total_volume = float(params.get("min_profile_total_volume", 0.0))
        self.min_profile_price_levels = float(params.get("min_profile_price_levels", 0.0))
        self.min_footprint_imbalance_volume = float(params.get("min_footprint_imbalance_volume", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))

        self.current_session = None
        self.session_first_open: float | None = None
        self.signaled_sessions: set = set()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = bar.get("session_date")
        if session_date in self.signaled_sessions:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        profile = self._cached_profile(bar)
        if profile is None:
            return None

        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if open_price is None or close is None:
            return None

        direction, boundary, boundary_type = self._trigger_direction(open_price, close, profile)
        if direction is None or boundary is None or boundary_type is None:
            return None

        if not self._start_location_allows(direction, profile):
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None or not self._flow_confirms(direction, imbalance):
            return None

        footprint_volume = self._footprint_volume(bar, direction)
        if footprint_volume < self.min_footprint_imbalance_volume:
            return None

        signal = self._signal(
            direction=direction,
            boundary=boundary,
            boundary_type=boundary_type,
            profile=profile,
            bar=bar,
            signal_timestamp=signal_timestamp,
            imbalance=imbalance,
            footprint_volume=footprint_volume,
        )
        self.signaled_sessions.add(session_date)
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session != session_date:
            self.current_session = session_date
            self.session_first_open = _finite_float(bar.get("open"))

    def _cached_profile(self, bar: pd.Series) -> dict | None:
        prefix = self.cached_profile_prefix
        vah = _finite_float(bar.get(f"{prefix}_vah"))
        val = _finite_float(bar.get(f"{prefix}_val"))
        poc = _finite_float(bar.get(f"{prefix}_poc"))
        total_volume = _finite_float(bar.get(f"{prefix}_total_volume"))
        price_levels = _finite_float(bar.get(f"{prefix}_price_levels"))
        if vah is None or val is None or poc is None:
            return None
        if vah <= val:
            return None
        if total_volume is not None and total_volume < self.min_profile_total_volume:
            return None
        if price_levels is not None and price_levels < self.min_profile_price_levels:
            return None
        return {
            "session": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "vah": vah,
            "val": val,
            "poc": poc,
            "total_volume": total_volume,
            "price_levels": price_levels,
        }

    def _trigger_direction(
        self,
        open_price: float,
        close: float,
        profile: dict,
    ) -> tuple[str | None, float | None, str | None]:
        buffer = self.breakout_buffer_ticks * self.tick_size
        if self.setup_mode in {"two_sided_acceptance", "vah_acceptance_long"} and self.allow_long:
            if close > profile["vah"] + buffer and (
                not self.cross_from_inside or open_price <= profile["vah"] + buffer
            ):
                return "long", profile["vah"], "vah"
        if self.setup_mode in {"two_sided_acceptance", "val_acceptance_short"} and self.allow_short:
            if close < profile["val"] - buffer and (
                not self.cross_from_inside or open_price >= profile["val"] - buffer
            ):
                return "short", profile["val"], "val"
        return None, None, None

    def _start_location_allows(self, direction: str, profile: dict) -> bool:
        first_open = self.session_first_open
        if first_open is None:
            return False
        if self.start_location_filter == "any":
            return True
        if self.start_location_filter == "inside_value":
            return profile["val"] <= first_open <= profile["vah"]
        if self.start_location_filter == "above_vah":
            return direction == "long" and first_open > profile["vah"]
        if self.start_location_filter == "below_val":
            return direction == "short" and first_open < profile["val"]
        if direction == "long":
            return first_open > profile["vah"]
        return first_open < profile["val"]

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _flow_confirms(self, direction: str, imbalance: float) -> bool:
        if direction == "long":
            return imbalance >= self.min_orderflow_imbalance
        return imbalance <= -self.min_orderflow_imbalance

    def _footprint_volume(self, bar: pd.Series, direction: str) -> float:
        column = (
            "footprint_max_buy_imbalance_volume"
            if direction == "long"
            else "footprint_max_sell_imbalance_volume"
        )
        return _finite_float(bar.get(column)) or 0.0

    def _signal(
        self,
        *,
        direction: str,
        boundary: float,
        boundary_type: str,
        profile: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        imbalance: float,
        footprint_volume: float,
    ) -> Signal:
        fields = {
            "setup_mode": self.setup_mode,
            "boundary_type": boundary_type,
            "prior_value_area_high": profile["vah"],
            "prior_value_area_low": profile["val"],
            "prior_point_of_control": profile["poc"],
            "prior_profile_session": profile["session"],
            "prior_profile_total_volume": profile["total_volume"],
            "prior_profile_price_levels": profile["price_levels"],
            "breakout_buffer_ticks": self.breakout_buffer_ticks,
            "flow_mode": self.flow_mode,
            "orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "start_location_filter": self.start_location_filter,
            "session_first_open": self.session_first_open,
            "cross_from_inside": self.cross_from_inside,
            "footprint_imbalance_volume": footprint_volume,
            "min_footprint_imbalance_volume": self.min_footprint_imbalance_volume,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"true_vap_{boundary_type}_acceptance",
            swept_level=float(boundary),
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(boundary),
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
        if self.breakout_buffer_ticks < 0:
            raise ValueError("entry.params.breakout_buffer_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed, signed_volume, large10, or large20.")
        if self.start_location_filter not in self._START_LOCATION_FILTERS:
            raise ValueError(
                f"entry.params.start_location_filter must be one of {sorted(self._START_LOCATION_FILTERS)}."
            )
        if self.min_profile_total_volume < 0 or self.min_profile_price_levels < 0:
            raise ValueError("entry.params profile minimums must be non-negative.")
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
