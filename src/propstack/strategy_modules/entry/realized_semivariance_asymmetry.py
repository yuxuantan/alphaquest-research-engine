from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class RealizedSemivarianceAsymmetryEntry:
    name = "realized_semivariance_asymmetry"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_badvol_long")).lower()
        self.direction_mode = str(params.get("direction_mode", "high_long")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_realized_semivariance_features_20110103_20260609.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.value_column = str(params.get("value_column", "prior_downside_semivariance_1d"))
        self.rank_column = str(params.get("rank_column", "downside1_rank_252"))
        self.semivar_rank_threshold = float(params.get("semivar_rank_threshold", 0.35))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
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
        rank = _finite_float(row.get(self.rank_column))
        value = _finite_float(row.get(self.value_column))
        if rank is None or value is None:
            return None

        direction = self._direction(rank)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "barndorff_nielsen_kinnebrock_shephard_2010_patton_sheppard_2015",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "semivar_value_column": self.value_column,
            "semivar_value": value,
            "semivar_rank_column": self.rank_column,
            "semivar_rank": rank,
            "semivar_rank_threshold": self.semivar_rank_threshold,
            "prior_close": row.get("prior_close"),
            "prior_rth_return": row.get("prior_rth_return"),
            "prior_realized_variance": row.get("prior_realized_variance"),
            "prior_downside_semivariance_1d": row.get("prior_downside_semivariance_1d"),
            "prior_upside_semivariance_1d": row.get("prior_upside_semivariance_1d"),
            "prior_downside_share_1d": row.get("prior_downside_share_1d"),
            "prior_semivariance_balance_1d": row.get("prior_semivariance_balance_1d"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"realized_semivariance_asymmetry_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "semivar_rank_column": self.rank_column,
                "semivar_rank": rank,
                "semivar_value_column": self.value_column,
                "semivar_value": value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        high_cutoff = 1.0 - self.semivar_rank_threshold
        if self.direction_mode == "high_long":
            return "long" if rank >= high_cutoff else None
        if self.direction_mode == "high_short":
            return "short" if rank >= high_cutoff else None
        if self.direction_mode == "low_long":
            return "long" if rank <= self.semivar_rank_threshold else None
        if self.direction_mode == "low_short":
            return "short" if rank <= self.semivar_rank_threshold else None
        if self.direction_mode == "two_sided_bad_good":
            if rank >= high_cutoff:
                return "long"
            if rank <= self.semivar_rank_threshold:
                return "short"
            return None
        raise ValueError(f"Unsupported direction_mode for realized_semivariance_asymmetry: {self.direction_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.semivar_rank_threshold <= 0.5:
            raise ValueError("semivar_rank_threshold must be in (0, 0.5].")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lagged realized-semivariance feature CSV not found: {path}")
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
