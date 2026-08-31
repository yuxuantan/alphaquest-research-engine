from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.data.sierra_events import reconstruct_sierra_trade_events


def test_reconstructs_unbundled_trade_and_preserves_first_source_order() -> None:
    frame = pd.DataFrame(
        {
            "scid_datetime_us": [10, 11, 12, 13, 14],
            "open": [0.0, -1.999001e37, 0.0, -1.999002e37, 0.0],
            "close": [6000.0, 6000.25, 6000.25, 6000.25, 6000.5],
            "volume": [2, 1, 2, 3, 4],
            "bid_volume": [0, 1, 2, 3, 0],
            "ask_volume": [2, 0, 0, 0, 4],
            "source_ordinal": [0, 1, 2, 3, 4],
        }
    )

    events, stats = reconstruct_sierra_trade_events(frame)

    assert stats["marker_valid"] is True
    assert events[["price", "volume", "side", "source_ordinal"]].to_dict("records") == [
        {"price": 6000.0, "volume": 2, "side": "B", "source_ordinal": 0},
        {"price": 6000.25, "volume": 6, "side": "A", "source_ordinal": 1},
        {"price": 6000.5, "volume": 4, "side": "B", "source_ordinal": 4},
    ]


def test_reconstruction_rejects_timestamp_inversion_instead_of_sorting() -> None:
    frame = pd.DataFrame(
        {
            "scid_datetime_us": [11, 10],
            "open": [0.0, 0.0],
            "close": [6000.0, 6000.25],
            "volume": [1, 1],
            "bid_volume": [0, 1],
            "ask_volume": [1, 0],
            "source_ordinal": [0, 1],
        }
    )

    with pytest.raises(ValueError, match="refusing to reorder"):
        reconstruct_sierra_trade_events(frame)


def test_reconstruction_can_clamp_governed_tiny_inversions_without_reordering() -> None:
    row_count = 1001
    timestamps = list(range(10_000, 10_000 + row_count))
    timestamps[500] = timestamps[499] - 3
    frame = pd.DataFrame(
        {
            "scid_datetime_us": timestamps,
            "open": [0.0] * row_count,
            "close": [6000.0] * row_count,
            "volume": [1] * row_count,
            "bid_volume": [0] * row_count,
            "ask_volume": [1] * row_count,
            "source_ordinal": list(range(row_count)),
        }
    )

    events, stats = reconstruct_sierra_trade_events(
        frame,
        timestamp_inversion_policy="preserve_source_order_clamp",
        max_timestamp_inversion_rate=0.002,
    )

    assert events["source_ordinal"].tolist() == list(range(row_count))
    assert events["scid_datetime_us"].is_monotonic_increasing
    assert events.loc[500, "source_scid_datetime_us"] == timestamps[500]
    assert events.loc[500, "scid_datetime_us"] == timestamps[499]
    assert stats["timestamp_inversion_count"] == 1
    assert stats["timestamp_inversion_rate"] == pytest.approx(1 / row_count)
    assert stats["clamped_timestamp_count"] == 1
    assert stats["maximum_backward_jump_us"] == 3


def test_reconstruction_rejects_inversions_above_governed_ceiling() -> None:
    frame = pd.DataFrame(
        {
            "scid_datetime_us": [10, 9, 12, 11, 14, 13, 16, 17, 18, 19, 20],
            "open": [0.0] * 11,
            "close": [6000.0] * 11,
            "volume": [1] * 11,
            "bid_volume": [0] * 11,
            "ask_volume": [1] * 11,
            "source_ordinal": list(range(11)),
        }
    )

    with pytest.raises(ValueError, match="exceeds the governed ceiling"):
        reconstruct_sierra_trade_events(
            frame,
            timestamp_inversion_policy="preserve_source_order_clamp",
            max_timestamp_inversion_rate=0.002,
        )
