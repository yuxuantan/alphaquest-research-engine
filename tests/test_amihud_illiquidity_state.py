from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.amihud_illiquidity_state import AmihudIlliquidityStateEntry
from tools.build_es_amihud_illiquidity_features import build_features


def test_amihud_high_rank_long_signal_uses_completed_bar(tmp_path):
    feature_csv = tmp_path / "amihud.csv"
    feature_csv.write_text(
        "session_date,prior_amihud_illiq_1d,illiq1_rank_252,prior_close,prior_rth_return,prior_abs_rth_return,prior_dollar_volume,prior_price_impact_per_billion\n"
        "2026-01-05,0.00000000001,0.82,5000,0.01,0.01,1000000000,0.01\n",
        encoding="utf-8",
    )
    entry = AmihudIlliquidityStateEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "illiq_rank_threshold": 0.25,
        }
    )
    signal = entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00"), 0)
    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["illiq_rank"] == 0.82
    assert signal.metadata["flatten_time"] == "15:55:00"


def test_amihud_high_rank_short_and_middle_rank_rejected(tmp_path):
    feature_csv = tmp_path / "amihud.csv"
    feature_csv.write_text(
        "session_date,prior_amihud_illiq_1d,illiq1_rank_252,prior_close,prior_rth_return,prior_abs_rth_return,prior_dollar_volume,prior_price_impact_per_billion\n"
        "2026-01-05,0.00000000001,0.80,5000,0.01,0.01,1000000000,0.01\n"
        "2026-01-06,0.00000000002,0.50,5010,0.002,0.002,1200000000,0.02\n",
        encoding="utf-8",
    )
    entry = AmihudIlliquidityStateEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "illiq_rank_threshold": 0.25,
        }
    )
    signal = entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00"), 0)
    assert signal is not None
    assert signal.direction == "short"
    assert entry.on_bar_close(_bar("2026-01-06 09:59:00-05:00"), 0) is None


def test_amihud_ignores_non_rth_and_duplicate_day_signal(tmp_path):
    feature_csv = tmp_path / "amihud.csv"
    feature_csv.write_text(
        "session_date,prior_amihud_illiq_1d,illiq1_rank_252,prior_close,prior_rth_return,prior_abs_rth_return,prior_dollar_volume,prior_price_impact_per_billion\n"
        "2026-01-05,0.00000000001,0.82,5000,0.01,0.01,1000000000,0.01\n",
        encoding="utf-8",
    )
    entry = AmihudIlliquidityStateEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "illiq_rank_threshold": 0.25,
        }
    )
    assert entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00", is_rth=False), 0) is None
    assert entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00"), 0) is not None
    assert entry.on_bar_close(_bar("2026-01-05 10:00:00-05:00"), 0) is None


def test_amihud_feature_builder_shifts_one_completed_session(tmp_path):
    source = tmp_path / "bars.parquet"
    output = tmp_path / "features.csv"
    rows = []
    for day, open_price, closes, volumes in [
        ("2026-01-05", 100.0, [101.0, 102.0], [10, 20]),
        ("2026-01-06", 102.0, [101.0, 100.0], [30, 40]),
    ]:
        for idx, close in enumerate(closes):
            rows.append(
                {
                    "timestamp": pd.Timestamp(f"{day} 09:{30 + idx}:00"),
                    "open": open_price if idx == 0 else closes[idx - 1],
                    "high": max(open_price, close),
                    "low": min(open_price, close),
                    "close": close,
                    "volume": volumes[idx],
                }
            )
    pd.DataFrame(rows).to_parquet(source)
    features = build_features(source, output, point_value=20.0)
    second = features.iloc[1]
    assert pd.isna(features.iloc[0]["prior_amihud_illiq_1d"])
    assert second["prior_amihud_illiq_1d"] > 0
    assert second["prior_dollar_volume"] == 61_000.0


def _bar(timestamp: str, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": 5000.0,
            "high": 5001.0,
            "low": 4999.0,
            "close": 5000.5,
        }
    )
