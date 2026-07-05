from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.gold_platinum_ratio_state import GoldPlatinumRatioStateEntry
from tools import build_nq_gold_platinum_ratio_features as builder


def _feature_csv(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "gp_features.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _row(**overrides) -> dict:
    row = {
        "session_date": "2024-01-03",
        "observation_date": "2024-01-02",
        "gold_close": 2100.0,
        "platinum_close": 1000.0,
        "gold_platinum_ratio": 2.1,
        "gp_change_1d": 0.1,
        "gp_change_5d": 0.2,
        "gp_pct_change_1d": 0.05,
        "gp_pct_change_5d": 0.1,
        "gp_5d_mean": 2.0,
        "gp_ratio_rank_252": 0.9,
        "gp_change_1d_rank_252": 0.85,
        "gp_change_5d_rank_252": 0.8,
        "gp_5d_mean_rank_252": 0.8,
    }
    row.update(overrides)
    return row


def _bar(**overrides) -> pd.Series:
    base = {
        "timestamp": pd.Timestamp("2024-01-03 09:55:00", tz="America/New_York"),
        "session_date": "2024-01-03",
        "is_rth": True,
        "open": 17000.0,
        "high": 17008.0,
        "low": 16990.0,
        "close": 17005.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_high_gp_state_emits_long_with_prior_observation(tmp_path):
    feature_csv = _feature_csv(tmp_path, [_row()])
    entry = GoldPlatinumRatioStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "high_gp_risk_premium_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "ratio_rank_threshold": 0.8,
        }
    )

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["metal_observation_date"] == "2024-01-02"
    assert "strictly before NQ session_date" in signal.report_fields["availability_rule"]


def test_low_gp_state_emits_short(tmp_path):
    feature_csv = _feature_csv(tmp_path, [_row(gp_ratio_rank_252=0.12)])
    entry = GoldPlatinumRatioStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "low_gp_complacency_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "ratio_rank_threshold": 0.8,
        }
    )

    signal = entry.on_bar_close(_bar(close=16995.0))

    assert signal is not None
    assert signal.direction == "short"


def test_return_filtered_gp_rising_short_uses_computed_session_return(tmp_path):
    feature_csv = _feature_csv(tmp_path, [_row(gp_change_5d_rank_252=0.9)])
    entry = GoldPlatinumRatioStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "gp_rising_morning_weakness_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "change_rank_threshold": 0.8,
            "return_filter_ticks": 12,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar(open=17000.0, close=16998.0)) is None
    assert entry.on_bar_close(_bar(timestamp=pd.Timestamp("2024-01-04 09:55:00", tz="America/New_York"), session_date="2024-01-04", open=17000.0, close=16996.0)) is None

    feature_csv = _feature_csv(tmp_path, [_row(session_date="2024-01-05", gp_change_5d_rank_252=0.9)])
    entry = GoldPlatinumRatioStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "gp_rising_morning_weakness_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "change_rank_threshold": 0.8,
            "return_filter_ticks": 12,
            "tick_size": 0.25,
        }
    )
    signal = entry.on_bar_close(
        _bar(timestamp=pd.Timestamp("2024-01-05 09:55:00", tz="America/New_York"), session_date="2024-01-05", open=17000.0, close=16996.0)
    )
    assert signal is not None
    assert signal.direction == "short"


def test_feature_builder_asof_uses_strict_prior_metals(tmp_path, monkeypatch):
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York"),
                pd.Timestamp("2024-01-04 09:30:00", tz="America/New_York"),
            ]
        }
    ).to_parquet(bars_path)

    def fake_download(ticker, value_column, *, start, end):
        values = [2000.0, 2100.0, 2200.0] if value_column == "gold_close" else [1000.0, 1000.0, 1100.0]
        return pd.DataFrame(
            {
                "observation_date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
                value_column: values,
            }
        )

    monkeypatch.setattr(builder, "_download_yahoo_chart", fake_download)
    out = builder.build_features(
        bars_path,
        tmp_path / "features.csv",
        raw_output_path=tmp_path / "raw.csv",
        rank_min_periods=1,
    )

    assert out.loc[out["session_date"] == "2024-01-03", "observation_date"].iloc[0] == "2024-01-02"
    assert out.loc[out["session_date"] == "2024-01-03", "gold_platinum_ratio"].iloc[0] == 2.0
    assert out.loc[out["session_date"] == "2024-01-04", "observation_date"].iloc[0] == "2024-01-03"
    assert out.loc[out["session_date"] == "2024-01-04", "gold_platinum_ratio"].iloc[0] == 2.1


def test_gold_platinum_ratio_state_registered():
    assert ENTRY_MODULES["gold_platinum_ratio_state"] is GoldPlatinumRatioStateEntry
