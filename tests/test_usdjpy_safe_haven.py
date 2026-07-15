from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.usdjpy_safe_haven import UsdJpySafeHavenEntry
from tools.build_es_usdjpy_safe_haven_features import build_features


def test_usdjpy_features_use_prior_business_day_observation(tmp_path):
    bars_path = tmp_path / "bars.parquet"
    usdjpy_path = tmp_path / "usdjpy.csv"
    output_path = tmp_path / "features.csv"

    pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-05 09:30:00",
                    "2024-01-08 09:30:00",
                    "2024-01-09 09:30:00",
                ]
            )
        }
    ).to_parquet(bars_path, index=False)
    pd.DataFrame(
        {
            "observation_date": pd.date_range("2023-12-28", periods=9, freq="B"),
            "DEXJPUS": [142.0, 142.2, 141.9, 141.5, 140.9, 140.4, 141.0, 141.4, 141.7],
        }
    ).to_csv(usdjpy_path, index=False)

    features = build_features(
        bars_path,
        output_path,
        usdjpy_input=usdjpy_path,
        availability_lag_business_days=1,
        rank_min_periods=2,
    )

    by_session = features.set_index("session_date")
    assert by_session.loc["2024-01-08", "availability_cutoff"] == "2024-01-05"
    assert by_session.loc["2024-01-08", "observation_date"] == "2024-01-05"
    assert by_session.loc["2024-01-09", "availability_cutoff"] == "2024-01-08"
    assert by_session.loc["2024-01-09", "observation_date"] == "2024-01-08"


def test_yen_appreciation_short_signal_uses_completed_entry_bar(tmp_path):
    feature_path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {
                "session_date": "2024-01-08",
                "observation_date": "2024-01-05",
                "availability_cutoff": "2024-01-05",
                "availability_lag_business_days": 1,
                "usdjpy": 140.4,
                "usdjpy_return_1d": -0.01,
                "usdjpy_return_5d": -0.02,
                "usdjpy_abs_return_1d": 0.01,
                "usdjpy_rank_252": 0.20,
                "usdjpy_return_1d_rank_252": 0.10,
                "usdjpy_return_5d_rank_252": 0.15,
                "usdjpy_abs_return_1d_rank_252": 0.90,
            }
        ]
    ).to_csv(feature_path, index=False)

    entry = UsdJpySafeHavenEntry(
        {
            "feature_csv": str(feature_path),
            "setup_mode": "yen_appreciation_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "return_rank_max": 0.20,
        }
    )

    early = _bar("2024-01-08 09:58:00")
    signal_bar = _bar("2024-01-08 09:59:00")

    assert entry.on_bar_close(early) is None
    signal = entry.on_bar_close(signal_bar)
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["usdjpy_observation_date"] == "2024-01-05"
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-08 10:00:00")


def test_yen_depreciation_long_signal(tmp_path):
    feature_path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {
                "session_date": "2024-01-08",
                "observation_date": "2024-01-05",
                "availability_cutoff": "2024-01-05",
                "availability_lag_business_days": 1,
                "usdjpy": 142.5,
                "usdjpy_return_1d": 0.01,
                "usdjpy_return_5d": 0.02,
                "usdjpy_abs_return_1d": 0.01,
                "usdjpy_rank_252": 0.80,
                "usdjpy_return_1d_rank_252": 0.90,
                "usdjpy_return_5d_rank_252": 0.85,
                "usdjpy_abs_return_1d_rank_252": 0.90,
            }
        ]
    ).to_csv(feature_path, index=False)
    entry = UsdJpySafeHavenEntry(
        {
            "feature_csv": str(feature_path),
            "setup_mode": "yen_depreciation_long",
            "entry_time": "10:30:00",
            "return_rank_min": 0.80,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 10:29:00"))

    assert signal is not None
    assert signal.direction == "long"


def _bar(timestamp: str) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": 4800.0,
            "high": 4801.0,
            "low": 4799.0,
            "close": 4800.5,
        }
    )
