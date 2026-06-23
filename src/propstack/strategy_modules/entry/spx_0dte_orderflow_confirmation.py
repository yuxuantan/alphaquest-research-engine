from __future__ import annotations

from datetime import date
import math

import pandas as pd

from propstack.strategy_modules.entry.spx_0dte_expiration_pressure import (
    Spx0dteExpirationPressureEntry,
)


class Spx0dteOrderflowConfirmationEntry(Spx0dteExpirationPressureEntry):
    name = "spx_0dte_orderflow_confirmation"

    def __init__(self, params: dict):
        super().__init__(params)
        self.orderflow_window_minutes = int(params.get("orderflow_window_minutes", 60))
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.flow_state_by_day: dict[date, dict] = {}
        self._validate_orderflow()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0):
        if bool(bar.get("is_rth", False)):
            timestamp = pd.Timestamp(bar["timestamp"])
            bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
            self._append_flow_bar(self._flow_state(bar, timestamp), bar, bar_close)

        session_date = _date(bar.get("session_date", pd.Timestamp(bar["timestamp"]).date()))
        parent_state = self.state_by_day.get(session_date)
        signal = super().on_bar_close(bar, trades_today=trades_today)
        if signal is None:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        observed = self._observed_values(self._flow_state(bar, timestamp), bar_close, signal.direction)
        if not self._matches(observed):
            if parent_state is not None:
                parent_state["signaled"] = False
            return None

        report_fields = {
            "spx_0dte_orderflow_flow_mode": self.flow_mode,
            "spx_0dte_orderflow_window_minutes": self.orderflow_window_minutes,
            "spx_0dte_min_orderflow_imbalance": self.min_orderflow_imbalance,
            **observed,
        }
        signal.level_type = f"{signal.level_type}_orderflow_confirmed"
        signal.metadata = {
            **signal.metadata,
            "spx_0dte_orderflow_flow_mode": self.flow_mode,
            "spx_0dte_orderflow_imbalance": observed["primary_orderflow_imbalance"],
        }
        signal.report_fields = {**signal.report_fields, **report_fields}
        return signal

    def _flow_state(self, bar: pd.Series, timestamp: pd.Timestamp) -> dict:
        session_date = _date(bar.get("session_date", timestamp.date()))
        state = self.flow_state_by_day.get(session_date)
        if state is None:
            state = {"bars": []}
            self.flow_state_by_day[session_date] = state
        return state

    def _append_flow_bar(self, state: dict, bar: pd.Series, bar_close: pd.Timestamp) -> None:
        state["bars"].append(
            {
                "bar_close": bar_close,
                "volume": max(_finite_float(bar.get("volume")) or 0.0, 0.0),
                "signed_volume": _finite_float(bar.get("signed_volume")) or 0.0,
                "large20_volume": max(_finite_float(bar.get("large20_volume")) or 0.0, 0.0),
                "large20_signed_volume": _finite_float(bar.get("large20_signed_volume")) or 0.0,
            }
        )
        cutoff = bar_close - pd.Timedelta(minutes=self.orderflow_window_minutes + 2)
        state["bars"] = [row for row in state["bars"] if row["bar_close"] >= cutoff]

    def _observed_values(self, state: dict, bar_close: pd.Timestamp, direction: str) -> dict:
        window_start = bar_close - pd.Timedelta(minutes=self.orderflow_window_minutes)
        rows = [
            row
            for row in state["bars"]
            if window_start < row["bar_close"] <= bar_close
        ]
        volume = sum(row["volume"] for row in rows)
        signed_volume = sum(row["signed_volume"] for row in rows)
        large20_volume = sum(row["large20_volume"] for row in rows)
        large20_signed_volume = sum(row["large20_signed_volume"] for row in rows)
        primary = (
            _ratio(large20_signed_volume, large20_volume)
            if self.flow_mode in {"large20", "large20_imbalance"}
            else _ratio(signed_volume, volume)
        )
        signed_mult = 1.0 if direction == "long" else -1.0
        return {
            "spx_0dte_orderflow_window_start": window_start,
            "spx_0dte_orderflow_window_end": bar_close,
            "spx_0dte_orderflow_window_bar_count": len(rows),
            "spx_0dte_orderflow_window_volume": volume,
            "primary_orderflow_imbalance": primary,
            "signed_directional_orderflow_imbalance": signed_mult * primary if primary is not None else math.nan,
        }

    def _matches(self, observed: dict) -> bool:
        signed = observed["signed_directional_orderflow_imbalance"]
        return _finite(signed) and signed >= self.min_orderflow_imbalance

    def _validate_orderflow(self) -> None:
        if self.orderflow_window_minutes <= 0:
            raise ValueError("entry.params.orderflow_window_minutes must be greater than 0.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in {"signed_imbalance", "large20", "large20_imbalance"}:
            raise ValueError("entry.params.flow_mode must be signed_imbalance or large20_imbalance.")


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    out = numerator / denominator
    return out if math.isfinite(out) else None
