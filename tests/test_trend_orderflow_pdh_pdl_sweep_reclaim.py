import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.trend_orderflow_pdh_pdl_sweep_reclaim import (
    TrendOrderflowPdhPdlSweepReclaimEntry,
)


def test_trend_orderflow_pdl_sweep_reclaim_emits_long_with_absorbed_selling():
    entry = TrendOrderflowPdhPdlSweepReclaimEntry(
        {
            "start_time": "09:50:00",
            "end_time": "10:30:00",
            "short_trend_bars": 2,
            "long_trend_bars": 2,
            "min_trend_move_ticks": 1,
            "min_sweep_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
        }
    )

    bars = _uptrend_pdl_reclaim_bars()
    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(bars[-1])

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_low_trend_flow_reclaim"
    assert signal.report_fields["orderflow_imbalance"] == -0.3
    assert signal.report_fields["short_trend_current_low"] == 96.0


def test_trend_orderflow_pdl_sweep_reclaim_rejects_when_flow_is_not_absorbed():
    entry = TrendOrderflowPdhPdlSweepReclaimEntry(
        {
            "start_time": "09:50:00",
            "end_time": "10:30:00",
            "short_trend_bars": 2,
            "long_trend_bars": 2,
            "min_trend_move_ticks": 1,
            "min_sweep_ticks": 1,
            "reclaim_buffer_ticks": 0,
            "reclaim_window_bars": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
        }
    )

    bars = _uptrend_pdl_reclaim_bars()
    bars[-1]["signed_volume"] = 300
    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    assert entry.on_bar_close(bars[-1]) is None


def test_engine_enters_trend_orderflow_sweep_reclaim_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=8, freq="5min", tz="America/New_York")
    rows = []
    for idx, ts in enumerate(timestamps):
        rows.append(_engine_row(ts, idx))
    df = pd.DataFrame(rows)

    cfg = {
        "strategy_name": "test_trend_orderflow_sweep_reclaim",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "trend_orderflow_pdh_pdl_sweep_reclaim",
                "params": {
                    "start_time": "09:50:00",
                    "end_time": "10:30:00",
                    "short_trend_bars": 2,
                    "long_trend_bars": 2,
                    "min_trend_move_ticks": 1,
                    "min_sweep_ticks": 1,
                    "reclaim_buffer_ticks": 0,
                    "reclaim_window_bars": 1,
                    "min_orderflow_imbalance": 0.20,
                    "orderflow_mode": "signed",
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                    "flatten_time": "10:05:00",
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:05:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:05:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["entry_timestamp"]) == "2024-01-03 10:00:00-05:00"
    assert trade["entry_price"] == 100.75
    assert trade["orderflow_imbalance"] == -0.3


def _uptrend_pdl_reclaim_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="5min")
    highs = [96.0, 97.0, 98.0, 99.0, 99.75, 100.5]
    lows = [94.0, 95.0, 96.0, 97.0, 98.25, 99.5]
    closes = [95.5, 96.5, 97.5, 98.5, 99.25, 100.25]
    bars = [
        _bar(ts, idx, high=high, low=low, close=close)
        for idx, (ts, high, low, close) in enumerate(zip(timestamps, highs, lows, closes))
    ]
    bars[-1]["low"] = 99.5
    bars[-1]["close"] = 100.25
    bars[-1]["signed_volume"] = -300
    return bars


def _bar(ts, idx, *, high, low, close):
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": pd.Timestamp(ts).date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close - 0.25,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
            "volume_ratio": 1.0,
            "signed_volume": 0,
            "large10_signed_volume": 0,
            "large10_volume": 100,
            "large20_signed_volume": 0,
            "large20_volume": 100,
            "prev_rth_high": 105.0,
            "prev_rth_low": 100.0,
            "prev_rth_high_fresh": True,
            "prev_rth_low_fresh": True,
        },
        name=idx,
    )


def _engine_row(ts, idx):
    base = _bar(ts, idx, high=96.0 + idx, low=94.0 + idx, close=95.5 + idx)
    if idx == 5:
        base["high"] = 100.5
        base["low"] = 99.5
        base["close"] = 100.25
        base["signed_volume"] = -300
    if idx == 6:
        base["open"] = 100.5
        base["high"] = 101.0
        base["low"] = 100.0
        base["close"] = 100.75
        base["signed_volume"] = 0
    return base.to_dict()
