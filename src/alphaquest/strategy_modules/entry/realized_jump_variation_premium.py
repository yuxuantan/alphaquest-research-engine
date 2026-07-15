from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class RealizedJumpVariationPremiumEntry:
    name = "realized_jump_variation_premium"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_jump_long")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_realized_jump_variation_features_20110103_20260609.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.jump_rank_column = str(params.get("jump_rank_column", "jump_var_rank_252"))
        self.jump_rank_min = float(params.get("jump_rank_min", 0.65))
        self.jump_rank_max = float(params.get("jump_rank_max", 0.35))
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
        direction, driver_column, driver_value = self._signal_direction(row)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "barndorff_nielsen_shephard_2004_bipower_jump_variation",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "jump_driver_column": driver_column,
            "jump_driver_value": driver_value,
            "jump_rank_min": self.jump_rank_min,
            "jump_rank_max": self.jump_rank_max,
            "prior_realized_variance": row.get("prior_realized_variance"),
            "prior_bipower_variation": row.get("prior_bipower_variation"),
            "prior_jump_variation": row.get("prior_jump_variation"),
            "prior_jump_share": row.get("prior_jump_share"),
            "prior_positive_jump_variation": row.get("prior_positive_jump_variation"),
            "prior_negative_jump_variation": row.get("prior_negative_jump_variation"),
            "prior_signed_jump_share": row.get("prior_signed_jump_share"),
            "jump_var_rank_252": row.get("jump_var_rank_252"),
            "jump_share_rank_252": row.get("jump_share_rank_252"),
            "negative_jump_rank_252": row.get("negative_jump_rank_252"),
            "positive_jump_rank_252": row.get("positive_jump_rank_252"),
            "signed_jump_rank_252": row.get("signed_jump_rank_252"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"realized_jump_variation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "jump_driver_column": driver_column,
                "jump_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float]) -> tuple[str | None, str, float]:
        if self.setup_mode == "high_jump_long":
            return self._threshold_direction(row, self.jump_rank_column, "long", high=True)
        if self.setup_mode == "high_jump_short":
            return self._threshold_direction(row, self.jump_rank_column, "short", high=True)
        if self.setup_mode == "negative_jump_long":
            return self._threshold_direction(row, "negative_jump_rank_252", "long", high=True)
        if self.setup_mode == "positive_jump_short":
            return self._threshold_direction(row, "positive_jump_rank_252", "short", high=True)
        if self.setup_mode == "two_sided_signed_jump_extreme":
            value = _finite_float(row.get("signed_jump_rank_252"))
            if value is None:
                return None, "signed_jump_rank_252", float("nan")
            if value <= self.jump_rank_max:
                return "long", "signed_jump_rank_252", value
            if value >= self.jump_rank_min:
                return "short", "signed_jump_rank_252", value
            return None, "signed_jump_rank_252", value
        raise ValueError(f"Unsupported setup_mode for realized_jump_variation_premium: {self.setup_mode}")

    def _threshold_direction(
        self,
        row: dict[str, float],
        column: str,
        direction: str,
        *,
        high: bool,
    ) -> tuple[str | None, str, float]:
        value = _finite_float(row.get(column))
        if value is None:
            return None, column, float("nan")
        passed = value >= self.jump_rank_min if high else value <= self.jump_rank_max
        return (direction if passed else None), column, value

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not 0 < self.jump_rank_max < self.jump_rank_min <= 1:
            raise ValueError("jump_rank thresholds must satisfy 0 < jump_rank_max < jump_rank_min <= 1.")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Realized jump-variation feature CSV not found: {path}")
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
