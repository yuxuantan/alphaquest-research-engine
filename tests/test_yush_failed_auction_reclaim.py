from __future__ import annotations

from datetime import date
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    EventEntryOrder,
    EventPositionView,
    EventReplaySessionView,
    canonicalize_event_session,
)
from alphaquest.data.databento_session_stream import RthSummary
from alphaquest.strategy_modules.event.yush_failed_auction_reclaim import (
    AggressionThresholdSnapshot,
    FailedAuctionEpisode,
    YushFailedAuctionConfig,
    YushFailedAuctionReclaimEventStrategy,
    _FailedAuctionState,
    _nearest_rank_threshold,
    build_failed_auction_session_feature_tape,
    build_strategy,
)


def _view() -> EventReplaySessionView:
    return EventReplaySessionView(
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        metadata=MappingProxyType(
            {
                "previous_rth": RthSummary(
                    date(2026, 5, 1),
                    "ESM6",
                    110.0,
                    100.0,
                    105.0,
                ),
                "overnight_high": 111.0,
                "overnight_low": 99.0,
            }
        ),
        input_was_canonically_sorted=True,
    )


def _prepared_state() -> _FailedAuctionState:
    state = _FailedAuctionState(_view(), YushFailedAuctionConfig())
    base = pd.Timestamp("2026-05-04 09:31:00", tz="America/New_York")
    state.event_count = 2
    state.timestamp_ns[:2] = np.array(
        [
            int((base - pd.Timedelta(milliseconds=100)).value),
            int(base.value),
        ],
        dtype=np.int64,
    )
    state.price_ticks[:2] = np.array([401, 399], dtype=np.int64)
    state.cumulative_low[:2] = np.array([390, 390], dtype=np.int64)
    state.cumulative_high[:2] = np.array([450, 450], dtype=np.int64)
    state.previous_decision_event_index = 0
    state.decision_event_index = 1
    state.decision_due = True
    state.current_profile = {
        "val_tick": 400,
        "vah_tick": 440,
        "poc_tick": 420,
        "total_volume": 10_000,
    }
    state.last_timestamp_ns = int(base.value)
    state.active_aggression_threshold = AggressionThresholdSnapshot(
        delta_threshold=50,
        big_trade_threshold=100,
        delta_reference_count=20,
        big_trade_reference_count=200,
    )
    return state


def _event(index: int, milliseconds: int, tick: int, *, size: int, side: str) -> CanonicalEvent:
    timestamp = pd.Timestamp("2026-05-04 09:31:00", tz="America/New_York") + pd.Timedelta(
        milliseconds=milliseconds
    )
    return CanonicalEvent(
        event_index=index,
        timestamp=timestamp,
        timestamp_ns=int(timestamp.value),
        source_ordinal=index,
        price=tick * 0.25,
        price_tick=tick,
        size=size,
        side=side,
        signed_size=size if side == "B" else -size,
    )


def _ready_episode(state: _FailedAuctionState) -> FailedAuctionEpisode:
    state.start_eligible_episodes()
    episode = state.episodes["VAL"]
    assert episode is not None
    assert episode.boundary_tick == 400
    assert episode.reference_type == "PDL"

    state.observe_event(_event(2, 10, 396, size=201, side="A"))
    assert episode.aggression_kind == "outward_big_trade_percentile_100ms"
    state.observe_event(_event(3, 20, 401, size=1, side="B"))

    assert episode.excursion_depth() == 4
    assert episode.reclaim_event_index == 3
    assert state.ready_episode(3) is episode
    return episode


