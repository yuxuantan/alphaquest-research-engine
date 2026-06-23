from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.cboe_vxn_vix_dispersion import CboeVxnVixDispersionEntry
from tools.build_es_cboe_vxn_vix_dispersion_features import build_features


def test_high_vxn_vix_ratio_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", ratio_rank=0.82)
    entry = CboeVxnVixDispersionEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_vxn_vix_ratio_short",
            "ratio_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "availability_market": "NQ",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["vxn_vix_driver_column"] == "vxn_vix_ratio_rank_252"
    assert signal.report_fields["availability_rule"] == "latest Cboe VIX and VXN closes strictly before NQ session_date"


def test_low_vxn_vix_ratio_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", ratio_rank=0.18)
    entry = CboeVxnVixDispersionEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_vxn_vix_ratio_long",
            "ratio_rank_max": 0.35,
            "entry_time": "11:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 11:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"


def test_rising_ratio_requires_change_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", ratio_rank=0.5, ratio_change_rank=0.58)
    entry = CboeVxnVixDispersionEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_vxn_vix_ratio_short",
            "change_rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-01-04",
        ratio_rank=0.5,
        ratio_change_rank=0.8,
        name="rising.csv",
    )
    entry = CboeVxnVixDispersionEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_vxn_vix_ratio_short",
            "change_rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 10:29", close=4801.0)) is not None


def test_builder_uses_prior_vix_and_vxn_closes_not_same_session_close(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=70, freq="B")
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        raw_path
    )
    vix_path = tmp_path / "vix.csv"
    vxn_path = tmp_path / "vxn.csv"
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
    pd.DataFrame(
        [
            {
                "DATE": f"{session:%m/%d/%Y}",
                "OPEN": 25.0 + i,
                "HIGH": 25.0 + i,
                "LOW": 25.0 + i,
                "CLOSE": 25.0 + i,
            }
            for i, session in enumerate(sessions)
        ]
    ).to_csv(vxn_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path, vix_input=vix_path, vxn_input=vxn_path, rank_min_periods=3)

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[65].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["vix_close"] == 20.0
    assert second["vxn_close"] == 25.0
    assert math.isfinite(late["vxn_vix_ratio_rank_252"])
    assert math.isfinite(late["vxn_vix_ratio_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    ratio_rank: float,
    ratio_change_rank: float = 0.8,
    spread_rank: float = 0.8,
    name: str = "vxn_vix.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,vix_close,vxn_close,vxn_minus_vix,vxn_vix_ratio,"
        "vxn_minus_vix_change_1d,vxn_vix_ratio_change_1d,vxn_minus_vix_5d_mean,"
        "vxn_vix_ratio_5d_mean,vxn_minus_vix_rank_252,vxn_vix_ratio_rank_252,"
        "vxn_minus_vix_change_1d_rank_252,vxn_vix_ratio_change_1d_rank_252,"
        "vxn_minus_vix_5d_mean_rank_252,vxn_vix_ratio_5d_mean_rank_252\n"
        f"{session_date},2024-01-02,20,25,5,1.25,1,0.03,4,1.2,"
        f"{spread_rank},{ratio_rank},0.7,{ratio_change_rank},0.8,0.8\n",
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
