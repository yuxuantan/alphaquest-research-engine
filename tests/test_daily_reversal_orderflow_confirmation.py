import pandas as pd

from alphaquest.strategy_modules.entry.daily_reversal_orderflow_confirmation import (
    DailyReversalOrderflowConfirmationEntry,
)


def _bar(ts, close, session_date=None, **extra):
    timestamp = pd.Timestamp(ts, tz="America/New_York")
    row = {
        "timestamp": timestamp,
        "session_date": session_date or timestamp.date().isoformat(),
        "is_rth": True,
        "open": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "trade_orderflow_imbalance_12": 0.0,
        "trade_orderflow_volume_12": 1000.0,
        "trade_orderflow_signed_volume_12": 0.0,
        "trade_orderflow_return_ticks_12": 0.0,
    }
    row.update(extra)
    return pd.Series(row)


def test_daily_reversal_orderflow_confirmation_signals_long_after_loss_with_buy_flow():
    entry = DailyReversalOrderflowConfirmationEntry(
        {
            "signal_time": "10:30:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.001,
            "flow_window_bars": 12,
            "min_reversal_flow_imbalance": 0.01,
        }
    )
    entry.on_bar_close(_bar("2024-01-02 15:55", 5000.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", 4970.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 10:25",
            4974.0,
            trade_orderflow_imbalance_12=0.025,
            trade_orderflow_signed_volume_12=250.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["reversal_return_pct"] < 0
    assert signal.report_fields["flow_imbalance"] == 0.025


def test_daily_reversal_orderflow_confirmation_signals_short_after_gain_with_sell_flow():
    entry = DailyReversalOrderflowConfirmationEntry(
        {
            "signal_time": "10:30:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.001,
            "flow_window_bars": 12,
            "min_reversal_flow_imbalance": 0.01,
        }
    )
    entry.on_bar_close(_bar("2024-01-02 15:55", 5000.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", 5030.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 10:25",
            5028.0,
            trade_orderflow_imbalance_12=-0.02,
            trade_orderflow_signed_volume_12=-200.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["reversal_return_pct"] > 0
    assert signal.report_fields["flow_imbalance"] == -0.02


def test_daily_reversal_orderflow_confirmation_rejects_wrong_flow_direction():
    entry = DailyReversalOrderflowConfirmationEntry(
        {
            "signal_time": "10:30:00",
            "rth_end": "16:00:00",
            "bar_interval_minutes": 5,
            "lookback_sessions": 1,
            "min_abs_reversal_return_pct": 0.001,
            "flow_window_bars": 12,
            "min_reversal_flow_imbalance": 0.01,
        }
    )
    entry.on_bar_close(_bar("2024-01-02 15:55", 5000.0))
    entry.on_bar_close(_bar("2024-01-03 15:55", 4970.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 10:25",
            4974.0,
            trade_orderflow_imbalance_12=-0.025,
            trade_orderflow_signed_volume_12=-250.0,
        )
    )

    assert signal is None
