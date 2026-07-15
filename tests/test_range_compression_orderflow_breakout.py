import pandas as pd

from alphaquest.strategy_modules.entry.range_compression_orderflow_breakout import (
    RangeCompressionOrderflowBreakoutEntry,
)


def test_range_compression_orderflow_breakout_requires_aligned_flow_after_compression():
    entry = RangeCompressionOrderflowBreakoutEntry(
        {
            "setup_mode": "nr2_prior_session_flow_breakout",
            "rth_start": "09:30:00",
            "start_time": "09:31:00",
            "end_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_days": 2,
            "max_range_rank_pct": 0.50,
            "require_inside_day": False,
            "breakout_level_source": "prior_session",
            "min_breakout_ticks": 1,
            "tick_size": 0.25,
            "flow_mode": "signed",
            "min_orderflow_imbalance": 0.20,
        }
    )
    _seed_prior_sessions(entry)

    weak_flow = _bar("2024-01-04 09:35:00", high=101.5, low=100.5, close=101.5, signed_volume=100)
    assert entry.on_bar_close(weak_flow) is None

    strong_flow = _bar("2024-01-04 09:36:00", high=101.75, low=101.0, close=101.75, signed_volume=300)
    signal = entry.on_bar_close(strong_flow)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 101.0
    assert signal.report_fields["flow_mode"] == "signed"
    assert signal.report_fields["orderflow_imbalance"] == 0.3
    assert signal.report_fields["feature_method"] == "range_compression_breakout_with_completed_bar_orderflow"


def test_range_compression_orderflow_breakout_uses_large_flow_for_shorts():
    entry = RangeCompressionOrderflowBreakoutEntry(
        {
            "setup_mode": "nr2_prior_session_large20_flow_breakout",
            "rth_start": "09:30:00",
            "start_time": "09:31:00",
            "end_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_days": 2,
            "max_range_rank_pct": 0.50,
            "require_inside_day": False,
            "breakout_level_source": "prior_session",
            "min_breakout_ticks": 1,
            "tick_size": 0.25,
            "flow_mode": "large20",
            "min_orderflow_imbalance": 0.50,
            "allow_long": False,
            "allow_short": True,
        }
    )
    _seed_prior_sessions(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-04 09:35:00",
            high=100.5,
            low=99.5,
            close=99.5,
            large20_signed_volume=-120,
            large20_volume=200,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 100.0
    assert signal.report_fields["flow_mode"] == "large20"
    assert signal.report_fields["orderflow_imbalance"] == -0.6


def _seed_prior_sessions(entry):
    assert entry.on_bar_close(_bar("2024-01-02 09:35:00", high=104.0, low=100.0, close=102.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35:00", high=101.0, low=100.0, close=100.5)) is None


def _bar(
    timestamp: str,
    *,
    high: float,
    low: float,
    close: float,
    signed_volume: float = 0,
    volume: float = 1000,
    large10_signed_volume: float = 0,
    large10_volume: float = 200,
    large20_signed_volume: float = 0,
    large20_volume: float = 200,
) -> pd.Series:
    ts = pd.Timestamp(timestamp, tz="America/New_York")
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
            "large10_signed_volume": large10_signed_volume,
            "large10_volume": large10_volume,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
        }
    )
