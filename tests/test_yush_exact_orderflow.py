from __future__ import annotations

from datetime import date
from types import MappingProxyType

import pandas as pd

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    EventEntryOrder,
    EventPositionView,
    EventReplaySessionView,
)
from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.event.yush_orderflow_primitives import (
    AoiCandidate,
    AoiLineage,
    ConfluencePoint,
    ExactYushRangeConfig,
    ExactYushRangeEventStrategy,
    PendingOrder,
    Visit,
    _YushSessionState,
    _best_aoi,
    _entry_tick,
)
from alphaquest.data.databento_session_stream import DatabentoTradeSession, RthSummary


def _session(prices=(100.0, 100.25, 100.5), sizes=(1, 1, 1), sides=("B", "B", "B"), offsets_ms=None):
    offsets_ms = offsets_ms or tuple(range(len(prices)))
    timestamps = [pd.Timestamp("2026-05-04 09:30:00", tz="America/New_York") + pd.Timedelta(milliseconds=x) for x in offsets_ms]
    signed = [size if side == "B" else -size for size, side in zip(sizes, sides, strict=True)]
    events = pd.DataFrame(
        {
            "timestamp": timestamps,
            "source_ordinal": range(len(prices)),
            "sequence": range(len(prices)),
            "symbol": "ES",
            "contract_symbol": "ESM6",
            "price": prices,
            "size": sizes,
            "side": sides,
            "signed_size": signed,
        }
    )
    return DatabentoTradeSession(
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        previous_rth=RthSummary(date(2026, 5, 1), "ESM6", 101.0, 99.0, 100.0),
        overnight_high=100.75,
        overnight_low=99.25,
        events=events,
    )


def _replay(session=None):
    session = session or _session()
    view = EventReplaySessionView(
        session_date=session.session_date,
        contract_symbol=session.contract_symbol,
        metadata=MappingProxyType(dict(session.event_replay_metadata)),
        input_was_canonically_sorted=True,
    )
    state = _YushSessionState(view, ExactYushRangeConfig())
    for index, row in session.events.reset_index(drop=True).iterrows():
        state._ingest_event(
            CanonicalEvent(
                event_index=index,
                timestamp=row["timestamp"],
                timestamp_ns=int(pd.Timestamp(row["timestamp"]).value),
                source_ordinal=int(row["source_ordinal"]),
                price=float(row["price"]),
                price_tick=int(round(float(row["price"]) / 0.25)),
                size=int(row["size"]),
                side=str(row["side"]),
                signed_size=int(row["signed_size"]),
            )
        )
    return state


def test_exact_backtester_routes_through_backtestengine_canonical_event_lane():
    config = {
        "strategy_name": "exact_yush_primitive_test",
        "engine_lane": "canonical_event_replay",
        "timezone": "America/New_York",
        "core": {
            "initial_balance": 50_000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "contracts": 1,
            "commission_per_contract": 2.5,
            "slippage_ticks": 0,
            "max_trades_per_day": 3,
            "entry_start": "09:30:00",
            "latest_entry_time": "10:59:59",
            "flatten_time": "11:00:00",
            "event_stop_market_fill_policy": "exact_requested_price",
        },
    }
    result = BacktestEngine(config).run_event_replay(
        [_session()], ExactYushRangeEventStrategy(ExactYushRangeConfig())
    )

    assert result["reproducibility"]["engine_lane"] == "canonical_event_replay"
    execution = result["reproducibility"]["execution_assumptions"]
    assert execution["commission_per_contract"] == 2.5
    assert execution["commission_source"] == "configured"


def test_best_aoi_maximizes_categories_then_minimizes_width():
    categories = {
        "market": [ConfluencePoint("market", "PDH", 402, 402, 402)],
        "delta_profile": [ConfluencePoint("delta_profile", "DELTA_1T", 404, 404, 404)],
        "big_trade": [ConfluencePoint("big_trade", "BIG_TRADE", 401, 401, 401)],
    }
    candidate = _best_aoi("VAL", "long", 400, categories, max_width_ticks=12)
    assert candidate is not None
    assert candidate.categories == ("market", "delta_profile", "big_trade")
    assert (candidate.low_tick, candidate.high_tick) == (400, 404)


