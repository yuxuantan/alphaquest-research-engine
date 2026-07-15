from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class RealYieldBreakevenStateEntry:
    name = "real_yield_breakeven_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "real_yield_1d_up_short")).lower()
        self.direction_mode = str(params.get("direction_mode", "high_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_real_yield_breakeven_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.value_column = str(params.get("value_column", "real_yield_change_1d"))
        self.rank_column = str(params.get("rank_column", "real_yield_change_1d_rank_252"))
        self.state_rank_threshold = float(params.get("state_rank_threshold", 0.60))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
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

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "real_yield_breakeven_equity_discount_rate",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "observation_date": row.get("observation_date"),
            "availability_rule": "latest FRED real-yield/breakeven observation strictly before NQ session_date",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "state_value_column": self.value_column,
            "state_value": value,
            "state_rank_column": self.rank_column,
            "state_rank": rank,
            "state_rank_threshold": self.state_rank_threshold,
            "dfii10": row.get("dfii10"),
            "t10yie": row.get("t10yie"),
            "dgs10": row.get("dgs10"),
            "real_yield_change_1d": row.get("real_yield_change_1d"),
            "real_yield_change_5d": row.get("real_yield_change_5d"),
            "breakeven_change_1d": row.get("breakeven_change_1d"),
            "breakeven_change_5d": row.get("breakeven_change_5d"),
            "nominal_real_gap_change_1d": row.get("nominal_real_gap_change_1d"),
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"real_yield_breakeven_state_{self.setup_mode}",
            swept_level=float(bar["close"]),
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "state_rank_column": self.rank_column,
                "state_rank": rank,
                "state_value_column": self.value_column,
                "state_value": value,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        low_tail = 1.0 - self.state_rank_threshold
        if self.direction_mode == "high_short":
            return "short" if rank >= self.state_rank_threshold else None
        if self.direction_mode == "high_long":
            return "long" if rank >= self.state_rank_threshold else None
        if self.direction_mode == "low_short":
            return "short" if rank <= low_tail else None
        if self.direction_mode == "low_long":
            return "long" if rank <= low_tail else None
        if self.direction_mode == "two_sided_high_short":
            if rank >= self.state_rank_threshold:
                return "short"
            if rank <= low_tail:
                return "long"
            return None
        raise ValueError(f"Unsupported direction_mode for real_yield_breakeven_state: {self.direction_mode}")

    def _validate(self) -> None:
        if self.direction_mode not in {"high_short", "high_long", "low_short", "low_long", "two_sided_high_short"}:
            raise ValueError("entry.params.direction_mode is unsupported.")
        if not 0.5 <= self.state_rank_threshold < 1.0:
            raise ValueError("entry.params.state_rank_threshold must be in [0.5, 1.0).")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than zero.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be positive.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Real-yield/breakeven feature CSV not found: {path}")
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
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
