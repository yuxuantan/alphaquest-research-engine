from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.cboe_skew_tail_risk import CboeSkewTailRiskEntry
from tools.build_es_cboe_skew_tail_risk_features import build_features


def test_high_skew_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", skew_rank=0.82)
    entry = CboeSkewTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_skew_short",
            "skew_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["skew_driver_column"] == "skew_close_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_low_skew_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", skew_rank=0.18)
    entry = CboeSkewTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_skew_long",
            "skew_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"


def test_rising_skew_requires_change_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", skew_rank=0.5, change_rank=0.58)
    entry = CboeSkewTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_skew_short",
            "skew_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 11:29", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-01-04", skew_rank=0.5, change_rank=0.8, name="rising.csv")
    entry = CboeSkewTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_skew_short",
            "skew_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 11:29", close=4801.0)) is not None


def test_builder_uses_prior_cboe_close_not_same_session_close(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=30, freq="B")
    bars = [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    skew_path = tmp_path / "skew.csv"
    pd.DataFrame(
        [{"DATE": f"{session:%m/%d/%Y}", "SKEW": 120.0 + i} for i, session in enumerate(sessions)]
    ).to_csv(skew_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(
        raw_path,
        out_path,
        skew_input=skew_path,
        rank_min_periods=3,
    )

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[25].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["skew_close"] == 120.0
    assert math.isfinite(late["skew_close_rank_252"])
    assert math.isfinite(late["skew_5d_mean_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    skew_rank: float,
    change_rank: float = 0.8,
    mean_rank: float = 0.8,
    name: str = "skew.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,skew_close,skew_change_1d,skew_change_5d,"
        "skew_5d_mean,skew_close_rank_252,skew_change_1d_rank_252,"
        "skew_change_5d_rank_252,skew_5d_mean_rank_252\n"
        f"{session_date},2024-01-02,142,2.5,4.0,139,{skew_rank},"
        f"{change_rank},0.7,{mean_rank}\n",
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
