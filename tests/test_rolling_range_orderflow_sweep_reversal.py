import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.rolling_range_orderflow_sweep_reversal import (
    RollingRangeOrderflowSweepReversalEntry,
)


def test_rolling_low_sweep_reclaim_requires_absorption_flow():
    entry = RollingRangeOrderflowSweepReversalEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "lookback_bars": 3,
            "min_sweep_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "flow_mode": "signed",
            "min_absorption_imbalance": 0.20,
            "tick_size": 0.25,
        }
    )

    for bar in _prior_bars():
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:33:00", high=100.2, low=98.5, close=99.2, signed_volume=-400)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 99.0
    assert signal.report_fields["orderflow_imbalance"] == -0.4


def test_rolling_low_sweep_rejects_continuation_flow():
    entry = RollingRangeOrderflowSweepReversalEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "lookback_bars": 3,
            "min_sweep_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "flow_mode": "signed",
            "min_absorption_imbalance": 0.20,
            "tick_size": 0.25,
        }
    )

    for bar in _prior_bars():
        assert entry.on_bar_close(bar) is None

    assert (
        entry.on_bar_close(
            _bar("2024-01-03 09:33:00", high=100.2, low=98.5, close=99.2, signed_volume=400)
        )
        is None
    )


def test_engine_enters_rolling_range_sweep_reversal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 99.8, 99.5, 99.0, 99.25, 99.4],
            "high": [100.5, 100.2, 100.0, 100.1, 99.6, 99.7],
            "low": [99.5, 99.2, 99.0, 98.5, 99.1, 99.2],
            "close": [100.0, 99.8, 99.5, 99.2, 99.4, 99.5],
            "volume": [1000] * len(timestamps),
            "signed_volume": [0, 0, 0, -400, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_rolling_range_orderflow_sweep_reversal",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "rolling_range_orderflow_sweep_reversal",
                "params": {
                    "start_time": "09:30:00",
                    "end_time": "10:00:00",
                    "lookback_bars": 3,
                    "min_sweep_ticks": 1,
                    "reclaim_buffer_ticks": 0,
                    "flow_mode": "signed",
                    "min_absorption_imbalance": 0.20,
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:36:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:36:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["breakout_timestamp"]) == "2024-01-03 09:33:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:34:00-05:00"


def _prior_bars():
    return [
        _bar("2024-01-03 09:30:00", high=100.5, low=99.5, close=100.0),
        _bar("2024-01-03 09:31:00", high=100.2, low=99.2, close=99.8),
        _bar("2024-01-03 09:32:00", high=100.0, low=99.0, close=99.5),
    ]


def _bar(
    timestamp: str,
    *,
    high: float,
    low: float,
    close: float,
    signed_volume: float = 0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": 0,
            "large20_volume": 0,
        }
    )