def test_four_tick_delta_confluence_requires_all_neighbours_and_two_x_magnitude():
    replay = _replay(_session(prices=(90.0, 100.0, 110.0)))
    center = 100
    center_index = center - replay.base_four
    replay.traded_four[center_index - 2 : center_index + 3] = True
    replay.delta_four[center_index - 2 : center_index + 3] = [100, -150, 300, 100, -149]
    assert replay._delta_level_qualifies(replay.delta_four, replay.traded_four, center, replay.base_four)
    replay.delta_four[center_index + 2] = 151
    assert not replay._delta_level_qualifies(replay.delta_four, replay.traded_four, center, replay.base_four)
    replay.traded_four[center_index + 2] = False
    assert not replay._delta_level_qualifies(replay.delta_four, replay.traded_four, center, replay.base_four)


def test_big_trade_chain_is_same_price_same_side_uninterrupted_and_strictly_over_200():
    session = _session(
        prices=(100.0, 100.0, 100.25, 100.0),
        sizes=(100, 100, 1, 201),
        sides=("B", "B", "A", "B"),
        offsets_ms=(0, 100, 101, 102),
    )
    replay = _replay(session)
    assert replay.big_trade_snapshots[400]["volume"] == 201


def test_neutral_trade_interrupts_big_trade_chain_and_never_contributes_delta():
    session = _session(
        prices=(100.0, 100.0, 100.0),
        sizes=(150, 1, 100),
        sides=("B", "N", "B"),
        offsets_ms=(0, 1, 2),
    )
    session.events.loc[1, "signed_size"] = 0
    replay = _replay(session)
    assert replay.big_trade_snapshots == {}


def test_aoi_cannot_tap_on_same_event_that_makes_it_eligible():
    replay = _replay()
    candidate = AoiCandidate(
        "VAL",
        "long",
        400,
        400,
        402,
        ("market",),
        (ConfluencePoint("market", "PDC", 402, 402, 402),),
    )
    first_ns = int(replay.timestamp_ns[0])
    replay._apply_candidate("VAL", candidate, first_ns, 0)
    lineage = replay.lineages["VAL"]
    assert lineage is not None
    replay.price_ticks[0] = 402
    replay._update_visit_and_order(lineage, 0)
    assert lineage.visit is None
    replay.price_ticks[1] = 402
    replay._update_visit_and_order(lineage, 1)
    assert lineage.visit is not None
    assert lineage.visit.tapped_at_ns == int(replay.timestamp_ns[1])


def test_overlapping_candidate_preserves_lineage_and_reprices_pending_order():
    replay = _replay()
    first = AoiCandidate("VAL", "long", 400, 400, 402, ("market",), ())
    second = AoiCandidate("VAL", "long", 401, 401, 403, ("market",), ())
    replay._apply_candidate("VAL", first, int(replay.timestamp_ns[0]), 0)
    lineage = replay.lineages["VAL"]
    assert lineage is not None
    lineage.pending = type("Pending", (), {"entry_tick": 404, "stop_tick": 398})()
    replay._apply_candidate("VAL", second, int(replay.timestamp_ns[1]), 1)
    assert replay.lineages["VAL"] is lineage
    assert lineage.pending.entry_tick == _entry_tick(second, 2)
    assert lineage.pending.stop_tick == 399


def test_causal_fill_uses_source_order_when_exchange_timestamps_are_equal():
    state = _replay()
    strategy = ExactYushRangeEventStrategy()
    strategy.state = state
    candidate = AoiCandidate("VAL", "long", 400, 398, 400, ("market",), ())
    same_ns = int(state.timestamp_ns[0])
    lineage = AoiLineage(
        lineage_id=1,
        candidate=candidate,
        eligible_at_ns=same_ns,
        eligible_event_index=1,
        visit=Visit(same_ns, 2, 398, 400),
        pending=PendingOrder(
            trigger_kind="big_trade_100ms",
            bubble_qualified_at_ns=same_ns,
            bubble_event_index=3,
            armed_at_ns=same_ns,
            armed_event_index=3,
            entry_tick=402,
            stop_tick=396,
            bubble_price_tick=400,
            bubble_value=201,
        ),
    )
    state.lineages["VAL"] = lineage
    state.current_profile = {"poc_tick": 402, "val_tick": 398, "vah_tick": 408, "total_volume": 1000}
    broker = _BrokerStub()
    position = _position_view(direction="long", entry_tick=402, stop_tick=396)
    order = EventEntryOrder(
        order_id="VAL",
        direction="long",
        entry_tick=402,
        stop_tick=396,
        metadata={"side": "VAL", "lineage_id": 1},
    )
    event = CanonicalEvent(
        event_index=4,
        timestamp=pd.Timestamp(same_ns, tz="UTC"),
        timestamp_ns=same_ns,
        source_ordinal=4,
        price=100.5,
        price_tick=402,
    )

    strategy.on_entry_filled(order, position, event, broker)

    assert lineage.locked
    assert lineage.pending is None
    assert broker.annotations["aoi_lineage_id"] == 1