def test_factory_rejects_undeclared_parameters_and_defaults_are_frozen() -> None:
    strategy = build_strategy({})
    assert isinstance(strategy, YushFailedAuctionReclaimEventStrategy)
    assert strategy.cfg.excursion_ticks == 4
    assert strategy.cfg.reclaim_window_seconds == 15
    assert strategy.cfg.stop_buffer_ticks == 2
    assert strategy.cfg.delta_aggression_percentile == 0.9
    assert strategy.cfg.big_trade_aggression_percentile == 0.995
    assert strategy.cfg.delta_percentile_min_observations == 20
    assert strategy.cfg.big_trade_percentile_min_observations == 200
    assert strategy.cfg.delta_profile_min_abs == strategy.cfg.delta_bubble_threshold
    assert strategy.cfg.delta_bubble_threshold == 1_000_000_000
    assert strategy.cfg.big_trade_threshold == 1_000_000_000

    reviewed = build_strategy(
        {
            "delta_aggression_percentile": 0.85,
            "big_trade_aggression_percentile": 0.99,
        }
    )
    assert reviewed.cfg.delta_aggression_percentile == 0.85
    assert reviewed.cfg.big_trade_aggression_percentile == 0.99

    with pytest.raises(ValueError, match="unknown yush_failed_auction_reclaim"):
        build_strategy({"future_leak": True})
    with pytest.raises(ValueError, match="delta_bubble_threshold"):
        build_strategy({"delta_bubble_threshold": 50})
    with pytest.raises(ValueError, match="big_trade_threshold"):
        build_strategy({"big_trade_threshold": 100})
    with pytest.raises(ValueError, match="delta_profile_min_abs"):
        build_strategy({"delta_profile_min_abs": 50})
    with pytest.raises(ValueError, match="opening_range_seconds"):
        build_strategy({"opening_range_seconds": 32})


def test_nearest_rank_percentile_is_deterministic_and_requires_warmup() -> None:
    histogram = __import__("collections").Counter({1: 2, 5: 2, 9: 1})

    assert _nearest_rank_threshold(histogram, 5, 0.8, 6) is None
    assert _nearest_rank_threshold(histogram, 5, 0.8, 2) == 5
    assert _nearest_rank_threshold(histogram, 5, 0.81, 2) == 9


def _canonical_percentile_session(*, final_size: int):
    start = pd.Timestamp("2026-05-04 09:30:00", tz="America/New_York")
    rows = []
    for index in range(25):
        timestamp = start + pd.Timedelta(milliseconds=index * 100)
        side = "B" if index % 2 == 0 else "A"
        size = index + 1
        rows.append(
            {
                "timestamp": timestamp,
                "source_ordinal": index,
                "price": (400 + index * 4) * 0.25,
                "size": size,
                "side": side,
                "signed_size": size if side == "B" else -size,
            }
        )
    rows.append(
        {
            "timestamp": start + pd.Timedelta(minutes=3),
            "source_ordinal": 25,
            "price": 400 * 0.25,
            "size": final_size,
            "side": "B",
            "signed_size": final_size,
        }
    )
    source = SimpleNamespace(
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        events=pd.DataFrame(rows),
        event_replay_metadata=dict(_view().metadata),
    )
    return canonicalize_event_session(
        source,
        tick_size=0.25,
        required_columns=("size", "side", "signed_size"),
    )


def test_percentile_tape_excludes_current_event_and_active_windows() -> None:
    config = YushFailedAuctionConfig(
        delta_percentile_min_observations=20,
        big_trade_percentile_min_observations=20,
    )
    ordinary = build_failed_auction_session_feature_tape(
        _canonical_percentile_session(final_size=1),
        config,
    )
    extreme = build_failed_auction_session_feature_tape(
        _canonical_percentile_session(final_size=10_000),
        config,
    )
    snapshot_index = max(ordinary.aggression_thresholds)
    ordinary_snapshot = ordinary.aggression_thresholds[snapshot_index]
    extreme_snapshot = extreme.aggression_thresholds[snapshot_index]

    assert ordinary_snapshot == extreme_snapshot
    assert ordinary_snapshot.delta_reference_count == 25
    assert ordinary_snapshot.big_trade_reference_count == 25
    assert ordinary_snapshot.delta_threshold is not None
    assert ordinary_snapshot.big_trade_threshold is not None


