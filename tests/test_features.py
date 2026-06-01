import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.quality import tradingview_comparison_report
from propstack.data.features import build_features
from propstack.data.sessions import assign_sessions

from tests.test_data_pipeline import DATA_CFG


def test_tradingview_comparison_columns():
    df, _, _ = clean_data(DATA_CFG)
    report = tradingview_comparison_report(build_features(df, DATA_CFG))
    assert "rth_open" in report.columns
    assert "overnight_high" in report.columns
    assert "previous_rth_low" in report.columns


def test_previous_rth_levels_skip_eth_boundary_bar_over_weekend():
    cfg = {
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "eth_start": "16:00:00",
        "eth_end": "09:29:00",
        "rolling_volume_window": 3,
    }
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2022-12-16 09:30:00",
                    "2022-12-16 15:59:00",
                    "2022-12-16 16:00:00",
                    "2022-12-19 09:30:00",
                ]
            ).tz_localize("America/New_York"),
            "symbol": "ES",
            "open": [3900.0, 3882.0, 3877.5, 3880.0],
            "high": [3912.5, 3882.25, 3879.25, 3883.5],
            "low": [3895.0, 3877.25, 3875.75, 3875.25],
            "close": [3910.0, 3879.0, 3878.5, 3876.0],
            "volume": [100, 100, 100, 100],
        }
    )
    sessions = assign_sessions(df, cfg)
    features = build_features(sessions, cfg)
    monday_ts = pd.Timestamp("2022-12-19 09:30:00", tz="America/New_York")
    monday = features[features["timestamp"] == monday_ts].iloc[0]

    assert monday["prev_rth_high"] == 3912.5
    assert monday["prev_rth_low"] == 3877.25


def test_previous_rth_freshness_detects_overnight_breaches():
    cfg = {
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "eth_start": "16:00:00",
        "eth_end": "09:29:00",
        "rolling_volume_window": 3,
    }
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02 09:30:00",
                    "2024-01-02 09:31:00",
                    "2024-01-02 16:00:00",
                    "2024-01-03 09:30:00",
                ]
            ).tz_localize("America/New_York"),
            "symbol": "ES",
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 100.5, 101.25, 100.5],
            "low": [99.0, 99.5, 98.75, 99.25],
            "close": [100.5, 100.0, 100.0, 100.0],
            "volume": [100, 100, 100, 100],
        }
    )
    features = build_features(assign_sessions(df, cfg), cfg)
    overnight = features[
        features["timestamp"] == pd.Timestamp("2024-01-02 16:00:00", tz="America/New_York")
    ].iloc[0]
    next_rth = features[
        features["timestamp"] == pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York")
    ].iloc[0]

    assert overnight["prev_rth_high_fresh"]
    assert overnight["prev_rth_low_fresh"]
    assert not next_rth["prev_rth_high_fresh"]
    assert not next_rth["prev_rth_low_fresh"]
