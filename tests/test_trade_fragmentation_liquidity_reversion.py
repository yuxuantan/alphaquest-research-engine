import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.trade_fragmentation_liquidity_reversion import (
    TradeFragmentationLiquidityReversionEntry,
)


def _bar(
    timestamp: str,
    *,
    return_ticks: float = 3.0,
    trade_count_rank: float = 0.8,
    avg_trade_size_rank: float = 0.3,
    is_rth: bool = True,
):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "trade_orderflow_trades_15": 5000.0,
            "trade_orderflow_trades_15_rank42": trade_count_rank,
            "trade_orderflow_avg_trade_size_15": 1.7,
            "trade_orderflow_avg_trade_size_15_rank42": avg_trade_size_rank,
            "trade_orderflow_return_ticks_15": return_ticks,
        }
    )


def test_fragmentation_entry_fades_up_move_on_completed_bar():
    entry = TradeFragmentationLiquidityReversionEntry(
        {
            "setup_mode": "fragmented_up_fade",
            "entry_time": "10:00:00",
            "flatten_time": "10:20:00",
            "window_minutes": 15,
            "rank_window": 42,
            "return_mode": "up",
            "trade_count_rank_threshold": 0.65,
            "avg_trade_size_rank_threshold": 0.40,
            "min_return_ticks": 2.0,
            "stop_pct": 0.003,
            "target_r_multiple": 1.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-04 09:58")) is None
    signal = entry.on_bar_close(_bar("2024-01-04 09:59"))

    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-04 10:00", tz="America/New_York")
    assert signal.report_fields["feature_method"] == "completed_bar_trade_fragmentation_liquidity_reversion"
    assert signal.report_fields["trade_count_rank"] == pytest.approx(0.8)
    assert signal.report_fields["avg_trade_size_rank"] == pytest.approx(0.3)
    assert signal.metadata["flatten_time"] == "10:20:00"


def test_fragmentation_entry_requires_both_fragmentation_ranks_and_trade_limit():
    entry = TradeFragmentationLiquidityReversionEntry(
        {
            "entry_time": "10:00:00",
            "window_minutes": 15,
            "return_mode": "down",
            "trade_count_rank_threshold": 0.65,
            "avg_trade_size_rank_threshold": 0.40,
            "min_return_ticks": 2.0,
            "max_trades_per_day": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-04 09:59", return_ticks=-3.0, trade_count_rank=0.5)) is None
    assert entry.on_bar_close(_bar("2024-01-04 09:59", return_ticks=-3.0, avg_trade_size_rank=0.6)) is None
    assert entry.on_bar_close(_bar("2024-01-04 09:59", return_ticks=-3.0), trades_today=1) is None

    signal = entry.on_bar_close(_bar("2024-01-04 09:59", return_ticks=-3.0), trades_today=0)
    assert signal.direction == "long"


def test_fragmentation_entry_uses_slots_and_two_sided_direction():
    entry = TradeFragmentationLiquidityReversionEntry(
        {
            "window_minutes": 15,
            "return_mode": "both",
            "trade_count_rank_threshold": 0.65,
            "avg_trade_size_rank_threshold": 0.40,
            "min_return_ticks": 2.0,
            "max_trades_per_day": 2,
            "slots": [
                {"slot_id": "first", "entry_time": "10:00:00", "flatten_time": "10:20:00"},
                {"slot_id": "second", "entry_time": "10:30:00", "flatten_time": "10:50:00"},
            ],
        }
    )

    early = entry.on_bar_close(_bar("2024-01-04 09:59", return_ticks=3.0))
    late = entry.on_bar_close(_bar("2024-01-04 10:29", return_ticks=-3.0), trades_today=1)

    assert early.direction == "short"
    assert early.report_fields["slot_id"] == "first"
    assert late.direction == "long"
    assert late.report_fields["slot_id"] == "second"
    assert entry.on_bar_close(_bar("2024-01-04 10:29", return_ticks=-3.0), trades_today=2) is None