def test_live_and_prepared_percentile_paths_publish_identical_thresholds() -> None:
    config = YushFailedAuctionConfig(
        delta_percentile_min_observations=20,
        big_trade_percentile_min_observations=20,
    )
    session = _canonical_percentile_session(final_size=10_000)
    prepared = build_failed_auction_session_feature_tape(session, config)
    state = _FailedAuctionState(session.public_view(), config)

    for event_index, row in session.events.iterrows():
        event = CanonicalEvent(
            event_index=int(event_index),
            timestamp=pd.Timestamp(row["timestamp"]),
            timestamp_ns=int(row["_canonical_timestamp_ns"]),
            source_ordinal=int(row["source_ordinal"]),
            price=float(row["price"]),
            price_tick=int(row["event_price_tick"]),
            size=int(row["size"]),
            side=str(row["side"]),
            signed_size=int(row["signed_size"]),
        )
        state.advance_live_aggression_threshold(event)
        expected = prepared.aggression_thresholds.get(event.event_index)
        if expected is not None:
            assert state.active_aggression_threshold == expected


def test_live_percentile_path_cannot_idle_batch_past_raw_events() -> None:
    strategy = YushFailedAuctionReclaimEventStrategy()
    state = _prepared_state()
    strategy.state = state
    state.active_decision_bucket = 600
    timestamps = np.array(
        [
            state.open_ns + 60_000_000_010,
            state.open_ns + 60_000_000_020,
            state.open_ns + 60_000_000_030,
        ],
        dtype=np.int64,
    )

    assert strategy.idle_batch_stop(timestamps, start=0, stop=3) == 0


def test_v02_reference_gate_excludes_inherited_opening_range_levels() -> None:
    state = _prepared_state()
    state._market_confluences = lambda: [
        SimpleNamespace(level_type="ORH", point_tick=400),
        SimpleNamespace(level_type="ORL", point_tick=398),
    ]

    assert state._nearest_reference(400) is None


def test_episode_freezes_known_reference_and_requires_directional_failed_auction() -> None:
    state = _prepared_state()
    episode = _ready_episode(state)

    assert episode.poc_tick == 420
    assert episode.aggression_event_index == 2
    assert episode.started_event_index < episode.aggression_event_index < episode.reclaim_event_index


def test_episode_freezes_percentile_thresholds_at_its_start() -> None:
    state = _prepared_state()
    state.start_eligible_episodes()
    episode = state.episodes["VAL"]
    assert episode is not None
    assert episode.delta_aggression_threshold == 50
    assert episode.big_trade_aggression_threshold == 100

    state.active_aggression_threshold = AggressionThresholdSnapshot(
        delta_threshold=5_000,
        big_trade_threshold=10_000,
        delta_reference_count=500,
        big_trade_reference_count=5_000,
    )
    state.observe_event(_event(2, 10, 396, size=201, side="A"))

    assert episode.aggression_kind == "outward_big_trade_percentile_100ms"
    assert episode.big_trade_aggression_threshold == 100
    assert episode.big_trade_reference_count == 200


def test_outward_delta_uses_the_frozen_causal_percentile_threshold() -> None:
    state = _prepared_state()
    state.start_eligible_episodes()
    episode = state.episodes["VAL"]
    assert episode is not None

    state.observe_event(_event(2, 10, 396, size=60, side="A"))

    assert episode.aggression_kind == "outward_delta_percentile_4tick"
    assert episode.aggression_value == -60
    assert episode.aggression_event_index == 2
    assert episode.delta_aggression_threshold == 50


