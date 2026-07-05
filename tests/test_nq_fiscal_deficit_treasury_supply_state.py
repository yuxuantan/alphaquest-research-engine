from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_fiscal_deficit_treasury_supply_state import (
    NqFiscalDeficitTreasurySupplyStateEntry,
)
from tools.build_nq_fiscal_deficit_treasury_supply_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_fiscal_deficit_treasury_supply_state"]
        is NqFiscalDeficitTreasurySupplyStateEntry
    )


def test_high_deficit_three_month_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", deficit_3m_rank=0.72)
    entry = NqFiscalDeficitTreasurySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_deficit_3m_short",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["fiscal_driver_column"] == "deficit_3m_sum_rank_120m"
    assert "60 calendar days" in signal.report_fields["availability_rule"]


def test_low_outlays_yoy_emits_long_on_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", outlays_yoy_rank=0.22)
    entry = NqFiscalDeficitTreasurySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_outlays_yoy_long",
            "rank_max": 0.35,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 11:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["fiscal_driver_column"] == "outlays_yoy_growth_rank_120m"


def test_strong_receipts_requires_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", receipts_yoy_rank=0.54)
    entry = NqFiscalDeficitTreasurySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "strong_receipts_yoy_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 11:29", close=19005.0)) is None


def test_builder_uses_60_day_cutoff_and_deficit_sign(tmp_path):
    sessions = pd.date_range("2024-04-01", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2018-01-01", "2024-04-01", freq="MS")
    _write_fred_cache(cache_dir / "fred_mtsds133fms_monthly.csv", "MTSDS133FMS", dates, -50000.0)
    _write_fred_cache(cache_dir / "fred_mtsr133fms_monthly.csv", "MTSR133FMS", dates, 300000.0)
    _write_fred_cache(cache_dir / "fred_mtso133fms_monthly.csv", "MTSO133FMS", dates, 400000.0)

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
    assert first["deficit"] == -first["fiscal_balance"]
    assert math.isfinite(first["deficit_3m_sum_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    deficit_3m_rank: float = 0.5,
    deficit_12m_rank: float = 0.5,
    receipts_yoy_rank: float = 0.5,
    outlays_yoy_rank: float = 0.5,
    fiscal_impulse_rank: float = 0.5,
):
    path = tmp_path / "fiscal.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "fiscal_balance,federal_receipts,federal_outlays,deficit,deficit_3m_sum,"
        "deficit_12m_sum,balance_3m_sum,receipts_yoy_growth,outlays_yoy_growth,"
        "fiscal_impulse_3m,deficit_change_3m,deficit_3m_sum_rank_120m,"
        "deficit_12m_sum_rank_120m,balance_3m_sum_rank_120m,receipts_yoy_growth_rank_120m,"
        "outlays_yoy_growth_rank_120m,fiscal_impulse_3m_rank_120m,deficit_change_3m_rank_120m\n"
        f"{session_date},2024-02-01,2024-02-01,60,-100000,300000,400000,"
        f"100000,300000,1200000,-300000,0.03,0.02,0.01,50000,{deficit_3m_rank},"
        f"{deficit_12m_rank},0.5,{receipts_yoy_rank},{outlays_yoy_rank},"
        f"{fiscal_impulse_rank},0.5\n",
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
