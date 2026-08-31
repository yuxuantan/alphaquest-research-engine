from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from alphaquest.authoring.models import EventExecutionSourceV1
from alphaquest.data.scid_execution import (
    SCID_RECORD_PRICE_PATH_SEMANTICS,
    SIERRA_CANONICAL_SESSION_CACHE_SCHEMA,
    _datetime_to_scid_us,
    _load_cached_session_events,
    load_scid_record_execution_data,
)


def test_scid_execution_loader_emits_normalized_trade_events(tmp_path, monkeypatch):
    monkeypatch.setattr("alphaquest.data.scid_execution._is_bar_like_contract", lambda symbol, path: False)

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


def test_full_rth_sierra_source_requires_dedicated_capability():
    common = {
        "source": "sierra_scid_records",
        "raw_dir": "/tmp/scid",
        "raw_manifest": "raw.json",
        "raw_manifest_sha256": "a" * 64,
        "session_levels": "levels.parquet",
        "session_levels_sha256": "b" * 64,
        "quality_manifest": "quality.csv",
        "quality_manifest_sha256": "c" * 64,
        "concordance_report": "concordance.json",
        "concordance_report_sha256": "d" * 64,
        "ineligible_session_policy": "blackout",
        "roll_calendar": "roll.csv",
        "roll_calendar_sha256": "e" * 64,
        "root_symbol": "ES",
        "rth_end": "16:00:00",
    }

    with pytest.raises(ValueError, match="dedicated full_rth"):
        EventExecutionSourceV1(
            **common,
            required_capability="full_strategy_events_extrapolated",
        )

    source = EventExecutionSourceV1(
        **common,
        required_capability="full_rth_strategy_events_extrapolated",
    )
    assert source.rth_end == "16:00:00"


def test_canonical_session_cache_is_hash_bound_and_reuses_reconstruction(
    tmp_path, monkeypatch
):
    source = tmp_path / "ESM26-CME.parquet"
    source.write_bytes(b"governed raw placeholder")
    cache_root = tmp_path / "cache"
    calls = []

    def reconstruct(*_args, **_kwargs):
        calls.append("reconstructed")
        base = pd.Timestamp("2026-01-05 09:30:00", tz="America/New_York")
        frame = pd.DataFrame(
            {
                "timestamp": [base, base + pd.Timedelta(milliseconds=1)],
                "source_ordinal": [0, 1],
                "contract_symbol": ["ESM26", "ESM26"],
                "close": [6000.0, 6000.25],
                "volume": [2, 3],
                "side": ["A", "B"],
                "signed_volume": [-2, 3],
            }
        )
        frame.attrs["timestamp_reconstruction"] = {"inversion_count": 0}
        frame.attrs["source_quality_label"] = "test governed reconstruction"
        return frame

    monkeypatch.setattr("alphaquest.data.scid_execution._load_session_events", reconstruct)
    kwargs = {
        "path": source,
        "session_date": "2026-01-05",
        "root_symbol": "ES",
        "contract_symbol": "ESM26",
        "rth_start_minute": 570,
        "rth_end_minute": 660,
        "required_capability": "full_strategy_events_extrapolated",
        "timestamp_inversion_policy": "preserve_source_order_below_threshold",
        "max_timestamp_inversion_rate": 0.002,
        "raw_file_sha256": "a" * 64,
        "cache_root": cache_root,
        "timezone": "America/New_York",
    }

    first = _load_cached_session_events(**kwargs)
    second = _load_cached_session_events(**kwargs)

    assert calls == ["reconstructed"]
    assert first.attrs["canonical_session_cache"]["hit"] is False
    assert second.attrs["canonical_session_cache"]["hit"] is True
    assert second.attrs["canonical_session_cache"]["schema"] == SIERRA_CANONICAL_SESSION_CACHE_SCHEMA
    assert second.attrs["timestamp_reconstruction"] == {"inversion_count": 0}
    pd.testing.assert_frame_equal(first, second, check_flags=False, check_freq=False)

    manifest = next(cache_root.glob("*/*/manifest.json"))
    events = manifest.parent / "events.parquet"
    events.write_bytes(events.read_bytes() + b"tamper")
    repaired = _load_cached_session_events(**kwargs)

    assert calls == ["reconstructed", "reconstructed"]
    assert repaired.attrs["canonical_session_cache"]["hit"] is False


def test_canonical_session_cache_misses_when_raw_identity_changes(tmp_path, monkeypatch):
    source = tmp_path / "ESM26-CME.parquet"
    source.write_bytes(b"governed raw placeholder")
    calls = []

    def reconstruct(*_args, **_kwargs):
        calls.append("reconstructed")
        return pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-05 09:30:00-05:00"]),
                "source_ordinal": [0],
                "contract_symbol": ["ESM26"],
                "close": [6000.0],
                "volume": [2],
                "side": ["A"],
                "signed_volume": [-2],
            }
        )

    monkeypatch.setattr("alphaquest.data.scid_execution._load_session_events", reconstruct)
    base = {
        "path": source,
        "session_date": "2026-01-05",
        "root_symbol": "ES",
        "contract_symbol": "ESM26",
        "rth_start_minute": 570,
        "rth_end_minute": 660,
        "required_capability": "full_strategy_events_extrapolated",
        "timestamp_inversion_policy": "preserve_source_order_below_threshold",
        "max_timestamp_inversion_rate": 0.002,
        "cache_root": tmp_path / "cache",
        "timezone": "America/New_York",
    }

    first = _load_cached_session_events(**base, raw_file_sha256="a" * 64)
    changed = _load_cached_session_events(**base, raw_file_sha256="b" * 64)

    assert calls == ["reconstructed", "reconstructed"]
    assert first.attrs["canonical_session_cache"]["cache_key"] != changed.attrs[
        "canonical_session_cache"
    ]["cache_key"]
