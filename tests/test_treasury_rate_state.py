from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.treasury_rate_state import TreasuryRateStateEntry
from tools.build_es_treasury_rate_state_features import build_features


def test_rate_up_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.82)
    entry = TreasuryRateStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rate_up_short",
            "rate_change_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["rate_driver_column"] == "dgs10_change_1d_rank_252"
    assert signal.report_fields["treasury_observation_date"] == "2024-01-02"


def test_rate_down_entry_emits_long(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.18)
    entry = TreasuryRateStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rate_down_long",
            "rate_change_rank_max": 0.35,
            "entry_time": "10:00:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"


def test_bear_steepening_requires_rate_and_curve_conditions(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", change_rank=0.82, curve_rank=0.4)
    entry = TreasuryRateStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "bear_steepening_short",
            "rate_change_rank_min": 0.65,
            "curve_change_rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=4801.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-01-04",
        change_rank=0.82,
        curve_rank=0.8,
        name="steepening.csv",
    )
    entry = TreasuryRateStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "bear_steepening_short",
            "rate_change_rank_min": 0.65,
            "curve_change_rank_min": 0.65,
            "entry_time": "10:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-01-04 09:59", close=4801.0)) is not None


def test_rate_state_builder_uses_prior_treasury_observation_only(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=90, freq="B")
    bars = []
    rates = []
    for i, session in enumerate(sessions):
        day = session.strftime("%Y-%m-%d")
        bars.append({"timestamp": pd.Timestamp(f"{day} 09:30")})
        bars.append({"timestamp": pd.Timestamp(f"{day} 09:31")})
        rates.append(
            {
                "observation_date": day,
                "DGS10": 4.0 + i * 0.01,
                "DGS2": 3.5 + i * 0.005,
            }
        )
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    rates_path = tmp_path / "rates.csv"
    pd.DataFrame(rates).to_csv(rates_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path, rates_input=rates_path, rank_min_periods=3)

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[70].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["dgs10"] == 4.0
    assert math.isfinite(late["dgs10_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    change_rank: float,
    curve_rank: float = 0.8,
    level_rank: float = 0.8,
    name: str = "rates.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,dgs10,dgs2,curve_10y2y,dgs10_change_1d,"
        "dgs2_change_1d,curve_change_1d,dgs10_change_5d,curve_change_5d,"
        "dgs10_rank_252,dgs2_rank_252,curve_10y2y_rank_252,"
        "dgs10_change_1d_rank_252,dgs2_change_1d_rank_252,"
        "curve_change_1d_rank_252,dgs10_change_5d_rank_252,"
        "curve_change_5d_rank_252\n"
        f"{session_date},2024-01-02,4.1,3.8,0.3,0.05,0.02,0.03,0.12,0.08,"
        f"{level_rank},0.7,0.6,{change_rank},0.7,{curve_rank},0.7,0.7\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.5,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000,
        }
    )
