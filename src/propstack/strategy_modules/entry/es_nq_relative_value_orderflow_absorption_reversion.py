from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.es_nq_relative_value_reversion import (
    EsNqRelativeValueReversionEntry,
)
from propstack.utils.time import parse_time


class EsNqRelativeValueOrderflowAbsorptionReversionEntry(EsNqRelativeValueReversionEntry):
    name = "es_nq_relative_value_orderflow_absorption_reversion"

    def __init__(self, params: dict):
        super().__init__(params)
        self.orderflow_window_minutes = int(params.get("orderflow_window_minutes", self.lookback_minutes))
        self.min_absorption_imbalance = float(params.get("min_absorption_imbalance", 0.0))
        self.window_mode = "start_time" in params or "end_time" in params
        self.start_time = parse_time(params.get("start_time", params.get("entry_time", "10:00:00")))
        self.end_time = parse_time(params.get("end_time", params.get("entry_time", "10:00:00")))
        if self.orderflow_window_minutes <= 0:
            raise ValueError("entry.params.orderflow_window_minutes must be greater than 0.")
        if self.min_absorption_imbalance < 0:
            raise ValueError("entry.params.min_absorption_imbalance must be non-negative.")
        if self.end_time < self.start_time:
            raise ValueError("entry.params.end_time must be after or equal to start_time.")

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if self.window_mode:
            if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
                return None
            signal_timestamp = bar_close
        else:
            signal_timestamp = _session_timestamp(timestamp, self.entry_time)
            if bar_close != signal_timestamp:
                return None

        es_return = _finite_float(bar.get(f"es_return_bps_{self.lookback_minutes}"))
        nq_return = _finite_float(bar.get(f"nq_return_bps_{self.lookback_minutes}"))
        spread = _finite_float(bar.get(f"nq_minus_es_return_bps_{self.lookback_minutes}"))
        if es_return is None or nq_return is None or spread is None:
            return None

        direction = self._direction(es_return, spread)
        if direction is None:
            return None

        absorption = self._absorption_imbalance(bar)
        if absorption is None or not self._absorption_confirms(direction, absorption):
            return None

        current_close = float(bar["close"])
        state["signaled"] = True
        report_fields = {
            "academic_source_key": "cross_index_relative_value_orderflow_absorption_reversion",
            "setup_mode": self.setup_mode,
            "leader_symbol": "NQ",
            "traded_symbol": "ES",
            "lookback_minutes": self.lookback_minutes,
            "es_return_bps": es_return,
            "nq_return_bps": nq_return,
            "nq_minus_es_return_bps": spread,
            "min_spread_bps": self.min_spread_bps,
            "min_abs_es_return_bps": self.min_abs_es_return_bps,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
            "orderflow_absorption_filter": "es_signed_imbalance_counter_to_es_return",
            "orderflow_window_minutes": self.orderflow_window_minutes,
            "es_signed_absorption_imbalance": absorption,
            "min_absorption_imbalance": self.min_absorption_imbalance,
            "entry_window_mode": self.window_mode,
            "entry_window_start": self.start_time.strftime("%H:%M:%S"),
            "entry_window_end": self.end_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"es_nq_relative_value_absorption_reversion_{self.setup_mode}_{self.lookback_minutes}m",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "leader_symbol": "NQ",
                "lookback_minutes": self.lookback_minutes,
                "nq_minus_es_return_bps": spread,
                "orderflow_absorption_filter": "es_signed_imbalance_counter_to_es_return",
                "orderflow_window_minutes": self.orderflow_window_minutes,
                "es_signed_absorption_imbalance": absorption,
                "min_absorption_imbalance": self.min_absorption_imbalance,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _absorption_imbalance(self, bar: pd.Series) -> float | None:
        return _finite_float(bar.get(f"es_signed_imbalance_{self.orderflow_window_minutes}"))

    def _absorption_confirms(self, direction: str, absorption: float) -> bool:
        if direction == "long":
            return absorption >= self.min_absorption_imbalance
        if direction == "short":
            return absorption <= -self.min_absorption_imbalance
        return False


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
