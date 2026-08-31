"""Deterministic quote/trade order simulation for certified research lanes.

This module intentionally does not simulate queue position or MBO priority.
Every order becomes eligible on the event after submission, so a strategy
cannot submit after observing an event and receive a fill from that same event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Literal


Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
OrderState = Literal["working", "partially_filled", "filled", "cancelled"]


@dataclass(frozen=True)
class QuoteTradeEvent:
    sequence: int
    timestamp: datetime
    trade_price: float
    trade_size: int | None = None
    bid: float | None = None
    ask: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None

    def validate(self) -> None:
        if self.sequence < 0:
            raise ValueError("event sequence must be non-negative")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("event timestamp must be timezone-aware")
        for name in ("trade_price", "bid", "ask"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        for name in ("trade_size", "bid_size", "ask_size"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (self.bid is None) != (self.ask is None):
            raise ValueError("bid and ask must be supplied together")
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError("bid cannot exceed ask")


@dataclass
class SimulatedOrder:
    order_id: str
    side: Side
    order_type: OrderType
    quantity: int
    submitted_sequence: int
    limit_price: float | None = None
    stop_price: float | None = None
    oco_group: str | None = None
    state: OrderState = "working"
    filled_quantity: int = 0
    triggered_sequence: int | None = None

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    def validate(self) -> None:
        if not self.order_id.strip():
            raise ValueError("order_id is required")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if self.quantity <= 0 or self.submitted_sequence < 0:
            raise ValueError("quantity must be positive and submitted_sequence non-negative")
        if self.order_type in {"limit", "stop_limit"} and self.limit_price is None:
            raise ValueError(f"{self.order_type} requires limit_price")
        if self.order_type in {"stop", "stop_limit"} and self.stop_price is None:
            raise ValueError(f"{self.order_type} requires stop_price")
        for name in ("limit_price", "stop_price"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class Fill:
    order_id: str
    sequence: int
    timestamp: datetime
    quantity: int
    price: float
    complete: bool
    liquidity_source: Literal["quote", "trade"]


@dataclass(frozen=True)
class OrderTransition:
    order_id: str
    sequence: int
    timestamp: datetime
    transition: str
    quantity: int = 0
    price: float | None = None
    reason: str | None = None


@dataclass
class OrderSimulator:
    """Replay generic order behavior from quote/trade events.

    ``require_displayed_liquidity`` keeps partial-fill assumptions auditable.
    When true, missing size is an error rather than an implicit infinite fill.
    """

    require_bid_ask_for_market: bool = True
    require_displayed_liquidity: bool = True
    queue_model: Literal["none"] = "none"
    orders: dict[str, SimulatedOrder] = field(default_factory=dict)
    transitions: list[OrderTransition] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.queue_model != "none":
            raise ValueError("MBO/queue simulation is unavailable without certified order-book data")

    def submit(self, order: SimulatedOrder, *, timestamp: datetime) -> None:
        order.validate()
        if order.order_id in self.orders:
            raise ValueError(f"duplicate order_id: {order.order_id}")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("submission timestamp must be timezone-aware")
        self.orders[order.order_id] = order
        self.transitions.append(
            OrderTransition(
                order_id=order.order_id,
                sequence=order.submitted_sequence,
                timestamp=timestamp,
                transition="submitted",
            )
        )

    def cancel(self, order_id: str, event: QuoteTradeEvent, *, reason: str = "cancelled") -> None:
        event.validate()
        order = self.orders[order_id]
        if order.state in {"filled", "cancelled"}:
            return
        order.state = "cancelled"
        self.transitions.append(OrderTransition(order_id, event.sequence, event.timestamp, "cancelled", reason=reason))

    def process(self, event: QuoteTradeEvent) -> list[Fill]:
        event.validate()
        fills: list[Fill] = []
        for order in list(self.orders.values()):
            if order.state not in {"working", "partially_filled"}:
                continue
            if event.sequence <= order.submitted_sequence:
                continue
            if order.order_type in {"stop", "stop_limit"} and order.triggered_sequence is None:
                if not _stop_touched(order, event.trade_price):
                    continue
                order.triggered_sequence = event.sequence
                self.transitions.append(
                    OrderTransition(
                        order.order_id,
                        event.sequence,
                        event.timestamp,
                        "stop_triggered",
                        price=event.trade_price,
                    )
                )
                if order.order_type == "stop_limit":
                    # A triggered stop-limit becomes a working limit only after
                    # this source event, preventing an inferred same-event path.
                    continue
            fill_price, liquidity, source = self._fillable(order, event)
            if fill_price is None:
                continue
            quantity = min(order.remaining_quantity, liquidity)
            if quantity <= 0:
                continue
            order.filled_quantity += quantity
            complete = order.remaining_quantity == 0
            order.state = "filled" if complete else "partially_filled"
            fill = Fill(
                order.order_id,
                event.sequence,
                event.timestamp,
                quantity,
                fill_price,
                complete,
                source,
            )
            fills.append(fill)
            self.transitions.append(
                OrderTransition(
                    order.order_id,
                    event.sequence,
                    event.timestamp,
                    "filled" if complete else "partially_filled",
                    quantity=quantity,
                    price=fill_price,
                )
            )
            if order.oco_group:
                self._cancel_oco_siblings(order, event)
        return fills

    def _fillable(
        self,
        order: SimulatedOrder,
        event: QuoteTradeEvent,
    ) -> tuple[float | None, int, Literal["quote", "trade"]]:
        if order.order_type == "market" or (order.order_type == "stop" and order.triggered_sequence is not None):
            if self.require_bid_ask_for_market and (event.bid is None or event.ask is None):
                raise ValueError("market and triggered-stop fills require certified bid/ask quotes")
            price = event.ask if order.side == "buy" else event.bid
            size = event.ask_size if order.side == "buy" else event.bid_size
            if price is None:
                return None, 0, "quote"
            return price, self._liquidity(size, order.remaining_quantity, "quote"), "quote"

        assert order.limit_price is not None
        touched = (
            event.trade_price <= order.limit_price if order.side == "buy" else event.trade_price >= order.limit_price
        )
        if not touched:
            return None, 0, "trade"
        # A resting limit is never improved beyond the observed trade price.
        price = (
            min(order.limit_price, event.trade_price)
            if order.side == "buy"
            else max(order.limit_price, event.trade_price)
        )
        return price, self._liquidity(event.trade_size, order.remaining_quantity, "trade"), "trade"

    def _liquidity(self, size: int | None, remaining: int, source: str) -> int:
        if size is None:
            if self.require_displayed_liquidity:
                raise ValueError(f"{source} size is required for partial-fill simulation")
            return remaining
        return int(size)

    def _cancel_oco_siblings(self, filled: SimulatedOrder, event: QuoteTradeEvent) -> None:
        for sibling in self.orders.values():
            if (
                sibling.order_id != filled.order_id
                and sibling.oco_group == filled.oco_group
                and sibling.state in {"working", "partially_filled"}
            ):
                sibling.state = "cancelled"
                self.transitions.append(
                    OrderTransition(
                        sibling.order_id,
                        event.sequence,
                        event.timestamp,
                        "cancelled",
                        reason=f"OCO peer {filled.order_id} received a fill",
                    )
                )


def _stop_touched(order: SimulatedOrder, price: float) -> bool:
    assert order.stop_price is not None
    return price >= order.stop_price if order.side == "buy" else price <= order.stop_price


__all__ = [
    "Fill",
    "OrderSimulator",
    "OrderTransition",
    "QuoteTradeEvent",
    "SimulatedOrder",
]
