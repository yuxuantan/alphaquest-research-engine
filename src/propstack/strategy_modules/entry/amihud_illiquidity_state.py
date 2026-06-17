from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class AmihudIlliquidityStateEntry:
    name = "amihud_illiquidity_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_illiq_long")).lower()
        self.direction_mode = str(params.get("direction_mode", "high_long")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_amihud_illiquidity_features_20110103_20260609.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.value_column = str(params.get("value_column", "prior_amihud_illiq_1d"))
        self.rank_column = str(params.get("rank_column", "illiq1_rank_252"))
        self.illiq_rank_threshold = float(params.get("illiq_rank_threshold", 0.35))
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
            "academic_source_key": "amihud_2002_acharya_pedersen_2005",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "illiq_value_column": self.value_column,
            "illiq_value": value,
            "illiq_rank_column": self.rank_column,
            "illiq_rank": rank,
            "illiq_rank_threshold": self.illiq_rank_threshold,
            "prior_close": row.get("prior_close"),
            "prior_rth_return": row.get("prior_rth_return"),
            "prior_abs_rth_return": row.get("prior_abs_rth_return"),
            "prior_dollar_volume": row.get("prior_dollar_volume"),
            "prior_amihud_illiq_1d": row.get("prior_amihud_illiq_1d"),
            "prior_price_impact_per_billion": row.get("prior_price_impact_per_billion"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"amihud_illiquidity_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "illiq_rank_column": self.rank_column,
                "illiq_rank": rank,
                "illiq_value_column": self.value_column,
                "illiq_value": value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        high_cutoff = 1.0 - self.illiq_rank_threshold
        if self.direction_mode == "high_long":
            return "long" if rank >= high_cutoff else None
        if self.direction_mode == "high_short":
            return "short" if rank >= high_cutoff else None
        if self.direction_mode == "low_long":
            return "long" if rank <= self.illiq_rank_threshold else None
        if self.direction_mode == "low_short":
            return "short" if rank <= self.illiq_rank_threshold else None
        if self.direction_mode == "two_sided_premium":
            if rank >= high_cutoff:
                return "long"
            if rank <= self.illiq_rank_threshold:
                return "short"
            return None
        if self.direction_mode == "two_sided_stress":
            if rank >= high_cutoff:
                return "short"
            if rank <= self.illiq_rank_threshold:
                return "long"
            return None
        raise ValueError(f"Unsupported direction_mode for amihud_illiquidity_state: {self.direction_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.illiq_rank_threshold <= 0.5:
            raise ValueError("illiq_rank_threshold must be in (0, 0.5].")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Amihud illiquidity feature CSV not found: {path}")
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
