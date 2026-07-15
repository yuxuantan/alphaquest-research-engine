from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TradeOrderflowPressureEntry:
    name = "trade_orderflow_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "pressure_continuation"))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "10:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.flow_column = str(params.get("flow_column", "trade_orderflow_imbalance_15"))
        self.flow_threshold = float(params.get("flow_threshold", 0.05))
        self.return_column = params.get("return_column")
        self.return_confirmation = str(params.get("return_confirmation", "none")).lower()
        self.min_return_ticks = float(params.get("min_return_ticks", 0.0))
        self.positive_flow_direction = str(params.get("positive_flow_direction", "long")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.stop_pct = float(params.get("stop_pct", 0.02))
        self.target_r_multiple = float(params.get("target_r_multiple", 10.0))

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.flow_threshold <= 0:
            raise ValueError("flow_threshold must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.return_confirmation not in {"none", "same_sign", "opposite_sign"}:
            raise ValueError("return_confirmation must be one of: none, same_sign, opposite_sign.")
        if self.positive_flow_direction not in {"long", "short"}:
            raise ValueError("positive_flow_direction must be long or short.")

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = _session_timestamp(timestamp, self.entry_time)
        if bar_close != signal_timestamp:
            return None

        flow = _finite_float(bar.get(self.flow_column))
        if flow is None:
            return None
        if flow >= self.flow_threshold:
            direction = self.positive_flow_direction
            flow_sign = 1
        elif flow <= -self.flow_threshold:
            direction = "short" if self.positive_flow_direction == "long" else "long"
            flow_sign = -1
        else:
            return None

        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None
        if not self._return_filter_passes(bar, flow_sign):
            return None

        current_close = float(bar["close"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "databento_trade_aggressor_side",
            "flow_column": self.flow_column,
            "flow_value": flow,
            "flow_threshold": self.flow_threshold,
            "return_column": self.return_column,
            "return_confirmation": self.return_confirmation,
            "min_return_ticks": self.min_return_ticks,
            "orderflow_signal_timestamp": signal_timestamp,
            "orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        if self.return_column:
            report_fields["return_value"] = _finite_float(bar.get(str(self.return_column)))

        return Signal(
            direction=direction,
            level_type=f"trade_orderflow_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "flow_column": self.flow_column,
                "flow_value": flow,
                "flow_threshold": self.flow_threshold,
                "return_column": self.return_column,
                "return_confirmation": self.return_confirmation,
                "min_return_ticks": self.min_return_ticks,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _return_filter_passes(self, bar: pd.Series, flow_sign: int) -> bool:
        if self.return_confirmation == "none":
            return True
        if not self.return_column:
            return False
        value = _finite_float(bar.get(str(self.return_column)))
        if value is None:
            return False
        required_sign = flow_sign if self.return_confirmation == "same_sign" else -flow_sign
        if required_sign > 0:
            return value >= self.min_return_ticks
        return value <= -self.min_return_ticks


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
