from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class InfectiousDiseaseEmvStateEntry:
    name = "infectious_disease_emv_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_21d_emv_riskoff_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_infectious_disease_emv_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.rank_column = str(params.get("rank_column", "infect_emv_21d_rank_252"))
        self.value_column = str(params.get("value_column", "infect_emv_21d"))
        self.state_name = str(params.get("state_name", "infectious disease EMV"))
        self.emv_rank_threshold = float(params.get("emv_rank_threshold", 0.40))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.stop_pct = float(params.get("stop_pct", 0.004))
        self.target_r_multiple = float(params.get("target_r_multiple", 2.0))
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
        high_cutoff = 1.0 - self.emv_rank_threshold
        report_fields = {
            "academic_source_key": "baker_bloom_davis_kost_2020_infectious_disease_emv",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "infect_emv_observation_date": row.get("observation_date"),
            "availability_cutoff": row.get("availability_cutoff"),
            "publication_lag_calendar_days": row.get("publication_lag_calendar_days"),
            "observation_age_days": row.get("observation_age_days"),
            "availability_rule": "latest FRED infectious-disease EMV daily observation at least configured calendar days before the futures session",
            "publication_schedule_caveat": "FRED marks the daily series as updated daily; the test still uses a conservative lag and requires manual release-cadence review if it passes.",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "infect_emv_state_name": self.state_name,
            "infect_emv_rank_column": self.rank_column,
            "infect_emv_rank": rank,
            "infect_emv_value_column": self.value_column,
            "infect_emv_value": value,
            "infect_emv_rank_threshold": self.emv_rank_threshold,
            "infect_emv_high_cutoff": high_cutoff,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"infectious_disease_emv_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "infect_emv_state_name": self.state_name,
                "infect_emv_rank_column": self.rank_column,
                "infect_emv_rank": rank,
                "infect_emv_value_column": self.value_column,
                "infect_emv_value": value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        high_cutoff = 1.0 - self.emv_rank_threshold
        if rank < high_cutoff:
            return None
        if self.setup_mode in {
            "high_21d_emv_riskoff_short",
            "rising_5d_emv_short",
            "high_7d_emv_short",
        }:
            return "short"
        if self.setup_mode in {
            "high_21d_emv_rebound_long",
            "high_1d_emv_rebound_long",
        }:
            return "long"
        raise ValueError(f"Unsupported setup_mode for infectious_disease_emv_state: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.emv_rank_threshold <= 0.5:
            raise ValueError("emv_rank_threshold must be in (0, 0.5].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Infectious disease EMV feature CSV not found: {path}")
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
