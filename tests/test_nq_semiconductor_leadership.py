from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_semiconductor_leadership import (
    NqSemiconductorLeadershipEntry,
)
from tools.build_nq_semiconductor_leadership_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_semiconductor_leadership"] is NqSemiconductorLeadershipEntry


def test_smh_1d_leadership_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", smh_1d_rank=0.78)
    entry = NqSemiconductorLeadershipEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "smh_1d_leadership_long",
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
    assert signal.report_fields["semiconductor_driver_column"] == (
        "smh_qqq_relative_return_1d_rank_252"
    )
    assert signal.report_fields["availability_rule"].startswith("latest SMH")


def test_smh_1d_nonleadership_emits_short_only_below_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", smh_1d_rank=0.46)
    entry = NqSemiconductorLeadershipEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "smh_1d_nonleadership_short",
            "rank_max": 0.35,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", smh_1d_rank=0.22, name="weak.csv")
    entry = NqSemiconductorLeadershipEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "smh_1d_nonleadership_short",
            "rank_max": 0.35,
            "entry_time": "10:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 09:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_soxx_3d_leadership_uses_soxx_ratio_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", soxx_3d_rank=0.58)
    entry = NqSemiconductorLeadershipEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "soxx_3d_leadership_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-04",
        soxx_3d_rank=0.82,
        name="soxx.csv",
    )
    entry = NqSemiconductorLeadershipEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "soxx_3d_leadership_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["semiconductor_driver_column"] == (
        "soxx_qqq_relative_return_3d_rank_252"
    )


def test_builder_uses_one_business_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "yahoo"
    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    _write_yahoo_csv(
        cache_dir / "yahoo_smh_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=100.0,
        volume=1000000,
    )
    _write_yahoo_csv(
        cache_dir / "yahoo_soxx_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=400.0,
        volume=800000,
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
    assert math.isfinite(later["smh_qqq_relative_return_1d_rank_252"])
    assert math.isfinite(later["soxx_qqq_relative_return_3d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    smh_1d_rank: float = 0.5,
    smh_3d_rank: float = 0.5,
    soxx_3d_rank: float = 0.5,
    name: str = "semis.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,availability_cutoff,observation_date,availability_lag_business_days,"
        "smh,soxx,qqq,smh_volume,soxx_volume,qqq_volume,smh_return_1d,"
        "soxx_return_1d,qqq_return_1d,smh_qqq_relative_return_1d,"
        "soxx_qqq_relative_return_1d,smh_return_3d,soxx_return_3d,qqq_return_3d,"
        "smh_qqq_relative_return_3d,soxx_qqq_relative_return_3d,smh_return_5d,"
        "soxx_return_5d,qqq_return_5d,smh_qqq_relative_return_5d,"
        "soxx_qqq_relative_return_5d,smh_volume_ratio_20,soxx_volume_ratio_20,"
        "smh_qqq_relative_return_1d_rank_252,smh_qqq_relative_return_3d_rank_252,"
        "smh_qqq_relative_return_5d_rank_252,soxx_qqq_relative_return_1d_rank_252,"
        "soxx_qqq_relative_return_3d_rank_252,soxx_qqq_relative_return_5d_rank_252,"
        "smh_volume_ratio_20_rank_252,soxx_volume_ratio_20_rank_252\n"
        f"{session_date},2024-04-02,2024-04-02,1,100,400,300,1000000,800000,"
        f"30000000,0.01,0.012,0.003,0.007,0.009,0.02,0.021,0.005,0.015,"
        f"0.016,0.03,0.031,0.01,0.02,0.021,1.2,1.1,{smh_1d_rank},{smh_3d_rank},"
        f"0.5,0.5,{soxx_3d_rank},0.5,0.5,0.5\n",
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
