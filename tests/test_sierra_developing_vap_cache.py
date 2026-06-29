from __future__ import annotations

import pandas as pd

from tools.build_sierra_developing_vap_cache import developing_vap_features


def test_developing_vap_features_use_only_completed_bars_through_row() -> None:
    bars = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 09:30:00"),
                "session_date": pd.Timestamp("2024-01-03"),
                "high": 100.25,
                "low": 100.0,
                "close": 100.25,
            },
            {
                "timestamp": pd.Timestamp("2024-01-03 09:33:00"),
                "session_date": pd.Timestamp("2024-01-03"),
                "high": 100.50,
                "low": 100.0,
                "close": 100.50,
            },
            {
                "timestamp": pd.Timestamp("2024-01-03 09:36:00"),
                "session_date": pd.Timestamp("2024-01-03"),
                "high": 101.00,
                "low": 100.50,
                "close": 100.75,
            },
        ]
    )
    price_volume = pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-03 09:30:00"), "price": 100.00, "volume": 100},
            {"timestamp": pd.Timestamp("2024-01-03 09:30:00"), "price": 100.25, "volume": 10},
            {"timestamp": pd.Timestamp("2024-01-03 09:33:00"), "price": 100.00, "volume": 20},
            {"timestamp": pd.Timestamp("2024-01-03 09:33:00"), "price": 100.50, "volume": 5},
            {"timestamp": pd.Timestamp("2024-01-03 09:36:00"), "price": 101.00, "volume": 200},
        ]
    )

    out = developing_vap_features(
        bars,
        price_volume,
        min_bars=2,
        value_area_fraction=0.70,
        lvn_quantile=0.50,
    )

    assert pd.isna(out.iloc[0]["developing_vap_poc"])
    assert out.iloc[1]["developing_vap_session_yyyymmdd"] == 20240103
    assert out.iloc[1]["developing_vap_poc"] == 100.00
    assert out.iloc[1]["developing_vap_lvn_near_close"] == 100.50
    assert out.iloc[1]["developing_vap_bars"] == 2
    assert out.iloc[2]["developing_vap_poc"] == 101.00
    assert out.iloc[2]["developing_vap_bars"] == 3
