from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.corporate_equity_supply_state import (
    CorporateEquitySupplyStateEntry,
)
from tools.build_nq_corporate_equity_supply_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["corporate_equity_supply_state"] is CorporateEquitySupplyStateEntry


def test_high_1q_net_equity_short_emits_only_on_completed_entry_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", net_equity_rank=0.86)
    entry = CorporateEquitySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_1q_net_equity_short",
            "rank_column": "net_equity_to_market_1q_rank_40q",
            "value_column": "net_equity_to_market_1q",
            "supply_rank_threshold": 0.25,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["corporate_supply_rank_column"] == "net_equity_to_market_1q_rank_40q"


def test_high_equity_share_requires_high_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", equity_share_rank=0.62)
    entry = CorporateEquitySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_equity_share_short",
            "rank_column": "equity_financing_share_4q_rank_40q",
            "value_column": "equity_financing_share_4q",
            "supply_rank_threshold": 0.30,
            "entry_time": "12:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-04",
        equity_share_rank=0.88,
        name="high_equity_share.csv",
    )
    entry = CorporateEquitySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_equity_share_short",
            "rank_column": "equity_financing_share_4q_rank_40q",
            "value_column": "equity_financing_share_4q",
            "supply_rank_threshold": 0.30,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_low_debt_minus_equity_uses_low_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", debt_minus_equity_rank=0.18)
    entry = CorporateEquitySupplyStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_debt_minus_equity_short",
            "rank_column": "debt_minus_equity_to_market_4q_rank_40q",
            "value_column": "debt_minus_equity_to_market_4q",
            "supply_rank_threshold": 0.25,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["corporate_supply_value_column"] == "debt_minus_equity_to_market_4q"


def test_builder_uses_180_calendar_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-07-15", periods=260, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    source_dir = tmp_path / "fred"
    source_dir.mkdir()
    quarter_dates = pd.date_range("2008-01-01", "2024-10-01", freq="QS")
    _write_series(source_dir / "NCBCEBQ027S.csv", "NCBCEBQ027S", quarter_dates, 10000.0)
    _write_series(source_dir / "BOGZ1FA104104005Q.csv", "BOGZ1FA104104005Q", quarter_dates, 50000.0)
    _write_series(source_dir / "NCBEILQ027S.csv", "NCBEILQ027S", quarter_dates, 1000000.0)
    out_path = tmp_path / "features.csv"

    features = build_features(
        bars_path,
        out_path,
        source_dir=source_dir,
        publication_lag_calendar_days=180,
        download_if_missing=False,
    )

    first = features.loc[features["session_date"] == "2024-07-15"].iloc[0]
    later = features.iloc[-1]
    assert first["availability_cutoff"] == "2024-01-17"
    assert first["observation_date"] <= "2024-01-17"
    assert int(first["observation_age_days"]) >= 180
    assert math.isfinite(later["net_equity_to_market_4q_rank_40q"])
    assert math.isfinite(later["equity_share_4q_change_rank_40q"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    net_equity_rank: float = 0.5,
    equity_share_rank: float = 0.5,
    debt_minus_equity_rank: float = 0.5,
    name: str = "corporate_supply.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,"
        "observation_age_days,net_equity_issuance_1q,debt_financing_1q,"
        "equity_market_value,net_equity_issuance_4q,debt_financing_4q,"
        "net_equity_to_market_1q,net_equity_to_market_4q,"
        "debt_minus_equity_to_market_4q,equity_financing_share_4q,"
        "net_equity_issuance_4q_change,equity_share_4q_change,"
        "net_equity_to_market_1q_rank_40q,net_equity_to_market_4q_rank_40q,"
        "debt_minus_equity_to_market_4q_rank_40q,equity_financing_share_4q_rank_40q,"
        "net_equity_issuance_4q_change_rank_40q,equity_share_4q_change_rank_40q\n"
        f"{session_date},2023-10-01,2023-10-06,180,185,5000,20000,1000000,"
        "25000,85000,0.005,0.025,0.060,0.227,20000,0.12,"
        f"{net_equity_rank},0.80,{debt_minus_equity_rank},{equity_share_rank},0.81,0.82\n",
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


def _write_series(path, series_id: str, dates, base: float) -> None:
    rows = ["observation_date," + series_id]
    for index, day in enumerate(dates):
        value = base + (index % 17) * base * 0.03 + (index // 8) * base * 0.01
        rows.append(f"{day:%Y-%m-%d},{value:.2f}")
    path.write_text("\n".join(rows), encoding="utf-8")
