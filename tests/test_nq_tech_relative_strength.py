from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.nq_tech_relative_strength import NqTechRelativeStrengthEntry
from tools.build_nq_tech_relative_strength_features import build_features


def test_tech_1d_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", one_day_rank=0.78)
    entry = NqTechRelativeStrengthEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_1d_strength_long",
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
    assert signal.report_fields["tech_driver_column"] == "xlk_minus_spy_1d_rank_252"
    assert signal.report_fields["availability_rule"].startswith("latest XLK and SPY daily close")


def test_tech_5d_weakness_emits_short_only_below_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", five_day_rank=0.46)
    entry = NqTechRelativeStrengthEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_5d_weakness_short",
            "rank_max": 0.35,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", five_day_rank=0.22, name="weak.csv")
    entry = NqTechRelativeStrengthEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_5d_weakness_short",
            "rank_max": 0.35,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_attention_strength_requires_volume_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", attention_rank=0.82, volume_rank=0.45)
    entry = NqTechRelativeStrengthEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_attention_strength_long",
            "rank_min": 0.70,
            "volume_rank_min": 0.70,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-04",
        attention_rank=0.82,
        volume_rank=0.88,
        name="attention.csv",
    )
    entry = NqTechRelativeStrengthEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_attention_strength_long",
            "rank_min": 0.70,
            "volume_rank_min": 0.70,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-04 13:29", close=18010.0)) is not None


def test_builder_uses_one_business_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        bars_path
    )

    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    xlk_path = tmp_path / "xlk.csv"
    spy_path = tmp_path / "spy.csv"
    _write_yahoo_csv(xlk_path, daily_dates, start_price=100.0, volume=1000000)
    _write_yahoo_csv(spy_path, daily_dates, start_price=400.0, volume=3000000)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        xlk_input=xlk_path,
        spy_input=spy_path,
        rank_min_periods=10,
    )

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    second = features.loc[features["session_date"] == "2024-01-03"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-01"
    assert second["observation_date"] == "2024-01-02"
    assert math.isfinite(later["xlk_minus_spy_1d_rank_252"])
    assert math.isfinite(later["xlk_volume_ratio_20_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    one_day_rank: float = 0.5,
    five_day_rank: float = 0.5,
    attention_rank: float = 0.5,
    volume_rank: float = 0.5,
    name: str = "tech.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,availability_cutoff,observation_date,availability_lag_business_days,"
        "xlk,spy,xlk_volume,xlk_return_1d,spy_return_1d,xlk_minus_spy_1d,"
        "xlk_return_5d,spy_return_5d,xlk_minus_spy_5d,xlk_volume_ratio_20,"
        "xlk_attention_pressure_1d,xlk_minus_spy_1d_rank_252,"
        "xlk_minus_spy_5d_rank_252,xlk_volume_ratio_20_rank_252,"
        "xlk_attention_pressure_1d_rank_252\n"
        f"{session_date},2024-04-02,2024-04-02,1,200,500,1000000,"
        f"0.01,0.002,0.008,0.02,0.005,0.015,1.2,0.0096,"
        f"{one_day_rank},{five_day_rank},{volume_rank},{attention_rank}\n",
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
    lines = ["Date,Open,High,Low,Close,Volume,Adj Close"]
    for index, day in enumerate(dates):
        price = start_price + index * 0.25
        lines.append(f"{day:%Y-%m-%d},{price},{price},{price},{price},{volume + index},{price}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
