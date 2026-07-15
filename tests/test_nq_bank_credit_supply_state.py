from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_bank_credit_supply_state import (
    NqBankCreditSupplyStateEntry,
)
from tools.build_nq_bank_credit_supply_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_bank_credit_supply_state"] is NqBankCreditSupplyStateEntry


def test_high_bank_credit_growth_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", bank_credit_rank=0.72)
    entry = NqBankCreditSupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_bank_credit_growth_long",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["bank_credit_driver_column"] == "bank_credit_change_13w_rank_260w"
    assert "14 calendar days" in signal.report_fields["availability_rule"]


def test_high_deposits_growth_requires_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", deposits_rank=0.54)
    entry = NqBankCreditSupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_deposits_growth_long",
            "rank_min": 0.65,
            "entry_time": "12:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 11:59", close=19005.0)) is None


def test_high_ci_loans_growth_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", ci_rank=0.82)
    entry = NqBankCreditSupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_ci_loans_growth_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 11:29", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["bank_credit_driver_column"] == "ci_loans_change_13w_rank_260w"


def test_builder_uses_14_day_cutoff_and_weekly_ranks(tmp_path):
    sessions = pd.date_range("2024-04-01", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2018-01-03", "2024-04-03", freq="W-WED")
    _write_fred_cache(cache_dir / "fred_totbkcr_weekly.csv", "TOTBKCR", dates, 10000.0)
    _write_fred_cache(cache_dir / "fred_totll_weekly.csv", "TOTLL", dates, 7000.0)
    _write_fred_cache(cache_dir / "fred_totci_weekly.csv", "TOTCI", dates, 2000.0)
    _write_fred_cache(cache_dir / "fred_dpsacbw027sbog_weekly.csv", "DPSACBW027SBOG", dates, 12000.0)
    _write_fred_cache(cache_dir / "fred_tlaacbw027sbog_weekly.csv", "TLAACBW027SBOG", dates, 16000.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
    )
    first = features.loc[features["session_date"] == "2024-04-01"].iloc[0]
    assert first["observation_cutoff"] == "2024-03-18"
    assert first["observation_date"] == "2024-03-13"
    assert math.isfinite(first["bank_credit_change_13w_rank_260w"])
    assert math.isfinite(first["loan_to_asset"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    bank_credit_rank: float = 0.5,
    loans_rank: float = 0.5,
    ci_rank: float = 0.5,
    deposits_rank: float = 0.5,
    assets_rank: float = 0.5,
):
    path = tmp_path / "bank_credit.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "bank_credit,loans_leases,ci_loans,deposits,total_assets,"
        "bank_credit_change_4w,bank_credit_change_13w,loans_leases_change_4w,"
        "loans_leases_change_13w,ci_loans_change_4w,ci_loans_change_13w,"
        "deposits_change_4w,deposits_change_13w,total_assets_change_4w,"
        "total_assets_change_13w,loan_to_asset,ci_to_loans,deposit_to_asset,"
        "bank_credit_change_13w_rank_260w,loans_leases_change_4w_rank_260w,"
        "ci_loans_change_13w_rank_260w,deposits_change_13w_rank_260w,"
        "total_assets_change_4w_rank_260w,loan_to_asset_rank_260w,"
        "ci_to_loans_rank_260w,deposit_to_asset_rank_260w\n"
        f"{session_date},2024-03-18,2024-03-13,14,10000,7000,2000,12000,16000,"
        f"0.01,0.03,0.01,0.02,0.01,0.04,0.01,0.03,0.01,0.02,0.44,0.29,0.75,"
        f"{bank_credit_rank},{loans_rank},{ci_rank},{deposits_rank},{assets_rank},0.5,0.5,0.5\n",
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
        value = start_value + index * 10.0
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
