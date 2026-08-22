from __future__ import annotations

import numpy as np
import pandas as pd

from tools.build_yush_big_trade_context import (
    _motivewave_consecutive_sizes,
    _nearest_rank_percentile_from_histogram,
    _session_volume_histogram,
)
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
)


def test_context_aggregation_matches_same_price_side_100ms_rule():
    events = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-05-04 09:30:00.010-04:00",
                    "2026-05-04 09:30:00.090-04:00",
                    "2026-05-04 09:30:00.090-04:00",
                    "2026-05-04 09:30:00.110-04:00",
                    "2026-05-04 09:30:00.120-04:00",
                ],
                utc=True,
            ).tz_convert("America/New_York"),
            "close": [100.0, 100.0, 100.0, 100.0, 100.25],
            "volume": [10, 15, 7, 20, 9],
            "side": ["B", "B", "A", "B", "N"],
        }
    )

    histogram, count = _session_volume_histogram(
        events,
        tick_size=0.25,
        interval_ms=100,
    )

    assert count == 3
    assert histogram[7] == 1
    assert histogram[20] == 1
    assert histogram[25] == 1


def test_context_percentile_uses_nearest_rank_higher():
    histogram = np.zeros(101, dtype=np.int64)
    histogram[1:101] = 1

    assert _nearest_rank_percentile_from_histogram(histogram, 0.995) == 100
    assert _nearest_rank_percentile_from_histogram(histogram, 0.50) == 50


def test_motivewave_context_keeps_only_consecutive_matching_executions():
    events = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-05-04 09:30:00.000-04:00",
                    "2026-05-04 09:30:00.010-04:00",
                    "2026-05-04 09:30:00.020-04:00",
                    "2026-05-04 09:30:00.030-04:00",
                    "2026-05-04 09:30:00.040-04:00",
                ],
                utc=True,
            ).tz_convert("America/New_York"),
            "close": [100.0, 100.0, 100.25, 100.0, 100.0],
            "volume": [80, 107, 1, 100, 104],
            "side": ["B", "B", "A", "B", "B"],
        }
    )

    histogram, count = _session_volume_histogram(
        events,
        tick_size=0.25,
        interval_ms=100,
        aggregation_mode=BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
    )

    assert count == 3
    assert histogram[1] == 1
    assert histogram[187] == 1
    assert histogram[204] == 1


def test_motivewave_context_restarts_sequence_after_100ms_from_first_execution():
    sizes = _motivewave_consecutive_sizes(
        np.array([0, 90_000_000, 101_000_000, 190_000_000], dtype=np.int64),
        np.array([400, 400, 400, 400], dtype=np.int64),
        np.array(["B", "B", "B", "B"]),
        np.array([10, 20, 30, 40], dtype=np.int64),
        interval_ns=100_000_000,
    )

    assert sizes.tolist() == [30, 70]
