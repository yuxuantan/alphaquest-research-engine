from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.realized_skewness_reversal import RealizedSkewnessReversalEntry
from tools.build_es_lagged_realized_skewness_features import build_features


def test_realized_skewness_entry_emits_low_rank_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", skew_rank=0.2, skew_value=-1.1)
    entry = RealizedSkewnessReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "low_long",
            "skew_value_column": "prior_realized_skew_1d",
            "skew_rank_column": "skew1_rank_252",
            "skew_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["skew_rank"] == 0.2
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_realized_skewness_entry_emits_high_rank_short(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", skew_rank=0.82, skew_value=1.4)
    entry = RealizedSkewnessReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_short",
            "skew_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "short"


def test_realized_skewness_entry_rejects_middle_rank_and_non_rth(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", skew_rank=0.5, skew_value=0.0)
    entry = RealizedSkewnessReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "two_sided_extreme",
            "skew_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5, is_rth=False)) is None


def test_realized_skewness_builder_shifts_features_one_session(tmp_path):
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
    assert math.isnan(first["prior_realized_skew_1d"])
    assert math.isfinite(second["prior_realized_skew_1d"])


def _feature_file(tmp_path, session_date: str, *, skew_rank: float, skew_value: float):
    path = tmp_path / "skew.csv"
    path.write_text(
        "session_date,prior_close,prior_rth_return,prior_realized_variance,prior_realized_skew_1d,"
        "prior_realized_kurtosis_1d,realized_skew_3d_mean,realized_skew_5d_mean,realized_skew_10d_mean,"
        "realized_skew_5d_min,realized_skew_5d_max,skew1_rank_252,skew3_rank_252,skew5_rank_252,skew10_rank_252\n"
        f"{session_date},100,0.01,0.0001,{skew_value},3.0,{skew_value},{skew_value},{skew_value},"
        f"{skew_value},{skew_value},{skew_rank},{skew_rank},{skew_rank},{skew_rank}\n",
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
