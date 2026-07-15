from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_labor_market_slack_state import (
    NqLaborMarketSlackStateEntry,
)
from tools.build_nq_labor_market_slack_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_labor_market_slack_state"] is NqLaborMarketSlackStateEntry


def test_high_unemployment_slack_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", unemployment_rank=0.72)
    entry = NqLaborMarketSlackStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_unemployment_slack_short",
            "rank_threshold": 0.60,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["labor_driver_column"] == "unemployment_rate_rank_120m"
    assert "45 calendar days" in signal.report_fields["availability_rule"]


def test_low_employment_ratio_uses_inverse_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", employment_ratio_rank=0.39)
    entry = NqLaborMarketSlackStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_employment_ratio_slack_short",
            "rank_threshold": 0.60,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 11:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["effective_cutoff"] == 0.4


def test_rising_participation_repair_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", participation_change_rank=0.66)
    entry = NqLaborMarketSlackStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_participation_repair_long",
            "rank_threshold": 0.60,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 13:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["labor_driver_column"] == "participation_rate_change_3m_rank_120m"


def test_builder_uses_45_day_cutoff_and_monthly_ranks(tmp_path):
    sessions = pd.date_range("2024-04-15", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2014-01-01", "2024-04-01", freq="MS")
    _write_fred_cache(cache_dir / "fred_unrate_monthly.csv", "UNRATE", dates, 4.0)
    _write_fred_cache(cache_dir / "fred_u6rate_monthly.csv", "U6RATE", dates, 8.0)
    _write_fred_cache(cache_dir / "fred_emratio_monthly.csv", "EMRATIO", dates, 58.0)
    _write_fred_cache(cache_dir / "fred_civpart_monthly.csv", "CIVPART", dates, 62.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_window_months=24,
        rank_min_periods=12,
    )
    first = features.loc[features["session_date"] == "2024-04-15"].iloc[0]
    assert first["observation_cutoff"] == "2024-03-01"
    assert first["observation_date"] == "2024-03-01"
    assert math.isfinite(first["unemployment_rate_rank_120m"])
    assert math.isfinite(first["participation_rate_change_3m_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    unemployment_rank: float = 0.5,
    underemployment_rank: float = 0.5,
    employment_ratio_rank: float = 0.5,
    participation_rank: float = 0.5,
    participation_change_rank: float = 0.5,
):
    path = tmp_path / "labor_market.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "unemployment_rate,underemployment_rate,employment_population_ratio,participation_rate,"
        "unemployment_rate_rank_120m,underemployment_rate_rank_120m,"
        "employment_population_ratio_rank_120m,participation_rate_rank_120m,"
        "participation_rate_change_3m,participation_rate_change_3m_rank_120m\n"
        f"{session_date},2024-02-16,2024-02-01,45,4.1,8.0,59.0,62.0,"
        f"{unemployment_rank},{underemployment_rank},{employment_ratio_rank},"
        f"{participation_rank},0.2,{participation_change_rank}\n",
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


def _write_fred_cache(path, series_id: str, dates, start_value: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["observation_date," + series_id]
    for index, day in enumerate(dates):
        value = start_value + index * 0.01
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
