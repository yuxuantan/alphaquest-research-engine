from __future__ import annotations

from datetime import datetime

import pandas as pd

from propstack.data.scid_execution import (
    SCID_RECORD_PRICE_PATH_SEMANTICS,
    _datetime_to_scid_us,
    load_scid_record_execution_data,
)


def test_scid_execution_loader_emits_normalized_trade_events(tmp_path, monkeypatch):
    monkeypatch.setattr("propstack.data.scid_execution._is_bar_like_contract", lambda symbol, path: False)

    raw_dir = tmp_path / "scid"
    raw_dir.mkdir()
    roll_calendar = tmp_path / "roll_calendar.csv"
    roll_calendar.write_text("contract_symbol,start_timestamp\nESM5,2025-01-01T15:00:00Z\n")

    rows = [
        {
            "scid_datetime_us": _datetime_to_scid_us(datetime(2025, 6, 9, 13, 30, 0)),
            "open": 0.0,
            "high": 6000.25,
            "low": 5999.75,
            "close": 6000.00,
            "num_trades": 1,
            "volume": 2,
            "bid_volume": 2,
            "ask_volume": 0,
        },
        {
            "scid_datetime_us": _datetime_to_scid_us(datetime(2025, 6, 9, 13, 30, 1)),
            "open": 0.0,
            "high": 6000.50,
            "low": 6000.25,
            "close": 6000.25,
            "num_trades": 1,
            "volume": 3,
            "bid_volume": 0,
            "ask_volume": 3,
        },
        {
            # Extra max-timestamp row keeps the first two rows inside the loader's
            # half-open active-contract interval.
            "scid_datetime_us": _datetime_to_scid_us(datetime(2025, 6, 9, 13, 31, 0)),
            "open": 6001.00,
            "high": 6001.25,
            "low": 6000.75,
            "close": 6001.00,
            "num_trades": 1,
            "volume": 1,
            "bid_volume": 1,
            "ask_volume": 0,
        },
    ]
    pd.DataFrame(rows).to_parquet(raw_dir / "ESM25-CME.parquet", index=False)

    out = load_scid_record_execution_data(
        {
            "raw_dir": str(raw_dir),
            "roll_calendar": str(roll_calendar),
            "root_symbol": "ES",
            "timezone": "America/New_York",
            "rth_start": "09:30:00",
            "rth_end": "11:00:00",
            "allow_unverified_for_tests": True,
        },
        date_bounds={"start_date": "2025-06-09", "end_date": "2025-06-09"},
    )

    assert list(out["close"]) == [6000.00, 6000.25, 6001.00]
    assert list(out["open"]) == list(out["close"])
    assert list(out["high"]) == list(out["close"])
    assert list(out["low"]) == list(out["close"])
    assert list(out["raw_scid_high"]) == list(out["close"])
    assert list(out["raw_scid_low"]) == list(out["close"])
    assert list(out["raw_scid_close"]) == list(out["close"])
    assert list(out["signed_volume"]) == [-2, 3, -1]
    assert set(out["price_path_semantics"]) == {SCID_RECORD_PRICE_PATH_SEMANTICS}
    assert out.attrs["detail_granularity"] == "normalized_trade_event"
    assert out.attrs["price_path_semantics"] == SCID_RECORD_PRICE_PATH_SEMANTICS
