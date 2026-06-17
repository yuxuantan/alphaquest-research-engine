from __future__ import annotations

import pandas as pd
import pytest

from propstack.strategy_modules.entry.finra_margin_leverage import FinraMarginLeverageEntry
from tools.build_es_finra_margin_features import build_features


def test_finra_margin_leverage_high_debt_short_signal(tmp_path):
    feature_csv = tmp_path / "features.csv"
    feature_csv.write_text(
        "\n".join(
            [
                "session_date,observation_date,margin_debt,cash_free_credit,margin_free_credit,total_free_credit,debit_credit_ratio,margin_debt_change_3m,margin_debt_rank_120m,debit_credit_ratio_rank_120m,margin_debt_change_3m_rank_120m",
                "2024-01-03,2023-11-30,1000,100,100,200,5.0,0.12,0.85,0.70,0.65",
            ]
        ),
        encoding="utf-8",
    )
    entry = FinraMarginLeverageEntry(
        {
            "feature_csv": str(feature_csv),
            "setup_mode": "high_margin_debt_short",
            "entry_time": "10:30:00",
            "bar_interval_minutes": 1,
            "rank_min": 0.8,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29:00-05:00"))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.level_type == "finra_margin_leverage_high_margin_debt_short"
    assert signal.report_fields["margin_observation_date"] == "2023-11-30"
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp(
        "2024-01-03 10:30:00-05:00"
    )


def test_finra_margin_leverage_low_debt_long_and_duplicate_guard(tmp_path):
    feature_csv = tmp_path / "features.csv"
    feature_csv.write_text(
        "\n".join(
            [
                "session_date,observation_date,margin_debt,cash_free_credit,margin_free_credit,total_free_credit,debit_credit_ratio,margin_debt_change_3m,margin_debt_rank_120m,debit_credit_ratio_rank_120m,margin_debt_change_3m_rank_120m",
                "2024-01-03,2023-11-30,1000,100,100,200,5.0,-0.05,0.15,0.20,0.25",
            ]
        ),
        encoding="utf-8",
    )
    entry = FinraMarginLeverageEntry(
        {
            "feature_csv": str(feature_csv),
            "setup_mode": "low_margin_debt_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "rank_max": 0.2,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59:00-05:00"))
    duplicate = entry.on_bar_close(_bar("2024-01-03 10:00:00-05:00"), trades_today=0)

    assert signal is not None
    assert signal.direction == "long"
    assert duplicate is None


def test_finra_margin_feature_builder_uses_conservative_availability_lag(tmp_path):
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-02-02 14:30:00Z",
                    "2024-02-06 14:30:00Z",
                    "2024-03-10 14:30:00Z",
                ]
            )
        }
    )
    bars_path = tmp_path / "bars.parquet"
    bars.to_parquet(bars_path)
    margin_csv = tmp_path / "margin.csv"
    rows = [
        ["year_month", "margin_debt", "cash_free_credit", "margin_free_credit"],
    ]
    for month in pd.period_range("2020-01", "2024-01", freq="M"):
        rows.append([month.strftime("%Y-%m"), 1000 + len(rows), 100, 100])
    margin_csv.write_text("\n".join(",".join(map(str, row)) for row in rows), encoding="utf-8")

    out = build_features(
        bars_path,
        tmp_path / "features.csv",
        margin_input=margin_csv,
        availability_lag_days=35,
        rank_min_periods=3,
    )

    by_day = out.set_index("session_date")
    assert by_day.loc["2024-02-02", "observation_date"] == "2023-11-30"
    assert by_day.loc["2024-02-06", "observation_date"] == "2023-12-31"
    assert by_day.loc["2024-03-10", "observation_date"] == "2024-01-31"


def test_finra_margin_leverage_rejects_invalid_threshold(tmp_path):
    feature_csv = tmp_path / "features.csv"
    feature_csv.write_text(
        "session_date,observation_date,margin_debt_rank_120m\n2024-01-03,2023-11-30,0.9\n",
        encoding="utf-8",
    )
    entry = FinraMarginLeverageEntry({"feature_csv": str(feature_csv), "rank_min": 0.0})

    with pytest.raises(ValueError, match="rank_min"):
        entry.on_bar_close(_bar("2024-01-03 10:29:00-05:00"))


def _bar(timestamp: str) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": 5000.0,
            "high": 5001.0,
            "low": 4999.0,
            "close": 5000.25,
        }
    )
