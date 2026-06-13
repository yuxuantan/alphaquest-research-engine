from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class GaoLastHalfHourOrderflowEntry:
    name = "gao_last_half_hour_orderflow"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "first_signed_flow_alignment")).lower()
        self.direction_mode = str(params.get("direction_mode", "two_sided_continuation")).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.last_window_start = parse_time(params.get("last_window_start", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "16:00:00"))
        self.first_window_minutes = float(params.get("first_window_minutes", 30))
        self.penultimate_window_minutes = float(params.get("penultimate_window_minutes", 30))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_first_return_ticks = float(params.get("min_first_return_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.min_penultimate_return_ticks = float(params.get("min_penultimate_return_ticks", 0))
        self.stop_pct = float(params.get("stop_pct", 0.0015))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        first_start = _session_timestamp(timestamp, self.rth_start)
        first_end = first_start + pd.Timedelta(minutes=self.first_window_minutes)
        last_start = _session_timestamp(timestamp, self.last_window_start)
        penultimate_start = last_start - pd.Timedelta(minutes=self.penultimate_window_minutes)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        if timestamp >= first_start and bar_close <= first_end:
            state["first_window"] = self._aggregate_bar(
                state["first_window"],
                bar,
                first_start,
                first_end,
            )

        if timestamp >= penultimate_start and bar_close <= last_start:
            state["penultimate_window"] = self._aggregate_bar(
                state["penultimate_window"],
                bar,
                penultimate_start,
                last_start,
            )

        if bar_close != last_start:
            return None

        signal = self._signal(state, last_start)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "first_window": None,
                "penultimate_window": None,
                "signaled": False,
            },
        )

    def _signal(self, state: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        first = state.get("first_window")
        if not first or not self._window_complete(first):
            return None

        first_open = float(first["open"])
        first_close = float(first["close"])
        first_return_points = first_close - first_open
        first_return_ticks = first_return_points / self.tick_size
        if abs(first_return_ticks) < self.min_first_return_ticks:
            return None

        first_metrics = _orderflow_metrics(first)
        primary, secondary = self._flow_values(first_metrics)
        if primary is None:
            return None

        direction = self._direction(first_return_ticks, primary, secondary)
        if direction is None:
            return None

        penultimate_report = self._penultimate_report_fields(state, direction)
        if penultimate_report is None and self.setup_mode == "first_penultimate_signed_flow_alignment":
            return None

        report_fields = {
            "academic_source_key": "gao_han_li_zhou_2018_first_half_hour_last_half_hour_orderflow",
            "setup_mode": self.setup_mode,
            "feature_method": "sierra_first_half_hour_orderflow_to_last_half_hour",
            "direction_mode": self.direction_mode,
            "flow_mode": self.flow_mode,
            "source_return_reference": "rth_open_to_first_half_hour_close",
            "target_window_reference": "last_half_hour_15_30_to_16_00",
            "first_window_start_timestamp": first["start_timestamp"],
            "first_window_end_timestamp": first["end_timestamp"],
            "first_window_open": first_open,
            "first_window_high": float(first["high"]),
            "first_window_low": float(first["low"]),
            "first_window_close": first_close,
            "first_window_return_points": first_return_points,
            "first_window_return_ticks": first_return_ticks,
            "first_window_volume": float(first["volume"]),
            "first_window_signed_volume": float(first["signed_volume"]),
            "first_window_imbalance": first_metrics["signed_imbalance"],
            "first_window_large10_imbalance": first_metrics["large10_imbalance"],
            "first_window_large20_imbalance": first_metrics["large20_imbalance"],
            "primary_orderflow_imbalance": primary,
            "secondary_orderflow_imbalance": secondary,
            "min_first_return_ticks": self.min_first_return_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "late_day_signal_timestamp": signal_timestamp,
            "late_day_entry_window_start": signal_timestamp,
            "late_day_entry_window_end": signal_timestamp + pd.Timedelta(minutes=30),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": first_open,
            "sweep_timestamp": first["start_timestamp"],
            "sweep_high": float(first["high"]),
            "sweep_low": float(first["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        report_fields.update(penultimate_report or {})

        return Signal(
            direction=direction,
            level_type=f"gao_last_half_hour_orderflow_{self.setup_mode}",
            swept_level=first_open,
            sweep_timestamp=first["start_timestamp"],
            sweep_high=float(first["high"]),
            sweep_low=float(first["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "flow_mode": self.flow_mode,
                "first_window_return_ticks": first_return_ticks,
                "primary_orderflow_imbalance": primary,
                "secondary_orderflow_imbalance": secondary,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _penultimate_report_fields(self, state: dict, direction: str) -> dict | None:
        penultimate = state.get("penultimate_window")
        if self.setup_mode != "first_penultimate_signed_flow_alignment":
            return {}
        if not penultimate or not self._window_complete(penultimate):
            return None

        penultimate_open = float(penultimate["open"])
        penultimate_close = float(penultimate["close"])
        penultimate_return_points = penultimate_close - penultimate_open
        penultimate_return_ticks = penultimate_return_points / self.tick_size
        if abs(penultimate_return_ticks) < self.min_penultimate_return_ticks:
            return None
        if not _same_direction(direction, penultimate_return_ticks):
            return None

        metrics = _orderflow_metrics(penultimate)
        signed_imbalance = metrics["signed_imbalance"]
        if signed_imbalance is None:
            return None
        if direction == "long" and signed_imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and signed_imbalance > -self.min_orderflow_imbalance:
            return None

        return {
            "penultimate_window_start_timestamp": penultimate["start_timestamp"],
            "penultimate_window_end_timestamp": penultimate["end_timestamp"],
            "penultimate_window_open": penultimate_open,
            "penultimate_window_close": penultimate_close,
            "penultimate_window_return_points": penultimate_return_points,
            "penultimate_window_return_ticks": penultimate_return_ticks,
            "penultimate_window_volume": float(penultimate["volume"]),
            "penultimate_window_signed_volume": float(penultimate["signed_volume"]),
            "penultimate_window_imbalance": signed_imbalance,
            "penultimate_window_large20_imbalance": metrics["large20_imbalance"],
            "min_penultimate_return_ticks": self.min_penultimate_return_ticks,
        }

    def _aggregate_bar(self, aggregate: dict | None, bar: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
        if aggregate is None or aggregate.get("start_timestamp") != start or aggregate.get("end_timestamp") != end:
            return {
                "start_timestamp": start,
                "end_timestamp": end,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": _finite_float(bar.get("volume")) or 0.0,
                "signed_volume": _finite_float(bar.get("signed_volume")) or 0.0,
                "large10_volume": _finite_float(bar.get("large10_volume")) or 0.0,
                "large10_signed_volume": _finite_float(bar.get("large10_signed_volume")) or 0.0,
                "large20_volume": _finite_float(bar.get("large20_volume")) or 0.0,
                "large20_signed_volume": _finite_float(bar.get("large20_signed_volume")) or 0.0,
                "bar_count": 1,
            }

        aggregate["high"] = max(float(aggregate["high"]), float(bar["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(bar["low"]))
        aggregate["close"] = float(bar["close"])
        for column in [
            "volume",
            "signed_volume",
            "large10_volume",
            "large10_signed_volume",
            "large20_volume",
            "large20_signed_volume",
        ]:
            aggregate[column] = float(aggregate[column]) + (_finite_float(bar.get(column)) or 0.0)
        aggregate["bar_count"] += 1
        return aggregate

    def _window_complete(self, window: dict) -> bool:
        start = pd.Timestamp(window["start_timestamp"])
        end = pd.Timestamp(window["end_timestamp"])
        minutes = (end - start).total_seconds() / 60
        expected = max(1, int(math.ceil(minutes / self.bar_interval_minutes)))
        return int(window.get("bar_count", 0)) >= expected

    def _flow_values(self, metrics: dict) -> tuple[float | None, float | None]:
        if self.flow_mode in {"signed_imbalance", "all_volume_imbalance"}:
            return metrics["signed_imbalance"], None
        if self.flow_mode in {"large10_imbalance", "large10"}:
            return metrics["large10_imbalance"], None
        if self.flow_mode in {"large20_imbalance", "large20"}:
            return metrics["large20_imbalance"], None
        if self.flow_mode in {"broad_large_alignment", "signed_and_large20"}:
            return metrics["signed_imbalance"], metrics["large20_imbalance"]
        raise ValueError(
            "gao_last_half_hour_orderflow flow_mode must be one of: "
            "signed_imbalance, large10_imbalance, large20_imbalance, broad_large_alignment."
        )

    def _direction(self, return_ticks: float, primary: float, secondary: float | None) -> str | None:
        threshold = self.min_orderflow_imbalance
        long_ok = return_ticks > 0 and primary >= threshold and (
            secondary is None or secondary >= threshold
        )
        short_ok = return_ticks < 0 and primary <= -threshold and (
            secondary is None or secondary <= -threshold
        )
        if self.direction_mode in {"two_sided_continuation", "two_sided"}:
            if long_ok:
                return "long"
            if short_ok:
                return "short"
            return None
        if self.direction_mode in {"long_only_continuation", "long_only"}:
            return "long" if long_ok else None
        if self.direction_mode in {"short_only_continuation", "short_only"}:
            return "short" if short_ok else None
        raise ValueError(
            "gao_last_half_hour_orderflow direction_mode must be one of: "
            "two_sided_continuation, long_only_continuation, short_only_continuation."
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.first_window_minutes <= 0:
            raise ValueError("first_window_minutes must be greater than 0.")
        if self.penultimate_window_minutes <= 0:
            raise ValueError("penultimate_window_minutes must be greater than 0.")
        if self.min_first_return_ticks < 0:
            raise ValueError("min_first_return_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.min_penultimate_return_ticks < 0:
            raise ValueError("min_penultimate_return_ticks must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        valid_setups = {
            "first_signed_flow_alignment",
            "first_large20_flow_alignment",
            "first_penultimate_signed_flow_alignment",
        }
        if self.setup_mode not in valid_setups:
            raise ValueError(f"gao_last_half_hour_orderflow setup_mode must be one of: {sorted(valid_setups)}.")


def _same_direction(direction: str, value: float) -> bool:
    if direction == "long":
        return value > 0
    if direction == "short":
        return value < 0
    return False


def _orderflow_metrics(source: dict) -> dict:
    volume = float(source.get("volume", 0.0))
    large10_volume = float(source.get("large10_volume", 0.0))
    large20_volume = float(source.get("large20_volume", 0.0))
    return {
        "signed_imbalance": _ratio(source.get("signed_volume"), volume),
        "large10_imbalance": _ratio(source.get("large10_signed_volume"), large10_volume),
        "large20_imbalance": _ratio(source.get("large20_signed_volume"), large20_volume),
    }


def _ratio(numerator, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    value = _finite_float(numerator)
    if value is None:
        return None
    return value / denominator


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )
