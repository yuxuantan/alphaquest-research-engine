import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.data.pipeline import prepare_data


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


def test_parquet_loading_preserves_orderflow_columns(tmp_path):
    path = tmp_path / "orderflow.parquet"
    pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-03 09:30", "2024-01-03 09:31"]),
            "open": [100.0, 100.5],
            "high": [101.0, 101.0],
            "low": [99.5, 100.0],
            "close": [100.5, 100.75],
            "volume": [1000, 1200],
            "signed_volume": [100, -50],
            "trades": [25, 30],
        }
    ).to_parquet(path, index=False)

    data, report = prepare_data(
        {
            "source": "parquet",
            "raw_parquet": str(path),
            "symbol": "ES",
            "timezone": "America/New_York",
            "rth_start": "09:30:00",
            "rth_end": "15:59:00",
            "feature_set": "none",
            "trade_orderflow_features": {
                "enabled": True,
                "windows": [2],
                "large_trade_sizes": [],
                "min_period_fraction": 1.0,
                "tick_size": 0.25,
            },
        }
    )

    assert str(data["timestamp"].dt.tz) == "America/New_York"
    assert report["rows"] == 2
    assert data.loc[1, "trade_orderflow_signed_volume_2"] == 50
    assert data.loc[1, "trade_orderflow_trades_2"] == 55


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
    assert jan3["prev_rth_close"] == 100.0
    assert jan3["overnight_high"] == 100.75
    assert jan3["overnight_low"] == 99.75
    assert jan3["vwap"] > 0
    assert "rolling_volume" in feat.columns


def test_prepare_data_applies_subset_after_feature_warmup():
    data, report = prepare_data(
        {**DATA_CFG, "warmup_days": 1},
        subset_config={"start_date": "2024-01-03", "end_date": "2024-01-03"},
    )

    assert data["session_date"].astype(str).unique().tolist() == ["2024-01-03"]
    assert report["loaded_rows"] > report["rows"]
    jan3 = data[data["is_rth"]].iloc[0]
    assert jan3["prev_rth_high"] == 101.0
    assert jan3["prev_rth_close"] == 100.0


def test_prepare_data_aggregates_to_requested_timeframe():
    data, report, execution_data = prepare_data(
        {**DATA_CFG, "feature_set": "opening_range"},
        timeframe="5m",
        include_execution_data=True,
    )

    jan3_rth = data[(data["session_date"].astype(str) == "2024-01-03") & data["is_rth"]].iloc[0]
    assert str(jan3_rth["timestamp"]) == "2024-01-03 08:30:00-06:00"
    assert jan3_rth["open"] == 100.0
    assert jan3_rth["high"] == 102.5
    assert jan3_rth["low"] == 98.5
    assert jan3_rth["close"] == 101.75
    assert jan3_rth["volume"] == 1010
    assert jan3_rth["source_bar_count"] == 5
    assert report["timeframe"] == "5m"
    assert report["strategy_rows"] < report["rows"]
    assert len(execution_data) == 20


def test_prepare_data_emits_status_updates():
    messages = []

    prepare_data(
        DATA_CFG,
        subset_config={"start_date": "2024-01-03", "end_date": "2024-01-03"},
        status_callback=messages.append,
    )

    assert "Loading raw market data..." in messages
    assert "Assigning market sessions..." in messages
    assert "Building previous RTH level features..." in messages
    assert "Applying final data subset after warmup feature build..." in messages
