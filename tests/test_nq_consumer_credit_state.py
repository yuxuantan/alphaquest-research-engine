from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_consumer_credit_state import NqConsumerCreditStateEntry
from tools.build_nq_consumer_credit_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_consumer_credit_state"] is NqConsumerCreditStateEntry


def test_total_credit_contraction_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", total_credit_3m_rank=0.25)
    entry = NqConsumerCreditStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "total_credit_3m_contraction_short",
            "rank_max": 0.35,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["consumer_credit_driver_column"] == "total_credit_change_3m_rank_120m"
    assert "60 calendar days" in signal.report_fields["availability_rule"]


def test_revolving_three_month_relief_emits_long_on_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", revolving_credit_3m_rank=0.25)
    entry = NqConsumerCreditStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "revolving_credit_3m_relief_long",
            "rank_max": 0.35,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 10:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"


def test_low_credit_burden_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", revolving_credit_to_income_rank=0.18)
    entry = NqConsumerCreditStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "revolving_credit_to_income_low_long",
            "rank_max": 0.35,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 11:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["consumer_credit_driver_column"] == (
        "revolving_credit_to_income_rank_120m"
    )


def test_revolving_relief_long_requires_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", revolving_credit_1m_rank=0.46)
    entry = NqConsumerCreditStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "revolving_credit_1m_relief_long",
            "rank_max": 0.35,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 13:29", close=19005.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-02",
        revolving_credit_1m_rank=0.22,
        name="relief.csv",
    )
    entry = NqConsumerCreditStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "revolving_credit_1m_relief_long",
            "rank_max": 0.35,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-02 13:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"


def test_builder_uses_60_day_cutoff_and_income_scaling(tmp_path):
    sessions = pd.date_range("2024-04-01", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2018-01-01", "2024-04-01", freq="MS")
    _write_fred_cache(cache_dir / "fred_totalsl_monthly.csv", "TOTALSL", dates, 4000000.0)
    _write_fred_cache(cache_dir / "fred_revolsl_monthly.csv", "REVOLSL", dates, 1000000.0)
    _write_fred_cache(cache_dir / "fred_nonrevsl_monthly.csv", "NONREVSL", dates, 3000000.0)
    _write_fred_cache(cache_dir / "fred_dspi_monthly.csv", "DSPI", dates, 18000.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
    )
    first = features.loc[features["session_date"] == "2024-04-01"].iloc[0]
    assert first["observation_cutoff"] == "2024-02-01"
    assert first["observation_date"] == "2024-02-01"
    assert math.isfinite(first["total_credit_change_3m_rank_120m"])
    assert math.isclose(
        first["total_credit_to_income"],
        first["total_credit"] / (first["disposable_income"] * 1000.0),
    )


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    total_credit_3m_rank: float = 0.5,
    revolving_credit_1m_rank: float = 0.5,
    revolving_credit_3m_rank: float = 0.5,
    total_credit_to_income_rank: float = 0.5,
    revolving_share_rank: float = 0.5,
    revolving_credit_to_income_rank: float = 0.5,
    name: str = "consumer_credit.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "total_credit,revolving_credit,nonrevolving_credit,disposable_income,"
        "total_credit_change_1m,total_credit_change_3m,revolving_credit_change_1m,"
        "revolving_credit_change_3m,nonrevolving_credit_change_3m,revolving_credit_share,"
        "total_credit_to_income,revolving_credit_to_income,total_credit_change_1m_rank_120m,"
        "total_credit_change_3m_rank_120m,revolving_credit_change_1m_rank_120m,"
        "revolving_credit_change_3m_rank_120m,nonrevolving_credit_change_3m_rank_120m,"
        "revolving_credit_share_rank_120m,total_credit_to_income_rank_120m,"
        "revolving_credit_to_income_rank_120m\n"
        f"{session_date},2024-02-01,2024-02-01,60,5000000,1200000,3800000,20000,"
        f"0.002,0.006,-0.002,0.01,0.004,0.24,0.25,0.06,0.5,{total_credit_3m_rank},"
        f"{revolving_credit_1m_rank},{revolving_credit_3m_rank},0.5,{revolving_share_rank},"
        f"{total_credit_to_income_rank},{revolving_credit_to_income_rank}\n",
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
        value = start_value + index * 1000.0
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
