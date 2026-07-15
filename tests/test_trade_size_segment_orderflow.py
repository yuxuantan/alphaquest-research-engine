import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.trade_size_segment_orderflow import TradeSizeSegmentOrderflowEntry


def _bar(
    timestamp: str,
    *,
    signed_volume: float = 40.0,
    volume: float = 1000.0,
    large_signed_volume: float = 80.0,
    large_volume: float = 400.0,
    is_rth: bool = True,
):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "trade_orderflow_signed_volume_15": signed_volume,
            "trade_orderflow_volume_15": volume,
            "trade_orderflow_large20_signed_volume_15": large_signed_volume,
            "trade_orderflow_large20_volume_15": large_volume,
        }
    )


def test_trade_size_segment_orderflow_follows_large_buy_against_residual_sell():
    entry = TradeSizeSegmentOrderflowEntry(
        {
            "entry_time": "10:00:00",
            "flatten_time": "10:45:00",
            "window_minutes": 15,
            "large_trade_size": 20,
            "direction": "long",
            "residual_mode": "opposite",
            "min_large_imbalance": 0.10,
            "min_disagreement": 0.20,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-04 09:58")) is None
    signal = entry.on_bar_close(_bar("2024-01-04 09:59"))

    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-04 10:00", tz="America/New_York")
    assert signal.report_fields["feature_method"] == "completed_bar_trade_size_segment_orderflow"
    assert signal.report_fields["large_imbalance"] == pytest.approx(0.20)
    assert signal.report_fields["residual_imbalance"] == pytest.approx(-40.0 / 600.0)
    assert signal.report_fields["long_disagreement"] == pytest.approx(0.20 + 40.0 / 600.0)


def test_trade_size_segment_orderflow_short_side_and_trade_limit():
    entry = TradeSizeSegmentOrderflowEntry(
        {
            "entry_time": "10:30:00",
            "window_minutes": 15,
            "large_trade_size": 20,
            "direction": "short",
            "residual_mode": "loose",
            "min_large_imbalance": 0.10,
            "min_disagreement": 0.20,
        }
    )

    bar = _bar(
        "2024-01-04 10:29",
        signed_volume=-20.0,
        large_signed_volume=-80.0,
        large_volume=400.0,
    )
    assert entry.on_bar_close(bar, trades_today=1) is None
    signal = entry.on_bar_close(bar, trades_today=0)

    assert signal.direction == "short"
    assert signal.report_fields["short_disagreement"] == pytest.approx(0.30)


def test_trade_size_segment_orderflow_residual_mode_filters_alignment():
    entry = TradeSizeSegmentOrderflowEntry(
        {
            "entry_time": "10:00:00",
            "window_minutes": 15,
            "large_trade_size": 20,
            "direction": "long",
            "residual_mode": "opposite",
            "min_large_imbalance": 0.10,
            "min_disagreement": 0.20,
        }
    )

    aligned_residual = _bar(
        "2024-01-04 09:59",
        signed_volume=180.0,
        large_signed_volume=80.0,
        large_volume=400.0,
    )

    assert entry.on_bar_close(aligned_residual) is None
