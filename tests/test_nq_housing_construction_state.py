from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_housing_construction_state import (
    NqHousingConstructionStateEntry,
)
from tools.build_nq_housing_construction_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_housing_construction_state"] is NqHousingConstructionStateEntry


def test_permits_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", permits_3m_rank=0.72)
    entry = NqHousingConstructionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "permits_3m_strength_long",
            "rank_min": 0.60,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["housing_driver_column"] == "total_permits_change_3m_rank_120m"
    assert "45 calendar days" in signal.report_fields["availability_rule"]


def test_permits_weakness_short_respects_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", permits_3m_rank=0.48)
    entry = NqHousingConstructionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "permits_3m_weakness_short",
            "rank_max": 0.40,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", permits_3m_rank=0.22, name="weak.csv")
    entry = NqHousingConstructionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "permits_3m_weakness_short",
            "rank_max": 0.40,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_single_family_permits_strength_uses_single_family_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", single_family_permits_3m_rank=0.82)
    entry = NqHousingConstructionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "single_family_permits_strength_long",
            "rank_min": 0.60,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["housing_driver_column"] == (
        "single_family_permits_change_3m_rank_120m"
    )


def test_multifamily_starts_weakness_short_uses_multifamily_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", multifamily_starts_3m_rank=0.22)
    entry = NqHousingConstructionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "multifamily_starts_3m_weakness_short",
            "rank_max": 0.40,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["housing_driver_column"] == (
        "multifamily_starts_change_3m_rank_120m"
    )


def test_permit_starts_ratio_high_uses_ratio_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", permit_starts_ratio_rank=0.77)
    entry = NqHousingConstructionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "permit_starts_ratio_high_long",
            "rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["housing_driver_column"] == "permit_starts_ratio_rank_120m"


def test_builder_uses_monthly_observations_at_least_45_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-03-18", periods=85, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    months = pd.date_range("2013-01-01", "2024-06-01", freq="MS")
    _write_fred_csv(cache_dir / "fred_permit_monthly.csv", "PERMIT", months, 1500.0)
    _write_fred_csv(cache_dir / "fred_permit1_monthly.csv", "PERMIT1", months, 900.0)
    _write_fred_csv(cache_dir / "fred_permit5_monthly.csv", "PERMIT5", months, 450.0)
    _write_fred_csv(cache_dir / "fred_houst_monthly.csv", "HOUST", months, 1450.0)
    _write_fred_csv(cache_dir / "fred_houst1f_monthly.csv", "HOUST1F", months, 850.0)
    _write_fred_csv(cache_dir / "fred_houst5f_monthly.csv", "HOUST5F", months, 500.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        availability_lag_days=45,
        rank_min_periods=6,
        start_session="2024-03-18",
    )

    first = features.loc[features["session_date"] == "2024-03-18"].iloc[0]
    later = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-02-01"
    assert math.isfinite(later["total_permits_change_3m_rank_120m"])
    assert math.isfinite(later["single_family_permits_change_3m_rank_120m"])
    assert math.isfinite(later["total_starts_change_3m_rank_120m"])
    assert math.isfinite(later["permit_starts_ratio_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    permits_3m_rank: float = 0.5,
    starts_3m_rank: float = 0.5,
    single_family_permits_3m_rank: float = 0.5,
    multifamily_starts_3m_rank: float = 0.5,
    permit_starts_ratio_rank: float = 0.5,
    name: str = "housing.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "total_permits,single_family_permits,multifamily_permits,total_starts,"
        "single_family_starts,multifamily_starts,permit_starts_ratio,"
        "single_family_permit_share,total_permits_change_1m,total_permits_change_3m,"
        "single_family_permits_change_1m,single_family_permits_change_3m,"
        "multifamily_permits_change_1m,multifamily_permits_change_3m,"
        "total_starts_change_1m,total_starts_change_3m,single_family_starts_change_1m,"
        "single_family_starts_change_3m,multifamily_starts_change_1m,"
        "multifamily_starts_change_3m,permit_starts_ratio_change_3m,"
        "total_permits_change_3m_rank_120m,single_family_permits_change_3m_rank_120m,"
        "total_starts_change_3m_rank_120m,multifamily_starts_change_3m_rank_120m,"
        "permit_starts_ratio_rank_120m,permit_starts_ratio_change_3m_rank_120m\n"
        f"{session_date},2024-02-18,2024-02-01,45,1500,900,450,1450,850,500,1.03,0.60,"
        f"0.01,0.03,0.01,0.03,0.01,0.03,0.01,0.03,0.01,0.03,0.01,0.03,0.02,"
        f"{permits_3m_rank},{single_family_permits_3m_rank},{starts_3m_rank},"
        f"{multifamily_starts_3m_rank},{permit_starts_ratio_rank},0.5\n",
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


def _write_fred_csv(path, series_id: str, dates, start_value: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["observation_date," + series_id]
    for index, day in enumerate(dates):
        value = start_value + index * 1.0
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
