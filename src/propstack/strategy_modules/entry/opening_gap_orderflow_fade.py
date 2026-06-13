from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OpeningGapOrderflowFadeEntry:
    name = "opening_gap_orderflow_fade"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "late_morning_large20_gap_fade")).lower()
        self.direction_mode = str(params.get("direction_mode", "two_sided_fade")).lower()
        self.flow_mode = str(params.get("flow_mode", "large20_imbalance")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.source_start = parse_time(params.get("source_start", "10:45:00"))
        self.signal_time = parse_time(params.get("signal_time", "11:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:45:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_opening_gap_ticks = float(params.get("min_opening_gap_ticks", 24))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.20))
        self.stop_pct = float(params.get("stop_pct", 0.003))
        self.target_r_multiple = float(params.get("target_r_multiple", 12.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar["session_date"]
        state = self._state(session_date)
        if state["signaled"]:
            return None

        session_start = _session_timestamp(timestamp, self.rth_start)
        source_start = _session_timestamp(timestamp, self.source_start)
        signal_timestamp = _session_timestamp(timestamp, self.signal_time)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        if state["opening"] is None and timestamp >= session_start:
            prev_close = _finite_float(bar.get("prev_rth_close"))
            if prev_close is not None:
                state["opening"] = {
                    "timestamp": timestamp,
                    "open": float(bar["open"]),
                    "prev_rth_close": prev_close,
                }

        if timestamp >= source_start and bar_close <= signal_timestamp:
            state["source_window"] = self._aggregate_bar(
                state["source_window"],
                bar,
                source_start,
                signal_timestamp,
            )

        if bar_close != signal_timestamp:
            return None

        signal = self._signal(state, signal_timestamp)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "opening": None,
                "source_window": None,
                "signaled": False,
            },
        )

    def _signal(self, state: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        opening = state.get("opening")
        source = state.get("source_window")
        if not opening or not source or not self._window_complete(source):
            return None

        prev_close = float(opening["prev_rth_close"])
        opening_price = float(opening["open"])
        gap_points = opening_price - prev_close
        gap_ticks = gap_points / self.tick_size
        if abs(gap_ticks) < self.min_opening_gap_ticks:
            return None

        metrics = _orderflow_metrics(source)
        primary, secondary = self._flow_values(metrics)
        if primary is None:
            return None

        direction = self._direction(gap_ticks, primary, secondary)
        if direction is None:
            return None

        source_open = float(source["open"])
        source_close = float(source["close"])
        source_return_points = source_close - source_open
        source_return_ticks = source_return_points / self.tick_size
        report_fields = {
            "academic_source_key": "empirical_sierra_opening_gap_large_trade_flow_fade",
            "setup_mode": self.setup_mode,
            "feature_method": "sierra_opening_gap_orderflow_fade",
            "direction_mode": self.direction_mode,
            "flow_mode": self.flow_mode,
            "prev_rth_close": prev_close,
            "rth_open": opening_price,
            "opening_gap_points": gap_points,
            "opening_gap_ticks": gap_ticks,
            "opening_gap_direction": "up" if gap_ticks > 0 else "down",
            "source_window_start_timestamp": source["start_timestamp"],
            "source_window_end_timestamp": source["end_timestamp"],
            "source_window_open": source_open,
            "source_window_high": float(source["high"]),
            "source_window_low": float(source["low"]),
            "source_window_close": source_close,
            "source_window_return_points": source_return_points,
            "source_window_return_ticks": source_return_ticks,
            "source_window_volume": float(source["volume"]),
            "source_window_signed_volume": float(source["signed_volume"]),
            "source_window_imbalance": metrics["signed_imbalance"],
            "source_window_large10_imbalance": metrics["large10_imbalance"],
            "source_window_large20_imbalance": metrics["large20_imbalance"],
            "primary_orderflow_imbalance": primary,
            "secondary_orderflow_imbalance": secondary,
            "min_opening_gap_ticks": self.min_opening_gap_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "opening_gap_orderflow_signal_timestamp": signal_timestamp,
            "opening_gap_orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": prev_close,
            "sweep_timestamp": opening["timestamp"],
            "sweep_high": float(source["high"]),
            "sweep_low": float(source["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"opening_gap_orderflow_fade_{self.setup_mode}",
            swept_level=prev_close,
            sweep_timestamp=opening["timestamp"],
            sweep_high=float(source["high"]),
            sweep_low=float(source["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "flow_mode": self.flow_mode,
                "opening_gap_ticks": gap_ticks,
                "primary_orderflow_imbalance": primary,
                "secondary_orderflow_imbalance": secondary,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

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
            return metrics["large20_imbalance"], metrics["signed_imbalance"]
        raise ValueError(
            "opening_gap_orderflow_fade flow_mode must be one of: "
            "signed_imbalance, large10_imbalance, large20_imbalance, broad_large_alignment."
        )

    def _direction(self, gap_ticks: float, primary: float, secondary: float | None) -> str | None:
        threshold = self.min_orderflow_imbalance
        long_ok = gap_ticks < 0 and primary >= threshold and (
            secondary is None or secondary >= threshold
        )
        short_ok = gap_ticks > 0 and primary <= -threshold and (
            secondary is None or secondary <= -threshold
        )
        if self.direction_mode in {"two_sided_fade", "two_sided"}:
            if long_ok:
                return "long"
            if short_ok:
                return "short"
            return None
        if self.direction_mode in {"long_only_fade", "long_only"}:
            return "long" if long_ok else None
        if self.direction_mode in {"short_only_fade", "short_only"}:
            return "short" if short_ok else None
        raise ValueError(
            "opening_gap_orderflow_fade direction_mode must be one of: "
            "two_sided_fade, long_only_fade, short_only_fade."
        )

    def _validate(self) -> None:
        if self.source_start >= self.signal_time:
            raise ValueError("source_start must be before signal_time.")
        if self.min_opening_gap_ticks < 0:
            raise ValueError("min_opening_gap_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")


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
