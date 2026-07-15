from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.es_nq_relative_value_orderflow_absorption_reversion import (
    EsNqRelativeValueOrderflowAbsorptionReversionEntry,
)


class EsNqSemivarianceFilteredRelativeValueAbsorptionEntry(
    EsNqRelativeValueOrderflowAbsorptionReversionEntry
):
    name = "es_nq_semivariance_filtered_relative_value_absorption"

    def __init__(self, params: dict):
        super().__init__(params)
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_realized_semivariance_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.semivar_value_column = str(params.get("semivar_value_column", "prior_downside_semivariance_1d"))
        self.semivar_rank_column = str(params.get("semivar_rank_column", "downside1_rank_252"))
        self.benign_semivar_rank_max = float(params.get("benign_semivar_rank_max", 0.50))
        self._validate_semivariance_filter()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        signal = super().on_bar_close(bar, trades_today=trades_today)
        if signal is None:
            return None

        session_date = _date(bar["session_date"])
        row = self.features.get(session_date)
        if row is None:
            return None

        rank = _finite_float(row.get(self.semivar_rank_column))
        value = _finite_float(row.get(self.semivar_value_column))
        if rank is None or value is None:
            return None
        if rank > self.benign_semivar_rank_max:
            return None

        semivar_fields = {
            "semivariance_filter": "prior_session_benign_downside_semivariance",
            "feature_csv": self.feature_csv,
            "semivar_feature_session_date": session_date.isoformat(),
            "semivar_value_column": self.semivar_value_column,
            "semivar_value": value,
            "semivar_rank_column": self.semivar_rank_column,
            "semivar_rank": rank,
            "benign_semivar_rank_max": self.benign_semivar_rank_max,
            "prior_realized_variance": row.get("prior_realized_variance"),
            "prior_upside_semivariance_1d": row.get("prior_upside_semivariance_1d"),
            "prior_downside_semivariance_1d": row.get("prior_downside_semivariance_1d"),
            "prior_downside_share_1d": row.get("prior_downside_share_1d"),
            "prior_semivariance_balance_1d": row.get("prior_semivariance_balance_1d"),
        }
        metadata = dict(signal.metadata)
        metadata.update(
            {
                "semivariance_filter": semivar_fields["semivariance_filter"],
                "semivar_rank_column": self.semivar_rank_column,
                "semivar_rank": rank,
                "semivar_value_column": self.semivar_value_column,
                "semivar_value": value,
                "benign_semivar_rank_max": self.benign_semivar_rank_max,
            }
        )
        report_fields = dict(signal.report_fields)
        report_fields.update(semivar_fields)
        report_fields["academic_source_key"] = "relative_value_orderflow_absorption_filtered_by_semivariance"

        return replace(
            signal,
            level_type=f"{signal.level_type}_low_semivariance_regime",
            metadata=metadata,
            report_fields=report_fields,
        )

    def _validate_semivariance_filter(self) -> None:
        if not 0 < self.benign_semivar_rank_max <= 1:
            raise ValueError("entry.params.benign_semivar_rank_max must be in (0, 1].")
        if not self.semivar_rank_column:
            raise ValueError("entry.params.semivar_rank_column must be non-empty.")
        if not self.semivar_value_column:
            raise ValueError("entry.params.semivar_value_column must be non-empty.")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lagged realized-semivariance feature CSV not found: {path}")
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
