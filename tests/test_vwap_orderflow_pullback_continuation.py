import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.vwap_orderflow_pullback_continuation import (
    VwapOrderflowPullbackContinuationEntry,
)


def test_vwap_orderflow_pullback_requires_aligned_confirmation_flow():
    entry = VwapOrderflowPullbackContinuationEntry(
        {
            "setup_mode": "trend_reclaim",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "required_trend_closes": 2,
            "min_drive_points": 0.0,
            "pullback_tolerance_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 2,
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.20,
            "tick_size": 0.25,
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=100.6, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", close=100.7, vwap=100.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:32:00",
            close=100.7,
            low=99.9,
            vwap=100.0,
            signed_volume=300,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "vwap_orderflow_trend_reclaim"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.3


def test_vwap_orderflow_pullback_rejects_misaligned_large_flow():
    entry = VwapOrderflowPullbackContinuationEntry(
        {
            "setup_mode": "trend_reclaim",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "required_trend_closes": 2,
            "min_drive_points": 0.0,
            "pullback_tolerance_ticks": 0,
            "reclaim_buffer_ticks": 0,
            "flow_mode": "large20",
            "min_orderflow_imbalance": 0.30,
            "tick_size": 0.25,
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=100.6, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", close=100.7, vwap=100.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:32:00",
            close=100.7,
            low=99.9,
            vwap=100.0,
            large20_signed_volume=-80,
            large20_volume=200,
        )
    )

    assert signal is None


def test_vwap_orderflow_opening_drive_mode_uses_completed_drive_before_pullback():
    entry = VwapOrderflowPullbackContinuationEntry(
        {
            "setup_mode": "opening_drive_pullback",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "opening_drive_minutes": 15,
            "min_drive_points": 1.0,
            "min_drive_close_location": 0.55,
            "pullback_tolerance_ticks": 4,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 2,
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.20,
            "tick_size": 0.25,
            "bar_interval_minutes": 5,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", close=100.0, vwap=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:35:00", close=101.0, vwap=100.4)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:40:00", close=102.0, vwap=100.8)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:45:00",
            close=101.4,
            low=100.8,
            high=101.8,
            vwap=101.0,
            signed_volume=300,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "vwap_orderflow_opening_drive_pullback"
    assert signal.report_fields["opening_drive_end_timestamp"] == pd.Timestamp("2024-01-03 09:45:00")
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.3


def test_engine_enters_vwap_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=5, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.5, 100.6, 100.4, 100.8, 100.9],
            "high": [100.7, 100.8, 100.7, 101.2, 101.3],
            "low": [100.3, 100.5, 99.9, 100.6, 100.7],
            "close": [100.6, 100.7, 100.7, 101.0, 101.1],
            "volume": [1000, 1000, 1000, 1000, 1000],
            "signed_volume": [0, 0, 300, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
            "vwap": [100.0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_vwap_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "vwap_orderflow_pullback_continuation",
                "params": {
                    "setup_mode": "trend_reclaim",
                    "start_time": "09:30:00",
                    "end_time": "10:00:00",
                    "required_trend_closes": 2,
                    "min_drive_points": 0.0,
                    "pullback_tolerance_ticks": 0,
                    "reclaim_buffer_ticks": 0,
                    "reclaim_window_bars": 2,
                    "flow_mode": "signed_volume",
                    "min_orderflow_imbalance": 0.20,
                    "tick_size": 0.25,
                    "bar_interval_minutes": 1,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:34:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:34:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["vwap_reclaim_timestamp"]) == "2024-01-03 09:32:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:33:00-05:00"


def _bar(
    timestamp: str,
    *,
    close: float,
    vwap: float,
    low: float | None = None,
    high: float | None = None,
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
            "high": close if high is None else high,
            "low": close if low is None else low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": large20_signed_volume,
            "large20_volume": large20_volume,
            "vwap": vwap,
        }
    )
