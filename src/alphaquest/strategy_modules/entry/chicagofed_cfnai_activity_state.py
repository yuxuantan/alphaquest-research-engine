from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class ChicagoFedCfnaiActivityStateEntry:
    name = "chicagofed_cfnai_activity_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "activity_weak_pullback_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.driver_column = str(params.get("driver_column", "CFNAI"))
        self.driver_max = float(params.get("driver_max", 0.0))
        self.max_session_return_bps = float(params.get("max_session_return_bps", -5.0))
        self.entry_time = parse_time(params.get("entry_time", "11:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.stop_pct = float(params.get("stop_pct", 0.006))
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
        state = self._state(session_date)
        self._update_state(state, bar)
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
        driver_value = _finite_float(row.get(self.driver_column))
        session_return_bps = self._session_return_bps(state, bar)
        if driver_value is None or driver_value > self.driver_max:
            return None
        if not math.isfinite(session_return_bps) or session_return_bps > self.max_session_return_bps:
            return None

        current_close = float(bar["close"])
        state["signaled"] = True
        return Signal(
            direction="long",
            level_type=f"chicagofed_cfnai_activity_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(state["high"]),
            sweep_low=float(state["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "driver_column": self.driver_column,
                "driver_value": driver_value,
                "driver_max": self.driver_max,
                "session_return_bps": session_return_bps,
                "max_session_return_bps": self.max_session_return_bps,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "academic_source_key": "chicagofed_cfnai_business_conditions_expected_returns",
                "setup_mode": self.setup_mode,
                "feature_csv": self.feature_csv,
                "feature_session_date": session_date.isoformat(),
                "cfnai_observation_date": row.get("obs_date"),
                "cfnai_eligible_date": row.get("eligible_date"),
                "availability_rule": "latest CFNAI observation whose conservative eligible date is on or before the futures session date",
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "cfnai_driver_column": self.driver_column,
                "cfnai_driver_value": driver_value,
                "driver_max": self.driver_max,
                "session_return_bps": session_return_bps,
                "max_session_return_bps": self.max_session_return_bps,
                "P_I": row.get("P_I"),
                "EU_H": row.get("EU_H"),
                "C_H": row.get("C_H"),
                "SO_I": row.get("SO_I"),
                "CFNAI": row.get("CFNAI"),
                "CFNAI_MA3": row.get("CFNAI_MA3"),
                "DIFFUSION": row.get("DIFFUSION"),
                "signal_stop_pct": self.stop_pct,
                "signal_target_r_multiple": self.target_r_multiple,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
                "swept_level": current_close,
                "sweep_timestamp": timestamp,
                "sweep_high": float(state["high"]),
                "sweep_low": float(state["low"]),
                "reclaim_timestamp": signal_timestamp,
            },
        )

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "first_open": None,
                "high": None,
                "low": None,
            },
        )

    def _update_state(self, state: dict, bar: pd.Series) -> None:
        open_price = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if open_price is not None and state["first_open"] is None:
            state["first_open"] = open_price
        if high is not None:
            state["high"] = high if state["high"] is None else max(float(state["high"]), high)
        if low is not None:
            state["low"] = low if state["low"] is None else min(float(state["low"]), low)

    def _session_return_bps(self, state: dict, bar: pd.Series) -> float:
        first_open = _finite_float(state.get("first_open"))
        close = _finite_float(bar.get("close"))
        if first_open is None or close is None or first_open <= 0:
            return float("nan")
        return (close / first_open - 1.0) * 10000.0

    def _validate(self) -> None:
        if not self.driver_column:
            raise ValueError("driver_column must be configured.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Chicago Fed CFNAI feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (
                    value
                    if key in {"obs_date", "obs_month", "eligible_date"}
                    else _nan_float(value)
                )
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
