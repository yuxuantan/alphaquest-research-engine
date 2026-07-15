from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.realized_semivariance_orderflow_confirmation import (
    RealizedSemivarianceOrderflowConfirmationEntry,
)


def test_semivariance_orderflow_confirmation_emits_short_with_price_and_flow_confirmation(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.90)
    entry = RealizedSemivarianceOrderflowConfirmationEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_short",
            "rank_column": "downside1_rank_252",
            "value_column": "prior_downside_semivariance_1d",
            "semivar_rank_threshold": 0.20,
            "entry_time": "10:30:00",
            "bar_interval_minutes": 5,
            "flow_window_bars": 12,
            "flow_mode": "signed",
            "min_orderflow_imbalance": 0.05,
            "min_session_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, close=100.0)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:25:00", open_=99.0, close=98.75, flow12=-0.08)
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["semivar_rank"] == 0.90
    assert signal.report_fields["session_move_ticks"] == -5.0
    assert signal.report_fields["orderflow_imbalance"] == -0.08


def test_semivariance_orderflow_confirmation_rejects_missing_price_confirmation(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.90)
    entry = RealizedSemivarianceOrderflowConfirmationEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_short",
            "semivar_rank_threshold": 0.20,
            "entry_time": "10:30:00",
            "bar_interval_minutes": 5,
            "flow_window_bars": 12,
            "min_orderflow_imbalance": 0.05,
            "min_session_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:25:00", open_=99.75, close=99.75, flow12=-0.08)) is None


def test_semivariance_orderflow_confirmation_rejects_missing_flow_confirmation(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.90)
    entry = RealizedSemivarianceOrderflowConfirmationEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_short",
            "semivar_rank_threshold": 0.20,
            "entry_time": "10:30:00",
            "bar_interval_minutes": 5,
            "flow_window_bars": 12,
            "min_orderflow_imbalance": 0.05,
            "min_session_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:25:00", open_=99.0, close=98.75, flow12=-0.02)) is None


def test_semivariance_orderflow_confirmation_supports_multiple_decision_times(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.90)
    entry = RealizedSemivarianceOrderflowConfirmationEntry(
        {
            "feature_csv": str(feature_csv),
            "direction_mode": "high_short",
            "semivar_rank_threshold": 0.20,
            "entry_times": ["10:30:00", "11:30:00"],
            "bar_interval_minutes": 5,
            "flow_window_bars": 12,
            "min_orderflow_imbalance": 0.05,
            "min_session_move_ticks": 4,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:25:00", open_=99.75, close=99.75, flow12=-0.08)) is None
    signal = entry.on_bar_close(_bar("2024-01-03 11:25:00", open_=99.0, close=98.75, flow12=-0.08))

    assert signal is not None
    assert signal.direction == "short"
    assert str(signal.report_fields["signal_timestamp"].time()) == "11:30:00"


def _feature_csv(tmp_path: Path, *, rank: float) -> Path:
    path = tmp_path / "semivar.csv"
    path.write_text(
        "session_date,downside1_rank_252,prior_downside_semivariance_1d,prior_close,prior_rth_return,"
        "prior_realized_variance,prior_upside_semivariance_1d,prior_downside_share_1d,"
        "prior_semivariance_balance_1d\n"
        f"2024-01-03,{rank},0.5,100,-1,1.0,0.2,0.7,0.3\n"
    )
    return path


def _bar(timestamp: str, *, open_: float, close: float, flow12: float = 0.0) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": open_,
            "high": max(open_, close),
            "low": min(open_, close),
            "close": close,
            "trade_orderflow_imbalance_12": flow12,
        }
    )
