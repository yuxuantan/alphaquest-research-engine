from __future__ import annotations

from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.sector_opening_breadth_orderflow import (
    SectorOpeningBreadthOrderflowEntry,
)


def _feature_csv(tmp_path: Path) -> str:
    path = tmp_path / "sector_opening_breadth.csv"
    path.write_text(
        "\n".join(
            [
                "session_date,feature_observation_date,feature_available_time,"
                "xlk_open_gap,xly_open_gap,xlf_open_gap,xli_open_gap,xlv_open_gap,xlp_open_gap,xlu_open_gap,"
                "sector_up_count_7,sector_down_count_7,sector_avg_open_gap_7,"
                "cyclical_up_count_4,cyclical_down_count_4,cyclical_avg_open_gap_4,"
                "defensive_avg_open_gap_3,cyclical_minus_defensive_open_gap",
                "2024-01-03,2024-01-03,09:30:00 America/New_York,"
                "0.003,0.002,0.001,0.001,-0.001,0.0005,-0.0005,"
                "5,2,0.000857,4,0,0.00175,-0.000333,0.002083",
                "2024-01-04,2024-01-04,09:30:00 America/New_York,"
                "-0.003,-0.002,-0.001,-0.001,0.001,0.0005,0.0005,"
                "3,4,-0.000714,0,4,-0.00175,0.000667,-0.002417",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def _bar(timestamp: str, **overrides):
    base = {
        "timestamp": pd.Timestamp(timestamp),
        "session_date": pd.Timestamp(timestamp).date(),
        "is_rth": True,
        "open": 100.0,
        "high": 101.0,
        "low": 99.75,
        "close": 100.75,
        "volume": 1000,
        "signed_volume": 200,
        "large10_volume": 500,
        "large10_signed_volume": 100,
        "large20_volume": 250,
        "large20_signed_volume": 50,
    }
    base.update(overrides)
    return pd.Series(base)


def test_sector_opening_breadth_long_uses_same_day_open_and_completed_flow(tmp_path):
    entry = SectorOpeningBreadthOrderflowEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "broad_up_long",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "min_sector_count": 4,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
            "flow_mode": "signed_volume",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:50:00", close=100.25), trades_today=0) is None
    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00", open=100.25, close=100.75), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["feature_observation_date"] == "2024-01-03"
    assert signal.report_fields["sector_up_count_7"] == 5.0
    assert signal.report_fields["es_move_ticks"] == 3.0
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.20
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:00")


def test_sector_opening_breadth_blocks_before_configured_signal_time(tmp_path):
    entry = SectorOpeningBreadthOrderflowEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "broad_up_long",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "min_sector_count": 4,
            "min_es_move_ticks": 0,
            "min_orderflow_imbalance": 0.0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:45:00", close=100.75), trades_today=0) is None


def test_sector_opening_breadth_short_requires_negative_es_move_and_flow(tmp_path):
    entry = SectorOpeningBreadthOrderflowEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "broad_down_short",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "min_sector_count": 4,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
            "flow_mode": "large10",
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 09:55:00",
            open=100.0,
            close=99.25,
            signed_volume=-200,
            large10_signed_volume=-100,
        ),
        trades_today=0,
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["sector_down_count_7"] == 4.0
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.20


def test_sector_opening_breadth_two_sided_selects_matching_direction(tmp_path):
    entry = SectorOpeningBreadthOrderflowEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "broad_two_sided",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "min_sector_count": 4,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    long_signal = entry.on_bar_close(_bar("2024-01-03 09:55:00", close=100.75), trades_today=0)
    short_signal = entry.on_bar_close(
        _bar("2024-01-04 09:55:00", close=99.25, signed_volume=-200),
        trades_today=0,
    )

    assert long_signal is not None
    assert long_signal.direction == "long"
    assert short_signal is not None
    assert short_signal.direction == "short"
