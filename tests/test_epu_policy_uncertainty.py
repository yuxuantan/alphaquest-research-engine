from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.epu_policy_uncertainty import EpuPolicyUncertaintyEntry
from tools.build_es_epu_policy_uncertainty_features import build_features


def test_high_epu_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-02-05", epu_rank=0.82)
    entry = EpuPolicyUncertaintyEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_epu_short",
            "epu_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-02-05 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-02-05 10:00")
    assert signal.report_fields["epu_driver_column"] == "epu_index_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-02-05"


def test_low_epu_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-02-05", epu_rank=0.18)
    entry = EpuPolicyUncertaintyEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_epu_long",
            "epu_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-02-05 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"


def test_persistent_high_epu_requires_level_and_change(tmp_path):
    features = _feature_file(
        tmp_path,
        "2024-02-05",
        epu_rank=0.82,
        change_rank=0.70,
        ma20_rank=0.40,
    )
    entry = EpuPolicyUncertaintyEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "persistent_high_epu_short",
            "epu_ma_rank_min": 0.60,
            "epu_change_rank_min": 0.60,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-02-05 13:29", close=4801.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-02-06",
        epu_rank=0.82,
        change_rank=0.70,
        ma20_rank=0.75,
        name="persistent.csv",
    )
    entry = EpuPolicyUncertaintyEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "persistent_high_epu_short",
            "epu_ma_rank_min": 0.60,
            "epu_change_rank_min": 0.60,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-02-06 13:29", close=4801.0)) is not None


def test_high_epu_ma_entry_uses_smoothed_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-02-05", epu_rank=0.40, ma20_rank=0.80)
    entry = EpuPolicyUncertaintyEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_epu_ma_short",
            "epu_ma_rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-02-05 13:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["epu_driver_column"] == "epu_ma_20_rank_252"


def test_builder_uses_observation_at_least_30_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-02-01", periods=75, freq="B")
    bars = [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    epu_path = tmp_path / "epu.csv"
    epu_dates = pd.date_range("2024-01-01", "2024-04-30", freq="D")
    pd.DataFrame(
        [
            {
                "day": session.day,
                "month": session.month,
                "year": session.year,
                "daily_policy_index": 100.0 + i,
            }
            for i, session in enumerate(epu_dates)
        ]
    ).to_csv(epu_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(
        raw_path,
        out_path,
        epu_input=epu_path,
        availability_lag_days=30,
        rank_min_periods=3,
    )

    first = features.loc[features["session_date"] == "2024-02-01"].iloc[0]
    late = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-02"
    assert first["epu_index"] == 101.0
    assert math.isfinite(late["epu_index_rank_252"])
    assert math.isfinite(late["epu_change_5d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    epu_rank: float,
    change_rank: float = 0.8,
    ma20_rank: float = 0.8,
    name: str = "epu.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,epu_index,epu_change_1d,epu_change_5d,"
        "epu_change_20d,epu_ma_5,epu_ma_20,epu_index_rank_252,"
        "epu_change_1d_rank_252,epu_change_5d_rank_252,epu_change_20d_rank_252,"
        "epu_ma_5_rank_252,epu_ma_20_rank_252\n"
        f"{session_date},2024-01-02,180,12,30,40,160,155,{epu_rank},0.7,"
        f"{change_rank},0.7,0.75,{ma20_rank}\n",
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
