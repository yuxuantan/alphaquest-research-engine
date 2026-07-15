from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.volatility_managed_intraday_premium import (
    VolatilityManagedIntradayPremiumEntry,
)


def _features(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "vol_features.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _bar(timestamp: str = "2024-01-03 09:59:00", *, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 4800.0,
            "high": 4802.0,
            "low": 4798.0,
            "close": 4801.0,
        }
    )


def _feature_row(session_date: str = "2024-01-03", **overrides) -> dict:
    row = {
        "session_date": session_date,
        "prior_close": 4790.0,
        "prior_rth_return": 0.001,
        "prior_range_pct": 0.005,
        "realized_vol_5": 0.004,
        "realized_vol_10": 0.005,
        "realized_vol_20": 0.006,
        "avg_range_pct_5": 0.006,
        "avg_range_pct_10": 0.007,
        "avg_abs_return_5": 0.003,
        "downside_vol_20": 0.002,
        "vol5_over_vol20": 0.7,
        "vol20_rank_252": 0.3,
        "range10_rank_252": 0.3,
        "absret5_rank_252": 0.3,
        "downside20_rank_252": 0.3,
        "vol_ratio_rank_252": 0.3,
    }
    row.update(overrides)
    return row


def test_low_vol_rank_signal_uses_completed_bar_time(tmp_path):
    entry = VolatilityManagedIntradayPremiumEntry(
        {
            "setup_mode": "low_vol20_long",
            "feature_csv": _features(tmp_path, [_feature_row()]),
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "vol_rank_max": 0.4,
        }
    )

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00:00")
    assert signal.report_fields["volatility_driver_column"] == "vol20_rank_252"


def test_rank_above_threshold_rejects(tmp_path):
    entry = VolatilityManagedIntradayPremiumEntry(
        {
            "setup_mode": "low_range10_long",
            "feature_csv": _features(tmp_path, [_feature_row(range10_rank_252=0.8)]),
            "entry_time": "10:00:00",
            "vol_rank_max": 0.4,
        }
    )

    assert entry.on_bar_close(_bar()) is None


def test_missing_feature_date_rejects(tmp_path):
    entry = VolatilityManagedIntradayPremiumEntry(
        {
            "setup_mode": "low_absret5_long",
            "feature_csv": _features(tmp_path, [_feature_row("2024-01-02")]),
            "entry_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar()) is None


def test_non_rth_bar_rejects(tmp_path):
    entry = VolatilityManagedIntradayPremiumEntry(
        {
            "setup_mode": "low_downside20_long",
            "feature_csv": _features(tmp_path, [_feature_row()]),
            "entry_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar(is_rth=False)) is None


def test_vol_downshift_ratio_signal(tmp_path):
    entry = VolatilityManagedIntradayPremiumEntry(
        {
            "setup_mode": "vol_downshift_long",
            "feature_csv": _features(tmp_path, [_feature_row(vol5_over_vol20=0.75)]),
            "entry_time": "10:00:00",
            "vol_ratio_max": 0.8,
        }
    )

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.report_fields["volatility_driver_column"] == "vol5_over_vol20"
