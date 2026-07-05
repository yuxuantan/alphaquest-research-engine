from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.ai_gpr_geopolitical_risk_state import (
    AiGprGeopoliticalRiskStateEntry,
)
from tools.build_nq_ai_gpr_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["ai_gpr_geopolitical_risk_state"] is AiGprGeopoliticalRiskStateEntry


def test_high_ai_gpr_short_emits_only_on_completed_entry_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", gpr_rank=0.82)
    entry = AiGprGeopoliticalRiskStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_ai_gpr_short",
            "rank_column": "gpr_ai_21d_rank_252",
            "value_column": "gpr_ai_21d",
            "gpr_rank_threshold": 0.30,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["gpr_rank_column"] == "gpr_ai_21d_rank_252"
    assert signal.report_fields["availability_rule"].startswith("latest AI-GPR")


def test_high_ai_gpr_rebound_requires_high_tail(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", gpr_rank=0.62)
    entry = AiGprGeopoliticalRiskStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_ai_gpr_rebound_long",
            "rank_column": "gpr_ai_21d_rank_252",
            "value_column": "gpr_ai_21d",
            "gpr_rank_threshold": 0.30,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", gpr_rank=0.91, name="high.csv")
    entry = AiGprGeopoliticalRiskStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_ai_gpr_rebound_long",
            "rank_column": "gpr_ai_21d_rank_252",
            "value_column": "gpr_ai_21d",
            "gpr_rank_threshold": 0.30,
            "entry_time": "13:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 13:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"


def test_rising_gpr_uses_configured_rank_column(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", change_rank=0.88)
    entry = AiGprGeopoliticalRiskStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_ai_gpr_short",
            "rank_column": "gpr_ai_5d_change_rank_252",
            "value_column": "gpr_ai_5d_change",
            "gpr_rank_threshold": 0.25,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["gpr_value_column"] == "gpr_ai_5d_change"


def test_builder_uses_30_calendar_day_availability_lag(tmp_path):
    sessions = pd.date_range("2024-04-15", periods=90, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    gpr_path = tmp_path / "ai_gpr.csv"
    _write_ai_gpr_csv(gpr_path, pd.date_range("2023-01-01", "2024-06-30", freq="D"))
    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        ai_gpr_csv_path=gpr_path,
        publication_lag_calendar_days=30,
        download_if_missing=False,
    )

    first = features.loc[features["session_date"] == "2024-04-15"].iloc[0]
    later = features.iloc[-1]
    assert first["availability_cutoff"] == "2024-03-16"
    assert first["observation_date"] <= "2024-03-16"
    assert int(first["observation_age_days"]) >= 30
    assert math.isfinite(later["gpr_ai_21d_rank_252"])
    assert math.isfinite(later["threats_gpr_ai_21d_rank_252"])
    assert math.isfinite(later["acts_gpr_ai_5d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    gpr_rank: float = 0.5,
    change_rank: float = 0.5,
    threats_rank: float = 0.5,
    acts_rank: float = 0.5,
    name: str = "gpr.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,"
        "observation_age_days,gpr_ai_1d,gpr_aer_1d,gpr_nonoil_1d,threats_gpr_ai_1d,"
        "acts_gpr_ai_1d,gpr_ai_5d,gpr_ai_21d,gpr_ai_5d_change,gpr_ai_21d_rank_252,"
        "gpr_ai_5d_change_rank_252,threats_gpr_ai_21d,threats_gpr_ai_21d_rank_252,"
        "acts_gpr_ai_5d,acts_gpr_ai_5d_rank_252,gpr_nonoil_21d,gpr_nonoil_21d_rank_252\n"
        f"{session_date},2024-02-15,2024-03-04,30,48,120,118,110,130,80,125,122,12,"
        f"{gpr_rank},{change_rank},128,{threats_rank},82,{acts_rank},111,0.55\n",
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


def _write_ai_gpr_csv(path, dates) -> None:
    rows = [
        "Date,GPR_AI,GPR_AER,GPR_OIL,GPR_NONOIL,THREATS_GPR_AI,ACTS_GPR_AI,"
        "GPR_OIL_MiddleEast,GPR_OIL_Russia,GPR_OIL_USA,GPR_OIL_Venezuela,"
        "GPR_OIL_Africa,GPR_OIL_Americas,GPR_OIL_Asia,GPR_OIL_NorthSea"
    ]
    for index, day in enumerate(dates):
        base = 100 + (index % 53)
        rows.append(
            f"{day:%Y-%m-%d},{base},{base - 3},0,{base - 5},{base + (index % 7)},"
            f"{base - (index % 11)},0,0,0,0,0,0,0,0"
        )
    path.write_text("\n".join(rows), encoding="utf-8")
