from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.vvix_tail_risk import VvixTailRiskEntry
from tools.build_es_vvix_tail_risk_features import build_features


def test_high_vvix_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vvix_rank=0.82)
    entry = VvixTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_vvix_short",
            "tail_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["tail_driver_column"] == "vvix_close_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_low_vvix_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vvix_rank=0.18)
    entry = VvixTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_vvix_long",
            "tail_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"


def test_rising_vvix_requires_change_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vvix_rank=0.5, change_rank=0.58)
    entry = VvixTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_vvix_short",
            "tail_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 11:29", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-01-04", vvix_rank=0.5, change_rank=0.8, name="rising.csv")
    entry = VvixTailRiskEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_vvix_short",
            "tail_change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 11:29", close=4801.0)) is not None


def test_builder_uses_prior_cboe_close_not_same_session_close(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=30, freq="B")
    bars = [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    vvix_path = tmp_path / "vvix.csv"
    vix_path = tmp_path / "vix.csv"
    pd.DataFrame(
        [{"DATE": f"{session:%m/%d/%Y}", "VVIX": 80.0 + i} for i, session in enumerate(sessions)]
    ).to_csv(vvix_path, index=False)
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
    ).to_csv(vix_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(
        raw_path,
        out_path,
        vvix_input=vvix_path,
        vix_input=vix_path,
        rank_min_periods=3,
    )

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[25].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["vvix_close"] == 80.0
    assert math.isfinite(late["vvix_close_rank_252"])
    assert math.isfinite(late["vvix_vix_ratio_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    vvix_rank: float,
    change_rank: float = 0.8,
    ratio_rank: float = 0.8,
    name: str = "vvix.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,vvix_close,vix_close,vvix_vix_ratio,vvix_change_1d,"
        "vvix_change_5d,vix_change_1d,vvix_close_rank_252,vix_close_rank_252,"
        "vvix_vix_ratio_rank_252,vvix_change_1d_rank_252,vvix_change_5d_rank_252,"
        "vix_change_1d_rank_252\n"
        f"{session_date},2024-01-02,92,18,5.111,2.5,4.0,1.0,{vvix_rank},0.6,"
        f"{ratio_rank},{change_rank},0.7,0.7\n",
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
