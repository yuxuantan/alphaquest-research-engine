from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.dollar_risk_appetite import DollarRiskAppetiteEntry
from tools.build_es_dollar_risk_appetite_features import build_features


def test_dollar_features_use_prior_business_day_observation(tmp_path):
    bars_path = tmp_path / "bars.parquet"
    dollar_path = tmp_path / "dollar.csv"
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
            "DATE": pd.date_range("2023-12-28", periods=9, freq="B"),
            "DTWEXBGS": [100.0, 100.2, 100.4, 100.1, 100.6, 101.0, 100.8, 101.2, 101.5],
        }
    ).to_csv(dollar_path, index=False)

    features = build_features(
        bars_path,
        output_path,
        dollar_input=dollar_path,
        availability_lag_business_days=1,
        rank_min_periods=2,
    )

    by_session = features.set_index("session_date")
    assert by_session.loc["2024-01-08", "availability_cutoff"] == "2024-01-05"
    assert by_session.loc["2024-01-08", "observation_date"] == "2024-01-05"
    assert by_session.loc["2024-01-09", "availability_cutoff"] == "2024-01-08"
    assert by_session.loc["2024-01-09", "observation_date"] == "2024-01-08"


def test_dollar_up_short_signal_uses_completed_entry_bar(tmp_path):
    feature_path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {
                "session_date": "2024-01-08",
                "observation_date": "2024-01-05",
                "availability_cutoff": "2024-01-05",
                "availability_lag_business_days": 1,
                "dollar_index": 101.0,
                "dollar_return_1d": 0.01,
                "dollar_return_5d": 0.02,
                "dollar_abs_return_1d": 0.01,
                "dollar_index_rank_252": 0.80,
                "dollar_return_1d_rank_252": 0.90,
                "dollar_return_5d_rank_252": 0.85,
                "dollar_abs_return_1d_rank_252": 0.90,
            }
        ]
    ).to_csv(feature_path, index=False)

    entry = DollarRiskAppetiteEntry(
        {
            "feature_csv": str(feature_path),
            "setup_mode": "dollar_up_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "dollar_return_rank_min": 0.80,
        }
    )

    early = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-08 09:58:00"),
            "session_date": "2024-01-08",
            "is_rth": True,
            "open": 4800.0,
            "high": 4801.0,
            "low": 4799.0,
            "close": 4800.5,
        }
    )
    signal_bar = early.copy()
    signal_bar["timestamp"] = pd.Timestamp("2024-01-08 09:59:00")

    assert entry.on_bar_close(early) is None
    signal = entry.on_bar_close(signal_bar)
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["dollar_observation_date"] == "2024-01-05"
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-08 10:00:00")
