import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.overnight_range_orderflow_breakout import (
    OvernightRangeOrderflowBreakoutEntry,
)


def test_overnight_range_breakout_emits_long_with_compressed_range_and_buy_flow(tmp_path):
    entry = OvernightRangeOrderflowBreakoutEntry(_entry_params(tmp_path))

    signal = entry.on_bar_close(_bar("2024-01-03 09:35:00-05:00", close=105.5, signed_volume=300))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "overnight_high_compression_breakout"
    assert signal.swept_level == 105.0
    assert signal.report_fields["overnight_range_rank_252"] == 0.2
    assert signal.report_fields["orderflow_imbalance"] == 0.3


def test_overnight_range_breakout_rejects_wrong_side_flow(tmp_path):
    entry = OvernightRangeOrderflowBreakoutEntry(_entry_params(tmp_path))

    signal = entry.on_bar_close(_bar("2024-01-03 09:35:00-05:00", close=105.5, signed_volume=-300))

    assert signal is None


def test_overnight_range_breakout_rejects_uncompressed_overnight_range(tmp_path):
    feature_csv = tmp_path / "features.csv"
    _write_features(feature_csv, rank=0.8)
    params = _entry_params(tmp_path / "base")
    params["feature_csv"] = str(feature_csv)
    entry = OvernightRangeOrderflowBreakoutEntry(params)

    signal = entry.on_bar_close(_bar("2024-01-03 09:35:00-05:00", close=105.5, signed_volume=300))

    assert signal is None


def test_engine_enters_overnight_range_breakout_on_next_bar_open(tmp_path):
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=4, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        [
            _bar(timestamps[0], open_=104.75, high=105.0, low=104.0, close=104.75, signed_volume=0).to_dict(),
            _bar(timestamps[1], open_=104.75, high=105.75, low=104.5, close=105.5, signed_volume=300).to_dict(),
            _bar(timestamps[2], open_=105.5, high=112.0, low=105.25, close=106.0, signed_volume=0).to_dict(),
            _bar(timestamps[3], open_=106.0, high=106.25, low=105.75, close=106.0, signed_volume=0).to_dict(),
        ]
    )
    cfg = {
        "strategy_name": "test_overnight_range_orderflow_breakout",
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "overnight_range_orderflow_breakout",
                "params": {**_entry_params(tmp_path), "flatten_time": "10:00:00"},
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
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:40:00-05:00"
    assert trade["entry_price"] == 105.75
    assert trade["overnight_high"] == 105.0
    assert trade["orderflow_imbalance"] == 0.3


def _entry_params(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    feature_csv = tmp_path / "features.csv"
    _write_features(feature_csv, rank=0.2)
    return {
        "feature_csv": str(feature_csv),
        "start_time": "09:35:00",
        "end_time": "10:30:00",
        "flatten_time": "10:00:00",
        "tick_size": 0.25,
        "max_overnight_range_rank": 0.3,
        "min_overnight_range_points": 2.0,
        "breakout_buffer_ticks": 1,
        "orderflow_mode": "signed",
        "min_orderflow_imbalance": 0.1,
        "min_flow_volume": 0,
        "allow_long": True,
        "allow_short": True,
        "max_trades_per_day": 1,
    }


def _write_features(path, rank):
    pd.DataFrame(
        [
            {
                "session_date": "2024-01-03",
                "overnight_high": 105.0,
                "overnight_low": 100.0,
                "overnight_midpoint": 102.5,
                "overnight_range_points": 5.0,
                "overnight_range_rank_252": rank,
            }
        ]
    ).to_csv(path, index=False)


def _bar(ts, *, open_=104.75, high=105.75, low=104.5, close=105.5, signed_volume=300):
    ts = pd.Timestamp(ts)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
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
        }
    )
