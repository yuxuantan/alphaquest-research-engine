from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TreasuryRateStateEntry:
    name = "treasury_rate_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "rate_up_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_treasury_rate_state_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.rate_change_rank_min = float(params.get("rate_change_rank_min", 0.6))
        self.rate_change_rank_max = float(params.get("rate_change_rank_max", 0.4))
        self.rate_level_rank_min = float(params.get("rate_level_rank_min", 0.6))
        self.curve_change_rank_min = float(params.get("curve_change_rank_min", 0.6))
        self.curve_change_rank_max = float(params.get("curve_change_rank_max", 0.4))
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
            "academic_source_key": "bernanke_kuttner_2005_monetary_policy_equity_prices",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "treasury_observation_date": row.get("observation_date"),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "rate_driver_column": driver_column,
            "rate_driver_value": driver_value,
            "rate_change_rank_min": self.rate_change_rank_min,
            "rate_change_rank_max": self.rate_change_rank_max,
            "rate_level_rank_min": self.rate_level_rank_min,
            "curve_change_rank_min": self.curve_change_rank_min,
            "curve_change_rank_max": self.curve_change_rank_max,
            "dgs10": row.get("dgs10"),
            "dgs2": row.get("dgs2"),
            "curve_10y2y": row.get("curve_10y2y"),
            "dgs10_change_1d": row.get("dgs10_change_1d"),
            "curve_change_1d": row.get("curve_change_1d"),
            "dgs10_rank_252": row.get("dgs10_rank_252"),
            "dgs10_change_1d_rank_252": row.get("dgs10_change_1d_rank_252"),
            "curve_change_1d_rank_252": row.get("curve_change_1d_rank_252"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"treasury_rate_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "rate_driver_column": driver_column,
                "rate_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        change_rank = _finite_float(row.get("dgs10_change_1d_rank_252"))
        level_rank = _finite_float(row.get("dgs10_rank_252"))
        curve_rank = _finite_float(row.get("curve_change_1d_rank_252"))
        if self.setup_mode == "rate_up_short":
            if change_rank is None:
                return None, "dgs10_change_1d_rank_252", float("nan")
            return ("short" if change_rank >= self.rate_change_rank_min else None), "dgs10_change_1d_rank_252", change_rank
        if self.setup_mode == "rate_down_long":
            if change_rank is None:
                return None, "dgs10_change_1d_rank_252", float("nan")
            return ("long" if change_rank <= self.rate_change_rank_max else None), "dgs10_change_1d_rank_252", change_rank
        if self.setup_mode == "rate_up_high_level_short":
            if change_rank is None or level_rank is None:
                return None, "dgs10_change_1d_rank_252", float("nan")
            passed = change_rank >= self.rate_change_rank_min and level_rank >= self.rate_level_rank_min
            return ("short" if passed else None), "dgs10_change_1d_rank_252", change_rank
        if self.setup_mode == "bear_steepening_short":
            if change_rank is None or curve_rank is None:
                return None, "dgs10_change_1d_rank_252", float("nan")
            passed = change_rank >= self.rate_change_rank_min and curve_rank >= self.curve_change_rank_min
            return ("short" if passed else None), "dgs10_change_1d_rank_252", change_rank
        if self.setup_mode == "bull_flattening_long":
            if change_rank is None or curve_rank is None:
                return None, "dgs10_change_1d_rank_252", float("nan")
            passed = change_rank <= self.rate_change_rank_max and curve_rank <= self.curve_change_rank_max
            return ("long" if passed else None), "dgs10_change_1d_rank_252", change_rank
        raise ValueError(f"Unsupported setup_mode for treasury_rate_state: {self.setup_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        for name, value in {
            "rate_change_rank_min": self.rate_change_rank_min,
            "rate_change_rank_max": self.rate_change_rank_max,
            "rate_level_rank_min": self.rate_level_rank_min,
            "curve_change_rank_min": self.curve_change_rank_min,
            "curve_change_rank_max": self.curve_change_rank_max,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Treasury rate-state feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key == "observation_date" else _nan_float(value))
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
