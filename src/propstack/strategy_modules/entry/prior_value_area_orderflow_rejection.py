from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.prior_value_area_orderflow_acceptance import (
    PriorValueAreaOrderflowAcceptanceEntry,
    _finite_float,
)


class PriorValueAreaOrderflowRejectionEntry(PriorValueAreaOrderflowAcceptanceEntry):
    name = "prior_value_area_orderflow_rejection"

    def __init__(self, params: dict):
        normalized = dict(params)
        if "breakout_buffer_ticks" not in normalized and "rejection_buffer_ticks" in normalized:
            normalized["breakout_buffer_ticks"] = normalized["rejection_buffer_ticks"]
        super().__init__(normalized)
        self.rejection_buffer_ticks = self.breakout_buffer_ticks

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

        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if high is None or low is None or close is None:
            return None
        direction, boundary, boundary_type = self._rejection_direction(high, low, close, self.prior_profile)
        if direction is None:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        self.signaled_sessions.add(session_date)
        profile = self.prior_profile
        return Signal(
            direction=direction,
            level_type=f"prior_value_area_{boundary_type}_rejection",
            swept_level=boundary,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            breakout_level=boundary,
            metadata={
                "setup_mode": self.setup_mode,
                "prior_profile_session": profile["session_date"],
                "prior_value_area_high": profile["vah"],
                "prior_value_area_low": profile["val"],
                "prior_point_of_control": profile["poc"],
                "prior_profile_total_volume": profile["total_volume"],
                "prior_profile_bars": profile["bar_count"],
                "value_area_fraction": self.value_area_fraction,
                "boundary_type": boundary_type,
                "rejection_buffer_ticks": self.rejection_buffer_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "setup_mode": self.setup_mode,
                "prior_profile_session": profile["session_date"],
                "prior_value_area_high": profile["vah"],
                "prior_value_area_low": profile["val"],
                "prior_point_of_control": profile["poc"],
                "prior_profile_total_volume": profile["total_volume"],
                "prior_profile_bars": profile["bar_count"],
                "value_area_fraction": self.value_area_fraction,
                "boundary_type": boundary_type,
                "rejection_buffer_ticks": self.rejection_buffer_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "signal_timestamp": bar_close,
                "intended_entry_timestamp": bar_close,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _rejection_direction(
        self,
        high: float,
        low: float,
        close: float,
        profile: dict,
    ) -> tuple[str | None, float | None, str | None]:
        buffer = self.rejection_buffer_ticks * self.tick_size
        if self.setup_mode not in {"two_sided_rejection", "vah_rejection_short", "val_rejection_long"}:
            raise ValueError(
                "entry.params.setup_mode must be two_sided_rejection, vah_rejection_short, or val_rejection_long."
            )
        if (
            self.setup_mode in {"two_sided_rejection", "vah_rejection_short"}
            and self.allow_short
            and high > profile["vah"] + buffer
            and close <= profile["vah"]
        ):
            return "short", profile["vah"], "vah"
        if (
            self.setup_mode in {"two_sided_rejection", "val_rejection_long"}
            and self.allow_long
            and low < profile["val"] - buffer
            and close >= profile["val"]
        ):
            return "long", profile["val"], "val"
        return None, None, None

    def _validate(self) -> None:
        super()._validate()
        setup_mode = str(self.params.get("setup_mode", "two_sided_rejection")).lower()
        if setup_mode not in {"two_sided_rejection", "vah_rejection_short", "val_rejection_long"}:
            raise ValueError(
                "entry.params.setup_mode must be two_sided_rejection, vah_rejection_short, or val_rejection_long."
            )
