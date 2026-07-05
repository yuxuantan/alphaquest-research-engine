from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class CorporateEquitySupplyStateEntry:
    name = "corporate_equity_supply_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_1q_net_equity_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_corporate_equity_supply_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.rank_column = str(params.get("rank_column", "net_equity_to_market_1q_rank_40q"))
        self.value_column = str(params.get("value_column", "net_equity_to_market_1q"))
        self.state_name = str(params.get("state_name", "corporate equity supply"))
        self.supply_rank_threshold = float(params.get("supply_rank_threshold", 0.25))
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
        report_fields = {
            "academic_source_key": "baker_wurgler_2000_equity_share",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "corporate_supply_observation_date": row.get("observation_date"),
            "availability_cutoff": row.get("availability_cutoff"),
            "publication_lag_calendar_days": row.get("publication_lag_calendar_days"),
            "observation_age_days": row.get("observation_age_days"),
            "availability_rule": "latest FRED quarterly corporate financing observation at least configured calendar days before the futures session",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "corporate_supply_state_name": self.state_name,
            "corporate_supply_rank_column": self.rank_column,
            "corporate_supply_rank": rank,
            "corporate_supply_value_column": self.value_column,
            "corporate_supply_value": value,
            "supply_rank_threshold": self.supply_rank_threshold,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"corporate_equity_supply_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "corporate_supply_state_name": self.state_name,
                "corporate_supply_rank_column": self.rank_column,
                "corporate_supply_rank": rank,
                "corporate_supply_value_column": self.value_column,
                "corporate_supply_value": value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        threshold = self.supply_rank_threshold
        if self.setup_mode == "low_debt_minus_equity_short":
            if rank > threshold:
                return None
            return "short"
        if rank < 1.0 - threshold:
            return None
        if self.setup_mode in {
            "high_1q_net_equity_short",
            "high_4q_net_equity_short",
            "rising_4q_net_equity_short",
            "high_equity_share_short",
        }:
            return "short"
        raise ValueError(f"Unsupported setup_mode for corporate_equity_supply_state: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.supply_rank_threshold <= 0.5:
            raise ValueError("supply_rank_threshold must be in (0, 0.5].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Corporate equity supply feature CSV not found: {path}")
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
