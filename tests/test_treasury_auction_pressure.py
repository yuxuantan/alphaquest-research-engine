from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.treasury_auction_pressure import TreasuryAuctionPressureEntry
from tools.build_es_treasury_auction_calendar import build_calendar


def test_auction_calendar_builder_uses_known_coupon_auctions_only(tmp_path):
    bars = tmp_path / "bars.parquet"
    pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-09 09:30")},
            {"timestamp": pd.Timestamp("2024-01-10 09:30")},
            {"timestamp": pd.Timestamp("2024-01-11 09:30")},
        ]
    ).to_parquet(bars, index=False)
    auctions = tmp_path / "auctions.csv"
    pd.DataFrame(
        [
            _auction("Bill", "13-Week", "2024-01-09", "2024-01-04"),
            _auction("Note", "3-Year", "2024-01-09", "2024-01-04"),
            _auction("Note", "10-Year", "2024-01-10", "2024-01-04"),
            _auction("Bond", "30-Year", "2024-01-11", "2024-01-04"),
            _auction("Note", "2-Year", "2024-01-11", "2024-01-11"),
        ]
    ).to_csv(auctions, index=False)

    calendar = build_calendar(
        bars,
        tmp_path / "calendar.csv",
        auctions_input=auctions,
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    rows = {row["signal_date"]: row for row in calendar.to_dict("records")}
    assert rows["2024-01-09"]["coupon_count"] == 1
    assert rows["2024-01-09"]["note_count"] == 1
    assert rows["2024-01-09"]["bond_count"] == 0
    assert rows["2024-01-10"]["terms"] == "10-Year"
    assert rows["2024-01-11"]["coupon_count"] == 1
    assert rows["2024-01-11"]["bond_count"] == 1


def test_auction_entry_emits_on_completed_signal_bar(tmp_path):
    calendar = _calendar(tmp_path, [_calendar_row("2024-01-10", note_count=1)])
    entry = TreasuryAuctionPressureEntry(
        {
            "event_calendar_csv": str(calendar),
            "auction_scope": "all_coupon",
            "signal_time": "13:05:00",
            "bar_interval_minutes": 1,
            "direction": "short",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-10 13:03:00")) is None
    signal = entry.on_bar_close(_bar("2024-01-10 13:04:00"))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-10 13:05:00")
    assert signal.report_fields["treasury_note_count"] == 1


def test_note_only_scope_rejects_bond_only_date(tmp_path):
    calendar = _calendar(tmp_path, [_calendar_row("2024-01-11", bond_count=1)])
    entry = TreasuryAuctionPressureEntry(
        {
            "event_calendar_csv": str(calendar),
            "auction_scope": "note_only",
            "signal_time": "13:05:00",
            "direction": "short",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-11 13:04:00")) is None


def test_all_coupon_scope_accepts_bond_only_date(tmp_path):
    calendar = _calendar(tmp_path, [_calendar_row("2024-01-11", bond_count=1)])
    entry = TreasuryAuctionPressureEntry(
        {
            "event_calendar_csv": str(calendar),
            "auction_scope": "all_coupon",
            "signal_time": "13:05:00",
            "direction": "long",
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-11 13:04:00"))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["treasury_bond_count"] == 1


def test_auction_entry_rejects_non_rth_and_duplicate_day(tmp_path):
    calendar = _calendar(tmp_path, [_calendar_row("2024-01-10", note_count=1)])
    entry = TreasuryAuctionPressureEntry(
        {
            "event_calendar_csv": str(calendar),
            "auction_scope": "all_coupon",
            "signal_time": "13:05:00",
            "direction": "short",
        }
    )

    assert entry.on_bar_close(_bar("2024-01-10 13:04:00", is_rth=False)) is None
    assert entry.on_bar_close(_bar("2024-01-10 13:04:00")) is not None
    assert entry.on_bar_close(_bar("2024-01-10 13:04:00")) is None


def _auction(security_type: str, term: str, auction_date: str, announcement_date: str) -> dict:
    return {
        "record_date": auction_date,
        "security_type": security_type,
        "security_term": term,
        "auction_date": auction_date,
        "announcemt_date": announcement_date,
        "offering_amt": "1000000000",
        "total_accepted": "1000000000",
        "closing_time_comp": "01:00 PM",
    }


def _calendar(tmp_path, rows: list[dict]):
    path = tmp_path / "auction_calendar.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _calendar_row(session_date: str, *, note_count: int = 0, bond_count: int = 0) -> dict:
    return {
        "signal_date": session_date,
        "coupon_count": note_count + bond_count,
        "note_count": note_count,
        "bond_count": bond_count,
        "terms": "3-Year" if note_count else "30-Year",
    }


def _bar(timestamp: str, *, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": 5000.0,
            "high": 5001.0,
            "low": 4999.0,
            "close": 5000.25,
            "volume": 1000,
        }
    )
