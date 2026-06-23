from __future__ import annotations

import pandas as pd
import pytest

from propstack.strategy_modules.entry.nq_tech_relative_orderflow_confirmation import (
    NqTechRelativeOrderflowConfirmationEntry,
)


def test_tech_weakness_short_requires_lagged_rank_and_completed_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank_5d=0.24)
    entry = NqTechRelativeOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_5d_nonleadership_short",
            "confirmation_mode": "return_and_flow",
            "direction": "short",
            "signal_time": "11:30:00",
            "rank_max": 0.35,
            "min_confirm_return_ticks": 8,
            "min_orderflow_imbalance": 0.05,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=99.75)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 11:29",
            open_=99.75,
            close=96.0,
            volume=1000,
            signed_volume=-300,
            large20_volume=200,
            large20_signed_volume=-80,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 11:30")
    assert signal.report_fields["tech_driver_column"] == "xlk_minus_spy_5d_rank_252"
    assert signal.report_fields["tech_driver_value"] == 0.24
    assert signal.report_fields["availability_lag_business_days"] == 1.0
    assert signal.report_fields["signed_session_return_ticks"] > 0
    assert signal.report_fields["signed_primary_orderflow_imbalance"] > 0


def test_tech_weakness_short_rejects_unconfirmed_orderflow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank_5d=0.24)
    entry = NqTechRelativeOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_5d_nonleadership_short",
            "confirmation_mode": "return_and_flow",
            "direction": "short",
            "signal_time": "11:30:00",
            "rank_max": 0.35,
            "min_confirm_return_ticks": 8,
            "min_orderflow_imbalance": 0.05,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=99.75))
    signal = entry.on_bar_close(
        _bar("2024-01-03 11:29", open_=99.75, close=96.0, volume=1000, signed_volume=300)
    )

    assert signal is None


def test_tech_weakness_short_rejects_rank_above_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank_5d=0.42)
    entry = NqTechRelativeOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_5d_nonleadership_short",
            "confirmation_mode": "return_and_flow",
            "direction": "short",
            "signal_time": "11:30:00",
            "rank_max": 0.35,
            "min_confirm_return_ticks": 8,
            "min_orderflow_imbalance": 0.05,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=99.75))
    signal = entry.on_bar_close(
        _bar("2024-01-03 11:29", open_=99.75, close=96.0, volume=1000, signed_volume=-300)
    )

    assert signal is None


def test_tech_strength_long_uses_same_completed_bar_confirmation(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank_5d=0.84)
    entry = NqTechRelativeOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tech_5d_strength_long",
            "confirmation_mode": "vwap_pressure",
            "direction": "long",
            "signal_time": "10:30:00",
            "rank_min": 0.70,
            "min_vwap_extension_ticks": 0,
            "min_orderflow_imbalance": 0.02,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.5)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:29", open_=100.5, close=103.0, volume=1000, signed_volume=200)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["signed_price_vs_vwap_ticks"] >= 0
    assert signal.report_fields["signed_primary_orderflow_imbalance"] > 0


def test_direction_cannot_conflict_with_setup_mode(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", rank_5d=0.24)

    with pytest.raises(ValueError, match="conflicts with setup_mode"):
        NqTechRelativeOrderflowConfirmationEntry(
            {
                "feature_csv": str(features),
                "setup_mode": "tech_5d_weakness_short",
                "direction": "long",
            }
        )


def _feature_file(tmp_path, session_date: str, *, rank_5d: float):
    path = tmp_path / "tech_features.csv"
    path.write_text(
        "session_date,availability_cutoff,observation_date,availability_lag_business_days,"
        "xlk,spy,xlk_volume,xlk_return_1d,spy_return_1d,xlk_minus_spy_1d,"
        "xlk_return_5d,spy_return_5d,xlk_minus_spy_5d,xlk_volume_ratio_20,"
        "xlk_attention_pressure_1d,xlk_minus_spy_1d_rank_252,"
        "xlk_minus_spy_5d_rank_252,xlk_volume_ratio_20_rank_252,"
        "xlk_attention_pressure_1d_rank_252\n"
        f"{session_date},2024-01-02,2024-01-02,1,100,100,1000000,0.01,0.0,0.01,"
        f"0.02,0.0,0.02,1.2,0.01,0.5,{rank_5d},0.7,0.7\n",
        encoding="utf-8",
    )
    return path


def _bar(
    timestamp,
    *,
    open_: float,
    close: float,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000,
    signed_volume: float = -100,
    large10_volume: float = 300,
    large10_signed_volume: float = -50,
    large20_volume: float = 100,
    large20_signed_volume: float = -25,
):
    ts = pd.Timestamp(timestamp)
    high = max(open_, close) if high is None else high
    low = min(open_, close) if low is None else low
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_volume": large10_volume,
            "large10_signed_volume": large10_signed_volume,
            "large20_volume": large20_volume,
            "large20_signed_volume": large20_signed_volume,
        }
    )
