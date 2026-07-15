import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.trend_filtered_mes_participation_crowding import (
    TrendFilteredMesParticipationCrowdingEntry,
)


def test_trend_filtered_mes_participation_emits_long_pullback_with_prior_uptrend():
    entry = TrendFilteredMesParticipationCrowdingEntry(
        {
            "entry_time": "10:30:00",
            "lookback_minutes": 15,
            "trend_lookback_minutes": 30,
            "share_mode": "notional",
            "direction": "both",
            "share_rank_min": 0.55,
            "min_abs_return_ticks": 4,
            "min_trend_return_ticks": 6,
            "tick_size": 0.25,
        }
    )
    assert entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0)) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            close=101.0,
            mes_participation_share_15=0.08,
            mes_participation_share_15_rank252=0.70,
            es_return_ticks_15=-5.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["trend_return_ticks"] == 8.0
    assert str(signal.report_fields["trend_end_timestamp"]) == "2024-01-03 10:15:00"


def test_trend_filtered_mes_participation_rejects_pullback_against_prior_trend():
    entry = TrendFilteredMesParticipationCrowdingEntry(
        {
            "entry_time": "10:30:00",
            "lookback_minutes": 15,
            "trend_lookback_minutes": 30,
            "share_mode": "notional",
            "direction": "long",
            "share_rank_min": 0.55,
            "min_abs_return_ticks": 4,
            "min_trend_return_ticks": 6,
        }
    )
    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=102.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=100.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            close=99.0,
            mes_participation_share_15=0.08,
            mes_participation_share_15_rank252=0.80,
            es_return_ticks_15=-5.0,
        )
    )

    assert signal is None


def test_trend_filtered_mes_participation_emits_short_pullback_with_prior_downtrend():
    entry = TrendFilteredMesParticipationCrowdingEntry(
        {
            "entry_time": "10:30:00",
            "lookback_minutes": 15,
            "trend_lookback_minutes": 30,
            "share_mode": "trade",
            "direction": "both",
            "share_rank_min": 0.55,
            "min_abs_return_ticks": 4,
            "min_trend_return_ticks": 6,
        }
    )
    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=102.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=100.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            close=101.0,
            mes_trade_share_15=0.20,
            mes_trade_share_15_rank252=0.75,
            es_return_ticks_15=5.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["trend_return_ticks"] == -8.0


def test_engine_enters_trend_filtered_mes_participation_on_next_bar_open():
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
            "mes_participation_share_15": [0.0, 0.0, 0.08, 0.0],
            "mes_participation_share_15_rank252": [0.0, 0.0, 0.70, 0.0],
            "mes_trade_share_15": [0.0] * len(timestamps),
            "mes_trade_share_15_rank252": [0.0] * len(timestamps),
            "es_return_ticks_15": [0.0, 0.0, -5.0, 0.0],
        }
    )
    cfg = {
        "strategy": {
            "entry": {
                "module": "trend_filtered_mes_participation_crowding",
                "params": {
                    "entry_time": "10:30:00",
                    "lookback_minutes": 15,
                    "trend_lookback_minutes": 30,
                    "share_mode": "notional",
                    "direction": "both",
                    "share_rank_min": 0.55,
                    "min_abs_return_ticks": 4,
                    "min_trend_return_ticks": 6,
                    "tick_size": 0.25,
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
