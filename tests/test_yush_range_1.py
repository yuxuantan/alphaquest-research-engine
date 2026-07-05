import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.yush_range_1 import YushRange1Entry
from propstack.strategy_modules.entry.yush_range_2 import YushRange2Entry


TZ = "America/New_York"


def _bar(timestamp, **overrides):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize(TZ)
    else:
        ts = ts.tz_convert(TZ)
    row = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "symbol": "ES",
        "open": 102.0,
        "high": 104.5,
        "low": 100.5,
        "close": 102.0,
        "volume": 1000,
        "prev_rth_high": 106.0,
        "prev_rth_low": 100.75,
        "prev_rth_close": 102.25,
        "overnight_high": 105.5,
        "overnight_low": 100.25,
    }
    row.update(overrides)
    return row


def _detail(timestamp, price, volume, buy=0, sell=0):
    return {
        "timestamp": pd.Timestamp(timestamp, tz=TZ),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": volume,
        "buy_volume": buy,
        "sell_volume": sell,
        "num_trades": 1,
        "execution_granularity": "scid_record",
    }


def _seed_profile_rows():
    rows = [
        _detail("2024-01-03 09:30:00", 100.5, 300, buy=150, sell=150),
        _detail("2024-01-03 09:30:01", 101.5, 800, buy=400, sell=400),
        _detail("2024-01-03 09:30:02", 102.5, 1500, buy=750, sell=750),
        _detail("2024-01-03 09:30:03", 103.5, 800, buy=400, sell=400),
        _detail("2024-01-03 09:30:04", 104.5, 100, buy=50, sell=50),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _absorption_rows(include_confirmation=True, include_target=False):
    rows = [
        _detail("2024-01-03 10:00:00", 100.5, 400, buy=0, sell=400),
        _detail("2024-01-03 10:00:01", 101.25, 10, buy=10, sell=0),
    ]
    if include_confirmation:
        rows.append(_detail("2024-01-03 10:00:04", 101.25, 10, buy=10, sell=0))
    if include_target:
        rows.append(_detail("2024-01-03 10:00:05", 104.75, 10, buy=10, sell=0))
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _entry_params(**overrides):
    params = {
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "flatten_time": "15:55:00",
        "tick_size": 0.25,
        "bar_interval_minutes": 3,
        "profile_bucket_points": 1.0,
        "delta_bucket_points": 1.0,
        "value_area_fraction": 0.70,
        "lvn_poc_fraction": 0.20,
        "max_lvn_between_value_area": 1,
        "range_snapshot_minutes": 30,
        "max_range_change_pct": 0.20,
        "atr_period": 2,
        "atr_multiple": 2.0,
        "absorption_delta_threshold": 300,
        "absorption_hold_seconds": 3,
        "stop_offset_ticks": 2,
        "max_trades_per_day": 1,
        "min_profile_volume": 100,
        "min_profile_buckets": 3,
    }
    params.update(overrides)
    return params


def _prime_entry(entry):
    entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 09:30:00")), _seed_profile_rows())
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))


def test_yush_range_1_enters_after_absorption_bucket_holds_for_three_seconds():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["entry_reference_price"] == 101.25
    assert signal.metadata["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:04", tz=TZ)
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.metadata["profile_poc"] == 102.5
    assert signal.metadata["profile_val"] == 101.0
    assert signal.metadata["profile_vah"] == 104.0
    assert signal.metadata["lvn_between_value_area_count"] <= 1
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["absorption_bucket_delta"] <= -300


def test_yush_range_1_rejects_absorption_without_full_hold_time():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _absorption_rows(include_confirmation=False),
    )

    assert signal is None


def test_yush_range_2_uses_own_registered_setup_name():
    entry = YushRange2Entry(_entry_params(atr_multiple=0.5, start_time="09:30:00", end_time="11:30:00"))
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert signal is not None
    assert entry.name == "yush_range_2"
    assert signal.metadata["setup_mode"] == "yush_range_2"
    assert signal.level_type.startswith("yush_range_2_")
    assert signal.metadata["atr_multiple"] == 0.5


def test_engine_opens_yush_range_1_at_intrabar_tick_with_bucket_stop_and_2r_target():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "yush_range_1",
        "strategy": {
            "entry": {"module": "yush_range_1", "params": _entry_params()},
            "sl": {"module": "signal_price", "params": {"metadata_key": "signal_stop_price"}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 2.0}},
            "flatten_time": "15:55:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 10000,
            "daily_profit_stop": 10000,
        },
    }
    bar_times = pd.date_range("2024-01-03 09:30:00", "2024-01-03 10:03:00", freq="3min", tz=TZ)
    bars = pd.DataFrame([_bar(ts, low=100.5, high=105.0 if ts.minute == 0 and ts.hour == 10 else 104.5) for ts in bar_times])
    detail = pd.concat(
        [
            _seed_profile_rows(),
            _absorption_rows(include_target=True),
        ],
        ignore_index=True,
    )
    detail.attrs["detail_granularity"] = "scid_record"

    result = BacktestEngine(cfg).run(bars, detail_data=detail)
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:04", tz=TZ)
    assert trade["entry_price"] == 101.25
    assert trade["stop_price"] == 99.5
    assert trade["target_price"] == 104.75
    assert trade["exit_reason"] == "target"
