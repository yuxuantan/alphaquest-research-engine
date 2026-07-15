from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.cboe_vix_term_structure import CboeVixTermStructureEntry
from tools.build_es_cboe_vix_term_structure_features import build_features


def test_backwardation_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.82)
    entry = CboeVixTermStructureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "backwardation_short",
            "term_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["term_structure_driver_column"] == "vix_vix3m_ratio_rank_252"


def test_contango_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.18)
    entry = CboeVixTermStructureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "contango_long",
            "availability_market": "NQ",
            "term_rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert "NQ session_date" in signal.report_fields["availability_rule"]


def test_front_stress_requires_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.5, short_rank=0.58)
    entry = CboeVixTermStructureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "front_stress_short",
            "short_term_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 11:29", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-01-04", term_rank=0.5, short_rank=0.8, name="front.csv")
    entry = CboeVixTermStructureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "front_stress_short",
            "short_term_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 11:29", close=4801.0)) is not None


def test_builder_uses_prior_cboe_close_not_same_session_close(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=30, freq="B")
    bars = [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    input_paths = {}
    for key, base in {"vix": 20.0, "vix9d": 18.0, "vix3m": 24.0, "vix6m": 26.0}.items():
        path = tmp_path / f"{key}.csv"
        pd.DataFrame(
            [
                {
                    "DATE": f"{session:%m/%d/%Y}",
                    "OPEN": base + i,
                    "HIGH": base + i,
                    "LOW": base + i,
                    "CLOSE": base + i,
                }
                for i, session in enumerate(sessions)
            ]
        ).to_csv(path, index=False)
        input_paths[key] = path
    out_path = tmp_path / "features.csv"

    features = build_features(
        raw_path,
        out_path,
        input_paths=input_paths,
        rank_min_periods=3,
    )

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[25].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["vix_close"] == 20.0
    assert math.isfinite(late["vix_vix3m_ratio_rank_252"])
    assert math.isfinite(late["vix9d_vix_ratio_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    term_rank: float,
    short_rank: float = 0.8,
    curve_rank: float = 0.8,
    change_rank: float = 0.8,
    name: str = "vix_ts.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,vix_close,vix9d_close,vix3m_close,vix6m_close,"
        "vix_vix3m_ratio,vix9d_vix_ratio,vix3m_vix6m_ratio,vix_vix3m_spread,"
        "vix_vix3m_ratio_change_1d,vix_close_rank_252,vix_vix3m_ratio_rank_252,"
        "vix9d_vix_ratio_rank_252,vix3m_vix6m_ratio_rank_252,"
        "vix_vix3m_spread_rank_252,vix_vix3m_ratio_change_1d_rank_252\n"
        f"{session_date},2024-01-02,22,24,21,23,1.0476,1.0909,0.9130,1,0.04,"
        f"0.7,{term_rank},{short_rank},{curve_rank},0.7,{change_rank}\n",
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
