from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class MaxDailyReturnLotteryReversalEntry:
    name = "max_daily_return_lottery_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_max_short")).lower()
        self.direction_mode = str(params.get("direction_mode", "high_short")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/nq_max_daily_return_features_20110103_20260612.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.max_value_column = str(params.get("max_value_column", "prior_max_return_20d"))
        self.max_rank_column = str(params.get("max_rank_column", "max_return_20d_rank_252"))
        self.max_rank_threshold = float(params.get("max_rank_threshold", 0.35))
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
        max_rank = _finite_float(row.get(self.max_rank_column))
        max_value = _finite_float(row.get(self.max_value_column))
        if max_rank is None or max_value is None:
            return None

        direction = self._direction(max_rank)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "bali_cakici_whitelaw_2011_max_daily_return_lottery",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "max_value_column": self.max_value_column,
            "max_value": max_value,
            "max_rank_column": self.max_rank_column,
            "max_rank": max_rank,
            "max_rank_threshold": self.max_rank_threshold,
            "prior_close": row.get("prior_close"),
            "prior_daily_return": row.get("prior_daily_return"),
            "prior_max_return_5d": row.get("prior_max_return_5d"),
            "prior_max_return_20d": row.get("prior_max_return_20d"),
            "prior_max_return_63d": row.get("prior_max_return_63d"),
            "prior_avg_top5_return_20d": row.get("prior_avg_top5_return_20d"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"max_daily_return_lottery_reversal_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "max_rank_column": self.max_rank_column,
                "max_rank": max_rank,
                "max_value_column": self.max_value_column,
                "max_value": max_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, max_rank: float) -> str | None:
        high_cutoff = 1.0 - self.max_rank_threshold
        if self.direction_mode == "high_short":
            return "short" if max_rank >= high_cutoff else None
        if self.direction_mode == "low_long":
            return "long" if max_rank <= self.max_rank_threshold else None
        if self.direction_mode == "two_sided_extreme":
            if max_rank >= high_cutoff:
                return "short"
            if max_rank <= self.max_rank_threshold:
                return "long"
            return None
        raise ValueError(f"Unsupported direction_mode for max_daily_return_lottery_reversal: {self.direction_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.max_rank_threshold <= 0.5:
            raise ValueError("max_rank_threshold must be in (0, 0.5].")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lagged MAX daily-return feature CSV not found: {path}")
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
