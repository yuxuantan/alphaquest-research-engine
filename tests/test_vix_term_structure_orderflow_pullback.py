from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.vix_term_structure_orderflow_pullback import (
    VixTermStructureOrderflowPullbackEntry,
)


def test_vix_term_contango_gates_vwap_orderflow_pullback_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.18)
    entry = VixTermStructureOrderflowPullbackEntry(
        {
            "feature_csv": str(features),
            "term_setup_mode": "contango_long",
            "term_rank_threshold": 0.35,
            "setup_mode": "trend_reclaim",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "required_trend_closes": 2,
            "min_drive_points": 0.0,
            "pullback_tolerance_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 2,
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.20,
            "tick_size": 0.25,
            "bar_interval_minutes": 1,
            "allow_long": True,
            "allow_short": False,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=100.6, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", close=100.7, vwap=100.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:32:00",
            close=100.7,
            low=99.9,
            vwap=100.0,
            signed_volume=300,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "vix_term_structure_contango_long_vwap_orderflow_trend_reclaim"
    assert signal.report_fields["term_structure_driver_column"] == "vix_vix3m_ratio_rank_252"
    assert signal.report_fields["term_structure_driver_rank"] == 0.18
    assert signal.report_fields["availability_rule"] == (
        "latest Cboe VIX term-structure close strictly before ES session_date"
    )


def test_vix_term_gate_rejects_wrong_direction_even_if_orderflow_matches(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.18)
    entry = VixTermStructureOrderflowPullbackEntry(
        {
            "feature_csv": str(features),
            "term_setup_mode": "contango_long",
            "term_rank_threshold": 0.35,
            "setup_mode": "trend_reclaim",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "required_trend_closes": 2,
            "min_drive_points": 0.0,
            "pullback_tolerance_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 2,
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.20,
            "tick_size": 0.25,
            "bar_interval_minutes": 1,
            "allow_long": False,
            "allow_short": True,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=99.4, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", close=99.3, vwap=100.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:32:00",
            close=99.3,
            high=100.1,
            vwap=100.0,
            signed_volume=-300,
            volume=1000,
        )
    )

    assert signal is None


def test_vix_term_availability_market_is_reported(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.18)
    entry = VixTermStructureOrderflowPullbackEntry(
        {
            "feature_csv": str(features),
            "availability_market": "NQ",
            "term_setup_mode": "contango_long",
            "term_rank_threshold": 0.35,
            "setup_mode": "trend_reclaim",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "required_trend_closes": 2,
            "min_drive_points": 0.0,
            "pullback_tolerance_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 2,
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.20,
            "tick_size": 0.25,
            "bar_interval_minutes": 1,
            "allow_long": True,
            "allow_short": False,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=100.6, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", close=100.7, vwap=100.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:32:00",
            close=100.7,
            low=99.9,
            vwap=100.0,
            signed_volume=300,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.report_fields["availability_rule"] == (
        "latest Cboe VIX term-structure close strictly before NQ session_date"
    )


def test_vix_term_front_stress_short_requires_upper_rank_and_short_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", term_rank=0.5, short_rank=0.82)
    entry = VixTermStructureOrderflowPullbackEntry(
        {
            "feature_csv": str(features),
            "term_setup_mode": "front_stress_short",
            "term_rank_threshold": 0.65,
            "setup_mode": "trend_reclaim",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "required_trend_closes": 2,
            "min_drive_points": 0.0,
            "pullback_tolerance_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 2,
            "flow_mode": "large20",
            "min_orderflow_imbalance": 0.25,
            "tick_size": 0.25,
            "bar_interval_minutes": 1,
            "allow_long": False,
            "allow_short": True,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=99.4, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", close=99.3, vwap=100.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:32:00",
            close=99.3,
            high=100.1,
            vwap=100.0,
            large20_signed_volume=-80,
            large20_volume=200,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["term_structure_driver_column"] == "vix9d_vix_ratio_rank_252"
    assert signal.report_fields["term_structure_driver_rank"] == 0.82
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.4


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    term_rank: float,
    short_rank: float = 0.8,
    curve_rank: float = 0.8,
    change_rank: float = 0.8,
):
    path = tmp_path / "vix_ts.csv"
    path.write_text(
        "session_date,observation_date,vix_close,vix9d_close,vix3m_close,vix6m_close,"
        "vix_vix3m_ratio,vix9d_vix_ratio,vix3m_vix6m_ratio,vix_vix3m_spread,"
        "vix_vix3m_ratio_change_1d,vix_close_rank_252,vix_vix3m_ratio_rank_252,"
        "vix9d_vix_ratio_rank_252,vix3m_vix6m_ratio_rank_252,"
        "vix_vix3m_spread_rank_252,vix_vix3m_ratio_change_1d_rank_252\n"
        f"{session_date},2024-01-02,22,24,21,23,1.0476,1.0909,0.9130,1,0.04,"
        f"0.7,{term_rank},{short_rank},{curve_rank},0.7,{change_rank}\n",
        encoding="utf-8",
    )
    return path


def _bar(
    timestamp: str,
    *,
    close: float,
    vwap: float,
    low: float | None = None,
    high: float | None = None,
    signed_volume: float = 0,
    volume: float = 1000,
    large20_signed_volume: float = 0,
    large20_volume: float = 0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close,
            "high": close if high is None else high,
            "low": close if low is None else low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
            "vwap": vwap,
        }
    )
