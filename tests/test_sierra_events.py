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
