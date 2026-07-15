from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.tpo_value_edge_auction_rejection import (
    TpoValueEdgeAuctionRejectionEntry,
)


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        }
    )


def _entry(setup_mode: str = "two_sided_rejection") -> TpoValueEdgeAuctionRejectionEntry:
    return TpoValueEdgeAuctionRejectionEntry(
        {
            "setup_mode": setup_mode,
            "start_time": "09:33:00",
            "end_time": "10:59:00",
            "opening_range_minutes": 3,
            "min_profile_bars": 3,
            "min_probe_ticks": 1,
            "max_aoi_width_points": 3.0,
            "cooldown_bars": 0,
        }
    )


def _seed_balanced_profile(entry: TpoValueEdgeAuctionRejectionEntry) -> None:
    for minute in range(30, 33):
        assert entry.on_bar_close(
            _bar(
                f"2024-01-03 09:{minute}:00",
                open_=100.25,
                high=101.0,
                low=100.0,
                close=100.5,
            )
        ) is None


def test_module_is_registered() -> None:
    assert ENTRY_MODULES[TpoValueEdgeAuctionRejectionEntry.name] is TpoValueEdgeAuctionRejectionEntry


def test_completed_rejection_uses_profile_known_before_current_bar() -> None:
    entry = _entry()
    _seed_balanced_profile(entry)

    signal = entry.on_bar_close(
        _bar("2024-01-03 09:33:00", open_=100.25, high=101.0, low=99.75, close=100.75)
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:34:00")
    assert signal.metadata["tpo_profile_bars"] == 3
    assert signal.metadata["profile_source"] == "developing_completed_bar_tpo"
    assert signal.metadata["aoi_anchor"] == "VAL"
    assert signal.metadata["aoi_market_confluence"] == "ORL"
    assert signal.metadata["signal_target_price"] > signal.swept_level
    assert signal.metadata["dynamic_stop_trigger_price"] < signal.metadata["signal_target_price"]


def test_two_bar_variant_waits_for_completed_confirmation() -> None:
    entry = _entry("two_bar_confirmation")
    _seed_balanced_profile(entry)

    rejection = entry.on_bar_close(
        _bar("2024-01-03 09:33:00", open_=100.25, high=101.0, low=99.75, close=100.75)
    )
    confirmation = entry.on_bar_close(
        _bar("2024-01-03 09:34:00", open_=100.75, high=101.25, low=100.5, close=101.0)
    )

    assert rejection is None
    assert confirmation is not None
    assert confirmation.reclaim_timestamp == pd.Timestamp("2024-01-03 09:35:00")
    assert confirmation.metadata["rejection_bar_timestamp"] == pd.Timestamp("2024-01-03 09:33:00")
    assert confirmation.metadata["confirmation_bar_timestamp"] == pd.Timestamp("2024-01-03 09:34:00")


def test_full_stop_requires_opposite_direction_but_non_stop_does_not() -> None:
    entry = _entry()
    session = "2024-01-03"

    entry.on_trade_closed({"session_date": session, "direction": "long", "exit_reason": "stop"})
    assert entry.required_direction_by_session[session] == "short"

    entry.on_trade_closed({"session_date": session, "direction": "short", "exit_reason": "target"})
    assert session not in entry.required_direction_by_session


def test_price_only_module_does_not_require_volume_or_orderflow_fields() -> None:
    entry = _entry("val_long_rejection")
    _seed_balanced_profile(entry)
    signal = entry.on_bar_close(
        _bar("2024-01-03 09:33:00", open_=100.25, high=101.0, low=99.75, close=100.75)
    )
    assert signal is not None
    assert signal.direction == "long"


def test_engine_materializes_dynamic_stop_offset_and_notifies_entry(monkeypatch) -> None:
    class CallbackEntry:
        name = "test_tpo_callback_entry"
        closed_trades: list[dict] = []

        def __init__(self, params: dict):
            self.sent = False

        def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
            if self.sent:
                return None
            self.sent = True
            return Signal(
                direction="long",
                level_type="test",
                swept_level=100.0,
                sweep_timestamp=bar["timestamp"],
                sweep_high=float(bar["high"]),
                sweep_low=float(bar["low"]),
                reclaim_timestamp=bar["timestamp"],
                metadata={
                    "dynamic_stop_trigger_price": 102.0,
                    "dynamic_stop_offset_points": 1.25,
                },
            )

        def on_trade_closed(self, trade: dict) -> None:
            type(self).closed_trades.append(trade)

    CallbackEntry.closed_trades = []
    monkeypatch.setitem(ENTRY_MODULES, CallbackEntry.name, CallbackEntry)
    rows = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 09:30", tz="America/New_York"),
                "session_date": "2024-01-03",
                "is_rth": True,
                "open": 100.0,
                "high": 100.25,
                "low": 99.75,
                "close": 100.0,
                "volume": 1,
            },
            {
                "timestamp": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
                "session_date": "2024-01-03",
                "is_rth": True,
                "open": 100.0,
                "high": 102.5,
                "low": 99.75,
                "close": 102.0,
                "volume": 1,
            },
        ]
    )
    config = {
        "strategy_name": "callback_test",
        "timeframe": "1m",
        "strategy": {
            "entry": {"module": CallbackEntry.name, "params": {}},
            "sl": {"module": "points_from_entry", "params": {"stop_points": 1.0}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 4.0}},
            "flatten_time": "11:00:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0,
            "slippage_ticks": 0,
            "contracts": 1,
            "daily_loss_limit": 4000,
            "daily_profit_stop": 1000000,
        },
    }

    result = BacktestEngine(config).run(rows)

    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert trade["dynamic_stop_trigger_price"] == 102.0
    assert trade["dynamic_stop_price"] == 101.25
    assert trade["dynamic_stop_activated"]
    assert trade["stop_price"] == 101.25
    assert len(CallbackEntry.closed_trades) == 1
    assert CallbackEntry.closed_trades[0]["exit_reason"] == "stop"
