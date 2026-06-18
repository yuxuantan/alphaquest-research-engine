import pandas as pd

from propstack.strategy_modules.entry.morning_trend_lunch_reversal_orderflow import (
    MorningTrendLunchReversalOrderflowEntry,
)


def _bar(
    timestamp,
    open_,
    high,
    low,
    close,
    *,
    signed_volume=0.0,
    volume=1000.0,
    large10_signed_volume=0.0,
    large10_volume=500.0,
    large20_signed_volume=0.0,
    large20_volume=250.0,
):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "signed_volume": signed_volume,
            "volume": volume,
            "large10_signed_volume": large10_signed_volume,
            "large10_volume": large10_volume,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
        }
    )


def test_morning_trend_lunch_reversal_emits_short_after_up_extension_and_sell_flow():
    entry = MorningTrendLunchReversalOrderflowEntry(
        {
            "setup_mode": "up_extension_short",
            "start_time": "10:30:00",
            "end_time": "12:00:00",
            "flatten_time": "13:00:00",
            "bar_interval_minutes": 5,
            "min_morning_return_ticks": 8,
            "min_counterflow_imbalance": 0.1,
            "flow_mode": "signed_volume",
            "allow_long": False,
            "allow_short": True,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30", 100.0, 100.5, 99.75, 100.25)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:25", 103.0, 103.5, 102.25, 102.5, signed_volume=-250.0)
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.sweep_high == 103.5
    assert signal.report_fields["morning_return_ticks"] == 10.0
    assert signal.report_fields["orderflow_imbalance"] == -0.25
    assert signal.report_fields["signal_flatten_time"] == "13:00:00"


def test_morning_trend_lunch_reversal_emits_long_after_down_extension_and_buy_flow():
    entry = MorningTrendLunchReversalOrderflowEntry(
        {
            "setup_mode": "down_extension_long",
            "start_time": "10:30:00",
            "end_time": "12:00:00",
            "bar_interval_minutes": 5,
            "min_morning_return_ticks": 8,
            "min_counterflow_imbalance": 0.2,
            "flow_mode": "large20",
            "allow_long": True,
            "allow_short": False,
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", 100.0, 100.25, 99.5, 99.75))
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:25",
            97.0,
            97.75,
            96.5,
            97.5,
            large20_signed_volume=80.0,
            large20_volume=250.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.sweep_low == 96.5
    assert signal.report_fields["orderflow_imbalance"] == 0.32


def test_morning_trend_lunch_reversal_requires_counterflow_and_session_limit():
    entry = MorningTrendLunchReversalOrderflowEntry(
        {
            "setup_mode": "two_sided_reversal",
            "start_time": "10:30:00",
            "end_time": "12:00:00",
            "bar_interval_minutes": 5,
            "min_morning_return_ticks": 8,
            "min_counterflow_imbalance": 0.1,
            "flow_mode": "signed_volume",
        }
    )

    entry.on_bar_close(_bar("2024-01-03 09:30", 100.0, 100.5, 99.75, 100.25))
    assert (
        entry.on_bar_close(_bar("2024-01-03 10:25", 103.0, 103.5, 102.25, 102.5, signed_volume=250.0))
        is None
    )
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:30", 102.5, 103.0, 101.75, 102.0, signed_volume=-250.0)
    )
    assert signal is not None
    assert entry.on_bar_close(
        _bar("2024-01-03 10:35", 102.0, 102.5, 101.25, 101.5, signed_volume=-250.0)
    ) is None
