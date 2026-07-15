from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.realized_semivariance_asymmetry import RealizedSemivarianceAsymmetryEntry
from tools.build_es_realized_semivariance_features import build_features


def test_realized_semivariance_entry_emits_high_rank_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank=0.86, value=0.0002)
    entry = RealizedSemivarianceAsymmetryEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_long",
            "value_column": "prior_downside_semivariance_1d",
            "rank_column": "downside1_rank_252",
            "semivar_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["semivar_rank"] == 0.86
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_realized_semivariance_entry_emits_high_rank_short(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank=0.82, value=0.0002)
    entry = RealizedSemivarianceAsymmetryEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_short",
            "semivar_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "short"


def test_realized_semivariance_entry_rejects_middle_rank_and_non_rth(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank=0.5, value=0.0002)
    entry = RealizedSemivarianceAsymmetryEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "two_sided_bad_good",
            "semivar_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5, is_rth=False)) is None


def test_realized_semivariance_builder_shifts_features_one_session(tmp_path):
    rows = []
    for day, closes in [
        ("2024-01-02", [100.0, 99.0, 101.0, 100.5]),
        ("2024-01-03", [100.5, 101.0, 101.5, 101.25]),
        ("2024-01-04", [101.25, 100.0, 99.5, 100.75]),
    ]:
        for minute, close in enumerate(closes):
            rows.append(
                {
                    "timestamp": pd.Timestamp(f"{day} 09:{30 + minute:02d}"),
                    "open": 100.0 if minute == 0 else closes[minute - 1],
                    "high": close + 0.25,
                    "low": close - 0.25,
                    "close": close,
                }
            )
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(rows).to_parquet(raw_path)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path)

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    second = features.loc[features["session_date"] == "2024-01-03"].iloc[0]
    assert math.isnan(first["prior_downside_semivariance_1d"])
    assert math.isfinite(second["prior_downside_semivariance_1d"])
    assert math.isfinite(second["prior_upside_semivariance_1d"])


def _feature_file(tmp_path, session_date: str, *, rank: float, value: float):
    path = tmp_path / "semivar.csv"
    path.write_text(
        "session_date,prior_close,prior_rth_return,prior_realized_variance,"
        "prior_downside_semivariance_1d,prior_upside_semivariance_1d,prior_downside_share_1d,"
        "prior_upside_share_1d,prior_semivariance_balance_1d,downside_semivariance_3d_mean,"
        "upside_semivariance_3d_mean,semivariance_balance_5d_mean,downside1_rank_252,"
        "upside1_rank_252,downside_share1_rank_252,semivar_balance1_rank_252,downside3_rank_252,"
        "upside3_rank_252,semivar_balance5_rank_252\n"
        f"{session_date},100,0.01,0.0004,{value},{value / 2},0.67,0.33,0.34,"
        f"{value},{value / 2},0.34,{rank},{rank},{rank},{rank},{rank},{rank},{rank}\n",
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
            "open": 100.0,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000,
        }
    )
