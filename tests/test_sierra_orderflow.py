import pandas as pd

from alphaquest.data.sierra_orderflow import (
    aggregate_sierra_orderflow_frame,
    build_sierra_orderflow_cache,
)


def test_aggregate_sierra_orderflow_maps_bid_ask_volume_to_signed_volume():
    raw = pd.DataFrame(
        [
            {
                "Date": "2025/6/9",
                "Time": "09:30:05.000",
                "Open": 6000.0,
                "High": 6000.5,
                "Low": 5999.75,
                "Last": 6000.25,
                "Volume": 10,
                "NumberOfTrades": 2,
                "BidVolume": 4,
                "AskVolume": 6,
            },
            {
                "Date": "2025/6/9",
                "Time": "09:30:40.000",
                "Open": 6000.25,
                "High": 6001.0,
                "Low": 6000.0,
                "Last": 6000.75,
                "Volume": 5,
                "NumberOfTrades": 1,
                "BidVolume": 3,
                "AskVolume": 2,
            },
            {
                "Date": "2025/6/9",
                "Time": "09:31:10.000",
                "Open": 6000.75,
                "High": 6001.25,
                "Low": 6000.5,
                "Last": 6001.0,
                "Volume": 8,
                "NumberOfTrades": 3,
                "BidVolume": 1,
                "AskVolume": 7,
            },
        ]
    )

    bars = aggregate_sierra_orderflow_frame(raw, rth_start="09:30:00", rth_end="09:32:00")

    assert len(bars) == 2
    first = bars.iloc[0]
    assert first["timestamp"] == pd.Timestamp("2025-06-09 09:30:00")
    assert first["open"] == 6000.0
    assert first["high"] == 6001.0
    assert first["low"] == 5999.75
    assert first["close"] == 6000.75
    assert first["volume"] == 15
    assert first["buy_volume"] == 8
    assert first["sell_volume"] == 7
    assert first["signed_volume"] == 1
    assert first["trades"] == 3


def test_sierra_orderflow_converts_export_timezone_to_new_york_minutes():
    raw = pd.DataFrame(
        [
            {
                "Date": "2025/6/9",
                "Time": "21:30:10.000",
                "Open": 6000.0,
                "High": 6000.0,
                "Low": 6000.0,
                "Last": 6000.0,
                "Volume": 10,
                "NumberOfTrades": 2,
                "BidVolume": 4,
                "AskVolume": 6,
            },
        ]
    )

    bars = aggregate_sierra_orderflow_frame(
        raw,
        input_timezone="Asia/Singapore",
        output_timezone="America/New_York",
        rth_start="09:30:00",
        rth_end="09:31:00",
    )

    assert len(bars) == 1
    assert bars.iloc[0]["timestamp"] == pd.Timestamp("2025-06-09 09:30:00")


def test_build_sierra_orderflow_cache_drops_incomplete_sessions(tmp_path):
    source = tmp_path / "ESM26-CME.txt"
    source.write_text(
        "\n".join(
            [
                "Date, Time, Open, High, Low, Last, Volume, NumberOfTrades, BidVolume, AskVolume",
                "2025/6/9, 09:30:05.000, 6000.0, 6000.0, 6000.0, 6000.0, 10, 2, 4, 6",
                "2025/6/10, 09:30:05.000, 6010.0, 6010.0, 6010.0, 6010.0, 10, 2, 4, 6",
                "2025/6/10, 09:31:05.000, 6011.0, 6011.0, 6011.0, 6011.0, 10, 2, 4, 6",
            ]
        )
    )
    out = tmp_path / "cache.csv"

    bars = build_sierra_orderflow_cache(
        raw_path=source,
        output_csv=out,
        rth_start="09:30:00",
        rth_end="09:32:00",
        complete_session_end="09:31:00",
        chunksize=1,
    )

    assert out.exists()
    assert bars["timestamp"].dt.date.unique().tolist() == [pd.Timestamp("2025-06-10").date()]
    assert bars["contract_symbol"].unique().tolist() == ["ESM26-CME"]


def test_build_sierra_orderflow_cache_can_select_dominant_session_contract(tmp_path):
    low_volume = tmp_path / "ESM26-CME.txt"
    high_volume = tmp_path / "ESU26-CME.txt"
    header = "Date, Time, Open, High, Low, Last, Volume, NumberOfTrades, BidVolume, AskVolume\n"
    low_volume.write_text(
        header + "2025/6/9, 09:30:05.000, 6000.0, 6000.0, 6000.0, 6000.0, 10, 2, 4, 6\n"
    )
    high_volume.write_text(
        header + "2025/6/9, 09:30:05.000, 6010.0, 6010.0, 6010.0, 6010.0, 20, 2, 8, 12\n"
    )

    bars = build_sierra_orderflow_cache(
        raw_path=tmp_path,
        output_csv=tmp_path / "cache.csv",
        rth_start="09:30:00",
        rth_end="09:31:00",
        complete_session_end="09:30:00",
        active_contract_mode="dominant_session_volume",
        chunksize=1,
    )

    assert bars["contract_symbol"].unique().tolist() == ["ESU26-CME"]
    assert bars.iloc[0]["volume"] == 20
