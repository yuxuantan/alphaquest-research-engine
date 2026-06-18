import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.session_open_orderflow_reclaim import (
    SessionOpenOrderflowReclaimEntry,
)


def test_session_open_orderflow_reclaim_requires_prior_completed_extension():
    entry = SessionOpenOrderflowReclaimEntry(
        {
            "signal_start": "09:31:00",
            "signal_end": "10:00:00",
            "bar_interval_minutes": 1,
            "min_open_extension_ticks": 4,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "direction": "long",
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, low=99.75, close=99.75)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", open_=99.75, low=98.75, close=99.0)) is None

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:32:00", open_=99.0, high=100.5, low=99.0, close=100.25, signed_volume=300)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 100.0
    assert str(signal.report_fields["extension_timestamp"]) == "2024-01-03 09:31:00"
    assert str(signal.report_fields["session_open_reclaim_signal_timestamp"]) == "2024-01-03 09:33:00"
    assert signal.report_fields["signal_orderflow_imbalance"] == 0.3


def test_session_open_orderflow_reclaim_rejects_same_bar_extension_sequence():
    entry = SessionOpenOrderflowReclaimEntry(
        {
            "signal_start": "09:30:00",
            "signal_end": "10:00:00",
            "bar_interval_minutes": 1,
            "min_open_extension_ticks": 4,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "direction": "long",
            "tick_size": 0.25,
        }
    )

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:30:00", open_=100.0, high=100.5, low=98.75, close=100.25, signed_volume=300)
    )

    assert signal is None


def test_session_open_orderflow_reclaim_uses_large20_flow_for_short_rejection():
    entry = SessionOpenOrderflowReclaimEntry(
        {
            "signal_start": "09:31:00",
            "signal_end": "10:00:00",
            "bar_interval_minutes": 1,
            "min_open_extension_ticks": 4,
            "min_orderflow_imbalance": 0.50,
            "flow_mode": "large20",
            "direction": "short",
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, high=101.25, close=101.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:31:00",
            open_=101.0,
            high=101.0,
            low=99.5,
            close=99.75,
            large20_signed_volume=-140,
            large20_volume=200,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["flow_mode"] == "large20"
    assert signal.report_fields["signal_orderflow_imbalance"] == -0.7


def test_engine_enters_session_open_reclaim_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=7, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 99.75, 99.0, 100.5, 100.25, 100.0, 100.0],
            "high": [100.25, 99.75, 100.5, 100.5, 100.25, 100.0, 100.0],
            "low": [99.75, 98.75, 99.0, 100.0, 99.75, 99.75, 99.75],
            "close": [99.75, 99.0, 100.25, 100.25, 100.0, 100.0, 100.0],
            "volume": [1000] * len(timestamps),
            "signed_volume": [0, 0, 300, 0, 0, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_session_open_reclaim",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "session_open_orderflow_reclaim",
                "params": {
                    "signal_start": "09:31:00",
                    "signal_end": "10:00:00",
                    "bar_interval_minutes": 1,
                    "min_open_extension_ticks": 4,
                    "min_orderflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "direction": "long",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                    "flatten_time": "09:35:00",
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:35:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:35:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["session_open_reclaim_signal_timestamp"]) == "2024-01-03 09:33:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:33:00-05:00"


def _bar(
    timestamp: str,
    *,
    open_: float = 100.0,
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
            "open": open_,
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
