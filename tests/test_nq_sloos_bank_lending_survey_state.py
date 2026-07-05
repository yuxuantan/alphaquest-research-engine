from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_sloos_bank_lending_survey_state import (
    NqSloosBankLendingSurveyStateEntry,
)
from tools.build_nq_sloos_bank_lending_survey_state_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_sloos_bank_lending_survey_state"]
        is NqSloosBankLendingSurveyStateEntry
    )


def test_tight_large_ci_standards_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", ci_large_tightening_rank=0.72)
    entry = NqSloosBankLendingSurveyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tight_ci_large_standards_short",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["sloos_driver_column"] == "ci_large_tightening_rank_80q"
    assert "75 calendar days" in signal.report_fields["availability_rule"]


def test_strong_small_ci_demand_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", ci_small_demand_rank=0.82)
    entry = NqSloosBankLendingSurveyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "strong_ci_small_demand_long",
            "rank_min": 0.65,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 11:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["sloos_driver_column"] == "ci_small_demand_rank_80q"


def test_tight_credit_card_standards_requires_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", credit_card_tightening_rank=0.54)
    entry = NqSloosBankLendingSurveyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "tight_credit_card_standards_short",
            "rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 13:29", close=19005.0)) is None


def test_confirmed_ci_demand_uses_min_rank_composite(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", ci_demand_rank_min=0.66)
    entry = NqSloosBankLendingSurveyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "confirmed_ci_demand_strength_long",
            "rank_min": 0.60,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 13:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["sloos_driver_column"] == "ci_demand_rank_min_80q"


def test_builder_uses_75_day_cutoff_and_quarterly_ranks(tmp_path):
    sessions = pd.date_range("2024-04-15", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2016-01-01", "2024-04-01", freq="QS")
    _write_fred_cache(cache_dir / "fred_drtscilm_quarterly.csv", "DRTSCILM", dates, 10.0)
    _write_fred_cache(cache_dir / "fred_drtscis_quarterly.csv", "DRTSCIS", dates, 11.0)
    _write_fred_cache(cache_dir / "fred_drsdcilm_quarterly.csv", "DRSDCILM", dates, 12.0)
    _write_fred_cache(cache_dir / "fred_drsdcis_quarterly.csv", "DRSDCIS", dates, 13.0)
    _write_fred_cache(cache_dir / "fred_drtsclcc_quarterly.csv", "DRTSCLCC", dates, 14.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_window_quarters=16,
        rank_min_periods=8,
    )
    first = features.loc[features["session_date"] == "2024-04-15"].iloc[0]
    assert first["observation_cutoff"] == "2024-01-31"
    assert first["observation_date"] == "2024-01-01"
    assert math.isfinite(first["ci_large_tightening_rank_80q"])
    assert math.isfinite(first["credit_card_tightening_rank_80q"])
    assert math.isfinite(first["ci_demand_rank_average_80q"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    ci_large_tightening_rank: float = 0.5,
    ci_small_tightening_rank: float = 0.5,
    ci_large_demand_rank: float = 0.5,
    ci_small_demand_rank: float = 0.5,
    credit_card_tightening_rank: float = 0.5,
    ci_demand_rank_average: float = 0.5,
    ci_demand_rank_max: float = 0.5,
    ci_demand_rank_min: float = 0.5,
):
    path = tmp_path / "sloos.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "ci_large_tightening,ci_small_tightening,ci_large_demand,ci_small_demand,"
        "credit_card_tightening,ci_large_tightening_change_1q,"
        "ci_large_tightening_change_4q,ci_small_tightening_change_1q,"
        "ci_small_tightening_change_4q,ci_large_demand_change_1q,"
        "ci_large_demand_change_4q,ci_small_demand_change_1q,"
        "ci_small_demand_change_4q,credit_card_tightening_change_1q,"
        "credit_card_tightening_change_4q,ci_large_tightening_rank_80q,"
        "ci_small_tightening_rank_80q,ci_large_demand_rank_80q,"
        "ci_small_demand_rank_80q,credit_card_tightening_rank_80q,"
        "ci_demand_rank_average_80q,ci_demand_rank_max_80q,ci_demand_rank_min_80q\n"
        f"{session_date},2024-01-17,2024-01-01,75,8,7,5,4,2,"
        f"1,2,1,2,1,2,1,2,1,2,{ci_large_tightening_rank},"
        f"{ci_small_tightening_rank},{ci_large_demand_rank},"
        f"{ci_small_demand_rank},{credit_card_tightening_rank},"
        f"{ci_demand_rank_average},{ci_demand_rank_max},{ci_demand_rank_min}\n",
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
        value = start_value + index * 0.5
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
