from __future__ import annotations

import pandas as pd

from tools.build_es_video_aoi_exact_cache import (
    aggregate_orb_30s_prints,
    aggregate_supplemental_1m_to_3m,
)


def test_video_aoi_exact_cache_aggregates_large200_and_carries_overnight_levels():
    rows = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-03 09:30:00",
                    "2024-01-03 09:31:00",
                    "2024-01-03 09:32:00",
                    "2024-01-03 09:33:00",
                ]
            ),
            "large200_record_volume": [200, 0, 300, 250],
            "large200_record_signed_volume": [200, 0, -300, -250],
            "large200_record_buy_volume": [200, 0, 0, 0],
            "large200_record_sell_volume": [0, 0, 300, 250],
            "large200_record_count": [1, 0, 1, 1],
            "large200_record_max_volume": [200, 0, 300, 250],
            "overnight_high": [101.0, 101.0, 101.0, 102.0],
            "overnight_low": [99.0, 99.0, 99.0, 98.0],
        }
    )

    out = aggregate_supplemental_1m_to_3m(rows, bar_minutes=3)

    first = out[out["timestamp"] == pd.Timestamp("2024-01-03 09:30:00")].iloc[0]
    second = out[out["timestamp"] == pd.Timestamp("2024-01-03 09:33:00")].iloc[0]
    assert first["large200_record_volume"] == 500
    assert first["large200_record_signed_volume"] == -100
    assert first["large200_record_max_volume"] == 300
    assert first["large200_record_count"] == 2
    assert first["overnight_high"] == 101.0
    assert second["large200_record_volume"] == 250
    assert second["overnight_low"] == 98.0


def test_video_aoi_exact_cache_aggregates_true_first_30_second_orb():
    prints = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-03 09:29:59.999",
                    "2024-01-03 09:30:00.000",
                    "2024-01-03 09:30:12.500",
                    "2024-01-03 09:30:29.999",
                    "2024-01-03 09:30:30.000",
                    "2024-01-04 09:30:05.000",
                ]
            ),
            "high": [99.0, 100.0, 101.25, 100.5, 105.0, 110.0],
            "low": [98.0, 99.75, 100.75, 99.5, 104.0, 109.0],
            "volume": [10, 100, 125, 150, 1000, 200],
            "num_trades": [1, 2, 3, 0, 10, 4],
        }
    )

    out = aggregate_orb_30s_prints(prints)

    first = out[out["_session_date"] == pd.Timestamp("2024-01-03")].iloc[0]
    second = out[out["_session_date"] == pd.Timestamp("2024-01-04")].iloc[0]
    assert first["orb_30s_high"] == 101.25
    assert first["orb_30s_low"] == 99.5
    assert first["orb_30s_range_points"] == 1.75
    assert first["orb_30s_volume"] == 375
    assert first["orb_30s_trades"] == 6
    assert first["orb_30s_available_after_open_seconds"] == 30.0
    assert second["orb_30s_high"] == 110.0
