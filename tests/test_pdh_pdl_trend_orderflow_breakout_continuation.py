import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.pdh_pdl_trend_orderflow_breakout_continuation import (
    PdhPdlTrendOrderflowBreakoutContinuationEntry,
)


def test_trend_orderflow_breakout_emits_long_when_prior_level_break_aligns_with_trend_and_flow():
    entry = PdhPdlTrendOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "fresh_close_break",
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 2,
            "close_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
        }
    )

    for bar in _rising_long_bars()[:-1]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(_rising_long_bars()[-1])

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_high_breakout"
    assert signal.report_fields["orderflow_imbalance"] == 0.4
    assert signal.report_fields["trend_direction"] == "long"
    assert signal.report_fields["short_trend_current_high"] == 101.0


def test_trend_orderflow_breakout_rejects_breakout_without_completed_trend_alignment():
    entry = PdhPdlTrendOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "fresh_close_break",
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 2,
            "close_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
        }
    )

    bars = _flat_then_breakout_bars()
    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    assert entry.on_bar_close(bars[-1]) is None


def test_trend_orderflow_level_hold_does_not_require_fresh_break_flag():
    entry = PdhPdlTrendOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "trend_level_hold",
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 2,
            "close_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
        }
    )

    bars = _rising_long_bars()
    bars[-1]["prev_rth_high_fresh"] = False
    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(bars[-1])

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_high_trend_hold"


def test_engine_enters_trend_orderflow_breakout_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=8, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [94.0, 95.0, 96.0, 97.0, 98.0, 99.0, 100.75, 100.75],
            "high": [95.0, 96.0, 97.0, 98.0, 99.0, 101.0, 101.0, 100.75],
            "low": [93.0, 94.0, 95.0, 96.0, 97.0, 98.5, 100.0, 100.25],
            "close": [94.5, 95.5, 96.5, 97.5, 98.5, 100.75, 100.75, 100.5],
            "volume": [1000] * len(timestamps),
            "volume_ratio": [1.0] * len(timestamps),
            "signed_volume": [0, 0, 0, 0, 0, 400, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [100] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [100] * len(timestamps),
            "prev_rth_high": [100.0] * len(timestamps),
            "prev_rth_low": [90.0] * len(timestamps),
            "prev_rth_high_fresh": [False, False, False, False, False, True, False, False],
            "prev_rth_low_fresh": [False] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_trend_orderflow_pdh_break",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "pdh_pdl_trend_orderflow_breakout_continuation",
                "params": {
                    "setup_mode": "fresh_close_break",
                    "start_time": "09:30:00",
                    "end_time": "10:30:00",
                    "short_trend_bars": 2,
                    "long_trend_bars": 3,
                    "min_trend_move_ticks": 2,
                    "close_buffer_ticks": 1,
                    "min_orderflow_imbalance": 0.20,
                    "orderflow_mode": "signed",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                    "flatten_time": "10:05:00",
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:05:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:05:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["entry_timestamp"]) == "2024-01-03 10:00:00-05:00"
    assert trade["entry_price"] == 101.0
    assert trade["trend_direction"] == "long"


def _rising_long_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="5min")
    highs = [95.0, 96.0, 97.0, 98.0, 99.0, 101.0]
    lows = [93.0, 94.0, 95.0, 96.0, 97.0, 98.5]
    closes = [94.5, 95.5, 96.5, 97.5, 98.5, 100.75]
    return [
        _bar(ts, high=high, low=low, close=close, signed_volume=400 if idx == 5 else 0, fresh_high=idx == 5)
        for idx, (ts, high, low, close) in enumerate(zip(timestamps, highs, lows, closes))
    ]


def _flat_then_breakout_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="5min")
    highs = [98.0, 98.25, 98.0, 98.25, 98.0, 101.0]
    lows = [96.0, 96.0, 95.75, 95.75, 95.5, 95.75]
    closes = [97.0, 97.0, 96.75, 96.75, 96.5, 100.75]
    return [
        _bar(ts, high=high, low=low, close=close, signed_volume=400 if idx == 5 else 0, fresh_high=idx == 5)
        for idx, (ts, high, low, close) in enumerate(zip(timestamps, highs, lows, closes))
    ]


def _bar(
    timestamp,
    *,
    high: float,
    low: float,
    close: float,
    signed_volume: float = 0.0,
    fresh_high: bool = False,
) -> pd.Series:
    return pd.Series(
        {
            "timestamp": pd.Timestamp(timestamp),
            "session_date": pd.Timestamp(timestamp).date(),
            "is_rth": True,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0,
            "volume_ratio": 1.0,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0.0,
            "large10_volume": 100.0,
            "large20_signed_volume": 0.0,
            "large20_volume": 100.0,
            "prev_rth_high": 100.0,
            "prev_rth_low": 90.0,
            "prev_rth_high_fresh": fresh_high,
            "prev_rth_low_fresh": False,
        }
    )
