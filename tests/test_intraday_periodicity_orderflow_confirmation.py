from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.intraday_periodicity_orderflow_confirmation import (
    IntradayPeriodicityOrderflowConfirmationEntry,
)


def test_periodicity_orderflow_confirms_completed_source_window(tmp_path):
    entry = IntradayPeriodicityOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, mean20=1.2)),
            "slot_id": "slot_1000_1030",
            "source_start": "09:30:00",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
            "flow_mode": "signed_imbalance",
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = None
    for minute in range(30):
        signal = entry.on_bar_close(_bar(f"2024-01-08 09:{30 + minute:02d}", signed_volume=150))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-08 10:00")
    assert signal.report_fields["source_window_end_timestamp"] == pd.Timestamp("2024-01-08 10:00")
    assert signal.report_fields["feature_availability_rule"].startswith("prior sessions only")


def test_periodicity_orderflow_rejects_opposing_flow(tmp_path):
    entry = IntradayPeriodicityOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, mean20=1.2)),
            "slot_id": "slot_1000_1030",
            "source_start": "09:30:00",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
            "flow_mode": "signed_imbalance",
            "min_orderflow_imbalance": 0.10,
        }
    )

    signal = None
    for minute in range(30):
        signal = entry.on_bar_close(_bar(f"2024-01-08 09:{30 + minute:02d}", signed_volume=-150))

    assert signal is None


def test_periodicity_orderflow_requires_complete_window_and_dedupes(tmp_path):
    entry = IntradayPeriodicityOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, mean20=-1.2)),
            "slot_id": "slot_1000_1030",
            "source_start": "09:30:00",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
            "flow_mode": "large10_imbalance",
            "min_orderflow_imbalance": 0.10,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-08 09:59", signed_volume=-150)) is None

    entry = IntradayPeriodicityOrderflowConfirmationEntry(
        {
            "feature_csv": str(_feature_file(tmp_path, mean20=-1.2)),
            "slot_id": "slot_1000_1030",
            "source_start": "09:30:00",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
            "flow_mode": "large10_imbalance",
            "min_orderflow_imbalance": 0.10,
        }
    )
    first = None
    for minute in range(30):
        first = entry.on_bar_close(_bar(f"2024-01-08 09:{30 + minute:02d}", signed_volume=-150))
    second = entry.on_bar_close(_bar("2024-01-08 09:59", signed_volume=-150))

    assert first is not None
    assert first.direction == "short"
    assert second is None


def _feature_file(tmp_path, *, mean20: float):
    path = tmp_path / f"periodicity_{mean20}.csv"
    path.write_text(
        "session_date,slot_id,entry_time,slot_end_time,"
        "prior_slot_return_mean_bps_20,prior_slot_return_pos_rate_20,prior_slot_return_obs_20\n"
        f"2024-01-08,slot_1000_1030,10:00:00,10:30:00,{mean20},0.75,20\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp: str, *, signed_volume: int, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": 4800.0,
            "high": 4800.5,
            "low": 4799.5,
            "close": 4800.25,
            "volume": 1000,
            "signed_volume": signed_volume,
            "large10_volume": 600,
            "large10_signed_volume": signed_volume,
            "large20_volume": 400,
            "large20_signed_volume": signed_volume,
        }
    )
