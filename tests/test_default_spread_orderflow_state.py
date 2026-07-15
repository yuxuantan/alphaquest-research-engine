from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.default_spread_orderflow_state import (
    DefaultSpreadOrderflowStateEntry,
)


def _feature_csv(tmp_path: Path) -> str:
    path = tmp_path / "default_spread.csv"
    path.write_text(
        "\n".join(
            [
                "session_date,credit_asof_date,observation_date,availability_lag_business_days,"
                "aaa_yield,baa_yield,default_spread,default_spread_change_1d,default_spread_change_5d,"
                "default_spread_rank_252,default_spread_change_1d_rank_252,default_spread_change_5d_rank_252",
                "2024-01-03,2023-12-29,2023-12-29,2,5.0,6.0,1.0,-0.02,-0.10,0.80,0.20,0.15",
                "2024-01-04,2024-01-02,2024-01-02,2,5.0,6.2,1.2,0.05,0.20,0.85,0.85,0.90",
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


def test_high_default_spread_long_uses_lagged_features_and_completed_flow(tmp_path):
    entry = DefaultSpreadOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "high_spread_long",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "credit_rank_threshold": 0.60,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["credit_observation_date"] == "2023-12-29"
    assert signal.report_fields["default_spread_rank_252"] == 0.80
    assert signal.report_fields["es_move_ticks"] == 3.0
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:00")


def test_widening_default_spread_short_requires_negative_es_move_and_flow(tmp_path):
    entry = DefaultSpreadOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "widening_spread_short",
            "flow_mode": "large10",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "credit_rank_threshold": 0.60,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(
        _bar("2024-01-04 09:55:00", close=99.25, signed_volume=-200, large10_signed_volume=-100),
        trades_today=0,
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["credit_driver_column"] == "default_spread_change_1d_rank_252"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.20


def test_tightening_default_spread_long_uses_lower_tail_change_rank(tmp_path):
    entry = DefaultSpreadOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "tightening_spread_long",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "credit_rank_threshold": 0.60,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["credit_driver_value"] == 0.20


def test_default_spread_blocks_before_configured_signal_time(tmp_path):
    entry = DefaultSpreadOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "high_spread_long",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "credit_rank_threshold": 0.60,
            "min_es_move_ticks": 0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:50:00"), trades_today=0) is None
