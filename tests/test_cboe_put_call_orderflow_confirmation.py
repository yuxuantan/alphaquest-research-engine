from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.cboe_put_call_orderflow_confirmation import (
    CboePutCallOrderflowConfirmationEntry,
)


def test_put_call_orderflow_confirmation_emits_long_with_aligned_completed_flow(tmp_path):
    entry = CboePutCallOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, "2024-03-20", total_change_rank=0.12)),
            "setup_mode": "falling_total_pc_long",
            "pc_change_rank_max": 0.4,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "orderflow_window_minutes": 5,
            "flow_mode": "signed_imbalance",
            "min_orderflow_imbalance": 0.05,
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 09:59", signed_volume=200))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["put_call_orderflow_confirmation_result"] == "passed"
    assert signal.report_fields["put_call_orderflow_signed_directional_imbalance"] > 0


def test_put_call_orderflow_confirmation_rejects_wrong_signed_flow(tmp_path):
    entry = CboePutCallOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, "2024-03-20", total_change_rank=0.12)),
            "setup_mode": "falling_total_pc_long",
            "pc_change_rank_max": 0.4,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "orderflow_window_minutes": 5,
            "flow_mode": "signed_imbalance",
            "min_orderflow_imbalance": 0.05,
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 09:59", signed_volume=-200))

    assert signal is None


def test_put_call_orderflow_confirmation_emits_short_with_large20_selling(tmp_path):
    entry = CboePutCallOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, "2024-03-20", equity_rank=0.88)),
            "setup_mode": "high_equity_pc_short",
            "pc_rank_min": 0.7,
            "entry_time": "10:30:00",
            "bar_interval_minutes": 1,
            "orderflow_window_minutes": 5,
            "flow_mode": "large20_imbalance",
            "min_orderflow_imbalance": 0.05,
        }
    )

    signal = entry.on_bar_close(
        _bar("2024-03-20 10:29", signed_volume=100, large20_signed_volume=-120)
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["put_call_orderflow_signed_directional_imbalance"] > 0


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    equity_rank: float = 0.5,
    total_change_rank: float = 0.6,
):
    path = tmp_path / "put_call.csv"
    path.write_text(
        "session_date,observation_date,equity_pc_ratio,index_pc_ratio,total_pc_ratio,"
        "equity_call_volume,equity_put_volume,index_call_volume,index_put_volume,"
        "total_call_volume,total_put_volume,equity_pc_change_1d,index_pc_change_1d,"
        "total_pc_change_1d,equity_pc_change_5d,index_pc_change_5d,total_pc_change_5d,"
        "index_minus_equity_pc,total_minus_equity_pc,equity_pc_ratio_rank_252,"
        "index_pc_ratio_rank_252,total_pc_ratio_rank_252,equity_pc_change_1d_rank_252,"
        "index_pc_change_1d_rank_252,total_pc_change_1d_rank_252,"
        "equity_pc_change_5d_rank_252,index_pc_change_5d_rank_252,"
        "total_pc_change_5d_rank_252,index_minus_equity_pc_rank_252,"
        "total_minus_equity_pc_rank_252\n"
        f"{session_date},2024-03-19,0.55,1.20,0.90,100,55,100,120,200,180,"
        f"-0.05,0.10,0.02,-0.08,0.12,0.04,0.65,0.35,{equity_rank},0.7,0.6,"
        f"0.25,0.75,{total_change_rank},0.25,0.75,0.6,0.8,0.7\n",
        encoding="utf-8",
    )
    return path


def _bar(
    timestamp,
    *,
    signed_volume: float,
    large20_signed_volume: float | None = None,
):
    ts = pd.Timestamp(timestamp)
    large20_signed_volume = signed_volume if large20_signed_volume is None else large20_signed_volume
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
            "signed_volume": signed_volume,
            "large10_volume": 500,
            "large10_signed_volume": signed_volume,
            "large20_volume": 300,
            "large20_signed_volume": large20_signed_volume,
        }
    )
