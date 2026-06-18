import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.pdh_pdl_orderflow_breakout_continuation import (
    PdhPdlOrderflowBreakoutContinuationEntry,
)
from propstack.strategy_modules.sl.prior_level_retest_boundary import PriorLevelRetestBoundaryStop


def test_prior_high_breakout_requires_aligned_aggregate_orderflow():
    entry = PdhPdlOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "fresh_close_break",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "close_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": False,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35:00",
            high=101.0,
            low=100.0,
            close=100.5,
            signed_volume=350,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["orderflow_mode"] == "signed"
    assert signal.report_fields["orderflow_imbalance"] == 0.35


def test_prior_high_breakout_rejects_opposing_orderflow():
    entry = PdhPdlOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "fresh_close_break",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "close_buffer_ticks": 1,
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": False,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:35:00",
            high=101.0,
            low=100.0,
            close=100.5,
            signed_volume=-350,
            volume=1000,
        )
    )

    assert signal is None


def test_prior_high_retest_hold_can_require_absorbed_selling_flow():
    entry = PdhPdlOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "break_retest_hold",
            "start_time": "09:30:00",
            "end_time": "10:15:00",
            "close_buffer_ticks": 0,
            "retest_window_bars": 3,
            "retest_tolerance_ticks": 2,
            "flow_confirmation": "absorbed",
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": False,
        }
    )

    assert entry.on_bar_close(
        _indexed_bar(
            1,
            "2024-01-03 09:35:00",
            high=101.0,
            low=100.2,
            close=100.6,
            signed_volume=400,
            volume=1000,
        )
    ) is None
    weak = entry.on_bar_close(
        _indexed_bar(
            2,
            "2024-01-03 09:40:00",
            high=100.8,
            low=100.0,
            close=100.3,
            signed_volume=-100,
            volume=1000,
        )
    )
    assert weak is None

    entry = PdhPdlOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "break_retest_hold",
            "start_time": "09:30:00",
            "end_time": "10:15:00",
            "close_buffer_ticks": 0,
            "retest_window_bars": 3,
            "retest_tolerance_ticks": 2,
            "flow_confirmation": "absorbed",
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": False,
        }
    )
    entry.on_bar_close(
        _indexed_bar(
            1,
            "2024-01-03 09:35:00",
            high=101.0,
            low=100.2,
            close=100.6,
            signed_volume=400,
            volume=1000,
        )
    )
    signal = entry.on_bar_close(
        _indexed_bar(
            2,
            "2024-01-03 09:40:00",
            high=100.8,
            low=100.0,
            close=100.3,
            signed_volume=-350,
            volume=1000,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_high_retest"
    assert signal.report_fields["flow_confirmation"] == "absorbed"
    assert signal.report_fields["orderflow_imbalance"] == -0.35


def test_prior_level_retest_can_allow_non_fresh_level_when_configured():
    entry = PdhPdlOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "break_retest_hold",
            "start_time": "09:30:00",
            "end_time": "10:15:00",
            "close_buffer_ticks": 0,
            "retest_window_bars": 3,
            "retest_tolerance_ticks": 2,
            "require_fresh_level": False,
            "flow_confirmation": "aligned",
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": False,
        }
    )

    breakout = _indexed_bar(
        1,
        "2024-01-03 09:35:00",
        high=101.0,
        low=100.2,
        close=100.6,
        signed_volume=400,
        volume=1000,
    )
    breakout["prev_rth_high_fresh"] = False
    retest = _indexed_bar(
        2,
        "2024-01-03 09:40:00",
        high=100.8,
        low=100.0,
        close=100.3,
        signed_volume=350,
        volume=1000,
    )
    retest["prev_rth_high_fresh"] = False

    assert entry.on_bar_close(breakout) is None
    signal = entry.on_bar_close(retest)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["orderflow_imbalance"] == 0.35


def test_prior_level_retest_boundary_stop_uses_flipped_level():
    entry = PdhPdlOrderflowBreakoutContinuationEntry(
        {
            "setup_mode": "break_retest_hold",
            "start_time": "09:30:00",
            "end_time": "10:15:00",
            "close_buffer_ticks": 0,
            "retest_window_bars": 3,
            "retest_tolerance_ticks": 2,
            "flow_confirmation": "aligned",
            "min_orderflow_imbalance": 0.20,
            "orderflow_mode": "signed",
            "tick_size": 0.25,
            "allow_long": False,
            "allow_short": True,
        }
    )
    entry.on_bar_close(
        _indexed_bar(
            1,
            "2024-01-03 09:35:00",
            high=97.8,
            low=97.0,
            close=97.7,
            signed_volume=-400,
            volume=1000,
        )
    )
    signal = entry.on_bar_close(
        _indexed_bar(
            2,
            "2024-01-03 09:40:00",
            high=98.2,
            low=97.4,
            close=97.8,
            signed_volume=-350,
            volume=1000,
        )
    )

    assert signal is not None
    stop = PriorLevelRetestBoundaryStop({"stop_offset_ticks": 3, "max_stop_points": 10}).price(
        signal,
        "short",
        0.25,
        entry_price=97.75,
    )
    assert stop == 98.75


