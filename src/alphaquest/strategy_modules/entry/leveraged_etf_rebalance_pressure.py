from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class LeveragedEtfRebalancePressureEntry:
    name = "leveraged_etf_rebalance_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_rebalance_pressure")).lower()
        self.signal_time = parse_time(params.get("signal_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.min_abs_day_return_bps = float(params.get("min_abs_day_return_bps", 25.0))
        self.recent_lookback_minutes = int(params.get("recent_lookback_minutes", 30))
        self.min_recent_return_bps = float(params.get("min_recent_return_bps", 0.0))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar["session_date"]
        state = self._state(session_date)
        state["bars"].append(_bar_snapshot(bar))
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = _session_timestamp(timestamp, self.signal_time)
        if bar_close != signal_timestamp:
            return None

        prev_close = _finite_float(bar.get("prev_rth_close"))
        if prev_close is None or prev_close <= 0:
            return None

        current_close = float(bar["close"])
        day_return_bps = ((current_close / prev_close) - 1.0) * 10000.0
        recent_return_bps = self._recent_return_bps(state["bars"], signal_timestamp)
        direction = self._direction(day_return_bps, recent_return_bps)
        if direction is None:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "leveraged_inverse_etf_rebalance_pressure",
            "setup_mode": self.setup_mode,
            "feature_method": "completed_intraday_return_from_prior_rth_close",
            "availability_rule": "prev_rth_close is known before RTH; signal uses completed bar close only",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "prev_rth_close": prev_close,
            "signal_close": current_close,
            "day_return_bps": day_return_bps,
            "min_abs_day_return_bps": self.min_abs_day_return_bps,
            "recent_lookback_minutes": self.recent_lookback_minutes,
            "recent_return_bps": recent_return_bps,
            "min_recent_return_bps": self.min_recent_return_bps,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"leveraged_etf_rebalance_pressure_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "day_return_bps": day_return_bps,
                "recent_return_bps": recent_return_bps,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, day_return_bps: float, recent_return_bps: float | None) -> str | None:
        if self.setup_mode == "two_sided_rebalance_pressure":
            return self._direction_from_day_return(day_return_bps)
        if self.setup_mode == "up_day_rebalance_long":
            return "long" if self.allow_long and day_return_bps >= self.min_abs_day_return_bps else None
        if self.setup_mode == "down_day_rebalance_short":
            return "short" if self.allow_short and day_return_bps <= -self.min_abs_day_return_bps else None
        if self.setup_mode == "late_acceleration_two_sided":
            direction = self._direction_from_day_return(day_return_bps)
            if direction is None or recent_return_bps is None:
                return None
            if direction == "long" and recent_return_bps >= self.min_recent_return_bps:
                return "long"
            if direction == "short" and recent_return_bps <= -self.min_recent_return_bps:
                return "short"
            return None
        raise ValueError(
            "Unsupported setup_mode for leveraged_etf_rebalance_pressure. Expected one of "
            "two_sided_rebalance_pressure, up_day_rebalance_long, "
            "down_day_rebalance_short, late_acceleration_two_sided."
        )

    def _direction_from_day_return(self, day_return_bps: float) -> str | None:
        if self.allow_long and day_return_bps >= self.min_abs_day_return_bps:
            return "long"
        if self.allow_short and day_return_bps <= -self.min_abs_day_return_bps:
            return "short"
        return None

    def _recent_return_bps(self, bars: list[dict], signal_timestamp: pd.Timestamp) -> float | None:
        if self.recent_lookback_minutes <= 0:
            return None
        start = signal_timestamp - pd.Timedelta(minutes=self.recent_lookback_minutes)
        window = [
            item
            for item in bars
            if start <= pd.Timestamp(item["timestamp"]) < signal_timestamp
        ]
        expected = max(1, int(math.ceil(self.recent_lookback_minutes / self.bar_interval_minutes)))
        if len(window) < expected:
            return None
        first_open = float(window[0]["open"])
        last_close = float(window[-1]["close"])
        if first_open <= 0:
            return None
        return ((last_close / first_open) - 1.0) * 10000.0

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False, "bars": []})

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.min_abs_day_return_bps < 0 or self.min_recent_return_bps < 0:
            raise ValueError("return thresholds must be non-negative.")
        if self.recent_lookback_minutes < 0:
            raise ValueError("recent_lookback_minutes must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )


def _bar_snapshot(bar: pd.Series) -> dict:
    return {
        "timestamp": pd.Timestamp(bar["timestamp"]),
        "open": float(bar["open"]),
        "high": float(bar["high"]),
        "low": float(bar["low"]),
        "close": float(bar["close"]),
    }


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
