from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class VolatilityManagedIntradayPremiumEntry:
    name = "volatility_managed_intraday_premium"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "low_vol20_long")).lower()
        self.feature_csv = str(params.get("feature_csv", "data/external/es_lagged_volatility_features_20110103_20260609.csv"))
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.vol_rank_max = float(params.get("vol_rank_max", 0.4))
        self.vol_ratio_max = float(params.get("vol_ratio_max", 0.8))
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
        passed, driver_column, driver_value = self._passes_setup(row)
        if not passed:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "moreira_muir_2017_volatility_managed_portfolios",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "volatility_driver_column": driver_column,
            "volatility_driver_value": driver_value,
            "vol_rank_max": self.vol_rank_max,
            "vol_ratio_max": self.vol_ratio_max,
            "prior_close": row.get("prior_close"),
            "prior_rth_return": row.get("prior_rth_return"),
            "prior_range_pct": row.get("prior_range_pct"),
            "realized_vol_5": row.get("realized_vol_5"),
            "realized_vol_20": row.get("realized_vol_20"),
            "avg_range_pct_10": row.get("avg_range_pct_10"),
            "avg_abs_return_5": row.get("avg_abs_return_5"),
            "downside_vol_20": row.get("downside_vol_20"),
            "vol5_over_vol20": row.get("vol5_over_vol20"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction="long",
            level_type=f"volatility_managed_intraday_premium_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "volatility_driver_column": driver_column,
                "volatility_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _passes_setup(self, row: dict[str, float]) -> tuple[bool, str, float]:
        if self.setup_mode == "low_vol20_long":
            return self._rank_check(row, "vol20_rank_252")
        if self.setup_mode == "low_range10_long":
            return self._rank_check(row, "range10_rank_252")
        if self.setup_mode == "low_absret5_long":
            return self._rank_check(row, "absret5_rank_252")
        if self.setup_mode == "low_downside20_long":
            return self._rank_check(row, "downside20_rank_252")
        if self.setup_mode == "vol_downshift_long":
            value = _finite_float(row.get("vol5_over_vol20"))
            if value is None:
                return False, "vol5_over_vol20", float("nan")
            return value <= self.vol_ratio_max, "vol5_over_vol20", value
        raise ValueError(f"Unsupported setup_mode for volatility_managed_intraday_premium: {self.setup_mode}")

    def _rank_check(self, row: dict[str, float], column: str) -> tuple[bool, str, float]:
        value = _finite_float(row.get(column))
        if value is None:
            return False, column, float("nan")
        return value <= self.vol_rank_max, column, value

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.vol_rank_max <= 1:
            raise ValueError("vol_rank_max must be in (0, 1].")
        if self.vol_ratio_max <= 0:
            raise ValueError("vol_ratio_max must be greater than 0.")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lagged volatility feature CSV not found: {path}")
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
