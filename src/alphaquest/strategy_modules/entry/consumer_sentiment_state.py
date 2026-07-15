from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class ConsumerSentimentStateEntry:
    name = "consumer_sentiment_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "low_sentiment_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_consumer_sentiment_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.sentiment_rank_min = float(params.get("sentiment_rank_min", 0.6))
        self.sentiment_rank_max = float(params.get("sentiment_rank_max", 0.4))
        self.sentiment_change_rank_min = float(params.get("sentiment_change_rank_min", 0.6))
        self.sentiment_change_rank_max = float(params.get("sentiment_change_rank_max", 0.4))
        self.sentiment_ma_rank_max = float(params.get("sentiment_ma_rank_max", 0.4))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False})
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.entry_time.hour,
            minute=self.entry_time.minute,
            second=self.entry_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        row = self.features.get(session_date)
        if row is None:
            return None
        direction, driver_column, driver_value = self._signal_direction(row)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "lemmon_portniaguina_2006_consumer_confidence",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "sentiment_observation_date": row.get("observation_date"),
            "availability_rule": "latest UMCSENT observation on or before session_date_minus_45_calendar_days",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "sentiment_driver_column": driver_column,
            "sentiment_driver_value": driver_value,
            "sentiment_rank_min": self.sentiment_rank_min,
            "sentiment_rank_max": self.sentiment_rank_max,
            "sentiment_change_rank_min": self.sentiment_change_rank_min,
            "sentiment_change_rank_max": self.sentiment_change_rank_max,
            "sentiment_ma_rank_max": self.sentiment_ma_rank_max,
            "consumer_sentiment": row.get("consumer_sentiment"),
            "sentiment_change_1m": row.get("sentiment_change_1m"),
            "sentiment_change_3m": row.get("sentiment_change_3m"),
            "sentiment_change_6m": row.get("sentiment_change_6m"),
            "sentiment_ma_3": row.get("sentiment_ma_3"),
            "sentiment_ma_12": row.get("sentiment_ma_12"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"consumer_sentiment_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "sentiment_driver_column": driver_column,
                "sentiment_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "low_sentiment_long":
            column = "consumer_sentiment_rank_120m"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.sentiment_rank_max, "long")
        if self.setup_mode == "high_sentiment_short":
            column = "consumer_sentiment_rank_120m"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.sentiment_rank_min, "short")
        if self.setup_mode == "rising_sentiment_long":
            column = "sentiment_change_3m_rank_120m"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.sentiment_change_rank_min, "long")
        if self.setup_mode == "falling_sentiment_short":
            column = "sentiment_change_3m_rank_120m"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.sentiment_change_rank_max, "short")
        if self.setup_mode == "low_sentiment_ma_long":
            column = "sentiment_ma_12_rank_120m"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.sentiment_ma_rank_max, "long")
        raise ValueError(f"Unsupported setup_mode for consumer_sentiment_state: {self.setup_mode}")

    @staticmethod
    def _if_rank(column: str, rank: float | None, op: str, threshold: float, direction: str):
        if rank is None:
            return None, column, float("nan")
        if op == ">=":
            return (direction if rank >= threshold else None), column, rank
        return (direction if rank <= threshold else None), column, rank

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        for name, value in {
            "sentiment_rank_min": self.sentiment_rank_min,
            "sentiment_rank_max": self.sentiment_rank_max,
            "sentiment_change_rank_min": self.sentiment_change_rank_min,
            "sentiment_change_rank_max": self.sentiment_change_rank_max,
            "sentiment_ma_rank_max": self.sentiment_ma_rank_max,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Consumer-sentiment feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key == "observation_date" else _nan_float(value))
                for key, value in row.items()
                if key != "session_date"
            }
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _nan_float(value) -> float:
    if value in {None, ""}:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
