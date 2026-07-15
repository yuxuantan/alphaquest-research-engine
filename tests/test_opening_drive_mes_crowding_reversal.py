import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.opening_drive_mes_crowding_reversal import (
    OpeningDriveMesCrowdingReversalEntry,
)


def test_opening_drive_mes_crowding_reversal_shorts_failed_up_drive_extension():
    entry = OpeningDriveMesCrowdingReversalEntry(
        {
            "opening_drive_minutes": 3,
            "signal_start_time": "09:33:00",
            "last_entry_time": "10:00:00",
            "participation_window": 15,
            "share_mode": "notional",
            "share_rank_min": 0.55,
            "min_opening_drive_ticks": 3,
            "min_extension_ticks": 1,
            "tick_size": 0.25,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", open=100.0, high=100.4, low=99.9, close=100.25),
        _bar("2024-01-03 09:31:00", open=100.25, high=100.7, low=100.2, close=100.5),
        _bar("2024-01-03 09:32:00", open=100.5, high=101.0, low=100.4, close=101.0),
    ]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:33:00",
            open=101.0,
            high=101.5,
            low=100.6,
            close=100.9,
            mes_participation_share_15=0.08,
            mes_participation_share_15_rank252=0.72,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.breakout_level == 101.0
    assert signal.sweep_high == 101.5
    assert signal.report_fields["opening_drive_direction"] == "up"
    assert signal.report_fields["share_rank"] == 0.72


def test_opening_drive_mes_crowding_reversal_longs_failed_down_drive_extension():
    entry = OpeningDriveMesCrowdingReversalEntry(
        {
            "opening_drive_minutes": 3,
            "signal_start_time": "09:33:00",
            "last_entry_time": "10:00:00",
            "participation_window": 30,
            "share_mode": "trade",
            "share_rank_min": 0.60,
            "min_opening_drive_ticks": 3,
            "min_extension_ticks": 1,
            "tick_size": 0.25,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", open=100.0, high=100.1, low=99.6, close=99.75),
        _bar("2024-01-03 09:31:00", open=99.75, high=99.8, low=99.2, close=99.5),
        _bar("2024-01-03 09:32:00", open=99.5, high=99.6, low=99.0, close=99.0),
    ]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:33:00",
            open=99.0,
            high=99.4,
            low=98.5,
            close=99.1,
            mes_trade_share_30=0.22,
            mes_trade_share_30_rank252=0.81,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.breakout_level == 99.0
    assert signal.sweep_low == 98.5
    assert signal.report_fields["opening_drive_direction"] == "down"
    assert signal.report_fields["share_mode"] == "trade"


def test_opening_drive_mes_crowding_reversal_rejects_low_mes_rank():
    entry = OpeningDriveMesCrowdingReversalEntry(
        {
            "opening_drive_minutes": 3,
            "signal_start_time": "09:33:00",
            "last_entry_time": "10:00:00",
            "share_rank_min": 0.70,
            "min_opening_drive_ticks": 3,
            "min_extension_ticks": 1,
        }
    )

    for bar in [
        _bar("2024-01-03 09:30:00", open=100.0, high=100.4, low=99.9, close=100.25),
        _bar("2024-01-03 09:31:00", open=100.25, high=100.7, low=100.2, close=100.5),
        _bar("2024-01-03 09:32:00", open=100.5, high=101.0, low=100.4, close=101.0),
    ]:
        entry.on_bar_close(bar)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:33:00",
            open=101.0,
            high=101.5,
            low=100.6,
            close=100.9,
            mes_participation_share_15=0.08,
            mes_participation_share_15_rank252=0.65,
        )
    )

    assert signal is None


def test_engine_enters_opening_drive_mes_crowding_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=6, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 100.25, 100.5, 101.0, 100.75, 100.7],
            "high": [100.4, 100.7, 101.0, 101.5, 100.9, 100.8],
            "low": [99.9, 100.2, 100.4, 100.6, 99.0, 100.3],
            "close": [100.25, 100.5, 101.0, 100.9, 99.2, 100.6],
            "volume": [1000] * len(timestamps),
            "mes_participation_share_15": [0.0, 0.0, 0.0, 0.08, 0.0, 0.0],
            "mes_participation_share_15_rank252": [0.0, 0.0, 0.0, 0.72, 0.0, 0.0],
            "mes_participation_share_30": [0.0] * len(timestamps),
            "mes_participation_share_30_rank252": [0.0] * len(timestamps),
            "mes_participation_share_60": [0.0] * len(timestamps),
            "mes_participation_share_60_rank252": [0.0] * len(timestamps),
            "mes_trade_share_15": [0.0] * len(timestamps),
            "mes_trade_share_15_rank252": [0.0] * len(timestamps),
            "mes_trade_share_30": [0.0] * len(timestamps),
            "mes_trade_share_30_rank252": [0.0] * len(timestamps),
            "mes_trade_share_60": [0.0] * len(timestamps),
            "mes_trade_share_60_rank252": [0.0] * len(timestamps),
        }
    )
    cfg = {
        "strategy": {
            "entry": {
                "module": "opening_drive_mes_crowding_reversal",
                "params": {
                    "opening_drive_minutes": 3,
                    "signal_start_time": "09:33:00",
                    "last_entry_time": "09:35:00",
                    "participation_window": 15,
                    "share_mode": "notional",
                    "share_rank_min": 0.55,
                    "min_opening_drive_ticks": 3,
                    "min_extension_ticks": 1,
                    "tick_size": 0.25,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:35:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:35:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["signal_close_timestamp"]) == "2024-01-03 09:34:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:34:00-05:00"
    assert trade["direction"] == "short"


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
        "mes_participation_share_15": 0.0,
        "mes_participation_share_15_rank252": 0.0,
        "mes_participation_share_30": 0.0,
        "mes_participation_share_30_rank252": 0.0,
        "mes_trade_share_15": 0.0,
        "mes_trade_share_15_rank252": 0.0,
        "mes_trade_share_30": 0.0,
        "mes_trade_share_30_rank252": 0.0,
    }
    row.update(overrides)
    return pd.Series(row)
