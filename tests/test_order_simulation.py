from datetime import UTC, datetime, timedelta

import pytest

from alphaquest.backtest.order_simulation import (
    OrderSimulator,
    QuoteTradeEvent,
    SimulatedOrder,
)


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def event(sequence: int, **changes) -> QuoteTradeEvent:
    values = {
        "sequence": sequence,
        "timestamp": NOW + timedelta(seconds=sequence),
        "trade_price": 100.0,
        "trade_size": 10,
        "bid": 99.75,
        "ask": 100.0,
        "bid_size": 4,
        "ask_size": 3,
    }
    values.update(changes)
    return QuoteTradeEvent(**values)


def test_market_fill_is_next_event_at_quote_with_partial_liquidity() -> None:
    simulator = OrderSimulator()
    simulator.submit(
        SimulatedOrder("entry", "buy", "market", 5, submitted_sequence=1),
        timestamp=NOW,
    )

    assert simulator.process(event(1)) == []
    first = simulator.process(event(2))
    second = simulator.process(event(3))

    assert [(fill.quantity, fill.price, fill.complete) for fill in first] == [(3, 100.0, False)]
    assert [(fill.quantity, fill.complete) for fill in second] == [(2, True)]


def test_limit_uses_observed_trade_and_oco_cancels_peer_on_first_fill() -> None:
    simulator = OrderSimulator()
    simulator.submit(
        SimulatedOrder("target", "sell", "limit", 2, 1, limit_price=101.0, oco_group="exit"),
        timestamp=NOW,
    )
    simulator.submit(
        SimulatedOrder("stop", "sell", "stop", 2, 1, stop_price=99.0, oco_group="exit"),
        timestamp=NOW,
    )

    fills = simulator.process(event(2, trade_price=101.25, trade_size=1))

    assert fills[0].price == 101.25
    assert fills[0].quantity == 1
    assert simulator.orders["target"].state == "partially_filled"
    assert simulator.orders["stop"].state == "cancelled"


def test_stop_limit_requires_a_later_event_after_trigger() -> None:
    simulator = OrderSimulator()
    simulator.submit(
        SimulatedOrder(
            "breakout",
            "buy",
            "stop_limit",
            1,
            1,
            stop_price=101.0,
            limit_price=101.25,
        ),
        timestamp=NOW,
    )

    assert simulator.process(event(2, trade_price=101.0)) == []
    fills = simulator.process(event(3, trade_price=101.25, trade_size=1))

    assert fills[0].price == 101.25
    assert fills[0].complete is True


def test_missing_quote_or_liquidity_fails_closed() -> None:
    market = OrderSimulator()
    market.submit(SimulatedOrder("m", "buy", "market", 1, 1), timestamp=NOW)
    with pytest.raises(ValueError, match="bid/ask"):
        market.process(event(2, bid=None, ask=None))

    limit = OrderSimulator()
    limit.submit(
        SimulatedOrder("l", "buy", "limit", 1, 1, limit_price=100.0),
        timestamp=NOW,
    )
    with pytest.raises(ValueError, match="trade size"):
        limit.process(event(2, trade_size=None))


def test_invalid_quote_and_queue_model_are_rejected() -> None:
    with pytest.raises(ValueError, match="bid cannot exceed ask"):
        event(1, bid=101.0, ask=100.0).validate()
    with pytest.raises(ValueError, match="MBO/queue"):
        OrderSimulator(queue_model="price_time")  # type: ignore[arg-type]
