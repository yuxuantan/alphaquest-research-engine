from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.vwap_orderflow_pullback_continuation import (
    VwapOrderflowPullbackContinuationEntry,
)


TERM_STATE_RULES = {
    "contango_long": ("vix_vix3m_ratio_rank_252", "<=", "long"),
    "backwardation_short": ("vix_vix3m_ratio_rank_252", ">=", "short"),
    "front_stress_short": ("vix9d_vix_ratio_rank_252", ">=", "short"),
    "curve_flattening_short": ("vix3m_vix6m_ratio_rank_252", ">=", "short"),
    "backwardation_surge_short": ("vix_vix3m_ratio_change_1d_rank_252", ">=", "short"),
}


class VixTermStructureOrderflowPullbackEntry(VwapOrderflowPullbackContinuationEntry):
    name = "vix_term_structure_orderflow_pullback"

    def __init__(self, params: dict):
        super().__init__(params)
        self.term_setup_mode = str(params.get("term_setup_mode", "contango_long")).lower()
        self.term_rank_threshold = float(params.get("term_rank_threshold", 0.4))
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self._validate_term_state()

    def _signal(self, direction: str, bar: pd.Series, pullback: dict, vwap: float, state: dict) -> Signal | None:
        term_state = self._term_state(bar, direction)
        if term_state is None:
            return None

        signal = super()._signal(direction, bar, pullback, vwap, state)
        if signal is None:
            return None

        signal.level_type = f"vix_term_structure_{self.term_setup_mode}_{signal.level_type}"
        signal.metadata.update(term_state)
        signal.report_fields.update(term_state)
        return signal

    def _term_state(self, bar: pd.Series, direction: str) -> dict | None:
        session_date = _date(bar.get("session_date", pd.Timestamp(bar["timestamp"]).date()))
        row = self.features.get(session_date)
        if row is None:
            return None

        column, op, expected_direction = TERM_STATE_RULES[self.term_setup_mode]
        if direction != expected_direction:
            return None
        rank = _finite_float(row.get(column))
        if rank is None:
            return None
        if op == "<=" and rank > self.term_rank_threshold:
            return None
        if op == ">=" and rank < self.term_rank_threshold:
            return None

        return {
            "term_structure_setup_mode": self.term_setup_mode,
            "term_structure_driver_column": column,
            "term_structure_driver_rank": rank,
            "term_structure_threshold_operator": op,
            "term_structure_rank_threshold": self.term_rank_threshold,
            "term_structure_expected_direction": expected_direction,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "cboe_observation_date": row.get("observation_date"),
            "availability_rule": "latest Cboe VIX term-structure close strictly before ES session_date",
            "vix_close": row.get("vix_close"),
            "vix9d_close": row.get("vix9d_close"),
            "vix3m_close": row.get("vix3m_close"),
            "vix6m_close": row.get("vix6m_close"),
            "vix_vix3m_ratio": row.get("vix_vix3m_ratio"),
            "vix9d_vix_ratio": row.get("vix9d_vix_ratio"),
            "vix3m_vix6m_ratio": row.get("vix3m_vix6m_ratio"),
            "vix_vix3m_ratio_change_1d": row.get("vix_vix3m_ratio_change_1d"),
        }

    def _validate_term_state(self) -> None:
        if self.term_setup_mode not in TERM_STATE_RULES:
            raise ValueError(f"entry.params.term_setup_mode must be one of {sorted(TERM_STATE_RULES)}.")
        if not 0 < self.term_rank_threshold <= 1:
            raise ValueError("entry.params.term_rank_threshold must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Cboe VIX term-structure feature CSV not found: {path}")
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
