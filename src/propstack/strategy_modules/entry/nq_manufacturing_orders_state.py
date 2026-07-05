from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class NqManufacturingOrdersStateEntry:
    name = "nq_manufacturing_orders_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "total_orders_3m_strength_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_manufacturing_orders_state_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.rank_min = float(params.get("rank_min", 0.60))
        self.rank_max = float(params.get("rank_max", 0.40))
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

        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"nq_manufacturing_orders_state_{self.setup_mode}",
            swept_level=float(bar["close"]),
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "manufacturing_orders_driver_column": driver_column,
                "manufacturing_orders_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "academic_source_key": "stock_watson_1989_leading_indicators_census_m3_manufacturing_orders_fred",
                "setup_mode": self.setup_mode,
                "feature_csv": self.feature_csv,
                "feature_session_date": session_date.isoformat(),
                "manufacturing_orders_observation_date": row.get("observation_date"),
                "observation_cutoff": row.get("observation_cutoff"),
                "availability_lag_days": row.get("availability_lag_days"),
                "availability_rule": "latest FRED/Census M3 monthly manufacturing-orders observation on or before NQ session_date minus 45 calendar days",
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "manufacturing_orders_driver_column": driver_column,
                "manufacturing_orders_driver_value": driver_value,
                "rank_min": self.rank_min,
                "rank_max": self.rank_max,
                "total_orders_change_3m": row.get("total_orders_change_3m"),
                "durable_goods_orders_change_1m": row.get("durable_goods_orders_change_1m"),
                "core_capgoods_orders_change_3m": row.get("core_capgoods_orders_change_3m"),
                "ex_transport_orders_change_3m": row.get("ex_transport_orders_change_3m"),
                "signal_stop_pct": self.stop_pct,
                "signal_target_r_multiple": self.target_r_multiple,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "total_orders_3m_strength_long":
            column = "total_orders_change_3m_rank_120m"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        if self.setup_mode == "total_orders_3m_weakness_short":
            column = "total_orders_change_3m_rank_120m"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.rank_max, "short")
        if self.setup_mode == "core_capgoods_3m_strength_long":
            column = "core_capgoods_orders_change_3m_rank_120m"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        if self.setup_mode == "durables_1m_weakness_short":
            column = "durable_goods_orders_change_1m_rank_120m"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.rank_max, "short")
        if self.setup_mode == "ex_transport_3m_strength_long":
            column = "ex_transport_orders_change_3m_rank_120m"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        raise ValueError(
            f"Unsupported setup_mode for nq_manufacturing_orders_state: {self.setup_mode}"
        )

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
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        for name, value in {"rank_min": self.rank_min, "rank_max": self.rank_max}.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"NQ manufacturing-orders feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"observation_date", "observation_cutoff"}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key in string_columns else _nan_float(value))
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
