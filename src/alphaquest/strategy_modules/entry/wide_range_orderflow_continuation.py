from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class WideRangeOrderflowContinuationEntry:
    name = "wide_range_orderflow_continuation"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "wide_range_orderflow_continuation"))
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_range_ticks = float(params.get("min_range_ticks", 8))
        self.min_body_ticks = float(params.get("min_body_ticks", 4))
        self.min_close_location = float(params.get("min_close_location", 0.70))
        self.min_volume_ratio = float(params.get("min_volume_ratio", 1.0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.03))
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
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)
        if state["signaled"]:
            return None

        open_price = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        volume_ratio = _finite_float(bar.get("volume_ratio"))
        if any(value is None for value in [open_price, high, low, close, volume_ratio]):
            return None
        if volume_ratio < self.min_volume_ratio:
            return None

        bar_range = high - low
        if bar_range <= 0:
            return None
        range_ticks = bar_range / self.tick_size
        body_ticks = (close - open_price) / self.tick_size
        if range_ticks < self.min_range_ticks or abs(body_ticks) < self.min_body_ticks:
            return None

        close_location = (close - low) / bar_range
        direction = self._direction(body_ticks, close_location)
        if direction is None:
            return None

        signed, total, imbalance = self._bar_flow(bar)
        if total <= 0:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "volume_return_orderflow_price_pressure_continuation",
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_wide_range_with_sierra_aggregate_orderflow",
            "signal_bar_timestamp": timestamp,
            "signal_close_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
            "signal_direction": direction,
            "flow_mode": self.flow_mode,
            "signal_open": open_price,
            "signal_high": high,
            "signal_low": low,
            "signal_close": close,
            "signal_return_ticks": body_ticks,
            "signal_range_ticks": range_ticks,
            "signal_close_location": close_location,
            "signal_volume_ratio": volume_ratio,
            "signal_signed_flow": signed,
            "signal_flow_volume": total,
            "signal_orderflow_imbalance": imbalance,
            "min_range_ticks": self.min_range_ticks,
            "min_body_ticks": self.min_body_ticks,
            "min_close_location": self.min_close_location,
            "min_volume_ratio": self.min_volume_ratio,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": close,
            "sweep_timestamp": timestamp,
            "sweep_high": high,
            "sweep_low": low,
            "reclaim_timestamp": bar_close,
        }
        return Signal(
            direction=direction,
            level_type=f"{direction}_{self.flow_mode}_{self.setup_mode}",
            swept_level=close,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            breakout_level=close,
            metadata=report_fields,
            report_fields=report_fields,
        )

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def _direction(self, body_ticks: float, close_location: float) -> str | None:
        long_ok = (
            self.allow_long
            and body_ticks > 0
            and close_location >= self.min_close_location
        )
        short_ok = (
            self.allow_short
            and body_ticks < 0
            and close_location <= 1.0 - self.min_close_location
        )
        if long_ok:
            return "long"
        if short_ok:
            return "short"
        return None

    def _bar_flow(self, bar: pd.Series) -> tuple[float, float, float]:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col)) or 0.0
        total = _finite_float(bar.get(total_col)) or 0.0
        if total <= 0:
            return signed, total, 0.0
        imbalance = signed / total
        return signed, total, imbalance if math.isfinite(imbalance) else 0.0

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.min_range_ticks <= 0 or self.min_body_ticks <= 0:
            raise ValueError("entry.params.min_range_ticks and min_body_ticks must be greater than 0.")
        if not 0.5 <= self.min_close_location < 1.0:
            raise ValueError("entry.params.min_close_location must be in [0.5, 1.0).")
        if self.min_volume_ratio < 0:
            raise ValueError("entry.params.min_volume_ratio must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if self.max_trades_per_day <= 0:
            raise ValueError("entry.params.max_trades_per_day must be greater than 0.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
