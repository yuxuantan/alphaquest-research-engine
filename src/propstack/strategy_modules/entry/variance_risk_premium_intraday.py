from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class VarianceRiskPremiumIntradayEntry:
    name = "variance_risk_premium_intraday"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_vrp_long")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_variance_risk_premium_features_20110103_20260609.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.vrp_rank_min = float(params.get("vrp_rank_min", 0.65))
        self.vrp_rank_max = float(params.get("vrp_rank_max", 0.35))
        self.vrp_ratio_rank_min = float(params.get("vrp_ratio_rank_min", 0.65))
        self.vrp_change_rank_min = float(params.get("vrp_change_rank_min", 0.65))
        self.realized_var_rank_max = float(params.get("realized_var_rank_max", 0.5))
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
            "academic_source_key": "bollerslev_tauchen_zhou_2009_variance_risk_premium",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "vrp_driver_column": driver_column,
            "vrp_driver_value": driver_value,
            "vrp_rank_min": self.vrp_rank_min,
            "vrp_rank_max": self.vrp_rank_max,
            "vrp_ratio_rank_min": self.vrp_ratio_rank_min,
            "vrp_change_rank_min": self.vrp_change_rank_min,
            "realized_var_rank_max": self.realized_var_rank_max,
            "prior_vix_close": row.get("prior_vix_close"),
            "prior_vix_variance_ann": row.get("prior_vix_variance_ann"),
            "realized_var_20_ann": row.get("realized_var_20_ann"),
            "vrp_20": row.get("vrp_20"),
            "vrp_ratio_20": row.get("vrp_ratio_20"),
            "vrp_change_5": row.get("vrp_change_5"),
            "vrp_rank_252": row.get("vrp_rank_252"),
            "vrp_ratio_rank_252": row.get("vrp_ratio_rank_252"),
            "realized_var20_rank_252": row.get("realized_var20_rank_252"),
            "vrp_change_rank_252": row.get("vrp_change_rank_252"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"variance_risk_premium_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "vrp_driver_column": driver_column,
                "vrp_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float]) -> tuple[str | None, str, float]:
        if self.setup_mode == "high_vrp_long":
            value = _finite_float(row.get("vrp_rank_252"))
            if value is None:
                return None, "vrp_rank_252", float("nan")
            return ("long" if value >= self.vrp_rank_min else None), "vrp_rank_252", value
        if self.setup_mode == "low_vrp_short":
            value = _finite_float(row.get("vrp_rank_252"))
            if value is None:
                return None, "vrp_rank_252", float("nan")
            return ("short" if value <= self.vrp_rank_max else None), "vrp_rank_252", value
        if self.setup_mode == "high_vrp_low_realized_long":
            vrp_rank = _finite_float(row.get("vrp_rank_252"))
            realized_rank = _finite_float(row.get("realized_var20_rank_252"))
            if vrp_rank is None or realized_rank is None:
                return None, "vrp_rank_252", float("nan")
            passed = vrp_rank >= self.vrp_rank_min and realized_rank <= self.realized_var_rank_max
            return ("long" if passed else None), "vrp_rank_252", vrp_rank
        if self.setup_mode == "high_vrp_ratio_long":
            value = _finite_float(row.get("vrp_ratio_rank_252"))
            if value is None:
                return None, "vrp_ratio_rank_252", float("nan")
            return ("long" if value >= self.vrp_ratio_rank_min else None), "vrp_ratio_rank_252", value
        if self.setup_mode == "vrp_rising_long":
            value = _finite_float(row.get("vrp_change_rank_252"))
            if value is None:
                return None, "vrp_change_rank_252", float("nan")
            return ("long" if value >= self.vrp_change_rank_min else None), "vrp_change_rank_252", value
        raise ValueError(f"Unsupported setup_mode for variance_risk_premium_intraday: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        for name, value in {
            "vrp_rank_min": self.vrp_rank_min,
            "vrp_rank_max": self.vrp_rank_max,
            "vrp_ratio_rank_min": self.vrp_ratio_rank_min,
            "vrp_change_rank_min": self.vrp_change_rank_min,
            "realized_var_rank_max": self.realized_var_rank_max,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Variance-risk-premium feature CSV not found: {path}")
    out: dict[date, dict[str, float]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: _nan_float(value)
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
