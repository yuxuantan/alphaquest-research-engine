from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class NqTaiwanSemiconductorSpilloverEntry:
    name = "nq_taiwan_semiconductor_spillover"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "twii_1d_strength_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_taiwan_semiconductor_spillover_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.rank_min = float(params.get("rank_min", 0.60))
        self.rank_max = float(params.get("rank_max", 0.40))
        self.max_observation_lag_calendar_days = int(
            params.get("max_observation_lag_calendar_days", 3)
        )
        self.stop_pct = float(params.get("stop_pct", 0.005))
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
        lag_days = _finite_float(row.get("taiwan_observation_lag_calendar_days"))
        if lag_days is None or lag_days > self.max_observation_lag_calendar_days:
            return None
        direction, driver_column, driver_value = self._signal_direction(row)
        if direction is None:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "taiwan_us_market_spillover_usitc_taiwan_semiconductor_exposure",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "taiwan_observation_date": row.get("observation_date"),
            "taiwan_observation_lag_calendar_days": row.get("taiwan_observation_lag_calendar_days"),
            "availability_rule": "latest TAIEX and 2330.TW close on or before the NQ session date; Taiwan cash trading closes before the NQ RTH decision time",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "taiwan_driver_column": driver_column,
            "taiwan_driver_value": driver_value,
            "rank_min": self.rank_min,
            "rank_max": self.rank_max,
            "max_observation_lag_calendar_days": self.max_observation_lag_calendar_days,
            "twii": row.get("twii"),
            "tsmc_tw": row.get("tsmc_tw"),
            "twii_return_1d": row.get("twii_return_1d"),
            "twii_return_3d": row.get("twii_return_3d"),
            "twii_return_5d": row.get("twii_return_5d"),
            "twii_abs_return_1d": row.get("twii_abs_return_1d"),
            "tsmc_tw_twii_relative_return_1d": row.get(
                "tsmc_tw_twii_relative_return_1d"
            ),
            "tsmc_tw_twii_relative_return_3d": row.get(
                "tsmc_tw_twii_relative_return_3d"
            ),
            "twii_return_1d_rank_252": row.get("twii_return_1d_rank_252"),
            "twii_abs_return_1d_rank_252": row.get("twii_abs_return_1d_rank_252"),
            "tsmc_tw_twii_relative_return_1d_rank_252": row.get(
                "tsmc_tw_twii_relative_return_1d_rank_252"
            ),
            "tsmc_tw_twii_relative_return_3d_rank_252": row.get(
                "tsmc_tw_twii_relative_return_3d_rank_252"
            ),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"nq_taiwan_semiconductor_spillover_{self.setup_mode}",
            swept_level=float(bar["close"]),
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "taiwan_driver_column": driver_column,
                "taiwan_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "twii_1d_strength_long":
            column = "twii_return_1d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        if self.setup_mode == "twii_1d_weakness_short":
            column = "twii_return_1d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.rank_max, "short")
        if self.setup_mode == "tsmc_1d_relative_strength_long":
            column = "tsmc_tw_twii_relative_return_1d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        if self.setup_mode == "tsmc_3d_relative_weakness_short":
            column = "tsmc_tw_twii_relative_return_3d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.rank_max, "short")
        if self.setup_mode == "taiwan_1d_volatility_short":
            column = "twii_abs_return_1d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "short")
        raise ValueError(
            f"Unsupported setup_mode for nq_taiwan_semiconductor_spillover: {self.setup_mode}"
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
        if self.max_observation_lag_calendar_days < 0:
            raise ValueError("max_observation_lag_calendar_days must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        for name, value in {"rank_min": self.rank_min, "rank_max": self.rank_max}.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"NQ Taiwan semiconductor spillover feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"observation_date"}
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
