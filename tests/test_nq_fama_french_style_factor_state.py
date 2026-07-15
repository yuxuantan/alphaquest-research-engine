from __future__ import annotations

import math
from zipfile import ZipFile

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.fama_french_style_factor_state import (
    FamaFrenchStyleFactorStateEntry,
)
from tools.build_nq_fama_french_style_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["fama_french_style_factor_state"] is FamaFrenchStyleFactorStateEntry


def test_hml_value_strength_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", hml_rank=0.82)
    entry = FamaFrenchStyleFactorStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hml_value_strength_short",
            "factor_name": "HML",
            "rank_column": "hml_21d_rank_252",
            "value_column": "hml_21d",
            "factor_rank_threshold": 0.30,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["factor_rank_column"] == "hml_21d_rank_252"
    assert signal.report_fields["availability_rule"].startswith("latest Fama-French")


def test_hml_growth_strength_requires_low_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", hml_rank=0.42)
    entry = FamaFrenchStyleFactorStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hml_growth_strength_long",
            "rank_column": "hml_21d_rank_252",
            "value_column": "hml_21d",
            "factor_rank_threshold": 0.30,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", hml_rank=0.18, name="growth.csv")
    entry = FamaFrenchStyleFactorStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hml_growth_strength_long",
            "rank_column": "hml_21d_rank_252",
            "value_column": "hml_21d",
            "factor_rank_threshold": 0.30,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"


def test_two_sided_hml_extreme_can_emit_long_or_short(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", hml63_rank=0.91)
    entry = FamaFrenchStyleFactorStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hml_extreme_two_sided",
            "rank_column": "hml_63d_rank_252",
            "value_column": "hml_63d",
            "factor_rank_threshold": 0.25,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0)).direction == "short"

    features = _feature_file(tmp_path, "2024-04-04", hml63_rank=0.09, name="low.csv")
    entry = FamaFrenchStyleFactorStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hml_extreme_two_sided",
            "rank_column": "hml_63d_rank_252",
            "value_column": "hml_63d",
            "factor_rank_threshold": 0.25,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-04 13:29", close=18010.0)).direction == "long"


def test_builder_uses_45_calendar_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-04-15", periods=90, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    zip_path = tmp_path / "ff.zip"
    _write_fama_french_zip(zip_path, pd.date_range("2023-01-02", "2024-06-30", freq="B"))
    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        ff_zip_path=zip_path,
        publication_lag_calendar_days=45,
        download_if_missing=False,
    )

    first = features.loc[features["session_date"] == "2024-04-15"].iloc[0]
    later = features.iloc[-1]
    assert first["availability_cutoff"] == "2024-03-01"
    assert first["observation_date"] <= "2024-03-01"
    assert int(first["observation_age_days"]) >= 45
    assert math.isfinite(later["hml_21d_rank_252"])
    assert math.isfinite(later["rmw_63d_rank_252"])
    assert math.isfinite(later["cma_63d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    hml_rank: float = 0.5,
    hml63_rank: float = 0.5,
    rmw_rank: float = 0.5,
    cma_rank: float = 0.5,
    name: str = "style.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,"
        "observation_age_days,mkt_rf_1d,smb_1d,hml_1d,rmw_1d,cma_1d,rf_1d,"
        "hml_21d,hml_63d,rmw_21d,rmw_63d,cma_21d,cma_63d,hml_z_63d,rmw_z_63d,cma_z_63d,"
        "hml_1d_rank_252,hml_21d_rank_252,hml_63d_rank_252,hml_z63_rank_252,"
        "rmw_21d_rank_252,rmw_63d_rank_252,rmw_z63_rank_252,cma_21d_rank_252,"
        "cma_63d_rank_252,cma_z63_rank_252\n"
        f"{session_date},2024-02-15,2024-02-18,45,48,0.001,0.0,0.002,0.001,-0.001,0.0,"
        f"0.02,0.03,0.01,0.04,0.01,0.05,0.2,0.3,0.4,0.55,{hml_rank},{hml63_rank},"
        f"0.52,0.51,{rmw_rank},0.53,0.54,{cma_rank},0.56\n",
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


def _write_fama_french_zip(path, dates) -> None:
    lines = [
        "This is a synthetic Fama-French style file for tests.",
        ",Mkt-RF,SMB,HML,RMW,CMA,RF",
    ]
    for index, day in enumerate(dates):
        hml = ((index % 17) - 8) / 100.0
        rmw = ((index % 13) - 6) / 100.0
        cma = ((index % 11) - 5) / 100.0
        lines.append(f"{day:%Y%m%d},0.10,0.02,{hml:.4f},{rmw:.4f},{cma:.4f},0.01")
    lines.append("Copyright 2024")
    with ZipFile(path, "w") as zf:
        zf.writestr("F-F_Research_Data_5_Factors_2x3_daily.csv", "\n".join(lines))
