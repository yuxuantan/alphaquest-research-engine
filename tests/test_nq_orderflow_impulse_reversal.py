from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.orderflow_regime import OrderflowRegimeEntry


def _bar(
    timestamp: str,
    *,
    pressure_rank: float = 0.9,
    return_ticks: float = 3.0,
    is_rth: bool = True,
) -> pd.Series:
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 18000.0,
            "high": 18012.0,
            "low": 17996.0,
            "close": 18008.0,
            "trade_orderflow_imbalance_5_rank42": pressure_rank,
            "trade_orderflow_imbalance_5": 0.2 if pressure_rank >= 0.5 else -0.2,
            "trade_orderflow_return_ticks_5": return_ticks,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _entry() -> OrderflowRegimeEntry:
    return OrderflowRegimeEntry(
        {
            "mode": "flow_impulse_reversal",
            "setup_mode": "early_5m_impulse_reversal_1000",
            "bar_interval_minutes": 1,
            "max_trades_per_day": 1,
            "pressure_rank_threshold": 0.8,
            "min_return_ticks": 2,
            "slots": [
                {
                    "slot_id": "early_5m_impulse_reversal_1000",
                    "setup_mode": "early_5m_impulse_reversal_1000",
                    "entry_time": "10:00:00",
                    "flatten_time": "10:45:00",
                    "pressure_rank_column": "trade_orderflow_imbalance_5_rank42",
                    "pressure_value_column": "trade_orderflow_imbalance_5",
                    "return_column": "trade_orderflow_return_ticks_5",
                }
            ],
        }
    )


def test_nq_orderflow_impulse_reversal_uses_completed_signal_bar_time():
    entry = _entry()

    assert entry.on_bar_close(_bar("2024-01-04 09:58:00")) is None

    signal = entry.on_bar_close(_bar("2024-01-04 09:59:00"))

    assert signal is not None
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-04 10:00:00", tz="America/New_York")
    assert signal.report_fields["orderflow_signal_timestamp"] == pd.Timestamp(
        "2024-01-04 10:00:00",
        tz="America/New_York",
    )
    assert signal.metadata["flatten_time"] == "10:45:00"


def test_nq_orderflow_impulse_reversal_fades_confirmed_flow_plus_return():
    entry = _entry()

    assert entry.on_bar_close(_bar("2024-01-04 09:59:00", pressure_rank=0.9, return_ticks=3)).direction == "short"
    assert entry.on_bar_close(_bar("2024-01-05 09:59:00", pressure_rank=0.1, return_ticks=-3)).direction == "long"
    assert entry.on_bar_close(_bar("2024-01-08 09:59:00", pressure_rank=0.9, return_ticks=-3)) is None
    assert entry.on_bar_close(_bar("2024-01-09 09:59:00", pressure_rank=0.9, return_ticks=1)) is None
