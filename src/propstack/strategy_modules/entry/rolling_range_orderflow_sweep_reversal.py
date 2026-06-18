from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class RollingRangeOrderflowSweepReversalEntry:
    name = "rolling_range_orderflow_sweep_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.lookback_bars = int(params.get("lookback_bars", 12))
        self.min_sweep_ticks = float(params.get("min_sweep_ticks", 1))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0))
        self.flow_mode = str(params.get("flow_mode", "signed")).lower()
        self.min_absorption_imbalance = float(params.get("min_absorption_imbalance", 0.0))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.setdefault(session_date, {"bars": [], "signaled": False})
        signal = None
        if trades_today < self.max_trades_per_day and not state["signaled"]:
            signal = self._signal_from_completed_bar(bar, state["bars"])
            if signal is not None:
                state["signaled"] = True
        state["bars"].append(bar.copy())
        return signal

    def _signal_from_completed_bar(self, bar: pd.Series, prior_bars: list[pd.Series]) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        if timestamp.time() < self.start_time or timestamp.time() > self.end_time:
            return None
        if len(prior_bars) < self.lookback_bars:
            return None

        window = prior_bars[-self.lookback_bars :]
        prior_high = max(float(item["high"]) for item in window)
        prior_low = min(float(item["low"]) for item in window)
        sweep = self.min_sweep_ticks * self.tick_size
        reclaim = self.reclaim_buffer_ticks * self.tick_size
        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None

        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        if (
            self.allow_long
            and low <= prior_low - sweep
            and close >= prior_low + reclaim
            and imbalance <= -self.min_absorption_imbalance
        ):
            return self._signal("long", bar, prior_low, prior_high, imbalance)
        if (
            self.allow_short
            and high >= prior_high + sweep
            and close <= prior_high - reclaim
            and imbalance >= self.min_absorption_imbalance
        ):
            return self._signal("short", bar, prior_low, prior_high, imbalance)
        return None

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        rolling_low: float,
        rolling_high: float,
        imbalance: float,
    ) -> Signal:
        level = rolling_low if direction == "long" else rolling_high
        return Signal(
            direction=direction,
            level_type="rolling_range_orderflow_sweep_reversal",
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar["timestamp"],
            metadata={
                "rolling_low": rolling_low,
                "rolling_high": rolling_high,
                "lookback_bars": self.lookback_bars,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_absorption_imbalance": self.min_absorption_imbalance,
            },
            report_fields={
                "breakout_timestamp": bar["timestamp"],
                "rolling_low": rolling_low,
                "rolling_high": rolling_high,
                "lookback_bars": self.lookback_bars,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_absorption_imbalance": self.min_absorption_imbalance,
                "min_sweep_ticks": self.min_sweep_ticks,
                "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            },
        )

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = {
            "signed": ("signed_volume", "volume"),
            "large10": ("large10_signed_volume", "large10_volume"),
            "large20": ("large20_signed_volume", "large20_volume"),
        }[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        return signed / volume

    def _validate(self) -> None:
        if self.lookback_bars < 2:
            raise ValueError("entry.params.lookback_bars must be at least 2.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.flow_mode not in {"signed", "large10", "large20"}:
            raise ValueError("entry.params.flow_mode must be one of: signed, large10, large20.")
        if self.min_absorption_imbalance < 0:
            raise ValueError("entry.params.min_absorption_imbalance must be non-negative.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
