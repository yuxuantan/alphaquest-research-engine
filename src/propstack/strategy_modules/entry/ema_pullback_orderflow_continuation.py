from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class EmaPullbackOrderflowContinuationEntry:
    name = "ema_pullback_orderflow_continuation"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_pullback")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.fast_period = int(params.get("fast_period", 12))
        self.slow_period = int(params.get("slow_period", 36))
        self.min_trend_gap_ticks = float(params.get("min_trend_gap_ticks", 4))
        self.pullback_tolerance_ticks = float(params.get("pullback_tolerance_ticks", 2))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self._validate()
        self.state_by_session: dict = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = bar.get("session_date")
        state = self.state_by_session.setdefault(
            session_date,
            {"fast_ema": None, "slow_ema": None, "count": 0, "signaled": False},
        )
        close = _finite_float(bar.get("close"))
        if close is None:
            return None

        signal = None
        if not state["signaled"] and state["count"] >= self.slow_period:
            signal = self._signal_from_bar(bar, state)
            if signal is not None:
                state["signaled"] = True
        self._update_emas(state, close)
        return signal

    def _signal_from_bar(self, bar: pd.Series, state: dict) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        prior_fast = _finite_float(state.get("fast_ema"))
        prior_slow = _finite_float(state.get("slow_ema"))
        bar_open = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if None in {prior_fast, prior_slow, bar_open, high, low, close}:
            return None

        direction, trend_gap_ticks = self._direction(bar_open, high, low, close, prior_fast, prior_slow)
        if direction is None:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        return Signal(
            direction=direction,
            level_type=f"ema_pullback_{direction}_continuation",
            swept_level=prior_fast,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "prior_fast_ema": prior_fast,
                "prior_slow_ema": prior_slow,
                "trend_gap_ticks": trend_gap_ticks,
                "pullback_tolerance_ticks": self.pullback_tolerance_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "setup_mode": self.setup_mode,
                "prior_fast_ema": prior_fast,
                "prior_slow_ema": prior_slow,
                "trend_gap_ticks": trend_gap_ticks,
                "min_trend_gap_ticks": self.min_trend_gap_ticks,
                "pullback_tolerance_ticks": self.pullback_tolerance_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _direction(
        self,
        bar_open: float,
        high: float,
        low: float,
        close: float,
        prior_fast: float,
        prior_slow: float,
    ) -> tuple[str | None, float | None]:
        tolerance = self.pullback_tolerance_ticks * self.tick_size
        up_gap_ticks = (prior_fast - prior_slow) / self.tick_size
        down_gap_ticks = (prior_slow - prior_fast) / self.tick_size
        if (
            self.setup_mode in {"two_sided_pullback", "long_pullback"}
            and self.allow_long
            and up_gap_ticks >= self.min_trend_gap_ticks
            and low <= prior_fast + tolerance
            and close > prior_fast
            and close > bar_open
        ):
            return "long", up_gap_ticks
        if (
            self.setup_mode in {"two_sided_pullback", "short_pullback"}
            and self.allow_short
            and down_gap_ticks >= self.min_trend_gap_ticks
            and high >= prior_fast - tolerance
            and close < prior_fast
            and close < bar_open
        ):
            return "short", down_gap_ticks
        return None, None

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _update_emas(self, state: dict, close: float) -> None:
        state["fast_ema"] = _ema_update(state.get("fast_ema"), close, self.fast_period)
        state["slow_ema"] = _ema_update(state.get("slow_ema"), close, self.slow_period)
        state["count"] += 1

    def _validate(self) -> None:
        if self.setup_mode not in {"two_sided_pullback", "long_pullback", "short_pullback"}:
            raise ValueError("entry.params.setup_mode must be two_sided_pullback, long_pullback, or short_pullback.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than zero.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than zero.")
        if self.fast_period <= 1 or self.slow_period <= 1 or self.fast_period >= self.slow_period:
            raise ValueError("entry.params.fast_period must be > 1 and less than slow_period.")
        if self.min_trend_gap_ticks < 0:
            raise ValueError("entry.params.min_trend_gap_ticks must be non-negative.")
        if self.pullback_tolerance_ticks < 0:
            raise ValueError("entry.params.pullback_tolerance_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed_volume, large10, or large20.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")


def _ema_update(previous: float | None, close: float, period: int) -> float:
    if previous is None or pd.isna(previous):
        return close
    alpha = 2.0 / (period + 1.0)
    return previous + alpha * (close - previous)


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
