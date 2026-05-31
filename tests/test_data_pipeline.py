from propstack.data.clean import clean_data
from propstack.data.features import build_features


DATA_CFG = {
    "raw_csv": "tests/fixtures/es_1m_no_header_sample.csv",
    "csv_format": "yyyymmdd_hhmmss_ohlcv",
    "has_header": False,
    "timestamp_format": "%Y%m%d %H%M%S",
    "symbol": "ES",
    "timezone": "America/Chicago",
    "rth_start": "08:30:00",
    "rth_end": "15:00:00",
    "eth_start": "17:00:00",
    "eth_end": "08:29:00",
    "rolling_volume_window": 3,
}


def test_csv_loading_and_cleaning():
    df, report, missing = clean_data(DATA_CFG)
    assert report["duplicate_count"] == 0
    assert report["invalid_ohlc_count"] == 0
    assert len(df) == 20
    assert "session_date" in df.columns


def test_timestamp_parsing_and_session_date_assignment():
    df, _, _ = clean_data(DATA_CFG)
    evening = df[df["timestamp"].astype(str).str.contains("2024-01-02 17:00")].iloc[0]
    assert str(evening["session_date"]) == "2024-01-03"
    rth = df[df["timestamp"].astype(str).str.contains("2024-01-03 08:30")].iloc[0]
    assert rth["session_label"] == "RTH"


def test_features_previous_rth_overnight_vwap_rolling_volume():
    df, _, _ = clean_data(DATA_CFG)
    feat = build_features(df, DATA_CFG)
    jan3 = feat[(feat["session_date"].astype(str) == "2024-01-03") & (feat["is_rth"])].iloc[0]
    assert jan3["prev_rth_high"] == 101.0
    assert jan3["prev_rth_low"] == 99.0
    assert jan3["overnight_high"] == 100.75
    assert jan3["overnight_low"] == 99.75
    assert jan3["vwap"] > 0
    assert "rolling_volume" in feat.columns
