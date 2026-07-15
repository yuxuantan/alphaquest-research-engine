from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_trade_balance_quantity_state import (
    NqTradeBalanceQuantityStateEntry,
)
from tools.build_nq_trade_balance_quantity_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_trade_balance_quantity_state"] is NqTradeBalanceQuantityStateEntry


def test_strong_trade_balance_share_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", trade_balance_rank=0.72)
    entry = NqTradeBalanceQuantityStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "strong_trade_balance_share_long",
            "rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 09:58", close=19000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-01 09:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-01 10:00")
    assert signal.report_fields["trade_balance_driver_column"] == "trade_balance_to_trade_rank_120m"
    assert "60 calendar days" in signal.report_fields["availability_rule"]


def test_weak_import_growth_emits_short_on_low_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", imports_rank=0.22)
    entry = NqTradeBalanceQuantityStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "weak_import_growth_short",
            "rank_max": 0.35,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-01 11:59", close=19005.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["trade_balance_driver_column"] == "imports_change_3m_rank_120m"


def test_export_growth_strength_requires_high_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-01", exports_rank=0.54)
    entry = NqTradeBalanceQuantityStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "export_growth_strength_long",
            "rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-01 11:29", close=19005.0)) is None


def test_builder_uses_60_day_cutoff_and_trade_ratios(tmp_path):
    sessions = pd.date_range("2024-04-01", periods=20, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    dates = pd.date_range("2018-01-01", "2024-04-01", freq="MS")
    _write_fred_cache(cache_dir / "fred_bopgstb_monthly.csv", "BOPGSTB", dates, -50000.0)
    _write_fred_cache(cache_dir / "fred_bopgexp_monthly.csv", "BOPGEXP", dates, 200000.0)
    _write_fred_cache(cache_dir / "fred_bopgimp_monthly.csv", "BOPGIMP", dates, 260000.0)

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
    assert math.isfinite(first["trade_balance_to_trade_rank_120m"])
    assert math.isfinite(first["export_import_ratio"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    trade_balance_rank: float = 0.5,
    ratio_rank: float = 0.5,
    exports_rank: float = 0.5,
    imports_rank: float = 0.5,
    balance_change_rank: float = 0.5,
):
    path = tmp_path / "trade_balance.csv"
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "trade_balance,exports,imports,trade_balance_to_trade,export_import_ratio,"
        "exports_change_3m,imports_change_3m,balance_change_3m,export_minus_import_growth_3m,"
        "trade_balance_to_trade_rank_120m,export_import_ratio_rank_120m,"
        "exports_change_3m_rank_120m,imports_change_3m_rank_120m,"
        "balance_change_3m_rank_120m,export_minus_import_growth_3m_rank_120m\n"
        f"{session_date},2024-02-01,2024-02-01,60,-50000,200000,260000,-0.1087,0.7692,"
        f"0.04,0.02,10000,0.02,{trade_balance_rank},{ratio_rank},{exports_rank},"
        f"{imports_rank},{balance_change_rank},0.5\n",
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
