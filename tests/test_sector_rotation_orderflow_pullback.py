from __future__ import annotations

from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.sector_rotation_orderflow_pullback import (
    SectorRotationOrderflowPullbackEntry,
)


def _feature_csv(tmp_path: Path, *, growth_rank: float = 0.80, cyclical_rank: float = 0.20) -> str:
    path = tmp_path / "sector_features.csv"
    path.write_text(
        "\n".join(
            [
                "session_date,availability_cutoff,observation_date,availability_lag_business_days,"
                "cyclical_minus_defensive_1d_rank_252,cyclical_minus_defensive_5d_rank_252,"
                "growth_minus_defensive_5d_rank_252,financial_industrial_minus_spy_1d_rank_252",
                f"2024-01-03,2024-01-02,2024-01-02,1,{cyclical_rank},0.25,{growth_rank},0.75",
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
        "high": 100.75,
        "low": 99.75,
        "close": 100.5,
        "vwap": 100.0,
        "volume": 1000,
        "signed_volume": 200,
        "large10_volume": 500,
        "large10_signed_volume": 100,
        "large20_volume": 250,
        "large20_signed_volume": 50,
    }
    base.update(overrides)
    return pd.Series(base)


def test_sector_growth_state_vwap_reclaim_uses_completed_bar_orderflow(tmp_path):
    entry = SectorRotationOrderflowPullbackEntry(
        {
            "feature_csv": _feature_csv(tmp_path, growth_rank=0.82),
            "sector_mode": "growth_risk_on_long",
            "trigger_mode": "vwap_reclaim",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "rank_threshold": 0.60,
            "required_trend_closes": 1,
            "min_orderflow_imbalance": 0.10,
            "flow_mode": "signed_volume",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00"), trades_today=0) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:31:00", open=100.25, close=100.75, vwap=100.25, signed_volume=250),
        trades_today=0,
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["sector_column"] == "growth_minus_defensive_5d_rank_252"
    assert signal.report_fields["sector_rank"] == 0.82
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.25
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 09:32:00")


def test_sector_state_blocks_price_action_when_rank_not_in_tail(tmp_path):
    entry = SectorRotationOrderflowPullbackEntry(
        {
            "feature_csv": _feature_csv(tmp_path, growth_rank=0.50),
            "sector_mode": "growth_risk_on_long",
            "trigger_mode": "vwap_reclaim",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "rank_threshold": 0.60,
            "required_trend_closes": 1,
            "min_orderflow_imbalance": 0.10,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30:00"), trades_today=0)
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:31:00", open=100.25, close=100.75, vwap=100.25, signed_volume=250),
        trades_today=0,
    )

    assert signal is None


def test_defensive_sector_state_emits_short_ema_pullback(tmp_path):
    entry = SectorRotationOrderflowPullbackEntry(
        {
            "feature_csv": _feature_csv(tmp_path, cyclical_rank=0.15),
            "sector_mode": "defensive_risk_off_short",
            "trigger_mode": "ema_pullback",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "bar_interval_minutes": 1,
            "rank_threshold": 0.60,
            "fast_period": 2,
            "slow_period": 3,
            "min_ema_gap_ticks": 0.0,
            "pullback_tolerance_ticks": 8,
            "min_orderflow_imbalance": 0.10,
        }
    )
    signal = None
    for i, close in enumerate([100.0, 99.5, 99.0, 98.75, 98.5]):
        signal = entry.on_bar_close(
            _bar(
                f"2024-01-03 09:3{i}:00",
                open=close + 0.25,
                high=close + 0.25,
                low=close - 0.25,
                close=close,
                signed_volume=-200,
            ),
            trades_today=0,
        )
        if signal is not None:
            break

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["sector_column"] == "cyclical_minus_defensive_1d_rank_252"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.20
