from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.macro_event_amd_distribution import MacroEventAmdDistributionEntry


def test_bls_amd_emits_long_after_completed_sellside_sweep_and_displacement(tmp_path):
    entry = MacroEventAmdDistributionEntry(
        {
            "event_source": "bls",
            "event_calendar_csv": str(_bls_calendar(tmp_path)),
            "release_types": ["employment_situation"],
            "setup_mode": "sellside_sweep_bullish_distribution",
            "accumulation_start_time": "09:30:00",
            "accumulation_end_time": "09:32:00",
            "signal_start_time": "09:32:00",
            "last_entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "tick_size": 0.25,
            "min_sweep_ticks": 2,
            "min_displacement_ticks": 1,
            "displacement_reference": "opposite_edge",
        }
    )

    assert entry.on_bar_close(_bar("2024-06-07 09:30", open=100.0, high=100.0, low=99.5, close=99.75)) is None
    assert entry.on_bar_close(_bar("2024-06-07 09:31", open=99.75, high=100.25, low=99.25, close=100.0)) is None
    signal = entry.on_bar_close(_bar("2024-06-07 09:32", open=100.0, high=100.75, low=98.50, close=100.50))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 99.25
    assert signal.reclaim_timestamp == pd.Timestamp("2024-06-07 09:33:00")
    assert signal.report_fields["event_types"] == "employment_situation"
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-06-07 09:33:00")


def test_bls_amd_rejects_non_event_session(tmp_path):
    entry = MacroEventAmdDistributionEntry(
        {
            "event_source": "bls",
            "event_calendar_csv": str(_bls_calendar(tmp_path)),
            "release_types": ["employment_situation"],
            "setup_mode": "sellside_sweep_bullish_distribution",
            "accumulation_start_time": "09:30:00",
            "accumulation_end_time": "09:32:00",
            "signal_start_time": "09:32:00",
            "last_entry_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-06-10 09:30", open=100.0, high=100.0, low=99.5, close=99.75)) is None
    assert entry.on_bar_close(_bar("2024-06-10 09:31", open=99.75, high=100.25, low=99.25, close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-06-10 09:32", open=100.0, high=100.75, low=98.50, close=100.50)) is None


def test_two_sided_amd_rejects_ambiguous_both_side_sweep_bar(tmp_path):
    entry = MacroEventAmdDistributionEntry(
        {
            "event_source": "bls",
            "event_calendar_csv": str(_bls_calendar(tmp_path)),
            "setup_mode": "two_sided_distribution",
            "accumulation_start_time": "09:30:00",
            "accumulation_end_time": "09:32:00",
            "signal_start_time": "09:32:00",
            "last_entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "tick_size": 0.25,
            "min_sweep_ticks": 2,
            "min_displacement_ticks": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-06-07 09:30", open=100.0, high=100.0, low=99.5, close=99.75)) is None
    assert entry.on_bar_close(_bar("2024-06-07 09:31", open=99.75, high=100.25, low=99.25, close=100.0)) is None
    signal = entry.on_bar_close(_bar("2024-06-07 09:32", open=100.0, high=101.0, low=98.5, close=100.5))

    assert signal is None


def test_fomc_amd_emits_short_after_afternoon_buyside_sweep(tmp_path):
    entry = MacroEventAmdDistributionEntry(
        {
            "event_source": "fomc",
            "event_calendar_csv": str(_fomc_calendar(tmp_path)),
            "setup_mode": "buyside_sweep_bearish_distribution",
            "accumulation_start_time": "13:58:00",
            "accumulation_end_time": "14:00:00",
            "signal_start_time": "14:00:00",
            "last_entry_time": "15:00:00",
            "bar_interval_minutes": 1,
            "tick_size": 0.25,
            "min_sweep_ticks": 2,
            "min_displacement_ticks": 1,
            "displacement_reference": "opposite_edge",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-31 13:58", open=100.0, high=100.5, low=99.5, close=100.25)) is None
    assert entry.on_bar_close(_bar("2024-01-31 13:59", open=100.25, high=100.75, low=99.75, close=100.0)) is None
    signal = entry.on_bar_close(_bar("2024-01-31 14:00", open=100.0, high=101.50, low=98.75, close=99.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 100.75
    assert signal.report_fields["event_types"] == "fomc_scheduled_decision"


def _bls_calendar(tmp_path):
    path = tmp_path / "bls.csv"
    path.write_text(
        "release_date,release_time,release_type,release_name,scheduled,source,source_url,notes\n"
        "2024-06-07,08:30:00,employment_situation,Employment Situation,true,unit_test,https://example.test,known\n",
        encoding="utf-8",
    )
    return path


def _fomc_calendar(tmp_path):
    path = tmp_path / "fomc.csv"
    path.write_text(
        "event_date,event_time,event_type,scheduled,source_year,source_url,source_label,notes\n"
        "2024-01-31,14:00:00,fomc_scheduled_decision,true,2024,https://example.test,January 30-31,test\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, *, open: float, high: float, low: float, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": open,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )
