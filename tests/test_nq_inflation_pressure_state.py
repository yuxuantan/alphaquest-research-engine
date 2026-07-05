from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_inflation_pressure_state import (
    NqInflationPressureStateEntry,
)
from tools.build_nq_inflation_pressure_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_inflation_pressure_state"] is NqInflationPressureStateEntry


def test_core_pce_high_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", core_pce_yoy_rank=0.82)
    entry = NqInflationPressureStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_pce_high_short",
            "rank_min": 0.60,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["inflation_driver_column"] == "core_pce_yoy_rank_120m"
    assert "45 calendar days" in signal.report_fields["availability_rule"]


def test_core_pce_disinflation_long_respects_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", core_pce_yoy_change_3m_rank=0.48)
    entry = NqInflationPressureStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_pce_disinflation_long",
            "rank_max": 0.40,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(
        tmp_path, "2024-04-04", core_pce_yoy_change_3m_rank=0.22, name="disinflation.csv"
    )
    entry = NqInflationPressureStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_pce_disinflation_long",
            "rank_max": 0.40,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"


def test_core_cpi_acceleration_uses_three_month_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", core_cpi_3m_rank=0.77)
    entry = NqInflationPressureStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_cpi_accel_short",
            "rank_min": 0.65,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["inflation_driver_column"] == "core_cpi_3m_ann_rank_120m"


def test_pce_disinflation_uses_pce_three_month_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", pce_3m_rank=0.18)
    entry = NqInflationPressureStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "pce_disinflation_long",
            "rank_max": 0.35,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["inflation_driver_column"] == "pce_3m_ann_rank_120m"


def test_builder_uses_monthly_observations_at_least_45_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-03-18", periods=85, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    months = pd.date_range("2010-01-01", "2024-06-01", freq="MS")
    _write_fred_csv(cache_dir / "fred_pcepi_monthly.csv", "PCEPI", months, 100.0)
    _write_fred_csv(cache_dir / "fred_pcepilfe_monthly.csv", "PCEPILFE", months, 100.0)
    _write_fred_csv(cache_dir / "fred_cpiaucsl_monthly.csv", "CPIAUCSL", months, 220.0)
    _write_fred_csv(cache_dir / "fred_cpilfesl_monthly.csv", "CPILFESL", months, 220.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        availability_lag_days=45,
        rank_min_periods=12,
        start_session="2024-03-18",
    )

    first = features.loc[features["session_date"] == "2024-03-18"].iloc[0]
    later = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-02-01"
    assert math.isfinite(later["core_pce_yoy_rank_120m"])
    assert math.isfinite(later["core_cpi_3m_ann_rank_120m"])
    assert math.isfinite(later["pce_3m_ann_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    core_pce_yoy_rank: float = 0.5,
    core_pce_yoy_change_3m_rank: float = 0.5,
    cpi_yoy_rank: float = 0.5,
    core_cpi_3m_rank: float = 0.5,
    pce_3m_rank: float = 0.5,
    name: str = "inflation.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "pce_price_index,core_pce_price_index,cpi_all_items,core_cpi,pce_yoy,"
        "core_pce_yoy,cpi_yoy,core_cpi_yoy,pce_3m_ann,core_pce_3m_ann,"
        "cpi_3m_ann,core_cpi_3m_ann,core_pce_yoy_change_3m,core_cpi_yoy_change_3m,"
        "pce_yoy_rank_120m,core_pce_yoy_rank_120m,cpi_yoy_rank_120m,"
        "core_cpi_yoy_rank_120m,pce_3m_ann_rank_120m,core_pce_3m_ann_rank_120m,"
        "cpi_3m_ann_rank_120m,core_cpi_3m_ann_rank_120m,"
        "core_pce_yoy_change_3m_rank_120m,core_cpi_yoy_change_3m_rank_120m\n"
        f"{session_date},2024-02-18,2024-02-01,45,120,121,300,305,0.03,0.032,0.035,0.034,"
        f"0.02,0.025,0.03,0.031,-0.002,0.001,0.5,{core_pce_yoy_rank},"
        f"{cpi_yoy_rank},0.5,{pce_3m_rank},0.5,0.5,{core_cpi_3m_rank},"
        f"{core_pce_yoy_change_3m_rank},0.5\n",
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
        value = start_value + index * 0.2
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
