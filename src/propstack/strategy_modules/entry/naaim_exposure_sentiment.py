from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class NaaimExposureSentimentEntry:
    name = "naaim_exposure_sentiment"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "level_median_contrarian")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_naaim_exposure_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.rank_threshold = float(params.get("rank_threshold", 0.5))
        self.delta_threshold = float(params.get("delta_threshold", 0.0))
        self.zscore_threshold = float(params.get("zscore_threshold", 0.0))
        self.ma_distance_threshold = float(params.get("ma_distance_threshold", 0.0))
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
            "academic_source_key": "baker_wurgler_2006_brown_cliff_2005_sentiment",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "naaim_observation_date": row.get("observation_date"),
            "naaim_availability_date": row.get("availability_date"),
            "availability_rule": "first ES RTH session at least two business days after NAAIM observation date",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "naaim_driver_column": driver_column,
            "naaim_driver_value": driver_value,
            "naaim_number": row.get("naaim_number"),
            "naaim_change_1w": row.get("naaim_change_1w"),
            "naaim_rank_104": row.get("naaim_rank_104"),
            "naaim_z_104": row.get("naaim_z_104"),
            "naaim_vs_ma_26": row.get("naaim_vs_ma_26"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"naaim_exposure_sentiment_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "naaim_driver_column": driver_column,
                "naaim_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "level_median_contrarian":
            value = _finite_float(row.get("naaim_number"))
            median = _finite_float(row.get("naaim_median_104"))
            if value is None or median is None:
                return None, "naaim_number_minus_median_104", float("nan")
            driver = value - median
            return ("short" if driver >= 0 else "long"), "naaim_number_minus_median_104", driver
        if self.setup_mode == "level_rank_contrarian":
            column = "naaim_rank_104"
            value = _finite_float(row.get(column))
            if value is None:
                return None, column, float("nan")
            return ("short" if value >= self.rank_threshold else "long"), column, value
        if self.setup_mode == "change_sign_contrarian":
            column = "naaim_change_1w"
            value = _finite_float(row.get(column))
            if value is None or abs(value) <= self.delta_threshold:
                return None, column, float("nan") if value is None else value
            return ("short" if value > 0 else "long"), column, value
        if self.setup_mode == "zscore_sign_contrarian":
            column = "naaim_z_104"
            value = _finite_float(row.get(column))
            if value is None or abs(value) <= self.zscore_threshold:
                return None, column, float("nan") if value is None else value
            return ("short" if value > 0 else "long"), column, value
        if self.setup_mode == "ma_distance_contrarian":
            column = "naaim_vs_ma_26"
            value = _finite_float(row.get(column))
            if value is None or abs(value) <= self.ma_distance_threshold:
                return None, column, float("nan") if value is None else value
            return ("short" if value > 0 else "long"), column, value
        raise ValueError(f"Unsupported setup_mode for naaim_exposure_sentiment: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.rank_threshold < 1:
            raise ValueError("rank_threshold must be in (0, 1).")
        if self.delta_threshold < 0 or self.zscore_threshold < 0 or self.ma_distance_threshold < 0:
            raise ValueError("contrarian dead-band thresholds must be non-negative.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"NAAIM exposure feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key in {"observation_date", "availability_date"} else _nan_float(value))
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
