from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.nq_nikkei225_close_spillover import (
    NqNikkei225CloseSpilloverEntry,
)
from tools.build_nq_nikkei225_spillover_features import build_features


def test_nikkei_1d_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", one_day_rank=0.78)
    entry = NqNikkei225CloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "nikkei_1d_strength_long",
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
    assert signal.report_fields["nikkei_driver_column"] == "nikkei_return_1d_rank_252"
    assert "Tokyo cash close" in signal.report_fields["availability_rule"]


def test_nikkei_5d_weakness_emits_short_only_below_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", five_day_rank=0.46)
    entry = NqNikkei225CloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "nikkei_5d_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", five_day_rank=0.22, name="weak.csv")
    entry = NqNikkei225CloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "nikkei_5d_weakness_short",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_nikkei_volatility_short_uses_absolute_return_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", abs_one_day_rank=0.71)
    entry = NqNikkei225CloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "nikkei_1d_volatility_short",
            "rank_min": 0.70,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["nikkei_driver_column"] == "nikkei_abs_return_1d_rank_252"


def test_builder_uses_same_date_nikkei_close_when_available(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        bars_path
    )

    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    fred_path = tmp_path / "nikkei.csv"
    _write_fred_csv(fred_path, daily_dates, start_price=30000.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        fred_input=fred_path,
        rank_min_periods=10,
    )

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-02"
    assert int(first["nikkei_observation_lag_calendar_days"]) == 0
    assert math.isfinite(later["nikkei_return_1d_rank_252"])
    assert math.isfinite(later["nikkei_abs_return_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    one_day_rank: float = 0.5,
    five_day_rank: float = 0.5,
    abs_one_day_rank: float = 0.5,
    name: str = "nikkei.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,nikkei_observation_lag_calendar_days,"
        "nikkei225,nikkei_return_1d,nikkei_return_3d,nikkei_return_5d,"
        "nikkei_abs_return_1d,nikkei_return_1d_rank_252,nikkei_return_3d_rank_252,"
        "nikkei_return_5d_rank_252,nikkei_abs_return_1d_rank_252\n"
        f"{session_date},2024-04-03,0,35000,0.01,0.012,0.02,0.01,"
        f"{one_day_rank},0.5,{five_day_rank},{abs_one_day_rank}\n",
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


def _write_fred_csv(path, dates, *, start_price: float) -> None:
    lines = ["observation_date,NIKKEI225"]
    for index, day in enumerate(dates):
        price = start_price + index * 25.0
        lines.append(f"{day:%Y-%m-%d},{price}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
