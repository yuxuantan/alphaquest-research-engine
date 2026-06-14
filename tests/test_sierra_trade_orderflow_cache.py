from __future__ import annotations

from datetime import datetime

import pandas as pd
import pyarrow as pa

from tools.build_sierra_trade_orderflow_cache import (
    SCID_EPOCH,
    aggregate_batch,
    datetime_to_scid_us,
    roll_contract_to_file_symbol,
)


def _batch(rows: list[dict]) -> pa.RecordBatch:
    schema = pa.schema(
        [
            ("scid_datetime_us", pa.int64()),
            ("close", pa.float64()),
            ("num_trades", pa.int64()),
            ("volume", pa.int64()),
            ("bid_volume", pa.int64()),
            ("ask_volume", pa.int64()),
        ]
    )
    return pa.record_batch(
        [pa.array([row[name] for row in rows], type=schema.field(name).type) for name in schema.names],
        schema=schema,
    )


def _timestamp_from_minute_us(value: int) -> pd.Timestamp:
    return pd.Timestamp(SCID_EPOCH) + pd.Timedelta(microseconds=int(value))


def test_aggregate_batch_converts_utc_scid_timestamps_to_new_york_rth_summer() -> None:
    batch = _batch(
        [
            {
                "scid_datetime_us": datetime_to_scid_us(datetime(2025, 6, 9, 9, 30)),
                "close": 5990.0,
                "num_trades": 1,
                "volume": 1,
                "bid_volume": 1,
                "ask_volume": 0,
            },
            {
                "scid_datetime_us": datetime_to_scid_us(datetime(2025, 6, 9, 13, 30)),
                "close": 6000.0,
                "num_trades": 1,
                "volume": 2,
                "bid_volume": 1,
                "ask_volume": 1,
            },
            {
                "scid_datetime_us": datetime_to_scid_us(datetime(2025, 6, 9, 13, 30, 30)),
                "close": 6001.0,
                "num_trades": 1,
                "volume": 3,
                "bid_volume": 1,
                "ask_volume": 2,
            },
        ]
    )

    out = aggregate_batch(
        batch,
        start_us=datetime_to_scid_us(datetime(2025, 6, 9)),
        end_us=datetime_to_scid_us(datetime(2025, 6, 10)),
    )

    assert len(out) == 1
    assert _timestamp_from_minute_us(out.iloc[0]["minute_us"]) == pd.Timestamp("2025-06-09 09:30")
    assert out.iloc[0]["volume"] == 5
    assert out.iloc[0]["open"] == 6000.0
    assert out.iloc[0]["close"] == 6001.0


def test_aggregate_batch_converts_utc_scid_timestamps_to_new_york_rth_winter() -> None:
    batch = _batch(
        [
            {
                "scid_datetime_us": datetime_to_scid_us(datetime(2025, 12, 15, 14, 30)),
                "close": 6000.0,
                "num_trades": 1,
                "volume": 2,
                "bid_volume": 1,
                "ask_volume": 1,
            },
        ]
    )

    out = aggregate_batch(
        batch,
        start_us=datetime_to_scid_us(datetime(2025, 12, 15)),
        end_us=datetime_to_scid_us(datetime(2025, 12, 16)),
    )

    assert len(out) == 1
    assert _timestamp_from_minute_us(out.iloc[0]["minute_us"]) == pd.Timestamp("2025-12-15 09:30")


def test_roll_contract_to_file_symbol_supports_non_es_root_symbol() -> None:
    assert roll_contract_to_file_symbol(pd.Timestamp("2025-12-15"), "ESH6", "NQ") == "NQH26"
    assert roll_contract_to_file_symbol(pd.Timestamp("2025-06-15"), "ESU5", "NQ") == "NQU25"
