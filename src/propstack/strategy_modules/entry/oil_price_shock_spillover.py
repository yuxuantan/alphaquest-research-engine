from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OilPriceShockSpilloverEntry:
    name = "oil_price_shock_spillover"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "wti_down_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_oil_price_shock_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.oil_return_rank_min = float(params.get("oil_return_rank_min", 0.6))
        self.oil_return_rank_max = float(params.get("oil_return_rank_max", 0.4))
        self.oil_abs_rank_min = float(params.get("oil_abs_rank_min", 0.6))
        self.spread_change_rank_min = float(params.get("spread_change_rank_min", 0.6))
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
            "academic_source_key": "jones_kaul_1996_kilian_park_2009_oil_stock_spillover",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "oil_observation_date": row.get("observation_date"),
            "availability_cutoff": row.get("availability_cutoff"),
            "availability_lag_business_days": row.get("availability_lag_business_days"),
            "availability_rule": "latest EIA WTI/Brent observation on or before session_date minus configured business-day lag",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "oil_driver_column": driver_column,
            "oil_driver_value": driver_value,
            "oil_return_rank_min": self.oil_return_rank_min,
            "oil_return_rank_max": self.oil_return_rank_max,
            "oil_abs_rank_min": self.oil_abs_rank_min,
            "spread_change_rank_min": self.spread_change_rank_min,
            "wti_spot": row.get("wti_spot"),
            "brent_spot": row.get("brent_spot"),
            "wti_return_1d": row.get("wti_return_1d"),
            "brent_return_1d": row.get("brent_return_1d"),
            "oil_composite_return_1d": row.get("oil_composite_return_1d"),
            "oil_abs_return_1d": row.get("oil_abs_return_1d"),
            "brent_wti_spread": row.get("brent_wti_spread"),
            "brent_wti_spread_change_1d": row.get("brent_wti_spread_change_1d"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"oil_price_shock_spillover_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "oil_driver_column": driver_column,
                "oil_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "wti_down_long":
            column = "wti_return_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, "<=", self.oil_return_rank_max, "long")
        if self.setup_mode == "wti_up_short":
            column = "wti_return_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.oil_return_rank_min, "short")
        if self.setup_mode == "brent_up_short":
            column = "brent_return_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.oil_return_rank_min, "short")
        if self.setup_mode == "oil_vol_shock_short":
            column = "oil_abs_return_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.oil_abs_rank_min, "short")
        if self.setup_mode == "brent_wti_spread_widen_short":
            column = "brent_wti_spread_change_1d_rank_252"
            rank = _finite_float(row.get(column))
            return self._if_rank(column, rank, ">=", self.spread_change_rank_min, "short")
        raise ValueError(f"Unsupported setup_mode for oil_price_shock_spillover: {self.setup_mode}")

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
            "oil_return_rank_min": self.oil_return_rank_min,
            "oil_return_rank_max": self.oil_return_rank_max,
            "oil_abs_rank_min": self.oil_abs_rank_min,
            "spread_change_rank_min": self.spread_change_rank_min,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Oil price-shock feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"observation_date", "availability_cutoff"}
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
