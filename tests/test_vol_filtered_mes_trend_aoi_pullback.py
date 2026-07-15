from __future__ import annotations

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.vol_filtered_mes_trend_aoi_pullback import (
    VolFilteredMesTrendAoiPullbackEntry,
)


def _feature_csv(tmp_path, value: float = 0.40):
    path = tmp_path / "lagged_vol_features.csv"
    path.write_text(
        "session_date,absret5_rank_252,downside20_rank_252,vol5_over_vol20\n"
        f"2024-01-03,{value},{value},0.90\n",
        encoding="utf-8",
    )
    return str(path)


def _params(feature_csv: str, **overrides):
    params = {
        "feature_csv": feature_csv,
        "volatility_filter_label": "exclude_extreme_absret5",
        "volatility_gate_column": "absret5_rank_252",
        "volatility_gate_max": 0.95,
        "setup_mode": "prior_extreme_pullback",
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "tick_size": 0.25,
        "opening_range_minutes": 30,
        "lookback_minutes": 15,
        "trend_lookback_minutes": 30,
        "rank_window": 252,
        "share_mode": "trade",
        "min_share_rank": 0.65,
        "min_abs_return_ticks": 4,
        "min_trend_return_ticks": 6,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_delta_imbalance": 0.02,
        "require_footprint_absorption": False,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return params


def _bar(timestamp: str, **overrides):
    close = overrides.pop("close", 100.0)
    values = {
        "timestamp": pd.Timestamp(timestamp),
        "session_date": "2024-01-03",
        "session_label": "RTH",
        "is_rth": True,
        "open": close,
        "high": close + 0.25,
        "low": close - 0.25,
        "close": close,
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
        "footprint_absorption_long": False,
        "footprint_absorption_short": False,
        "footprint_sell_imbalance_below_close": False,
        "footprint_buy_imbalance_above_close": False,
    }
    values.update(overrides)
    return pd.Series(values)


def test_vol_filtered_mes_trend_aoi_pullback_emits_when_lagged_vol_filter_passes(tmp_path):
    entry = VolFilteredMesTrendAoiPullbackEntry(_params(_feature_csv(tmp_path, value=0.40)))

    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0))
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:29:00", open=99.75, high=100.50, low=99.50, close=100.25)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["volatility_gate_column"] == "absret5_rank_252"
    assert signal.report_fields["volatility_gate_value"] == 0.40
    assert signal.report_fields["volatility_filter_result"] == "passed"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30:00")


def test_vol_filtered_mes_trend_aoi_pullback_rejects_when_lagged_vol_filter_fails(tmp_path):
    entry = VolFilteredMesTrendAoiPullbackEntry(_params(_feature_csv(tmp_path, value=0.99)))

    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0))
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:29:00", open=99.75, high=100.50, low=99.50, close=100.25)
    )

    assert signal is None


def test_engine_enters_vol_filtered_mes_trend_aoi_pullback_on_next_bar_open(tmp_path):
    feature_csv = _feature_csv(tmp_path, value=0.40)
    timestamps = pd.to_datetime(
        ["2024-01-03 09:44:00", "2024-01-03 10:14:00", "2024-01-03 10:29:00", "2024-01-03 10:30:00"]
    ).tz_localize("America/New_York")
    rows = [
        _bar("2024-01-03 09:44:00", close=100.0).to_dict(),
        _bar("2024-01-03 10:14:00", close=102.0).to_dict(),
        _bar("2024-01-03 10:29:00", open=99.75, high=100.50, low=99.50, close=100.25).to_dict(),
        _bar("2024-01-03 10:30:00", open=100.25, high=100.75, low=100.00, close=100.50).to_dict(),
    ]
    df = pd.DataFrame(rows)
    df["timestamp"] = timestamps
    df["session_date"] = [timestamps[0].date()] * len(df)
    cfg = {
        "strategy": {
            "entry": {"module": "vol_filtered_mes_trend_aoi_pullback", "params": _params(feature_csv)},
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 2.0}},
            "flatten_time": "10:31:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:31:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["signal_close_timestamp"]) == "2024-01-03 10:30:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 10:30:00-05:00"
    assert result["trades"].iloc[0]["volatility_gate_value"] == 0.40


def test_factory_registration_builds_vol_filtered_mes_trend_aoi_pullback(tmp_path):
    entry = build_entry_module(
        {"module": "vol_filtered_mes_trend_aoi_pullback", "params": _params(_feature_csv(tmp_path))}
    )

    assert isinstance(entry, VolFilteredMesTrendAoiPullbackEntry)
