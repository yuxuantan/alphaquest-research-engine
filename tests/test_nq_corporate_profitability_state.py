from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_corporate_profitability_state import (
    NqCorporateProfitabilityStateEntry,
)
from tools.build_nq_corporate_profitability_state_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_corporate_profitability_state"]
        is NqCorporateProfitabilityStateEntry
    )


def test_high_corporate_profit_growth_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", corporate_yoy_rank=0.72)
    entry = NqCorporateProfitabilityStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_corporate_profit_yoy_growth_long",
            "rank_min": 0.60,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["profitability_driver_column"] == "corporate_profits_growth_4q_rank_80q"
    assert "120 calendar days" in signal.report_fields["availability_rule"]


def test_after_tax_profit_margin_requires_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", after_tax_margin_rank=0.54)
    entry = NqCorporateProfitabilityStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_after_tax_profit_margin_long",
            "rank_min": 0.60,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 11:29", close=19005.0)) is None


def test_corporate_qoq_growth_uses_1q_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", corporate_qoq_rank=0.66)
    entry = NqCorporateProfitabilityStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_corporate_profit_qoq_growth_long",
            "rank_min": 0.60,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 13:29", close=19005.0))
    assert signal is not None
    assert signal.report_fields["profitability_driver_column"] == "corporate_profits_growth_1q_rank_80q"


def test_builder_uses_120_day_cutoff_and_quarterly_ranks(tmp_path):
    sessions = pd.date_range("2024-06-03", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2016-01-01", "2024-04-01", freq="QS")
    _write_fred_cache(cache_dir / "fred_cprofit_quarterly.csv", "CPROFIT", dates, 1000.0)
    _write_fred_cache(cache_dir / "fred_cpatax_quarterly.csv", "CPATAX", dates, 800.0)
    _write_fred_cache(cache_dir / "fred_gdp_quarterly.csv", "GDP", dates, 20000.0)

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
    assert math.isfinite(first["corporate_profits_growth_4q_rank_80q"])
    assert math.isfinite(first["after_tax_profit_gdp_share_rank_80q"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    corporate_yoy_rank: float = 0.5,
    after_tax_yoy_rank: float = 0.5,
    after_tax_margin_rank: float = 0.5,
    corporate_margin_rank: float = 0.5,
    corporate_qoq_rank: float = 0.5,
):
    path = tmp_path / "corporate_profitability.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "corporate_profits,after_tax_profits,gdp,corporate_profits_growth_1q,"
        "corporate_profits_growth_4q,after_tax_profits_growth_1q,"
        "after_tax_profits_growth_4q,corporate_profit_gdp_share,"
        "after_tax_profit_gdp_share,corporate_profits_growth_1q_rank_80q,"
        "corporate_profits_growth_4q_rank_80q,after_tax_profits_growth_1q_rank_80q,"
        "after_tax_profits_growth_4q_rank_80q,corporate_profit_gdp_share_rank_80q,"
        "after_tax_profit_gdp_share_rank_80q\n"
        f"{session_date},2024-02-04,2024-01-01,120,1000,800,20000,"
        f"0.02,0.08,0.01,0.07,0.05,0.04,{corporate_qoq_rank},"
        f"{corporate_yoy_rank},0.5,{after_tax_yoy_rank},{corporate_margin_rank},"
        f"{after_tax_margin_rank}\n",
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
        value = start_value + index * 25.0
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
