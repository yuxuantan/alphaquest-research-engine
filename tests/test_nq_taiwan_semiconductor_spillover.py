from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_taiwan_semiconductor_spillover import (
    NqTaiwanSemiconductorSpilloverEntry,
)
from tools.build_nq_taiwan_semiconductor_spillover_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_taiwan_semiconductor_spillover"]
        is NqTaiwanSemiconductorSpilloverEntry
    )


def test_twii_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", twii_one_day_rank=0.72)
    entry = NqTaiwanSemiconductorSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "twii_1d_strength_long",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18100.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18105.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["taiwan_driver_column"] == "twii_return_1d_rank_252"
    assert "Taiwan cash trading closes" in signal.report_fields["availability_rule"]


def test_tsmc_relative_weakness_emits_short_only_below_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", tsmc_three_day_relative_rank=0.46)
    entry = NqTaiwanSemiconductorSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tsmc_3d_relative_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18105.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-04",
        tsmc_three_day_relative_rank=0.24,
        name="weak.csv",
    )
    entry = NqTaiwanSemiconductorSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tsmc_3d_relative_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18105.0))
    assert signal is not None
    assert signal.direction == "short"


def test_taiwan_volatility_short_uses_absolute_twii_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", twii_abs_rank=0.74)
    entry = NqTaiwanSemiconductorSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "taiwan_1d_volatility_short",
            "rank_min": 0.70,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:29", close=18105.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["taiwan_driver_column"] == "twii_abs_return_1d_rank_252"


def test_stale_taiwan_observation_is_blocked(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", twii_one_day_rank=0.8, lag_days=4)
    entry = NqTaiwanSemiconductorSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "twii_1d_strength_long",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
            "max_observation_lag_calendar_days": 3,
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 09:59", close=18105.0)) is None


def test_builder_uses_same_date_taiwan_close_when_available(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "cache"
    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    _write_yahoo_cache(
        cache_dir / "yahoo_twii_daily_2010-01-04_2026-06-12.csv",
        daily_dates,
        start_price=15000.0,
    )
    _write_yahoo_cache(
        cache_dir / "yahoo_2330.tw_daily_2010-01-04_2026-06-12.csv",
        daily_dates,
        start_price=500.0,
    )

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
    )

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-02"
    assert int(first["taiwan_observation_lag_calendar_days"]) == 0
    assert math.isfinite(later["twii_return_1d_rank_252"])
    assert math.isfinite(later["tsmc_tw_twii_relative_return_3d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    twii_one_day_rank: float = 0.5,
    twii_abs_rank: float = 0.5,
    tsmc_one_day_relative_rank: float = 0.5,
    tsmc_three_day_relative_rank: float = 0.5,
    lag_days: int = 0,
    name: str = "taiwan.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,taiwan_observation_lag_calendar_days,"
        "twii,tsmc_tw,twii_return_1d,twii_return_3d,twii_return_5d,"
        "twii_abs_return_1d,tsmc_tw_return_1d,tsmc_tw_return_3d,tsmc_tw_return_5d,"
        "tsmc_tw_twii_relative_return_1d,tsmc_tw_twii_relative_return_3d,"
        "tsmc_tw_twii_relative_return_5d,twii_return_1d_rank_252,"
        "twii_return_3d_rank_252,twii_return_5d_rank_252,twii_abs_return_1d_rank_252,"
        "tsmc_tw_twii_relative_return_1d_rank_252,"
        "tsmc_tw_twii_relative_return_3d_rank_252,"
        "tsmc_tw_twii_relative_return_5d_rank_252\n"
        f"{session_date},2024-04-03,{lag_days},20000,600,0.01,0.012,0.02,0.01,"
        f"0.015,0.018,0.021,0.005,0.006,0.001,{twii_one_day_rank},0.5,0.5,"
        f"{twii_abs_rank},{tsmc_one_day_relative_rank},{tsmc_three_day_relative_rank},0.5\n",
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


def _write_yahoo_cache(path, dates, *, start_price: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Date,Open,High,Low,Close,Volume,Adj Close"]
    for index, day in enumerate(dates):
        price = start_price + index * 2.0
        lines.append(f"{day:%Y-%m-%d},{price},{price},{price},{price},1000,{price}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
