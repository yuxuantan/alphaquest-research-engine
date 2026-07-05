from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.trade_orderflow_pressure import TradeOrderflowPressureEntry


def _bar(
    timestamp: str,
    *,
    flow: float = 0.07,
    return_ticks: float = 5.0,
    is_rth: bool = True,
) -> pd.Series:
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 18000.0,
            "high": 18010.0,
            "low": 17992.0,
            "close": 18005.0,
            "trade_orderflow_imbalance_5": flow,
            "trade_orderflow_return_ticks_5": return_ticks,
        },
        name=ts.hour * 60 + ts.minute,
    )


def test_nq_signed_flow_signal_uses_completed_bar_closing_at_decision_time():
    entry = TradeOrderflowPressureEntry(
        {
            "setup_mode": "early_5m_signed_flow_continuation_1000",
            "entry_time": "10:00:00",
            "flatten_time": "10:45:00",
            "bar_interval_minutes": 1,
            "flow_column": "trade_orderflow_imbalance_5",
            "flow_threshold": 0.06,
            "return_column": "trade_orderflow_return_ticks_5",
            "return_confirmation": "same_sign",
            "min_return_ticks": 4,
            "positive_flow_direction": "long",
            "allow_long": True,
            "allow_short": True,
            "max_trades_per_day": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-04 09:58:00")) is None

    signal = entry.on_bar_close(_bar("2024-01-04 09:59:00"))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-04 10:00:00", tz="America/New_York")
    assert signal.report_fields["orderflow_signal_timestamp"] == pd.Timestamp(
        "2024-01-04 10:00:00",
        tz="America/New_York",
    )
    assert signal.metadata["flatten_time"] == "10:45:00"


def test_nq_signed_flow_return_confirmation_blocks_unconfirmed_flow():
    entry = TradeOrderflowPressureEntry(
        {
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "flow_column": "trade_orderflow_imbalance_5",
            "flow_threshold": 0.06,
            "return_column": "trade_orderflow_return_ticks_5",
            "return_confirmation": "same_sign",
            "min_return_ticks": 4,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-04 09:59:00", flow=0.07, return_ticks=2.0)) is None
    assert entry.on_bar_close(_bar("2024-01-04 09:59:00", flow=-0.07, return_ticks=5.0)) is None
    assert entry.on_bar_close(_bar("2024-01-04 09:59:00", flow=-0.07, return_ticks=-5.0)).direction == "short"
