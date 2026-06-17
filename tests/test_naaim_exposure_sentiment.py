from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.naaim_exposure_sentiment import NaaimExposureSentimentEntry
from tools.build_es_naaim_exposure_features import build_session_features


def test_level_rank_contrarian_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-03-22", naaim_rank=0.80, naaim_number=90.0)
    entry = NaaimExposureSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "level_rank_contrarian",
            "rank_threshold": 0.5,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-22 09:59", close=5201.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-03-22 10:00")
    assert signal.report_fields["naaim_driver_column"] == "naaim_rank_104"
    assert signal.report_fields["naaim_availability_date"] == "2024-03-22"


def test_change_sign_contrarian_entry_emits_long_after_exposure_cut(tmp_path):
    features = _feature_file(tmp_path, "2024-03-22", naaim_change=-15.0)
    entry = NaaimExposureSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "change_sign_contrarian",
            "entry_time": "11:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-22 11:29", close=5201.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["naaim_driver_column"] == "naaim_change_1w"


def test_entry_requires_signal_session_and_exact_bar_close(tmp_path):
    features = _feature_file(tmp_path, "2024-03-22", naaim_z=1.2)
    entry = NaaimExposureSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "zscore_sign_contrarian",
            "entry_time": "12:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-03-22 11:58", close=5201.0)) is None
    assert entry.on_bar_close(_bar("2024-03-21 11:59", close=5201.0)) is None


def test_builder_maps_observation_to_first_session_after_two_business_days():
    sessions = pd.DataFrame(
        {
            "session_date": [
                "2024-03-20",
                "2024-03-21",
                "2024-03-22",
                "2024-03-25",
                "2024-03-26",
                "2024-03-27",
            ]
        }
    )
    naaim = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(["2024-03-20", "2024-03-27"]),
            "naaim_number": [80.0, 60.0],
            "mean_average": [80.0, 60.0],
            "quartile_1": [50.0, 40.0],
            "median": [75.0, 55.0],
            "quartile_3": [100.0, 80.0],
            "standard_deviation": [20.0, 25.0],
            "sp500": [5200.0, 5250.0],
        }
    )

    features = build_session_features(
        sessions,
        naaim,
        availability_lag_business_days=2,
        rank_window=2,
        rank_min_periods=1,
        ma_window=2,
    )

    assert list(features["session_date"]) == ["2024-03-22"]
    assert features.iloc[0]["observation_date"] == "2024-03-20"
    assert features.iloc[0]["availability_date"] == "2024-03-22"


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    naaim_number: float = 60.0,
    naaim_change: float = 10.0,
    naaim_rank: float = 0.25,
    naaim_z: float = -0.5,
    naaim_vs_ma: float = -5.0,
):
    path = tmp_path / "naaim.csv"
    path.write_text(
        "session_date,observation_date,availability_date,naaim_number,mean_average,"
        "quartile_1,median,quartile_3,standard_deviation,sp500,naaim_change_1w,"
        "naaim_change_4w,naaim_rank_104,naaim_change_rank_104,naaim_median_104,"
        "naaim_mean_104,naaim_std_104,naaim_z_104,naaim_ma_26,naaim_vs_ma_26\n"
        f"{session_date},2024-03-20,2024-03-22,{naaim_number},{naaim_number},"
        f"40,55,80,25,5200,{naaim_change},5,{naaim_rank},0.8,55,60,10,"
        f"{naaim_z},65,{naaim_vs_ma}\n",
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
            "open": close - 0.5,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000,
        }
    )
