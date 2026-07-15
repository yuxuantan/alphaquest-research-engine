from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_industrial_production_state import (
    NqIndustrialProductionStateEntry,
)
from tools.build_nq_industrial_production_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_industrial_production_state"] is NqIndustrialProductionStateEntry


def test_ipman_weakness_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", ipman_3m_rank=0.24)
    entry = NqIndustrialProductionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "ipman_3m_weakness_long",
            "rank_max": 0.40,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["industrial_production_driver_column"] == (
        "ipman_change_3m_rank_120m"
    )
    assert "45 calendar days" in signal.report_fields["availability_rule"]


def test_ipman_strength_emits_short_only_above_rank_min(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", ipman_3m_rank=0.58)
    entry = NqIndustrialProductionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "ipman_3m_strength_short",
            "rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", ipman_3m_rank=0.83, name="strong.csv")
    entry = NqIndustrialProductionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "ipman_3m_strength_short",
            "rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_cumfns_weakness_long_uses_capacity_change_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", cumfns_3m_rank=0.30)
    entry = NqIndustrialProductionStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "cumfns_3m_weakness_long",
            "rank_max": 0.50,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["industrial_production_driver_column"] == (
        "cumfns_change_3m_rank_120m"
    )


def test_builder_uses_monthly_observations_at_least_45_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-03-18", periods=85, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    months = pd.date_range("2017-01-01", "2024-06-01", freq="MS")
    _write_fred_csv(cache_dir / "fred_ipman_monthly.csv", "IPMAN", months, 95.0)
    _write_fred_csv(cache_dir / "fred_indpro_monthly.csv", "INDPRO", months, 100.0)
    _write_fred_csv(cache_dir / "fred_cumfns_monthly.csv", "CUMFNS", months, 74.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        availability_lag_days=45,
        rank_min_periods=6,
        start_session="2024-03-18",
    )

    first = features.loc[features["session_date"] == "2024-03-18"].iloc[0]
    later = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-02-01"
    assert math.isfinite(later["ipman_change_3m_rank_120m"])
    assert math.isfinite(later["indpro_change_3m_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    ipman_3m_rank: float = 0.5,
    ipman_6m_rank: float = 0.5,
    indpro_3m_rank: float = 0.5,
    cumfns_rank: float = 0.5,
    cumfns_3m_rank: float = 0.5,
    name: str = "ip.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "ipman,indpro,cumfns,ipman_change_1m,ipman_change_3m,ipman_change_6m,"
        "indpro_change_3m,cumfns_change_3m,ipman_rank_120m,cumfns_rank_120m,"
        "ipman_change_3m_rank_120m,ipman_change_6m_rank_120m,"
        "indpro_change_3m_rank_120m,cumfns_change_3m_rank_120m\n"
        f"{session_date},2024-02-18,2024-02-01,45,98,102,75,0.001,0.003,"
        f"0.005,0.004,0.002,0.55,{cumfns_rank},{ipman_3m_rank},"
        f"{ipman_6m_rank},{indpro_3m_rank},{cumfns_3m_rank}\n",
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


def _write_fred_csv(path, series_id: str, dates, start_value: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["observation_date," + series_id]
    for index, day in enumerate(dates):
        value = start_value + index * 0.1
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
