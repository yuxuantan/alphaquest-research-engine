import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry.footprint_absorption_initiation import (
    FootprintAbsorptionInitiationEntry,
)


def _entry(**overrides):
    params = {
        "setup_mode": "prior_low_long",
        "start_time": "09:30:00",
        "end_time": "10:30:00",
        "flatten_time": "15:30:00",
        "tick_size": 0.25,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_absorption_volume": 20,
        "opening_range_minutes": 3,
        "lookback_bars": 3,
        "round_number_interval": 25.0,
        "max_trades_per_day": 1,
    }
    params.update(overrides)
    return FootprintAbsorptionInitiationEntry(params)


def test_prior_low_sell_absorption_reclaim_emits_long():
    entry = _entry(setup_mode="prior_low_long", allow_long=True, allow_short=False)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=100.0,
            high=100.75,
            low=99.5,
            close=100.25,
            prev_rth_low=100.0,
            footprint_absorption_long=1,
            footprint_max_sell_imbalance_volume=50,
            footprint_highest_sell_imbalance_price=100.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 100.0
    assert signal.sweep_low == 99.5
    assert signal.report_fields["footprint_absorption_volume"] == 50


def test_prior_high_buy_absorption_reject_emits_short():
    entry = _entry(setup_mode="prior_high_short", allow_long=False, allow_short=True)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=100.25,
            high=100.75,
            low=99.5,
            close=99.75,
            prev_rth_high=100.0,
            footprint_absorption_short=1,
            footprint_max_buy_imbalance_volume=60,
            footprint_lowest_buy_imbalance_price=100.25,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 100.0
    assert signal.sweep_high == 100.75
    assert signal.report_fields["footprint_absorption_volume"] == 60


def test_rolling_range_uses_only_prior_bars_for_swept_level():
    entry = _entry(setup_mode="rolling_range_two_sided", allow_long=True, allow_short=True)
    for bar in [
        _bar("2024-01-03 09:57:00", high=101.0, low=100.0, close=100.5),
        _bar("2024-01-03 09:58:00", high=100.75, low=99.75, close=100.25),
        _bar("2024-01-03 09:59:00", high=100.5, low=99.5, close=100.0),
    ]:
        assert entry.on_bar_close(bar) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=99.25,
            high=100.75,
            low=99.0,
            close=99.5,
            footprint_absorption_long=1,
            footprint_max_sell_imbalance_volume=50,
            footprint_highest_sell_imbalance_price=99.25,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 99.5


def test_absorption_signal_requires_absorbed_volume_above_threshold():
    entry = _entry(setup_mode="prior_low_long", min_absorption_volume=100)

    assert (
        entry.on_bar_close(
            _bar(
                "2024-01-03 10:00:00",
                open_=100.0,
                high=100.75,
                low=99.5,
                close=100.25,
                prev_rth_low=100.0,
                footprint_absorption_long=1,
                footprint_max_sell_imbalance_volume=50,
                footprint_highest_sell_imbalance_price=100.0,
            )
        )
        is None
    )


