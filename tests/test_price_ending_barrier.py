from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.market_structure_filtered_entry import MarketStructureFilteredEntry
from alphaquest.strategy_modules.entry.price_ending_barrier import PriceEndingBarrierEntry


def test_price_ending_barrier_support_reclaim_uses_completed_bar_close():
    entry = PriceEndingBarrierEntry(
        {
            "setup_mode": "support_reclaim_long",
            "start_time": "09:35:00",
            "end_time": "12:00:00",
            "level_interval_points": 100,
            "level_endings": [20, 80],
            "buffer_ticks": 1,
            "max_close_distance_ticks": 12,
            "bar_interval_minutes": 5,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:55", low=25619.75, close=25620.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 25620
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["price_ending_level"] == 25620
    assert signal.report_fields["level_ending"] == 20


def test_price_ending_barrier_resistance_rejects_only_configured_endings():
    entry = PriceEndingBarrierEntry(
        {
            "setup_mode": "resistance_reject_short",
            "level_interval_points": 100,
            "level_endings": [20, 80],
            "buffer_ticks": 1,
            "max_close_distance_ticks": 12,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 10:00", high=25650.25, close=25649.5)) is None
    signal = entry.on_bar_close(_bar("2024-01-04 10:00", high=25680.25, close=25679.5))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 25680
    assert signal.report_fields["level_ending"] == 80


def test_price_ending_barrier_breakout_waits_for_prior_completed_close():
    entry = PriceEndingBarrierEntry(
        {
            "setup_mode": "upside_breakout_long",
            "level_interval_points": 100,
            "level_endings": [20, 80],
            "buffer_ticks": 1,
            "max_close_distance_ticks": 12,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:35", low=25678.0, close=25679.5)) is None
    signal = entry.on_bar_close(_bar("2024-01-03 09:40", high=25681.0, low=25679.25, close=25680.5))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "price_ending_upside_breakout"
    assert signal.swept_level == 25680


def test_price_ending_barrier_rejects_non_rth_and_one_trade_per_day():
    entry = PriceEndingBarrierEntry({"setup_mode": "two_sided_reclaim"})

    assert entry.on_bar_close(_bar("2024-01-03 10:00", low=25619.75, close=25620.5, is_rth=False)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:05", low=25619.75, close=25620.5)) is not None
    assert entry.on_bar_close(_bar("2024-01-03 10:10", low=25679.75, close=25680.5)) is None


def test_price_ending_barrier_factory_registration_builds_module():
    entry = build_entry_module({"module": "price_ending_barrier", "params": {"setup_mode": "support_reclaim_long"}})

    assert isinstance(entry, PriceEndingBarrierEntry)


def test_market_structure_filter_supports_price_ending_base_module():
    entry = MarketStructureFilteredEntry(
        {
            "bar_interval_minutes": 5,
            "timeframes_minutes": [5],
            "min_aligned_timeframes": 1,
            "pivot_left_bars": 1,
            "pivot_right_bars": 1,
            "min_pivot_move_ticks": 0,
            "base_module": "price_ending_barrier",
            "base_params": {
                "setup_mode": "support_reclaim_long",
                "start_time": "10:10:00",
                "end_time": "10:30:00",
                "bar_interval_minutes": 5,
                "level_interval_points": 100,
                "level_endings": [20, 80],
                "buffer_ticks": 1,
                "max_close_distance_ticks": 8,
            },
        }
    )

    signal = None
    for bar in _pivot_bars_shifted_to_20_ending():
        signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["price_ending_level"] == 25620
    assert signal.report_fields["market_structure_filter_direction"] == "long"


def _bar(timestamp: str, *, low: float | None = None, high: float | None = None, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    low = close - 1.0 if low is None else low
    high = close + 1.0 if high is None else high
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.25,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
        }
    )


def _pivot_bars_shifted_to_20_ending() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=9, freq="5min")
    shift = 25520.0
    return [
        pd.Series(
            {
                "timestamp": ts,
                "session_date": ts.date(),
                "session_label": "RTH",
                "is_rth": True,
                "volume": 1000,
                **{key: value + shift for key, value in row.items()},
            }
        )
        for ts, row in zip(timestamps, _pivot_ohlc_rows())
    ]


def _pivot_ohlc_rows() -> list[dict]:
    return [
        {"open": 100.0, "high": 100.5, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.5},
        {"open": 101.5, "high": 101.0, "low": 99.5, "close": 100.0},
        {"open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0},
        {"open": 99.0, "high": 100.0, "low": 99.0, "close": 99.5},
        {"open": 99.5, "high": 103.0, "low": 100.0, "close": 102.0},
        {"open": 102.0, "high": 102.0, "low": 99.5, "close": 100.5},
        {"open": 100.5, "high": 101.0, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.0},
    ]
