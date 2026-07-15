from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.realized_jump_variation_premium import RealizedJumpVariationPremiumEntry
from tools.build_es_realized_jump_variation_features import build_features


def test_realized_jump_entry_emits_high_jump_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", jump_rank=0.82)
    entry = RealizedJumpVariationPremiumEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_jump_long",
            "jump_rank_column": "jump_var_rank_252",
            "jump_rank_min": 0.65,
            "jump_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["jump_driver_value"] == 0.82
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_realized_jump_entry_rejects_middle_rank_and_non_rth(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", jump_rank=0.5)
    entry = RealizedJumpVariationPremiumEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_jump_short",
            "jump_rank_min": 0.65,
            "jump_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5, is_rth=False)) is None


def test_realized_jump_entry_maps_signed_extremes(tmp_path):
    low_features = _feature_file(tmp_path, "2024-01-03", jump_rank=0.5, signed_rank=0.2)
    high_features = _feature_file(tmp_path, "2024-01-04", jump_rank=0.5, signed_rank=0.85)
    entry_low = RealizedJumpVariationPremiumEntry(
        {
            "feature_csv": str(low_features),
            "setup_mode": "two_sided_signed_jump_extreme",
            "jump_rank_min": 0.65,
            "jump_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )
    entry_high = RealizedJumpVariationPremiumEntry(
        {
            "feature_csv": str(high_features),
            "setup_mode": "two_sided_signed_jump_extreme",
            "jump_rank_min": 0.65,
            "jump_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    low_signal = entry_low.on_bar_close(_bar("2024-01-03 09:59", close=100.5))
    high_signal = entry_high.on_bar_close(_bar("2024-01-04 09:59", close=100.5))

    assert low_signal is not None
    assert low_signal.direction == "long"
    assert high_signal is not None
    assert high_signal.direction == "short"


def test_realized_jump_builder_shifts_features_one_session(tmp_path):
    rows = []
    for day, closes in [
        ("2024-01-02", [100.0, 99.0, 101.0, 100.5, 102.0]),
        ("2024-01-03", [100.5, 101.0, 101.5, 101.25, 101.0]),
        ("2024-01-04", [101.25, 100.0, 99.5, 100.75, 100.25]),
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
    assert math.isnan(first["prior_jump_variation"])
    assert math.isfinite(second["prior_jump_variation"])


def _feature_file(tmp_path, session_date: str, *, jump_rank: float, signed_rank: float | None = None):
    signed_rank = jump_rank if signed_rank is None else signed_rank
    path = tmp_path / f"jump_{session_date}.csv"
    path.write_text(
        "session_date,prior_close,prior_rth_return,prior_realized_variance,prior_bipower_variation,"
        "prior_jump_variation,prior_jump_share,prior_positive_jump_variation,prior_negative_jump_variation,"
        "prior_signed_jump_share,jump_variation_3d_mean,jump_share_3d_mean,jump_share_5d_mean,"
        "jump_variation_change_5d,jump_var_rank_252,jump_share_rank_252,jump_var3_rank_252,"
        "jump_share3_rank_252,negative_jump_rank_252,positive_jump_rank_252,signed_jump_rank_252,"
        "jump_change_rank_252\n"
        f"{session_date},100,0.01,0.0001,0.00008,0.00002,0.2,0.00001,0.00002,-0.33,"
        f"0.00002,0.2,0.2,0.00001,{jump_rank},{jump_rank},{jump_rank},{jump_rank},"
        f"{jump_rank},{jump_rank},{signed_rank},{jump_rank}\n",
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