def test_prior_extreme_two_sided_can_emit_short_from_prior_high():
    entry = _entry(setup_mode="prior_extreme_two_sided", allow_long=True, allow_short=True)

    signal = entry.on_bar_close(
            _bar(
                "2024-01-03 10:00:00",
                open_=101.25,
                high=101.5,
                low=100.0,
            close=100.75,
            prev_rth_high=101.0,
            footprint_absorption_short=1,
            footprint_max_buy_imbalance_volume=70,
            footprint_lowest_buy_imbalance_price=101.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 101.0
    assert signal.level_type == "prior_high_footprint_absorption"


def test_session_open_two_sided_uses_first_completed_bar_open_as_level():
    entry = _entry(setup_mode="session_open_two_sided", allow_long=True, allow_short=True)
    assert entry.on_bar_close(_bar("2024-01-03 09:30:00", open_=100.0, high=100.5, low=99.5, close=100.25)) is None

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=99.5,
            high=100.75,
            low=99.5,
            close=100.25,
            footprint_absorption_long=1,
            footprint_max_sell_imbalance_volume=55,
            footprint_highest_sell_imbalance_price=100.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 100.0
    assert signal.level_type == "session_open_footprint_absorption"


def test_engine_enters_footprint_absorption_signal_on_next_bar_open():
    timestamps = pd.date_range("2024-01-03 09:59:00", periods=5, freq="1min", tz="America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * len(timestamps),
            "session_date": [timestamps[0].date()] * len(timestamps),
            "session_label": ["RTH"] * len(timestamps),
            "is_rth": [True] * len(timestamps),
            "open": [100.0, 100.0, 100.5, 100.6, 100.7],
            "high": [100.25, 100.75, 100.75, 100.8, 100.9],
            "low": [99.75, 99.5, 100.25, 100.5, 100.6],
            "close": [100.0, 100.25, 100.5, 100.7, 100.8],
            "volume": [1000] * len(timestamps),
            "prev_rth_high": [101.0] * len(timestamps),
            "prev_rth_low": [100.0] * len(timestamps),
            "footprint_absorption_long": [0, 1, 0, 0, 0],
            "footprint_absorption_short": [0, 0, 0, 0, 0],
            "footprint_max_sell_imbalance_volume": [0, 50, 0, 0, 0],
            "footprint_max_buy_imbalance_volume": [0, 0, 0, 0, 0],
            "footprint_highest_sell_imbalance_price": [0, 100.0, 0, 0, 0],
            "footprint_lowest_buy_imbalance_price": [0, 0, 0, 0, 0],
        }
    )
    cfg = {
        "strategy_name": "test_footprint_absorption_initiation",
        "timeframe": "1m",
        "strategy": {
            "entry": {
                "module": "footprint_absorption_initiation",
                "params": {
                    "setup_mode": "prior_low_long",
                    "start_time": "10:00:00",
                    "end_time": "10:30:00",
                    "tick_size": 0.25,
                    "min_probe_ticks": 1,
                    "confirmation_ticks": 0,
                    "min_absorption_volume": 20,
                    "allow_long": True,
                    "allow_short": False,
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:04:00",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:04:00",
            "max_trades_per_day": 1,
        },
    }

    result = BacktestEngine(cfg).run(df)

    assert result["diagnostics"]["signals_generated"] == 1
    assert len(result["trades"]) == 1
    assert str(result["trades"].iloc[0]["entry_timestamp"]) == "2024-01-03 10:01:00-05:00"


def _bar(
    timestamp: str,
    *,
    high: float,
    low: float,
    close: float,
    open_: float | None = None,
    prev_rth_low: float = 99.0,
    prev_rth_high: float = 101.0,
    footprint_absorption_long: float = 0.0,
    footprint_absorption_short: float = 0.0,
    footprint_max_sell_imbalance_volume: float = 0.0,
    footprint_max_buy_imbalance_volume: float = 0.0,
    footprint_highest_sell_imbalance_price: float = 0.0,
    footprint_lowest_buy_imbalance_price: float = 0.0,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "session_label": "RTH",
            "is_rth": True,
            "open": close if open_ is None else open_,
            "high": high,
            "low": low,
            "close": close,
            "prev_rth_low": prev_rth_low,
            "prev_rth_high": prev_rth_high,
            "volume": 1000,
            "footprint_absorption_long": footprint_absorption_long,
            "footprint_absorption_short": footprint_absorption_short,
            "footprint_max_sell_imbalance_volume": footprint_max_sell_imbalance_volume,
            "footprint_max_buy_imbalance_volume": footprint_max_buy_imbalance_volume,
            "footprint_highest_sell_imbalance_price": footprint_highest_sell_imbalance_price,
            "footprint_lowest_buy_imbalance_price": footprint_lowest_buy_imbalance_price,
        }
    )
