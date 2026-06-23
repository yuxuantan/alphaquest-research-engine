from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.mes_trend_aoi_pullback import MesTrendAoiPullbackEntry


class VolFilteredMesTrendAoiPullbackEntry(MesTrendAoiPullbackEntry):
    name = "vol_filtered_mes_trend_aoi_pullback"

    def __init__(self, params: dict):
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_lagged_volatility_features_20110103_20260609.csv")
        )
        self.volatility_gate_column = str(params.get("volatility_gate_column", "absret5_rank_252"))
        self.volatility_gate_min = _optional_float(params.get("volatility_gate_min"))
        self.volatility_gate_max = _optional_float(params.get("volatility_gate_max", 0.95))
        self.volatility_filter_label = str(params.get("volatility_filter_label", self.volatility_gate_column))
        self.features = _load_features(self.feature_csv)
        super().__init__(params)

    def _signal_from_completed_bar(self, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal | None:
        gate_fields = self._volatility_gate_fields(bar)
        if gate_fields is None:
            return None
        signal = super()._signal_from_completed_bar(bar, signal_timestamp)
        if signal is None:
            return None
        signal.level_type = f"{signal.level_type}_vol_filtered"
        signal.metadata = {**signal.metadata, **gate_fields}
        signal.report_fields = {**signal.report_fields, **gate_fields}
        return signal

    def _volatility_gate_fields(self, bar: pd.Series) -> dict[str, object] | None:
        session_date = _date(bar.get("session_date", pd.Timestamp(bar["timestamp"]).date()))
        feature_row = self.features.get(session_date)
        if feature_row is None:
            return None
        gate_value = _finite_float(feature_row.get(self.volatility_gate_column))
        if gate_value is None:
            return None
        if self.volatility_gate_min is not None and gate_value < self.volatility_gate_min:
            return None
        if self.volatility_gate_max is not None and gate_value > self.volatility_gate_max:
            return None
        return {
            "volatility_filter_label": self.volatility_filter_label,
            "volatility_feature_csv": self.feature_csv,
            "volatility_feature_session_date": session_date.isoformat(),
            "volatility_gate_column": self.volatility_gate_column,
            "volatility_gate_value": gate_value,
            "volatility_gate_min": self.volatility_gate_min,
            "volatility_gate_max": self.volatility_gate_max,
            "volatility_filter_result": "passed",
        }

    def _validate(self) -> None:
        super()._validate()
        if not self.volatility_gate_column:
            raise ValueError("entry.params.volatility_gate_column is required.")
        if self.volatility_gate_min is None and self.volatility_gate_max is None:
            raise ValueError("entry.params.volatility_gate_min or volatility_gate_max is required.")
        if self.volatility_gate_min is not None and self.volatility_gate_max is not None:
            if self.volatility_gate_min > self.volatility_gate_max:
                raise ValueError("entry.params.volatility_gate_min cannot exceed volatility_gate_max.")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lagged volatility feature CSV not found: {path}")
    out: dict[date, dict[str, float]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {key: _nan_float(value) for key, value in row.items() if key != "session_date"}
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return _finite_float(value)


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
