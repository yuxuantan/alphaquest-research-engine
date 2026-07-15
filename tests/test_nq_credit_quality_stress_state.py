from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_credit_quality_stress_state import (
    NqCreditQualityStressStateEntry,
)
from tools.build_nq_credit_quality_stress_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_credit_quality_stress_state"] is NqCreditQualityStressStateEntry


def test_high_credit_card_chargeoff_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", credit_card_chargeoff_rank=0.72)
    entry = NqCreditQualityStressStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_credit_card_chargeoff_short",
            "rank_threshold": 0.60,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["credit_quality_driver_column"] == "credit_card_chargeoff_rank_80q"
    assert "120 calendar days" in signal.report_fields["availability_rule"]


def test_falling_consumer_delinquency_uses_inverse_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", consumer_delinquency_change_rank=0.39)
    entry = NqCreditQualityStressStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "falling_consumer_loan_delinquency_long",
            "rank_threshold": 0.60,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 13:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["rank_side_cutoff"] == 0.4


def test_business_chargeoff_requires_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", business_chargeoff_rank=0.54)
    entry = NqCreditQualityStressStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_business_loan_chargeoff_short",
            "rank_threshold": 0.60,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 10:29", close=19005.0)) is None


def test_builder_uses_120_day_cutoff_and_quarterly_ranks(tmp_path):
    sessions = pd.date_range("2024-06-03", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2016-01-01", "2024-04-01", freq="QS")
    _write_fred_cache(cache_dir / "fred_drcclacbs_quarterly.csv", "DRCCLACBS", dates, 3.0)
    _write_fred_cache(cache_dir / "fred_drclacbs_quarterly.csv", "DRCLACBS", dates, 2.0)
    _write_fred_cache(cache_dir / "fred_corcct100s_quarterly.csv", "CORCCT100S", dates, 1.0)
    _write_fred_cache(cache_dir / "fred_corblacbs_quarterly.csv", "CORBLACBS", dates, 0.8)
    _write_fred_cache(cache_dir / "fred_coralacbn_quarterly.csv", "CORALACBN", dates, 0.6)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_window_quarters=16,
        rank_min_periods=8,
    )
    first = features.loc[features["session_date"] == "2024-06-03"].iloc[0]
    assert first["observation_cutoff"] == "2024-02-04"
    assert first["observation_date"] == "2024-01-01"
    assert math.isfinite(first["credit_card_chargeoff_rank_80q"])
    assert math.isfinite(first["consumer_loan_delinquency_change_4q_rank_80q"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    credit_card_delinquency_change_rank: float = 0.5,
    consumer_delinquency_change_rank: float = 0.5,
    credit_card_chargeoff_rank: float = 0.5,
    business_chargeoff_rank: float = 0.5,
    all_chargeoff_rank: float = 0.5,
):
    path = tmp_path / "credit_quality.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "credit_card_delinquency,consumer_loan_delinquency,credit_card_chargeoff,"
        "business_loan_chargeoff,all_loan_chargeoff,credit_card_delinquency_change_4q,"
        "consumer_loan_delinquency_change_4q,credit_card_chargeoff_change_4q,"
        "business_loan_chargeoff_change_4q,all_loan_chargeoff_change_4q,"
        "credit_card_delinquency_change_4q_rank_80q,"
        "consumer_loan_delinquency_change_4q_rank_80q,credit_card_chargeoff_rank_80q,"
        "business_loan_chargeoff_rank_80q,all_loan_chargeoff_rank_80q\n"
        f"{session_date},2024-02-04,2024-01-01,120,3,2,1,0.8,0.6,"
        f"-0.2,-0.1,0.1,0.05,0.02,{credit_card_delinquency_change_rank},"
        f"{consumer_delinquency_change_rank},{credit_card_chargeoff_rank},"
        f"{business_chargeoff_rank},{all_chargeoff_rank}\n",
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
        value = start_value + index * 0.1
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
