from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.spy_turnover_orderflow_attention import (
    SpyTurnoverOrderflowAttentionEntry,
)


def _feature_csv(tmp_path: Path) -> str:
    path = tmp_path / "spy_turnover.csv"
    path.write_text(
        "\n".join(
            [
                "session_date,observation_date,availability_rule,spy,spy_volume,"
                "spy_ret_1d,spy_ret_3d,spy_ret_5d,spy_volume_ratio_20,spy_volume_ratio_63,"
                "spy_absret_volume_1d,spy_absret_volume_3d,spy_signed_pressure_1d,"
                "spy_volume_ratio_20_rank_252,spy_volume_ratio_63_rank_252,"
                "spy_absret_volume_1d_rank_252,spy_absret_volume_3d_rank_252,"
                "spy_signed_pressure_1d_rank_252",
                "2024-01-03,2024-01-02,prior SPY close,480,90000000,"
                "0.012,0.018,0.025,1.8,1.5,0.0216,0.027,0.0216,0.85,0.80,0.90,0.75,0.88",
                "2024-01-04,2024-01-03,prior SPY close,470,110000000,"
                "-0.015,-0.030,-0.040,2.1,1.7,0.0315,0.051,-0.0315,0.92,0.87,0.95,0.91,0.05",
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


def test_spy_attention_long_uses_prior_spy_close_and_completed_flow(tmp_path):
    entry = SpyTurnoverOrderflowAttentionEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "spy_up_attention_long",
            "rank_mode": "volume_20",
            "return_mode": "spy_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "attention_rank_threshold": 0.60,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["spy_observation_date"] == "2024-01-02"
    assert signal.report_fields["attention_rank_column"] == "spy_volume_ratio_20_rank_252"
    assert signal.report_fields["attention_rank_value"] == 0.85
    assert signal.report_fields["spy_return_value"] == 0.012
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:00")


def test_spy_attention_short_requires_negative_return_move_and_flow(tmp_path):
    entry = SpyTurnoverOrderflowAttentionEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "spy_down_attention_short",
            "rank_mode": "absret_1d",
            "return_mode": "spy_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "attention_rank_threshold": 0.60,
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
    assert signal.report_fields["attention_rank_value"] == 0.95
    assert signal.report_fields["spy_return_value"] == -0.015
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.20


def test_spy_two_sided_attention_uses_configured_return_mode(tmp_path):
    entry = SpyTurnoverOrderflowAttentionEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "spy_two_sided_attention_continuation",
            "rank_mode": "volume_63",
            "return_mode": "spy_3d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "attention_rank_threshold": 0.60,
            "min_es_move_ticks": 2,
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["attention_rank_column"] == "spy_volume_ratio_63_rank_252"
    assert signal.report_fields["spy_return_column"] == "spy_ret_3d"


def test_spy_attention_blocks_before_configured_signal_time(tmp_path):
    entry = SpyTurnoverOrderflowAttentionEntry(
        {
            "feature_csv": _feature_csv(tmp_path),
            "setup_mode": "spy_two_sided_attention_continuation",
            "rank_mode": "volume_20",
            "return_mode": "spy_1d",
            "signal_times": ["10:00:00"],
            "bar_interval_minutes": 5,
            "attention_rank_threshold": 0.60,
            "min_es_move_ticks": 0,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:50:00"), trades_today=0) is None
