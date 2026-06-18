import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.es_mes_lead_lag import EsMesLeadLagEntry


def test_es_mes_lead_lag_emits_long_when_mes_leads_and_es_lags():
    entry = EsMesLeadLagEntry(
        {
            "signal_time": "10:30:00",
            "lookback_minutes": 15,
            "flow_window_minutes": 15,
            "mes_flow_mode": "signed",
            "min_mes_return_ticks": 5,
            "min_lag_gap_ticks": 3,
            "min_mes_flow_imbalance": 0.04,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            es_trade_orderflow_return_ticks_15=2.0,
            mes_trade_orderflow_return_ticks_15=7.0,
            mes_trade_orderflow_imbalance_15=0.08,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["directional_lag_gap_ticks"] == 5.0
    assert str(signal.report_fields["signal_close_timestamp"]) == "2024-01-03 10:30:00"


def test_es_mes_lead_lag_rejects_when_es_has_already_followed():
    entry = EsMesLeadLagEntry(
        {
            "signal_time": "10:30:00",
            "lookback_minutes": 15,
            "flow_window_minutes": 15,
            "mes_flow_mode": "signed",
            "min_mes_return_ticks": 5,
            "min_lag_gap_ticks": 3,
            "min_mes_flow_imbalance": 0.04,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            es_trade_orderflow_return_ticks_15=5.5,
            mes_trade_orderflow_return_ticks_15=7.0,
            mes_trade_orderflow_imbalance_15=0.08,
        )
    )

    assert signal is None


def test_es_mes_lead_lag_accepts_predeclared_signal_window():
    entry = EsMesLeadLagEntry(
        {
            "signal_start": "10:00:00",
            "signal_end": "11:30:00",
            "lookback_minutes": 15,
            "flow_window_minutes": 15,
            "mes_flow_mode": "signed",
            "min_mes_return_ticks": 5,
            "min_lag_gap_ticks": 3,
            "min_mes_flow_imbalance": 0.04,
        }
    )

    early = entry.on_bar_close(
        _bar(
            "2024-01-03 09:58:00",
            es_trade_orderflow_return_ticks_15=2.0,
            mes_trade_orderflow_return_ticks_15=7.0,
            mes_trade_orderflow_imbalance_15=0.08,
        )
    )
    in_window = entry.on_bar_close(
        _bar(
            "2024-01-03 10:14:00",
            es_trade_orderflow_return_ticks_15=2.0,
            mes_trade_orderflow_return_ticks_15=7.0,
            mes_trade_orderflow_imbalance_15=0.08,
        )
    )

    assert early is None
    assert in_window is not None
    assert in_window.report_fields["signal_start"] == "10:00:00"
    assert in_window.report_fields["signal_end"] == "11:30:00"


def test_es_mes_lead_lag_emits_short_when_mes_leads_lower_and_es_lags():
    entry = EsMesLeadLagEntry(
        {
            "setup_mode": "mes_down_es_lag_short",
            "signal_time": "11:30:00",
            "lookback_minutes": 30,
            "flow_window_minutes": 30,
            "mes_flow_mode": "large10",
            "min_mes_return_ticks": 6,
            "min_lag_gap_ticks": 2,
            "min_mes_flow_imbalance": 0.03,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 11:29:00",
            es_trade_orderflow_return_ticks_30=-3.0,
            mes_trade_orderflow_return_ticks_30=-8.0,
            mes_trade_orderflow_large10_imbalance_30=-0.07,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["directional_lag_gap_ticks"] == 5.0


def test_engine_enters_es_mes_lead_lag_on_next_bar_open():
    timestamps = pd.to_datetime(
        [
            "2024-01-03 10:29:00",
            "2024-01-03 10:30:00",
        ]
    ).tz_localize("America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 101.0],
            "high": [100.25, 101.50],
            "low": [99.75, 100.75],
            "close": [100.0, 101.25],
            "volume": [1000] * len(timestamps),
            "es_trade_orderflow_return_ticks_15": [2.0, 0.0],
            "mes_trade_orderflow_return_ticks_15": [7.0, 0.0],
            "mes_trade_orderflow_imbalance_15": [0.08, 0.0],
        }
    )
    cfg = {
        "strategy": {
            "entry": {
                "module": "es_mes_lead_lag",
                "params": {
                    "signal_time": "10:30:00",
                    "lookback_minutes": 15,
                    "flow_window_minutes": 15,
                    "mes_flow_mode": "signed",
                    "min_mes_return_ticks": 5,
                    "min_lag_gap_ticks": 3,
                    "min_mes_flow_imbalance": 0.04,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.0025, "round_to_tick": True}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
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


def _bar(timestamp: str, **overrides) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    row = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "open": 100.0,
        "high": 100.25,
        "low": 99.75,
        "close": 100.0,
        "es_trade_orderflow_return_ticks_15": 0.0,
        "mes_trade_orderflow_return_ticks_15": 0.0,
        "mes_trade_orderflow_imbalance_15": 0.0,
        "es_trade_orderflow_return_ticks_30": 0.0,
        "mes_trade_orderflow_return_ticks_30": 0.0,
        "mes_trade_orderflow_large10_imbalance_30": 0.0,
    }
    row.update(overrides)
    return pd.Series(row)
