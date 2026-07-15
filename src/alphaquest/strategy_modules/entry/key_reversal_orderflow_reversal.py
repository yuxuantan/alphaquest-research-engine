from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class KeyReversalOrderflowReversalEntry:
    name = "key_reversal_orderflow_reversal"

    _FLOW_COLUMNS = {
        "signed": ("signed_volume", "volume"),
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_key_reversal"))
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_sweep_ticks = float(params.get("min_sweep_ticks", 1))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0))
        self.min_body_ticks = float(params.get("min_body_ticks", 1))
        self.min_close_location = float(params.get("min_close_location", 0.65))
        self.min_volume_ratio = float(params.get("min_volume_ratio", 0.90))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_session: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_session.setdefault(session_date, {"prior_bar": None, "signaled": False})

        signal = None
        if trades_today < self.max_trades_per_day and not state["signaled"]:
            signal = self._signal_from_completed_bar(bar, state.get("prior_bar"))
            if signal is not None:
                state["signaled"] = True

        state["prior_bar"] = bar.copy()
        return signal

    def _signal_from_completed_bar(self, bar: pd.Series, prior_bar: pd.Series | None) -> Signal | None:
        if prior_bar is None:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        bar_open = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        volume_ratio = _finite_float(bar.get("volume_ratio"))
        prior_high = _finite_float(prior_bar.get("high"))
        prior_low = _finite_float(prior_bar.get("low"))
        prior_close = _finite_float(prior_bar.get("close"))
        if any(
            value is None
            for value in [bar_open, high, low, close, volume_ratio, prior_high, prior_low, prior_close]
        ):
            return None
        if volume_ratio < self.min_volume_ratio:
            return None

        bar_range = high - low
        if bar_range <= 0:
            return None
        body_ticks = (close - bar_open) / self.tick_size
        close_location = (close - low) / bar_range
        flow = self._orderflow_imbalance(bar)
        if flow is None:
            return None

        sweep_distance = self.min_sweep_ticks * self.tick_size
        reclaim_buffer = self.reclaim_buffer_ticks * self.tick_size
        long_ok = (
            self.allow_long
            and low <= prior_low - sweep_distance
            and close >= prior_close + reclaim_buffer
            and body_ticks >= self.min_body_ticks
            and close_location >= self.min_close_location
            and flow >= self.min_orderflow_imbalance
        )
        short_ok = (
            self.allow_short
            and high >= prior_high + sweep_distance
            and close <= prior_close - reclaim_buffer
            and body_ticks <= -self.min_body_ticks
            and close_location <= 1.0 - self.min_close_location
            and flow <= -self.min_orderflow_imbalance
        )
        if long_ok and short_ok:
            return None
        if long_ok:
            return self._signal(
                "long",
                bar,
                signal_timestamp,
                level=prior_low,
                prior_high=prior_high,
                prior_low=prior_low,
                prior_close=prior_close,
                body_ticks=body_ticks,
                close_location=close_location,
                volume_ratio=volume_ratio,
                orderflow_imbalance=flow,
            )
        if short_ok:
            return self._signal(
                "short",
                bar,
                signal_timestamp,
                level=prior_high,
                prior_high=prior_high,
                prior_low=prior_low,
                prior_close=prior_close,
                body_ticks=body_ticks,
                close_location=close_location,
                volume_ratio=volume_ratio,
                orderflow_imbalance=flow,
            )
        return None

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        *,
        level: float,
        prior_high: float,
        prior_low: float,
        prior_close: float,
        body_ticks: float,
        close_location: float,
        volume_ratio: float,
        orderflow_imbalance: float,
    ) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        high = float(bar["high"])
        low = float(bar["low"])
        report_fields = {
            "academic_source_key": "technical_pattern_orderflow_reversal",
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_prior_bar_sweep_reclaim_with_sierra_aggregate_orderflow",
            "signal_bar_timestamp": timestamp,
            "signal_close_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_direction": direction,
            "flow_mode": self.flow_mode,
            "prior_bar_high": prior_high,
            "prior_bar_low": prior_low,
            "prior_bar_close": prior_close,
            "swept_level": level,
            "signal_open": float(bar["open"]),
            "signal_high": high,
            "signal_low": low,
            "signal_close": float(bar["close"]),
            "signal_body_ticks": body_ticks,
            "signal_close_location": close_location,
            "signal_volume_ratio": volume_ratio,
            "signal_orderflow_imbalance": orderflow_imbalance,
            "min_sweep_ticks": self.min_sweep_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "min_body_ticks": self.min_body_ticks,
            "min_close_location": self.min_close_location,
            "min_volume_ratio": self.min_volume_ratio,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{direction}_{self.flow_mode}_{self.setup_mode}",
            swept_level=level,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            breakout_level=level,
            metadata=report_fields,
            report_fields=report_fields,
        )

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _validate(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than zero.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than zero.")
        if self.min_sweep_ticks < 0:
            raise ValueError("entry.params.min_sweep_ticks must be non-negative.")
        if self.reclaim_buffer_ticks < 0:
            raise ValueError("entry.params.reclaim_buffer_ticks must be non-negative.")
        if self.min_body_ticks < 0:
            raise ValueError("entry.params.min_body_ticks must be non-negative.")
        if not 0.5 <= self.min_close_location < 1.0:
            raise ValueError("entry.params.min_close_location must be in [0.5, 1.0).")
        if self.min_volume_ratio < 0:
            raise ValueError("entry.params.min_volume_ratio must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be one of signed_volume, signed, large10, or large20.")
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
