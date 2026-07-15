from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class NqLaborMarketSlackStateEntry:
    name = "nq_labor_market_slack_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_unemployment_slack_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_labor_market_slack_state_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.rank_threshold = float(params.get("rank_threshold", 0.55))
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
        direction, driver_column, driver_value, cutoff = self._signal_direction(row)
        if direction is None:
            return None
        state["signaled"] = True
        report_fields = {
            "academic_source_key": "fred_bls_labor_market_slack_state",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "observation_date": row.get("observation_date"),
            "observation_cutoff": row.get("observation_cutoff"),
            "availability_lag_days": row.get("availability_lag_days"),
            "availability_rule": "latest monthly FRED/BLS labor observation on or before session_date minus 45 calendar days",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "labor_driver_column": driver_column,
            "labor_driver_value": driver_value,
            "rank_threshold": self.rank_threshold,
            "effective_cutoff": cutoff,
            "unemployment_rate_rank_120m": row.get("unemployment_rate_rank_120m"),
            "underemployment_rate_rank_120m": row.get("underemployment_rate_rank_120m"),
            "employment_population_ratio_rank_120m": row.get("employment_population_ratio_rank_120m"),
            "participation_rate_rank_120m": row.get("participation_rate_rank_120m"),
            "participation_rate_change_3m_rank_120m": row.get("participation_rate_change_3m_rank_120m"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"nq_labor_market_slack_state_{self.setup_mode}",
            swept_level=float(bar["close"]),
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "labor_driver_column": driver_column,
                "labor_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float, float]:
        high_short = {
            "high_unemployment_slack_short": "unemployment_rate_rank_120m",
            "high_underemployment_slack_short": "underemployment_rate_rank_120m",
        }
        low_short = {
            "low_employment_ratio_slack_short": "employment_population_ratio_rank_120m",
            "low_participation_slack_short": "participation_rate_rank_120m",
        }
        high_long = {
            "rising_participation_repair_long": "participation_rate_change_3m_rank_120m",
        }
        if self.setup_mode in high_short:
            column = high_short[self.setup_mode]
            rank = _finite_float(row.get(column))
            return (
                ("short" if rank is not None and rank >= self.rank_threshold else None),
                column,
                rank if rank is not None else float("nan"),
                self.rank_threshold,
            )
        if self.setup_mode in low_short:
            column = low_short[self.setup_mode]
            cutoff = 1.0 - self.rank_threshold
            rank = _finite_float(row.get(column))
            return (
                ("short" if rank is not None and rank <= cutoff else None),
                column,
                rank if rank is not None else float("nan"),
                cutoff,
            )
        if self.setup_mode in high_long:
            column = high_long[self.setup_mode]
            rank = _finite_float(row.get(column))
            return (
                ("long" if rank is not None and rank >= self.rank_threshold else None),
                column,
                rank if rank is not None else float("nan"),
                self.rank_threshold,
            )
        raise ValueError(f"Unsupported setup_mode for nq_labor_market_slack_state: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.rank_threshold <= 1:
            raise ValueError("rank_threshold must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"NQ labor-market feature CSV not found: {path}")
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
