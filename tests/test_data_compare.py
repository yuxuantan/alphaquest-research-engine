import pandas as pd

from alphaquest.data.compare_sources import compare_ohlcv_sources, timestamp_gap_segments


def _bars(rows):
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([row[0] for row in rows], utc=True),
            "session_date": [row[0][:10] for row in rows],
            "session_label": ["RTH"] * len(rows),
            "symbol": ["ES"] * len(rows),
            "open": [row[1] for row in rows],
            "high": [row[2] for row in rows],
            "low": [row[3] for row in rows],
            "close": [row[4] for row in rows],
            "volume": [row[5] for row in rows],
        }
    )


def test_compare_ohlcv_sources_flags_price_volume_and_missing_rows(tmp_path):
    csv = _bars(
        [
            ("2024-01-02 14:30", 100.0, 101.0, 99.0, 100.5, 10),
            ("2024-01-02 14:31", 100.5, 101.5, 100.0, 101.0, 20),
        ]
    )
    dbn = _bars(
        [
            ("2024-01-02 14:30", 100.0, 101.0, 99.0, 100.5, 10),
            ("2024-01-02 14:31", 100.5, 101.75, 100.0, 101.0, 30),
            ("2024-01-02 14:32", 101.0, 102.0, 100.5, 101.5, 40),
        ]
    )
    dbn["contract_symbol"] = "ESH4"

    summary = compare_ohlcv_sources(csv, dbn, tmp_path)

    assert summary["matched_timestamps"] == 2
    assert summary["timestamps_only_in_databento"] == 1
    assert summary["rows_with_any_price_mismatch"] == 1
    assert summary["rows_with_volume_mismatch"] == 1
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "column_mismatch_summary.csv").exists()


def test_timestamp_gap_segments_groups_consecutive_missing_rows():
    df = _bars(
        [
            ("2024-01-02 14:30", 100.0, 101.0, 99.0, 100.5, 10),
            ("2024-01-02 14:31", 100.5, 101.5, 100.0, 101.0, 20),
            ("2024-01-02 14:35", 101.0, 102.0, 100.5, 101.5, 40),
        ]
    )

    segments = timestamp_gap_segments(df)

    assert segments["row_count"].tolist() == [2, 1]
