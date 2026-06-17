from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.sector_rotation_risk_appetite import (
    SectorRotationRiskAppetiteEntry,
)
from tools.build_es_sector_rotation_features import SECTOR_SYMBOLS, build_features


def test_sector_rotation_features_use_prior_business_day_close(tmp_path):
    bars_path = tmp_path / "bars.parquet"
    output_path = tmp_path / "features.csv"
    pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-08 09:30:00",
                    "2024-01-09 09:30:00",
                ]
            )
        }
    ).to_parquet(bars_path, index=False)

    dates = pd.date_range("2023-12-26", periods=11, freq="B")
    input_paths = {}
    for idx, symbol in enumerate(SECTOR_SYMBOLS):
        path = tmp_path / f"{symbol}.csv"
        pd.DataFrame(
            {
                "Date": dates,
                "Adj Close": [100.0 + idx + i for i in range(len(dates))],
            }
        ).to_csv(path, index=False)
        input_paths[symbol] = path

    features = build_features(
        bars_path,
        output_path,
        input_paths=input_paths,
        rank_min_periods=2,
        availability_lag_bdays=1,
    )

    by_session = features.set_index("session_date")
    assert by_session.loc["2024-01-08", "availability_cutoff"] == "2024-01-05"
    assert by_session.loc["2024-01-08", "observation_date"] == "2024-01-05"
    assert by_session.loc["2024-01-09", "availability_cutoff"] == "2024-01-08"
    assert by_session.loc["2024-01-09", "observation_date"] == "2024-01-08"


def test_sector_rotation_long_signal_uses_completed_entry_bar(tmp_path):
    feature_path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {
                "session_date": "2024-01-08",
                "availability_cutoff": "2024-01-05",
                "observation_date": "2024-01-05",
                "availability_lag_business_days": 1,
                "cyclical_return_1d": 0.01,
                "defensive_return_1d": -0.002,
                "cyclical_minus_defensive_1d": 0.012,
                "cyclical_return_5d": 0.02,
                "defensive_return_5d": 0.001,
                "cyclical_minus_defensive_5d": 0.019,
                "growth_minus_defensive_5d": 0.021,
                "financial_industrial_minus_spy_1d": 0.003,
                "cyclical_minus_defensive_1d_rank_252": 0.90,
                "cyclical_minus_defensive_5d_rank_252": 0.85,
                "growth_minus_defensive_5d_rank_252": 0.88,
                "financial_industrial_minus_spy_1d_rank_252": 0.80,
            }
        ]
    ).to_csv(feature_path, index=False)

    entry = SectorRotationRiskAppetiteEntry(
        {
            "feature_csv": str(feature_path),
            "setup_mode": "cyclical_lead_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "rank_min": 0.80,
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
    assert signal.direction == "long"
    assert signal.report_fields["sector_observation_date"] == "2024-01-05"
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-08 10:00:00")


def test_sector_rotation_defensive_mode_short_signal(tmp_path):
    feature_path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {
                "session_date": "2024-01-08",
                "availability_cutoff": "2024-01-05",
                "observation_date": "2024-01-05",
                "availability_lag_business_days": 1,
                "cyclical_minus_defensive_1d_rank_252": 0.10,
                "cyclical_minus_defensive_5d_rank_252": 0.20,
                "growth_minus_defensive_5d_rank_252": 0.25,
                "financial_industrial_minus_spy_1d_rank_252": 0.30,
            }
        ]
    ).to_csv(feature_path, index=False)

    entry = SectorRotationRiskAppetiteEntry(
        {
            "feature_csv": str(feature_path),
            "setup_mode": "defensive_lead_short",
            "entry_time": "10:00:00",
            "rank_max": 0.20,
        }
    )
    bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-08 09:59:00"),
            "session_date": "2024-01-08",
            "is_rth": True,
            "open": 4800.0,
            "high": 4801.0,
            "low": 4799.0,
            "close": 4800.5,
        }
    )
    signal = entry.on_bar_close(bar)
    assert signal is not None
    assert signal.direction == "short"
