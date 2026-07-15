from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.treasury_rate_orderflow_state import (
    TreasuryRateOrderflowStateEntry,
)


def _feature_csv(tmp_path: Path) -> str:
    path = tmp_path / "treasury_rate.csv"
    path.write_text(
        "\n".join(
            [
                "session_date,observation_date,dgs10,dgs2,curve_10y2y,"
                "dgs10_change_1d,dgs2_change_1d,curve_change_1d,dgs10_change_5d,curve_change_5d,"
                "dgs10_rank_252,dgs2_rank_252,curve_10y2y_rank_252,"
                "dgs10_change_1d_rank_252,dgs2_change_1d_rank_252,curve_change_1d_rank_252,"
                "dgs10_change_5d_rank_252,curve_change_5d_rank_252",
                "2024-01-03,2024-01-02,4.1,3.9,0.2,0.08,0.06,0.02,0.18,0.05,"
                "0.70,0.65,0.55,0.90,0.80,0.75,0.85,0.70",
                "2024-01-04,2024-01-03,4.0,3.8,0.2,-0.07,-0.05,-0.02,-0.15,-0.04,"
                "0.60,0.55,0.50,0.10,0.20,0.25,0.15,0.30",
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
        "low": 99.0,
        "close": 99.25,
        "volume": 1000,
        "signed_volume": -200,
        "large10_volume": 500,
        "large10_signed_volume": -125,
        "large20_volume": 250,
        "large20_signed_volume": -75,
    }
    base.update(overrides)
    return pd.Series(base)


def test_rate_up_confirmed_by_es_down_move_and_flow_emits_short(tmp_path):
    entry = TreasuryRateOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "rate_two_sided_confirmation",
            "rank_mode": "dgs10_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rate_rank_threshold": 0.70,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["treasury_observation_date"] == "2024-01-02"
    assert signal.report_fields["rate_driver_column"] == "dgs10_change_1d_rank_252"
    assert signal.report_fields["rate_driver_value"] == 0.90
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:00")


def test_rate_down_confirmed_by_es_up_move_and_flow_emits_long(tmp_path):
    entry = TreasuryRateOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "rate_two_sided_confirmation",
            "rank_mode": "dgs10_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rate_rank_threshold": 0.70,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(
        _bar("2024-01-04 09:55:00", close=100.75, signed_volume=200, large10_signed_volume=125),
        trades_today=0,
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["treasury_observation_date"] == "2024-01-03"
    assert signal.report_fields["rate_driver_value"] == 0.10
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.20


def test_curve_rank_mode_and_large10_flow_are_configurable(tmp_path):
    entry = TreasuryRateOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "rate_two_sided_confirmation",
            "rank_mode": "curve_1d",
            "flow_mode": "large10",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rate_rank_threshold": 0.70,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.20,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["rate_driver_column"] == "curve_change_1d_rank_252"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.25


def test_rate_orderflow_blocks_before_configured_signal_time(tmp_path):
    entry = TreasuryRateOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "rate_two_sided_confirmation",
            "rank_mode": "dgs10_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rate_rank_threshold": 0.70,
            "min_es_move_ticks": 0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:50:00"), trades_today=0) is None
