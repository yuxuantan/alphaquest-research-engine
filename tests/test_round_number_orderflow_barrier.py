from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.round_number_orderflow_barrier import RoundNumberOrderflowBarrierEntry


def test_support_reclaim_long_requires_absorbed_selling_flow():
    entry = RoundNumberOrderflowBarrierEntry(
        {
            "setup_mode": "support_reclaim_long",
            "barrier_interval_points": 25,
            "buffer_ticks": 1,
            "flow_confirmation": "absorbed",
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.05,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:35", low=4999.75, close=5000.5, signed_volume=100)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-04 09:35", low=4999.75, close=5000.5, signed_volume=-100, volume=1000)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "round_number_orderflow_round_number_support_reclaim"
    assert signal.report_fields["flow_confirmation"] == "absorbed"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.1


def test_upside_breakout_long_requires_aligned_buying_flow():
    entry = RoundNumberOrderflowBarrierEntry(
        {
            "setup_mode": "upside_breakout_long",
            "barrier_interval_points": 25,
            "buffer_ticks": 1,
            "flow_confirmation": "aligned",
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.05,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:35", close=4999.5, signed_volume=0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:40", high=5001, low=4999.25, close=5000.5, signed_volume=-80)) is None

    entry = RoundNumberOrderflowBarrierEntry(
        {
            "setup_mode": "upside_breakout_long",
            "barrier_interval_points": 25,
            "buffer_ticks": 1,
            "flow_confirmation": "aligned",
            "flow_mode": "signed_volume",
            "min_orderflow_imbalance": 0.05,
        }
    )
    entry.on_bar_close(_bar("2024-01-03 09:35", close=4999.5, signed_volume=0))
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:40", high=5001, low=4999.25, close=5000.5, signed_volume=80)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["flow_confirmation"] == "aligned"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == 0.08


def test_large_orderflow_mode_is_used_for_reclaim_filter():
    entry = RoundNumberOrderflowBarrierEntry(
        {
            "setup_mode": "support_reclaim_long",
            "barrier_interval_points": 25,
            "buffer_ticks": 0,
            "flow_confirmation": "absorbed",
            "flow_mode": "large10",
            "min_orderflow_imbalance": 0.20,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:35",
            low=4999.75,
            close=5000.25,
            large10_signed_volume=-80,
            large10_volume=200,
        )
    )

    assert signal is not None
    assert signal.report_fields["flow_mode"] == "large10"
    assert signal.report_fields["confirmation_orderflow_imbalance"] == -0.4


def test_engine_enters_round_number_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:35:00", periods=3, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [4999.5, 5000.75, 5001.0],
            "high": [5000.75, 5001.25, 5001.5],
            "low": [4999.5, 5000.25, 5000.75],
            "close": [5000.5, 5001.0, 5001.25],
            "volume": [1000, 1000, 1000],
            "signed_volume": [-100, 0, 0],
            "large10_signed_volume": [0, 0, 0],
            "large10_volume": [0, 0, 0],
            "large20_signed_volume": [0, 0, 0],
            "large20_volume": [0, 0, 0],
        }
    )
    cfg = {
        "strategy_name": "test_round_number_orderflow",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "round_number_orderflow_barrier",
                "params": {
                    "setup_mode": "support_reclaim_long",
                    "start_time": "09:35:00",
                    "end_time": "10:00:00",
                    "bar_interval_minutes": 5,
                    "barrier_interval_points": 25,
                    "buffer_ticks": 1,
                    "max_close_distance_ticks": 12,
                    "flow_confirmation": "absorbed",
                    "flow_mode": "signed_volume",
                    "min_orderflow_imbalance": 0.05,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:50:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:50:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["signal_timestamp"]) == "2024-01-03 09:40:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:40:00-05:00"


def _bar(
    timestamp: str,
    *,
    close: float,
    low: float | None = None,
    high: float | None = None,
    signed_volume: float = 0,
    volume: float = 1000,
    large10_signed_volume: float = 0,
    large10_volume: float = 0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close - 0.25,
            "high": high if high is not None else close + 0.25,
            "low": low if low is not None else close - 0.25,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": large10_signed_volume,
            "large10_volume": large10_volume,
            "large20_signed_volume": 0,
            "large20_volume": 0,
        }
    )
