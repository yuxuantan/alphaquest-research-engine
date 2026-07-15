import pandas as pd

from alphaquest.strategy_modules.entry.emv_macro_news_state import EmvMacroNewsStateEntry
from tools.build_es_emv_macro_news_features import build_features


def test_emv_macro_news_entry_emits_on_completed_entry_bar(tmp_path):
    feature_csv = tmp_path / "emv_features.csv"
    feature_csv.write_text(
        "session_date,observation_date,availability_date,emv_macro_news,emv_interest_rates,emv_labor,"
        "emv_macro_news_rank_120m,emv_macro_news_change_1m_rank_120m,"
        "emv_interest_rates_rank_120m,emv_labor_rank_120m\n"
        "2026-06-10,2026-05-01,2026-05-22,20.0,5.0,4.0,0.91,0.80,0.70,0.60\n"
    )
    entry = EmvMacroNewsStateEntry(
        {
            "feature_csv": str(feature_csv),
            "setup_mode": "high_macro_news_short",
            "entry_time": "10:30:00",
            "bar_interval_minutes": 1,
            "emv_rank_min": 0.9,
            "stop_pct": 0.003,
            "target_r_multiple": 1.5,
        }
    )

    assert entry.on_bar_close(_bar("2026-06-10 10:28")) is None
    signal = entry.on_bar_close(_bar("2026-06-10 10:29"))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2026-06-10 10:30", tz="America/New_York")
    assert signal.report_fields["emv_driver_column"] == "emv_macro_news_rank_120m"
    assert signal.report_fields["availability_rule"].startswith("monthly FRED EMV")


def test_emv_feature_builder_applies_conservative_monthly_lag(tmp_path):
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-02-20 09:30:00",
                    "2026-02-21 09:30:00",
                    "2026-03-24 09:30:00",
                ]
            )
        }
    )
    bars_path = tmp_path / "bars.parquet"
    bars.to_parquet(bars_path)
    cache_dir = tmp_path / "fred"
    cache_dir.mkdir()
    for series_id, values in {
        "emvmacronews": [10.0, 30.0],
        "emvmacrobus": [1.0, 2.0],
        "emvmacrolabormkt": [3.0, 4.0],
        "emvmacrointerest": [5.0, 6.0],
    }.items():
        pd.DataFrame(
            {
                "observation_date": ["2026-01-01", "2026-02-01"],
                series_id.upper(): values,
            }
        ).to_csv(cache_dir / f"{series_id}.csv", index=False)

    out = build_features(
        bars_path,
        tmp_path / "features.csv",
        cache_dir=cache_dir,
        release_lag_days=21,
        rank_min_periods=1,
    )

    by_date = out.set_index("session_date")
    assert by_date.loc["2026-02-20", "observation_date"] == "NaT"
    assert pd.isna(by_date.loc["2026-02-20", "emv_macro_news"])
    assert by_date.loc["2026-02-21", "observation_date"] == "2026-01-01"
    assert by_date.loc["2026-02-21", "emv_macro_news"] == 10.0
    assert by_date.loc["2026-03-24", "observation_date"] == "2026-02-01"


def _bar(timestamp: str):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": 5000.0,
            "high": 5002.0,
            "low": 4998.0,
            "close": 5000.5,
            "volume": 1000,
        }
    )