def test_engine_enters_prior_level_orderflow_breakout_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:34:00", periods=4, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [99.8, 100.0, 100.75, 101.0],
            "high": [100.0, 101.0, 101.25, 101.25],
            "low": [99.5, 100.0, 100.5, 100.75],
            "close": [99.9, 100.5, 101.0, 101.0],
            "volume": [1000, 1000, 1000, 1000],
            "signed_volume": [0, 400, 0, 0],
            "large10_signed_volume": [0, 0, 0, 0],
            "large10_volume": [0, 0, 0, 0],
            "large20_signed_volume": [0, 0, 0, 0],
            "large20_volume": [0, 0, 0, 0],
            "prev_rth_high": [100.0] * len(timestamps),
            "prev_rth_low": [98.0] * len(timestamps),
            "prev_rth_high_fresh": [True] * len(timestamps),
            "prev_rth_low_fresh": [True] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_prior_level_orderflow_breakout",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "pdh_pdl_orderflow_breakout_continuation",
                "params": {
                    "setup_mode": "fresh_close_break",
                    "start_time": "09:30:00",
                    "end_time": "10:00:00",
                    "close_buffer_ticks": 1,
                    "min_orderflow_imbalance": 0.20,
                    "orderflow_mode": "signed",
                    "tick_size": 0.25,
                    "bar_interval_minutes": 1,
                    "max_trades_per_day": 1,
                    "allow_long": True,
                    "allow_short": False,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:38:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:38:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["breakout_timestamp"]) == "2024-01-03 09:35:00-05:00"
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 09:36:00-05:00"


def test_engine_enters_prior_level_retest_orderflow_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:34:00", periods=6, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [99.8, 100.0, 100.75, 100.3, 100.5, 100.7],
            "high": [100.0, 101.0, 101.25, 100.6, 100.8, 100.9],
            "low": [99.5, 100.2, 100.6, 100.0, 100.4, 100.6],
            "close": [99.9, 100.6, 101.0, 100.3, 100.7, 100.8],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000],
            "signed_volume": [0, 400, 0, -350, 0, 0],
            "large10_signed_volume": [0, 0, 0, 0, 0, 0],
            "large10_volume": [0, 0, 0, 0, 0, 0],
            "large20_signed_volume": [0, 0, 0, 0, 0, 0],
            "large20_volume": [0, 0, 0, 0, 0, 0],
            "prev_rth_high": [100.0] * len(timestamps),
            "prev_rth_low": [98.0] * len(timestamps),
            "prev_rth_high_fresh": [True] * len(timestamps),
            "prev_rth_low_fresh": [True] * len(timestamps),
        }
    )
    cfg = {
        "strategy_name": "test_prior_level_retest_orderflow",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "pdh_pdl_orderflow_breakout_continuation",
                "params": {
                    "setup_mode": "break_retest_hold",
                    "start_time": "09:30:00",
                    "end_time": "10:00:00",
                    "close_buffer_ticks": 0,
                    "retest_window_bars": 3,
                    "retest_tolerance_ticks": 2,
                    "flow_confirmation": "absorbed",
                    "min_orderflow_imbalance": 0.20,
                    "orderflow_mode": "signed",
                    "tick_size": 0.25,
                    "bar_interval_minutes": 1,
                    "max_trades_per_day": 1,
                    "allow_long": True,
                    "allow_short": False,
                },
            },
            "sl": {"module": "prior_level_retest_boundary", "params": {"stop_offset_ticks": 2, "max_stop_points": 10}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:40:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "09:40:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert str(trade["breakout_timestamp"]) == "2024-01-03 09:35:00-05:00"
    assert str(trade["continuation_timestamp"]) == "2024-01-03 09:37:00-05:00"
    assert str(trade["entry_timestamp"]) == "2024-01-03 09:38:00-05:00"


def _bar(
    timestamp: str,
    *,
    high: float,
    low: float,
    close: float,
    signed_volume: float,
    volume: float,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "signed_volume": signed_volume,
            "large10_signed_volume": 0,
            "large10_volume": 0,
            "large20_signed_volume": 0,
            "large20_volume": 0,
            "prev_rth_high": 100.0,
            "prev_rth_low": 98.0,
            "prev_rth_high_fresh": True,
            "prev_rth_low_fresh": True,
        }
    )


def _indexed_bar(index: int, *args, **kwargs) -> pd.Series:
    bar = _bar(*args, **kwargs)
    bar.name = index
    return bar
