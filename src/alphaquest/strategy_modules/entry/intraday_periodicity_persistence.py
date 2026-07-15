from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class IntradayPeriodicityPersistenceEntry:
    name = "intraday_periodicity_persistence"

    def __init__(self, params: dict):
        self.params = params
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_intraday_periodicity_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.setup_mode = str(params.get("setup_mode", "slot_return_persistence")).lower()
        self.slot_id = str(params.get("slot_id", "slot_1000_1030"))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.slot_end_time = parse_time(params.get("slot_end_time", "10:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", params.get("slot_end_time", "10:30:00")))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_days = int(params.get("lookback_days", 20))
        self.min_mean_return_bps = float(params.get("min_mean_return_bps", 0.5))
        self.direction_mode = str(params.get("direction_mode", "two_sided")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.stop_pct = float(params.get("stop_pct", 0.0015))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.0))
        self.state_by_day: dict[date, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.entry_time.hour,
            minute=self.entry_time.minute,
            second=self.entry_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False})
        if state["signaled"]:
            return None

        row = self.features.get((session_date, self.slot_id))
        if row is None:
            return None

        mean_column = f"prior_slot_return_mean_bps_{self.lookback_days}"
        obs_column = f"prior_slot_return_obs_{self.lookback_days}"
        pos_rate_column = f"prior_slot_return_pos_rate_{self.lookback_days}"
        mean_return = _finite_float(row.get(mean_column))
        observations = _finite_float(row.get(obs_column))
        if mean_return is None or observations is None or observations < self.lookback_days:
            return None

        direction = self._direction_from_mean(mean_return)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "heston_korajczyk_sadka_2010_intraday_periodicity",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "slot_id": self.slot_id,
            "entry_time": self.entry_time.strftime("%H:%M:%S"),
            "slot_end_time": self.slot_end_time.strftime("%H:%M:%S"),
            "feature_session_date": session_date.isoformat(),
            "feature_availability_rule": "prior sessions only; current slot return excluded by shift(1)",
            "mean_return_column": mean_column,
            "prior_slot_return_mean_bps": mean_return,
            "prior_slot_return_obs": observations,
            "prior_slot_return_pos_rate": _finite_float(row.get(pos_rate_column)),
            "lookback_days": self.lookback_days,
            "min_mean_return_bps": self.min_mean_return_bps,
            "direction_mode": self.direction_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "entry_reference_stop_pct": self.stop_pct,
            "entry_reference_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"intraday_periodicity_{self.slot_id}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "slot_id": self.slot_id,
                "lookback_days": self.lookback_days,
                "min_mean_return_bps": self.min_mean_return_bps,
                "direction_mode": self.direction_mode,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction_from_mean(self, mean_return: float) -> str | None:
        if mean_return >= self.min_mean_return_bps:
            direction = "long"
        elif mean_return <= -self.min_mean_return_bps:
            direction = "short"
        else:
            return None

        if self.direction_mode == "two_sided":
            return direction
        if self.direction_mode == "long_only":
            return "long" if direction == "long" else None
        if self.direction_mode == "short_only":
            return "short" if direction == "short" else None
        raise ValueError("direction_mode must be one of two_sided, long_only, short_only.")

    def _validate(self) -> None:
        if self.setup_mode != "slot_return_persistence":
            raise ValueError("setup_mode must be slot_return_persistence.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be greater than 0.")
        if self.min_mean_return_bps < 0:
            raise ValueError("min_mean_return_bps must be non-negative.")
        if self.direction_mode not in {"two_sided", "long_only", "short_only"}:
            raise ValueError("direction_mode must be one of two_sided, long_only, short_only.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _load_features(path: str) -> dict[tuple[date, str], dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Intraday periodicity feature CSV not found: {path}")
    out: dict[tuple[date, str], dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            slot_id = str(row["slot_id"])
            out[(session_date, slot_id)] = {
                key: (value if key in {"slot_id", "entry_time", "slot_end_time"} else _nan_float(value))
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
