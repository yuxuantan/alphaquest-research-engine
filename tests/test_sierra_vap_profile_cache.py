from __future__ import annotations

import pandas as pd

from tools.build_sierra_vap_profile_cache import (
    compute_session_profile,
    merge_prior_profiles,
    session_profiles_from_price_volume,
)
from tools.build_es_overnight_vap_footprint_cache import merge_completed_overnight_features


def test_compute_session_profile_uses_true_price_volume_levels() -> None:
    price_volume = pd.DataFrame(
        [
            {"price": 99.50, "volume": 10},
            {"price": 99.75, "volume": 25},
            {"price": 100.00, "volume": 100},
            {"price": 100.25, "volume": 75},
            {"price": 100.50, "volume": 15},
        ]
    )

    profile = compute_session_profile(
        price_volume,
        session_high=100.50,
        session_low=99.50,
        value_area_fraction=0.70,
        lvn_quantile=0.40,
    )

    assert profile is not None
    assert profile["vap_poc"] == 100.00
    assert profile["vap_val"] == 100.00
    assert profile["vap_vah"] == 100.25
    assert profile["vap_lvn_near_low"] == 99.50
    assert profile["vap_lvn_near_high"] == 100.50
    assert profile["vap_price_levels"] == 5


def test_merge_prior_profiles_shifts_completed_session_forward_only() -> None:
    base = pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-02 09:30"), "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1},
            {"timestamp": pd.Timestamp("2024-01-03 09:30"), "open": 101, "high": 102, "low": 100, "close": 101, "volume": 1},
            {"timestamp": pd.Timestamp("2024-01-04 09:30"), "open": 102, "high": 103, "low": 101, "close": 102, "volume": 1},
        ]
    )
    price_volume = pd.DataFrame(
        [
            {"session_date": pd.Timestamp("2024-01-02").date(), "price": 100.0, "volume": 100},
            {"session_date": pd.Timestamp("2024-01-02").date(), "price": 100.25, "volume": 10},
            {"session_date": pd.Timestamp("2024-01-03").date(), "price": 101.0, "volume": 200},
            {"session_date": pd.Timestamp("2024-01-03").date(), "price": 101.25, "volume": 20},
            {"session_date": pd.Timestamp("2024-01-04").date(), "price": 102.0, "volume": 300},
            {"session_date": pd.Timestamp("2024-01-04").date(), "price": 102.25, "volume": 30},
        ]
    )
    daily = pd.DataFrame(
        [
            {"session_date": pd.Timestamp("2024-01-02").date(), "session_high": 101.0, "session_low": 99.0, "bars": 1},
            {"session_date": pd.Timestamp("2024-01-03").date(), "session_high": 102.0, "session_low": 100.0, "bars": 1},
            {"session_date": pd.Timestamp("2024-01-04").date(), "session_high": 103.0, "session_low": 101.0, "bars": 1},
        ]
    )

    profiles = session_profiles_from_price_volume(price_volume, daily=daily)
    out = merge_prior_profiles(base, profiles)

    assert pd.isna(out.iloc[0]["prior_vap_poc"])
    assert out.iloc[1]["prior_vap_session_yyyymmdd"] == 20240102
    assert out.iloc[1]["prior_vap_poc"] == 100.0
    assert out.iloc[2]["prior_vap_session_yyyymmdd"] == 20240103
    assert out.iloc[2]["prior_vap_poc"] == 101.0


def test_merge_completed_overnight_features_joins_same_session_after_overnight_end() -> None:
    base = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 09:30"),
                "session_date": "2024-01-03",
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "volume": 1,
            },
            {
                "timestamp": pd.Timestamp("2024-01-04 09:30"),
                "session_date": "2024-01-04",
                "open": 101.0,
                "high": 101.5,
                "low": 100.5,
                "close": 101.0,
                "volume": 1,
            },
        ]
    )
    overnight = pd.DataFrame(
        [
            {
                "session_date": "2024-01-03",
                "overnight_start": "2024-01-02 18:00:00-05:00",
                "overnight_end": "2024-01-03 09:29:00-05:00",
                "overnight_high": 101.0,
                "overnight_low": 99.0,
                "overnight_midpoint": 100.0,
                "overnight_range_points": 2.0,
                "overnight_return_points": 0.5,
                "overnight_volume": 1000,
                "overnight_bars": 930,
                "overnight_range_rank_252": 0.25,
                "overnight_range_mean_252_prior": 8.0,
                "overnight_range_median_252_prior": 7.5,
            },
            {
                "session_date": "2024-01-04",
                "overnight_start": "2024-01-03 18:00:00-05:00",
                "overnight_end": "2024-01-04 09:31:00-05:00",
                "overnight_high": 102.0,
                "overnight_low": 100.0,
                "overnight_midpoint": 101.0,
                "overnight_range_points": 2.0,
                "overnight_return_points": 0.25,
                "overnight_volume": 1100,
                "overnight_bars": 930,
                "overnight_range_rank_252": 0.35,
                "overnight_range_mean_252_prior": 8.1,
                "overnight_range_median_252_prior": 7.6,
            },
        ]
    )

    out, report = merge_completed_overnight_features(base, overnight)

    assert out.loc[0, "overnight_high"] == 101.0
    assert out.loc[0, "overnight_low"] == 99.0
    assert out.loc[1, "overnight_high"] == 102.0
    assert report["bars_with_overnight_levels"] == 2
    assert report["missing_overnight_sessions"] == 0
    assert report["bad_overnight_window_rows"] == 1
