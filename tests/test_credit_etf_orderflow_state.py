from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.credit_etf_orderflow_state import CreditEtfOrderflowStateEntry


def _feature_csv(tmp_path: Path) -> str:
    path = tmp_path / "credit_etf.csv"
    path.write_text(
        "\n".join(
            [
                "session_date,observation_date,availability_rule,hyg,lqd,spy,"
                "hyg_ret_1d,hyg_ret_3d,hyg_ret_5d,lqd_ret_1d,spy_ret_1d,"
                "hyg_lqd_excess_3d,hyg_spy_excess_1d,hyg_spy_excess_3d,"
                "hyg_ret_1d_rank_252,hyg_ret_3d_rank_252,hyg_ret_5d_rank_252,"
                "hyg_lqd_excess_3d_rank_252,hyg_spy_excess_1d_rank_252,hyg_spy_excess_3d_rank_252",
                "2024-01-03,2024-01-02,prior ETF close,80,105,480,0.01,0.02,0.03,0.002,0.004,0.018,0.006,0.012,0.85,0.80,0.75,0.70,0.65,0.60",
                "2024-01-04,2024-01-03,prior ETF close,79,106,482,-0.02,-0.03,-0.04,0.001,0.003,-0.031,-0.023,-0.033,0.10,0.15,0.20,0.25,0.30,0.35",
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


def test_hyg_strength_long_uses_prior_etf_close_and_completed_flow(tmp_path):
    entry = CreditEtfOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "hyg_strength_long",
            "rank_mode": "hyg_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rank_threshold": 0.65,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["credit_etf_observation_date"] == "2024-01-02"
    assert signal.report_fields["credit_driver_column"] == "hyg_ret_1d_rank_252"
    assert signal.report_fields["credit_driver_value"] == 0.85
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:00")


def test_hyg_weakness_short_requires_negative_move_and_flow(tmp_path):
    entry = CreditEtfOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "hyg_weakness_short",
            "rank_mode": "hyg_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rank_threshold": 0.65,
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
    assert signal.report_fields["credit_driver_value"] == 0.10
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.20


def test_hyg_two_sided_continuation_uses_configured_rank_mode(tmp_path):
    entry = CreditEtfOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "hyg_two_sided_continuation",
            "rank_mode": "hyg_3d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rank_threshold": 0.65,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["credit_driver_column"] == "hyg_ret_3d_rank_252"
    assert signal.report_fields["credit_driver_value"] == 0.80


def test_credit_etf_blocks_before_configured_signal_time(tmp_path):
    entry = CreditEtfOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "hyg_strength_long",
            "rank_mode": "hyg_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rank_threshold": 0.65,
            "min_es_move_ticks": 0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:50:00"), trades_today=0) is None


def test_credit_etf_accepts_generic_min_move_ticks_alias(tmp_path):
    entry = CreditEtfOrderflowStateEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "hyg_strength_long",
            "rank_mode": "hyg_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "rank_threshold": 0.65,
            "min_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.report_fields["instrument_move_ticks"] == 3.0
    assert signal.report_fields["min_move_ticks"] == 2.0
