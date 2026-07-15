from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.bankruptcy_distress_reversion import (
    BankruptcyDistressReversionEntry,
)


def test_bankruptcy_distress_uses_effective_feature_and_prior_session_filter(tmp_path):
    feature_file = tmp_path / "bankruptcy_features.csv"
    feature_file.write_text(
        "period_end,effective_date,total_ch11_yoy_pct\n"
        "2024-03-31,2024-05-15,30.0\n",
        encoding="utf-8",
    )
    entry = BankruptcyDistressReversionEntry(
        {
            "feature_file": str(feature_file),
            "feature_name": "total_ch11_yoy_pct",
            "threshold": 20.0,
            "entry_time": "11:30:00",
            "bar_interval_minutes": 5,
            "prior_return_filter": "down",
            "direction": "long",
        }
    )

    entry.on_bar_close(_bar("2024-05-13 11:25", close=100.0))
    entry.on_bar_close(_bar("2024-05-14 11:25", close=99.0))

    assert entry.on_bar_close(_bar("2024-05-14 11:25", close=99.0), trades_today=1) is None
    assert entry.on_bar_close(_bar("2024-05-14 11:25", close=99.0)) is None

    signal = entry.on_bar_close(_bar("2024-05-15 11:25", close=98.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["feature_effective_date"] == "2024-05-15"
    assert signal.report_fields["prior_session_return_pct"] < 0


def test_bankruptcy_distress_rejects_future_unreleased_feature(tmp_path):
    feature_file = tmp_path / "bankruptcy_features.csv"
    feature_file.write_text(
        "period_end,effective_date,total_ch11_yoy_pct\n"
        "2024-03-31,2024-05-15,30.0\n",
        encoding="utf-8",
    )
    entry = BankruptcyDistressReversionEntry(
        {
            "feature_file": str(feature_file),
            "feature_name": "total_ch11_yoy_pct",
            "threshold": 20.0,
            "entry_time": "11:30:00",
            "bar_interval_minutes": 5,
            "prior_return_filter": "down",
            "direction": "long",
        }
    )

    entry.on_bar_close(_bar("2024-05-10 11:25", close=100.0))
    entry.on_bar_close(_bar("2024-05-13 11:25", close=99.0))

    assert entry.on_bar_close(_bar("2024-05-14 11:25", close=98.5)) is None


def _bar(timestamp: str, *, close: float, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
        }
    )
