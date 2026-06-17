from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class AqrBabFactorStateEntry:
    name = "aqr_bab_factor_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "low_bab_rebound_long")).lower()
        self.feature_csv = str(params.get("feature_csv", "data/external/es_aqr_bab_features_20110103_20260609.csv"))
        self.features = _load_features(self.feature_csv)
        self.rank_column = str(params.get("rank_column", "bab_usa_return_rank_252"))
        self.value_column = str(params.get("value_column", "bab_usa_return_1d"))
        self.bab_rank_threshold = float(params.get("bab_rank_threshold", 0.25))
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
            "academic_source_key": "frazzini_pedersen_2014_betting_against_beta",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "bab_observation_date": row.get("observation_date"),
            "availability_cutoff": row.get("availability_cutoff"),
            "publication_lag_calendar_days": row.get("publication_lag_calendar_days"),
            "observation_age_days": row.get("observation_age_days"),
            "availability_rule": "latest AQR BAB observation at least configured calendar days before the ES session",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "bab_rank_column": self.rank_column,
            "bab_rank": rank,
            "bab_value_column": self.value_column,
            "bab_value": value,
            "bab_rank_threshold": self.bab_rank_threshold,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"aqr_bab_factor_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "bab_rank_column": self.rank_column,
                "bab_rank": rank,
                "bab_value_column": self.value_column,
                "bab_value": value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        high_cutoff = 1.0 - self.bab_rank_threshold
        if self.setup_mode in {
            "low_bab_rebound_long",
            "bab_drawdown_rebound_long",
            "low_bab_z_rebound_long",
        }:
            return "long" if rank <= self.bab_rank_threshold else None
        if self.setup_mode == "high_bab_risk_on_long":
            return "long" if rank >= high_cutoff else None
        if self.setup_mode == "two_sided_bab_state":
            if rank <= self.bab_rank_threshold:
                return "long"
            if rank >= high_cutoff:
                return "short"
            return None
        raise ValueError(f"Unsupported setup_mode for aqr_bab_factor_state: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.bab_rank_threshold <= 0.5:
            raise ValueError("bab_rank_threshold must be in (0, 0.5].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"AQR BAB feature CSV not found: {path}")
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
