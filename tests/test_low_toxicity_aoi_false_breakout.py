from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry import build_entry_module
from propstack.strategy_modules.entry.low_toxicity_aoi_false_breakout import (
    LowToxicityAoiFalseBreakoutEntry,
)


def _params(**overrides):
    params = {
        "setup_mode": "prior_extreme_false_breakout",
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "bar_interval_minutes": 1,
        "opening_range_minutes": 30,
        "tick_size": 0.25,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "max_abs_delta_imbalance": 0.12,
        "large_volume_col": "large20_volume",
        "max_large_volume_share": 0.10,
        "cached_profile_prefix": "prior_vap",
        "require_reversal_body": True,
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
        "signed_volume": 50,
        "large20_volume": 25,
        "prev_rth_low": 100.0,
        "prev_rth_high": 102.0,
        "overnight_low": 99.75,
        "overnight_high": 102.25,
        "prior_vap_poc": 101.0,
        "prior_vap_vah": 102.0,
        "prior_vap_val": 100.0,
        "prior_vap_lvn_near_low": 100.0,
        "prior_vap_lvn_near_high": 102.0,
    }
    values.update(overrides)
    return pd.Series(values)


def test_low_toxicity_aoi_false_breakout_emits_long_on_weak_flow_support_reclaim():
    entry = LowToxicityAoiFalseBreakoutEntry(_params())

    signal = entry.on_bar_close(
        _bar("2024-01-03 10:29:00", open=99.75, high=100.50, low=99.50, close=100.25)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["aoi_type"] == "prior_rth_low"
    assert signal.report_fields["abs_delta_imbalance"] == 0.05
    assert signal.report_fields["large_volume_share"] == 0.025
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30:00")


def test_low_toxicity_aoi_false_breakout_rejects_high_delta_pressure():
    entry = LowToxicityAoiFalseBreakoutEntry(_params())

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            open=99.75,
            high=100.50,
            low=99.50,
            close=100.25,
            signed_volume=-250,
        )
    )

    assert signal is None


def test_low_toxicity_aoi_false_breakout_uses_completed_opening_range():
    entry = LowToxicityAoiFalseBreakoutEntry(_params(setup_mode="opening_range_false_breakout"))

    for minute in range(30):
        entry.on_bar_close(_bar(f"2024-01-03 09:{30 + minute:02d}:00", high=101.0, low=100.0, close=100.5))
    signal = entry.on_bar_close(
        _bar("2024-01-03 10:00:00", open=99.75, high=100.50, low=99.50, close=100.25)
    )

    assert signal is not None
    assert signal.report_fields["aoi_type"] == "opening_range_low"


def test_engine_enters_low_toxicity_aoi_false_breakout_on_next_bar_open():
    timestamps = pd.to_datetime(["2024-01-03 10:29:00", "2024-01-03 10:30:00"]).tz_localize(
        "America/New_York"
    )
    rows = [
        _bar("2024-01-03 10:29:00", open=99.75, high=100.50, low=99.50, close=100.25).to_dict(),
        _bar("2024-01-03 10:30:00", open=100.25, high=100.75, low=100.00, close=100.50).to_dict(),
    ]
    df = pd.DataFrame(rows)
    df["timestamp"] = timestamps
    df["session_date"] = [timestamps[0].date()] * len(df)
    cfg = {
        "strategy": {
            "entry": {"module": "low_toxicity_aoi_false_breakout", "params": _params()},
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


def test_factory_registration_builds_low_toxicity_aoi_false_breakout():
    entry = build_entry_module({"module": "low_toxicity_aoi_false_breakout", "params": _params()})

    assert isinstance(entry, LowToxicityAoiFalseBreakoutEntry)
