from __future__ import annotations

import numpy as np
import pandas as pd

from tools.build_yush_bar_delta_context import (
    _nearest_rank_percentile_from_histogram,
    _session_bar_delta_histogram,
)


def _events(rows: list[tuple[str, float, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [row[0] for row in rows], utc=True
            ).tz_convert("America/New_York"),
            "close": [row[1] for row in rows],
            "signed_volume": [row[2] for row in rows],
        }
    )


def test_bar_delta_context_uses_three_minute_four_tick_fixed_cells() -> None:
    histogram, observations = _session_bar_delta_histogram(
        _events(
            [
                ("2026-05-19T13:30:00Z", 7380.00, -699),
                ("2026-05-19T13:30:01Z", 7380.25, -274),
                ("2026-05-19T13:30:02Z", 7380.50, -6),
                ("2026-05-19T13:30:03Z", 7380.75, 70),
                ("2026-05-19T13:33:00Z", 7380.00, 100),
            ]
        ),
        tick_size=0.25,
        bar_seconds=180,
        price_bin_ticks=4,
    )

    assert observations == 2
    assert histogram[909] == 1
    assert histogram[100] == 1


def test_bar_delta_context_keeps_zero_delta_populated_cells_in_reference() -> None:
    histogram, observations = _session_bar_delta_histogram(
        _events(
            [
                ("2026-05-19T13:30:00Z", 7380.00, 20),
                ("2026-05-19T13:30:01Z", 7380.25, -20),
            ]
        ),
        tick_size=0.25,
        bar_seconds=180,
        price_bin_ticks=4,
    )

    assert observations == 1
    assert histogram[0] == 1


def test_bar_delta_context_uses_nearest_rank_higher_percentile() -> None:
    histogram = np.bincount(np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

    assert _nearest_rank_percentile_from_histogram(histogram, 0.90) == 80
