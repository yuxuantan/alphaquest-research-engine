from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.ofr_financial_stress import OfrFinancialStressEntry
from tools.build_es_ofr_financial_stress_features import build_features


def test_rising_global_stress_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", fsi_change_rank=0.82)
    entry = OfrFinancialStressEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_global_stress_short",
            "stress_change_rank_min": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-08 10:00")
    assert signal.report_fields["stress_driver_column"] == "ofr_fsi_change_1d_rank_252"
    assert signal.report_fields["ofr_observation_date"] == "2024-01-04"


def test_credit_stress_uses_level_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", credit_rank=0.8)
    entry = OfrFinancialStressEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_credit_stress_short",
            "stress_rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-08 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["stress_driver_column"] == "credit_rank_252"


def test_funding_stress_does_not_emit_below_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-01-08", funding_rank=0.4)
    entry = OfrFinancialStressEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "funding_stress_short",
            "stress_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-08 11:29", close=4801.0)) is None


def test_ofr_builder_uses_two_business_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=90, freq="B")
    bars = []
    ofr_rows = []
    for i, session in enumerate(sessions):
        day = session.strftime("%Y-%m-%d")
        bars.append({"timestamp": pd.Timestamp(f"{day} 09:30")})
        bars.append({"timestamp": pd.Timestamp(f"{day} 09:31")})
        ofr_rows.append(
            {
                "Date": day,
                "OFR FSI": i / 10,
                "Credit": i / 20,
                "Equity valuation": 0.1,
                "Safe assets": 0.2,
                "Funding": i / 30,
                "Volatility": i / 40,
                "United States": i / 50,
                "Other advanced economies": 0.3,
                "Emerging markets": 0.4,
            }
        )
    raw_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(raw_path)
    ofr_path = tmp_path / "ofr.csv"
    pd.DataFrame(ofr_rows).to_csv(ofr_path, index=False)
    out_path = tmp_path / "features.csv"

    features = build_features(raw_path, out_path, ofr_input=ofr_path, rank_min_periods=3)

    third = features.loc[features["session_date"] == sessions[2].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[70].strftime("%Y-%m-%d")].iloc[0]
    assert third["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert third["ofr_fsi"] == 0.0
    assert math.isfinite(late["ofr_fsi_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    fsi_change_rank: float = 0.7,
    credit_rank: float = 0.7,
    funding_rank: float = 0.7,
    us_rank: float = 0.7,
    volatility_rank: float = 0.7,
):
    path = tmp_path / "ofr_features.csv"
    path.write_text(
        "session_date,observation_date,ofr_fsi,credit,equity_valuation,safe_assets,"
        "funding,volatility,united_states,other_advanced_economies,emerging_markets,"
        "ofr_fsi_change_1d,credit_change_1d,funding_change_1d,volatility_change_1d,"
        "united_states_change_1d,ofr_fsi_change_5d,credit_change_5d,"
        "ofr_fsi_rank_252,credit_rank_252,funding_rank_252,volatility_rank_252,"
        "united_states_rank_252,ofr_fsi_change_1d_rank_252,credit_change_1d_rank_252,"
        "funding_change_1d_rank_252,volatility_change_1d_rank_252,"
        "united_states_change_1d_rank_252,ofr_fsi_change_5d_rank_252,"
        "credit_change_5d_rank_252\n"
        f"{session_date},2024-01-04,1.1,0.5,0.1,0.2,0.3,0.4,0.6,0.1,0.1,"
        f"0.2,0.1,0.1,0.1,0.1,0.4,0.2,0.7,{credit_rank},{funding_rank},"
        f"{volatility_rank},{us_rank},{fsi_change_rank},0.7,0.7,0.7,0.7,0.7,0.7\n",
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
