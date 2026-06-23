from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.cboe_implied_correlation import CboeImpliedCorrelationEntry
from tools.build_es_cboe_implied_correlation_features import build_features


def test_high_cor3m_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", cor_rank=0.82)
    entry = CboeImpliedCorrelationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_cor3m_short",
            "correlation_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["correlation_driver_column"] == "cor3m_close_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_low_cor3m_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", cor_rank=0.18)
    entry = CboeImpliedCorrelationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_cor3m_long",
            "correlation_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"


def test_availability_rule_can_label_nq_sessions(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", cor_rank=0.18)
    entry = CboeImpliedCorrelationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_cor3m_long",
            "correlation_rank_max": 0.35,
            "availability_market": "NQ",
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0))

    assert signal is not None
    assert "NQ session_date" in signal.report_fields["availability_rule"]


def test_rising_cor3m_requires_change_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", cor_rank=0.5, change_rank=0.58)
    entry = CboeImpliedCorrelationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_cor3m_short",
            "correlation_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 11:29", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-01-04", cor_rank=0.5, change_rank=0.8, name="rising.csv")
    entry = CboeImpliedCorrelationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_cor3m_short",
            "correlation_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 11:29", close=4801.0)) is not None


def test_builder_uses_prior_cboe_close_not_same_session_close(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=30, freq="B")
    bars = [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    cor1m_path = tmp_path / "cor1m.csv"
    cor3m_path = tmp_path / "cor3m.csv"
    pd.DataFrame(
        [
            {
                "DATE": f"{session:%m/%d/%Y}",
                "OPEN": 20.0 + i,
                "HIGH": 20.0 + i,
                "LOW": 20.0 + i,
                "CLOSE": 20.0 + i,
            }
            for i, session in enumerate(sessions)
        ]
    ).to_csv(cor1m_path, index=False)
    pd.DataFrame(
        [
            {
                "DATE": f"{session:%m/%d/%Y}",
                "OPEN": 30.0 + i,
                "HIGH": 30.0 + i,
                "LOW": 30.0 + i,
                "CLOSE": 30.0 + i,
            }
            for i, session in enumerate(sessions)
        ]
    ).to_csv(cor3m_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(
        raw_path,
        out_path,
        cor1m_input=cor1m_path,
        cor3m_input=cor3m_path,
        rank_min_periods=3,
    )

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[25].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["cor3m_close"] == 30.0
    assert math.isfinite(late["cor3m_close_rank_252"])
    assert math.isfinite(late["cor1m_minus_cor3m_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    cor_rank: float,
    change_rank: float = 0.8,
    spread_rank: float = 0.8,
    name: str = "correlation.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,cor1m_close,cor3m_close,cor3m_change_1d,"
        "cor3m_change_5d,cor1m_minus_cor3m,cor1m_close_rank_252,cor3m_close_rank_252,"
        "cor3m_change_1d_rank_252,cor3m_change_5d_rank_252,cor1m_minus_cor3m_rank_252\n"
        f"{session_date},2024-01-02,28,32,2.5,4.0,-4,0.7,{cor_rank},"
        f"{change_rank},0.7,{spread_rank}\n",
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
