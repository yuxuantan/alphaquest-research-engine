from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_china_tech_risk_sentiment import (
    NqChinaTechRiskSentimentEntry,
)
from tools.build_nq_china_tech_risk_sentiment_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_china_tech_risk_sentiment"] is NqChinaTechRiskSentimentEntry


def test_cqqq_1d_relative_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", cqqq_1d_rank=0.78)
    entry = NqChinaTechRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "cqqq_1d_relative_strength_long",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["china_driver_column"] == (
        "cqqq_qqq_relative_return_1d_rank_252"
    )
    assert signal.report_fields["availability_rule"].startswith("latest CQQQ")


def test_cqqq_3d_relative_weakness_emits_short_only_below_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", cqqq_3d_rank=0.46)
    entry = NqChinaTechRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "cqqq_3d_relative_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", cqqq_3d_rank=0.22, name="weak.csv")
    entry = NqChinaTechRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "cqqq_3d_relative_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_fxi_strength_and_cqqq_volatility_use_expected_driver_columns(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", fxi_1d_rank=0.81, cqqq_abs_rank=0.74)
    entry = NqChinaTechRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "fxi_1d_relative_strength_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["china_driver_column"] == "fxi_qqq_relative_return_1d_rank_252"

    entry = NqChinaTechRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "cqqq_1d_volatility_short",
            "rank_min": 0.70,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["china_driver_column"] == "cqqq_abs_return_1d_rank_252"


def test_builder_uses_one_business_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "yahoo"
    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    _write_yahoo_csv(
        cache_dir / "yahoo_cqqq_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=60.0,
        volume=900000,
    )
    _write_yahoo_csv(
        cache_dir / "yahoo_fxi_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=30.0,
        volume=12000000,
    )
    _write_yahoo_csv(
        cache_dir / "yahoo_qqq_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=300.0,
        volume=30000000,
    )

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
        start_session="2024-01-02",
        yahoo_start_date="2023-08-01",
        yahoo_end_date="2024-05-31",
    )

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    second = features.loc[features["session_date"] == "2024-01-03"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-01"
    assert second["observation_date"] == "2024-01-02"
    assert math.isfinite(later["cqqq_qqq_relative_return_1d_rank_252"])
    assert math.isfinite(later["fxi_qqq_relative_return_3d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    cqqq_1d_rank: float = 0.5,
    cqqq_3d_rank: float = 0.5,
    fxi_1d_rank: float = 0.5,
    fxi_3d_rank: float = 0.5,
    cqqq_abs_rank: float = 0.5,
    name: str = "china.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,availability_cutoff,observation_date,availability_lag_business_days,"
        "cqqq,fxi,qqq,cqqq_volume,fxi_volume,qqq_volume,cqqq_return_1d,"
        "fxi_return_1d,qqq_return_1d,cqqq_qqq_relative_return_1d,"
        "fxi_qqq_relative_return_1d,cqqq_return_3d,fxi_return_3d,qqq_return_3d,"
        "cqqq_qqq_relative_return_3d,fxi_qqq_relative_return_3d,cqqq_return_5d,"
        "fxi_return_5d,qqq_return_5d,cqqq_qqq_relative_return_5d,"
        "fxi_qqq_relative_return_5d,cqqq_abs_return_1d,fxi_abs_return_1d,"
        "cqqq_volume_ratio_20,fxi_volume_ratio_20,cqqq_qqq_relative_return_1d_rank_252,"
        "cqqq_qqq_relative_return_3d_rank_252,cqqq_qqq_relative_return_5d_rank_252,"
        "fxi_qqq_relative_return_1d_rank_252,fxi_qqq_relative_return_3d_rank_252,"
        "fxi_qqq_relative_return_5d_rank_252,cqqq_abs_return_1d_rank_252,"
        "fxi_abs_return_1d_rank_252,cqqq_volume_ratio_20_rank_252,"
        "fxi_volume_ratio_20_rank_252\n"
        f"{session_date},2024-04-02,2024-04-02,1,60,30,300,900000,12000000,"
        f"30000000,0.01,0.012,0.003,0.007,0.009,0.02,0.021,0.005,0.015,"
        f"0.016,0.03,0.031,0.01,0.02,0.021,0.01,0.012,1.2,1.1,{cqqq_1d_rank},"
        f"{cqqq_3d_rank},0.5,{fxi_1d_rank},{fxi_3d_rank},0.5,{cqqq_abs_rank},"
        f"0.5,0.5,0.5\n",
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


def _write_yahoo_csv(path, dates, *, start_price: float, volume: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Date,Open,High,Low,Close,Volume,Adj Close"]
    for index, day in enumerate(dates):
        price = start_price + index * 0.25
        lines.append(f"{day:%Y-%m-%d},{price},{price},{price},{price},{volume + index},{price}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
