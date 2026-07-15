from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.cboe_implied_correlation_orderflow_confirmation import (
    CboeImpliedCorrelationOrderflowConfirmationEntry,
)


def test_high_short_term_correlation_short_requires_lagged_state_and_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.72)
    entry = CboeImpliedCorrelationOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_short_term_correlation_short",
            "confirmation_mode": "flow_only",
            "direction": "short",
            "signal_time": "13:30:00",
            "term_spread_rank_min": 0.65,
            "min_orderflow_imbalance": 0.05,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.5)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 13:29",
            open_=100.5,
            close=101.0,
            volume=1000,
            signed_volume=-120,
            large20_volume=200,
            large20_signed_volume=-60,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 13:30")
    assert signal.report_fields["correlation_driver_column"] == "cor1m_minus_cor3m_rank_252"
    assert signal.report_fields["correlation_driver_value"] == 0.72
    assert signal.report_fields["cboe_observation_date"] == "2024-01-02"
    assert signal.report_fields["signed_primary_orderflow_imbalance"] > 0


def test_high_short_term_correlation_short_rejects_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.52)
    entry = CboeImpliedCorrelationOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_short_term_correlation_short",
            "confirmation_mode": "flow_only",
            "direction": "short",
            "signal_time": "13:30:00",
            "term_spread_rank_min": 0.65,
            "min_orderflow_imbalance": 0.05,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.5))
    signal = entry.on_bar_close(
        _bar("2024-01-03 13:29", open_=100.5, close=101.0, volume=1000, signed_volume=-120)
    )

    assert signal is None


def test_high_short_term_correlation_short_rejects_unconfirmed_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.72)
    entry = CboeImpliedCorrelationOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_short_term_correlation_short",
            "confirmation_mode": "flow_only",
            "direction": "short",
            "signal_time": "13:30:00",
            "term_spread_rank_min": 0.65,
            "min_orderflow_imbalance": 0.05,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.5))
    signal = entry.on_bar_close(
        _bar("2024-01-03 13:29", open_=100.5, close=101.0, volume=1000, signed_volume=120)
    )

    assert signal is None


def test_large20_flow_mode_uses_completed_large_lot_imbalance(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.72)
    entry = CboeImpliedCorrelationOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_short_term_correlation_short",
            "confirmation_mode": "flow_only",
            "direction": "short",
            "flow_mode": "large20_imbalance",
            "signal_time": "13:30:00",
            "term_spread_rank_min": 0.65,
            "min_orderflow_imbalance": 0.20,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.5))
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 13:29",
            open_=100.5,
            close=101.0,
            volume=1000,
            signed_volume=120,
            large20_volume=200,
            large20_signed_volume=-80,
        )
    )

    assert signal is not None
    assert signal.report_fields["primary_orderflow_imbalance"] == -0.35
    assert signal.report_fields["signed_primary_orderflow_imbalance"] == 0.35


def test_direction_cannot_conflict_with_correlation_setup(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.72)

    with pytest.raises(ValueError, match="conflicts with setup_mode"):
        CboeImpliedCorrelationOrderflowConfirmationEntry(
            {
                "feature_csv": str(features),
                "setup_mode": "high_short_term_correlation_short",
                "direction": "long",
            }
        )


def _feature_file(tmp_path, session_date: str, *, term_rank: float):
    path = tmp_path / "correlation_features.csv"
    path.write_text(
        "session_date,observation_date,cor1m_close,cor3m_close,cor3m_change_1d,"
        "cor3m_change_5d,cor1m_minus_cor3m,cor1m_close_rank_252,"
        "cor3m_close_rank_252,cor3m_change_1d_rank_252,"
        "cor3m_change_5d_rank_252,cor1m_minus_cor3m_rank_252\n"
        f"{session_date},2024-01-02,65,55,1,4,10,0.6,0.7,0.8,0.75,{term_rank}\n",
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
