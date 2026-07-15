from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class ImpulsePauseOrderflowContinuationEntry:
    name = "impulse_pause_orderflow_continuation"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "impulse_pause_breakout"))
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.impulse_bars = int(params.get("impulse_bars", 3))
        self.pause_bars = int(params.get("pause_bars", 2))
        self.max_pullback_fraction = float(params.get("max_pullback_fraction", 0.5))
        self.min_impulse_ticks = float(params.get("min_impulse_ticks", 8))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)

        try:
            row = _CompletedBar.from_series(bar)
        except ValueError:
            return None

        signal = None
        if self.start_time <= bar_close.time() <= self.end_time and not state["signaled"]:
            signal = self._candidate_signal(row, timestamp, bar_close, state)
        state["bars"].append(row)
        return signal

    def _candidate_signal(
        self,
        bar: "_CompletedBar",
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
        state: dict,
    ) -> Signal | None:
        prior_bars: list[_CompletedBar] = state["bars"]
        required = self.impulse_bars + self.pause_bars
        if len(prior_bars) < required:
            return None

        impulse_window = prior_bars[-required : -self.pause_bars]
        pause_window = prior_bars[-self.pause_bars :]
        long_setup = self._long_setup(impulse_window, pause_window, bar)
        short_setup = self._short_setup(impulse_window, pause_window, bar)

        candidates = []
        if self.allow_long and long_setup is not None:
            candidates.append(long_setup)
        if self.allow_short and short_setup is not None:
            candidates.append(short_setup)
        if not candidates:
            return None

        signed, total, imbalance = self._bar_flow(bar.raw)
        if total <= 0:
            return None

        chosen = candidates[0]
        if len(candidates) == 2:
            chosen = max(candidates, key=lambda item: abs(item["breakout_ticks"]))
        direction = chosen["direction"]
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "impulse_pause_orderflow_continuation",
            "setup_mode": self.setup_mode,
            "feature_method": "completed_impulse_pause_breakout_with_sierra_aggregate_orderflow",
            "signal_bar_timestamp": timestamp,
            "signal_close_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
            "signal_direction": direction,
            "flow_mode": self.flow_mode,
            "impulse_start_timestamp": chosen["impulse_start_timestamp"],
            "impulse_end_timestamp": chosen["impulse_end_timestamp"],
            "pause_start_timestamp": chosen["pause_start_timestamp"],
            "pause_end_timestamp": chosen["pause_end_timestamp"],
            "impulse_move_ticks": chosen["impulse_move_ticks"],
            "pause_high": chosen["pause_high"],
            "pause_low": chosen["pause_low"],
            "pause_retrace_fraction": chosen["pause_retrace_fraction"],
            "breakout_level": chosen["breakout_level"],
            "breakout_ticks": chosen["breakout_ticks"],
            "signal_open": bar.open,
            "signal_high": bar.high,
            "signal_low": bar.low,
            "signal_close": bar.close,
            "signal_signed_flow": signed,
            "signal_flow_volume": total,
            "signal_orderflow_imbalance": imbalance,
            "impulse_bars": self.impulse_bars,
            "pause_bars": self.pause_bars,
            "max_pullback_fraction": self.max_pullback_fraction,
            "min_impulse_ticks": self.min_impulse_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": chosen["breakout_level"],
            "sweep_timestamp": timestamp,
            "sweep_high": bar.high,
            "sweep_low": bar.low,
            "reclaim_timestamp": bar_close,
        }
        return Signal(
            direction=direction,
            level_type=f"{direction}_{self.flow_mode}_{self.setup_mode}",
            swept_level=chosen["breakout_level"],
            sweep_timestamp=timestamp,
            sweep_high=bar.high,
            sweep_low=bar.low,
            reclaim_timestamp=bar_close,
            breakout_level=chosen["breakout_level"],
            metadata=report_fields,
            report_fields=report_fields,
        )

    def _long_setup(
        self,
        impulse_window: list["_CompletedBar"],
        pause_window: list["_CompletedBar"],
        bar: "_CompletedBar",
    ) -> dict | None:
        impulse_start = impulse_window[0]
        impulse_end = impulse_window[-1]
        impulse_move = impulse_end.close - impulse_start.open
        impulse_ticks = impulse_move / self.tick_size
        if impulse_ticks < self.min_impulse_ticks:
            return None

        pause_high = max(item.high for item in pause_window)
        pause_low = min(item.low for item in pause_window)
        retrace = max(0.0, impulse_end.close - pause_low)
        retrace_fraction = retrace / impulse_move if impulse_move > 0 else math.inf
        if retrace_fraction > self.max_pullback_fraction:
            return None
        if bar.close <= pause_high or bar.close <= bar.open:
            return None
        breakout_ticks = (bar.close - pause_high) / self.tick_size
        if breakout_ticks <= 0:
            return None
        return {
            "direction": "long",
            "impulse_start_timestamp": impulse_start.timestamp,
            "impulse_end_timestamp": impulse_end.timestamp,
            "pause_start_timestamp": pause_window[0].timestamp,
            "pause_end_timestamp": pause_window[-1].timestamp,
            "impulse_move_ticks": impulse_ticks,
            "pause_high": pause_high,
            "pause_low": pause_low,
            "pause_retrace_fraction": retrace_fraction,
            "breakout_level": pause_high,
            "breakout_ticks": breakout_ticks,
        }

    def _short_setup(
        self,
        impulse_window: list["_CompletedBar"],
        pause_window: list["_CompletedBar"],
        bar: "_CompletedBar",
    ) -> dict | None:
        impulse_start = impulse_window[0]
        impulse_end = impulse_window[-1]
        impulse_move = impulse_start.open - impulse_end.close
        impulse_ticks = impulse_move / self.tick_size
        if impulse_ticks < self.min_impulse_ticks:
            return None

        pause_high = max(item.high for item in pause_window)
        pause_low = min(item.low for item in pause_window)
        retrace = max(0.0, pause_high - impulse_end.close)
        retrace_fraction = retrace / impulse_move if impulse_move > 0 else math.inf
        if retrace_fraction > self.max_pullback_fraction:
            return None
        if bar.close >= pause_low or bar.close >= bar.open:
            return None
        breakout_ticks = (pause_low - bar.close) / self.tick_size
        if breakout_ticks <= 0:
            return None
        return {
            "direction": "short",
            "impulse_start_timestamp": impulse_start.timestamp,
            "impulse_end_timestamp": impulse_end.timestamp,
            "pause_start_timestamp": pause_window[0].timestamp,
            "pause_end_timestamp": pause_window[-1].timestamp,
            "impulse_move_ticks": impulse_ticks,
            "pause_high": pause_high,
            "pause_low": pause_low,
            "pause_retrace_fraction": retrace_fraction,
            "breakout_level": pause_low,
            "breakout_ticks": breakout_ticks,
        }

    def _bar_flow(self, bar: pd.Series) -> tuple[float, float, float]:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col)) or 0.0
        total = _finite_float(bar.get(total_col)) or 0.0
        if total <= 0:
            return signed, total, 0.0
        imbalance = signed / total
        return signed, total, imbalance if math.isfinite(imbalance) else 0.0

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(session_date, {"bars": [], "signaled": False})

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.impulse_bars <= 0 or self.pause_bars <= 0:
            raise ValueError("entry.params.impulse_bars and pause_bars must be greater than 0.")
        if not 0.0 <= self.max_pullback_fraction <= 1.0:
            raise ValueError("entry.params.max_pullback_fraction must be in [0.0, 1.0].")
        if self.min_impulse_ticks <= 0:
            raise ValueError("entry.params.min_impulse_ticks must be greater than 0.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if self.max_trades_per_day <= 0:
            raise ValueError("entry.params.max_trades_per_day must be greater than 0.")


class _CompletedBar:
    def __init__(self, bar: pd.Series):
        self.raw = bar
        self.timestamp = pd.Timestamp(bar["timestamp"])
        self.open = _required_float(bar.get("open"), "open")
        self.high = _required_float(bar.get("high"), "high")
        self.low = _required_float(bar.get("low"), "low")
        self.close = _required_float(bar.get("close"), "close")
        if self.high < self.low:
            raise ValueError("bar high is lower than low.")

    @classmethod
    def from_series(cls, bar: pd.Series) -> "_CompletedBar":
        return cls(bar)


def _required_float(value, name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"bar {name} is not finite.")
    return out


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
