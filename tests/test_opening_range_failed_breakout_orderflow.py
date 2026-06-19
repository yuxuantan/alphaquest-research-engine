import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.opening_range_failed_breakout_orderflow import (
    OpeningRangeFailedBreakoutOrderflowEntry,
)
from propstack.strategy_modules.entry.opening_range_failed_breakout_trend_orderflow import (
    OpeningRangeFailedBreakoutTrendOrderflowEntry,
)


def test_opening_range_failed_breakout_orderflow_shorts_upside_reclaim_with_selling_flow():
    entry = OpeningRangeFailedBreakoutOrderflowEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "max_opening_range_pct_of_open": 0.03,
            "breakout_buffer_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "max_reclaim_bars": 2,
            "min_reclaim_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )

    for bar in _bars("2024-01-03", closes=[100.0, 100.1, 100.2, 100.1, 100.0]):
        assert entry.on_bar_close(bar) is None

    breakout = _bar("2024-01-03 09:35:00", close=100.75, high=100.9, signed_volume=500, volume=1000)
    assert entry.on_bar_close(breakout) is None
    weak_reclaim = _bar("2024-01-03 09:36:00", close=100.15, high=100.6, signed_volume=-100, volume=1000)
    assert entry.on_bar_close(weak_reclaim) is None

    entry = OpeningRangeFailedBreakoutOrderflowEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "max_opening_range_pct_of_open": 0.03,
            "breakout_buffer_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "max_reclaim_bars": 2,
            "min_reclaim_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )
    for bar in _bars("2024-01-03", closes=[100.0, 100.1, 100.2, 100.1, 100.0]):
        entry.on_bar_close(bar)
    entry.on_bar_close(breakout)
    confirmed = _bar("2024-01-03 09:36:00", close=100.15, high=100.6, signed_volume=-350, volume=1000)
    signal = entry.on_bar_close(confirmed)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.breakout_level == 100.2
    assert signal.report_fields["failed_breakout_side"] == "upside"
    assert signal.report_fields["reclaim_orderflow_imbalance"] == -0.35


def test_opening_range_failed_breakout_orderflow_longs_downside_reclaim_with_large_flow():
    entry = OpeningRangeFailedBreakoutOrderflowEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "breakout_buffer_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "max_reclaim_bars": 2,
            "min_reclaim_orderflow_imbalance": 0.50,
            "flow_mode": "large20",
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": False,
        }
    )

    for bar in _bars("2024-01-03", closes=[100.0, 100.1, 100.2, 100.1, 100.0]):
        assert entry.on_bar_close(bar) is None

    breakdown = _bar("2024-01-03 09:35:00", close=99.6, low=99.4)
    assert entry.on_bar_close(breakdown) is None
    reclaim = _bar(
        "2024-01-03 09:36:00",
        close=99.85,
        low=99.5,
        large20_signed_volume=120,
        large20_volume=200,
    )
    signal = entry.on_bar_close(reclaim)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["failed_breakout_side"] == "downside"
    assert signal.report_fields["flow_mode"] == "large20"
    assert signal.report_fields["reclaim_orderflow_imbalance"] == 0.6


def test_opening_range_failed_breakout_trend_orderflow_requires_matching_downtrend_for_short():
    entry = OpeningRangeFailedBreakoutTrendOrderflowEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "max_opening_range_pct_of_open": 0.03,
            "breakout_buffer_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "max_reclaim_bars": 2,
            "min_reclaim_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
            "short_trend_bars": 3,
            "long_trend_bars": 5,
            "min_trend_move_ticks": 1,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", close=100.5, high=100.8, low=100.2),
        _bar("2024-01-03 09:31:00", close=100.25, high=100.55, low=99.95),
        _bar("2024-01-03 09:32:00", close=100.0, high=100.3, low=99.7),
        _bar("2024-01-03 09:33:00", close=99.75, high=100.05, low=99.45),
        _bar("2024-01-03 09:34:00", close=99.5, high=99.8, low=99.2),
    ]:
        assert entry.on_bar_close(bar) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35:00", close=101.1, high=101.2, low=100.45)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:36:00", close=100.15, high=100.2, low=99.7, signed_volume=-350, volume=1000)
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.level_type.endswith("_trend_filtered")
    assert signal.report_fields["trend_filter"] == "hh_hl_lh_ll_reclaim_direction"
    assert signal.report_fields["short_trend_high_move_ticks"] >= 1
    assert signal.report_fields["long_trend_low_move_ticks"] >= 1


def test_opening_range_failed_breakout_trend_orderflow_rejects_wrong_trend():
    entry = OpeningRangeFailedBreakoutTrendOrderflowEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "max_opening_range_pct_of_open": 0.03,
            "breakout_buffer_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "max_reclaim_bars": 2,
            "min_reclaim_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
            "short_trend_bars": 3,
            "long_trend_bars": 5,
            "min_trend_move_ticks": 1,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", close=99.6, high=99.8, low=99.4),
        _bar("2024-01-03 09:31:00", close=99.7, high=99.9, low=99.5),
        _bar("2024-01-03 09:32:00", close=99.8, high=100.0, low=99.6),
        _bar("2024-01-03 09:33:00", close=99.9, high=100.1, low=99.7),
        _bar("2024-01-03 09:34:00", close=100.0, high=100.2, low=99.8),
    ]:
        assert entry.on_bar_close(bar) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35:00", close=100.75, high=100.9, low=100.45)) is None
    assert entry.on_bar_close(
        _bar("2024-01-03 09:36:00", close=99.85, high=100.2, low=99.7, signed_volume=-350, volume=1000)
    ) is None


def test_engine_enters_failed_breakout_reclaim_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=9, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100, 100, 100, 100, 100, 100.8, 100.1, 100.0, 99.9],
            "high": [100.2, 100.1, 100.2, 100.1, 100.0, 100.9, 100.3, 100.1, 100.0],
            "low": [99.8, 99.9, 99.9, 99.9, 99.9, 100.7, 99.9, 99.7, 99.6],
            "close": [100.0, 100.1, 100.2, 100.1, 100.0, 100.75, 100.15, 99.8, 99.8],
            "volume": [1000] * len(timestamps),
            "signed_volume": [0, 0, 0, 0, 0, 500, -350, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_or_failed_breakout",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "opening_range_failed_breakout_orderflow",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "bar_interval_minutes": 1,
                    "last_entry_time": "10:00:00",
                    "breakout_buffer_ticks": 1,
                    "reclaim_buffer_ticks": 0,
                    "max_reclaim_bars": 2,
                    "min_reclaim_orderflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "opening_range_edge", "params": {"stop_offset_ticks": 2, "max_stop_points": 10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:39:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:39:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["failed_breakout_timestamp"]) == "2024-01-03 09:36:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:37:00-05:00"


def _bars(session_date: str, closes: list[float]):
    out = []
    timestamps = pd.date_range(f"{session_date} 09:30:00", periods=len(closes), freq="1min")
    for ts, close in zip(timestamps, closes):
        out.append(_bar(str(ts), close=close, high=max(close, 100.2), low=min(close, 99.8)))
    return out


def _bar(
    timestamp: str,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    signed_volume: float = 0,
    volume: float = 1000,
    large20_signed_volume: float = 0,
    large20_volume: float = 0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close,
            "high": close if high is None else high,
            "low": close if low is None else low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
        }
    )
