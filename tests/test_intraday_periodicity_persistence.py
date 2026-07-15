from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.intraday_periodicity_persistence import (
    IntradayPeriodicityPersistenceEntry,
)
from tools.build_es_intraday_periodicity_features import build_features


def test_intraday_periodicity_emits_long_on_completed_entry_bar(tmp_path):
    features = _feature_file(tmp_path, mean20=0.8)
    entry = IntradayPeriodicityPersistenceEntry(
        {
            "feature_csv": str(features),
            "slot_id": "slot_1000_1030",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 09:59", close=4800.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-08 10:00")
    assert signal.report_fields["feature_availability_rule"].startswith("prior sessions only")


def test_intraday_periodicity_emits_short_and_respects_threshold(tmp_path):
    features = _feature_file(tmp_path, mean20=-0.4)
    entry = IntradayPeriodicityPersistenceEntry(
        {
            "feature_csv": str(features),
            "slot_id": "slot_1000_1030",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
        }
    )
    assert entry.on_bar_close(_bar("2024-01-08 09:59", close=4800.0)) is None

    features = _feature_file(tmp_path, mean20=-0.9, name="short.csv")
    entry = IntradayPeriodicityPersistenceEntry(
        {
            "feature_csv": str(features),
            "slot_id": "slot_1000_1030",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
        }
    )
    signal = entry.on_bar_close(_bar("2024-01-08 09:59", close=4800.0))
    assert signal is not None
    assert signal.direction == "short"


def test_intraday_periodicity_direction_modes_and_duplicate_guard(tmp_path):
    features = _feature_file(tmp_path, mean20=-0.9)
    entry = IntradayPeriodicityPersistenceEntry(
        {
            "feature_csv": str(features),
            "slot_id": "slot_1000_1030",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "direction_mode": "long_only",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
        }
    )
    assert entry.on_bar_close(_bar("2024-01-08 09:59", close=4800.0)) is None

    features = _feature_file(tmp_path, mean20=0.9, name="long.csv")
    entry = IntradayPeriodicityPersistenceEntry(
        {
            "feature_csv": str(features),
            "slot_id": "slot_1000_1030",
            "entry_time": "10:00:00",
            "slot_end_time": "10:30:00",
            "direction_mode": "long_only",
            "lookback_days": 20,
            "min_mean_return_bps": 0.5,
        }
    )
    first = entry.on_bar_close(_bar("2024-01-08 09:59", close=4800.0))
    second = entry.on_bar_close(_bar("2024-01-08 09:59", close=4800.0))
    assert first is not None
    assert first.direction == "long"
    assert second is None


def test_intraday_periodicity_builder_uses_prior_slot_returns(tmp_path):
    rows = []
    sessions = pd.date_range("2024-01-02", periods=25, freq="B")
    for i, session in enumerate(sessions):
        date = session.strftime("%Y-%m-%d")
        rows.extend(
            [
                {"timestamp": f"{date} 10:00:00", "open": 100.0, "close": 100.0},
                {"timestamp": f"{date} 10:29:00", "open": 100.0, "close": 101.0 + i},
            ]
        )
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(rows).to_parquet(bars_path)

    out = build_features(
        bars_path,
        tmp_path / "features.csv",
        slots=[("slot_1000_1030", "10:00:00", "10:30:00")],
        lookback_days=(3,),
    )

    fourth = out.loc[out["session_date"] == sessions[3].strftime("%Y-%m-%d")].iloc[0]
    expected = ((101.0 / 100.0 - 1.0) + (102.0 / 100.0 - 1.0) + (103.0 / 100.0 - 1.0)) * 10_000.0 / 3.0
    assert fourth["prior_slot_return_mean_bps_3"] == expected
    assert fourth["prior_slot_return_obs_3"] == 3


def _feature_file(tmp_path, *, mean20: float, name: str = "periodicity.csv"):
    path = tmp_path / name
    path.write_text(
        "session_date,slot_id,entry_time,slot_end_time,"
        "prior_slot_return_mean_bps_20,prior_slot_return_pos_rate_20,prior_slot_return_obs_20\n"
        f"2024-01-08,slot_1000_1030,10:00:00,10:30:00,{mean20},0.75,20\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000,
        }
    )
