import pandas as pd

from alphaquest.strategy_modules.entry.ema_pullback_orderflow_continuation import (
    EmaPullbackOrderflowContinuationEntry,
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


def _entry(**overrides):
    params = {
        "setup_mode": "two_sided_pullback",
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "flatten_time": "15:00:00",
        "bar_interval_minutes": 5,
        "tick_size": 0.25,
        "fast_period": 3,
        "slow_period": 5,
        "min_trend_gap_ticks": 2,
        "pullback_tolerance_ticks": 1,
        "min_orderflow_imbalance": 0.1,
        "flow_mode": "signed_volume",
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return EmaPullbackOrderflowContinuationEntry(params)


def test_ema_pullback_orderflow_continuation_emits_long_from_prior_completed_ema_state():
    entry = _entry(setup_mode="long_pullback", allow_long=True, allow_short=False)
    for minute, close in enumerate([100.0, 101.0, 102.0, 103.0, 104.0]):
        assert entry.on_bar_close(_bar(f"2024-01-03 09:{30 + minute * 5:02d}", close, close, close, close)) is None

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:55", 103.0, 104.0, 103.0, 103.8, signed_volume=200.0)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == signal.report_fields["prior_fast_ema"]
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00", tz="America/New_York")
    assert signal.report_fields["trend_gap_ticks"] >= 2
    assert signal.report_fields["orderflow_imbalance"] == 0.2
    assert signal.report_fields["signal_flatten_time"] == "15:00:00"


def test_ema_pullback_orderflow_continuation_emits_short_from_prior_completed_ema_state():
    entry = _entry(
        setup_mode="short_pullback",
        flow_mode="large20",
        allow_long=False,
        allow_short=True,
    )
    for minute, close in enumerate([104.0, 103.0, 102.0, 101.0, 100.0]):
        assert entry.on_bar_close(_bar(f"2024-01-03 09:{30 + minute * 5:02d}", close, close, close, close)) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:55",
            101.0,
            101.25,
            99.5,
            100.25,
            large20_signed_volume=-80.0,
            large20_volume=250.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.sweep_high == 101.25
    assert signal.report_fields["trend_gap_ticks"] >= 2
    assert signal.report_fields["orderflow_imbalance"] == -0.32


def test_ema_pullback_orderflow_continuation_requires_confirming_flow_and_session_limit():
    entry = _entry()
    for minute, close in enumerate([100.0, 101.0, 102.0, 103.0, 104.0]):
        entry.on_bar_close(_bar(f"2024-01-03 09:{30 + minute * 5:02d}", close, close, close, close))

    assert entry.on_bar_close(
        _bar("2024-01-03 09:55", 103.0, 104.0, 103.0, 103.8, signed_volume=-200.0)
    ) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:00", 103.5, 104.25, 103.5, 104.0, signed_volume=200.0)
    )
    assert signal is not None
    assert entry.on_bar_close(
        _bar("2024-01-03 10:05", 103.75, 104.5, 103.75, 104.25, signed_volume=200.0)
    ) is None


def test_ema_pullback_orderflow_continuation_does_not_use_current_close_to_create_trend():
    entry = _entry(min_trend_gap_ticks=1)
    for minute in range(5):
        entry.on_bar_close(_bar(f"2024-01-03 09:{30 + minute * 5:02d}", 100.0, 100.0, 100.0, 100.0))

    assert entry.on_bar_close(
        _bar("2024-01-03 09:55", 100.0, 105.0, 100.0, 105.0, signed_volume=500.0)
    ) is None
