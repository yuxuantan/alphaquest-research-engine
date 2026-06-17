from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.variance_risk_premium_intraday import VarianceRiskPremiumIntradayEntry
from tools.build_es_variance_risk_premium_features import build_features


def test_high_vrp_entry_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vrp_rank=0.82)
    entry = VarianceRiskPremiumIntradayEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_vrp_long",
            "vrp_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["vrp_driver_column"] == "vrp_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_low_vrp_entry_emits_short(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vrp_rank=0.18)
    entry = VarianceRiskPremiumIntradayEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_vrp_short",
            "vrp_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"


def test_high_vrp_low_realized_requires_both_conditions(tmp_path):
    high_realized = _feature_file(
        tmp_path,
        "2024-01-03",
        vrp_rank=0.82,
        realized_var_rank=0.8,
        name="high_realized.csv",
    )
    entry = VarianceRiskPremiumIntradayEntry(
        {
            "feature_csv": str(high_realized),
            "setup_mode": "high_vrp_low_realized_long",
            "vrp_rank_min": 0.65,
            "realized_var_rank_max": 0.5,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0)) is None

    low_realized = _feature_file(
        tmp_path,
        "2024-01-04",
        vrp_rank=0.82,
        realized_var_rank=0.3,
        name="low_realized.csv",
    )
    entry = VarianceRiskPremiumIntradayEntry(
        {
            "feature_csv": str(low_realized),
            "setup_mode": "high_vrp_low_realized_long",
            "vrp_rank_min": 0.65,
            "realized_var_rank_max": 0.5,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 09:59", close=4801.0)) is not None


def test_vrp_entry_rejects_middle_rank_and_non_rth(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", vrp_rank=0.5)
    entry = VarianceRiskPremiumIntradayEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_vrp_long",
            "vrp_rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0, is_rth=False)) is None


def test_vrp_builder_uses_prior_vix_close_and_prior_realized_variance(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=30, freq="B")
    bars = []
    vix_rows = []
    for i, session in enumerate(sessions):
        day = session.strftime("%Y-%m-%d")
        first_open = 100.0 + i
        closes = [first_open + 0.5, first_open + 1.0, first_open + 0.75]
        for minute, close in enumerate(closes):
            bars.append(
                {
                    "timestamp": pd.Timestamp(f"{day} 09:{30 + minute:02d}"),
                    "open": first_open if minute == 0 else closes[minute - 1],
                    "close": close,
                }
            )
        vix_rows.append(
            {
                "DATE": session.strftime("%m/%d/%Y"),
                "OPEN": 20.0 + i,
                "HIGH": 20.0 + i,
                "LOW": 20.0 + i,
                "CLOSE": 20.0 + i,
            }
        )
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    vix_path = tmp_path / "vix.csv"
    pd.DataFrame(vix_rows).to_csv(vix_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path, vix_input=vix_path, rank_min_periods=3)

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[25].strftime("%Y-%m-%d")].iloc[0]
    assert second["prior_vix_close"] == 20.0
    assert math.isfinite(late["realized_var_20_ann"])
    assert math.isfinite(late["vrp_20"])
    assert math.isfinite(late["vrp_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    vrp_rank: float,
    realized_var_rank: float = 0.3,
    ratio_rank: float = 0.8,
    change_rank: float = 0.8,
    name: str = "vrp.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,prior_close,prior_rth_return,prior_vix_close,prior_vix_variance_ann,"
        "realized_var_5_ann,realized_var_20_ann,vrp_20,vrp_ratio_20,vrp_change_5,"
        "vix_change_5,vrp_rank_252,vrp_ratio_rank_252,vix_rank_252,realized_var20_rank_252,"
        "vrp_change_rank_252\n"
        f"{session_date},4800,0.001,20,0.04,0.02,0.025,0.015,1.6,0.004,1.0,"
        f"{vrp_rank},{ratio_rank},0.6,{realized_var_rank},{change_rank}\n",
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
