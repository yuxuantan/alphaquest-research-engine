from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.consumer_sentiment_state import ConsumerSentimentStateEntry
from tools.build_es_consumer_sentiment_features import build_features


def test_low_sentiment_entry_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", sentiment_rank=0.18)
    entry = ConsumerSentimentStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_sentiment_long",
            "sentiment_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-03-20 10:00")
    assert signal.report_fields["sentiment_driver_column"] == "consumer_sentiment_rank_120m"
    assert signal.report_fields["feature_session_date"] == "2024-03-20"


def test_high_sentiment_entry_emits_short(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", sentiment_rank=0.82)
    entry = ConsumerSentimentStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_sentiment_short",
            "sentiment_rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"


def test_rising_sentiment_requires_change_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", sentiment_rank=0.5, change_rank=0.55)
    entry = ConsumerSentimentStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_sentiment_long",
            "sentiment_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-03-20 11:29", close=4801.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-03-21",
        sentiment_rank=0.5,
        change_rank=0.80,
        name="rising.csv",
    )
    entry = ConsumerSentimentStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_sentiment_long",
            "sentiment_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-03-21 11:29", close=4801.0)) is not None


def test_builder_uses_monthly_observation_at_least_45_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-03-18", periods=80, freq="B")
    bars = [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(bars_path)

    sentiment_dates = pd.date_range("2020-01-01", "2024-06-01", freq="MS")
    sentiment_path = tmp_path / "umcsent.csv"
    pd.DataFrame(
        [
            {
                "observation_date": f"{session:%Y-%m-%d}",
                "UMCSENT": 70.0 + i,
            }
            for i, session in enumerate(sentiment_dates)
        ]
    ).to_csv(sentiment_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(
        bars_path,
        out_path,
        sentiment_input=sentiment_path,
        availability_lag_days=45,
        rank_min_periods=6,
    )

    first = features.loc[features["session_date"] == "2024-03-18"].iloc[0]
    late = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-02-01"
    assert first["consumer_sentiment"] == 119.0
    assert math.isfinite(late["consumer_sentiment_rank_120m"])
    assert math.isfinite(late["sentiment_change_3m_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    sentiment_rank: float,
    change_rank: float = 0.8,
    ma12_rank: float = 0.2,
    name: str = "sentiment.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,consumer_sentiment,sentiment_change_1m,"
        "sentiment_change_3m,sentiment_change_6m,sentiment_ma_3,sentiment_ma_12,"
        "consumer_sentiment_rank_120m,sentiment_change_1m_rank_120m,"
        "sentiment_change_3m_rank_120m,sentiment_change_6m_rank_120m,"
        "sentiment_ma_3_rank_120m,sentiment_ma_12_rank_120m\n"
        f"{session_date},2024-02-01,75,1.5,4.0,6.0,73,72,{sentiment_rank},"
        f"0.7,{change_rank},0.7,0.75,{ma12_rank}\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.5,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000,
        }
    )