def test_news_window_resets_setup_flattens_position_and_blocks_through_release():
    release = pd.Timestamp("2026-05-04 10:00:00", tz="America/New_York")
    state = _replay()
    state.news_release_ns = (int(release.value),)
    strategy = ExactYushRangeEventStrategy()
    strategy.state = state
    candidate = AoiCandidate("VAL", "long", 400, 398, 400, ("market",), ())
    state.lineages["VAL"] = AoiLineage(
        lineage_id=1,
        candidate=candidate,
        eligible_at_ns=1,
        eligible_event_index=1,
        visit=Visit(2, 2, 398, 400),
        pending=PendingOrder("big_trade_100ms", 3, 3, 3, 3, 402, 396, 400, bubble_value=201),
    )
    broker = _BrokerStub(position=_position_view(direction="long", entry_tick=402, stop_tick=396))
    start = release - pd.Timedelta(minutes=5)
    directive = strategy.pre_execution(_event(start, 401), broker)
    assert directive.block_entries
    assert directive.flatten_reason == "news_flatten"
    assert directive.cancel_entry_orders
    assert state.lineages["VAL"].visit is None
    assert state.lineages["VAL"].pending is None
    at_release = strategy.pre_execution(_event(release, 401), broker)
    assert at_release.block_entries and at_release.flatten_reason is None
    after = release + pd.Timedelta(nanoseconds=1)
    assert not strategy.pre_execution(_event(after, 401), broker).block_entries


def test_midpoint_management_waits_until_requested_stop_is_not_marketable_then_activates_next_event():
    state = _replay()
    state.current_profile = {"poc_tick": 403, "val_tick": 398, "vah_tick": 408, "total_volume": 1000}
    strategy = ExactYushRangeEventStrategy()
    strategy.state = state
    position = _position_view(direction="long", entry_tick=400, stop_tick=396)
    broker = _BrokerStub(position=position)
    timestamp = pd.Timestamp("2026-05-04 09:31:01", tz="America/New_York")
    inactive = strategy.position_directive(_event(timestamp, 403), position, broker)
    assert inactive.stop_tick is None
    active = strategy.position_directive(
        _event(timestamp + pd.Timedelta(milliseconds=1), 405),
        position,
        broker,
    )
    assert active.stop_tick == 405
    assert active.target_tick == 408
    assert active.stop_exit_reason == "managed_stop"
    assert active.allow_inverted_oco and active.allow_marketable_bracket


def test_only_unmanaged_initial_stop_activates_opposite_direction_requirement():
    state = _replay()
    strategy = ExactYushRangeEventStrategy()
    strategy.state = state
    position = _position_view(direction="long", entry_tick=400, stop_tick=396)
    strategy.on_position_closed(position, {"exit_reason": "initial_stop"}, _BrokerStub())
    assert state.required_direction == "short"

    state.required_direction = None
    managed = _position_view(
        direction="long",
        entry_tick=400,
        stop_tick=405,
        report_fields={"midpoint_activated": True},
    )
    strategy.on_position_closed(managed, {"exit_reason": "managed_stop"}, _BrokerStub())
    assert state.required_direction is None


class _BrokerStub:
    def __init__(self, position=None):
        self.position = position
        self.annotations = {}

    def annotate_position(self, **fields):
        self.annotations.update(fields)


def _position_view(*, direction, entry_tick, stop_tick, report_fields=None):
    timestamp = pd.Timestamp("2026-05-04 09:31:00", tz="America/New_York")
    return EventPositionView(
        trade_id=1,
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        direction=direction,
        entry_timestamp=timestamp,
        entry_event_index=4,
        entry_trigger_tick=entry_tick,
        entry_reference_tick=entry_tick,
        entry_price=entry_tick * 0.25,
        initial_stop_tick=stop_tick,
        stop_tick=stop_tick,
        target_tick=None,
        contracts=1,
        risk_points=abs(entry_tick - stop_tick) * 0.25,
        order_id="VAL",
        stop_exit_reason="initial_stop",
        bracket_active_from_event_index=5,
        max_price_tick=entry_tick,
        min_price_tick=entry_tick,
        report_fields=MappingProxyType(dict(report_fields or {"midpoint_activated": False})),
        metadata=MappingProxyType({}),
    )


def _event(timestamp, price_tick):
    return CanonicalEvent(
        event_index=5,
        timestamp=timestamp,
        timestamp_ns=int(timestamp.value),
        source_ordinal=5,
        price=price_tick * 0.25,
        price_tick=price_tick,
    )
