from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class RoundNumberBarrierEntry:
    name = "round_number_barrier"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "support_reclaim_long")).lower()
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "14:30:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.barrier_interval_points = float(params.get("barrier_interval_points", 50.0))
        self.buffer_ticks = int(params.get("buffer_ticks", 1))
        self.max_close_distance_ticks = int(params.get("max_close_distance_ticks", 12))
        self.min_bar_range_ticks = int(params.get("min_bar_range_ticks", 2))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_time = timestamp.time()
        if bar_time < self.start_time or bar_time > self.end_time:
            return None

        session_date = bar["session_date"]
        state = self.state_by_day.setdefault(session_date, {"signaled": False, "previous_close": None})
        previous_close = state["previous_close"]
        state["previous_close"] = float(bar["close"])
        if state["signaled"]:
            return None
        if float(bar["high"]) - float(bar["low"]) < self.min_bar_range_ticks * self.tick_size:
            return None

        signal: Signal | None
        if self.setup_mode == "support_reclaim_long":
            signal = self._support_reclaim_long(bar)
        elif self.setup_mode == "resistance_reject_short":
            signal = self._resistance_reject_short(bar)
        elif self.setup_mode == "two_sided_reclaim":
            signal = self._support_reclaim_long(bar) or self._resistance_reject_short(bar)
        elif self.setup_mode == "upside_breakout_long":
            signal = self._upside_breakout_long(bar, previous_close)
        elif self.setup_mode == "downside_breakout_short":
            signal = self._downside_breakout_short(bar, previous_close)
        else:
            raise ValueError(f"Unsupported setup_mode for round_number_barrier: {self.setup_mode}")

        if signal is not None:
            state["signaled"] = True
        return signal

    def _support_reclaim_long(self, bar: pd.Series) -> Signal | None:
        close = float(bar["close"])
        barrier = self._floor_barrier(close)
        if not self._near_close(close, barrier):
            return None
        if float(bar["low"]) <= barrier + self._buffer and close >= barrier + self._buffer:
            return self._signal("long", bar, barrier, "round_number_support_reclaim")
        return None

    def _resistance_reject_short(self, bar: pd.Series) -> Signal | None:
        close = float(bar["close"])
        barrier = self._ceil_barrier(close)
        if not self._near_close(close, barrier):
            return None
        if float(bar["high"]) >= barrier - self._buffer and close <= barrier - self._buffer:
            return self._signal("short", bar, barrier, "round_number_resistance_reject")
        return None

    def _upside_breakout_long(self, bar: pd.Series, previous_close: float | None) -> Signal | None:
        if previous_close is None or not math.isfinite(previous_close):
            return None
        close = float(bar["close"])
        barrier = self._floor_barrier(close)
        if not self._near_close(close, barrier):
            return None
        if previous_close <= barrier - self._buffer and close >= barrier + self._buffer:
            return self._signal("long", bar, barrier, "round_number_upside_breakout")
        return None

    def _downside_breakout_short(self, bar: pd.Series, previous_close: float | None) -> Signal | None:
        if previous_close is None or not math.isfinite(previous_close):
            return None
        close = float(bar["close"])
        barrier = self._ceil_barrier(close)
        if not self._near_close(close, barrier):
            return None
        if previous_close >= barrier + self._buffer and close <= barrier - self._buffer:
            return self._signal("short", bar, barrier, "round_number_downside_breakout")
        return None

    def _signal(self, direction: str, bar: pd.Series, barrier: float, level_type: str) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=barrier,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=barrier,
            metadata={
                "setup_mode": self.setup_mode,
                "barrier": barrier,
                "barrier_interval_points": self.barrier_interval_points,
                "buffer_ticks": self.buffer_ticks,
                "max_close_distance_ticks": self.max_close_distance_ticks,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
            },
            report_fields={
                "academic_source_key": "donaldson_kim_1993_osler_2003_round_number_barriers",
                "setup_mode": self.setup_mode,
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "round_number_barrier": barrier,
                "barrier_interval_points": self.barrier_interval_points,
                "buffer_ticks": self.buffer_ticks,
                "max_close_distance_ticks": self.max_close_distance_ticks,
                "bar_open": float(bar["open"]),
                "bar_high": float(bar["high"]),
                "bar_low": float(bar["low"]),
                "bar_close": float(bar["close"]),
                "signal_stop_pct": self.stop_pct,
                "signal_target_r_multiple": self.target_r_multiple,
            },
        )

    @property
    def _buffer(self) -> float:
        return self.buffer_ticks * self.tick_size

    def _floor_barrier(self, price: float) -> float:
        return math.floor(price / self.barrier_interval_points) * self.barrier_interval_points

    def _ceil_barrier(self, price: float) -> float:
        return math.ceil(price / self.barrier_interval_points) * self.barrier_interval_points

    def _near_close(self, close: float, barrier: float) -> bool:
        return abs(close - barrier) <= self.max_close_distance_ticks * self.tick_size

    def _validate(self) -> None:
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.barrier_interval_points <= 0:
            raise ValueError("barrier_interval_points must be greater than 0.")
        if self.buffer_ticks < 0 or self.max_close_distance_ticks < 0:
            raise ValueError("buffer_ticks and max_close_distance_ticks must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
