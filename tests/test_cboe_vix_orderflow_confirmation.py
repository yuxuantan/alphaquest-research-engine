from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.cboe_vix_orderflow_confirmation import (
    CboeVixOrderflowConfirmationEntry,
)


def test_vix_orderflow_short_requires_lagged_vix_spike_and_completed_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.72)
    entry = CboeVixOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "unit_riskoff_short",
            "confirmation_mode": "riskoff_continuation",
            "direction": "short",
            "signal_time": "10:30:00",
            "vix_change_rank_min": 0.65,
            "min_confirm_return_ticks": 8,
            "min_orderflow_imbalance": 0.05,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=99.5)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29",
            open_=99.5,
            close=96.0,
            volume=1000,
            signed_volume=-300,
            large20_volume=200,
            large20_signed_volume=-80,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30")
    assert signal.report_fields["vix_change_1d_rank_252"] == 0.72
    assert signal.report_fields["signed_session_return_ticks"] > 0
    assert signal.report_fields["signed_primary_orderflow_imbalance"] > 0


def test_vix_orderflow_short_rejects_unconfirmed_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.72)
    entry = CboeVixOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "confirmation_mode": "riskoff_continuation",
            "direction": "short",
            "signal_time": "10:30:00",
            "vix_change_rank_min": 0.65,
            "min_confirm_return_ticks": 8,
            "min_orderflow_imbalance": 0.05,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=99.5))
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:29", open_=99.5, close=96.0, volume=1000, signed_volume=300)
    )

    assert signal is None


def test_vix_orderflow_rejects_low_vix_change_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.52)
    entry = CboeVixOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "confirmation_mode": "riskoff_continuation",
            "direction": "short",
            "signal_time": "10:30:00",
            "vix_change_rank_min": 0.65,
            "min_confirm_return_ticks": 8,
            "min_orderflow_imbalance": 0.05,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=99.5))
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:29", open_=99.5, close=96.0, volume=1000, signed_volume=-300)
    )

    assert signal is None


def test_vix_orderflow_failed_bounce_uses_only_pre_signal_bounce(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.8)
    entry = CboeVixOrderflowConfirmationEntry(
        {
            "feature_csv": str(features),
            "confirmation_mode": "failed_bounce",
            "direction": "short",
            "bounce_window_end": "10:00:00",
            "signal_time": "11:30:00",
            "vix_change_rank_min": 0.65,
            "min_bounce_return_ticks": 4,
            "min_confirm_return_ticks": 4,
            "min_orderflow_imbalance": 0.02,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", open_=100.0, close=100.25)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", open_=100.25, close=102.0)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 11:29", open_=101.0, close=98.0, volume=1000, signed_volume=-200)
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["bounce_return_ticks"] > 0


def _feature_file(tmp_path, session_date: str, *, change_rank: float):
    path = tmp_path / "vix_features.csv"
    path.write_text(
        "session_date,observation_date,vix_close,vix_change_1d,vix_change_5d,vix_5d_mean,"
        "vix_close_rank_252,vix_change_1d_rank_252,vix_change_5d_rank_252,vix_5d_mean_rank_252\n"
        f"{session_date},2024-01-02,22,1,3,21,0.5,{change_rank},0.5,0.5\n",
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
