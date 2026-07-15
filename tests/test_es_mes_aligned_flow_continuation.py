import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.es_mes_aligned_flow_continuation import (
    EsMesAlignedFlowContinuationEntry,
)


def test_es_mes_aligned_flow_continuation_uses_completed_bar_features():
    entry = EsMesAlignedFlowContinuationEntry(
        {
            "signal_time": "10:30:00",
            "bar_interval_minutes": 1,
            "return_window_minutes": 30,
            "flow_window_minutes": 30,
            "mes_flow_mode": "signed",
            "min_es_return_ticks": 4,
            "min_mes_flow_imbalance": 0.05,
        }
    )

    early = _bar("2024-01-03 10:28:00", es_return=8, mes_flow=0.08)
    assert entry.on_bar_close(early) is None

    signal = entry.on_bar_close(_bar("2024-01-03 10:29:00", es_return=8, mes_flow=0.08))

    assert signal is not None
    assert signal.direction == "long"
    assert str(signal.report_fields["signal_close_timestamp"]) == "2024-01-03 10:30:00"
    assert signal.report_fields["feature_method"] == "completed_bar_es_trend_mes_aligned_flow"


def test_es_mes_aligned_flow_continuation_rejects_misaligned_mes_flow():
    entry = EsMesAlignedFlowContinuationEntry(
        {
            "signal_time": "10:30:00",
            "bar_interval_minutes": 1,
            "return_window_minutes": 30,
            "flow_window_minutes": 30,
            "mes_flow_mode": "large10",
            "min_es_return_ticks": 4,
            "min_mes_flow_imbalance": 0.05,
        }
    )

    bar = _bar(
        "2024-01-03 10:29:00",
        es_return=8,
        mes_flow=-0.10,
        flow_column="mes_trade_orderflow_large10_imbalance_30",
    )

    assert entry.on_bar_close(bar) is None


def test_mes_aligned_flow_continuation_supports_nq_primary_prefix():
    entry = EsMesAlignedFlowContinuationEntry(
        {
            "primary_prefix": "nq",
            "signal_time": "10:30:00",
            "bar_interval_minutes": 1,
            "return_window_minutes": 30,
            "flow_window_minutes": 30,
            "mes_flow_mode": "signed",
            "min_primary_return_ticks": 4,
            "min_mes_flow_imbalance": 0.05,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29:00", es_return=0, nq_return=-8, mes_flow=-0.08))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["primary_prefix"] == "nq"
    assert signal.report_fields["feature_method"] == "completed_bar_nq_trend_mes_aligned_flow"
    assert signal.report_fields["primary_return_ticks"] == -8


def test_engine_enters_es_mes_aligned_flow_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 10:24:00", periods=8, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7],
            "high": [100.2, 100.3, 100.4, 100.5, 100.6, 100.8, 100.9, 101.0],
            "low": [99.8, 99.9, 100.0, 100.1, 100.2, 100.3, 100.4, 100.5],
            "close": [100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7, 100.8],
            "volume": [1000] * len(timestamps),
            "es_trade_orderflow_return_ticks_15": [0, 0, 0, 0, 0, 8, 0, 0],
            "es_trade_orderflow_return_ticks_30": [0, 0, 0, 0, 0, 8, 0, 0],
            "es_trade_orderflow_return_ticks_60": [0, 0, 0, 0, 0, 8, 0, 0],
            "mes_trade_orderflow_imbalance_15": [0, 0, 0, 0, 0, 0.08, 0, 0],
            "mes_trade_orderflow_imbalance_30": [0, 0, 0, 0, 0, 0.08, 0, 0],
            "mes_trade_orderflow_imbalance_60": [0, 0, 0, 0, 0, 0.08, 0, 0],
            "mes_trade_orderflow_large10_imbalance_15": [0] * len(timestamps),
            "mes_trade_orderflow_large10_imbalance_30": [0] * len(timestamps),
            "mes_trade_orderflow_large10_imbalance_60": [0] * len(timestamps),
            "mes_trade_orderflow_large20_imbalance_15": [0] * len(timestamps),
            "mes_trade_orderflow_large20_imbalance_30": [0] * len(timestamps),
            "mes_trade_orderflow_large20_imbalance_60": [0] * len(timestamps),
        }
    )
    cfg = {
        "strategy": {
            "entry": {
                "module": "es_mes_aligned_flow_continuation",
                "params": {
                    "signal_time": "10:30:00",
                    "bar_interval_minutes": 1,
                    "return_window_minutes": 30,
                    "flow_window_minutes": 30,
                    "mes_flow_mode": "signed",
                    "min_es_return_ticks": 4,
                    "min_mes_flow_imbalance": 0.05,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:32:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:32:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["signal_close_timestamp"]) == "2024-01-03 10:30:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 10:30:00-05:00"


def _bar(
    timestamp: str,
    *,
    es_return: float,
    mes_flow: float,
    nq_return: float | None = None,
    flow_column: str = "mes_trade_orderflow_imbalance_30",
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    bar = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "open": 100.0,
        "high": 101.0,
        "low": 99.5,
        "close": 100.5,
        "es_trade_orderflow_return_ticks_30": es_return,
        "nq_trade_orderflow_return_ticks_30": es_return if nq_return is None else nq_return,
        "mes_trade_orderflow_imbalance_30": 0.0,
        "mes_trade_orderflow_large10_imbalance_30": 0.0,
    }
    bar[flow_column] = mes_flow
    return pd.Series(bar)
