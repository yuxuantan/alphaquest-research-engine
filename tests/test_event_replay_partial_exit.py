from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import pytest

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.event_replay import (
    CanonicalEventReplayStrategy,
    PositionDirective,
)
from alphaquest.backtest.sizing import size_position
from alphaquest.strategy_modules.event.runner import (
    _require_session_independent_sizing,
    _session_independent_sizing,
)


@dataclass(frozen=True)
class _Session:
    session_date: date
    contract_symbol: str
    events: pd.DataFrame
    event_replay_metadata: dict


class _ScaleOutStrategy(CanonicalEventReplayStrategy):
    def __init__(self) -> None:
        self.submitted = False
        self.t1_done = False

    def after_event(self, event, broker, **_) -> None:
        if self.submitted:
            return
        broker.submit_or_replace_entry(
            order_id="range",
            direction="long",
            entry_tick=401,
            stop_tick=397,
        )
        self.submitted = True

    def position_directive(self, event, position, broker):
        del broker
        if not self.t1_done and event.price_tick >= 404:
            self.t1_done = True
            return PositionDirective(
                partial_exit_contracts=1,
                partial_exit_tick=404,
                partial_exit_reason="target_1",
                stop_tick=403,
                target_tick=408,
                stop_exit_reason="post_target_1_stop",
            )
        if self.t1_done and event.price_tick >= 408:
            return PositionDirective(immediate_target_tick=408)
        return PositionDirective()


def _config() -> dict:
    return {
        "strategy_name": "partial_exit_test",
        "strategy": {},
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "point_value": 50.0,
            "commission_per_contract": 1.55,
            "slippage_ticks": 1,
            "entry_slippage_ticks": 1,
            "protective_stop_slippage_ticks": 1,
            "target_limit_slippage_ticks": 0,
            "market_exit_slippage_ticks": 1,
            "initial_balance": 50_000.0,
            "entry_start": "09:30:00",
            "flatten_time": "15:55:00",
            "event_stop_market_fill_policy": "exact_requested_price",
            "position_sizing": {
                "mode": "fixed_dollar_risk",
                "risk_budget": 250.0,
                "cost_allowance_per_contract": 28.10,
                "rounding": "floor",
            },
        },
    }


def _session() -> _Session:
    start = pd.Timestamp(
        "2026-05-14 09:30:00",
        tz="America/New_York",
    )
    ticks = [400, 401, 404, 408]
    events = pd.DataFrame(
        {
            "timestamp": [
                start + pd.Timedelta(milliseconds=index)
                for index in range(len(ticks))
            ],
            "source_ordinal": range(len(ticks)),
            "contract_symbol": "ESM26",
            "price": [tick * 0.25 for tick in ticks],
            "size": 1,
            "side": "B",
            "signed_size": 1,
        }
    )
    return _Session(
        date(2026, 5, 14),
        "ESM26",
        events,
        {},
    )


def test_fixed_dollar_sizing_includes_cost_allowance() -> None:
    sizing = size_position(
        _config()["core"],
        risk_points=1.25,
        tick_size=0.25,
        tick_value=12.5,
        net_liq=50_000,
    )

    assert sizing.mode == "fixed_dollar_risk"
    assert sizing.contracts == 2
    assert sizing.dollar_risk_per_contract == 90.60
    assert sizing.planned_dollar_risk == 181.20


def test_partial_target_preserves_remainder_and_combines_trade_pnl() -> None:
    result = BacktestEngine(_config()).run_event_replay(
        [_session()],
        _ScaleOutStrategy(),
    )

    trade = result["trades"].iloc[0]
    assert trade["contracts"] == 2
    assert trade["exit_reason"] == "target"
    assert trade["gross_pnl"] == 100.0
    assert trade["commission"] == 6.20
    assert trade["slippage_cost"] == 25.0
    assert trade["net_pnl"] == 93.80
    assert '"exit_reason": "target_1"' in trade["partial_exit_legs"]
    transitions = result["event_transitions"]["transition"].tolist()
    assert "position_partially_closed" in transitions
    amended = result["event_transitions"].loc[
        result["event_transitions"]["transition"] == "bracket_amended"
    ].iloc[0]
    assert amended["stop_price"] == 100.75
    assert amended["target_price"] == 102.0


def test_single_contract_partial_target_records_active_target() -> None:
    config = _config()
    config["core"]["position_sizing"]["risk_budget"] = 100.0

    result = BacktestEngine(config).run_event_replay(
        [_session()],
        _ScaleOutStrategy(),
    )

    trade = result["trades"].iloc[0]
    assert trade["contracts"] == 1
    assert trade["exit_reason"] == "target_1"
    assert trade["target_price"] == 101.0
    close = result["event_transitions"].loc[
        result["event_transitions"]["transition"]
        == "position_closed"
    ].iloc[0]
    assert close["target_price"] == 101.0


def test_parallel_replay_accepts_fixed_dollar_sizing() -> None:
    _require_session_independent_sizing(_config())
    assert _session_independent_sizing(_config()) is True


def test_parallel_replay_rejects_equity_dependent_sizing() -> None:
    config = _config()
    config["core"]["position_sizing"] = {
        "mode": "risk_percent_net_liq",
        "risk_pct": 0.01,
    }

    with pytest.raises(ValueError, match="session-independent position sizing"):
        _require_session_independent_sizing(config)
    assert _session_independent_sizing(config) is False
