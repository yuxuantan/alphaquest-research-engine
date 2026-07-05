from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.treasury_term_premium_state import (
    TreasuryTermPremiumStateEntry,
)
from tools.build_nq_treasury_term_premium_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["treasury_term_premium_state"] is TreasuryTermPremiumStateEntry


def test_high_21d_short_emits_only_on_completed_entry_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", term_rank=0.86)
    entry = TreasuryTermPremiumStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_21d_term_premium_short",
            "rank_column": "term_premium_10y_21d_rank_252",
            "value_column": "term_premium_10y_21d",
            "term_premium_rank_threshold": 0.25,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["term_premium_rank_column"] == "term_premium_10y_21d_rank_252"


def test_high_21d_rebound_requires_high_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", term_rank=0.72)
    entry = TreasuryTermPremiumStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_21d_term_premium_rebound_long",
            "rank_column": "term_premium_10y_21d_rank_252",
            "value_column": "term_premium_10y_21d",
            "term_premium_rank_threshold": 0.25,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", term_rank=0.91, name="high.csv")
    entry = TreasuryTermPremiumStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_21d_term_premium_rebound_long",
            "rank_column": "term_premium_10y_21d_rank_252",
            "value_column": "term_premium_10y_21d",
            "term_premium_rank_threshold": 0.25,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"


def test_falling_21d_uses_low_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", change_rank=0.31)
    entry = TreasuryTermPremiumStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "falling_21d_term_premium_rebound_long",
            "rank_column": "term_premium_10y_21d_change_rank_252",
            "value_column": "term_premium_10y_21d_change",
            "term_premium_rank_threshold": 0.35,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["term_premium_value_column"] == "term_premium_10y_21d_change"


def test_builder_uses_7_calendar_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-04-15", periods=180, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    term_path = tmp_path / "term_premium.csv"
    _write_term_premium_csv(term_path, pd.date_range("2023-01-01", "2024-12-31", freq="B"))
    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        term_premium_csv_path=term_path,
        publication_lag_calendar_days=7,
        download_if_missing=False,
    )

    first = features.loc[features["session_date"] == "2024-04-15"].iloc[0]
    later = features.iloc[-1]
    assert first["availability_cutoff"] == "2024-04-08"
    assert first["observation_date"] <= "2024-04-08"
    assert int(first["observation_age_days"]) >= 7
    assert math.isfinite(later["term_premium_10y_21d_rank_252"])
    assert math.isfinite(later["term_premium_10y_5d_change_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    term_rank: float = 0.5,
    change_rank: float = 0.5,
    five_day_rank: float = 0.5,
    name: str = "term_premium.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,"
        "observation_age_days,term_premium_10y_1d,term_premium_10y_5d,"
        "term_premium_10y_21d,term_premium_10y_5d_change,term_premium_10y_21d_change,"
        "term_premium_10y_1d_rank_252,term_premium_10y_5d_rank_252,"
        "term_premium_10y_21d_rank_252,term_premium_10y_5d_change_rank_252,"
        "term_premium_10y_21d_change_rank_252\n"
        f"{session_date},2024-03-26,2024-03-27,7,8,0.5,0.45,0.42,0.04,-0.03,"
        f"0.50,{five_day_rank},{term_rank},0.80,{change_rank}\n",
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


def _write_term_premium_csv(path, dates) -> None:
    rows = ["observation_date,THREEFYTP10"]
    for index, day in enumerate(dates):
        value = 0.25 + (index % 61) / 100.0 + ((index // 37) % 5) / 50.0
        rows.append(f"{day:%Y-%m-%d},{value:.4f}")
    path.write_text("\n".join(rows), encoding="utf-8")
