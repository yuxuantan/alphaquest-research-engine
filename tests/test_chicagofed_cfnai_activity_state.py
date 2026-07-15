from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.chicagofed_cfnai_activity_state import (
    ChicagoFedCfnaiActivityStateEntry,
)
from tools.build_es_chicagofed_cfnai_features import build_features


def _features_csv(tmp_path: Path, rows: list[dict]) -> str:
    path = tmp_path / "features.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _entry(feature_csv: str, **params) -> ChicagoFedCfnaiActivityStateEntry:
    base = {
        "feature_csv": feature_csv,
        "setup_mode": "test_activity_pullback_long",
        "driver_column": "CFNAI",
        "driver_max": 0.1,
        "max_session_return_bps": -5.0,
        "entry_time": "11:00:00",
        "bar_interval_minutes": 1,
        "max_trades_per_day": 1,
        "stop_pct": 0.006,
        "target_r_multiple": 1.5,
        "flatten_time": "15:55:00",
    }
    base.update(params)
    return ChicagoFedCfnaiActivityStateEntry(base)


def _bars(session_date: str, *, last_close: float = 4996.0) -> list[pd.Series]:
    start = pd.Timestamp(f"{session_date} 09:30:00")
    rows = []
    for idx, ts in enumerate(pd.date_range(start, periods=90, freq="1min")):
        close = last_close if idx == 89 else 5000.0
        rows.append(
            pd.Series(
                {
                    "timestamp": ts,
                    "session_date": ts.date(),
                    "is_rth": True,
                    "open": 5000.0,
                    "high": max(5000.5, close + 0.25),
                    "low": min(4995.5, close - 0.25),
                    "close": close,
                }
            )
        )
    return rows


def _feed(entry: ChicagoFedCfnaiActivityStateEntry, bars: list[pd.Series]):
    signal = None
    for bar in bars:
        maybe = entry.on_bar_close(bar)
        if maybe is not None:
            signal = maybe
    return signal


def test_signals_long_on_lagged_weak_activity_and_completed_pullback(tmp_path):
    feature_csv = _features_csv(
        tmp_path,
        [
            {
                "session_date": "2024-06-03",
                "obs_date": "2024-04-30",
                "obs_month": "2024:04",
                "eligible_date": "2024-06-01",
                "P_I": -0.20,
                "EU_H": 0.10,
                "C_H": 0.02,
                "SO_I": -0.03,
                "CFNAI": 0.05,
                "CFNAI_MA3": -0.10,
                "DIFFUSION": -0.15,
            }
        ],
    )
    entry = _entry(feature_csv)

    signal = _feed(entry, _bars("2024-06-03", last_close=4996.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["cfnai_observation_date"] == "2024-04-30"
    assert signal.report_fields["cfnai_eligible_date"] == "2024-06-01"
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-06-03 11:00:00")
    assert signal.report_fields["session_return_bps"] < -5.0


def test_no_signal_when_completed_pullback_filter_does_not_pass(tmp_path):
    feature_csv = _features_csv(
        tmp_path,
        [
            {
                "session_date": "2024-06-03",
                "obs_date": "2024-04-30",
                "obs_month": "2024:04",
                "eligible_date": "2024-06-01",
                "CFNAI": 0.05,
            }
        ],
    )
    entry = _entry(feature_csv)

    signal = _feed(entry, _bars("2024-06-03", last_close=5001.0))

    assert signal is None


def test_builder_uses_latest_eligible_cfnai_observation_without_lookahead(tmp_path):
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-06-03 09:30:00",
                    "2024-06-14 09:30:00",
                    "2024-06-17 09:30:00",
                ]
            )
        }
    )
    bars_path = tmp_path / "bars.parquet"
    bars.to_parquet(bars_path)
    monthly_path = tmp_path / "monthly.csv"
    pd.DataFrame(
        [
            {
                "obs_date": "2024-04-30",
                "obs_month": "2024:04",
                "eligible_date": "2024-06-14",
                "CFNAI": -0.10,
                "P_I": -0.20,
                "EU_H": -0.05,
                "C_H": 0.01,
                "SO_I": -0.02,
                "CFNAI_MA3": -0.08,
                "DIFFUSION": -0.20,
            },
            {
                "obs_date": "2024-05-31",
                "obs_month": "2024:05",
                "eligible_date": "2024-07-15",
                "CFNAI": 0.50,
                "P_I": 0.40,
                "EU_H": 0.30,
                "C_H": 0.20,
                "SO_I": 0.10,
                "CFNAI_MA3": 0.25,
                "DIFFUSION": 0.15,
            },
        ]
    ).to_csv(monthly_path, index=False)

    out = build_features(bars_path, monthly_path, tmp_path / "daily.csv")

    june_3 = out.loc[out["session_date"] == "2024-06-03"].iloc[0]
    june_14 = out.loc[out["session_date"] == "2024-06-14"].iloc[0]
    june_17 = out.loc[out["session_date"] == "2024-06-17"].iloc[0]
    assert pd.isna(june_3["CFNAI"])
    assert june_14["obs_date"] == "2024-04-30"
    assert june_17["obs_date"] == "2024-04-30"