def test_wrong_side_aggression_cannot_qualify_reclaim() -> None:
    state = _prepared_state()
    state.start_eligible_episodes()
    episode = state.episodes["VAL"]
    assert episode is not None

    state.observe_event(_event(2, 10, 396, size=500, side="B"))
    state.observe_event(_event(3, 20, 401, size=1, side="B"))

    assert episode.reclaim_event_index is None
    assert episode.expired is True
    assert state.diagnostics["failed_auction_missing_aggression"] == 1


def test_reclaim_may_trade_through_the_frozen_boundary_before_one_tick_inside() -> None:
    state = _prepared_state()
    state.start_eligible_episodes()
    episode = state.episodes["VAL"]
    assert episode is not None

    state.observe_event(_event(2, 10, 396, size=201, side="A"))
    state.observe_event(_event(3, 20, 400, size=1, side="B"))
    assert episode.reclaim_event_index is None
    assert episode.expired is False

    state.observe_event(_event(4, 30, 401, size=1, side="B"))

    assert episode.reclaim_event_index == 4
    assert episode.expired is False
    assert state.ready_episode(4) is episode


def test_first_reclaim_is_frozen_and_cannot_move_to_a_later_inside_trade() -> None:
    state = _prepared_state()
    episode = _ready_episode(state)

    state.observe_event(_event(4, 30, 402, size=1, side="B"))

    assert episode.reclaim_event_index == 3
    assert state.diagnostics["failed_auction_reclaims"] == 1


def test_entry_is_live_only_on_event_after_reclaim_and_bracket_is_ordered() -> None:
    strategy = YushFailedAuctionReclaimEventStrategy()
    state = _prepared_state()
    strategy.state = state
    episode = _ready_episode(state)
    episode.order_submitted = True
    order = EventEntryOrder(
        order_id="failed_auction_VAL",
        direction="long",
        entry_tick=395,
        stop_tick=394,
        target_tick=420,
        submitted_event_index=3,
        active_from_event_index=4,
        metadata={"side": "VAL", "episode_id": episode.episode_id},
    )
    next_event = _event(4, 30, 401, size=1, side="B")

    assert strategy.entry_order_is_live(order, next_event, SimpleNamespace()) is True
    assert strategy.entry_fill_allowed(order, next_event, SimpleNamespace()) is True
    assert (
        strategy.entry_order_is_live(
            order,
            _event(5, 40, 402, size=1, side="B"),
            SimpleNamespace(),
        )
        is False
    )


def test_time_exit_uses_only_elapsed_events_and_forced_flatten_remains_engine_owned() -> None:
    strategy = YushFailedAuctionReclaimEventStrategy()
    strategy.state = _prepared_state()
    entry_time = pd.Timestamp("2026-05-04 09:40:00", tz="America/New_York")
    position = EventPositionView(
        trade_id=1,
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        direction="long",
        entry_timestamp=entry_time,
        entry_event_index=10,
        entry_trigger_tick=395,
        entry_reference_tick=401,
        entry_price=100.5,
        initial_stop_tick=394,
        stop_tick=394,
        target_tick=420,
        contracts=1,
        risk_points=2.0,
        order_id="failed_auction_VAL",
        stop_exit_reason="initial_stop",
        bracket_active_from_event_index=11,
        max_price_tick=401,
        min_price_tick=401,
        report_fields={},
        metadata={},
    )
    before = CanonicalEvent(
        event_index=11,
        timestamp=entry_time + pd.Timedelta(seconds=599),
        timestamp_ns=int((entry_time + pd.Timedelta(seconds=599)).value),
        price_tick=402,
    )
    at_timeout = CanonicalEvent(
        event_index=12,
        timestamp=entry_time + pd.Timedelta(seconds=600),
        timestamp_ns=int((entry_time + pd.Timedelta(seconds=600)).value),
        price_tick=402,
    )

    assert strategy.position_directive(before, position, SimpleNamespace()).flatten_reason is None
    directive = strategy.position_directive(at_timeout, position, SimpleNamespace())
    assert directive.flatten_reason == "failed_auction_time_exit"
    assert directive.flatten_tick == 402
