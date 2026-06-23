from __future__ import annotations

from dataclasses import replace
from datetime import date
import math

import pandas as pd

from propstack.strategy_modules.entry.cboe_put_call_sentiment import CboePutCallSentimentEntry


class CboePutCallOrderflowConfirmationEntry:
    name = "cboe_put_call_orderflow_confirmation"

    def __init__(self, params: dict):
        self.params = params
        base_params = dict(params)
        for key in {
            "orderflow_window_minutes",
            "flow_mode",
            "min_orderflow_imbalance",
        }:
            base_params.pop(key, None)
        self.base_entry = CboePutCallSentimentEntry(base_params)
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.orderflow_window_minutes = int(params.get("orderflow_window_minutes", 30))
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.flow_state_by_day: dict[date, dict] = {}
        self._validate_orderflow()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0):
        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._flow_state(bar, timestamp)
        if bool(bar.get("is_rth", False)):
            bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
            self._append_flow_bar(state, bar, bar_close)

        signal = self.base_entry.on_bar_close(bar, trades_today=trades_today)
        if signal is None:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        observed = self._observed_values(state, bar_close, signal.direction)
        if not self._matches(observed):
            return None

        report_fields = {
            "put_call_orderflow_confirmation_result": "passed",
            "put_call_orderflow_flow_mode": self.flow_mode,
            "put_call_orderflow_window_minutes": self.orderflow_window_minutes,
            "put_call_orderflow_min_imbalance": self.min_orderflow_imbalance,
            **observed,
        }
        metadata = {
            **signal.metadata,
            "put_call_orderflow_flow_mode": self.flow_mode,
            "put_call_orderflow_window_minutes": self.orderflow_window_minutes,
            "put_call_orderflow_signed_directional_imbalance": observed[
                "put_call_orderflow_signed_directional_imbalance"
            ],
        }
        return replace(
            signal,
            level_type=f"{signal.level_type}_with_orderflow_confirmation",
            metadata=metadata,
            report_fields={**signal.report_fields, **report_fields},
        )

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
                "large10_volume": max(_finite_float(bar.get("large10_volume")) or 0.0, 0.0),
                "large10_signed_volume": _finite_float(bar.get("large10_signed_volume")) or 0.0,
                "large20_volume": max(_finite_float(bar.get("large20_volume")) or 0.0, 0.0),
                "large20_signed_volume": _finite_float(bar.get("large20_signed_volume")) or 0.0,
            }
        )
        cutoff = bar_close - pd.Timedelta(minutes=self.orderflow_window_minutes + self.bar_interval_minutes + 1)
        state["bars"] = [row for row in state["bars"] if row["bar_close"] >= cutoff]

    def _observed_values(self, state: dict, bar_close: pd.Timestamp, direction: str) -> dict:
        window_start = bar_close - pd.Timedelta(minutes=self.orderflow_window_minutes)
        rows = [row for row in state["bars"] if window_start < row["bar_close"] <= bar_close]
        volume = sum(row["volume"] for row in rows)
        signed_volume = sum(row["signed_volume"] for row in rows)
        large10_volume = sum(row["large10_volume"] for row in rows)
        large10_signed_volume = sum(row["large10_signed_volume"] for row in rows)
        large20_volume = sum(row["large20_volume"] for row in rows)
        large20_signed_volume = sum(row["large20_signed_volume"] for row in rows)
        primary, secondary = self._flow_values(
            volume=volume,
            signed_volume=signed_volume,
            large10_volume=large10_volume,
            large10_signed_volume=large10_signed_volume,
            large20_volume=large20_volume,
            large20_signed_volume=large20_signed_volume,
        )
        direction_mult = 1.0 if direction == "long" else -1.0
        signed_primary = direction_mult * primary if primary is not None else math.nan
        signed_secondary = direction_mult * secondary if secondary is not None else math.nan
        return {
            "put_call_orderflow_window_start": window_start,
            "put_call_orderflow_window_end": bar_close,
            "put_call_orderflow_window_bar_count": len(rows),
            "put_call_orderflow_window_volume": volume,
            "put_call_orderflow_volume_imbalance": _ratio(signed_volume, volume),
            "put_call_orderflow_large10_imbalance": _ratio(large10_signed_volume, large10_volume),
            "put_call_orderflow_large20_imbalance": _ratio(large20_signed_volume, large20_volume),
            "put_call_orderflow_primary_imbalance": primary,
            "put_call_orderflow_secondary_imbalance": secondary,
            "put_call_orderflow_signed_directional_imbalance": signed_primary,
            "put_call_orderflow_signed_secondary_directional_imbalance": signed_secondary,
        }

    def _flow_values(
        self,
        *,
        volume: float,
        signed_volume: float,
        large10_volume: float,
        large10_signed_volume: float,
        large20_volume: float,
        large20_signed_volume: float,
    ) -> tuple[float | None, float | None]:
        signed = _ratio(signed_volume, volume)
        large10 = _ratio(large10_signed_volume, large10_volume)
        large20 = _ratio(large20_signed_volume, large20_volume)
        if self.flow_mode in {"signed_imbalance", "all_volume_imbalance"}:
            return signed, None
        if self.flow_mode in {"large10_imbalance", "large10"}:
            return large10, None
        if self.flow_mode in {"large20_imbalance", "large20"}:
            return large20, None
        if self.flow_mode in {"signed_and_large20", "broad_large_alignment"}:
            return signed, large20
        raise ValueError(
            "flow_mode must be signed_imbalance, large10_imbalance, "
            "large20_imbalance, or signed_and_large20."
        )

    def _matches(self, observed: dict) -> bool:
        primary = observed["put_call_orderflow_signed_directional_imbalance"]
        secondary_raw = observed["put_call_orderflow_secondary_imbalance"]
        secondary = observed["put_call_orderflow_signed_secondary_directional_imbalance"]
        if not _finite(primary) or primary < self.min_orderflow_imbalance:
            return False
        return secondary_raw is None or (_finite(secondary) and secondary >= self.min_orderflow_imbalance)

    def _validate_orderflow(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.orderflow_window_minutes <= 0:
            raise ValueError("entry.params.orderflow_window_minutes must be greater than 0.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in {
            "signed_imbalance",
            "all_volume_imbalance",
            "large10_imbalance",
            "large10",
            "large20_imbalance",
            "large20",
            "signed_and_large20",
            "broad_large_alignment",
        }:
            raise ValueError(
                "entry.params.flow_mode must be signed_imbalance, large10_imbalance, "
                "large20_imbalance, or signed_and_large20."
            )


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
