from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo
import copy
import json
import math

import numpy as np
import pandas as pd

from propstack.backtest.contracts import ExecutionAssumptions
from propstack.backtest.fills import entry_price, exit_price
from propstack.backtest.metrics import calculate_metrics, daily_results
from propstack.backtest.risk import DailyRisk
from propstack.backtest.sizing import size_position
from propstack.utils.hashing import object_sha256
from propstack.utils.time import parse_time
from propstack.version import ENGINE_CONTRACT_VERSION


EVENT_REPLAY_CONTRACT_VERSION = "1.0"
CANONICAL_EVENT_ORDER = "utc_timestamp_ns_then_source_ordinal"
EVENT_TRANSITION_COLUMNS = (
    "trade_id",
    "session_date",
    "contract",
    "order_id",
    "timestamp",
    "source_ordinal",
    "event_index",
    "transition",
    "direction",
    "price",
    "active_from_event_index",
    "stop_price",
    "target_price",
    "reason",
    "state_json",
    "evidence_json",
)

ENGINE_TRADE_FIELDS = frozenset(
    {
        "trade_id",
        "strategy_name",
        "session_date",
        "contract_symbol",
        "direction",
        "entry_timestamp",
        "exit_timestamp",
        "entry_trigger_price",
        "entry_price",
        "exit_price",
        "initial_stop_price",
        "stop_price",
        "target_price",
        "exit_reason",
        "risk_points",
        "gross_pnl",
        "gross_pnl_before_slippage",
        "net_pnl",
        "r_multiple",
        "commission",
        "slippage_cost",
        "total_transaction_cost",
        "cost_accounting_error",
        "net_liq_after",
        "contracts",
        "entry_event_index",
        "exit_event_index",
        "max_favorable_excursion",
        "max_adverse_excursion",
    }
)


@dataclass
class CanonicalEvent:
    """Ephemeral view of the event currently being replayed.

    The runtime reuses one instance for performance. Strategies must copy any
    values they need to retain after a callback returns.
    """

    event_index: int = -1
    timestamp: pd.Timestamp | None = None
    timestamp_ns: int = 0
    source_ordinal: int = -1
    price: float = math.nan
    price_tick: int = 0
    size: int | float | None = None
    side: str | None = None
    signed_size: int | float | None = None


@dataclass(frozen=True)
class CanonicalEventSession:
    """Engine-private source session normalized into canonical order."""

    source_session: Any
    events: pd.DataFrame
    input_was_canonically_sorted: bool
    metadata: Mapping[str, Any]

    @property
    def session_date(self) -> Any:
        return self.source_session.session_date

    @property
    def contract_symbol(self) -> str:
        return str(self.source_session.contract_symbol)

    def public_view(self) -> "EventReplaySessionView":
        return EventReplaySessionView(
            session_date=self.session_date,
            contract_symbol=self.contract_symbol,
            metadata=MappingProxyType(copy.deepcopy(dict(self.metadata))),
            input_was_canonically_sorted=self.input_was_canonically_sorted,
        )


@dataclass(frozen=True)
class EventReplaySessionView:
    """Causal session metadata exposed to a strategy, never future events."""

    session_date: Any
    contract_symbol: str
    metadata: Mapping[str, Any]
    input_was_canonically_sorted: bool


@dataclass
class EventEntryOrder:
    order_id: str
    direction: str
    entry_tick: int
    stop_tick: int
    target_tick: int | None = None
    priority: int = 0
    active_from_event_index: int = 0
    submitted_event_index: int = -1
    report_fields: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventPosition:
    trade_id: int
    session_date: Any
    contract_symbol: str
    direction: str
    entry_timestamp: pd.Timestamp
    entry_event_index: int
    entry_trigger_tick: int
    entry_reference_tick: int
    entry_price: float
    initial_stop_tick: int
    stop_tick: int
    target_tick: int | None
    contracts: int
    risk_points: float
    order_id: str
    stop_exit_reason: str = "initial_stop"
    bracket_active_from_event_index: int = 0
    max_price_tick: int = 0
    min_price_tick: int = 0
    report_fields: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventPositionView:
    trade_id: int
    session_date: Any
    contract_symbol: str
    direction: str
    entry_timestamp: pd.Timestamp
    entry_event_index: int
    entry_trigger_tick: int
    entry_reference_tick: int
    entry_price: float
    initial_stop_tick: int
    stop_tick: int
    target_tick: int | None
    contracts: int
    risk_points: float
    order_id: str
    stop_exit_reason: str
    bracket_active_from_event_index: int
    max_price_tick: int
    min_price_tick: int
    report_fields: Mapping[str, Any]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class EventPreExecution:
    block_entries: bool = False
    cancel_entry_orders: bool = False
    flatten_reason: str | None = None
    flatten_tick: int | None = None


@dataclass(frozen=True)
class PositionDirective:
    stop_tick: int | None = None
    target_tick: int | None = None
    stop_exit_reason: str | None = None
    flatten_reason: str | None = None
    flatten_tick: int | None = None
    report_fields: Mapping[str, Any] = field(default_factory=dict)
    allow_inverted_oco: bool = False
    allow_marketable_bracket: bool = False


class CanonicalEventReplayStrategy:
    """Callback contract for strategies using canonical trade-event replay.

    Feature state is updated in ``on_event_start`` before execution. Existing
    brackets and prior-event entry orders are then evaluated by the engine.
    ``after_event`` is where strategies recompute state and submit/reprice
    orders; those changes cannot execute until a later event.
    """

    required_event_columns: tuple[str, ...] = ()

    def on_replay_start(self, broker: "EventReplayBroker") -> None:
        pass

    def on_session_start(self, session: EventReplaySessionView, broker: "EventReplayBroker") -> None:
        pass

    def on_event_start(self, event: CanonicalEvent, broker: "EventReplayBroker") -> None:
        pass

    def pre_execution(self, event: CanonicalEvent, broker: "EventReplayBroker") -> EventPreExecution:
        return EventPreExecution()

    def entry_order_is_live(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: "EventReplayBroker",
    ) -> bool:
        return True

    def entry_order_is_suspended(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: "EventReplayBroker",
    ) -> bool:
        """Return true to retain an order without evaluating or cancelling it."""

        return False

    def entry_fill_allowed(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: "EventReplayBroker",
    ) -> bool:
        return True

    def on_order_cancelled(
        self,
        order: EventEntryOrder,
        reason: str,
        event: CanonicalEvent | None,
        broker: "EventReplayBroker",
    ) -> None:
        pass

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: "EventReplayBroker",
    ) -> None:
        pass

    def position_directive(
        self,
        event: CanonicalEvent,
        position: EventPositionView,
        broker: "EventReplayBroker",
    ) -> PositionDirective:
        return PositionDirective()

    def on_position_closed(
        self,
        position: EventPositionView,
        trade: Mapping[str, Any],
        broker: "EventReplayBroker",
    ) -> None:
        pass

    def after_event(
        self,
        event: CanonicalEvent,
        broker: "EventReplayBroker",
        *,
        closed_this_event: bool,
        opened_this_event: bool,
        entries_blocked: bool,
    ) -> None:
        pass

    def finish_session(self, session: EventReplaySessionView, broker: "EventReplayBroker") -> None:
        pass

    def session_audit(self) -> Mapping[str, Any]:
        return {}


