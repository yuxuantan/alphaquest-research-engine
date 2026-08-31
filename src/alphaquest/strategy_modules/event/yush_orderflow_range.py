"""Frozen event strategy for the Yush order-flow range-reversal specification."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
import math
import numpy as np
import pandas as pd

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    CanonicalEventBatch,
    CanonicalEventSession,
    EventEntryOrder,
    EventPositionView,
    EventReplayBroker,
    EventReplaySessionView,
    PositionDirective,
)
from alphaquest.strategy_modules.event.yush_orderflow_primitives import (
    AoiCandidate,
    AoiLineage,
    ConfluencePoint,
    ExactYushRangeConfig,
    ExactYushRangeEventStrategy,
    PendingOrder,
    Visit,
    _YushSessionState,
    _entry_crossed,
    _entry_tick,
    _format_point_price,
    _overlap,
    _point_in_or_beyond,
    _price_in_or_beyond,
)


@dataclass(frozen=True)
class YushOrderflowRangeConfig(ExactYushRangeConfig):
    """The reviewed fixed mechanics; these values are not an optimization grid."""

    minimum_stop_points: float = 2.0
    slippage_ticks: int = 1
    delta_neighbour_multiple: float = 2.0
    decision_interval_ms: int = 100
    aoi_lineage_mode: str = "exact_fingerprint"

    def __post_init__(self) -> None:
        if self.aoi_lineage_mode != "exact_fingerprint":
            raise ValueError("aoi_lineage_mode must be exact_fingerprint")
        if self.tick_size <= 0 or self.point_value <= 0 or self.contracts < 1:
            raise ValueError("tick size, point value, and contracts must be positive")
        if self.minimum_stop_points <= 0 or self.minimum_stop_points > self.max_stop_points:
            raise ValueError("minimum_stop_points must be positive and no greater than max_stop_points")
        if self.max_aoi_width_points < self.tick_size:
            raise ValueError("max_aoi_width_points must be at least one tick")
        if not 0 < self.value_area_fraction <= 1:
            raise ValueError("value_area_fraction must be in (0, 1]")
        if self.range_expansion_fraction < 0:
            raise ValueError("range_expansion_fraction cannot be negative")
        if self.delta_profile_min_abs != self.delta_bubble_threshold:
            raise ValueError("delta profile and trigger thresholds must remain aligned")
        if min(
            self.delta_profile_min_abs,
            self.big_trade_threshold,
            self.big_trade_window_ms,
            self.decision_interval_ms,
            self.opening_range_seconds,
            self.bar_seconds,
        ) <= 0:
            raise ValueError("order-flow thresholds and aggregation windows must be positive")
        if self.decision_interval_ms != 100 or self.big_trade_window_ms != 100:
            raise ValueError(
                "the reviewed strategy requires one shared 100 ms decision and big-trade aggregation interval"
            )

    @property
    def minimum_stop_ticks(self) -> int:
        return int(round(self.minimum_stop_points / self.tick_size))

    @property
    def max_stop_ticks(self) -> int:
        return int(round(self.max_stop_points / self.tick_size))

    @property
    def breakeven_offset_ticks(self) -> int:
        return int(round(self.breakeven_offset_points / self.tick_size))


@dataclass(frozen=True)
class YushDecisionFeatureSnapshot:
    event_index: int
    previous_decision_event_index: int | None
    current_profile: dict | None
    decision_bar_delta_values: dict[int, int]
    crossing_updates: dict[tuple[int, int], int]
    qualified_delta_four: frozenset[int]
    new_big_trade_occurrences: tuple[dict, ...]
    new_big_trade_levels: tuple[tuple[int, dict], ...]
    or_high_tick: int | None
    or_low_tick: int | None
    candidate_categories: dict[str, tuple[ConfluencePoint, ...]]
    candidate_signature_id: int


@dataclass(frozen=True)
class YushSessionFeatureTape:
    session_date: object
    timestamp_ns: np.ndarray
    price_ticks: np.ndarray
    cumulative_low: np.ndarray
    cumulative_high: np.ndarray
    neutral_cumulative: np.ndarray
    completed_bars: tuple[tuple[int, int], ...]
    decision_snapshots: dict[int, YushDecisionFeatureSnapshot]
    candidate_cache: dict[tuple, AoiCandidate | None] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )


def build_strategy(params: dict) -> "YushOrderflowRangeEventStrategy":
    """Certified factory used by the generic event-strategy registry."""

    allowed = {field.name for field in fields(YushOrderflowRangeConfig) if field.init}
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"unknown yush_orderflow_range parameter(s): {', '.join(unknown)}")
    return YushOrderflowRangeEventStrategy(YushOrderflowRangeConfig(**params))


class _YushOrderflowRangeState(_YushSessionState):
    def __init__(self, session: EventReplaySessionView, config: YushOrderflowRangeConfig):
        super().__init__(session, config, news_releases=())
        self.cfg = config
        self.big_trade_occurrences: list[dict] = []
        self.big_trade_levels: dict[int, dict] = {}
        self.delta_threshold_crossings: dict[tuple[int, int], int] = {}
        self.decision_interval_ns = int(config.decision_interval_ms) * 1_000_000
        self.active_decision_bucket: int | None = None
        self.decision_due = False
        self.decision_event_index: int | None = None
        self.previous_decision_event_index: int | None = None
        self.decision_bar_delta_values: dict[int, int] = {}
        self._last_decision_bar_delta: dict[tuple[int, int], int] = {}
        self._dirty_four_buckets: set[int] = set()
        self._decision_big_trade_volume: dict[tuple[int, str], int] = {}
        self._candidate_cache_keys: dict[str, tuple | None] = {"VAL": None, "VAH": None}
        self._candidate_cache: dict[str, AoiCandidate | None] = {"VAL": None, "VAH": None}
        self.diagnostics.update(
            {
                "decision_intervals": 0,
                "aoi_cache_hits": 0,
                "aoi_cache_misses": 0,
                "aoi_anchor_invalidations": 0,
                "aoi_fingerprint_resets": 0,
                "wrong_approach_rejections": 0,
                "midpoint_distance_rejections": 0,
                "stop_limit_rejections": 0,
            }
        )
        self.feature_tape: YushSessionFeatureTape | None = None
        self.active_feature_snapshot: YushDecisionFeatureSnapshot | None = None
        self._feature_decision_indices: tuple[int, ...] = ()
        self._feature_decision_cursor = 0

    def bind_feature_tape(self, tape: YushSessionFeatureTape) -> None:
        if str(tape.session_date) != str(self.session.session_date):
            raise ValueError("Yush feature tape session does not match the active replay session.")
        self.feature_tape = tape
        self._feature_decision_indices = tuple(sorted(tape.decision_snapshots))
        self._feature_decision_cursor = 0
        count = len(tape.timestamp_ns)
        self._capacity = max(count, 1)
        self.timestamp_ns = tape.timestamp_ns
        self.price_ticks = tape.price_ticks
        self.cumulative_low = tape.cumulative_low
        self.cumulative_high = tape.cumulative_high
        self.completed_bars = list(tape.completed_bars)

    def advance_feature_event(self, event: CanonicalEvent) -> None:
        tape = self.feature_tape
        if tape is None:
            self.last_timestamp_ns = event.timestamp_ns
            self._ingest_event(event)
            return
        if event.event_index != self.event_count:
            raise AssertionError("Yush feature-tape events must be contiguous.")
        if int(tape.timestamp_ns[event.event_index]) != event.timestamp_ns:
            raise AssertionError("Yush feature tape timestamp drifted from canonical replay.")
        self.decision_due = False
        self.event_count = event.event_index + 1
        self.last_timestamp_ns = event.timestamp_ns
        self.active_decision_bucket = int(
            (event.timestamp_ns - self.open_ns) // self.decision_interval_ns
        )
        self.neutral_side_events = int(tape.neutral_cumulative[event.event_index])
        self.diagnostics["events"] = self.event_count
        self.diagnostics["neutral_side_events"] = self.neutral_side_events
        snapshot = tape.decision_snapshots.get(event.event_index)
        self.active_feature_snapshot = snapshot
        while (
            self._feature_decision_cursor < len(self._feature_decision_indices)
            and self._feature_decision_indices[self._feature_decision_cursor] <= event.event_index
        ):
            self._feature_decision_cursor += 1
        if snapshot is None:
            return
        self.previous_decision_event_index = snapshot.previous_decision_event_index
        self.decision_event_index = snapshot.event_index
        self.current_profile = (
            None if snapshot.current_profile is None else dict(snapshot.current_profile)
        )
        self.decision_bar_delta_values = dict(snapshot.decision_bar_delta_values)
        self.delta_threshold_crossings.update(snapshot.crossing_updates)
        self.qualified_delta_four = set(snapshot.qualified_delta_four)
        self.big_trade_occurrences.extend(
            dict(value) for value in snapshot.new_big_trade_occurrences
        )
        for price_tick, value in snapshot.new_big_trade_levels:
            self.big_trade_levels.setdefault(int(price_tick), dict(value))
        self.or_high_tick = snapshot.or_high_tick
        self.or_low_tick = snapshot.or_low_tick
        self.decision_due = True
        self.diagnostics["decision_intervals"] += 1

    def advance_feature_batch(self, batch: CanonicalEventBatch) -> None:
        tape = self.feature_tape
        if tape is None:
            self._ingest_idle_batch(batch)
            return
        start = int(batch.start_event_index)
        stop = int(batch.stop_event_index)
        if start != self.event_count or stop <= start:
            raise AssertionError("Yush feature-tape batches must be non-empty and contiguous.")
        if any(index in tape.decision_snapshots for index in range(start, stop)):
            raise AssertionError("Yush feature-tape batch crossed a decision snapshot.")
        last = stop - 1
        self.event_count = stop
        self.last_timestamp_ns = int(tape.timestamp_ns[last])
        self.active_decision_bucket = int(
            (self.last_timestamp_ns - self.open_ns) // self.decision_interval_ns
        )
        self.neutral_side_events = int(tape.neutral_cumulative[last])
        self.decision_due = False
        self.active_feature_snapshot = None
        self.diagnostics["events"] = self.event_count
        self.diagnostics["neutral_side_events"] = self.neutral_side_events

    def _ingest_event(self, event: CanonicalEvent) -> None:
        """Ingest every executable event but publish strategy state every 100 ms."""

        if event.event_index != self.event_count:
            raise AssertionError("Yush event indices must be contiguous from session start.")
        if event.timestamp_ns < self.open_ns:
            raise ValueError("The Yush strategy requires replay events at or after the 09:30 RTH anchor.")

        self.decision_due = False
        decision_bucket = int((event.timestamp_ns - self.open_ns) // self.decision_interval_ns)
        if self.active_decision_bucket is None:
            self.active_decision_bucket = decision_bucket
        elif decision_bucket != self.active_decision_bucket:
            self._finalize_decision_interval(self.event_count - 1)
            self.active_decision_bucket = decision_bucket
            self._decision_big_trade_volume.clear()

        self._ensure_capacity(event.event_index + 1)
        self.timestamp_ns[event.event_index] = event.timestamp_ns
        self.price_ticks[event.event_index] = event.price_tick
        self.event_count += 1
        self.diagnostics["events"] = self.event_count
        if event.side not in {"A", "B"}:
            self.neutral_side_events += 1
            self.diagnostics["neutral_side_events"] = self.neutral_side_events
        self._finalize_completed_bar(event.timestamp_ns, event.price_tick)
        self._update_market_state(event.event_index, int(event.size), int(event.signed_size))
        self._update_big_trade(event.event_index, str(event.side), int(event.size))

    def _finalize_decision_interval(self, event_index: int) -> None:
        if event_index < 0:
            return
        timestamp_ns = int(self.timestamp_ns[event_index])
        bar_id = self._bar_id(timestamp_ns)
        threshold = self.cfg.delta_bubble_threshold
        dirty = tuple(sorted(self._dirty_four_buckets))
        for bucket in dirty:
            if self.base_four is None or not self.base_four <= bucket <= int(self.top_four):
                continue
            value = int(self.bar_delta_four[bucket - int(self.base_four)])
            key = (bar_id, bucket)
            before = int(self._last_decision_bar_delta.get(key, 0))
            if abs(before) < threshold <= abs(value):
                self.delta_threshold_crossings[key] = event_index
            self._last_decision_bar_delta[key] = value

        for center in {candidate for bucket in dirty for candidate in range(bucket - 2, bucket + 3)}:
            if self._delta_level_qualifies(self.delta_four, self.traded_four, center, int(self.base_four)):
                self.qualified_delta_four.add(center)
            else:
                self.qualified_delta_four.discard(center)
        self.qualified_delta_one.clear()
        self._dirty_four_buckets.clear()

        for (price_tick, side), volume in sorted(self._decision_big_trade_volume.items()):
            if side not in {"A", "B"} or int(volume) <= self.cfg.big_trade_threshold:
                continue
            occurrence = {
                "occurrence_id": len(self.big_trade_occurrences) + 1,
                "qualified_at_ns": timestamp_ns,
                "qualified_event_index": event_index,
                "price_tick": int(price_tick),
                "side": side,
                "volume": int(volume),
            }
            self.big_trade_occurrences.append(occurrence)
            self.big_trade_levels.setdefault(int(price_tick), occurrence)

        self.current_profile = self._profile()
        self.decision_bar_delta_values = (
            {
                bucket: int(self.bar_delta_four[bucket - int(self.base_four)])
                for bucket in range(int(self.base_four), int(self.top_four) + 1)
            }
            if self.base_four is not None and self.top_four is not None
            else {}
        )
        self.previous_decision_event_index = self.decision_event_index
        self.decision_event_index = event_index
        self.decision_due = True
        self.diagnostics["decision_intervals"] += 1

    def _update_market_state(self, index: int, volume: int, signed: int) -> None:
        super()._update_market_state(index, volume, signed)

    def _delta_level_qualifies(self, delta, traded, center_tick: int, base_tick: int) -> bool:
        center = center_tick - base_tick
        if center - 2 < 0 or center + 2 >= len(delta):
            return False
        neighbours = (center - 2, center - 1, center + 1, center + 2)
        if not bool(traded[center]) or not all(bool(traded[item]) for item in neighbours):
            return False
        magnitude = abs(int(delta[center]))
        neighbour_mean = sum(abs(int(delta[item])) for item in neighbours) / 4.0
        return (
            magnitude >= self.cfg.delta_profile_min_abs
            and magnitude >= self.cfg.delta_neighbour_multiple * neighbour_mean
        )

    def _refresh_delta_qualifications(self, one_tick: int, four_bucket: int) -> None:
        del one_tick
        self._dirty_four_buckets.add(four_bucket)

    def _update_big_trade(self, index: int, side: str, size: int) -> None:
        price_tick = int(self.price_ticks[index])
        key = (price_tick, side)
        self._decision_big_trade_volume[key] = int(self._decision_big_trade_volume.get(key, 0)) + int(size)

    def _delta_confluences(self) -> list[ConfluencePoint]:
        return [
            ConfluencePoint("delta_profile", "DELTA_4T_LOCAL_PROMINENCE", bucket * 4, bucket * 4, bucket * 4 + 3)
            for bucket in sorted(self.qualified_delta_four)
        ]

    def _selected_candidates(self) -> dict[str, AoiCandidate]:
        profile = self.current_profile
        if profile is None:
            return {}
        tape = self.feature_tape
        snapshot = self.active_feature_snapshot if tape is not None else None
        if snapshot is not None:
            categories = snapshot.candidate_categories
            signature = ("feature_tape", snapshot.candidate_signature_id)
        else:
            market = self._market_confluences()
            delta = self._delta_confluences()
            big = [
                ConfluencePoint(
                    "big_trade",
                    "BIG_TRADE_LEVEL",
                    int(price_tick),
                    int(price_tick),
                    int(price_tick),
                )
                for price_tick in sorted(self.big_trade_levels)
            ]
            categories = {"market": market, "delta_profile": delta, "big_trade": big}
            signature = tuple(
                _point_signature(point)
                for name in categories
                for point in categories[name]
            )
        selected: dict[str, AoiCandidate] = {}
        for side, direction, anchor in (
            ("VAL", "long", int(profile["val_tick"])),
            ("VAH", "short", int(profile["vah_tick"])),
        ):
            current = self.lineages[side]
            if (
                current is not None
                and current.visit is not None
                and current.candidate.low_tick <= anchor <= current.candidate.high_tick
            ):
                selected[side] = current.candidate
                self.diagnostics["aoi_cache_hits"] += 1
                continue
            key = (
                anchor,
                self.cfg.max_aoi_width_ticks,
                signature,
            )
            if self._candidate_cache_keys[side] == key:
                candidate = self._candidate_cache[side]
                self.diagnostics["aoi_cache_hits"] += 1
            else:
                shared_key = (side, direction, *key)
                if tape is not None and shared_key in tape.candidate_cache:
                    candidate = tape.candidate_cache[shared_key]
                else:
                    candidate = _best_local_cluster_aoi(
                        side,
                        direction,
                        anchor,
                        categories,
                        self.cfg.max_aoi_width_ticks,
                    )
                    if tape is not None:
                        tape.candidate_cache[shared_key] = candidate
                self._candidate_cache_keys[side] = key
                self._candidate_cache[side] = candidate
                self.diagnostics["aoi_cache_misses"] += 1
            if candidate is not None:
                selected[side] = candidate
        return selected

    def _apply_candidate(self, side: str, candidate: AoiCandidate | None, timestamp_ns: int, event_index: int) -> None:
        current = self.lineages[side]
        if current is not None and current.visit is not None:
            anchor = self._current_anchor(side)
            if anchor is not None and current.candidate.low_tick <= anchor <= current.candidate.high_tick:
                return
            self.lineages[side] = None
            self.diagnostics["aoi_anchor_invalidations"] += 1
            current = None
        if candidate is None:
            self.lineages[side] = None
            return
        if current is not None and _aoi_fingerprint(current.candidate) == _aoi_fingerprint(candidate):
            current.candidate = candidate
            return
        if current is not None:
            self.diagnostics["aoi_fingerprint_resets"] += 1
        self.lineage_counter += 1
        self.lineages[side] = AoiLineage(
            lineage_id=self.lineage_counter,
            candidate=candidate,
            eligible_at_ns=timestamp_ns,
            eligible_event_index=event_index,
        )
        self.diagnostics["aoi_eligible_events"] += 1

    def _current_anchor(self, side: str) -> int | None:
        if self.current_profile is None:
            return None
        return int(self.current_profile["val_tick" if side == "VAL" else "vah_tick"])

    def _update_visit_and_order(self, lineage: AoiLineage, index: int) -> None:
        timestamp_ns = int(self.timestamp_ns[index])
        price_tick = int(self.price_ticks[index])
        candidate = lineage.candidate
        if lineage.visit is None:
            if timestamp_ns <= lineage.eligible_at_ns or index <= 0:
                return
            previous_index = self.previous_decision_event_index
            if previous_index is None or previous_index >= index:
                return
            previous_tick = int(self.price_ticks[previous_index])
            approached = (
                previous_tick > candidate.high_tick and price_tick <= candidate.high_tick
                if candidate.direction == "long"
                else previous_tick < candidate.low_tick and price_tick >= candidate.low_tick
            )
            if not approached:
                if candidate.low_tick <= price_tick <= candidate.high_tick:
                    self.diagnostics["wrong_approach_rejections"] += 1
                return
            lineage.visit = Visit(timestamp_ns, index, candidate.low_tick, candidate.high_tick)
            self.diagnostics["taps"] += 1
            return

        visit = lineage.visit
        if timestamp_ns <= visit.tapped_at_ns:
            return
        bubble = self._qualifying_entry_bubble(candidate, visit.tapped_event_index, index)
        if bubble is not None and lineage.pending is None and self._preorder_range_gate(index, lineage):
            entry_tick = _entry_tick(candidate, self.cfg.entry_offset_ticks)
            structural_stop = (
                candidate.low_tick - self.cfg.stop_offset_ticks
                if candidate.direction == "long"
                else candidate.high_tick + self.cfg.stop_offset_ticks
            )
            stop_tick = (
                min(structural_stop, entry_tick - self.cfg.minimum_stop_ticks)
                if candidate.direction == "long"
                else max(structural_stop, entry_tick + self.cfg.minimum_stop_ticks)
            )
            lineage.pending = PendingOrder(
                trigger_kind=bubble["kind"],
                bubble_qualified_at_ns=int(bubble["qualified_at_ns"]),
                bubble_event_index=int(bubble["qualified_event_index"]),
                armed_at_ns=timestamp_ns,
                armed_event_index=index,
                entry_tick=entry_tick,
                stop_tick=stop_tick,
                bubble_price_tick=int(bubble["price_tick"]),
                bubble_bar_id=bubble.get("bar_id"),
                bubble_bucket=bubble.get("bucket"),
                bubble_value=int(bubble["value"]),
            )
            self.diagnostics["orders_armed"] += 1

        hypothetical_entry = _entry_tick(candidate, self.cfg.entry_offset_ticks)
        if _entry_crossed(candidate.direction, hypothetical_entry, price_tick) and visit.confirmed_at_ns is None:
            visit.confirmed_at_ns = timestamp_ns
            self.reversals[candidate.side].append(
                Visit(visit.tapped_at_ns, visit.tapped_event_index, visit.low_tick, visit.high_tick, timestamp_ns)
            )
            if lineage.pending is None:
                lineage.visit = None

    def _qualifying_entry_bubble(self, candidate: AoiCandidate, tap_event_index: int, index: int) -> dict | None:
        timestamp_ns = int(self.timestamp_ns[index])
        price_tick = int(self.price_ticks[index])
        bar_id = self._bar_id(timestamp_ns)
        bucket = math.floor(price_tick / 4)
        value = int(self.decision_bar_delta_values.get(bucket, 0))
        crossed_at = self.delta_threshold_crossings.get((bar_id, bucket))
        if (
            crossed_at is not None
            and tap_event_index < crossed_at <= index
            and abs(value) >= self.cfg.delta_bubble_threshold
            and _price_in_or_beyond(candidate, bucket * 4, bucket * 4 + 3)
        ):
            self.diagnostics["delta_bubbles"] += 1
            return {
                "kind": "delta_4tick_3m",
                "price_tick": price_tick,
                "bar_id": bar_id,
                "bucket": bucket,
                "value": value,
                "qualified_at_ns": int(self.timestamp_ns[crossed_at]),
                "qualified_event_index": crossed_at,
            }
        eligible = [
            item
            for item in self.big_trade_occurrences
            if tap_event_index < int(item["qualified_event_index"]) <= index
            and _point_in_or_beyond(candidate, int(item["price_tick"]))
        ]
        if eligible:
            item = max(eligible, key=lambda value: int(value["qualified_event_index"]))
            self.diagnostics["big_trade_bubbles"] += 1
            return {
                "kind": "big_trade_100ms",
                "price_tick": int(item["price_tick"]),
                "value": int(item["volume"]),
                "qualified_at_ns": int(item["qualified_at_ns"]),
                "qualified_event_index": int(item["qualified_event_index"]),
            }
        return None

    def _pending_is_live(self, pending: PendingOrder, candidate: AoiCandidate, index: int) -> bool:
        anchor = self._current_anchor(candidate.side)
        if anchor is None or not candidate.low_tick <= anchor <= candidate.high_tick:
            return False
        if pending.trigger_kind == "big_trade_100ms":
            return True
        decision_index = self.decision_event_index
        if (
            decision_index is None
            or pending.bubble_bucket is None
            or pending.bubble_bar_id != self._bar_id(int(self.timestamp_ns[decision_index]))
        ):
            return False
        value = int(self.decision_bar_delta_values.get(pending.bubble_bucket, 0))
        return abs(value) >= self.cfg.delta_bubble_threshold

    def _preorder_range_gate(self, index: int, lineage: AoiLineage) -> bool:
        return self._range_and_profile_pass(index) and self._has_prior_reversal(index, lineage)

    def _range_and_profile_pass(self, index: int) -> bool:
        if self.current_profile is None or index <= 0:
            return False
        low = int(self.cumulative_low[index])
        high = int(self.cumulative_high[index])
        width = high - low
        poc = int(self.current_profile["poc_tick"])
        return width > 0 and low + width / 3.0 <= poc <= low + 2.0 * width / 3.0

    def _has_prior_reversal(self, index: int, lineage: AoiLineage) -> bool:
        candidate = lineage.candidate
        return any(
            visit.confirmed_at_ns is not None
            and visit.tapped_event_index < index
            and (lineage.visit is None or visit.tapped_at_ns != lineage.visit.tapped_at_ns)
            and _overlap(visit.low_tick, visit.high_tick, candidate.low_tick, candidate.high_tick)
            for visit in self.reversals[candidate.side]
        )

    def _fill_gate_passes(self, index: int, lineage: AoiLineage) -> bool:
        pending = lineage.pending
        profile = self.current_profile
        if pending is None or profile is None:
            return False
        candidate = lineage.candidate
        anchor = self._current_anchor(candidate.side)
        if anchor is None or not candidate.low_tick <= anchor <= candidate.high_tick:
            return False
        if self.required_direction and candidate.direction != self.required_direction:
            return False
        if not self._range_and_profile_pass(index) or not self._has_prior_reversal(index, lineage):
            return False
        event_tick = int(self.price_ticks[index])
        reference_fill = (
            max(pending.entry_tick, event_tick) + self.cfg.slippage_ticks
            if candidate.direction == "long"
            else min(pending.entry_tick, event_tick) - self.cfg.slippage_ticks
        )
        midpoint = (int(profile["vah_tick"]) + int(profile["val_tick"])) / 2.0
        favorable_distance = (
            midpoint - reference_fill
            if candidate.direction == "long"
            else reference_fill - midpoint
        )
        if favorable_distance <= self.cfg.breakeven_offset_ticks:
            self.diagnostics["midpoint_distance_rejections"] += 1
            return False
        risk_ticks = (
            reference_fill - pending.stop_tick
            if candidate.direction == "long"
            else pending.stop_tick - reference_fill
        )
        if risk_ticks <= 0 or risk_ticks > self.cfg.max_stop_ticks:
            self.diagnostics["stop_limit_rejections"] += 1
            return False
        return True


def build_session_feature_tape(
    session: CanonicalEventSession,
    config: YushOrderflowRangeConfig,
) -> YushSessionFeatureTape:
    """Build parameter-invariant causal market state once for a grid session."""

    state = _YushOrderflowRangeState(session.public_view(), config)
    events = session.events
    timestamp_values = events["timestamp"].array
    timestamp_ns = events["_canonical_timestamp_ns"].to_numpy(dtype=np.int64, copy=False)
    source_ordinals = events["source_ordinal"].to_numpy(dtype=np.int64, copy=False)
    price_ticks = events["event_price_tick"].to_numpy(dtype=np.int64, copy=False)
    sizes = events["size"].to_numpy(dtype=np.int64, copy=False)
    sides = events["side"].astype(str).to_numpy(copy=False)
    signed = events["signed_size"].to_numpy(dtype=np.int64, copy=False)
    snapshots: dict[int, YushDecisionFeatureSnapshot] = {}
    previous_crossings: dict[tuple[int, int], int] = {}
    previous_occurrence_count = 0
    previous_level_keys: set[int] = set()
    candidate_signature_ids: dict[tuple, int] = {}

    index = 0
    while index < len(events):
        if state.active_decision_bucket is not None:
            first_bucket = int(
                (int(timestamp_ns[index]) - state.open_ns) // state.decision_interval_ns
            )
            if first_bucket == state.active_decision_bucket:
                boundary_ns = state.open_ns + (first_bucket + 1) * state.decision_interval_ns
                stop = min(
                    len(events),
                    int(np.searchsorted(timestamp_ns, boundary_ns, side="left")),
                )
                if stop > index:
                    state._ingest_idle_batch(
                        CanonicalEventBatch(
                            start_event_index=index,
                            stop_event_index=stop,
                            timestamp_ns=timestamp_ns[index:stop],
                            price_ticks=price_ticks[index:stop],
                            sizes=sizes[index:stop],
                            sides=sides[index:stop],
                            signed_sizes=signed[index:stop],
                        )
                    )
                    index = stop
                    continue
        event = CanonicalEvent(
            event_index=index,
            timestamp=pd.Timestamp(timestamp_values[index]),
            timestamp_ns=int(timestamp_ns[index]),
            source_ordinal=int(source_ordinals[index]),
            price=float(price_ticks[index]) * config.tick_size,
            price_tick=int(price_ticks[index]),
            size=int(sizes[index]),
            side=str(sides[index]),
            signed_size=int(signed[index]),
        )
        state.last_timestamp_ns = event.timestamp_ns
        state._ingest_event(event)
        if state.decision_due:
            market = tuple(state._market_confluences())
            delta = tuple(state._delta_confluences())
            big = tuple(
                ConfluencePoint(
                    "big_trade",
                    "BIG_TRADE_LEVEL",
                    int(price_tick),
                    int(price_tick),
                    int(price_tick),
                )
                for price_tick in sorted(state.big_trade_levels)
            )
            candidate_categories = {
                "market": market,
                "delta_profile": delta,
                "big_trade": big,
            }
            candidate_signature = tuple(
                _point_signature(point)
                for name in candidate_categories
                for point in candidate_categories[name]
            )
            candidate_signature_id = candidate_signature_ids.setdefault(
                candidate_signature,
                len(candidate_signature_ids),
            )
            crossing_updates = {
                key: int(value)
                for key, value in state.delta_threshold_crossings.items()
                if previous_crossings.get(key) != int(value)
            }
            new_occurrences = tuple(
                dict(value)
                for value in state.big_trade_occurrences[previous_occurrence_count:]
            )
            new_levels = tuple(
                (int(key), dict(state.big_trade_levels[key]))
                for key in sorted(set(state.big_trade_levels) - previous_level_keys)
            )
            snapshots[index] = YushDecisionFeatureSnapshot(
                event_index=int(state.decision_event_index),
                previous_decision_event_index=state.previous_decision_event_index,
                current_profile=(
                    None if state.current_profile is None else dict(state.current_profile)
                ),
                decision_bar_delta_values=dict(state.decision_bar_delta_values),
                crossing_updates=crossing_updates,
                qualified_delta_four=frozenset(state.qualified_delta_four),
                new_big_trade_occurrences=new_occurrences,
                new_big_trade_levels=new_levels,
                or_high_tick=state.or_high_tick,
                or_low_tick=state.or_low_tick,
                candidate_categories=candidate_categories,
                candidate_signature_id=candidate_signature_id,
            )
            previous_crossings.update(crossing_updates)
            previous_occurrence_count = len(state.big_trade_occurrences)
            previous_level_keys = set(state.big_trade_levels)
        index += 1

    count = len(events)
    neutral = np.cumsum((sides != "A") & (sides != "B"), dtype=np.int64)
    arrays = [
        timestamp_ns.copy(),
        price_ticks.copy(),
        state.cumulative_low[:count].copy(),
        state.cumulative_high[:count].copy(),
        neutral,
    ]
    for value in arrays:
        value.setflags(write=False)
    return YushSessionFeatureTape(
        session_date=session.session_date,
        timestamp_ns=arrays[0],
        price_ticks=arrays[1],
        cumulative_low=arrays[2],
        cumulative_high=arrays[3],
        neutral_cumulative=arrays[4],
        completed_bars=tuple(state.completed_bars),
        decision_snapshots=snapshots,
    )


class YushOrderflowRangeEventStrategy(ExactYushRangeEventStrategy):
    def __init__(self, config: YushOrderflowRangeConfig | None = None):
        super().__init__(config or YushOrderflowRangeConfig(), news_events_by_session={})
        self.cfg: YushOrderflowRangeConfig
        self._session_feature_tapes: dict[str, YushSessionFeatureTape] = {}

    def prepare_session_features(
        self,
        session: CanonicalEventSession,
    ) -> YushSessionFeatureTape:
        return build_session_feature_tape(session, self.cfg)

    def bind_session_features(
        self,
        values: dict[str, YushSessionFeatureTape],
    ) -> None:
        self._session_feature_tapes = dict(values)

    def on_session_start(self, session: EventReplaySessionView, broker: EventReplayBroker) -> None:
        self.state = _YushOrderflowRangeState(session, self.cfg)
        tape = self._session_feature_tapes.get(str(session.session_date))
        if tape is not None:
            self._state().bind_feature_tape(tape)

    def on_event_start(self, event: CanonicalEvent, broker: EventReplayBroker) -> None:
        del broker
        self._state().advance_feature_event(event)

    def pre_execution_required(self, event: CanonicalEvent) -> bool:
        del event
        return False

    def validate_entry_order_without_crossing(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
    ) -> bool:
        del order, event
        return bool(self._state().decision_due)

    def after_event_required(
        self,
        event: CanonicalEvent,
        *,
        closed_this_event: bool,
        opened_this_event: bool,
        entries_blocked: bool,
    ) -> bool:
        del event, entries_blocked
        return bool(
            closed_this_event
            or opened_this_event
            or self._state().decision_due
        )

    def idle_batch_stop(
        self,
        timestamp_ns: np.ndarray,
        *,
        start: int,
        stop: int,
    ) -> int:
        state = self._state()
        if state.active_decision_bucket is None or start >= stop:
            return start
        if state.feature_tape is not None:
            if state._feature_decision_cursor >= len(state._feature_decision_indices):
                return stop
            boundary = state._feature_decision_indices[state._feature_decision_cursor]
            return min(stop, boundary) if boundary > start else start
        first_bucket = int(
            (int(timestamp_ns[start]) - state.open_ns) // state.decision_interval_ns
        )
        if first_bucket != state.active_decision_bucket:
            return start
        boundary_ns = state.open_ns + (first_bucket + 1) * state.decision_interval_ns
        return min(stop, int(np.searchsorted(timestamp_ns, boundary_ns, side="left")))

    def on_idle_event_batch(
        self,
        batch: CanonicalEventBatch,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        self._state().advance_feature_batch(batch)

    def pending_order_batch_stop(
        self,
        price_ticks: np.ndarray,
        *,
        start: int,
        stop: int,
        orders: tuple[EventEntryOrder, ...],
    ) -> int:
        boundary = int(stop)
        for order in orders:
            active_start = max(int(start), int(order.active_from_event_index))
            if active_start >= boundary:
                continue
            values = price_ticks[active_start:boundary]
            crossed = (
                values >= int(order.entry_tick)
                if order.direction == "long"
                else values <= int(order.entry_tick)
            )
            locations = np.flatnonzero(crossed)
            if len(locations):
                boundary = min(boundary, active_start + int(locations[0]))
        return boundary

    def position_batch_stop(
        self,
        price_ticks: np.ndarray,
        *,
        start: int,
        stop: int,
        position: EventPositionView,
    ) -> int:
        boundary = int(stop)

        def first_crossing(values: np.ndarray, crossed: np.ndarray, offset: int) -> None:
            nonlocal boundary
            locations = np.flatnonzero(crossed)
            if len(locations):
                boundary = min(boundary, offset + int(locations[0]))

        active_start = max(int(start), int(position.bracket_active_from_event_index))
        if active_start < boundary:
            values = price_ticks[active_start:boundary]
            if position.direction == "long":
                first_crossing(
                    values,
                    values <= int(position.stop_tick),
                    active_start,
                )
                if position.target_tick is not None:
                    first_crossing(
                        values,
                        values >= int(position.target_tick),
                        active_start,
                    )
            else:
                first_crossing(
                    values,
                    values >= int(position.stop_tick),
                    active_start,
                )
                if position.target_tick is not None:
                    first_crossing(
                        values,
                        values <= int(position.target_tick),
                        active_start,
                    )

        midpoint_price = position.report_fields.get("entry_midpoint_price")
        midpoint = (
            None
            if midpoint_price is None
            else float(midpoint_price) / self.cfg.tick_size
        )
        if (
            not bool(position.report_fields.get("midpoint_activated"))
            and midpoint is not None
            and int(start) < boundary
        ):
            values = price_ticks[int(start):boundary]
            first_crossing(
                values,
                values >= float(midpoint)
                if position.direction == "long"
                else values <= float(midpoint),
                int(start),
            )
        return boundary

    def entry_fill_allowed(self, order: EventEntryOrder, event: CanonicalEvent, broker: EventReplayBroker) -> bool:
        lineage = self._lineage_for_order(order)
        return bool(lineage is not None and lineage.pending is not None and self._state()._fill_gate_passes(event.event_index, lineage))

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        if state.current_profile is None:
            raise AssertionError("Entry profile must exist at fill.")
        lineage = self._lineage_for_order(order)
        if lineage is None:
            raise AssertionError("Entry AOI lineage must exist at fill.")
        fingerprint = _format_aoi_fingerprint(
            _aoi_fingerprint(lineage.candidate),
            self.cfg.tick_size,
        )
        midpoint_tick = (int(state.current_profile["vah_tick"]) + int(state.current_profile["val_tick"])) / 2.0
        super().on_entry_filled(order, position, event, broker)
        source_quality_label = str(
            state.session.metadata.get(
                "source_quality_label",
                "Governed canonical trade events; source identity is recorded in the attempt data manifest.",
            )
        )
        broker.annotate_position(
            entry_midpoint_price=midpoint_tick * self.cfg.tick_size,
            aoi_lineage_mode=self.cfg.aoi_lineage_mode,
            aoi_exact_fingerprint=fingerprint,
            source_quality_label=source_quality_label,
            fill_model="trade_event_stop_market_with_one_tick_adverse_slippage_and_five_point_stop_limit",
        )

    def position_directive(
        self,
        event: CanonicalEvent,
        position: EventPositionView,
        broker: EventReplayBroker,
    ) -> PositionDirective:
        state = self._state()
        if bool(position.report_fields.get("midpoint_activated")) or state.current_profile is None:
            return PositionDirective()
        midpoint = (
            float(position.report_fields["entry_midpoint_price"])
            / self.cfg.tick_size
        )
        reached = event.price_tick >= midpoint if position.direction == "long" else event.price_tick <= midpoint
        if not reached:
            return PositionDirective()
        actual_entry_tick = int(round(position.entry_price / self.cfg.tick_size))
        stop_tick = (
            actual_entry_tick + self.cfg.breakeven_offset_ticks
            if position.direction == "long"
            else actual_entry_tick - self.cfg.breakeven_offset_ticks
        )
        target_tick = (
            int(state.current_profile["vah_tick"])
            if position.direction == "long"
            else int(state.current_profile["val_tick"])
        )
        valid = target_tick > position.entry_reference_tick if position.direction == "long" else target_tick < position.entry_reference_tick
        if not valid:
            return PositionDirective(flatten_reason="invalid_target_guard", flatten_tick=event.price_tick)
        target_crossed = event.price_tick >= target_tick if position.direction == "long" else event.price_tick <= target_tick
        report = {
            "midpoint_activated": True,
            "midpoint_activated_at": pd.Timestamp(event.timestamp),
            "managed_target_already_reached_at_activation": target_crossed,
        }
        if target_crossed:
            return PositionDirective(immediate_target_tick=target_tick, report_fields=report)
        bracket_ordered = target_tick > stop_tick if position.direction == "long" else target_tick < stop_tick
        if not bracket_ordered:
            state.diagnostics["target_guard_exits"] += 1
            return PositionDirective(
                flatten_reason="invalid_target_guard",
                flatten_tick=event.price_tick,
                report_fields=report,
            )
        return PositionDirective(
            stop_tick=stop_tick,
            target_tick=target_tick,
            stop_exit_reason="managed_stop",
            report_fields=report,
        )

    def on_position_closed(self, position: EventPositionView, trade: dict, broker: EventReplayBroker) -> None:
        self._state().required_direction = (
            "short" if position.direction == "long" else "long"
        ) if float(trade["net_pnl"]) < 0 else None

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
            broker.cancel_all_entries(reason="position_opened_cancel_other_entries")
            return
        if closed_this_event:
            broker.cancel_all_entries(reason="position_closed_fresh_aoi_required")
            state.lineages = {"VAL": None, "VAH": None}
            return
        if not state.decision_due or state.decision_event_index is None:
            return
        daily_limit_reached = (
            self.cfg.max_trades_per_day > 0
            and broker.trades_today >= self.cfg.max_trades_per_day
        )
        if broker.position is not None or daily_limit_reached:
            return

        candidates = state._selected_candidates()
        for side in ("VAL", "VAH"):
            self._apply_candidate_and_sync(side, candidates.get(side), event, broker)
        if entries_blocked:
            return
        for side in ("VAL", "VAH"):
            lineage = state.lineages[side]
            if lineage is None or lineage.locked:
                continue
            pending_before = lineage.pending
            state._update_visit_and_order(lineage, state.decision_event_index)
            if lineage.pending is not None and lineage.pending is not pending_before:
                self._sync_pending_order(side, lineage, broker)

    def _state(self) -> _YushOrderflowRangeState:
        state = self.state
        if state is None:
            raise RuntimeError("Yush event strategy has not started a session.")
        return state

    def _apply_candidate_and_sync(
        self,
        side: str,
        candidate: AoiCandidate | None,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        current = state.lineages[side]
        had_pending = bool(current is not None and current.pending is not None)
        decision_index = state.decision_event_index
        if decision_index is None:
            return
        state._apply_candidate(
            side,
            candidate,
            int(state.timestamp_ns[decision_index]),
            decision_index,
        )
        updated = state.lineages[side]
        lineage_replaced = bool(
            current is not None
            and (updated is None or updated.lineage_id != current.lineage_id)
        )
        if had_pending and lineage_replaced:
            broker.cancel_entry(side, reason="aoi_invalidated_or_replaced")
        elif updated is not None and updated.pending is not None:
            self._sync_pending_order(side, updated, broker)


def _aoi_fingerprint(candidate: AoiCandidate) -> tuple:
    """Identify one exact tradable AOI without treating geometric overlap as sameness."""

    confluences = tuple(
        (
            point.category,
            point.level_type,
            point.point_tick,
            point.interval_low_tick,
            point.interval_high_tick,
        )
        for point in candidate.confluences
    )
    return (
        candidate.side,
        candidate.direction,
        candidate.low_tick,
        candidate.high_tick,
        candidate.categories,
        confluences,
    )


def _format_aoi_fingerprint(
    fingerprint: tuple,
    tick_size: float,
) -> str:
    side, direction, low, high, categories, confluences = fingerprint
    category_text = ",".join(categories)
    low_price = _format_point_price(low, tick_size)
    high_price = _format_point_price(high, tick_size)
    confluence_text = ";".join(
        (
            f"{category}:{level_type}:"
            f"{_format_point_price(point_tick, tick_size)}:"
            f"{_format_point_price(interval_low, tick_size)}-"
            f"{_format_point_price(interval_high, tick_size)}"
        )
        for category, level_type, point_tick, interval_low, interval_high in confluences
    )
    return (
        f"{side}|{direction}|{low_price}-{high_price}|"
        f"{category_text}|{confluence_text}"
    )


def _point_signature(point: ConfluencePoint) -> tuple:
    return (
        point.category,
        point.level_type,
        point.point_tick,
        point.interval_low_tick,
        point.interval_high_tick,
    )


def _best_local_cluster_aoi(
    side: str,
    direction: str,
    anchor_tick: int,
    categories: dict[str, list[ConfluencePoint]],
    max_width_ticks: int,
) -> AoiCandidate | None:
    """Choose a bounded price-local category cluster without occurrence ranking."""

    local = {
        name: tuple(
            point
            for point in points
            if max(anchor_tick, point.interval_high_tick) - min(anchor_tick, point.interval_low_tick)
            <= max_width_ticks
        )
        for name, points in categories.items()
    }
    if not any(local.values()):
        return None

    best: tuple[tuple, tuple[str, ...], tuple[ConfluencePoint, ...], int, int] | None = None
    for low in range(anchor_tick - max_width_ticks, anchor_tick + 1):
        for high in range(anchor_tick, min(anchor_tick + max_width_ticks, low + max_width_ticks) + 1):
            selected_by_category = {
                name: tuple(
                    point
                    for point in points
                    if low <= point.interval_low_tick and point.interval_high_tick <= high
                )
                for name, points in local.items()
            }
            names = tuple(name for name in categories if selected_by_category[name])
            if not names:
                continue
            selected = tuple(
                point
                for name in names
                for point in selected_by_category[name]
            )
            canonical = tuple(_point_signature(point) for point in selected)
            key = (
                -len(names),
                high - low,
                abs((low + high) / 2.0 - anchor_tick),
                low,
                high,
                canonical,
            )
            if best is None or key < best[0]:
                best = (key, names, selected, low, high)
    if best is None:
        return None
    _, names, selected, low, high = best
    return AoiCandidate(side, direction, anchor_tick, low, high, names, selected)
