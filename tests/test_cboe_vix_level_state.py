from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.cboe_vix_level_state import CboeVixLevelStateEntry
from tools.build_es_cboe_vix_level_features import build_features


def test_high_vix_entry_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vix_rank=0.82)
    entry = CboeVixLevelStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_vix_rebound_long",
            "vix_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["vix_driver_column"] == "vix_close_rank_252"


def test_low_vix_entry_emits_short(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vix_rank=0.18)
    entry = CboeVixLevelStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_vix_complacency_short",
            "availability_market": "NQ",
            "vix_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert "NQ session_date" in signal.report_fields["availability_rule"]


def test_vix_spike_requires_change_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vix_rank=0.5, change_rank=0.58)
    entry = CboeVixLevelStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "vix_spike_riskoff_short",
            "change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 11:29", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-01-04", vix_rank=0.5, change_rank=0.8, name="spike.csv")
    entry = CboeVixLevelStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "vix_spike_riskoff_short",
            "change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 11:29", close=4801.0)) is not None


def test_builder_uses_prior_vix_close_not_same_session_close(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=70, freq="B")
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        raw_path
    )
    vix_path = tmp_path / "vix.csv"
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

    features = build_features(raw_path, out_path, vix_input=vix_path, rank_min_periods=3)

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[65].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["vix_close"] == 20.0
    assert math.isfinite(late["vix_close_rank_252"])
    assert math.isfinite(late["vix_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    vix_rank: float,
    change_rank: float = 0.8,
    change_5d_rank: float = 0.8,
    mean_rank: float = 0.8,
    name: str = "vix_level.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,vix_close,vix_change_1d,vix_change_5d,vix_5d_mean,"
        "vix_close_rank_252,vix_change_1d_rank_252,vix_change_5d_rank_252,vix_5d_mean_rank_252\n"
        f"{session_date},2024-01-02,22,1,3,21,{vix_rank},{change_rank},{change_5d_rank},{mean_rank}\n",
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
