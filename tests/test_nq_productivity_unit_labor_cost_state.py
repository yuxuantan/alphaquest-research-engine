from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_productivity_unit_labor_cost_state import (
    NqProductivityUnitLaborCostStateEntry,
)
from tools.build_nq_productivity_unit_labor_cost_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_productivity_unit_labor_cost_state"]
        is NqProductivityUnitLaborCostStateEntry
    )


def test_productivity_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-07-01", productivity_4q_rank=0.74)
    entry = NqProductivityUnitLaborCostStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "productivity_4q_strength_long",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-07-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-07-01 09:59", close=19005.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-07-01 10:00")
    assert signal.report_fields["productivity_driver_column"] == "productivity_change_4q_rank_80q"
    assert "180 calendar days" in signal.report_fields["availability_rule"]


def test_unit_labor_cost_pressure_emits_short_on_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-07-01", ulc_4q_rank=0.7)
    entry = NqProductivityUnitLaborCostStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "unit_labor_cost_4q_pressure_short",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-07-01 11:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"


def test_productivity_one_quarter_weakness_emits_short_on_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-07-01", productivity_1q_rank=0.25)
    entry = NqProductivityUnitLaborCostStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "productivity_1q_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-07-01 10:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["productivity_driver_column"] == "productivity_change_1q_rank_80q"


def test_unit_labor_cost_relief_long_requires_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-07-01", ulc_1q_rank=0.46)
    entry = NqProductivityUnitLaborCostStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "unit_labor_cost_1q_relief_long",
            "rank_max": 0.35,
            "entry_time": "12:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-07-01 11:59", close=19005.0)) is None

    features = _feature_file(tmp_path, "2024-07-02", ulc_1q_rank=0.24, name="relief.csv")
    entry = NqProductivityUnitLaborCostStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "unit_labor_cost_1q_relief_long",
            "rank_max": 0.35,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-07-02 11:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"


def test_builder_uses_180_day_cutoff(tmp_path):
    sessions = pd.date_range("2024-07-01", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    quarterly_dates = pd.date_range("2010-01-01", "2024-04-01", freq="QS")
    _write_fred_cache(cache_dir / "fred_ophnfb_quarterly.csv", "OPHNFB", quarterly_dates, 100.0)
    _write_fred_cache(cache_dir / "fred_ulcnfb_quarterly.csv", "ULCNFB", quarterly_dates, 90.0)
    _write_fred_cache(cache_dir / "fred_comprnfb_quarterly.csv", "COMPRNFB", quarterly_dates, 80.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
    )

    first = features.loc[features["session_date"] == "2024-07-01"].iloc[0]
    assert first["observation_cutoff"] == "2024-01-03"
    assert first["observation_date"] == "2024-01-01"
    assert math.isfinite(first["productivity_change_4q_rank_80q"])
    assert math.isfinite(first["unit_labor_cost_change_4q_rank_80q"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    productivity_1q_rank: float = 0.5,
    productivity_4q_rank: float = 0.5,
    ulc_1q_rank: float = 0.5,
    ulc_4q_rank: float = 0.5,
    prod_minus_ulc_rank: float = 0.5,
    name: str = "productivity.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "productivity_index,unit_labor_cost_index,real_hourly_comp_index,"
        "productivity_change_1q,productivity_change_4q,unit_labor_cost_change_1q,"
        "unit_labor_cost_change_4q,real_hourly_comp_change_4q,"
        "productivity_minus_ulc_change_4q,productivity_change_1q_rank_80q,"
        "productivity_change_4q_rank_80q,unit_labor_cost_change_1q_rank_80q,"
        "unit_labor_cost_change_4q_rank_80q,real_hourly_comp_change_4q_rank_80q,"
        "productivity_minus_ulc_change_4q_rank_80q\n"
        f"{session_date},2024-01-03,2024-01-01,180,110,120,105,0.01,0.02,"
        f"0.015,0.03,0.01,-0.01,{productivity_1q_rank},{productivity_4q_rank},{ulc_1q_rank},"
        f"{ulc_4q_rank},0.5,{prod_minus_ulc_rank}\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp: str, *, close: float, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": close - 5.0,
            "high": close + 10.0,
            "low": close - 10.0,
            "close": close,
        }
    )


def _write_fred_cache(path, series_id: str, dates, start_price: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["observation_date," + series_id]
    for index, day in enumerate(dates):
        value = start_price + index * 0.5
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
