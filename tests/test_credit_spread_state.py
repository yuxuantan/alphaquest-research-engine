from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.credit_spread_state import CreditSpreadStateEntry
from tools.build_es_credit_spread_features import build_features


def test_high_hy_oas_entry_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", hy_rank=0.82)
    entry = CreditSpreadStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_hy_oas_rebound_long",
            "hy_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-08 10:00")
    assert signal.report_fields["credit_driver_column"] == "hy_oas_rank_252"
    assert signal.report_fields["credit_observation_date"] == "2024-01-04"


def test_low_hy_oas_entry_emits_short(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", hy_rank=0.18)
    entry = CreditSpreadStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_hy_oas_complacency_short",
            "hy_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["credit_driver_column"] == "hy_oas_rank_252"


def test_hy_oas_widening_requires_change_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", change_rank=0.58)
    entry = CreditSpreadStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hy_oas_widening_riskoff_short",
            "change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-08 11:29", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-01-09", change_rank=0.8, name="widening.csv")
    entry = CreditSpreadStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hy_oas_widening_riskoff_short",
            "change_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-01-09 11:29", close=4801.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["credit_driver_column"] == "hy_oas_change_1d_rank_252"


def test_hy_ig_spread_widening_uses_diff_change_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", diff_change_rank=0.8)
    entry = CreditSpreadStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "hy_ig_spread_widening_short",
            "diff_change_rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 13:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["credit_driver_column"] == "hy_ig_oas_diff_change_1d_rank_252"


def test_credit_builder_uses_two_business_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=90, freq="B")
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        raw_path
    )
    hy_path = tmp_path / "hy.csv"
    ig_path = tmp_path / "ig.csv"
    pd.DataFrame(
        [{"DATE": f"{session:%Y-%m-%d}", "BAMLH0A0HYM2": 4.0 + i / 100.0} for i, session in enumerate(sessions)]
    ).to_csv(hy_path, index=False)
    pd.DataFrame(
        [{"DATE": f"{session:%Y-%m-%d}", "BAMLC0A0CM": 1.0 + i / 200.0} for i, session in enumerate(sessions)]
    ).to_csv(ig_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(
        raw_path,
        out_path,
        input_paths={"hy_oas": hy_path, "ig_oas": ig_path},
        rank_min_periods=3,
    )

    third = features.loc[features["session_date"] == sessions[2].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[70].strftime("%Y-%m-%d")].iloc[0]
    assert third["credit_asof_date"] == sessions[0].strftime("%Y-%m-%d")
    assert third["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert third["hy_oas"] == 4.0
    assert math.isfinite(late["hy_oas_rank_252"])
    assert math.isfinite(late["hy_oas_change_1d_rank_252"])
    assert math.isfinite(late["hy_ig_oas_diff_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    hy_rank: float = 0.7,
    change_rank: float = 0.7,
    change_max_rank: float = 0.3,
    diff_rank: float = 0.7,
    diff_change_rank: float = 0.7,
    name: str = "credit_features.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,credit_asof_date,observation_date,hy_oas,ig_oas,hy_ig_oas_diff,"
        "hy_oas_change_1d,hy_oas_change_5d,ig_oas_change_1d,hy_ig_oas_diff_change_1d,"
        "hy_oas_rank_252,ig_oas_rank_252,hy_ig_oas_diff_rank_252,hy_oas_change_1d_rank_252,"
        "hy_oas_change_5d_rank_252,ig_oas_change_1d_rank_252,hy_ig_oas_diff_change_1d_rank_252\n"
        f"{session_date},2024-01-04,2024-01-04,4.2,1.2,3.0,0.2,0.6,0.1,0.1,"
        f"{hy_rank},0.6,{diff_rank},{change_rank},{change_max_rank},0.6,{diff_change_rank}\n",
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
