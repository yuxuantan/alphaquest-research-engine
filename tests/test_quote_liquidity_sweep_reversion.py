import pandas as pd

from propstack.data.tbbo_liquidity import aggregate_tbbo_liquidity_1m
from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.quote_liquidity_sweep_reversion import (
    QuoteLiquiditySweepReversionEntry,
)


def test_tbbo_liquidity_cache_builds_refill_and_aggressive_imbalance_features():
    events = pd.DataFrame(
        [
            {
                "ts_event": "2026-06-10T13:30:10Z",
                "symbol": "ESM6",
                "price": 100.00,
                "size": 20,
                "side": "A",
                "bid_px_00": 99.75,
                "ask_px_00": 100.00,
                "bid_sz_00": 20,
                "ask_sz_00": 80,
            },
            {
                "ts_event": "2026-06-10T13:31:15Z",
                "symbol": "ESM6",
                "price": 100.25,
                "size": 10,
                "side": "B",
                "bid_px_00": 100.25,
                "ask_px_00": 100.50,
                "bid_sz_00": 100,
                "ask_sz_00": 50,
            },
        ]
    )

    bars = aggregate_tbbo_liquidity_1m(events, windows=[2], complete_session_end=None)

    assert list(bars["timestamp"]) == [
        pd.Timestamp("2026-06-10 09:30:00"),
        pd.Timestamp("2026-06-10 09:31:00"),
    ]
    second = bars.iloc[1]
    assert second["tbbo_bid_refill_ratio_2"] > 4.0
    assert round(second["tbbo_aggressive_imbalance_2"], 6) == round(-10 / 30, 6)
    assert second["tbbo_spread_ticks_max_2"] == 1.0


def test_quote_liquidity_sweep_reversion_emits_long_after_pdl_sweep_with_bid_refill():
    entry = QuoteLiquiditySweepReversionEntry(
        {
            "level_set": "previous_rth",
            "start_time": "09:35:00",
            "end_time": "10:00:00",
            "bar_interval_minutes": 1,
            "tick_size": 0.25,
            "min_sweep_ticks": 2,
            "reclaim_window_bars": 2,
            "depth_window": 3,
            "min_refill_ratio": 2.0,
            "min_quote_imbalance": 0.20,
            "max_spread_ticks": 2.0,
            "require_liquidity_demand": True,
            "min_failed_demand_imbalance": 0.20,
            "target_r_multiple": 1.5,
        }
    )

    assert entry.on_bar_close(
        _quote_bar("2026-06-10 09:35", low=99.25, close=99.50, demand=-0.40, bid_refill=1.0)
    ) is None
    signal = entry.on_bar_close(
        _quote_bar("2026-06-10 09:36", low=99.50, high=100.50, close=100.25, demand=-0.30, bid_refill=3.0)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_low"
    assert signal.swept_level == 100.0
    assert signal.sweep_low == 99.25
    assert signal.reclaim_timestamp == pd.Timestamp("2026-06-10 09:37", tz="America/New_York")
    assert signal.metadata["target_r_multiple"] == 1.5
    assert signal.report_fields["tbbo_quote_imbalance_close"] == 0.30


def test_quote_liquidity_sweep_reversion_rejects_reclaim_without_refill():
    entry = QuoteLiquiditySweepReversionEntry(
        {
            "level_set": "previous_rth",
            "start_time": "09:35:00",
            "end_time": "10:00:00",
            "min_sweep_ticks": 2,
            "depth_window": 3,
            "min_refill_ratio": 2.0,
            "min_quote_imbalance": 0.20,
            "max_spread_ticks": 2.0,
        }
    )

    assert entry.on_bar_close(_quote_bar("2026-06-10 09:35", low=99.25, close=99.50)) is None
    assert entry.on_bar_close(_quote_bar("2026-06-10 09:36", low=99.50, close=100.25, bid_refill=1.2)) is None


def test_quote_liquidity_sweep_reversion_emits_short_after_opening_range_sweep():
    entry = build_entry_module(
        {
            "module": "quote_liquidity_sweep_reversion",
            "params": {
                "level_set": "opening_range",
                "opening_range_minutes": 2,
                "start_time": "09:32:00",
                "end_time": "10:00:00",
                "min_sweep_ticks": 2,
                "depth_window": 3,
                "min_refill_ratio": 2.0,
                "min_quote_imbalance": 0.20,
                "max_spread_ticks": 2.0,
                "require_liquidity_demand": True,
                "min_failed_demand_imbalance": 0.20,
                "allow_long": False,
                "allow_short": True,
            },
        }
    )

    assert entry.on_bar_close(_quote_bar("2026-06-10 09:30", high=101.0, low=100.0, close=100.5)) is None
    assert entry.on_bar_close(_quote_bar("2026-06-10 09:31", high=102.0, low=100.25, close=101.5)) is None
    signal = entry.on_bar_close(
        _quote_bar(
            "2026-06-10 09:32",
            high=102.75,
            low=101.25,
            close=101.75,
            quote_imbalance=-0.30,
            demand=0.35,
            ask_refill=3.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.level_type == "opening_range_2m_high"
    assert signal.swept_level == 102.0
    assert signal.opening_range_high == 102.0
    assert signal.opening_range_low == 100.0


def _quote_bar(
    timestamp,
    *,
    open_=100.0,
    high=100.25,
    low=99.75,
    close=100.0,
    prev_low=100.0,
    prev_high=110.0,
    bid_refill=3.0,
    ask_refill=3.0,
    quote_imbalance=0.30,
    demand=-0.30,
    spread=1.0,
):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
            "prev_rth_low": prev_low,
            "prev_rth_high": prev_high,
            "tbbo_quote_imbalance_close": quote_imbalance,
            "tbbo_bid_refill_ratio_3": bid_refill,
            "tbbo_ask_refill_ratio_3": ask_refill,
            "tbbo_aggressive_imbalance_3": demand,
            "tbbo_spread_ticks_max_3": spread,
        }
    )
