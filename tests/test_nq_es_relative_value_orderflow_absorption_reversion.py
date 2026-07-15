from __future__ import annotations

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.nq_es_relative_value_orderflow_absorption_reversion import (
    NqEsRelativeValueOrderflowAbsorptionReversionEntry,
)


def test_nq_es_absorption_reversion_emits_long_when_nq_underperforms_with_buy_absorption():
    entry = NqEsRelativeValueOrderflowAbsorptionReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "orderflow_window_minutes": 30,
            "min_spread_bps": 6,
            "min_absorption_imbalance": 0.1,
        }
    )

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:59", es_return=1.0, nq_return=-8.0, nq_signed_imbalance=0.18)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["leader_symbol"] == "ES"
    assert signal.report_fields["traded_symbol"] == "NQ"
    assert signal.report_fields["nq_signed_absorption_imbalance"] == 0.18


def test_nq_es_absorption_reversion_emits_short_when_nq_outperforms_with_sell_absorption():
    entry = NqEsRelativeValueOrderflowAbsorptionReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "orderflow_window_minutes": 30,
            "min_spread_bps": 6,
            "min_absorption_imbalance": 0.1,
        }
    )

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:59", es_return=-1.0, nq_return=8.0, nq_signed_imbalance=-0.18)
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["nq_signed_absorption_imbalance"] == -0.18


def test_nq_es_absorption_reversion_rejects_flow_that_confirms_the_nq_price_move_and_releases_session():
    entry = NqEsRelativeValueOrderflowAbsorptionReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "orderflow_window_minutes": 30,
            "min_spread_bps": 6,
            "min_absorption_imbalance": 0.1,
        }
    )

    rejected = entry.on_bar_close(
        _bar("2024-01-03 09:59", es_return=1.0, nq_return=-8.0, nq_signed_imbalance=-0.18)
    )

    assert rejected is None
    assert entry.state_by_day[pd.Timestamp("2024-01-03").date().isoformat()]["signaled"] is False


def test_engine_enters_nq_es_absorption_reversion_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:58:00", periods=4, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["NQ"] * 4,
            "session_date": [timestamps[0].date().isoformat()] * 4,
            "session_label": ["RTH"] * 4,
            "is_rth": [True] * 4,
            "open": [100.0, 100.0, 100.75, 100.75],
            "high": [100.5, 101.0, 101.0, 101.0],
            "low": [99.5, 99.5, 100.25, 100.25],
            "close": [100.0, 100.5, 100.5, 100.5],
            "volume": [1000.0] * 4,
            "es_return_bps_15": [1.0] * 4,
            "nq_return_bps_15": [-8.0] * 4,
            "nq_minus_es_return_bps_15": [-9.0] * 4,
            "nq_signed_imbalance_15": [0.18] * 4,
            "es_return_bps_30": [1.0] * 4,
            "nq_return_bps_30": [-8.0] * 4,
            "nq_minus_es_return_bps_30": [-9.0] * 4,
            "nq_signed_imbalance_30": [0.18] * 4,
            "es_return_bps_60": [1.0] * 4,
            "nq_return_bps_60": [-8.0] * 4,
            "nq_minus_es_return_bps_60": [-9.0] * 4,
            "nq_signed_imbalance_60": [0.18] * 4,
        }
    )
    cfg = {
        "strategy_name": "test_nq_es_absorption_reversion",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "nq_es_relative_value_orderflow_absorption_reversion",
                "params": {
                    "setup_mode": "two_sided_divergence_fade",
                    "entry_time": "10:00:00",
                    "bar_interval_minutes": 1,
                    "lookback_minutes": 30,
                    "orderflow_window_minutes": 30,
                    "min_spread_bps": 6,
                    "min_absorption_imbalance": 0.1,
                    "max_trades_per_day": 1,
                    "flatten_time": "10:01:00",
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:01:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 5.0,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:01:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["entry_timestamp"]) == "2024-01-03 10:00:00-05:00"
    assert trade["entry_price"] == 101.0
    assert trade["nq_signed_absorption_imbalance"] == 0.18


def _bar(timestamp, *, es_return: float, nq_return: float, nq_signed_imbalance: float):
    ts = pd.Timestamp(timestamp)
    lookback = 30
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1000,
            f"es_return_bps_{lookback}": es_return,
            f"nq_return_bps_{lookback}": nq_return,
            f"nq_minus_es_return_bps_{lookback}": nq_return - es_return,
            f"nq_signed_imbalance_{lookback}": nq_signed_imbalance,
        }
    )
