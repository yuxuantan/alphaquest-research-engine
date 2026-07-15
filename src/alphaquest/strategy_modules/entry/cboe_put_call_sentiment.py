from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class CboePutCallSentimentEntry:
    name = "cboe_put_call_sentiment"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "low_equity_pc_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_cboe_put_call_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.pc_rank_min = float(params.get("pc_rank_min", 0.6))
        self.pc_rank_max = float(params.get("pc_rank_max", 0.4))
        self.pc_change_rank_min = float(params.get("pc_change_rank_min", 0.6))
        self.pc_change_rank_max = float(params.get("pc_change_rank_max", 0.4))
        self.pc_spread_rank_min = float(params.get("pc_spread_rank_min", 0.6))
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
            "academic_source_key": "pan_poteshman_2006_option_volume",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "cboe_observation_date": row.get("observation_date"),
            "availability_rule": "latest Cboe put/call ratio observation strictly before ES session_date",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "put_call_driver_column": driver_column,
            "put_call_driver_value": driver_value,
            "pc_rank_min": self.pc_rank_min,
            "pc_rank_max": self.pc_rank_max,
            "pc_change_rank_min": self.pc_change_rank_min,
            "pc_change_rank_max": self.pc_change_rank_max,
            "pc_spread_rank_min": self.pc_spread_rank_min,
            "equity_pc_ratio": row.get("equity_pc_ratio"),
            "index_pc_ratio": row.get("index_pc_ratio"),
            "total_pc_ratio": row.get("total_pc_ratio"),
            "equity_pc_change_1d": row.get("equity_pc_change_1d"),
            "index_pc_change_1d": row.get("index_pc_change_1d"),
            "index_minus_equity_pc": row.get("index_minus_equity_pc"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"cboe_put_call_sentiment_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "put_call_driver_column": driver_column,
                "put_call_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "low_equity_pc_long":
            column = "equity_pc_ratio_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.pc_rank_max, "long")
        if self.setup_mode == "high_equity_pc_short":
            column = "equity_pc_ratio_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.pc_rank_min, "short")
        if self.setup_mode == "falling_equity_pc_long":
            column = "equity_pc_change_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.pc_change_rank_max, "long")
        if self.setup_mode == "falling_total_pc_long":
            column = "total_pc_change_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.pc_change_rank_max, "long")
        if self.setup_mode == "rising_index_pc_short":
            column = "index_pc_change_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.pc_change_rank_min, "short")
        if self.setup_mode == "rising_total_pc_short":
            column = "total_pc_change_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.pc_change_rank_min, "short")
        if self.setup_mode == "high_index_vs_equity_pc_short":
            column = "index_minus_equity_pc_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.pc_spread_rank_min, "short")
        if self.setup_mode == "high_total_vs_equity_pc_short":
            column = "total_minus_equity_pc_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.pc_spread_rank_min, "short")
        raise ValueError(f"Unsupported setup_mode for cboe_put_call_sentiment: {self.setup_mode}")

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
            "pc_rank_min": self.pc_rank_min,
            "pc_rank_max": self.pc_rank_max,
            "pc_change_rank_min": self.pc_change_rank_min,
            "pc_change_rank_max": self.pc_change_rank_max,
            "pc_spread_rank_min": self.pc_spread_rank_min,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Cboe put/call feature CSV not found: {path}")
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
