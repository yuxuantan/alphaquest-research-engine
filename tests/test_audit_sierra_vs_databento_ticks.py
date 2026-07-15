from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from tools.audit_sierra_vs_databento_ticks import (
    datetime_to_scid_us,
    reconstruct_sierra_events,
    strict_big_trade_events,
)


def test_reconstruct_sierra_unbundled_trade_preserves_order_and_sums_volume() -> None:
    base = datetime_to_scid_us(datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc))
    frame = pd.DataFrame(
        {
            "scid_datetime_us": [base, base + 1, base + 2, base + 3, base + 4],
            "open": [0.0, -1.999001e37, 0.0, -1.999002e37, 0.0],
            "close": [7000.0, 7000.25, 7000.25, 7000.25, 7000.5],
            "num_trades": [1, 1, 1, 1, 1],
            "volume": [2, 1, 2, 3, 4],
            "bid_volume": [0, 1, 2, 3, 0],
            "ask_volume": [2, 0, 0, 0, 4],
            "side": ["B", "A", "A", "A", "B"],
            "source_ordinal": range(5),
        }
    )

    events, stats = reconstruct_sierra_events(frame)

    assert stats["marker_valid"] is True
    assert stats["first_markers"] == 1
    assert events[["price", "size", "side"]].to_dict(orient="records") == [
        {"price": 7000.0, "size": 2, "side": "B"},
        {"price": 7000.25, "size": 6, "side": "A"},
        {"price": 7000.5, "size": 4, "side": "B"},
    ]


def test_strict_big_trade_requires_over_200_and_uninterrupted_sequence() -> None:
    events = pd.DataFrame(
        {
            "timestamp_ns": [0, 50_000_000, 60_000_000, 70_000_000, 80_000_000],
            "price": [7000.0, 7000.0, 7000.25, 7000.0, 7000.0],
            "size": [100, 101, 1, 150, 50],
            "side": ["B", "B", "A", "B", "B"],
        }
    )

    triggers = strict_big_trade_events(events)

    assert triggers["event_index"].tolist() == [1]
