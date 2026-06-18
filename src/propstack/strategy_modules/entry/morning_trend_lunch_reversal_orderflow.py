from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class MorningTrendLunchReversalOrderflowEntry:
    name = "morning_trend_lunch_reversal_orderflow"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_reversal")).lower()
        self.start_time = parse_time(params.get("start_time", "10:30:00"))
        self.end_time = parse_time(params.get("end_time", "13:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "14:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_morning_return_ticks = float(params.get("min_morning_return_ticks", 8))
        self.min_counterflow_imbalance = float(params.get("min_counterflow_imbalance", 0.02))
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
        state = self.state_by_session.setdefault(session_date, {"session_open": None, "signaled": False})
        if state["session_open"] is None:
            state["session_open"] = _finite_float(bar.get("open"))
        if state["signaled"]:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        direction, morning_return_ticks, signal_body_ticks = self._direction(bar, state["session_open"])
        if direction is None:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None
        if direction == "long" and imbalance < self.min_counterflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_counterflow_imbalance:
            return None

        close = _finite_float(bar.get("close"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if close is None or high is None or low is None:
            return None

        state["signaled"] = True
        level_type = "morning_up_extension_lunch_reversal" if direction == "short" else "morning_down_extension_lunch_reversal"
        swept_level = high if direction == "short" else low
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=swept_level,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "session_open": state["session_open"],
                "morning_return_ticks": morning_return_ticks,
                "signal_body_ticks": signal_body_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_counterflow_imbalance": self.min_counterflow_imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "setup_mode": self.setup_mode,
                "session_open": state["session_open"],
                "signal_close": close,
                "morning_return_ticks": morning_return_ticks,
                "min_morning_return_ticks": self.min_morning_return_ticks,
                "signal_body_ticks": signal_body_ticks,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_counterflow_imbalance": self.min_counterflow_imbalance,
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _direction(self, bar: pd.Series, session_open: float | None) -> tuple[str | None, float | None, float | None]:
        if session_open is None:
            return None, None, None
        bar_open = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if bar_open is None or close is None:
            return None, None, None
        morning_return_ticks = (close - session_open) / self.tick_size
        signal_body_ticks = (close - bar_open) / self.tick_size
        if (
            self.setup_mode in {"two_sided_reversal", "up_extension_short"}
            and self.allow_short
            and morning_return_ticks >= self.min_morning_return_ticks
            and signal_body_ticks < 0
        ):
            return "short", morning_return_ticks, signal_body_ticks
        if (
            self.setup_mode in {"two_sided_reversal", "down_extension_long"}
            and self.allow_long
            and morning_return_ticks <= -self.min_morning_return_ticks
            and signal_body_ticks > 0
        ):
            return "long", morning_return_ticks, signal_body_ticks
        return None, morning_return_ticks, signal_body_ticks

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _validate(self) -> None:
        if self.setup_mode not in {"two_sided_reversal", "up_extension_short", "down_extension_long"}:
            raise ValueError(
                "entry.params.setup_mode must be two_sided_reversal, up_extension_short, or down_extension_long."
            )
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than zero.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than zero.")
        if self.min_morning_return_ticks < 0:
            raise ValueError("entry.params.min_morning_return_ticks must be non-negative.")
        if self.min_counterflow_imbalance < 0:
            raise ValueError("entry.params.min_counterflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed_volume, large10, or large20.")
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
