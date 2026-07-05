from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.max_daily_return_lottery_reversal import (
    MaxDailyReturnLotteryReversalEntry,
)
from propstack.strategy_modules.entry import ENTRY_MODULES
from tools.build_nq_max_daily_return_features import build_features


def test_max_daily_return_entry_emits_high_rank_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", max_rank=0.88, max_value=0.025)
    entry = MaxDailyReturnLotteryReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_short",
            "max_value_column": "prior_max_return_20d",
            "max_rank_column": "max_return_20d_rank_252",
            "max_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["max_rank"] == 0.88
    assert signal.report_fields["feature_session_date"] == "2024-01-03"


def test_max_daily_return_entry_emits_low_rank_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", max_rank=0.18, max_value=0.004)
    entry = MaxDailyReturnLotteryReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "low_long",
            "max_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5))

    assert signal is not None
    assert signal.direction == "long"


def test_max_daily_return_entry_rejects_middle_rank_non_rth_and_duplicate_signal(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", max_rank=0.5, max_value=0.011)
    entry = MaxDailyReturnLotteryReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "two_sided_extreme",
            "max_rank_threshold": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=100.5, is_rth=False)) is None

    features = _feature_file(tmp_path, "2024-01-04", max_rank=0.9, max_value=0.025)
    entry = MaxDailyReturnLotteryReversalEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 09:59", close=100.5)) is not None
    assert entry.on_bar_close(_bar("2024-01-04 09:59", close=100.5)) is None


def test_max_daily_return_builder_uses_only_prior_sessions(tmp_path):
    rows = []
    for day, open_, close in [
        ("2024-01-02", 100.0, 101.0),
        ("2024-01-03", 101.0, 103.0),
        ("2024-01-04", 103.0, 102.0),
        ("2024-01-05", 102.0, 104.0),
        ("2024-01-08", 104.0, 103.0),
        ("2024-01-09", 103.0, 106.0),
    ]:
        rows.append(
            {
                "timestamp": pd.Timestamp(f"{day} 09:30"),
                "open": open_,
                "high": max(open_, close),
                "low": min(open_, close),
                "close": open_,
            }
        )
        rows.append(
            {
                "timestamp": pd.Timestamp(f"{day} 09:31"),
                "open": open_,
                "high": max(open_, close),
                "low": min(open_, close),
                "close": close,
            }
        )
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(rows).to_parquet(raw_path)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path, rank_min_periods=1)

    day_2024_01_09 = features.loc[features["session_date"] == "2024-01-09"].iloc[0]
    assert math.isfinite(day_2024_01_09["prior_max_return_5d"])
    assert day_2024_01_09["prior_max_return_5d"] > 0
    # The 2024-01-09 feature cannot include the large 2024-01-09 same-session return.
    assert day_2024_01_09["prior_max_return_5d"] < (106.0 / 103.0 - 1.0)


def test_max_daily_return_entry_is_registered():
    assert ENTRY_MODULES["max_daily_return_lottery_reversal"] is MaxDailyReturnLotteryReversalEntry


def _feature_file(tmp_path, session_date: str, *, max_rank: float, max_value: float):
    path = tmp_path / "max_daily_return.csv"
    path.write_text(
        "session_date,prior_close,prior_daily_return,prior_max_return_5d,prior_max_return_20d,"
        "prior_max_return_63d,prior_avg_top5_return_20d,max_return_5d_rank_252,"
        "max_return_20d_rank_252,max_return_63d_rank_252,avg_top5_return_20d_rank_252\n"
        f"{session_date},100,0.01,{max_value},{max_value},{max_value},{max_value},"
        f"{max_rank},{max_rank},{max_rank},{max_rank}\n",
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
