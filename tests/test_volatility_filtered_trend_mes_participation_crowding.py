from pathlib import Path

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.volatility_filtered_trend_mes_participation_crowding import (
    VolatilityFilteredTrendMesParticipationCrowdingEntry,
)


def test_volatility_filtered_trend_mes_participation_passes_when_gate_is_below_threshold(tmp_path):
    feature_csv = _feature_csv(tmp_path, "2024-01-03", vol20_rank_252=0.50)
    entry = VolatilityFilteredTrendMesParticipationCrowdingEntry(
        _params(feature_csv, volatility_gate_column="vol20_rank_252", volatility_gate_max=0.95)
    )
    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            close=101.0,
            mes_trade_share_15=0.20,
            mes_trade_share_15_rank252=0.75,
            es_return_ticks_15=-5.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["volatility_gate_column"] == "vol20_rank_252"
    assert signal.report_fields["volatility_gate_value"] == 0.50
    assert signal.report_fields["volatility_gate_max"] == 0.95
    assert signal.report_fields["volatility_filter_result"] == "passed"
    assert signal.report_fields["trend_return_ticks"] == 8.0


def test_volatility_filtered_trend_mes_participation_rejects_extreme_volatility(tmp_path):
    feature_csv = _feature_csv(tmp_path, "2024-01-03", vol20_rank_252=0.99)
    entry = VolatilityFilteredTrendMesParticipationCrowdingEntry(
        _params(feature_csv, volatility_gate_column="vol20_rank_252", volatility_gate_max=0.95)
    )
    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            close=101.0,
            mes_trade_share_15=0.20,
            mes_trade_share_15_rank252=0.75,
            es_return_ticks_15=-5.0,
        )
    )

    assert signal is None


def test_engine_enters_volatility_filtered_mes_participation_on_next_bar_open(tmp_path):
    feature_csv = _feature_csv(tmp_path, "2024-01-03", range10_rank_252=0.40)
    timestamps = pd.to_datetime(
        [
            "2024-01-03 09:44:00",
            "2024-01-03 10:14:00",
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
            "open": [100.0, 102.0, 101.0, 101.25],
            "high": [100.25, 102.25, 101.25, 101.50],
            "low": [99.75, 101.75, 100.75, 101.00],
            "close": [100.0, 102.0, 101.0, 101.25],
            "volume": [1000] * len(timestamps),
            "mes_participation_share_15": [0.0] * len(timestamps),
            "mes_participation_share_15_rank252": [0.0] * len(timestamps),
            "mes_trade_share_15": [0.0, 0.0, 0.20, 0.0],
            "mes_trade_share_15_rank252": [0.0, 0.0, 0.75, 0.0],
            "es_return_ticks_15": [0.0, 0.0, -5.0, 0.0],
        }
    )
    cfg = {
        "strategy": {
            "entry": {
                "module": "volatility_filtered_trend_mes_participation_crowding",
                "params": {
                    **_params(feature_csv),
                    "volatility_gate_column": "range10_rank_252",
                    "volatility_gate_max": 0.95,
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
    trade = result["trades"].iloc[0]
    assert str(trade["signal_close_timestamp"]) == "2024-01-03 10:30:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 10:30:00-05:00"
    assert trade["volatility_gate_column"] == "range10_rank_252"
    assert trade["volatility_gate_value"] == 0.40


def _params(feature_csv: Path, **overrides) -> dict:
    params = {
        "setup_mode": "exclude_extreme_vol20_trade_morning_1030",
        "entry_time": "10:30:00",
        "flatten_time": "12:00:00",
        "bar_interval_minutes": 1,
        "lookback_minutes": 15,
        "trend_lookback_minutes": 30,
        "rank_window": 252,
        "share_mode": "trade",
        "direction": "both",
        "share_rank_min": 0.55,
        "min_abs_return_ticks": 4,
        "min_trend_return_ticks": 6,
        "max_trades_per_day": 1,
        "stop_pct": 0.0025,
        "target_r_multiple": 1.5,
        "tick_size": 0.25,
        "feature_csv": str(feature_csv),
        "volatility_gate_column": "vol20_rank_252",
        "volatility_gate_max": 0.95,
    }
    params.update(overrides)
    return params


def _feature_csv(tmp_path: Path, session_date: str, **overrides) -> Path:
    row = {
        "session_date": session_date,
        "vol20_rank_252": 0.50,
        "range10_rank_252": 0.50,
        "absret5_rank_252": 0.50,
        "downside20_rank_252": 0.50,
        "vol5_over_vol20": 1.00,
    }
    row.update(overrides)
    path = tmp_path / "features.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def _bar(timestamp: str, **overrides) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    row = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "open": overrides.get("close", 100.0),
        "high": overrides.get("close", 100.0) + 0.25,
        "low": overrides.get("close", 100.0) - 0.25,
        "close": overrides.get("close", 100.0),
        "mes_participation_share_15": 0.0,
        "mes_participation_share_15_rank252": 0.0,
        "mes_trade_share_15": 0.0,
        "mes_trade_share_15_rank252": 0.0,
        "es_return_ticks_15": 0.0,
    }
    row.update(overrides)
    return pd.Series(row)
