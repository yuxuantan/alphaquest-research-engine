from __future__ import annotations

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.mes_crowding_aoi_trap import MesCrowdingAoiTrapEntry


def _params(**overrides):
    params = {
        "setup_mode": "prior_extreme_trap",
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "opening_range_minutes": 30,
        "lookback_minutes": 15,
        "rank_window": 252,
        "share_mode": "trade",
        "min_share_rank": 0.65,
        "min_abs_return_ticks": 4,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_delta_imbalance": 0.02,
        "require_footprint_absorption": True,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _bar(timestamp: str, **overrides):
    values = {
        "timestamp": pd.Timestamp(timestamp),
        "session_date": "2024-01-03",
        "session_label": "RTH",
        "is_rth": True,
        "open": 99.75,
        "high": 100.50,
        "low": 99.50,
        "close": 100.25,
        "volume": 1000,
        "signed_volume": 100,
        "prev_rth_low": 100.0,
        "prev_rth_high": 102.0,
        "overnight_low": 99.75,
        "overnight_high": 102.25,
        "prior_vap_poc": 101.0,
        "prior_vap_vah": 102.0,
        "prior_vap_val": 100.0,
        "prior_vap_lvn_near_low": 100.0,
        "prior_vap_lvn_near_high": 102.0,
        "mes_trade_share_15": 0.15,
        "mes_trade_share_15_rank252": 0.80,
        "mes_participation_share_15": 0.08,
        "mes_participation_share_15_rank252": 0.75,
        "es_return_ticks_15": -6.0,
        "footprint_absorption_long": True,
        "footprint_absorption_short": False,
        "footprint_sell_imbalance_below_close": False,
        "footprint_buy_imbalance_above_close": False,
    }
    values.update(overrides)
    return pd.Series(values)


def test_mes_crowding_aoi_trap_emits_long_after_completed_reclaim_bar():
    entry = MesCrowdingAoiTrapEntry(_params())

    signal = entry.on_bar_close(_bar("2024-01-03 10:00:00"))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:01:00")
    assert signal.report_fields["aoi_type"] == "prior_rth_low"
    assert signal.report_fields["mes_share_rank"] == 0.80


def test_mes_crowding_aoi_trap_rejects_low_mes_rank():
    entry = MesCrowdingAoiTrapEntry(_params())

    signal = entry.on_bar_close(_bar("2024-01-03 10:00:00", mes_trade_share_15_rank252=0.50))

    assert signal is None


def test_opening_range_aoi_is_available_only_after_opening_window():
    entry = MesCrowdingAoiTrapEntry(
        _params(
            setup_mode="opening_range_trap",
            start_time="09:32:00",
            opening_range_minutes=2,
            min_delta_imbalance=0.0,
            require_footprint_absorption=False,
        )
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", low=100.00, close=100.50)) is None
    assert entry.on_bar_close(_bar("2024-01-03 09:31:00", low=100.00, close=100.25)) is None
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:32:00", low=99.50, close=100.25, es_return_ticks_15=-6.0)
    )

    assert signal is not None
    assert signal.report_fields["aoi_type"] == "opening_range_low"


def test_engine_enters_mes_crowding_aoi_trap_on_next_bar_open():
    timestamps = pd.to_datetime(["2024-01-03 10:00:00", "2024-01-03 10:01:00"]).tz_localize(
        "America/New_York"
    )
    rows = []
    rows.append(_bar("2024-01-03 10:00:00").to_dict())
    rows.append(_bar("2024-01-03 10:01:00", open=100.25, high=100.75, low=100.00, close=100.50).to_dict())
    df = pd.DataFrame(rows)
    df["timestamp"] = timestamps
    df["session_date"] = [timestamps[0].date()] * len(df)
    cfg = {
        "strategy": {
            "entry": {"module": "mes_crowding_aoi_trap", "params": _params()},
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 2.0}},
            "flatten_time": "10:02:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:02:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["signal_close_timestamp"]) == "2024-01-03 10:01:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 10:01:00-05:00"


def test_factory_registration_builds_mes_crowding_aoi_trap():
    entry = build_entry_module({"module": "mes_crowding_aoi_trap", "params": _params()})

    assert isinstance(entry, MesCrowdingAoiTrapEntry)
