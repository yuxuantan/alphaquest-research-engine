import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.opening_range_nq_orderflow_breakout import (
    OpeningRangeNqOrderflowBreakoutEntry,
)


def test_opening_range_nq_orderflow_breakout_accepts_long_when_nq_leads():
    entry = OpeningRangeNqOrderflowBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "breakout_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "nq_lookback_minutes": 15,
            "min_nq_return_bps": 4,
            "min_nq_lead_gap_bps": 1,
            "tick_size": 0.25,
        }
    )
    for bar in _bars("2024-01-03", closes=[100.0, 100.1, 100.2, 100.1, 100.0]):
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35:00",
            close=101.0,
            high=101.0,
            signed_volume=400,
            volume=1000,
            nq_return_bps_15=8.0,
            es_return_bps_15=3.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type.endswith("_nq_lead_confirmed")
    assert signal.report_fields["nq_directional_lead_gap_bps"] == 5.0


def test_opening_range_nq_orderflow_breakout_accepts_short_when_nq_leads_lower():
    entry = OpeningRangeNqOrderflowBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "breakout_buffer_ticks": 0,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "nq_lookback_minutes": 30,
            "min_nq_return_bps": 4,
            "min_nq_lead_gap_bps": 1,
            "tick_size": 0.25,
        }
    )
    for bar in _bars("2024-01-03", closes=[100.0, 100.1, 100.2, 100.1, 100.0]):
        entry.on_bar_close(bar)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35:00",
            close=99.25,
            low=99.25,
            signed_volume=-400,
            volume=1000,
            nq_return_bps_30=-9.0,
            es_return_bps_30=-3.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["nq_return_bps"] == -9.0
    assert signal.report_fields["nq_directional_lead_gap_bps"] == 6.0


def test_opening_range_nq_orderflow_breakout_rejects_when_nq_does_not_lead():
    entry = OpeningRangeNqOrderflowBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "last_entry_time": "10:00:00",
            "breakout_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "flow_mode": "signed_volume",
            "nq_lookback_minutes": 15,
            "min_nq_return_bps": 4,
            "min_nq_lead_gap_bps": 2,
            "tick_size": 0.25,
        }
    )
    for bar in _bars("2024-01-03", closes=[100.0, 100.1, 100.2, 100.1, 100.0]):
        entry.on_bar_close(bar)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35:00",
            close=101.0,
            high=101.0,
            signed_volume=400,
            volume=1000,
            nq_return_bps_15=5.0,
            es_return_bps_15=4.0,
        )
    )

    assert signal is None


def test_engine_enters_opening_range_nq_orderflow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=8, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100, 100, 100, 100, 100, 100.9, 101.1, 101.0],
            "high": [100.2, 100.1, 100.2, 100.1, 100.0, 101.1, 101.3, 101.2],
            "low": [99.8, 99.9, 99.9, 99.9, 99.9, 100.8, 99.0, 100.9],
            "close": [100.0, 100.1, 100.2, 100.1, 100.0, 101.0, 99.2, 101.0],
            "volume": [1000] * len(timestamps),
            "signed_volume": [0, 0, 0, 0, 0, 500, 0, 0],
            "large10_signed_volume": [0] * len(timestamps),
            "large10_volume": [0] * len(timestamps),
            "large20_signed_volume": [0] * len(timestamps),
            "large20_volume": [0] * len(timestamps),
            "es_return_bps_5": [0, 0, 0, 0, 0, 3.0, 0, 0],
            "nq_return_bps_5": [0, 0, 0, 0, 0, 8.0, 0, 0],
            "es_return_bps_15": [0, 0, 0, 0, 0, 3.0, 0, 0],
            "nq_return_bps_15": [0, 0, 0, 0, 0, 8.0, 0, 0],
            "es_return_bps_30": [0, 0, 0, 0, 0, 3.0, 0, 0],
            "nq_return_bps_30": [0, 0, 0, 0, 0, 8.0, 0, 0],
            "es_return_bps_60": [0, 0, 0, 0, 0, 3.0, 0, 0],
            "nq_return_bps_60": [0, 0, 0, 0, 0, 8.0, 0, 0],
        }
    )
    cfg = {
        "strategy_name": "test_or_nq_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "opening_range_nq_orderflow_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 1,
                    "bar_interval_minutes": 1,
                    "last_entry_time": "10:00:00",
                    "breakout_buffer_ticks": 1,
                    "min_orderflow_imbalance": 0.20,
                    "flow_mode": "signed_volume",
                    "nq_lookback_minutes": 15,
                    "min_nq_return_bps": 4,
                    "min_nq_lead_gap_bps": 1,
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:38:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:38:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["breakout_timestamp"]) == "2024-01-03 09:36:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:36:00-05:00"


def _bars(session_date: str, closes: list[float]):
    out = []
    timestamps = pd.date_range(f"{session_date} 09:30:00", periods=len(closes), freq="1min")
    for ts, close in zip(timestamps, closes):
        out.append(_bar(str(ts), close=close, high=max(close, 100.2), low=min(close, 99.8)))
    return out


def _bar(timestamp: str, *, close: float, high: float | None = None, low: float | None = None, **overrides):
    ts = pd.Timestamp(timestamp)
    row = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "open": close,
        "high": close if high is None else high,
        "low": close if low is None else low,
        "close": close,
        "volume": 1000,
        "signed_volume": 0,
        "large10_signed_volume": 0,
        "large10_volume": 0,
        "large20_signed_volume": 0,
        "large20_volume": 0,
        "es_return_bps_5": 0.0,
        "nq_return_bps_5": 0.0,
        "es_return_bps_15": 0.0,
        "nq_return_bps_15": 0.0,
        "es_return_bps_30": 0.0,
        "nq_return_bps_30": 0.0,
        "es_return_bps_60": 0.0,
        "nq_return_bps_60": 0.0,
    }
    row.update(overrides)
    return pd.Series(row)
