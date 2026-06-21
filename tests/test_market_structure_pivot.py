import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.market_structure_filtered_entry import MarketStructureFilteredEntry
from propstack.strategy_modules.entry.market_structure_pivot_continuation import (
    MarketStructurePivotContinuationEntry,
)
from propstack.strategy_modules.entry.market_structure_pivots import MultiTimeframePivotStructure


def test_market_structure_pivot_emits_after_four_confirmed_pivots_only():
    entry = MarketStructurePivotContinuationEntry(
        {
            "signal_time": "10:15:00",
            "bar_interval_minutes": 5,
            "timeframes_minutes": [5],
            "min_aligned_timeframes": 1,
            "pivot_left_bars": 1,
            "pivot_right_bars": 1,
            "min_pivot_move_ticks": 0,
            "tick_size": 0.25,
        }
    )
    bars = _pivot_bars()
    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(bars[-1])

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["market_structure_5m_pattern"] == "HH_HL"
    assert signal.report_fields["market_structure_5m_pivot1_type"] == "high"
    assert str(signal.report_fields["signal_close_timestamp"]) == "2024-01-03 10:15:00"


def test_market_structure_pivot_rejects_before_right_side_confirmation():
    entry = MarketStructurePivotContinuationEntry(
        {
            "signal_time": "10:10:00",
            "bar_interval_minutes": 5,
            "timeframes_minutes": [5],
            "min_aligned_timeframes": 1,
            "pivot_left_bars": 1,
            "pivot_right_bars": 1,
            "min_pivot_move_ticks": 0,
        }
    )
    for bar in _pivot_bars()[:-1]:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_market_structure_pivot_engine_enters_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=10, freq="5min", tz="America/New_York")
    bars = _pivot_ohlc_rows(timestamps)
    bars.append({"open": 101.25, "high": 101.75, "low": 100.75, "close": 101.25})
    df = _df_from_rows(timestamps, bars)
    cfg = {
        "timeframe": "5m",
        "strategy": {
            "entry": {
                "module": "market_structure_pivot_continuation",
                "params": {
                    "signal_time": "10:15:00",
                    "flatten_time": "10:20:00",
                    "bar_interval_minutes": 5,
                    "timeframes_minutes": [5],
                    "min_aligned_timeframes": 1,
                    "pivot_left_bars": 1,
                    "pivot_right_bars": 1,
                    "min_pivot_move_ticks": 0,
                    "tick_size": 0.25,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.0025, "round_to_tick": True}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:20:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:20:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["signal_close_timestamp"]) == "2024-01-03 10:15:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 10:15:00-05:00"


def test_market_structure_pivot_first_bias_window_signals_once():
    entry = MarketStructurePivotContinuationEntry(
        {
            "signal_mode": "first_bias_in_window",
            "start_time": "10:00:00",
            "end_time": "10:30:00",
            "bar_interval_minutes": 5,
            "timeframes_minutes": [5],
            "min_aligned_timeframes": 1,
            "pivot_left_bars": 1,
            "pivot_right_bars": 1,
            "min_pivot_move_ticks": 0,
        }
    )

    signals = [entry.on_bar_close(bar) for bar in _pivot_bars()]

    emitted = [signal for signal in signals if signal is not None]
    assert len(emitted) == 1
    assert emitted[0].direction == "long"
    assert emitted[0].report_fields["signal_mode"] == "first_bias_in_window"


def test_market_structure_filtered_entry_passes_matching_base_signal():
    entry = MarketStructureFilteredEntry(
        {
            "bar_interval_minutes": 5,
            "timeframes_minutes": [5],
            "min_aligned_timeframes": 1,
            "pivot_left_bars": 1,
            "pivot_right_bars": 1,
            "min_pivot_move_ticks": 0,
            "base_module": "mes_participation_crowding",
            "base_params": {
                "entry_time": "10:15:00",
                "bar_interval_minutes": 5,
                "lookback_minutes": 30,
                "share_mode": "notional",
                "direction": "long",
                "share_rank_min": 0.5,
                "min_abs_return_ticks": 4,
            },
        }
    )

    signal = None
    for bar in _pivot_bars():
        enriched = bar.copy()
        enriched["mes_participation_share_30"] = 0.1
        enriched["mes_participation_share_30_rank252"] = 0.8
        enriched["es_return_ticks_30"] = -6.0
        signal = entry.on_bar_close(enriched)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["market_structure_filter_direction"] == "long"


def test_market_structure_filtered_entry_rejects_opposite_base_signal():
    entry = MarketStructureFilteredEntry(
        {
            "bar_interval_minutes": 5,
            "timeframes_minutes": [5],
            "min_aligned_timeframes": 1,
            "pivot_left_bars": 1,
            "pivot_right_bars": 1,
            "min_pivot_move_ticks": 0,
            "base_module": "mes_participation_crowding",
            "base_params": {
                "entry_time": "10:15:00",
                "bar_interval_minutes": 5,
                "lookback_minutes": 30,
                "share_mode": "notional",
                "direction": "short",
                "share_rank_min": 0.5,
                "min_abs_return_ticks": 4,
            },
        }
    )

    signal = None
    for bar in _pivot_bars():
        enriched = bar.copy()
        enriched["mes_participation_share_30"] = 0.1
        enriched["mes_participation_share_30_rank252"] = 0.8
        enriched["es_return_ticks_30"] = 6.0
        signal = entry.on_bar_close(enriched)

    assert signal is None


def test_market_structure_pivot_can_carry_completed_pattern_across_sessions():
    base_params = {
        "timeframes_minutes": [5],
        "bar_interval_minutes": 5,
        "rth_start": pd.Timestamp("2024-01-03 09:30:00").time(),
        "tick_size": 0.25,
        "pivot_left_bars": 1,
        "pivot_right_bars": 1,
        "min_pivot_move_ticks": 0,
        "min_aligned_timeframes": 1,
    }
    reset_structure = MultiTimeframePivotStructure(**base_params)
    carry_structure = MultiTimeframePivotStructure(**base_params, carry_pivots_across_sessions=True)

    for bar in _pivot_bars():
        reset_structure.update(bar)
        carry_structure.update(bar)

    next_day = _pivot_bars()[0].copy()
    next_day["timestamp"] = pd.Timestamp("2024-01-04 09:30:00")
    next_day["session_date"] = pd.Timestamp("2024-01-04").date()
    reset_structure.update(next_day)
    carry_structure.update(next_day)

    assert reset_structure.bias()["direction"] is None
    assert carry_structure.bias()["direction"] == "long"


def _pivot_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=9, freq="5min")
    return [
        pd.Series(
            {
                "timestamp": ts,
                "session_date": ts.date(),
                "session_label": "RTH",
                "is_rth": True,
                "volume": 1000,
                **row,
            }
        )
        for ts, row in zip(timestamps, _pivot_ohlc_rows(timestamps[:9]))
    ]


def _pivot_ohlc_rows(timestamps) -> list[dict]:
    return [
        {"open": 100.0, "high": 100.5, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.5},
        {"open": 101.5, "high": 101.0, "low": 99.5, "close": 100.0},
        {"open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0},
        {"open": 99.0, "high": 100.0, "low": 99.0, "close": 99.5},
        {"open": 99.5, "high": 103.0, "low": 100.0, "close": 102.0},
        {"open": 102.0, "high": 102.0, "low": 99.5, "close": 100.5},
        {"open": 100.5, "high": 101.0, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.0},
    ]


def _df_from_rows(timestamps, rows) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [ts.date() for ts in timestamps],
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "volume": [1000] * len(timestamps),
            **{key: [row[key] for row in rows] for key in ["open", "high", "low", "close"]},
        }
    )