class EventReplayBroker:
    """Strategy-facing order interface for the canonical event lane."""

    def __init__(self, runtime: "CanonicalEventReplay"):
        self._runtime = runtime

    @property
    def position(self) -> EventPositionView | None:
        return self._runtime._position_view()

    @property
    def orders(self) -> Mapping[str, EventEntryOrder]:
        return MappingProxyType(
            {order_id: copy.deepcopy(order) for order_id, order in self._runtime._orders.items()}
        )

    @property
    def current_event(self) -> CanonicalEvent | None:
        return copy.deepcopy(self._runtime._current_event)

    @property
    def current_session(self) -> EventReplaySessionView | None:
        return self._runtime._current_session_view

    @property
    def net_liq(self) -> float:
        return self._runtime._net_liq

    @property
    def trades_today(self) -> int:
        session = self.current_session
        return 0 if session is None else self._runtime._risk.trades_today(session.session_date)

    def submit_or_replace_entry(
        self,
        *,
        order_id: str,
        direction: str,
        entry_tick: int,
        stop_tick: int,
        target_tick: int | None = None,
        priority: int = 0,
        report_fields: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> EventEntryOrder:
        self._runtime._require_broker_phase("after_event", operation="submit or replace an entry order")
        order = self._runtime._submit_or_replace_entry(
            order_id=order_id,
            direction=direction,
            entry_tick=entry_tick,
            stop_tick=stop_tick,
            target_tick=target_tick,
            priority=priority,
            report_fields=copy.deepcopy(dict(report_fields or {})),
            metadata=copy.deepcopy(dict(metadata or {})),
        )
        return copy.deepcopy(order)

    def cancel_entry(self, order_id: str, reason: str = "strategy_cancel") -> None:
        self._runtime._require_broker_phase("after_event", operation="cancel an entry order")
        self._runtime._cancel_order(str(order_id), reason=reason, notify=False)

    def cancel_all_entries(self, reason: str = "strategy_cancel_all") -> None:
        self._runtime._require_broker_phase("after_event", operation="cancel entry orders")
        for order_id in tuple(self._runtime._orders):
            self._runtime._cancel_order(order_id, reason=reason, notify=False)

    def annotate_position(self, **report_fields: Any) -> None:
        self._runtime._require_broker_phase("on_entry_filled", operation="annotate an opened position")
        if self._runtime._position is None:
            raise RuntimeError("Cannot annotate a position when no position is open.")
        _validate_report_fields(report_fields)
        self._runtime._position.report_fields.update(copy.deepcopy(report_fields))


class CanonicalEventReplay:
    """Reusable, single-instrument canonical event execution runtime."""

    def __init__(self, config: dict[str, Any], execution: ExecutionAssumptions):
        self.config = config
        self.core = dict(config.get("core") or {})
        self.execution = execution
        self._strategy: CanonicalEventReplayStrategy | None = None
        self._broker = EventReplayBroker(self)
        self._orders: dict[str, EventEntryOrder] = {}
        self._position: EventPosition | None = None
        self._current_event: CanonicalEvent | None = None
        self._current_session: CanonicalEventSession | None = None
        self._current_session_view: EventReplaySessionView | None = None
        self._current_entry_start_ns: int | None = None
        self._phase = "engine"
        self.stop_market_fill_policy = str(self.core.get("event_stop_market_fill_policy") or "")
        if self.stop_market_fill_policy not in {"exact_requested_price", "trade_event_price_on_gap"}:
            raise ValueError(
                "core.event_stop_market_fill_policy is required for canonical event replay and must be "
                "'exact_requested_price' or 'trade_event_price_on_gap'."
            )
        self._risk = DailyRisk(self.core)
        self._trades: list[dict[str, Any]] = []
        self._session_audits: list[dict[str, Any]] = []
        self._transitions: list[dict[str, Any]] = []
        self._next_trade_id = 1
        self._net_liq = float(self.core.get("initial_balance", 0.0))
        self._session_open_trade_count = 0
        self._diagnostics = self._new_diagnostics()

    def run(
        self,
        sessions: Iterable[Any],
        strategy: CanonicalEventReplayStrategy,
    ) -> dict[str, Any]:
        self._reset_run_state()
        self._strategy = strategy
        with self._strategy_phase("on_replay_start"):
            strategy.on_replay_start(self._broker)
        previous_session_date = None
        for source_session in sessions:
            session_date = _normalized_session_date(source_session)
            if previous_session_date is not None and session_date <= previous_session_date:
                raise ValueError(
                    "Canonical event replay sessions must be unique and strictly chronological; "
                    f"received {session_date} after {previous_session_date}."
                )
            self._run_session(source_session)
            previous_session_date = session_date

        trades = pd.DataFrame(self._trades)
        initial_balance = float(self.core.get("initial_balance", 0.0))
        return {
            "trades": trades,
            "daily": daily_results(trades),
            "metrics": calculate_metrics(trades, initial_balance=initial_balance),
            "session_audits": pd.DataFrame(self._session_audits),
            "event_transitions": pd.DataFrame(self._transitions, columns=EVENT_TRANSITION_COLUMNS),
            "diagnostics": dict(self._diagnostics),
            "reproducibility": {
                "engine_lane": "canonical_event_replay",
                "event_replay_contract_version": EVENT_REPLAY_CONTRACT_VERSION,
                "canonical_event_order": CANONICAL_EVENT_ORDER,
                "stop_market_fill_policy": self.stop_market_fill_policy,
                "engine_contract_version": ENGINE_CONTRACT_VERSION,
                "config_hash": object_sha256(self.config),
                "execution_assumptions": self.execution.as_dict(),
                "sessions": int(len(self._session_audits)),
                "events": int(self._diagnostics["events"]),
            },
        }

    def _reset_run_state(self) -> None:
        self._orders = {}
        self._position = None
        self._current_event = None
        self._current_session = None
        self._current_session_view = None
        self._current_entry_start_ns = None
        self._phase = "engine"
        self._risk = DailyRisk(self.core)
        self._trades = []
        self._session_audits = []
        self._transitions = []
        self._next_trade_id = 1
        self._net_liq = float(self.core.get("initial_balance", 0.0))
        self._session_open_trade_count = 0
        self._diagnostics = self._new_diagnostics()

    @staticmethod
    def _new_diagnostics() -> dict[str, int]:
        return {
            "sessions": 0,
            "events": 0,
            "orders_submitted": 0,
            "orders_replaced": 0,
            "orders_cancelled": 0,
            "entry_gate_rejections": 0,
            "position_sizing_rejections": 0,
            "risk_rejections": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "forced_flattens": 0,
            "events_at_or_after_cutoff_skipped": 0,
            "entry_events_blocked_before_start": 0,
        }

    @contextmanager
    def _strategy_phase(self, phase: str):
        previous = self._phase
        self._phase = phase
        try:
            yield
        finally:
            self._phase = previous

    def _require_broker_phase(self, allowed: str, *, operation: str) -> None:
        if self._phase != allowed:
            raise RuntimeError(
                f"Event strategies may only {operation} during {allowed}; current callback phase is {self._phase}."
            )

    def _run_session(self, source_session: Any) -> None:
        if self._position is not None:
            raise RuntimeError("Canonical event replay cannot carry a position between sessions.")
        self._orders.clear()
        self._session_open_trade_count = len(self._trades)
        session = canonicalize_event_session(
            source_session,
            tick_size=self.execution.tick_size,
            required_columns=tuple(self._strategy.required_event_columns if self._strategy else ()),
        )
        self._current_session = session
        self._current_session_view = session.public_view()
        self._diagnostics["sessions"] += 1
        with self._strategy_phase("on_session_start"):
            self._strategy.on_session_start(self._current_session_view, self._broker)

        events = session.events
        timestamp_values = events["timestamp"].array
        timestamp_ns = events["_canonical_timestamp_ns"].to_numpy(dtype=np.int64, copy=False)
        source_ordinals = events["source_ordinal"].to_numpy(dtype=np.int64, copy=False)
        prices = pd.to_numeric(events["price"], errors="raise").to_numpy(dtype=float, copy=False)
        price_ticks = events["event_price_tick"].to_numpy(dtype=np.int64, copy=False)
        sizes = events["size"].to_numpy(copy=False) if "size" in events else None
        sides = events["side"].astype(str).to_numpy(copy=False) if "side" in events else None
        signed = events["signed_size"].to_numpy(copy=False) if "signed_size" in events else None
        cursor = CanonicalEvent()
        last_processed_event: CanonicalEvent | None = None
        cutoff_ns = self._session_cutoff_ns(session)
        self._current_entry_start_ns = self._session_entry_start_ns(session)
        processed_events = 0

        for index in range(len(events)):
            if int(timestamp_ns[index]) >= cutoff_ns:
                self._diagnostics["events_at_or_after_cutoff_skipped"] += len(events) - index
                break
            cursor.event_index = index
            cursor.timestamp = pd.Timestamp(timestamp_values[index])
            cursor.timestamp_ns = int(timestamp_ns[index])
            cursor.source_ordinal = int(source_ordinals[index])
            cursor.price = float(prices[index])
            cursor.price_tick = int(price_ticks[index])
            cursor.size = None if sizes is None else sizes[index]
            cursor.side = None if sides is None else str(sides[index])
            cursor.signed_size = None if signed is None else signed[index]
            self._current_event = cursor
            self._diagnostics["events"] += 1
            self._process_event(cursor)
            last_processed_event = cursor
            processed_events += 1

        cutoff_event = self._cutoff_event(session, last_processed_event)
        if cutoff_event is not None:
            self._current_event = cutoff_event
        self._flatten_at_session_end(session, last_processed_event, cutoff_event)
        self._cancel_all_orders("session_end", notify=True)
        self._current_event = None
        with self._strategy_phase("finish_session"):
            self._strategy.finish_session(self._current_session_view, self._broker)
        with self._strategy_phase("session_audit"):
            strategy_audit = dict(self._strategy.session_audit())
        session_trade_count = len(self._trades) - self._session_open_trade_count
        audit = {
            **strategy_audit,
            "session_date": session.session_date,
            "contract_symbol": session.contract_symbol,
            "events": int(processed_events),
            "source_events": int(len(events)),
            "trades": int(session_trade_count),
            "input_was_canonically_sorted": bool(session.input_was_canonically_sorted),
            "canonical_event_order": CANONICAL_EVENT_ORDER,
        }
        self._session_audits.append(audit)
        self._current_event = None
        self._current_session = None
        self._current_session_view = None
        self._current_entry_start_ns = None

    def _process_event(self, event: CanonicalEvent) -> None:
        strategy = self._strategy
        event_identity = _event_fingerprint(event)
        with self._strategy_phase("on_event_start"):
            strategy.on_event_start(event, self._broker)
        _assert_event_unchanged(event, event_identity)
        with self._strategy_phase("pre_execution"):
            pre = strategy.pre_execution(event, self._broker)
        _assert_event_unchanged(event, event_identity)
        if pre.cancel_entry_orders:
            self._cancel_all_orders("pre_execution_cancel", notify=True)

        closed = False
        opened = False
        if pre.flatten_reason is not None and self._position is not None:
            _validate_flatten_tick(pre.flatten_tick, event)
            self._close_position(
                exit_tick=event.price_tick,
                exit_timestamp=event.timestamp,
                exit_event_index=event.event_index,
                exit_reason=pre.flatten_reason,
            )
            closed = True

        if self._position is not None and not closed:
            closed = self._evaluate_position(event)

        before_entry_start = bool(
            self._current_entry_start_ns is not None and event.timestamp_ns < self._current_entry_start_ns
        )
        if before_entry_start:
            self._diagnostics["entry_events_blocked_before_start"] += 1
        entries_blocked = pre.block_entries or before_entry_start
        if not entries_blocked and not closed and self._position is None:
            opened = self._evaluate_entry_orders(event)

        with self._strategy_phase("after_event"):
            strategy.after_event(
                event,
                self._broker,
                closed_this_event=closed,
                opened_this_event=opened,
                entries_blocked=entries_blocked,
            )
        _assert_event_unchanged(event, event_identity)

    def _evaluate_position(self, event: CanonicalEvent) -> bool:
        position = self._position
        if position is None:
            return False
        position.max_price_tick = max(position.max_price_tick, event.price_tick)
        position.min_price_tick = min(position.min_price_tick, event.price_tick)
        if event.event_index >= position.bracket_active_from_event_index:
            stop_hit = (
                event.price_tick <= position.stop_tick
                if position.direction == "long"
                else event.price_tick >= position.stop_tick
            )
            if stop_hit:
                stop_fill_tick = self._stop_fill_reference_tick(position, event)
                self._close_position(
                    exit_tick=stop_fill_tick,
                    exit_timestamp=event.timestamp,
                    exit_event_index=event.event_index,
                    exit_reason=position.stop_exit_reason,
                )
                return True
            if position.target_tick is not None:
                target_hit = (
                    event.price_tick >= position.target_tick
                    if position.direction == "long"
                    else event.price_tick <= position.target_tick
                )
                if target_hit:
                    self._close_position(
                        exit_tick=position.target_tick,
                        exit_timestamp=event.timestamp,
                        exit_event_index=event.event_index,
                        exit_reason="target",
                    )
                    return True

        event_identity = _event_fingerprint(event)
        with self._strategy_phase("position_directive"):
            directive = self._strategy.position_directive(event, self._position_view(), self._broker)
        _assert_event_unchanged(event, event_identity)
        _validate_report_fields(directive.report_fields)
        if directive.flatten_reason is not None:
            _validate_flatten_tick(directive.flatten_tick, event)
            position.report_fields.update(copy.deepcopy(dict(directive.report_fields)))
            self._close_position(
                exit_tick=event.price_tick,
                exit_timestamp=event.timestamp,
                exit_event_index=event.event_index,
                exit_reason=directive.flatten_reason,
            )
            return True

        changed = False
        proposed_stop = position.stop_tick if directive.stop_tick is None else int(directive.stop_tick)
        proposed_target = position.target_tick if directive.target_tick is None else int(directive.target_tick)
        if directive.stop_tick is not None or directive.target_tick is not None:
            _validate_amended_bracket(
                direction=position.direction,
                entry_tick=position.entry_reference_tick,
                current_price_tick=event.price_tick,
                stop_tick=proposed_stop,
                target_tick=proposed_target,
                allow_inverted_oco=directive.allow_inverted_oco,
                allow_marketable=directive.allow_marketable_bracket,
            )
        if directive.stop_tick is not None:
            position.stop_tick = proposed_stop
            changed = True
        if directive.target_tick is not None:
            position.target_tick = proposed_target
            changed = True
        if directive.stop_exit_reason is not None:
            position.stop_exit_reason = str(directive.stop_exit_reason)
        position.report_fields.update(copy.deepcopy(dict(directive.report_fields)))
        if changed:
            position.bracket_active_from_event_index = event.event_index + 1
            self._record_transition(
                transition="bracket_amended",
                order_id=position.order_id,
                direction=position.direction,
                price_tick=event.price_tick,
                active_from_event_index=position.bracket_active_from_event_index,
                stop_tick=position.stop_tick,
                target_tick=position.target_tick,
                reason=position.stop_exit_reason,
            )
        return False

    def _evaluate_entry_orders(self, event: CanonicalEvent) -> bool:
        session_date = self._current_session.session_date
        if not self._risk.allow_new_trade(session_date):
            self._diagnostics["risk_rejections"] += 1
            return False
        ordered = sorted(tuple(self._orders.values()), key=lambda item: (item.priority, item.order_id))
        for order in ordered:
            if order.active_from_event_index > event.event_index:
                continue
            order_view = copy.deepcopy(order)
            event_identity = _event_fingerprint(event)
            with self._strategy_phase("entry_order_is_suspended"):
                is_suspended = self._strategy.entry_order_is_suspended(order_view, event, self._broker)
            _assert_event_unchanged(event, event_identity)
            if is_suspended:
                continue
            with self._strategy_phase("entry_order_is_live"):
                is_live = self._strategy.entry_order_is_live(order_view, event, self._broker)
            if not is_live:
                _assert_event_unchanged(event, event_identity)
                self._cancel_order(order.order_id, reason="order_not_live", notify=True)
                continue
            _assert_event_unchanged(event, event_identity)
            if not _entry_crossed(order.direction, order.entry_tick, event.price_tick):
                continue
            with self._strategy_phase("entry_fill_allowed"):
                fill_allowed = self._strategy.entry_fill_allowed(order_view, event, self._broker)
            if not fill_allowed:
                _assert_event_unchanged(event, event_identity)
                self._diagnostics["entry_gate_rejections"] += 1
                self._cancel_order(order.order_id, reason="fill_gate_rejected", notify=True)
                continue
            _assert_event_unchanged(event, event_identity)
            if self._orders.get(order.order_id) is not order:
                raise RuntimeError("The engine-owned entry order changed during its execution validation phase.")
            if self._open_position(order, event):
                return True
        return False

    def _open_position(self, order: EventEntryOrder, event: CanonicalEvent) -> bool:
        tick_size = self.execution.tick_size
        fill_reference_tick = self._entry_fill_reference_tick(order, event)
        reference_price = fill_reference_tick * tick_size
        filled_price = entry_price(reference_price, order.direction, tick_size, self.execution.slippage_ticks)
        stop_price = order.stop_tick * tick_size
        if order.direction == "long" and stop_price >= filled_price:
            raise ValueError("Long event entry slippage moved the fill to or below its protective stop distance.")
        if order.direction == "short" and stop_price <= filled_price:
            raise ValueError("Short event entry slippage moved the fill to or above its protective stop distance.")
        if order.target_tick is not None:
            target_price = order.target_tick * tick_size
            if order.direction == "long" and target_price <= filled_price:
                raise ValueError("Long event entry slippage moved the fill to or beyond its target.")
            if order.direction == "short" and target_price >= filled_price:
                raise ValueError("Short event entry slippage moved the fill to or beyond its target.")
        risk_points = abs(filled_price - stop_price)
        sizing = size_position(
            self.core,
            risk_points,
            tick_size,
            self.execution.tick_value,
            net_liq=self._net_liq,
        )
        if sizing.contracts < 1:
            self._diagnostics["position_sizing_rejections"] += 1
            return False
        position = EventPosition(
            trade_id=self._next_trade_id,
            session_date=self._current_session.session_date,
            contract_symbol=self._current_session.contract_symbol,
            direction=order.direction,
            entry_timestamp=pd.Timestamp(event.timestamp),
            entry_event_index=event.event_index,
            entry_trigger_tick=order.entry_tick,
            entry_reference_tick=fill_reference_tick,
            entry_price=filled_price,
            initial_stop_tick=order.stop_tick,
            stop_tick=order.stop_tick,
            target_tick=order.target_tick,
            contracts=sizing.contracts,
            risk_points=risk_points,
            order_id=order.order_id,
            bracket_active_from_event_index=event.event_index + 1,
            max_price_tick=fill_reference_tick,
            min_price_tick=fill_reference_tick,
            report_fields={**order.report_fields, **sizing.report_fields()},
            metadata=dict(order.metadata),
        )
        self._position = position
        self._orders.pop(order.order_id, None)
        self._next_trade_id += 1
        self._risk.record_entry(position.session_date)
        self._diagnostics["positions_opened"] += 1
        self._record_transition(
            transition="entry_filled",
            order_id=order.order_id,
            direction=order.direction,
            price_tick=fill_reference_tick,
            active_from_event_index=event.event_index,
            stop_tick=order.stop_tick,
            target_tick=order.target_tick,
            reason="stop_entry_triggered",
        )
        event_identity = _event_fingerprint(event)
        with self._strategy_phase("on_entry_filled"):
            self._strategy.on_entry_filled(copy.deepcopy(order), self._position_view(), event, self._broker)
        _assert_event_unchanged(event, event_identity)
        return True

    def _close_position(
        self,
        *,
        exit_tick: int,
        exit_timestamp: pd.Timestamp | None,
        exit_event_index: int,
        exit_reason: str,
    ) -> None:
        position = self._position
        if position is None:
            return
        tick_size = self.execution.tick_size
        tick_value = self.execution.tick_value
        reference_entry_price = position.entry_reference_tick * tick_size
        reference_exit_price = int(exit_tick) * tick_size
        filled_exit_price = exit_price(
            reference_exit_price,
            position.direction,
            tick_size,
            self.execution.slippage_ticks,
        )
        direction_sign = 1.0 if position.direction == "long" else -1.0
        point_value = tick_value / tick_size
        gross_before_slippage = (
            (reference_exit_price - reference_entry_price)
            * direction_sign
            * point_value
            * position.contracts
        )
        gross = (
            (filled_exit_price - position.entry_price)
            * direction_sign
            * point_value
            * position.contracts
        )
        slippage_cost = gross_before_slippage - gross
        commission = self.execution.commission_per_contract * 2.0 * position.contracts
        net = gross - commission
        mfe_ticks = (
            position.max_price_tick - position.entry_reference_tick
            if position.direction == "long"
            else position.entry_reference_tick - position.min_price_tick
        )
        mae_ticks = (
            position.entry_reference_tick - position.min_price_tick
            if position.direction == "long"
            else position.max_price_tick - position.entry_reference_tick
        )
        _validate_report_fields(position.report_fields)
        strategy_name = str(self.config.get("strategy_name") or self.config.get("variant_id") or "event_strategy")
        trade = {
            "trade_id": position.trade_id,
            "strategy_name": strategy_name,
            "session_date": position.session_date,
            "contract_symbol": position.contract_symbol,
            "direction": position.direction,
            "entry_timestamp": position.entry_timestamp,
            "exit_timestamp": pd.Timestamp(exit_timestamp),
            "entry_trigger_price": position.entry_trigger_tick * tick_size,
            "entry_price": position.entry_price,
            "exit_price": filled_exit_price,
            "initial_stop_price": position.initial_stop_tick * tick_size,
            "stop_price": position.stop_tick * tick_size,
            "target_price": position.target_tick * tick_size if position.target_tick is not None else np.nan,
            "exit_reason": str(exit_reason),
            "risk_points": position.risk_points,
            "gross_pnl": gross,
            "gross_pnl_before_slippage": gross_before_slippage,
            "net_pnl": net,
            "r_multiple": (
                ((filled_exit_price - position.entry_price) * direction_sign) / position.risk_points
                if position.risk_points
                else 0.0
            ),
            "commission": commission,
            "slippage_cost": slippage_cost,
            "total_transaction_cost": commission + slippage_cost,
            "cost_accounting_error": gross_before_slippage - slippage_cost - commission - net,
            "net_liq_after": self._net_liq + net,
            "contracts": position.contracts,
            "entry_event_index": position.entry_event_index,
            "exit_event_index": int(exit_event_index),
            "max_favorable_excursion": mfe_ticks * tick_size,
            "max_adverse_excursion": mae_ticks * tick_size,
            **position.report_fields,
        }
        self._trades.append(trade)
        self._net_liq += net
        self._risk.record_exit(position.session_date, net)
        self._diagnostics["positions_closed"] += 1
        self._record_transition(
            transition="position_closed",
            order_id=position.order_id,
            direction=position.direction,
            price_tick=int(exit_tick),
            active_from_event_index=exit_event_index,
            stop_tick=position.stop_tick,
            target_tick=position.target_tick,
            reason=str(exit_reason),
        )
        self._position = None
        with self._strategy_phase("on_position_closed"):
            self._strategy.on_position_closed(
                self._position_view(position),
                MappingProxyType(copy.deepcopy(trade)),
                self._broker,
            )

    def _position_view(self, position: EventPosition | None = None) -> EventPositionView | None:
        state = self._position if position is None else position
        if state is None:
            return None
        return EventPositionView(
            trade_id=state.trade_id,
            session_date=state.session_date,
            contract_symbol=state.contract_symbol,
            direction=state.direction,
            entry_timestamp=state.entry_timestamp,
            entry_event_index=state.entry_event_index,
            entry_trigger_tick=state.entry_trigger_tick,
            entry_reference_tick=state.entry_reference_tick,
            entry_price=state.entry_price,
            initial_stop_tick=state.initial_stop_tick,
            stop_tick=state.stop_tick,
            target_tick=state.target_tick,
            contracts=state.contracts,
            risk_points=state.risk_points,
            order_id=state.order_id,
            stop_exit_reason=state.stop_exit_reason,
            bracket_active_from_event_index=state.bracket_active_from_event_index,
            max_price_tick=state.max_price_tick,
            min_price_tick=state.min_price_tick,
            report_fields=MappingProxyType(copy.deepcopy(state.report_fields)),
            metadata=MappingProxyType(copy.deepcopy(state.metadata)),
        )

    def _flatten_at_session_end(
        self,
        session: CanonicalEventSession,
        last_event: CanonicalEvent | None,
        cutoff_event: CanonicalEvent | None,
    ) -> None:
        if self._position is None:
            return
        if last_event is None:
            raise RuntimeError("Cannot flatten an event position without a session price.")
        if cutoff_event is None:
            raise RuntimeError("Cannot construct a cutoff event without a session price.")
        self._close_position(
            exit_tick=last_event.price_tick,
            exit_timestamp=cutoff_event.timestamp,
            exit_event_index=cutoff_event.event_index,
            exit_reason="time_flatten",
        )
        self._diagnostics["forced_flattens"] += 1

    def _cutoff_event(
        self,
        session: CanonicalEventSession,
        last_event: CanonicalEvent | None,
    ) -> CanonicalEvent | None:
        if last_event is None:
            return None
        cutoff_ns = self._session_cutoff_ns(session)
        timezone = str(self.config.get("timezone") or self.core.get("timezone") or "America/New_York")
        return CanonicalEvent(
            event_index=last_event.event_index + 1,
            timestamp=pd.Timestamp(cutoff_ns, tz="UTC").tz_convert(timezone),
            timestamp_ns=cutoff_ns,
            source_ordinal=-1,
            price=last_event.price,
            price_tick=last_event.price_tick,
            size=None,
            side=None,
            signed_size=None,
        )

    def _session_cutoff_ns(self, session: CanonicalEventSession) -> int:
        flatten_time = parse_time(self.core.get("flatten_time", "16:00:00"))
        timezone = ZoneInfo(str(self.config.get("timezone") or self.core.get("timezone") or "America/New_York"))
        return int(pd.Timestamp.combine(pd.Timestamp(session.session_date), flatten_time).tz_localize(timezone).value)

    def _session_entry_start_ns(self, session: CanonicalEventSession) -> int:
        entry_start = parse_time(self.core.get("entry_start", "00:00:00"))
        timezone = ZoneInfo(str(self.config.get("timezone") or self.core.get("timezone") or "America/New_York"))
        return int(pd.Timestamp.combine(pd.Timestamp(session.session_date), entry_start).tz_localize(timezone).value)

    def _entry_fill_reference_tick(self, order: EventEntryOrder, event: CanonicalEvent) -> int:
        if self.stop_market_fill_policy == "exact_requested_price":
            return order.entry_tick
        return max(order.entry_tick, event.price_tick) if order.direction == "long" else min(
            order.entry_tick,
            event.price_tick,
        )

    def _stop_fill_reference_tick(self, position: EventPosition, event: CanonicalEvent) -> int:
        if self.stop_market_fill_policy == "exact_requested_price":
            return position.stop_tick
        return min(position.stop_tick, event.price_tick) if position.direction == "long" else max(
            position.stop_tick,
            event.price_tick,
        )

    def _submit_or_replace_entry(
        self,
        *,
        order_id: str,
        direction: str,
        entry_tick: int,
        stop_tick: int,
        target_tick: int | None,
        priority: int,
        report_fields: dict[str, Any],
        metadata: dict[str, Any],
    ) -> EventEntryOrder:
        if self._current_session is None or self._current_event is None:
            raise RuntimeError("Entry orders may only be submitted during an event callback.")
        direction = str(direction).lower()
        entry_tick = int(entry_tick)
        stop_tick = int(stop_tick)
        target_tick = None if target_tick is None else int(target_tick)
        _validate_bracket(direction, entry_tick, stop_tick, target_tick)
        _validate_report_fields(report_fields)
        order_id = str(order_id)
        current = self._orders.get(order_id)
        if current is not None and (
            current.direction,
            current.entry_tick,
            current.stop_tick,
            current.target_tick,
            current.priority,
        ) == (direction, entry_tick, stop_tick, target_tick, int(priority)):
            current.report_fields = report_fields
            current.metadata = metadata
            return current
        active_from = self._current_event.event_index + 1
        order = EventEntryOrder(
            order_id=order_id,
            direction=direction,
            entry_tick=entry_tick,
            stop_tick=stop_tick,
            target_tick=target_tick,
            priority=int(priority),
            active_from_event_index=active_from,
            submitted_event_index=self._current_event.event_index,
            report_fields=report_fields,
            metadata=metadata,
        )
        transition = "order_submitted" if current is None else "order_replaced"
        self._orders[order_id] = order
        self._diagnostics["orders_submitted" if current is None else "orders_replaced"] += 1
        self._record_transition(
            transition=transition,
            order_id=order_id,
            direction=direction,
            price_tick=entry_tick,
            active_from_event_index=active_from,
            stop_tick=stop_tick,
            target_tick=target_tick,
            reason="strategy_request",
        )
        return order

    def _cancel_order(self, order_id: str, *, reason: str, notify: bool) -> None:
        order = self._orders.pop(order_id, None)
        if order is None:
            return
        self._diagnostics["orders_cancelled"] += 1
        self._record_transition(
            transition="order_cancelled",
            order_id=order.order_id,
            direction=order.direction,
            price_tick=order.entry_tick,
            active_from_event_index=order.active_from_event_index,
            stop_tick=order.stop_tick,
            target_tick=order.target_tick,
            reason=reason,
        )
        if notify and self._strategy is not None:
            with self._strategy_phase("on_order_cancelled"):
                self._strategy.on_order_cancelled(
                    copy.deepcopy(order),
                    reason,
                    copy.deepcopy(self._current_event),
                    self._broker,
                )

    def _cancel_all_orders(self, reason: str, *, notify: bool) -> None:
        for order_id in tuple(self._orders):
            self._cancel_order(order_id, reason=reason, notify=notify)

    def _record_transition(
        self,
        *,
        transition: str,
        order_id: str,
        direction: str,
        price_tick: int,
        active_from_event_index: int,
        stop_tick: int | None,
        target_tick: int | None,
        reason: str,
    ) -> None:
        event = self._current_event
        session = self._current_session
        position = self._position
        state = {
            "order_id": order_id,
            "transition": transition,
            "direction": direction,
            "active_from_event_index": active_from_event_index,
            "stop_tick": stop_tick,
            "target_tick": target_tick,
            "position_trade_id": None if position is None else position.trade_id,
        }
        evidence = None
        if event is not None:
            evidence = {
                "timestamp_ns": event.timestamp_ns,
                "source_ordinal": event.source_ordinal,
                "event_index": event.event_index,
                "event_price_tick": event.price_tick,
                "event_size": None if event.size is None else int(event.size),
                "event_side": event.side,
                "event_signed_size": None if event.signed_size is None else int(event.signed_size),
            }
        self._transitions.append(
            {
                "trade_id": self._position.trade_id if self._position is not None else None,
                "session_date": None if session is None else session.session_date,
                "contract": None if session is None else session.contract_symbol,
                "order_id": order_id,
                "timestamp": None if event is None else event.timestamp,
                "source_ordinal": None if event is None else event.source_ordinal,
                "event_index": None if event is None else event.event_index,
                "transition": transition,
                "direction": direction,
                "price": price_tick * self.execution.tick_size,
                "active_from_event_index": active_from_event_index,
                "stop_price": None if stop_tick is None else stop_tick * self.execution.tick_size,
                "target_price": None if target_tick is None else target_tick * self.execution.tick_size,
                "reason": reason,
                "state_json": json.dumps(state, sort_keys=True),
                "evidence_json": None if evidence is None else json.dumps(evidence, sort_keys=True),
            }
        )


def canonicalize_event_session(
    source_session: Any,
    *,
    tick_size: float,
    required_columns: tuple[str, ...] = (),
) -> CanonicalEventSession:
    missing_attributes = [
        name for name in ("session_date", "contract_symbol", "events") if not hasattr(source_session, name)
    ]
    if missing_attributes:
        raise ValueError(
            "Event replay sessions must expose session_date, contract_symbol, and events; missing: "
            + ", ".join(missing_attributes)
            + "."
        )
    events = source_session.events
    if not isinstance(events, pd.DataFrame):
        raise ValueError("Event replay session.events must be a pandas DataFrame.")
    raw_metadata = getattr(source_session, "event_replay_metadata", {})
    raw_metadata = raw_metadata() if callable(raw_metadata) else raw_metadata
    if not isinstance(raw_metadata, Mapping):
        raise ValueError("Event replay session.event_replay_metadata must be a mapping when supplied.")
    metadata = copy.deepcopy(dict(raw_metadata))
    required = {"timestamp", "source_ordinal", "price", *required_columns}
    missing = sorted(required.difference(events.columns))
    if missing:
        raise ValueError(f"Event replay data is missing required column(s): {missing}.")
    if events.empty:
        out = events.copy()
        out["_canonical_timestamp_ns"] = pd.Series(dtype="int64")
        out["event_price_tick"] = pd.Series(dtype="int64")
        out["event_index"] = pd.Series(dtype="int64")
        return CanonicalEventSession(source_session, out, True, metadata)

    for column in required_columns:
        missing_values = events[column].isna()
        if bool(missing_values.any()):
            rows = [str(value) for value in events.index[missing_values][:5]]
            raise ValueError(f"Event replay required column {column!r} is null at row(s): {', '.join(rows)}.")

    timestamp_ns: list[int] = []
    normalized_timestamps: list[pd.Timestamp] = []
    naive_rows: list[str] = []
    invalid_rows: list[str] = []
    for row_index, value in events["timestamp"].items():
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            invalid_rows.append(str(row_index))
            continue
        if pd.isna(timestamp):
            invalid_rows.append(str(row_index))
            continue
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            naive_rows.append(str(row_index))
            continue
        normalized_timestamps.append(timestamp)
        timestamp_ns.append(int(timestamp.tz_convert("UTC").value))
    if invalid_rows:
        raise ValueError(f"Event replay timestamp contains invalid values at row(s): {', '.join(invalid_rows[:5])}.")
    if naive_rows:
        raise ValueError(f"Event replay timestamp must be timezone-aware at row(s): {', '.join(naive_rows[:5])}.")

    ordinal_values = pd.to_numeric(events["source_ordinal"], errors="coerce")
    invalid_ordinals = ordinal_values.isna() | ~ordinal_values.map(math.isfinite) | (ordinal_values % 1 != 0)
    if bool(invalid_ordinals.any()):
        rows = [str(value) for value in events.index[invalid_ordinals][:5]]
        raise ValueError(f"Event replay source_ordinal must contain finite integers at row(s): {', '.join(rows)}.")
    ordinals = ordinal_values.to_numpy(dtype=np.int64)

    price_values = pd.to_numeric(events["price"], errors="coerce")
    invalid_prices = price_values.isna() | ~price_values.map(math.isfinite)
    if bool(invalid_prices.any()):
        rows = [str(value) for value in events.index[invalid_prices][:5]]
        raise ValueError(f"Event replay price contains non-finite values at row(s): {', '.join(rows)}.")
    prices = price_values.to_numpy(dtype=float)
    raw_ticks = prices / float(tick_size)
    rounded_ticks = np.rint(raw_ticks)
    off_tick = ~np.isclose(raw_ticks, rounded_ticks, rtol=0.0, atol=1e-8)
    if bool(off_tick.any()):
        rows = [str(value) for value in events.index[np.flatnonzero(off_tick)[:5]]]
        raise ValueError(f"Event replay price is off the configured tick grid at row(s): {', '.join(rows)}.")

    if "size" in events:
        sizes = pd.to_numeric(events["size"], errors="coerce")
        invalid_sizes = sizes.isna() | ~sizes.map(math.isfinite) | (sizes < 0) | (sizes % 1 != 0)
        if bool(invalid_sizes.any()):
            rows = [str(value) for value in events.index[invalid_sizes][:5]]
            raise ValueError(
                f"Event replay size must contain finite non-negative integers at row(s): {', '.join(rows)}."
            )
    if "signed_size" in events:
        signed = pd.to_numeric(events["signed_size"], errors="coerce")
        invalid_signed = signed.isna() | ~signed.map(math.isfinite) | (signed % 1 != 0)
        if bool(invalid_signed.any()):
            rows = [str(value) for value in events.index[invalid_signed][:5]]
            raise ValueError(f"Event replay signed_size must contain finite integers at row(s): {', '.join(rows)}.")
    if "side" in events and bool(events["side"].isna().any()):
        rows = [str(value) for value in events.index[events["side"].isna()][:5]]
        raise ValueError(f"Event replay side is null at row(s): {', '.join(rows)}.")
    if {"size", "signed_size", "side"}.issubset(events.columns):
        sides = events["side"].astype(str)
        expected_signed = np.where(sides.eq("B"), sizes, np.where(sides.eq("A"), -sizes, 0))
        inconsistent = signed.to_numpy(dtype=np.int64) != np.asarray(expected_signed, dtype=np.int64)
        if bool(inconsistent.any()):
            rows = [str(value) for value in events.index[np.flatnonzero(inconsistent)[:5]]]
            raise ValueError(
                "Event replay signed_size is inconsistent with side and size at row(s): " + ", ".join(rows) + "."
            )

    timestamp_array = np.asarray(timestamp_ns, dtype=np.int64)
    keys = pd.MultiIndex.from_arrays([timestamp_array, ordinals])
    duplicates = keys.duplicated(keep=False)
    if bool(duplicates.any()):
        rows = [str(value) for value in events.index[np.flatnonzero(duplicates)[:5]]]
        raise ValueError(
            "Event replay contains duplicate (timestamp, source_ordinal) keys at row(s): " + ", ".join(rows) + "."
        )

    if "contract_symbol" in events:
        if bool(events["contract_symbol"].isna().any()):
            rows = [str(value) for value in events.index[events["contract_symbol"].isna()][:5]]
            raise ValueError(f"Event replay contract_symbol is null at row(s): {', '.join(rows)}.")
        contracts = set(events["contract_symbol"].astype(str))
        expected = str(source_session.contract_symbol)
        if contracts and contracts != {expected}:
            raise ValueError(
                f"Event replay session {source_session.session_date} mixes contracts {sorted(contracts)}; expected {expected}."
            )

    order = np.lexsort((np.arange(len(events), dtype=np.int64), ordinals, timestamp_array))
    canonical_already = bool(np.array_equal(order, np.arange(len(events), dtype=np.int64)))
    out = events.iloc[order].copy().reset_index(drop=True)
    out["timestamp"] = [normalized_timestamps[index] for index in order]
    out["source_ordinal"] = ordinals[order]
    out["price"] = prices[order]
    if "size" in out:
        out["size"] = sizes.to_numpy(dtype=np.int64)[order]
    if "signed_size" in out:
        out["signed_size"] = signed.to_numpy(dtype=np.int64)[order]
    if "side" in out:
        out["side"] = events["side"].astype(str).to_numpy()[order]
    out["_canonical_timestamp_ns"] = timestamp_array[order]
    out["event_price_tick"] = rounded_ticks[order].astype(np.int64)
    out["event_index"] = np.arange(len(out), dtype=np.int64)
    return CanonicalEventSession(source_session, out, canonical_already, metadata)


def _normalized_session_date(source_session: Any):
    if not hasattr(source_session, "session_date"):
        raise ValueError("Event replay sessions must expose session_date, contract_symbol, and events.")
    try:
        value = pd.Timestamp(source_session.session_date)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid event replay session_date: {source_session.session_date!r}.") from exc
    if pd.isna(value):
        raise ValueError(f"Invalid event replay session_date: {source_session.session_date!r}.")
    return value.date()


def _entry_crossed(direction: str, entry_tick: int, price_tick: int) -> bool:
    return price_tick >= entry_tick if direction == "long" else price_tick <= entry_tick


def _event_fingerprint(event: CanonicalEvent) -> tuple[Any, ...]:
    return (
        event.event_index,
        event.timestamp,
        event.timestamp_ns,
        event.source_ordinal,
        event.price,
        event.price_tick,
        event.size,
        event.side,
        event.signed_size,
    )


def _assert_event_unchanged(event: CanonicalEvent, expected: tuple[Any, ...]) -> None:
    if _event_fingerprint(event) != expected:
        raise RuntimeError("Event strategies cannot mutate the canonical event supplied by BacktestEngine.")


def _validate_bracket(
    direction: str,
    entry_tick: int,
    stop_tick: int,
    target_tick: int | None,
) -> None:
    if direction not in {"long", "short"}:
        raise ValueError("Event entry direction must be 'long' or 'short'.")
    if direction == "long" and stop_tick >= entry_tick:
        raise ValueError("A long event entry stop must be below its entry trigger.")
    if direction == "short" and stop_tick <= entry_tick:
        raise ValueError("A short event entry stop must be above its entry trigger.")
    if target_tick is not None:
        _validate_target(direction, entry_tick, target_tick)


def _validate_target(direction: str, entry_tick: int, target_tick: int) -> None:
    if direction == "long" and target_tick <= entry_tick:
        raise ValueError("A long event entry target must be above its entry trigger.")
    if direction == "short" and target_tick >= entry_tick:
        raise ValueError("A short event entry target must be below its entry trigger.")


def _validate_report_fields(fields: Mapping[str, Any]) -> None:
    collisions = sorted(ENGINE_TRADE_FIELDS.intersection(fields))
    if collisions:
        raise ValueError(
            "Strategy report fields cannot overwrite engine-owned trade fields: " + ", ".join(collisions) + "."
        )


def _validate_flatten_tick(flatten_tick: int | None, event: CanonicalEvent) -> None:
    if flatten_tick is not None and int(flatten_tick) != event.price_tick:
        raise ValueError("Event flatten requests must execute at the current canonical event price.")


def _validate_amended_bracket(
    *,
    direction: str,
    entry_tick: int,
    current_price_tick: int,
    stop_tick: int,
    target_tick: int | None,
    allow_inverted_oco: bool,
    allow_marketable: bool,
) -> None:
    if target_tick is not None:
        _validate_target(direction, entry_tick, target_tick)
    if not allow_marketable:
        stop_marketable = stop_tick >= current_price_tick if direction == "long" else stop_tick <= current_price_tick
        target_marketable = bool(
            target_tick is not None
            and (target_tick <= current_price_tick if direction == "long" else target_tick >= current_price_tick)
        )
        if stop_marketable or target_marketable:
            raise ValueError(
                "Dynamic event bracket levels cannot already be marketable at submission unless explicitly opted in."
            )
    if target_tick is not None and not allow_inverted_oco:
        inverted = stop_tick >= target_tick if direction == "long" else stop_tick <= target_tick
        if inverted:
            raise ValueError("Dynamic event bracket stop and target are inverted; explicit opt-in is required.")
