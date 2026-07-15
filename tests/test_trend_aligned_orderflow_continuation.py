import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.trend_aligned_orderflow_continuation import (
    TrendAlignedOrderflowContinuationEntry,
)


def test_trend_aligned_orderflow_continuation_requires_completed_time_and_aligned_flow():
    entry = TrendAlignedOrderflowContinuationEntry(
        {
            "signal_time": "09:36:00",
            "bar_interval_minutes": 1,
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )

    bars = [
        _bar("2024-01-03 09:30:00", high=100.0, low=99.5, close=99.8),
        _bar("2024-01-03 09:31:00", high=100.2, low=99.6, close=99.9),
        _bar("2024-01-03 09:32:00", high=100.1, low=99.7, close=100.0),
        _bar("2024-01-03 09:33:00", high=100.5, low=99.8, close=100.2),
        _bar("2024-01-03 09:34:00", high=100.6, low=100.0, close=100.4),
    ]
    for bar in bars:
        assert entry.on_bar_close(bar) is None

    signal_bar = _bar(
        "2024-01-03 09:35:00",
        high=101.0,
        low=100.2,
        close=100.8,
        signed_volume=300,
        volume=1000,
    )
    signal = entry.on_bar_close(signal_bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["signal_orderflow_imbalance"] == 0.3
    assert str(signal.report_fields["signal_close_timestamp"]) == "2024-01-03 09:36:00"


def test_trend_aligned_orderflow_continuation_rejects_misaligned_large_flow():
    entry = TrendAlignedOrderflowContinuationEntry(
        {
            "signal_time": "09:36:00",
            "bar_interval_minutes": 1,
            "short_trend_bars": 2,
            "long_trend_bars": 3,
            "min_trend_move_ticks": 0,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "large20",
            "tick_size": 0.25,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", high=100.0, low=99.5, close=99.8),
        _bar("2024-01-03 09:31:00", high=100.2, low=99.6, close=99.9),
        _bar("2024-01-03 09:32:00", high=100.1, low=99.7, close=100.0),
        _bar("2024-01-03 09:33:00", high=100.5, low=99.8, close=100.2),
        _bar("2024-01-03 09:34:00", high=100.6, low=100.0, close=100.4),
        _bar(
            "2024-01-03 09:35:00",
            high=101.0,
            low=100.2,
            close=100.8,
            large20_signed_volume=-60,
            large20_volume=100,
        ),
    ]:
        assert entry.on_bar_close(bar) is None


def test_engine_enters_trend_aligned_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=8, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [99.8, 99.9, 100.0, 100.2, 100.4, 100.8, 100.9, 100.7],
            "high": [100.0, 100.2, 100.1, 100.5, 100.6, 101.0, 101.2, 101.0],
            "low": [99.5, 99.6, 99.7, 99.8, 100.0, 100.2, 100.6, 100.5],
            "close": [99.8, 99.9, 100.0, 100.2, 100.4, 100.8, 100.9, 100.7],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
            "signed_volume": [0, 0, 0, 0, 0, 300, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_trend_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "trend_aligned_orderflow_continuation",
                "params": {
                    "signal_time": "09:36:00",
                    "bar_interval_minutes": 1,
                    "short_trend_bars": 2,
                    "long_trend_bars": 3,
                    "min_trend_move_ticks": 1,
                    "min_orderflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:38:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:38:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["signal_close_timestamp"]) == "2024-01-03 09:36:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:36:00-05:00"


def _bar(
    timestamp: str,
    *,
    high: float,
    low: float,
    close: float,
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
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
        }
    )
