from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.prior_value_area_orderflow_acceptance import (
    PriorValueAreaOrderflowAcceptanceEntry,
    _finite_float,
)


class PriorPocOrderflowMagnetEntry(PriorValueAreaOrderflowAcceptanceEntry):
    name = "prior_poc_orderflow_magnet"

    def __init__(self, params: dict):
        normalized = dict(params)
        if "breakout_buffer_ticks" not in normalized and "poc_buffer_ticks" in normalized:
            normalized["breakout_buffer_ticks"] = normalized["poc_buffer_ticks"]
        super().__init__(normalized)
        self.poc_buffer_ticks = self.breakout_buffer_ticks
        self.min_poc_distance_ticks = int(params.get("min_poc_distance_ticks", 8))
        self.max_poc_distance_ticks = int(params.get("max_poc_distance_ticks", 160))
        self.min_toward_move_ticks = int(params.get("min_toward_move_ticks", 1))
        self.require_open_same_side = bool(params.get("require_open_same_side", True))
        self._validate_poc_params()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None
        self.current_session_bars.append(bar)

        session_date = bar.get("session_date")
        if self.prior_profile is None:
            return None
        if session_date in self.signaled_sessions:
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        direction = self._magnet_direction(bar, self.prior_profile)
        if direction is None:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if high is None or low is None or close is None:
            return None

        self.signaled_sessions.add(session_date)
        profile = self.prior_profile
        poc = profile["poc"]
        side = "above" if close > poc else "below"
        distance_ticks = abs(close - poc) / self.tick_size
        return Signal(
            direction=direction,
            level_type=f"prior_poc_{side}_magnet",
            swept_level=poc,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            breakout_level=poc,
            metadata={
                "setup_mode": self.setup_mode,
                "prior_profile_session": profile["session_date"],
                "prior_point_of_control": poc,
                "prior_value_area_high": profile["vah"],
                "prior_value_area_low": profile["val"],
                "prior_profile_total_volume": profile["total_volume"],
                "prior_profile_bars": profile["bar_count"],
                "poc_side": side,
                "poc_distance_ticks": distance_ticks,
                "min_poc_distance_ticks": self.min_poc_distance_ticks,
                "max_poc_distance_ticks": self.max_poc_distance_ticks,
                "poc_buffer_ticks": self.poc_buffer_ticks,
                "min_toward_move_ticks": self.min_toward_move_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "setup_mode": self.setup_mode,
                "prior_profile_session": profile["session_date"],
                "prior_point_of_control": poc,
                "prior_value_area_high": profile["vah"],
                "prior_value_area_low": profile["val"],
                "prior_profile_total_volume": profile["total_volume"],
                "prior_profile_bars": profile["bar_count"],
                "poc_side": side,
                "poc_distance_ticks": distance_ticks,
                "min_poc_distance_ticks": self.min_poc_distance_ticks,
                "max_poc_distance_ticks": self.max_poc_distance_ticks,
                "poc_buffer_ticks": self.poc_buffer_ticks,
                "min_toward_move_ticks": self.min_toward_move_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "signal_timestamp": bar_close,
                "intended_entry_timestamp": bar_close,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _magnet_direction(self, bar: pd.Series, profile: dict) -> str | None:
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if open_price is None or close is None:
            return None
        poc = float(profile["poc"])
        buffer = self.poc_buffer_ticks * self.tick_size
        distance_ticks = abs(close - poc) / self.tick_size
        if distance_ticks < self.min_poc_distance_ticks:
            return None
        if self.max_poc_distance_ticks > 0 and distance_ticks > self.max_poc_distance_ticks:
            return None

        toward_move = self.min_toward_move_ticks * self.tick_size
        if (
            self.setup_mode in {"two_sided_magnet", "above_poc_magnet_short"}
            and self.allow_short
            and close > poc + buffer
            and open_price - close >= toward_move
            and self._session_open_same_side("above", poc)
        ):
            return "short"
        if (
            self.setup_mode in {"two_sided_magnet", "below_poc_magnet_long"}
            and self.allow_long
            and close < poc - buffer
            and close - open_price >= toward_move
            and self._session_open_same_side("below", poc)
        ):
            return "long"
        return None

    def _session_open_same_side(self, side: str, poc: float) -> bool:
        if not self.require_open_same_side or not self.current_session_bars:
            return True
        first_open = _finite_float(self.current_session_bars[0].get("open"))
        if first_open is None:
            return False
        if side == "above":
            return first_open > poc
        return first_open < poc

    def _validate(self) -> None:
        super()._validate()
        setup_mode = str(self.params.get("setup_mode", "two_sided_magnet")).lower()
        if setup_mode not in {"two_sided_magnet", "above_poc_magnet_short", "below_poc_magnet_long"}:
            raise ValueError(
                "entry.params.setup_mode must be two_sided_magnet, "
                "above_poc_magnet_short, or below_poc_magnet_long."
            )

    def _validate_poc_params(self) -> None:
        if self.min_poc_distance_ticks < 1:
            raise ValueError("entry.params.min_poc_distance_ticks must be at least 1.")
        if self.max_poc_distance_ticks < 0:
            raise ValueError("entry.params.max_poc_distance_ticks must be non-negative.")
        if 0 < self.max_poc_distance_ticks < self.min_poc_distance_ticks:
            raise ValueError("entry.params.max_poc_distance_ticks must be >= min_poc_distance_ticks or 0.")
        if self.min_toward_move_ticks < 0:
            raise ValueError("entry.params.min_toward_move_ticks must be non-negative.")
