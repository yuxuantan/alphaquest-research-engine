import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.vwap_deviation_orderflow_reversion import (
    VwapDeviationOrderflowReversionEntry,
)


def test_vwap_deviation_counterflow_long_signal():
    entry = VwapDeviationOrderflowReversionEntry(
        {
            "start_time": "09:35:00",
            "end_time": "15:00:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "min_vwap_deviation_ticks": 12,
            "min_counterflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:30:00",
            close=100.0,
            high=101.0,
            low=99.0,
            vwap=103.0,
            signed_volume=300,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["vwap_deviation_ticks"] == -12.0
    assert signal.report_fields["counterflow_imbalance"] == 0.3


def test_vwap_deviation_rejects_same_direction_flow():
    entry = VwapDeviationOrderflowReversionEntry(
        {
            "start_time": "09:35:00",
            "end_time": "15:00:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "min_vwap_deviation_ticks": 12,
            "min_counterflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:30:00",
            close=100.0,
            high=101.0,
            low=99.0,
            vwap=103.0,
            signed_volume=-300,
            volume=1000,
        )
    )

    assert signal is None


def test_engine_enters_vwap_deviation_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=4, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.2, 100.4, 100.6, 100.8],
            "high": [101.0, 101.0, 101.2, 101.3],
            "low": [99.0, 100.2, 100.4, 100.6],
            "close": [100.0, 100.7, 100.9, 101.1],
            "volume": [1000, 1000, 1000, 1000],
            "signed_volume": [300, 0, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
            "vwap": [103.0] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_vwap_deviation_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "vwap_deviation_orderflow_reversion",
                "params": {
                    "start_time": "09:31:00",
                    "end_time": "09:34:00",
                    "bar_interval_minutes": 1,
                    "tick_size": 0.25,
                    "min_vwap_deviation_ticks": 12,
                    "min_counterflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:33:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:33:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["vwap_deviation_signal_timestamp"]) == "2024-01-03 09:31:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:31:00-05:00"


def _bar(
    timestamp: str,
    *,
    close: float,
    high: float,
    low: float,
    vwap: float,
    signed_volume: float,
    volume: float,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
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
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": 0,
            "large20_volume": 0,
            "vwap": vwap,
        }
    )
