from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.move_treasury_vol_state import MoveTreasuryVolStateEntry
from tools import build_nq_move_treasury_vol_features as builder


def _feature_csv(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "move_features.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _bar(**overrides) -> pd.Series:
    base = {
        "timestamp": pd.Timestamp("2024-01-03 09:55:00", tz="America/New_York"),
        "session_date": "2024-01-03",
        "is_rth": True,
        "open": 17000.0,
        "high": 17008.0,
        "low": 16990.0,
        "close": 16995.0,
        "rth_return_since_open_ticks": -20.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_high_move_riskoff_short_uses_prior_feature_row(tmp_path):
    feature_csv = _feature_csv(
        tmp_path,
        [
            {
                "session_date": "2024-01-03",
                "observation_date": "2024-01-02",
                "move_close": 150.0,
                "move_change_1d": 10.0,
                "move_change_5d": 20.0,
                "move_pct_change_1d": 0.07,
                "move_pct_change_5d": 0.15,
                "move_5d_mean": 135.0,
                "move_close_rank_252": 0.92,
                "move_change_1d_rank_252": 0.88,
                "move_change_5d_rank_252": 0.82,
                "move_5d_mean_rank_252": 0.8,
            }
        ],
    )
    entry = MoveTreasuryVolStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "high_move_riskoff_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "rank_threshold": 0.8,
            "change_threshold": 0.7,
        }
    )

    signal = entry.on_bar_close(_bar())

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["move_observation_date"] == "2024-01-02"
    assert "strictly before NQ session_date" in signal.report_fields["availability_rule"]


def test_low_move_carry_long_inverts_rank_thresholds(tmp_path):
    feature_csv = _feature_csv(
        tmp_path,
        [
            {
                "session_date": "2024-01-03",
                "observation_date": "2024-01-02",
                "move_close": 60.0,
                "move_change_1d": -5.0,
                "move_change_5d": -15.0,
                "move_pct_change_1d": -0.08,
                "move_pct_change_5d": -0.2,
                "move_5d_mean": 68.0,
                "move_close_rank_252": 0.18,
                "move_change_1d_rank_252": 0.2,
                "move_change_5d_rank_252": 0.12,
                "move_5d_mean_rank_252": 0.2,
            }
        ],
    )
    entry = MoveTreasuryVolStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "low_move_carry_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "rank_threshold": 0.8,
            "change_threshold": 0.7,
        }
    )

    signal = entry.on_bar_close(_bar(close=17005.0, rth_return_since_open_ticks=20.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["move_driver_column"] == "move_close_rank_252"


def test_morning_weakness_filter_blocks_if_return_not_negative_enough(tmp_path):
    feature_csv = _feature_csv(
        tmp_path,
        [
            {
                "session_date": "2024-01-03",
                "observation_date": "2024-01-02",
                "move_close": 120.0,
                "move_change_1d": 12.0,
                "move_change_5d": 9.0,
                "move_pct_change_1d": 0.1,
                "move_pct_change_5d": 0.08,
                "move_5d_mean": 115.0,
                "move_close_rank_252": 0.75,
                "move_change_1d_rank_252": 0.95,
                "move_change_5d_rank_252": 0.8,
                "move_5d_mean_rank_252": 0.75,
            }
        ],
    )
    entry = MoveTreasuryVolStateEntry(
        {
            "feature_csv": feature_csv,
            "setup_mode": "move_spike_morning_weakness_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 5,
            "change_threshold": 0.8,
            "return_filter_ticks": 12,
        }
    )

    assert entry.on_bar_close(_bar(rth_return_since_open_ticks=-8.0)) is None
    assert entry.on_bar_close(_bar(rth_return_since_open_ticks=-16.0)) is not None


def test_feature_builder_asof_uses_strict_prior_move_close(tmp_path, monkeypatch):
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York"),
                pd.Timestamp("2024-01-04 09:30:00", tz="America/New_York"),
            ]
        }
    ).to_parquet(bars_path)

    def fake_download(*_args, **_kwargs):
        return pd.DataFrame(
            {
                "observation_date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
                "move_close": [100.0, 120.0, 80.0],
            }
        )

    monkeypatch.setattr(builder, "_download_move", fake_download)
    out = builder.build_features(
        bars_path,
        tmp_path / "features.csv",
        raw_output_path=tmp_path / "raw.csv",
        rank_min_periods=1,
    )

    assert out.loc[out["session_date"] == "2024-01-03", "observation_date"].iloc[0] == "2024-01-02"
    assert out.loc[out["session_date"] == "2024-01-03", "move_close"].iloc[0] == 100.0
    assert out.loc[out["session_date"] == "2024-01-04", "observation_date"].iloc[0] == "2024-01-03"
    assert out.loc[out["session_date"] == "2024-01-04", "move_close"].iloc[0] == 120.0


def test_move_treasury_vol_state_registered():
    assert ENTRY_MODULES["move_treasury_vol_state"] is MoveTreasuryVolStateEntry
