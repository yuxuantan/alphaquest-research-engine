from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.session_liquidity_fvg_reversal import SessionLiquidityFvgReversalEntry
from tools.build_nq_asia_london_session_levels import build_features


def test_failed_asia_high_sweep_short_uses_completed_bar_close(tmp_path):
    entry = SessionLiquidityFvgReversalEntry(
        {
            "feature_csv": str(_feature_csv(tmp_path)),
            "setup_mode": "asia_high_failed_sweep_short",
            "setup_start_time": "09:30:00",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "reclaim_close_buffer_ticks": 0,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:30", 99.5, 101.0, 99.0, 99.75))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 100.0
    assert signal.sweep_high == 101.0
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:35")
    assert signal.report_fields["liquidity_reference_type"] == "asia_high"


def test_asia_high_fvg_rejection_waits_for_retest_after_completed_gap(tmp_path):
    entry = SessionLiquidityFvgReversalEntry(
        {
            "feature_csv": str(_feature_csv(tmp_path)),
            "setup_mode": "asia_high_fvg_rejection_short",
            "setup_start_time": "09:30:00",
            "start_time": "09:35:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "min_gap_ticks": 2,
            "max_fvg_retest_bars": 4,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", 99.5, 101.0, 99.75, 100.5)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35", 100.5, 100.75, 99.5, 100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:40", 100.0, 98.75, 97.75, 98.0)) is None

    signal = entry.on_bar_close(_bar("2024-01-03 09:45", 98.0, 99.0, 97.5, 98.5))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["trigger_type"] == "session_liquidity_fvg_rejection"
    assert signal.report_fields["fvg_type"] == "bearish_fvg"
    assert signal.report_fields["fvg_bottom"] == 98.75
    assert signal.report_fields["fvg_top"] == 99.75


def test_london_low_fvg_rejection_long_uses_london_level(tmp_path):
    entry = SessionLiquidityFvgReversalEntry(
        {
            "feature_csv": str(_feature_csv(tmp_path)),
            "setup_mode": "london_low_fvg_rejection_long",
            "setup_start_time": "09:30:00",
            "start_time": "09:35:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "sweep_buffer_ticks": 0,
            "min_gap_ticks": 2,
            "max_fvg_retest_bars": 4,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", 90.5, 90.25, 88.5, 90.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35", 90.0, 90.5, 89.75, 90.25)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:40", 90.25, 92.0, 91.25, 91.75)) is None

    signal = entry.on_bar_close(_bar("2024-01-03 09:45", 91.75, 92.25, 91.0, 91.75))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["liquidity_reference_type"] == "london_low"
    assert signal.report_fields["fvg_type"] == "bullish_fvg"


def test_feature_builder_freezes_asia_and_london_before_rth(tmp_path):
    rows = []
    for ts in pd.date_range("2024-01-02 18:00", "2024-01-03 09:29", freq="1min", tz="America/New_York"):
        base = 100.0
        rows.append({"timestamp": ts, "open": base, "high": base + 1.0, "low": base - 1.0, "close": base, "volume": 1})
    for ts in pd.date_range("2024-01-03 09:30", "2024-01-03 15:59", freq="1min", tz="America/New_York"):
        rows.append({"timestamp": ts, "open": 200.0, "high": 250.0, "low": 150.0, "close": 200.0, "volume": 1})
    frame = pd.DataFrame(rows)
    frame.loc[frame["timestamp"].between("2024-01-02 20:00", "2024-01-02 20:00"), "high"] = 110.0
    frame.loc[frame["timestamp"].between("2024-01-03 04:00", "2024-01-03 04:00"), "low"] = 88.0
    input_path = tmp_path / "bars.parquet"
    output_path = tmp_path / "features.csv"
    frame.to_parquet(input_path)

    features = build_features(input_path, output_path)

    assert output_path.exists()
    row = features.iloc[0]
    assert row["session_date"] == "2024-01-03"
    assert row["asia_high"] == 110.0
    assert row["london_low"] == 88.0
    assert row["combined_high"] == 110.0
    assert row["combined_low"] == 88.0


def test_session_liquidity_entry_is_registered(tmp_path):
    entry = build_entry_module(
        {
            "module": "session_liquidity_fvg_reversal",
            "params": {
                "feature_csv": str(_feature_csv(tmp_path)),
                "setup_mode": "asia_two_sided_failed_sweep",
            },
        }
    )
    assert isinstance(entry, SessionLiquidityFvgReversalEntry)


def _feature_csv(tmp_path):
    path = tmp_path / "levels.csv"
    path.write_text(
        "session_date,asia_high,asia_low,london_high,london_low,combined_high,combined_low\n"
        "2024-01-03,100,90,105,89,105,89\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, open_, high, low, close):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )
