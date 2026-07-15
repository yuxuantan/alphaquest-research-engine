from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class PriorValueAreaOrderflowAcceptanceEntry:
    name = "prior_value_area_orderflow_acceptance"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_acceptance")).lower()
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.value_area_fraction = float(params.get("value_area_fraction", 0.70))
        self.breakout_buffer_ticks = int(params.get("breakout_buffer_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.min_prior_profile_bars = int(params.get("min_prior_profile_bars", 20))
        self._validate()

        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.prior_profile: dict | None = None
        self.signaled_sessions: set = set()

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

        close = _finite_float(bar.get("close"))
        if close is None:
            return None
        direction, boundary, boundary_type = self._trigger_direction(close, self.prior_profile)
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
            level_type=f"prior_value_area_{boundary_type}_acceptance",
            swept_level=boundary,
            sweep_timestamp=profile["session_date"],
            sweep_high=profile["vah"],
            sweep_low=profile["val"],
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
                "breakout_buffer_ticks": self.breakout_buffer_ticks,
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
                "breakout_buffer_ticks": self.breakout_buffer_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "signal_timestamp": bar_close,
                "intended_entry_timestamp": bar_close,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.prior_profile = self._build_profile(self.current_session, self.current_session_bars)
        self.current_session = session_date
        self.current_session_bars = []

    def _trigger_direction(self, close: float, profile: dict) -> tuple[str | None, float | None, str | None]:
        buffer = self.breakout_buffer_ticks * self.tick_size
        if self.setup_mode not in {"two_sided_acceptance", "vah_acceptance_long", "val_acceptance_short"}:
            raise ValueError(
                "entry.params.setup_mode must be two_sided_acceptance, vah_acceptance_long, or val_acceptance_short."
            )
        if (
            self.setup_mode in {"two_sided_acceptance", "vah_acceptance_long"}
            and self.allow_long
            and close > profile["vah"] + buffer
        ):
            return "long", profile["vah"], "vah"
        if (
            self.setup_mode in {"two_sided_acceptance", "val_acceptance_short"}
            and self.allow_short
            and close < profile["val"] - buffer
        ):
            return "short", profile["val"], "val"
        return None, None, None

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _build_profile(self, session_date, bars: list[pd.Series]) -> dict | None:
        if len(bars) < self.min_prior_profile_bars:
            return None
        volume_by_tick: dict[int, float] = {}
        bar_count = 0
        for bar in bars:
            volume = _finite_float(bar.get("volume"))
            low = _finite_float(bar.get("low"))
            high = _finite_float(bar.get("high"))
            if volume is None or volume <= 0 or low is None or high is None:
                continue
            low_tick = math.floor(low / self.tick_size)
            high_tick = math.ceil(high / self.tick_size)
            if high_tick < low_tick:
                continue
            ticks = list(range(low_tick, high_tick + 1))
            if not ticks:
                continue
            per_tick = volume / len(ticks)
            for tick in ticks:
                volume_by_tick[tick] = volume_by_tick.get(tick, 0.0) + per_tick
            bar_count += 1
        if bar_count < self.min_prior_profile_bars or not volume_by_tick:
            return None

        prices = sorted(volume_by_tick)
        total_volume = sum(volume_by_tick.values())
        if total_volume <= 0:
            return None
        poc_tick = max(prices, key=lambda tick: (volume_by_tick[tick], -abs(tick - (prices[0] + prices[-1]) / 2)))
        poc_index = prices.index(poc_tick)
        left = right = poc_index
        included = volume_by_tick[poc_tick]
        target_volume = self.value_area_fraction * total_volume
        while included < target_volume and (left > 0 or right < len(prices) - 1):
            left_volume = volume_by_tick[prices[left - 1]] if left > 0 else -1.0
            right_volume = volume_by_tick[prices[right + 1]] if right < len(prices) - 1 else -1.0
            if left_volume > right_volume:
                left -= 1
                included += left_volume
            elif right_volume > left_volume:
                right += 1
                included += right_volume
            else:
                if left > 0:
                    left -= 1
                    included += left_volume
                if right < len(prices) - 1 and included < target_volume:
                    right += 1
                    included += right_volume

        return {
            "session_date": session_date,
            "val": prices[left] * self.tick_size,
            "vah": prices[right] * self.tick_size,
            "poc": poc_tick * self.tick_size,
            "total_volume": total_volume,
            "bar_count": bar_count,
        }

    def _validate(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if not 0 < self.value_area_fraction <= 1:
            raise ValueError("entry.params.value_area_fraction must be in (0, 1].")
        if self.breakout_buffer_ticks < 0:
            raise ValueError("entry.params.breakout_buffer_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed_volume, large10, or large20.")
        if self.min_prior_profile_bars <= 0:
            raise ValueError("entry.params.min_prior_profile_bars must be greater than 0.")

def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
