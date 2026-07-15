from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_jobless_claims_state import (
    NqJoblessClaimsStateEntry,
)
from tools.build_nq_jobless_claims_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_jobless_claims_state"] is NqJoblessClaimsStateEntry


def test_low_claims_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", initial_claims_rank=0.24)
    entry = NqJoblessClaimsStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "claims_low_long",
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
    assert signal.report_fields["jobless_claims_driver_column"] == "initial_claims_4w_rank_156w"
    assert "7 calendar days" in signal.report_fields["availability_rule"]


def test_high_claims_short_respects_rank_min(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", initial_claims_rank=0.54)
    entry = NqJoblessClaimsStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "claims_high_short",
            "rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", initial_claims_rank=0.82, name="high.csv")
    entry = NqJoblessClaimsStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "claims_high_short",
            "rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_claims_rising_short_uses_four_week_change_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", initial_claims_change_4w_rank=0.88)
    entry = NqJoblessClaimsStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "claims_rising_short",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["jobless_claims_driver_column"] == (
        "initial_claims_4w_change_4w_rank_156w"
    )


def test_continued_claims_rising_short_uses_continued_claims_change_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", continued_claims_change_1w_rank=0.77)
    entry = NqJoblessClaimsStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "continued_claims_rising_short",
            "rank_min": 0.65,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["jobless_claims_driver_column"] == (
        "continued_claims_4w_change_1w_rank_156w"
    )


def test_builder_uses_weekly_observations_at_least_7_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-03-18", periods=85, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    weeks = pd.date_range("2021-01-02", "2024-06-22", freq="W-SAT")
    _write_fred_csv(cache_dir / "fred_icsa_weekly.csv", "ICSA", weeks, 210000.0)
    _write_fred_csv(cache_dir / "fred_ic4wsa_weekly.csv", "IC4WSA", weeks, 215000.0)
    _write_fred_csv(cache_dir / "fred_ccsa_weekly.csv", "CCSA", weeks, 1700000.0)
    _write_fred_csv(cache_dir / "fred_cc4wsa_weekly.csv", "CC4WSA", weeks, 1710000.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        availability_lag_days=7,
        rank_min_periods=12,
        start_session="2024-03-18",
    )

    first = features.loc[features["session_date"] == "2024-03-18"].iloc[0]
    later = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-03-09"
    assert math.isfinite(later["initial_claims_4w_rank_156w"])
    assert math.isfinite(later["continued_claims_4w_rank_156w"])
    assert math.isfinite(later["initial_claims_4w_change_4w_rank_156w"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    initial_claims_rank: float = 0.5,
    continued_claims_rank: float = 0.5,
    initial_claims_change_1w_rank: float = 0.5,
    initial_claims_change_4w_rank: float = 0.5,
    continued_claims_change_1w_rank: float = 0.5,
    name: str = "claims.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "initial_claims,initial_claims_4w,continued_claims,continued_claims_4w,"
        "initial_claims_4w_change_1w,initial_claims_4w_change_4w,"
        "continued_claims_4w_change_1w,continued_claims_4w_change_4w,"
        "initial_claims_4w_rank_156w,continued_claims_4w_rank_156w,"
        "initial_claims_4w_change_1w_rank_156w,initial_claims_4w_change_4w_rank_156w,"
        "continued_claims_4w_change_1w_rank_156w,continued_claims_4w_change_4w_rank_156w\n"
        f"{session_date},2024-03-27,2024-03-23,7,215000,220000,1800000,1810000,"
        f"0.01,0.03,0.01,0.02,{initial_claims_rank},{continued_claims_rank},"
        f"{initial_claims_change_1w_rank},{initial_claims_change_4w_rank},"
        f"{continued_claims_change_1w_rank},0.5\n",
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
        value = start_value + index * 10.0
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
