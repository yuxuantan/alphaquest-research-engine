import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.trend_filtered_prior_value_area_acceptance import (
    TrendFilteredPriorValueAreaAcceptanceEntry,
)


def test_trend_filtered_value_area_acceptance_emits_long_with_completed_trend_and_flow():
    entry = TrendFilteredPriorValueAreaAcceptanceEntry(
        {
            "setup_mode": "vah_acceptance_long",
            "start_time": "09:35:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "min_prior_profile_bars": 2,
            "breakout_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 2,
            "allow_long": True,
            "allow_short": False,
        }
    )

    for bar in _prior_profile_bars():
        assert entry.on_bar_close(bar) is None
    for bar in _rising_current_session_bars()[:-1]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(_rising_current_session_bars()[-1])

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "prior_value_area_vah_acceptance"
    assert signal.report_fields["orderflow_imbalance"] == 0.4
    assert signal.report_fields["trend_direction"] == "long"
    assert signal.report_fields["short_trend_current_high"] == 101.25


def test_trend_filtered_value_area_acceptance_rejects_without_completed_trend_alignment():
    entry = TrendFilteredPriorValueAreaAcceptanceEntry(
        {
            "setup_mode": "vah_acceptance_long",
            "start_time": "09:35:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "min_prior_profile_bars": 2,
            "breakout_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 2,
            "allow_long": True,
            "allow_short": False,
        }
    )

    for bar in _prior_profile_bars():
        assert entry.on_bar_close(bar) is None
    for bar in _flat_then_break_current_session_bars()[:-1]:
        assert entry.on_bar_close(bar) is None

    rejected = entry.on_bar_close(_flat_then_break_current_session_bars()[-1])

    assert rejected is None
    assert pd.Timestamp("2024-01-03").date() not in entry.signaled_sessions


def test_engine_enters_trend_filtered_value_area_acceptance_on_next_bar_open():
    timestamps = pd.date_range("2024-01-02 09:30:00", periods=10, freq="5min", tz="America/New_York")
    current_timestamps = pd.date_range("2024-01-03 09:30:00", periods=7, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": list(timestamps[:2]) + list(current_timestamps),
            "symbol": ["ES"] * 9,
            "session_date": [timestamps[0].date()] * 2 + [current_timestamps[0].date()] * 7,
            "session_label": ["RTH"] * 9,
            "is_rth": [True] * 9,
            "open": [100.0, 100.0, 94.0, 95.0, 96.0, 97.0, 98.0, 100.75, 101.25],
            "high": [100.5, 100.5, 95.0, 96.0, 97.0, 98.0, 99.0, 101.25, 101.5],
            "low": [99.5, 99.5, 93.0, 94.0, 95.0, 96.0, 97.0, 98.5, 100.75],
            "close": [100.0, 100.0, 94.5, 95.5, 96.5, 97.5, 98.5, 100.75, 101.0],
            "volume": [1000.0] * 9,
            "signed_volume": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 400.0, 0.0],
            "large10_signed_volume": [0.0] * 9,
            "large10_volume": [100.0] * 9,
            "large20_signed_volume": [0.0] * 9,
            "large20_volume": [100.0] * 9,
        }
    )
    cfg = {
        "strategy_name": "test_trend_filtered_value_area_acceptance",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "trend_filtered_prior_value_area_acceptance",
                "params": {
                    "setup_mode": "vah_acceptance_long",
                    "start_time": "09:35:00",
                    "end_time": "10:30:00",
                    "bar_interval_minutes": 5,
                    "tick_size": 0.25,
                    "min_prior_profile_bars": 2,
                    "breakout_buffer_ticks": 1,
                    "min_orderflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "short_trend_bars": 2,
                    "long_trend_bars": 3,
                    "min_trend_move_ticks": 2,
                    "allow_long": True,
                    "allow_short": False,
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
    assert trade["entry_price"] == 101.5
    assert trade["trend_direction"] == "long"


def _prior_profile_bars() -> list[pd.Series]:
    return [
        _bar("2024-01-02 09:30", high=100.5, low=99.5, close=100.0),
        _bar("2024-01-02 09:35", high=100.5, low=99.5, close=100.0),
    ]


def _rising_current_session_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="5min")
    highs = [95.0, 96.0, 97.0, 98.0, 99.0, 101.25]
    lows = [93.0, 94.0, 95.0, 96.0, 97.0, 98.5]
    closes = [94.5, 95.5, 96.5, 97.5, 98.5, 100.75]
    return [
        _bar(ts, high=high, low=low, close=close, signed_volume=400.0 if idx == 5 else 0.0)
        for idx, (ts, high, low, close) in enumerate(zip(timestamps, highs, lows, closes))
    ]


def _flat_then_break_current_session_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="5min")
    highs = [98.0, 98.25, 98.0, 98.25, 98.0, 101.25]
    lows = [96.0, 96.0, 95.75, 95.75, 95.5, 95.75]
    closes = [97.0, 97.0, 96.75, 96.75, 96.5, 100.75]
    return [
        _bar(ts, high=high, low=low, close=close, signed_volume=400.0 if idx == 5 else 0.0)
        for idx, (ts, high, low, close) in enumerate(zip(timestamps, highs, lows, closes))
    ]


def _bar(
    timestamp,
    *,
    high: float,
    low: float,
    close: float,
    signed_volume: float = 0.0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0.0,
            "large10_volume": 100.0,
            "large20_signed_volume": 0.0,
            "large20_volume": 100.0,
        }
    )
