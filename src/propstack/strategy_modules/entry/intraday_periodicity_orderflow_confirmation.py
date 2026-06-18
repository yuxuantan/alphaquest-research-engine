from __future__ import annotations

from datetime import date
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.intraday_periodicity_persistence import _date, _finite_float, _load_features
from propstack.strategy_modules.entry.opening_gap_orderflow_fade import _orderflow_metrics
from propstack.utils.time import parse_time


class IntradayPeriodicityOrderflowConfirmationEntry:
    name = "intraday_periodicity_orderflow_confirmation"

    def __init__(self, params: dict):
        self.params = params
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_intraday_periodicity_features_20110103_20260609.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.setup_mode = str(params.get("setup_mode", "slot_return_orderflow_confirmation")).lower()
        self.slot_id = str(params.get("slot_id", "slot_1000_1030"))
        self.source_start = parse_time(params.get("source_start", "09:30:00"))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.slot_end_time = parse_time(params.get("slot_end_time", "10:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", params.get("slot_end_time", "10:30:00")))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_days = int(params.get("lookback_days", 20))
        self.min_mean_return_bps = float(params.get("min_mean_return_bps", 1.0))
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.direction_mode = str(params.get("direction_mode", "two_sided")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"source_window": None, "signaled": False})
        if state["signaled"]:
            return None

        source_start = _session_timestamp(timestamp, self.source_start)
        signal_timestamp = _session_timestamp(timestamp, self.entry_time)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if timestamp >= source_start and bar_close <= signal_timestamp:
            state["source_window"] = _aggregate_bar(
                state["source_window"],
                bar,
                source_start,
                signal_timestamp,
            )

        if bar_close != signal_timestamp:
            return None

        signal = self._signal(bar, state, session_date, signal_timestamp)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _signal(
        self,
        bar: pd.Series,
        state: dict,
        session_date: date,
        signal_timestamp: pd.Timestamp,
    ) -> Signal | None:
        source = state.get("source_window")
        if source is None or not _window_complete(source, self.bar_interval_minutes):
            return None

        row = self.features.get((session_date, self.slot_id))
        if row is None:
            return None

        mean_column = f"prior_slot_return_mean_bps_{self.lookback_days}"
        obs_column = f"prior_slot_return_obs_{self.lookback_days}"
        pos_rate_column = f"prior_slot_return_pos_rate_{self.lookback_days}"
        mean_return = _finite_float(row.get(mean_column))
        observations = _finite_float(row.get(obs_column))
        if mean_return is None or observations is None or observations < self.lookback_days:
            return None

        direction = self._direction_from_mean(mean_return)
        if direction is None:
            return None

        metrics = _orderflow_metrics(source)
        primary = self._flow_value(metrics)
        if primary is None:
            return None
        if direction == "long" and primary < self.min_orderflow_imbalance:
            return None
        if direction == "short" and primary > -self.min_orderflow_imbalance:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "heston_korajczyk_sadka_2010_intraday_periodicity_orderflow_confirmation",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_availability_rule": "prior sessions only; current slot return excluded by shift(1)",
            "slot_id": self.slot_id,
            "entry_time": self.entry_time.strftime("%H:%M:%S"),
            "slot_end_time": self.slot_end_time.strftime("%H:%M:%S"),
            "source_window_start_timestamp": source["start_timestamp"],
            "source_window_end_timestamp": source["end_timestamp"],
            "source_window_open": float(source["open"]),
            "source_window_close": float(source["close"]),
            "source_window_volume": float(source["volume"]),
            "source_window_signed_volume": float(source["signed_volume"]),
            "source_window_large10_signed_volume": float(source["large10_signed_volume"]),
            "source_window_large20_signed_volume": float(source["large20_signed_volume"]),
            "source_window_imbalance": metrics["signed_imbalance"],
            "source_window_large10_imbalance": metrics["large10_imbalance"],
            "source_window_large20_imbalance": metrics["large20_imbalance"],
            "primary_orderflow_imbalance": primary,
            "flow_mode": self.flow_mode,
            "mean_return_column": mean_column,
            "prior_slot_return_mean_bps": mean_return,
            "prior_slot_return_obs": observations,
            "prior_slot_return_pos_rate": _finite_float(row.get(pos_rate_column)),
            "lookback_days": self.lookback_days,
            "min_mean_return_bps": self.min_mean_return_bps,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "direction_mode": self.direction_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": signal_timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"intraday_periodicity_orderflow_{self.slot_id}",
            swept_level=current_close,
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "slot_id": self.slot_id,
                "lookback_days": self.lookback_days,
                "min_mean_return_bps": self.min_mean_return_bps,
                "flow_mode": self.flow_mode,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "direction": direction,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _flow_value(self, metrics: dict) -> float | None:
        if self.flow_mode in {"signed_imbalance", "all_volume_imbalance"}:
            return metrics["signed_imbalance"]
        if self.flow_mode in {"large10_imbalance", "large10"}:
            return metrics["large10_imbalance"]
        if self.flow_mode in {"large20_imbalance", "large20"}:
            return metrics["large20_imbalance"]
        raise ValueError("flow_mode must be signed_imbalance, large10_imbalance, or large20_imbalance.")

    def _direction_from_mean(self, mean_return: float) -> str | None:
        if mean_return >= self.min_mean_return_bps:
            direction = "long"
        elif mean_return <= -self.min_mean_return_bps:
            direction = "short"
        else:
            return None

        if self.direction_mode == "two_sided":
            return direction
        if self.direction_mode == "long_only":
            return "long" if direction == "long" else None
        if self.direction_mode == "short_only":
            return "short" if direction == "short" else None
        raise ValueError("direction_mode must be one of two_sided, long_only, short_only.")

    def _validate(self) -> None:
        if self.setup_mode != "slot_return_orderflow_confirmation":
            raise ValueError("setup_mode must be slot_return_orderflow_confirmation.")
        if self.source_start >= self.entry_time:
            raise ValueError("source_start must be before entry_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be greater than 0.")
        if self.min_mean_return_bps < 0:
            raise ValueError("min_mean_return_bps must be non-negative.")
        if not 0 <= self.min_orderflow_imbalance <= 1:
            raise ValueError("min_orderflow_imbalance must be in [0, 1].")
        if self.direction_mode not in {"two_sided", "long_only", "short_only"}:
            raise ValueError("direction_mode must be one of two_sided, long_only, short_only.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")


def _aggregate_bar(aggregate: dict | None, bar: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
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
    for column in (
        "volume",
        "signed_volume",
        "large10_volume",
        "large10_signed_volume",
        "large20_volume",
        "large20_signed_volume",
    ):
        aggregate[column] = float(aggregate[column]) + (_finite_float(bar.get(column)) or 0.0)
    aggregate["bar_count"] += 1
    return aggregate


def _window_complete(window: dict, bar_interval_minutes: float) -> bool:
    start = pd.Timestamp(window["start_timestamp"])
    end = pd.Timestamp(window["end_timestamp"])
    minutes = (end - start).total_seconds() / 60
    expected = max(1, int(math.ceil(minutes / bar_interval_minutes)))
    return int(window.get("bar_count", 0)) >= expected


def _session_timestamp(timestamp: pd.Timestamp, value) -> pd.Timestamp:
    return timestamp.replace(hour=value.hour, minute=value.minute, second=value.second, microsecond=0)
