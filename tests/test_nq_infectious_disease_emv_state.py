from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.infectious_disease_emv_state import (
    InfectiousDiseaseEmvStateEntry,
)
from tools.build_nq_infectious_disease_emv_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["infectious_disease_emv_state"] is InfectiousDiseaseEmvStateEntry


def test_high_21d_short_emits_only_on_completed_entry_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", emv_rank=0.72)
    entry = InfectiousDiseaseEmvStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_21d_emv_riskoff_short",
            "rank_column": "infect_emv_21d_rank_252",
            "value_column": "infect_emv_21d",
            "emv_rank_threshold": 0.40,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["infect_emv_rank_column"] == "infect_emv_21d_rank_252"
    assert signal.report_fields["availability_rule"].startswith("latest FRED")


def test_high_21d_rebound_requires_high_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", emv_rank=0.55)
    entry = InfectiousDiseaseEmvStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_21d_emv_rebound_long",
            "rank_column": "infect_emv_21d_rank_252",
            "value_column": "infect_emv_21d",
            "emv_rank_threshold": 0.40,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", emv_rank=0.91, name="high.csv")
    entry = InfectiousDiseaseEmvStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_21d_emv_rebound_long",
            "rank_column": "infect_emv_21d_rank_252",
            "value_column": "infect_emv_21d",
            "emv_rank_threshold": 0.40,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"


def test_rising_5d_uses_configured_rank_column(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", change_rank=0.80)
    entry = InfectiousDiseaseEmvStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_5d_emv_short",
            "rank_column": "infect_emv_5d_change_rank_252",
            "value_column": "infect_emv_5d_change",
            "emv_rank_threshold": 0.25,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["infect_emv_value_column"] == "infect_emv_5d_change"


def test_builder_uses_7_calendar_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-04-15", periods=180, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    emv_path = tmp_path / "infect_emv.csv"
    _write_infect_emv_csv(emv_path, pd.date_range("2023-01-01", "2024-12-31", freq="D"))
    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        infect_emv_csv_path=emv_path,
        publication_lag_calendar_days=7,
        download_if_missing=False,
    )

    first = features.loc[features["session_date"] == "2024-04-15"].iloc[0]
    later = features.iloc[-1]
    assert first["availability_cutoff"] == "2024-04-08"
    assert first["observation_date"] <= "2024-04-08"
    assert int(first["observation_age_days"]) >= 7
    assert math.isfinite(later["infect_emv_21d_rank_252"])
    assert math.isfinite(later["infect_emv_5d_change_rank_252"])
    assert math.isfinite(later["infect_emv_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    emv_rank: float = 0.5,
    change_rank: float = 0.5,
    seven_day_rank: float = 0.5,
    one_day_rank: float = 0.5,
    name: str = "infect_emv.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,"
        "observation_age_days,infect_emv_1d,infect_emv_7d,infect_emv_21d,"
        "infect_emv_5d_change,infect_emv_21d_change,infect_emv_1d_rank_252,"
        "infect_emv_7d_rank_252,infect_emv_21d_rank_252,infect_emv_5d_change_rank_252,"
        "infect_emv_21d_change_rank_252\n"
        f"{session_date},2024-03-26,2024-03-27,7,8,12,13,14,2,3,"
        f"{one_day_rank},{seven_day_rank},{emv_rank},{change_rank},0.55\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp: str, *, close: float, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": close - 5.0,
            "high": close + 10.0,
            "low": close - 10.0,
            "close": close,
        }
    )


def _write_infect_emv_csv(path, dates) -> None:
    rows = ["observation_date,INFECTDISEMVTRACKD"]
    for index, day in enumerate(dates):
        value = 10 + (index % 47) + ((index // 29) % 7)
        rows.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(rows), encoding="utf-8")
