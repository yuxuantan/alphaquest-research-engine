import pandas as pd

from propstack.utils.reports import market_timezone, normalize_report_timestamps, write_report_csv


def test_market_timezone_prefers_exchange_timezone():
    assert (
        market_timezone(
            {
                "data": {
                    "timezone": "Asia/Singapore",
                    "exchange_timezone": "America/New_York",
                }
            }
        )
        == "America/New_York"
    )


def test_normalize_report_timestamps_converts_gmt8_to_market_timezone():
    df = pd.DataFrame(
        {
            "entry_timestamp": [pd.Timestamp("2024-01-02 22:30:00", tz="Asia/Singapore")],
            "timestamp_utc": [pd.Timestamp("2024-01-02 14:30:00", tz="UTC")],
            "train_start": [pd.Timestamp("2024-01-01")],
            "note": ["leave me alone"],
        }
    )

    out = normalize_report_timestamps(df, "America/New_York")

    assert out.loc[0, "entry_timestamp"] == "2024-01-02 09:30:00-05:00"
    assert out.loc[0, "timestamp_utc"] == pd.Timestamp("2024-01-02 14:30:00", tz="UTC")
    assert out.loc[0, "train_start"] == pd.Timestamp("2024-01-01")
    assert out.loc[0, "note"] == "leave me alone"


def test_write_report_csv_serializes_market_timezone(tmp_path):
    path = tmp_path / "trade_log.csv"
    df = pd.DataFrame(
        {
            "entry_timestamp": [pd.Timestamp("2024-07-02 21:30:00", tz="Asia/Singapore")],
        }
    )

    write_report_csv(df, path, "America/New_York", index=False)

    assert path.read_text(encoding="utf-8").splitlines()[1] == "2024-07-02 09:30:00-04:00"
