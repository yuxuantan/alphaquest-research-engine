import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.impulse_pause_orderflow_continuation import (
    ImpulsePauseOrderflowContinuationEntry,
)


def test_impulse_pause_orderflow_continuation_emits_long_after_completed_pause_breakout():
    entry = ImpulsePauseOrderflowContinuationEntry(
        {
            "start_time": "09:35:00",
            "end_time": "10:00:00",
            "bar_interval_minutes": 1,
            "impulse_bars": 2,
            "pause_bars": 2,
            "max_pullback_fraction": 0.5,
            "min_impulse_ticks": 4,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", open=100.0, high=100.6, low=99.9, close=100.5),
        _bar("2024-01-03 09:31:00", open=100.5, high=101.1, low=100.4, close=101.0),
        _bar("2024-01-03 09:32:00", open=101.0, high=101.05, low=100.8, close=100.85),
        _bar("2024-01-03 09:33:00", open=100.85, high=101.05, low=100.75, close=100.95),
    ]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:34:00",
            open=100.95,
            high=101.4,
            low=100.9,
            close=101.25,
            signed_volume=300,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["impulse_move_ticks"] == 4
    assert signal.report_fields["pause_retrace_fraction"] == 0.25
    assert signal.report_fields["signal_orderflow_imbalance"] == 0.3
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 09:35:00")


def test_impulse_pause_orderflow_continuation_rejects_deep_pause_or_misaligned_flow():
    deep_pause = ImpulsePauseOrderflowContinuationEntry(
        {
            "start_time": "09:35:00",
            "bar_interval_minutes": 1,
            "impulse_bars": 2,
            "pause_bars": 2,
            "max_pullback_fraction": 0.5,
            "min_impulse_ticks": 4,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )
    for bar in [
        _bar("2024-01-03 09:30:00", open=100.0, high=100.6, low=99.9, close=100.5),
        _bar("2024-01-03 09:31:00", open=100.5, high=101.1, low=100.4, close=101.0),
        _bar("2024-01-03 09:32:00", open=101.0, high=101.05, low=100.3, close=100.55),
        _bar("2024-01-03 09:33:00", open=100.55, high=101.05, low=100.5, close=100.95),
        _bar(
            "2024-01-03 09:34:00",
            open=100.95,
            high=101.4,
            low=100.9,
            close=101.25,
            signed_volume=300,
            volume=1000,
        ),
    ]:
        assert deep_pause.on_bar_close(bar) is None

    misaligned_flow = ImpulsePauseOrderflowContinuationEntry(
        {
            "start_time": "09:35:00",
            "bar_interval_minutes": 1,
            "impulse_bars": 2,
            "pause_bars": 2,
            "max_pullback_fraction": 0.5,
            "min_impulse_ticks": 4,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "tick_size": 0.25,
        }
    )
    for bar in [
        _bar("2024-01-03 09:30:00", open=100.0, high=100.6, low=99.9, close=100.5),
        _bar("2024-01-03 09:31:00", open=100.5, high=101.1, low=100.4, close=101.0),
        _bar("2024-01-03 09:32:00", open=101.0, high=101.05, low=100.8, close=100.85),
        _bar("2024-01-03 09:33:00", open=100.85, high=101.05, low=100.75, close=100.95),
        _bar(
            "2024-01-03 09:34:00",
            open=100.95,
            high=101.4,
            low=100.9,
            close=101.25,
            signed_volume=-300,
            volume=1000,
        ),
    ]:
        assert misaligned_flow.on_bar_close(bar) is None


def test_engine_enters_impulse_pause_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=8, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 100.5, 101.0, 100.85, 100.95, 101.3, 101.35, 101.2],
            "high": [100.6, 101.1, 101.05, 101.05, 101.4, 101.5, 101.45, 101.35],
            "low": [99.9, 100.4, 100.8, 100.75, 100.9, 101.1, 101.05, 101.0],
            "close": [100.5, 101.0, 100.85, 100.95, 101.25, 101.35, 101.2, 101.1],
            "volume": [1000] * len(timestamps),
            "signed_volume": [0, 0, 0, 0, 300, 0, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_impulse_pause_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "impulse_pause_orderflow_continuation",
                "params": {
                    "start_time": "09:35:00",
                    "end_time": "10:00:00",
                    "bar_interval_minutes": 1,
                    "impulse_bars": 2,
                    "pause_bars": 2,
                    "max_pullback_fraction": 0.5,
                    "min_impulse_ticks": 4,
                    "min_orderflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:37:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:37:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["signal_close_timestamp"]) == "2024-01-03 09:35:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:35:00-05:00"


def _bar(
    timestamp: str,
    *,
    open: float,
    high: float,
    low: float,
    close: float,
    signed_volume: float = 0,
    volume: float = 1000,
    large10_signed_volume: float = 0,
    large10_volume: float = 0,
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
            "open": open,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": large10_signed_volume,
            "large10_volume": large10_volume,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
        }
    )
