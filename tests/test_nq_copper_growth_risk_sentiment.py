from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_copper_growth_risk_sentiment import (
    NqCopperGrowthRiskSentimentEntry,
)
from tools.build_nq_copper_growth_risk_sentiment_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_copper_growth_risk_sentiment"]
        is NqCopperGrowthRiskSentimentEntry
    )


def test_copper_1d_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", copper_1d_rank=0.78)
    entry = NqCopperGrowthRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "copper_1d_strength_long",
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
    assert signal.report_fields["copper_driver_column"] == "copper_return_1d_rank_252"
    assert signal.report_fields["availability_rule"].startswith("latest copper/gold")


def test_copper_1d_weakness_emits_short_only_below_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", copper_1d_rank=0.46)
    entry = NqCopperGrowthRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "copper_1d_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", copper_1d_rank=0.22, name="weak.csv")
    entry = NqCopperGrowthRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "copper_1d_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 09:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_copper_gold_ratio_strength_uses_ratio_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", copper_gold_3d_rank=0.58)
    entry = NqCopperGrowthRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "copper_gold_ratio_strength_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-04",
        copper_gold_3d_rank=0.82,
        name="ratio.csv",
    )
    entry = NqCopperGrowthRiskSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "copper_gold_ratio_strength_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["copper_driver_column"] == (
        "copper_gold_ratio_return_3d_rank_252"
    )


def test_builder_uses_one_calendar_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-01-15", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "yahoo"
    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="D")
    _write_yahoo_csv(
        cache_dir / "yahoo_hg_f_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=3.80,
        volume=100000,
    )
    _write_yahoo_csv(
        cache_dir / "yahoo_gc_f_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=1900.0,
        volume=200000,
    )

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
        start_session="2024-01-15",
        yahoo_start_date="2023-08-01",
        yahoo_end_date="2024-05-31",
    )

    first = features.loc[features["session_date"] == "2024-01-15"].iloc[0]
    second = features.loc[features["session_date"] == "2024-01-16"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-14"
    assert second["observation_date"] == "2024-01-15"
    assert math.isfinite(later["copper_return_1d_rank_252"])
    assert math.isfinite(later["copper_gold_ratio_return_3d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    copper_1d_rank: float = 0.5,
    copper_3d_rank: float = 0.5,
    copper_gold_3d_rank: float = 0.5,
    name: str = "copper.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,availability_cutoff,observation_date,availability_lag_calendar_days,"
        "copper,gold,copper_volume,gold_volume,copper_gold_ratio,copper_return_1d,"
        "copper_return_3d,copper_return_5d,copper_gold_ratio_return_1d,"
        "copper_gold_ratio_return_3d,copper_gold_ratio_return_5d,copper_abs_return_1d,"
        "copper_volume_ratio_20,copper_return_1d_rank_252,copper_return_3d_rank_252,"
        "copper_return_5d_rank_252,copper_gold_ratio_return_1d_rank_252,"
        "copper_gold_ratio_return_3d_rank_252,copper_gold_ratio_return_5d_rank_252,"
        "copper_abs_return_1d_rank_252,copper_volume_ratio_20_rank_252\n"
        f"{session_date},2024-04-02,2024-04-02,1,4.0,2000,100000,200000,"
        f"0.002,0.01,0.02,0.03,0.01,0.02,0.03,0.01,1.2,{copper_1d_rank},"
        f"{copper_3d_rank},0.5,0.5,{copper_gold_3d_rank},0.5,0.5,0.5\n",
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
        price = start_price + index * 0.01
        lines.append(f"{day:%Y-%m-%d},{price},{price},{price},{price},{volume + index},{price}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
