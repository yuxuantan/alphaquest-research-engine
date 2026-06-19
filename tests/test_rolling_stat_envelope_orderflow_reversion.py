import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.rolling_stat_envelope_orderflow_reversion import (
    RollingStatEnvelopeOrderflowReversionEntry,
)


def test_rolling_stat_envelope_reversion_emits_long_on_lower_band_sell_pressure():
    entry = RollingStatEnvelopeOrderflowReversionEntry(_entry_params())
    bars = _lower_band_bars()

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(bars[-1])

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "rolling_stat_lower_band_reversion"
    assert signal.sweep_low == 99.5
    assert signal.report_fields["orderflow_imbalance"] == -0.2
    assert signal.report_fields["rolling_mean"] == 100.5
    assert signal.report_fields["lower_band"] == 100.0


def test_rolling_stat_envelope_reversion_rejects_wrong_side_orderflow():
    entry = RollingStatEnvelopeOrderflowReversionEntry(_entry_params())
    bars = _lower_band_bars()
    bars[-1]["signed_volume"] = 200

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    assert entry.on_bar_close(bars[-1]) is None


def test_engine_enters_rolling_stat_envelope_reversion_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=7, freq="5min", tz="America/New_York")
    bars = _lower_band_bars(timestamps=timestamps[:5])
    rows = [bar.to_dict() for bar in bars]
    rows.append(_bar(timestamps[5], 5, open_=100.0, high=100.5, low=99.75, close=100.25).to_dict())
    rows.append(_bar(timestamps[6], 6, open_=100.25, high=100.5, low=100.0, close=100.25).to_dict())
    df = pd.DataFrame(rows)

    cfg = {
        "strategy_name": "test_rolling_stat_envelope_reversion",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "rolling_stat_envelope_orderflow_reversion",
                "params": {**_entry_params(), "flatten_time": "10:00:00"},
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:00:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:00:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:55:00-05:00"
    assert trade["entry_price"] == 100.25
    assert trade["orderflow_imbalance"] == -0.2


def _entry_params():
    return {
        "start_time": "09:50:00",
        "end_time": "10:30:00",
        "lookback_bars": 4,
        "band_z": 1.0,
        "min_std_ticks": 0.5,
        "min_bar_range_ticks": 1,
        "orderflow_mode": "signed",
        "min_orderflow_imbalance": 0.1,
        "tick_size": 0.25,
        "allow_long": True,
        "allow_short": True,
        "max_trades_per_day": 1,
    }


def _lower_band_bars(timestamps=None):
    if timestamps is None:
        timestamps = pd.date_range("2024-01-03 09:30:00", periods=5, freq="5min")
    specs = [
        (100.0, 100.5, 99.75, 100.0, 0),
        (101.0, 101.25, 100.75, 101.0, 0),
        (100.0, 100.5, 99.75, 100.0, 0),
        (101.0, 101.25, 100.75, 101.0, 0),
        (100.25, 100.5, 99.5, 99.75, -200),
    ]
    return [
        _bar(ts, idx, open_=open_, high=high, low=low, close=close, signed_volume=signed_volume)
        for idx, (ts, (open_, high, low, close, signed_volume)) in enumerate(zip(timestamps, specs))
    ]


def _bar(ts, idx, *, open_, high, low, close, signed_volume=0):
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": pd.Timestamp(ts).date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
            "signed_volume": signed_volume,
            "large10_signed_volume": signed_volume,
            "large10_volume": 1000,
            "large20_signed_volume": signed_volume,
            "large20_volume": 1000,
        },
        name=idx,
    )
