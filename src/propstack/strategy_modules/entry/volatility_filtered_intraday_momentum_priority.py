from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.intraday_momentum_priority import IntradayMomentumPriorityEntry


class VolatilityFilteredIntradayMomentumPriorityEntry(IntradayMomentumPriorityEntry):
    name = "volatility_filtered_intraday_momentum_priority"

    def __init__(self, params: dict):
        super().__init__(params)
        self.feature_csv = str(params.get("feature_csv", "data/external/nq_lagged_volatility_features_20110103_20260612.csv"))
        self.volatility_gate_column = str(params.get("volatility_gate_column", "range10_rank_252")).strip()
        self.volatility_gate_max = float(params.get("volatility_gate_max", 0.6))
        self.features = _load_features(self.feature_csv)
        self._validate_volatility_filter()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0):
        signal = super().on_bar_close(bar, trades_today=trades_today)
        if signal is None:
            return None

        session_date = _date(bar.get("session_date", pd.Timestamp(bar["timestamp"]).date()))
        feature_row = self.features.get(session_date)
        if feature_row is None:
            return None
        gate_value = _finite_float(feature_row.get(self.volatility_gate_column))
        if gate_value is None or gate_value > self.volatility_gate_max:
            return None

        gate_fields = {
            "volatility_feature_csv": self.feature_csv,
            "volatility_feature_session_date": session_date.isoformat(),
            "volatility_gate_column": self.volatility_gate_column,
            "volatility_gate_value": gate_value,
            "volatility_gate_max": self.volatility_gate_max,
            "volatility_filter_result": "passed",
        }
        signal.level_type = f"{signal.level_type}_volatility_filtered"
        signal.metadata = {**signal.metadata, **gate_fields}
        signal.report_fields = {**signal.report_fields, **gate_fields}
        return signal

    def _validate_volatility_filter(self) -> None:
        if not self.volatility_gate_column:
            raise ValueError("volatility_gate_column must be non-empty.")
        if not math.isfinite(self.volatility_gate_max) or self.volatility_gate_max <= 0:
            raise ValueError("volatility_gate_max must be a positive finite value.")


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
