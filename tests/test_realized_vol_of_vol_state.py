from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.realized_vol_of_vol_state import RealizedVolOfVolStateEntry
from tools.build_es_realized_vol_of_vol_features import build_features


def test_realized_vol_of_vol_entry_emits_high_rank_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank=0.86, value=0.45)
    entry = RealizedVolOfVolStateEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_long",
            "value_column": "prior_intraday_vov_1d",
            "rank_column": "intraday_vov1_rank_252",
            "vov_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["vov_rank"] == 0.86
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_realized_vol_of_vol_entry_emits_high_rank_short(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank=0.82, value=0.45)
    entry = RealizedVolOfVolStateEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_short",
            "vov_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "short"


def test_realized_vol_of_vol_entry_rejects_middle_rank_and_non_rth(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank=0.5, value=0.45)
    entry = RealizedVolOfVolStateEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "two_sided_high_long",
            "vov_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5, is_rth=False)) is None


def test_realized_vol_of_vol_builder_shifts_features_one_session(tmp_path):
    rows = []
    for day, closes in [
        ("2024-01-02", [100.0, 99.0, 101.0, 100.5, 101.5, 99.5, 100.75, 101.25, 99.75, 100.25, 100.5]),
        ("2024-01-03", [100.5, 101.0, 101.5, 101.25, 101.75, 102.25, 101.25, 100.75, 101.5, 102.0, 101.75]),
        ("2024-01-04", [101.25, 100.0, 99.5, 100.75, 99.75, 99.25, 100.0, 100.5, 99.5, 98.75, 99.25]),
    ]:
        for minute, close in enumerate(closes):
            rows.append(
                {
                    "timestamp": pd.Timestamp(f"{day} 09:{30 + minute:02d}"),
                    "open": 100.0 if minute == 0 else closes[minute - 1],
                    "close": close,
                }
            )
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(rows).to_parquet(raw_path)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path)

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    second = features.loc[features["session_date"] == "2024-01-03"].iloc[0]
    assert math.isnan(first["prior_intraday_vov_1d"])
    assert math.isfinite(second["prior_intraday_vov_1d"])
    assert math.isfinite(second["prior_realized_quarticity_1d"])


def _feature_file(tmp_path, session_date: str, *, rank: float, value: float):
    path = tmp_path / "vov.csv"
    path.write_text(
        "session_date,prior_rth_return,prior_realized_variance,prior_realized_volatility,"
        "prior_realized_quarticity_1d,prior_quarticity_ratio_1d,prior_intraday_vov_1d,"
        "intraday_vov_5d_mean,intraday_vov_20d_mean,quarticity_ratio_5d_mean,"
        "quarticity_ratio_20d_mean,intraday_vov1_rank_252,quarticity_ratio1_rank_252,"
        "intraday_vov5_rank_252,intraday_vov20_rank_252,quarticity_ratio20_rank_252\n"
        f"{session_date},0.01,0.0004,0.02,0.000001,1.5,{value},{value},{value},1.4,1.5,"
        f"{rank},{rank},{rank},{rank},{rank}\n",
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
