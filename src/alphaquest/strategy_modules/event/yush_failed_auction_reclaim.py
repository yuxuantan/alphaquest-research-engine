"""Failure-informed Yush v02: directional failed-auction reclaim.

The strategy keeps the campaign's economic edge but deliberately replaces the
v01 AOI/fingerprint state machine.  A setup freezes one developing value edge,
one already-known market reference, and the developing POC.  It then requires
directional aggressive flow outside value and a causal reclaim before entering
on the next ordered trade event.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
from typing import Any

import numpy as np
import pandas as pd

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    CanonicalEventSession,
    EventEntryOrder,
    EventPositionView,
    EventReplayBroker,
    EventReplaySessionView,
    PositionDirective,
)
from alphaquest.strategy_modules.event.yush_orderflow_range import (
    YushOrderflowRangeConfig,
    YushOrderflowRangeEventStrategy,
    YushSessionFeatureTape,
    _YushOrderflowRangeState,
    build_session_feature_tape,
)


STRATEGY_ID = "yush_failed_auction_reclaim"
ENTRY_MODULE = STRATEGY_ID
STOP_MODULE = "event_excursion_structural_stop"
TARGET_MODULE = "event_frozen_poc_time_exit"
SUPPORTED_REFERENCE_TYPES = frozenset({"PDH", "PDL", "PDC", "ONH", "ONL"})


@dataclass(frozen=True)
class YushFailedAuctionConfig(YushOrderflowRangeConfig):
    """Reviewed defaults for the v02 failed-auction state machine."""

    # v02 does not consume v01's absolute delta/big-trade qualifications. Keep
    # those inherited feature-tape paths inert and expose only the causal
    # percentile mechanic below.
    delta_profile_min_abs: int = field(default=1_000_000_000, init=False, repr=False)
    delta_bubble_threshold: int = field(default=1_000_000_000, init=False, repr=False)
    big_trade_threshold: int = field(default=1_000_000_000, init=False, repr=False)
    reference_distance_ticks: int = 4
    excursion_ticks: int = 4
    reclaim_window_seconds: int = 15
    delta_aggression_percentile: float = 0.90
    big_trade_aggression_percentile: float = 0.995
    delta_percentile_min_observations: int = 20
    big_trade_percentile_min_observations: int = 200
    stop_buffer_ticks: int = 2
    time_exit_seconds: int = 600
    minimum_reward_risk: float = 1.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.reference_distance_ticks < 0:
            raise ValueError("reference_distance_ticks cannot be negative")
        if self.excursion_ticks < 1:
            raise ValueError("excursion_ticks must be at least one tick")
        if self.reclaim_window_seconds < 1:
            raise ValueError("reclaim_window_seconds must be positive")
        if not 0 < self.delta_aggression_percentile < 1:
            raise ValueError("delta_aggression_percentile must be in (0, 1)")
        if not 0 < self.big_trade_aggression_percentile < 1:
            raise ValueError("big_trade_aggression_percentile must be in (0, 1)")
        if self.delta_percentile_min_observations < 2:
            raise ValueError("delta_percentile_min_observations must be at least two")
        if self.big_trade_percentile_min_observations < 2:
            raise ValueError("big_trade_percentile_min_observations must be at least two")
        if self.stop_buffer_ticks < 1:
            raise ValueError("stop_buffer_ticks must be positive")
        if self.time_exit_seconds < 1:
            raise ValueError("time_exit_seconds must be positive")
        if self.minimum_reward_risk < 1.0:
            raise ValueError("minimum_reward_risk must be at least 1.0")


_ACCEPTED_PARAMETERS = {
    "tick_size",
    "point_value",
    "contracts",
    "commission_per_contract",
    "max_trades_per_day",
    "max_stop_points",
    "value_area_fraction",
    "big_trade_window_ms",
    "bar_seconds",
    "initial_balance",
    "slippage_ticks",
    "delta_neighbour_multiple",
    "decision_interval_ms",
    "reference_distance_ticks",
    "excursion_ticks",
    "reclaim_window_seconds",
    "delta_aggression_percentile",
    "big_trade_aggression_percentile",
    "delta_percentile_min_observations",
    "big_trade_percentile_min_observations",
    "stop_buffer_ticks",
    "time_exit_seconds",
    "minimum_reward_risk",
}


def build_strategy(params: dict[str, Any]) -> "YushFailedAuctionReclaimEventStrategy":
    unknown = sorted(set(params) - _ACCEPTED_PARAMETERS)
    if unknown:
        raise ValueError(
            "unknown yush_failed_auction_reclaim parameter(s): " + ", ".join(unknown)
        )
    return YushFailedAuctionReclaimEventStrategy(
        YushFailedAuctionConfig(**params)
    )


@dataclass(frozen=True)
class AggressionThresholdSnapshot:
    """Causal percentile thresholds available at one decision publication."""

    delta_threshold: int | None
    big_trade_threshold: int | None
    delta_reference_count: int
    big_trade_reference_count: int


@dataclass(frozen=True)
class FailedAuctionSessionFeatureTape:
    """Shared Yush market tape plus v02-only causal percentile thresholds."""

    market_tape: YushSessionFeatureTape
    aggression_thresholds: dict[int, AggressionThresholdSnapshot]


@dataclass
class FailedAuctionEpisode:
    episode_id: int
    side: str
    direction: str
    boundary_tick: int
    reference_type: str
    reference_tick: int
    poc_tick: int
    delta_aggression_threshold: int | None
    big_trade_aggression_threshold: int | None
    delta_reference_count: int
    big_trade_reference_count: int
    started_at_ns: int
    started_event_index: int
    deadline_ns: int
    min_tick: int
    max_tick: int
    last_price_tick: int
    aggression_kind: str | None = None
    aggression_value: int = 0
    aggression_event_index: int | None = None
    reclaim_event_index: int | None = None
    reclaim_timestamp_ns: int | None = None
    expired: bool = False
    order_submitted: bool = False
    delta_by_bar_bucket: dict[tuple[int, int], int] = field(default_factory=dict)
    large_trade_by_interval: dict[tuple[int, int, str], int] = field(default_factory=dict)

    def outside(self, price_tick: int) -> bool:
        return (
            price_tick < self.boundary_tick
            if self.direction == "long"
            else price_tick > self.boundary_tick
        )

    def reclaimed(self, price_tick: int) -> bool:
        return (
            price_tick >= self.boundary_tick + 1
            if self.direction == "long"
            else price_tick <= self.boundary_tick - 1
        )

    def excursion_depth(self) -> int:
        return (
            self.boundary_tick - self.min_tick
            if self.direction == "long"
            else self.max_tick - self.boundary_tick
        )

    def outward_side(self) -> str:
        return "A" if self.direction == "long" else "B"

    def outward_sign(self) -> int:
        return -1 if self.direction == "long" else 1


class _FailedAuctionState(_YushOrderflowRangeState):
    def __init__(
        self,
        session: EventReplaySessionView,
        config: YushFailedAuctionConfig,
    ) -> None:
        super().__init__(session, config)
        self.cfg = config
        self.episodes: dict[str, FailedAuctionEpisode | None] = {
            "VAL": None,
            "VAH": None,
        }
        self.episode_counter = 0
        self.action_due = False
        self.aggression_thresholds: dict[int, AggressionThresholdSnapshot] = {}
        self.active_aggression_threshold = AggressionThresholdSnapshot(
            delta_threshold=None,
            big_trade_threshold=None,
            delta_reference_count=0,
            big_trade_reference_count=0,
        )
        self._live_delta_histogram: Counter[int] = Counter()
        self._live_big_trade_histogram: Counter[int] = Counter()
        self._live_delta_count = 0
        self._live_big_trade_count = 0
        self._live_bar_id: int | None = None
        self._live_bar_delta: dict[int, int] = {}
        self._live_interval_id: int | None = None
        self._live_big_trade: dict[tuple[int, str], int] = {}
        self.diagnostics.update(
            {
                "failed_auction_episodes": 0,
                "failed_auction_expired": 0,
                "failed_auction_insufficient_excursion": 0,
                "failed_auction_missing_aggression": 0,
                "failed_auction_reclaims": 0,
                "failed_auction_orders": 0,
                "failed_auction_fill_rejections": 0,
                "failed_auction_time_exits": 0,
            }
        )

    def bind_aggression_thresholds(
        self,
        values: dict[int, AggressionThresholdSnapshot],
    ) -> None:
        self.aggression_thresholds = dict(values)

    def activate_aggression_threshold(self, event_index: int) -> None:
        snapshot = self.aggression_thresholds.get(int(event_index))
        if snapshot is not None:
            self.active_aggression_threshold = snapshot

    def advance_live_aggression_threshold(self, event: CanonicalEvent) -> None:
        """Advance the same causal percentile state when no tape is prebound."""

        timestamp_ns = int(event.timestamp_ns)
        bar_id = self._bar_id(timestamp_ns)
        interval_id = timestamp_ns // (
            int(self.cfg.big_trade_window_ms) * 1_000_000
        )
        if self._live_bar_id is not None and bar_id != self._live_bar_id:
            for value in self._live_bar_delta.values():
                self._live_delta_histogram[abs(int(value))] += 1
                self._live_delta_count += 1
            self._live_bar_delta.clear()
        if (
            self._live_interval_id is not None
            and interval_id != self._live_interval_id
        ):
            for value in self._live_big_trade.values():
                self._live_big_trade_histogram[int(value)] += 1
                self._live_big_trade_count += 1
            self._live_big_trade.clear()

        self._live_bar_id = bar_id
        self._live_interval_id = interval_id
        self.active_aggression_threshold = AggressionThresholdSnapshot(
            delta_threshold=_nearest_rank_threshold(
                self._live_delta_histogram,
                self._live_delta_count,
                self.cfg.delta_aggression_percentile,
                self.cfg.delta_percentile_min_observations,
            ),
            big_trade_threshold=_nearest_rank_threshold(
                self._live_big_trade_histogram,
                self._live_big_trade_count,
                self.cfg.big_trade_aggression_percentile,
                self.cfg.big_trade_percentile_min_observations,
            ),
            delta_reference_count=self._live_delta_count,
            big_trade_reference_count=self._live_big_trade_count,
        )

        four_tick_bucket = math.floor(int(event.price_tick) / 4)
        self._live_bar_delta[four_tick_bucket] = (
            int(self._live_bar_delta.get(four_tick_bucket, 0))
            + int(event.signed_size or 0)
        )
        side = str(event.side or "")
        if side in {"A", "B"}:
            key = (int(event.price_tick), side)
            self._live_big_trade[key] = (
                int(self._live_big_trade.get(key, 0))
                + int(event.size or 0)
            )

    def observe_event(self, event: CanonicalEvent) -> None:
        """Advance frozen episodes using only the current canonical event."""

        self.action_due = False
        for episode in tuple(self.episodes.values()):
            if episode is None or episode.expired or episode.order_submitted:
                continue
            if event.timestamp_ns > episode.deadline_ns:
                episode.expired = True
                self.diagnostics["failed_auction_expired"] += 1
                self.action_due = True
                continue

            price_tick = int(event.price_tick)
            episode.min_tick = min(episode.min_tick, price_tick)
            episode.max_tick = max(episode.max_tick, price_tick)
            is_outside = episode.outside(price_tick)
            if is_outside:
                self._observe_outward_flow(episode, event)

            if (
                episode.reclaim_event_index is None
                and episode.reclaimed(price_tick)
                and event.event_index > episode.started_event_index
            ):
                if episode.excursion_depth() < self.cfg.excursion_ticks:
                    self.diagnostics["failed_auction_insufficient_excursion"] += 1
                    episode.expired = True
                elif episode.aggression_event_index is None:
                    self.diagnostics["failed_auction_missing_aggression"] += 1
                    episode.expired = True
                else:
                    episode.reclaim_event_index = int(event.event_index)
                    episode.reclaim_timestamp_ns = int(event.timestamp_ns)
                    self.diagnostics["failed_auction_reclaims"] += 1
                self.action_due = True
            episode.last_price_tick = price_tick

    def start_eligible_episodes(self) -> None:
        if (
            not self.decision_due
            or self.decision_event_index is None
            or self.previous_decision_event_index is None
            or self.current_profile is None
        ):
            return
        index = int(self.decision_event_index)
        previous_index = int(self.previous_decision_event_index)
        if not self._range_and_profile_pass(index):
            return
        previous_tick = int(self.price_ticks[previous_index])
        current_tick = int(self.price_ticks[index])
        profile = dict(self.current_profile)
        for side, direction, boundary_key in (
            ("VAL", "long", "val_tick"),
            ("VAH", "short", "vah_tick"),
        ):
            current = self.episodes[side]
            if current is not None and not current.expired:
                continue
            boundary_tick = int(profile[boundary_key])
            crossed = (
                previous_tick >= boundary_tick and current_tick < boundary_tick
                if direction == "long"
                else previous_tick <= boundary_tick and current_tick > boundary_tick
            )
            if not crossed:
                continue
            reference = self._nearest_reference(boundary_tick)
            poc_tick = int(profile["poc_tick"])
            target_is_favorable = (
                poc_tick > boundary_tick
                if direction == "long"
                else poc_tick < boundary_tick
            )
            if reference is None or not target_is_favorable:
                continue
            aggression = self.active_aggression_threshold
            if (
                aggression.delta_threshold is None
                and aggression.big_trade_threshold is None
            ):
                continue
            self.episode_counter += 1
            timestamp_ns = int(self.timestamp_ns[index])
            self.episodes[side] = FailedAuctionEpisode(
                episode_id=self.episode_counter,
                side=side,
                direction=direction,
                boundary_tick=boundary_tick,
                reference_type=reference[0],
                reference_tick=reference[1],
                poc_tick=poc_tick,
                delta_aggression_threshold=aggression.delta_threshold,
                big_trade_aggression_threshold=aggression.big_trade_threshold,
                delta_reference_count=aggression.delta_reference_count,
                big_trade_reference_count=aggression.big_trade_reference_count,
                started_at_ns=timestamp_ns,
                started_event_index=index,
                deadline_ns=timestamp_ns
                + int(self.cfg.reclaim_window_seconds) * 1_000_000_000,
                min_tick=current_tick,
                max_tick=current_tick,
                last_price_tick=current_tick,
            )
            self.diagnostics["failed_auction_episodes"] += 1

    def ready_episode(self, event_index: int) -> FailedAuctionEpisode | None:
        ready = [
            episode
            for episode in self.episodes.values()
            if episode is not None
            and not episode.expired
            and not episode.order_submitted
            and episode.reclaim_event_index == event_index
        ]
        if not ready:
            return None
        return min(ready, key=lambda item: (item.started_event_index, item.side))

    def _nearest_reference(self, boundary_tick: int) -> tuple[str, int] | None:
        candidates = [
            (point.level_type, int(point.point_tick))
            for point in self._market_confluences()
            if point.level_type in SUPPORTED_REFERENCE_TYPES
            and abs(int(point.point_tick) - boundary_tick)
            <= self.cfg.reference_distance_ticks
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (
                abs(item[1] - boundary_tick),
                item[0],
                item[1],
            ),
        )

    def _observe_outward_flow(
        self,
        episode: FailedAuctionEpisode,
        event: CanonicalEvent,
    ) -> None:
        price_tick = int(event.price_tick)
        timestamp_ns = int(event.timestamp_ns)
        bar_id = self._bar_id(timestamp_ns)
        four_bucket = math.floor(price_tick / 4)
        delta_key = (bar_id, four_bucket)
        episode.delta_by_bar_bucket[delta_key] = (
            int(episode.delta_by_bar_bucket.get(delta_key, 0))
            + int(event.signed_size or 0)
        )
        self._promote_delta_aggression(episode, delta_key, int(event.event_index))

        side = str(event.side or "")
        interval = timestamp_ns // (int(self.cfg.big_trade_window_ms) * 1_000_000)
        large_key = (interval, price_tick, side)
        episode.large_trade_by_interval[large_key] = (
            int(episode.large_trade_by_interval.get(large_key, 0))
            + int(event.size or 0)
        )
        volume = int(episode.large_trade_by_interval[large_key])
        if (
            episode.big_trade_aggression_threshold is not None
            and side == episode.outward_side()
            and volume >= episode.big_trade_aggression_threshold
        ):
            episode.aggression_kind = "outward_big_trade_percentile_100ms"
            episode.aggression_value = volume
            episode.aggression_event_index = int(event.event_index)

    def _promote_delta_aggression(
        self,
        episode: FailedAuctionEpisode,
        key: tuple[int, int],
        event_index: int,
    ) -> None:
        bar_id, bucket = key
        value = int(episode.delta_by_bar_bucket[key])
        threshold = episode.delta_aggression_threshold
        if threshold is None or episode.outward_sign() * value < threshold:
            return
        neighbours = [
            abs(int(episode.delta_by_bar_bucket.get((bar_id, candidate), 0)))
            for candidate in (bucket - 2, bucket - 1, bucket + 1, bucket + 2)
        ]
        neighbour_mean = sum(neighbours) / 4.0
        if abs(value) < self.cfg.delta_neighbour_multiple * neighbour_mean:
            return
        episode.aggression_kind = "outward_delta_percentile_4tick"
        episode.aggression_value = value
        episode.aggression_event_index = int(event_index)


def _nearest_rank_threshold(
    histogram: Counter[int],
    observation_count: int,
    percentile: float,
    minimum_observations: int,
) -> int | None:
    """Return the deterministic nearest-rank percentile of completed values."""

    if observation_count < minimum_observations:
        return None
    rank = max(1, int(math.ceil(float(percentile) * observation_count)))
    cumulative = 0
    for value in sorted(histogram):
        cumulative += int(histogram[value])
        if cumulative >= rank:
            return int(value)
    raise AssertionError("percentile histogram count does not match its observation count")


def build_failed_auction_session_feature_tape(
    session: CanonicalEventSession,
    config: YushFailedAuctionConfig,
) -> FailedAuctionSessionFeatureTape:
    """Build causal v02 thresholds without making sessions worker-order dependent.

    Delta references contain only completed earlier three-minute/four-tick
    bucket observations from the active session. Big-trade references contain
    only completed earlier 100 ms same-price/same-side aggregates. The current
    event and active aggregation windows are excluded from every threshold.
    """

    market_tape = build_session_feature_tape(session, config)
    events = session.events
    if events.empty:
        return FailedAuctionSessionFeatureTape(
            market_tape=market_tape,
            aggression_thresholds={},
        )

    timestamp_ns = events["_canonical_timestamp_ns"].to_numpy(
        dtype=np.int64,
        copy=False,
    )
    price_ticks = events["event_price_tick"].to_numpy(dtype=np.int64, copy=False)
    sizes = events["size"].to_numpy(dtype=np.int64, copy=False)
    sides = events["side"].astype(str).to_numpy(copy=False)
    signed = events["signed_size"].to_numpy(dtype=np.int64, copy=False)
    first_timestamp = pd.Timestamp(events["timestamp"].array[0])
    open_ns = int(
        (
            first_timestamp.normalize()
            + pd.Timedelta(hours=9, minutes=30)
        ).value
    )
    bar_ns = int(config.bar_seconds) * 1_000_000_000
    interval_ns = int(config.big_trade_window_ms) * 1_000_000
    decision_indices = set(market_tape.decision_snapshots)

    delta_histogram: Counter[int] = Counter()
    big_trade_histogram: Counter[int] = Counter()
    delta_count = 0
    big_trade_count = 0
    active_bar_id: int | None = None
    active_bar_delta: dict[int, int] = {}
    active_interval_id: int | None = None
    active_big_trade: dict[tuple[int, str], int] = {}
    snapshots: dict[int, AggressionThresholdSnapshot] = {}

    for index in range(len(events)):
        timestamp = int(timestamp_ns[index])
        bar_id = int((timestamp - open_ns) // bar_ns)
        interval_id = int(timestamp // interval_ns)

        if active_bar_id is not None and bar_id != active_bar_id:
            for value in active_bar_delta.values():
                delta_histogram[abs(int(value))] += 1
                delta_count += 1
            active_bar_delta.clear()
        if active_interval_id is not None and interval_id != active_interval_id:
            for value in active_big_trade.values():
                big_trade_histogram[int(value)] += 1
                big_trade_count += 1
            active_big_trade.clear()

        active_bar_id = bar_id
        active_interval_id = interval_id
        if index in decision_indices:
            snapshots[index] = AggressionThresholdSnapshot(
                delta_threshold=_nearest_rank_threshold(
                    delta_histogram,
                    delta_count,
                    config.delta_aggression_percentile,
                    config.delta_percentile_min_observations,
                ),
                big_trade_threshold=_nearest_rank_threshold(
                    big_trade_histogram,
                    big_trade_count,
                    config.big_trade_aggression_percentile,
                    config.big_trade_percentile_min_observations,
                ),
                delta_reference_count=delta_count,
                big_trade_reference_count=big_trade_count,
            )

        four_tick_bucket = math.floor(int(price_ticks[index]) / 4)
        active_bar_delta[four_tick_bucket] = (
            int(active_bar_delta.get(four_tick_bucket, 0))
            + int(signed[index])
        )
        side = str(sides[index])
        if side in {"A", "B"}:
            key = (int(price_ticks[index]), side)
            active_big_trade[key] = (
                int(active_big_trade.get(key, 0))
                + int(sizes[index])
            )

    return FailedAuctionSessionFeatureTape(
        market_tape=market_tape,
        aggression_thresholds=snapshots,
    )


class YushFailedAuctionReclaimEventStrategy(YushOrderflowRangeEventStrategy):
    """v02 strategy adapter using the generic canonical event broker."""

    def __init__(self, config: YushFailedAuctionConfig | None = None) -> None:
        super().__init__(config or YushFailedAuctionConfig())
        self.cfg: YushFailedAuctionConfig

    def prepare_session_features(
        self,
        session: CanonicalEventSession,
    ) -> FailedAuctionSessionFeatureTape:
        return build_failed_auction_session_feature_tape(session, self.cfg)

    def on_session_start(
        self,
        session: EventReplaySessionView,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        self.state = _FailedAuctionState(session, self.cfg)
        tape = self._session_feature_tapes.get(str(session.session_date))
        if isinstance(tape, FailedAuctionSessionFeatureTape):
            self._state().bind_feature_tape(tape.market_tape)
            self._state().bind_aggression_thresholds(
                tape.aggression_thresholds
            )
        elif tape is not None:
            raise TypeError("v02 requires a failed-auction percentile feature tape")

    def on_event_start(
        self,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        state = self._state()
        state.advance_feature_event(event)
        if state.feature_tape is None:
            state.advance_live_aggression_threshold(event)
        else:
            state.activate_aggression_threshold(event.event_index)
        state.observe_event(event)

    def idle_batch_stop(
        self,
        timestamp_ns: np.ndarray,
        *,
        start: int,
        stop: int,
    ) -> int:
        state = self._state()
        if state.feature_tape is None:
            # The live percentile accumulator is updated in on_event_start.
            # Skipping otherwise-idle events would bias its reference
            # distribution downward and make the live mechanics lane disagree
            # with the precomputed core-grid feature tape.
            return start
        if any(
            episode is not None and not episode.expired
            for episode in state.episodes.values()
        ):
            return start
        return super().idle_batch_stop(timestamp_ns, start=start, stop=stop)

    def pending_order_batch_stop(
        self,
        price_ticks: np.ndarray,
        *,
        start: int,
        stop: int,
        orders: tuple[EventEntryOrder, ...],
    ) -> int:
        del price_ticks, stop, orders
        return start

    def position_batch_stop(
        self,
        price_ticks: np.ndarray,
        *,
        start: int,
        stop: int,
        position: EventPositionView,
    ) -> int:
        del price_ticks, stop, position
        return start

    def after_event_required(
        self,
        event: CanonicalEvent,
        *,
        closed_this_event: bool,
        opened_this_event: bool,
        entries_blocked: bool,
    ) -> bool:
        del event, entries_blocked
        state = self._state()
        return bool(
            closed_this_event
            or opened_this_event
            or state.decision_due
            or state.action_due
        )

    def validate_entry_order_without_crossing(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
    ) -> bool:
        del order, event
        return True

    def entry_order_is_live(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del broker
        return int(event.event_index) == int(order.submitted_event_index) + 1

    def entry_order_is_suspended(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del order, event, broker
        return False

    def entry_fill_allowed(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del broker
        episode = self._episode_for_order(order)
        if episode is None or episode.reclaim_event_index is None:
            return False
        fill_reference_tick = (
            max(int(order.entry_tick), int(event.price_tick))
            if order.direction == "long"
            else min(int(order.entry_tick), int(event.price_tick))
        )
        actual_fill_tick = (
            fill_reference_tick + int(self.cfg.slippage_ticks)
            if order.direction == "long"
            else fill_reference_tick - int(self.cfg.slippage_ticks)
        )
        risk_ticks = (
            actual_fill_tick - int(order.stop_tick)
            if order.direction == "long"
            else int(order.stop_tick) - actual_fill_tick
        )
        reward_ticks = (
            int(order.target_tick) - actual_fill_tick
            if order.direction == "long"
            else actual_fill_tick - int(order.target_tick)
        )
        tick_value = self.cfg.tick_size * self.cfg.point_value
        round_turn_cost_ticks = math.ceil(
            (2.0 * self.cfg.commission_per_contract) / tick_value
            + 2.0 * self.cfg.slippage_ticks
        )
        allowed = (
            0 < risk_ticks <= self.cfg.max_stop_ticks
            and reward_ticks > 0
            and reward_ticks
            >= math.ceil(self.cfg.minimum_reward_risk * risk_ticks)
            + round_turn_cost_ticks
        )
        if not allowed:
            self._state().diagnostics["failed_auction_fill_rejections"] += 1
        return allowed

    def on_order_cancelled(
        self,
        order: EventEntryOrder,
        reason: str,
        event: CanonicalEvent | None,
        broker: EventReplayBroker,
    ) -> None:
        del reason, event, broker
        episode = self._episode_for_order(order)
        if episode is not None:
            episode.expired = True

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        episode = self._episode_for_order(order)
        if episode is None or episode.reclaim_event_index is None:
            raise AssertionError("Failed-auction entry filled without a frozen episode.")
        if not (
            episode.started_event_index
            < int(episode.aggression_event_index or -1)
            <= int(episode.reclaim_event_index)
            < int(event.event_index)
        ):
            raise AssertionError(
                "Failed-auction episode, aggression, reclaim, and fill are not causal."
            )
        broker.annotate_position(
            failed_auction_episode_id=episode.episode_id,
            failed_auction_side=episode.side,
            failed_auction_boundary=episode.boundary_tick * self.cfg.tick_size,
            failed_auction_reference_type=episode.reference_type,
            failed_auction_reference=episode.reference_tick * self.cfg.tick_size,
            failed_auction_excursion_low=episode.min_tick * self.cfg.tick_size,
            failed_auction_excursion_high=episode.max_tick * self.cfg.tick_size,
            failed_auction_aggression_kind=episode.aggression_kind,
            failed_auction_aggression_value=episode.aggression_value,
            failed_auction_delta_percentile=self.cfg.delta_aggression_percentile,
            failed_auction_delta_threshold=episode.delta_aggression_threshold,
            failed_auction_delta_reference_count=episode.delta_reference_count,
            failed_auction_big_trade_percentile=self.cfg.big_trade_aggression_percentile,
            failed_auction_big_trade_threshold=episode.big_trade_aggression_threshold,
            failed_auction_big_trade_reference_count=episode.big_trade_reference_count,
            failed_auction_started_at=pd.Timestamp(
                episode.started_at_ns,
                tz="UTC",
            ).tz_convert("America/New_York"),
            failed_auction_reclaimed_at=pd.Timestamp(
                int(episode.reclaim_timestamp_ns),
                tz="UTC",
            ).tz_convert("America/New_York"),
            frozen_entry_poc=episode.poc_tick * self.cfg.tick_size,
            time_exit_seconds=self.cfg.time_exit_seconds,
            fill_model="next_ordered_trade_after_causal_reclaim_with_adverse_slippage",
        )
        for candidate in self._state().episodes.values():
            if candidate is not None:
                candidate.expired = True

    def position_directive(
        self,
        event: CanonicalEvent,
        position: EventPositionView,
        broker: EventReplayBroker,
    ) -> PositionDirective:
        del broker
        deadline_ns = int(position.entry_timestamp.value) + (
            int(self.cfg.time_exit_seconds) * 1_000_000_000
        )
        if int(event.timestamp_ns) < deadline_ns:
            return PositionDirective()
        self._state().diagnostics["failed_auction_time_exits"] += 1
        return PositionDirective(
            flatten_reason="failed_auction_time_exit",
            flatten_tick=int(event.price_tick),
        )

    def on_position_closed(
        self,
        position: EventPositionView,
        trade: dict,
        broker: EventReplayBroker,
    ) -> None:
        del position, trade, broker
        self._state().episodes = {"VAL": None, "VAH": None}

    def after_event(
        self,
        event: CanonicalEvent,
        broker: EventReplayBroker,
        *,
        closed_this_event: bool,
        opened_this_event: bool,
        entries_blocked: bool,
    ) -> None:
        state = self._state()
        if opened_this_event:
            broker.cancel_all_entries(reason="failed_auction_position_opened")
            return
        if closed_this_event:
            broker.cancel_all_entries(reason="failed_auction_position_closed")
            state.episodes = {"VAL": None, "VAH": None}
            return
        if broker.position is not None:
            return

        for side, episode in tuple(state.episodes.items()):
            if episode is not None and episode.expired:
                state.episodes[side] = None
        if state.decision_due:
            state.start_eligible_episodes()
        if (
            entries_blocked
            or broker.trades_today >= self.cfg.max_trades_per_day
            or broker.orders
        ):
            return
        episode = state.ready_episode(int(event.event_index))
        if episode is None:
            return

        stop_tick = (
            episode.min_tick - self.cfg.stop_buffer_ticks
            if episode.direction == "long"
            else episode.max_tick + self.cfg.stop_buffer_ticks
        )
        # The engine owns stop-market entries.  A trigger one tick inside the
        # protective stop is marketable for any still-valid next event and
        # therefore gives a causal next-event fill without same-event entry.
        entry_tick = stop_tick + 1 if episode.direction == "long" else stop_tick - 1
        broker.submit_or_replace_entry(
            order_id=f"failed_auction_{episode.side}",
            direction=episode.direction,
            entry_tick=entry_tick,
            stop_tick=stop_tick,
            target_tick=episode.poc_tick,
            priority=0 if episode.side == "VAL" else 1,
            report_fields={
                "failed_auction_reclaim_event_index": episode.reclaim_event_index,
                "failed_auction_aggression_event_index": episode.aggression_event_index,
            },
            metadata={
                "side": episode.side,
                "episode_id": episode.episode_id,
            },
        )
        episode.order_submitted = True
        state.diagnostics["failed_auction_orders"] += 1

    def session_audit(self) -> dict[str, Any]:
        state = self._state()
        return {
            "previous_rth_available": state.previous_rth is not None,
            "overnight_available": (
                state.overnight_high is not None and state.overnight_low is not None
            ),
            **state.diagnostics,
        }

    def _episode_for_order(
        self,
        order: EventEntryOrder,
    ) -> FailedAuctionEpisode | None:
        side = str(order.metadata.get("side") or "")
        episode = self._state().episodes.get(side)
        if (
            episode is None
            or int(order.metadata.get("episode_id", -1)) != episode.episode_id
        ):
            return None
        return episode

    def _state(self) -> _FailedAuctionState:
        state = self.state
        if not isinstance(state, _FailedAuctionState):
            raise RuntimeError("Failed-auction strategy has not started a session.")
        return state


__all__ = [
    "ENTRY_MODULE",
    "STOP_MODULE",
    "STRATEGY_ID",
    "TARGET_MODULE",
    "FailedAuctionEpisode",
    "YushFailedAuctionConfig",
    "YushFailedAuctionReclaimEventStrategy",
    "build_strategy",
]
