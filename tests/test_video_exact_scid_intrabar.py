import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.video_exact_orderflow_playbook_scid_intrabar import (
    VideoExactOrderflowPlaybookScidIntrabarEntry,
)


def _bar(timestamp, **overrides):
    row = {
        "timestamp": pd.Timestamp(timestamp, tz="America/New_York"),
        "session_date": pd.Timestamp(timestamp).date(),
        "is_rth": True,
        "open": 100.0,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 1000,
        "signed_volume": 0,
        "developing_vap_poc": 101.0,
        "developing_vap_vah": 102.0,
        "developing_vap_val": 100.0,
        "developing_vap_lvn_near_close": 101.0,
        "developing_vap_lvn_near_high": 101.5,
        "developing_vap_lvn_near_low": 100.25,
        "developing_vap_total_volume": 10000,
        "developing_vap_bars": 20,
        "overnight_low": 100.0,
        "overnight_high": 104.0,
    }
    row.update(overrides)
    return row


def _detail_rows():
    rows = [
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:00", tz="America/New_York"),
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 5,
            "buy_volume": 5,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:10", tz="America/New_York"),
            "open": 99.75,
            "high": 99.75,
            "low": 99.75,
            "close": 99.75,
            "volume": 60,
            "buy_volume": 0,
            "sell_volume": 60,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:20", tz="America/New_York"),
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 200,
            "buy_volume": 0,
            "sell_volume": 200,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:21", tz="America/New_York"),
            "open": 100.25,
            "high": 100.25,
            "low": 100.25,
            "close": 100.25,
            "volume": 1,
            "buy_volume": 1,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _entry_params():
    return {
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "flatten_time": "15:55:00",
        "bar_interval_minutes": 3,
        "tick_size": 0.25,
        "market_aoi_max_distance_ticks": 16,
        "aoi_reach_tolerance_ticks": 4,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_absorption_volume": 50,
        "min_aoi_confluences": 2,
        "min_large200_record_volume": 200,
        "min_delta_activity_imbalance": 0.03,
        "profile_source": "cached_developing_vap",
        "cached_profile_prefix": "developing_vap",
        "setup_mode": "model1_range_value_edge_two_sided",
        "target_reference": "value_midpoint",
        "allow_long": True,
        "allow_short": True,
    }


def test_scid_intrabar_video_entry_detects_first_long_reclaim_tick():
    entry = VideoExactOrderflowPlaybookScidIntrabarEntry(_entry_params())
    entry.on_bar_close(pd.Series(_bar("2024-01-03 09:57:00")))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["entry_reference_price"] == 100.25
    assert signal.metadata["intended_entry_timestamp"] == pd.Timestamp(
        "2024-01-03 10:00:21", tz="America/New_York"
    )
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,market_level,big_trades,delta_activity"


def test_engine_opens_scid_intrabar_video_entry_at_tick_price():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "video_exact_orderflow_playbook_scid_intrabar",
        "strategy": {
            "entry": {
                "module": "video_exact_orderflow_playbook_scid_intrabar",
                "params": _entry_params(),
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 2}},
            "tp": {
                "module": "signal_price",
                "params": {"metadata_key": "signal_target_price", "fallback_target_r_multiple": 3.0},
            },
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
    bars = pd.DataFrame(
        [
            _bar("2024-01-03 09:57:00", high=100.5, low=99.5, close=100.0),
            _bar("2024-01-03 10:00:00", high=100.5, low=99.75, close=100.25),
            _bar("2024-01-03 10:03:00", open=100.25, high=101.25, low=100.25, close=101.0),
        ]
    )

    result = BacktestEngine(cfg).run(bars, detail_data=_detail_rows())
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:21", tz="America/New_York")
    assert trade["entry_price"] == 100.25
    assert trade["target_price"] == 101.0
