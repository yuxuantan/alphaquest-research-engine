from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.real_yield_breakeven_state import RealYieldBreakevenStateEntry
from tools.build_nq_real_yield_breakeven_features import build_features


def test_real_yield_up_entry_emits_short_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", real_yield_rank=0.82)
    entry = RealYieldBreakevenStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "real_yield_1d_up_short",
            "direction_mode": "high_short",
            "value_column": "real_yield_change_1d",
            "rank_column": "real_yield_change_1d_rank_252",
            "state_rank_threshold": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=17000.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["state_rank_column"] == "real_yield_change_1d_rank_252"
    assert signal.report_fields["observation_date"] == "2024-01-02"


def test_real_yield_down_entry_emits_long_from_low_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", real_yield_rank=0.18)
    entry = RealYieldBreakevenStateEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "low_long",
            "rank_column": "real_yield_change_1d_rank_252",
            "value_column": "real_yield_change_1d",
            "state_rank_threshold": 0.65,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", close=17000.0))

    assert signal is not None
    assert signal.direction == "long"


def test_breakeven_entry_rejects_middle_rank_and_non_rth(tmp_path):
    features = _feature_file(tmp_path, "2024-01-03", breakeven_rank=0.50)
    entry = RealYieldBreakevenStateEntry(
        {
            "feature_csv": str(features),
            "direction_mode": "high_long",
            "rank_column": "breakeven_change_1d_rank_252",
            "value_column": "breakeven_change_1d",
            "state_rank_threshold": 0.60,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=17000.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:59", close=17000.0, is_rth=False)) is None


def test_real_yield_feature_builder_uses_prior_observation_only(tmp_path):
    bars = []
    sessions = pd.date_range("2024-01-02", periods=90, freq="B")
    for session in sessions:
        day = session.strftime("%Y-%m-%d")
        bars.append({"timestamp": pd.Timestamp(f"{day} 09:30", tz="America/New_York")})
        bars.append({"timestamp": pd.Timestamp(f"{day} 09:31", tz="America/New_York")})
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(bars).to_parquet(bars_path)

    dfii10_path, t10yie_path, dgs10_path = _rate_inputs(tmp_path, sessions)
    out_path = tmp_path / "features.csv"

    features = build_features(
        bars_path,
        out_path,
        dfii10_input=dfii10_path,
        t10yie_input=t10yie_path,
        dgs10_input=dgs10_path,
        rank_min_periods=3,
    )

    second = features.loc[features["session_date"] == sessions[1].strftime("%Y-%m-%d")].iloc[0]
    late = features.loc[features["session_date"] == sessions[70].strftime("%Y-%m-%d")].iloc[0]
    assert second["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert second["dfii10"] == 1.0
    assert math.isfinite(late["real_yield_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    real_yield_rank: float = 0.8,
    breakeven_rank: float = 0.8,
):
    path = tmp_path / "real_yield.csv"
    path.write_text(
        "session_date,observation_date,dfii10,t10yie,dgs10,real_yield_change_1d,"
        "real_yield_change_5d,breakeven_change_1d,breakeven_change_5d,"
        "nominal_real_gap_change_1d,dfii10_rank_252,t10yie_rank_252,"
        "real_yield_change_1d_rank_252,real_yield_change_5d_rank_252,"
        "breakeven_change_1d_rank_252,breakeven_change_5d_rank_252,"
        "nominal_real_gap_change_1d_rank_252\n"
        f"{session_date},2024-01-02,2.1,2.3,4.4,0.05,0.12,0.03,0.08,0.02,"
        f"0.7,0.6,{real_yield_rank},0.7,{breakeven_rank},0.7,0.5\n",
        encoding="utf-8",
    )
    return path


def _rate_inputs(tmp_path, sessions):
    rows_dfii10 = []
    rows_t10yie = []
    rows_dgs10 = []
    for i, session in enumerate(sessions):
        day = session.strftime("%Y-%m-%d")
        rows_dfii10.append({"observation_date": day, "DFII10": 1.0 + i * 0.01})
        rows_t10yie.append({"observation_date": day, "T10YIE": 2.0 + i * 0.005})
        rows_dgs10.append({"observation_date": day, "DGS10": 3.0 + i * 0.015})
    dfii10_path = tmp_path / "dfii10.csv"
    t10yie_path = tmp_path / "t10yie.csv"
    dgs10_path = tmp_path / "dgs10.csv"
    pd.DataFrame(rows_dfii10).to_csv(dfii10_path, index=False)
    pd.DataFrame(rows_t10yie).to_csv(t10yie_path, index=False)
    pd.DataFrame(rows_dgs10).to_csv(dgs10_path, index=False)
    return dfii10_path, t10yie_path, dgs10_path


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 5.0,
            "high": close + 2.5,
            "low": close - 2.5,
            "close": close,
            "volume": 1000,
        }
    )
