from __future__ import annotations

import math
from statistics import fmean, pstdev

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class RollingStatEnvelopeOrderflowReversionEntry:
    name = "rolling_stat_envelope_orderflow_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.lookback_bars = int(params.get("lookback_bars", 24))
        self.band_z = float(params.get("band_z", 1.5))
        self.min_std_ticks = float(params.get("min_std_ticks", 1.0))
        self.min_bar_range_ticks = float(params.get("min_bar_range_ticks", 0.0))
        self.orderflow_mode = str(params.get("orderflow_mode", "signed")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.05))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)
        try:
            if state["completed"] or trades_today >= self.max_trades_per_day:
                return None
            bar_time = timestamp.time()
            if bar_time < self.start_time or bar_time > self.end_time:
                return None
            if len(state["closes"]) < self.lookback_bars:
                return None
            if self._bar_range_ticks(bar) < self.min_bar_range_ticks:
                return None

            mean = fmean(state["closes"][-self.lookback_bars :])
            std = pstdev(state["closes"][-self.lookback_bars :])
            min_std = self.min_std_ticks * self.tick_size
            if not math.isfinite(std) or std < min_std:
                return None
            upper = mean + self.band_z * std
            lower = mean - self.band_z * std
            close = _required_float(bar.get("close"), "close")
            imbalance = self._orderflow_imbalance(bar)
            if imbalance is None:
                return None

            signal = None
            if close <= lower and self.allow_long and imbalance <= -self.min_orderflow_imbalance:
                signal = self._signal(bar, "long", lower, mean, std, upper, lower, imbalance)
            elif close >= upper and self.allow_short and imbalance >= self.min_orderflow_imbalance:
                signal = self._signal(bar, "short", upper, mean, std, upper, lower, imbalance)
            if signal is not None:
                state["completed"] = True
            return signal
        finally:
            self._record_bar(state, bar)

    def _signal(
        self,
        bar: pd.Series,
        direction: str,
        touched_level: float,
        mean: float,
        std: float,
        upper: float,
        lower: float,
        imbalance: float,
    ) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        close = _required_float(bar.get("close"), "close")
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        deviation_ticks = abs(close - mean) / self.tick_size
        report_fields = {
            "feature_method": "prior_completed_rolling_close_envelope",
            "setup_mode": "rolling_stat_envelope_orderflow_reversion",
            "orderflow_mode": self.orderflow_mode,
            "flow_confirmation": "same_side_pressure_into_envelope_extreme",
            "lookback_bars": self.lookback_bars,
            "band_z": self.band_z,
            "rolling_mean": mean,
            "rolling_std": std,
            "upper_band": upper,
            "lower_band": lower,
            "touched_band": touched_level,
            "signal_close": close,
            "deviation_ticks": deviation_ticks,
            "orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_bar_range_ticks": self._bar_range_ticks(bar),
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type="rolling_stat_lower_band_reversion" if direction == "long" else "rolling_stat_upper_band_reversion",
            swept_level=touched_level,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=timestamp,
            metadata={
                "setup_mode": "rolling_stat_envelope_orderflow_reversion",
                "orderflow_mode": self.orderflow_mode,
                "orderflow_imbalance": imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = {
            "signed": ("signed_volume", "volume"),
            "large10": ("large10_signed_volume", "large10_volume"),
            "large20": ("large20_signed_volume", "large20_volume"),
        }[self.orderflow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        return signed / volume

    def _bar_range_ticks(self, bar: pd.Series) -> float:
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        return (high - low) / self.tick_size

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(session_date, {"closes": [], "completed": False})

    def _record_bar(self, state: dict, bar: pd.Series) -> None:
        close = _finite_float(bar.get("close"))
        if close is None:
            return
        state["closes"].append(close)
        state["closes"][:] = state["closes"][-self.lookback_bars :]

    def _validate(self) -> None:
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.lookback_bars < 3:
            raise ValueError("lookback_bars must be at least 3.")
        if self.band_z <= 0 or not math.isfinite(self.band_z):
            raise ValueError("band_z must be positive and finite.")
        if self.min_std_ticks < 0 or self.min_bar_range_ticks < 0:
            raise ValueError("min_std_ticks and min_bar_range_ticks must be non-negative.")
        if self.orderflow_mode not in {"signed", "large10", "large20"}:
            raise ValueError("orderflow_mode must be signed, large10, or large20.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _required_float(value, name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"entry bar is missing finite {name}.")
    return out
