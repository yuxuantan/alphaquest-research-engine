"""Frozen event strategy for the Yush order-flow range-reversal specification."""

from __future__ import annotations

from dataclasses import dataclass, fields
from itertools import combinations, product
import math
import pandas as pd

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
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
            self.opening_range_seconds,
            self.bar_seconds,
        ) <= 0:
            raise ValueError("order-flow thresholds and aggregation windows must be positive")

    @property
    def minimum_stop_ticks(self) -> int:
        return int(round(self.minimum_stop_points / self.tick_size))

    @property
    def max_stop_ticks(self) -> int:
        return int(round(self.max_stop_points / self.tick_size))

    @property
    def breakeven_offset_ticks(self) -> int:
        return int(round(self.breakeven_offset_points / self.tick_size))


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
        self.delta_threshold_crossings: dict[tuple[int, int], int] = {}
        self.diagnostics.update(
            {
                "aoi_anchor_invalidations": 0,
                "aoi_fingerprint_resets": 0,
                "wrong_approach_rejections": 0,
                "midpoint_distance_rejections": 0,
                "stop_limit_rejections": 0,
            }
        )

    def _update_market_state(self, index: int, volume: int, signed: int) -> None:
        price_tick = int(self.price_ticks[index])
        bucket = math.floor(price_tick / 4)
        before = 0
        if self.base_four is not None and self.base_four <= bucket <= int(self.top_four):
            before = int(self.bar_delta_four[bucket - int(self.base_four)])
        super()._update_market_state(index, volume, signed)
        after = int(self.bar_delta_four[bucket - int(self.base_four)])
        threshold = self.cfg.delta_bubble_threshold
        if abs(before) < threshold <= abs(after):
            self.delta_threshold_crossings[(self._bar_id(int(self.timestamp_ns[index])), bucket)] = index

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
        for center in range(four_bucket - 2, four_bucket + 3):
            if self._delta_level_qualifies(self.delta_four, self.traded_four, center, int(self.base_four)):
                self.qualified_delta_four.add(center)
            else:
                self.qualified_delta_four.discard(center)
        self.qualified_delta_one.clear()

    def _update_big_trade(self, index: int, side: str, size: int) -> None:
        timestamp_ns = int(self.timestamp_ns[index])
        price_tick = int(self.price_ticks[index])
        anchor = self.big_anchor
        same_occurrence = bool(
            anchor is not None
            and timestamp_ns - int(anchor["started_at_ns"]) <= self.cfg.big_trade_window_ms * 1_000_000
            and price_tick == int(anchor["price_tick"])
            and side == anchor["side"]
        )
        if not same_occurrence:
            anchor = {
                "started_at_ns": timestamp_ns,
                "price_tick": price_tick,
                "side": side,
                "volume": size,
                "qualified": False,
            }
            self.big_anchor = anchor
        else:
            anchor["volume"] += size
        if side in {"A", "B"} and not anchor["qualified"] and int(anchor["volume"]) > self.cfg.big_trade_threshold:
            anchor["qualified"] = True
            occurrence = {
                "occurrence_id": len(self.big_trade_occurrences) + 1,
                "qualified_at_ns": timestamp_ns,
                "qualified_event_index": index,
                "price_tick": price_tick,
                "side": side,
                "volume": int(anchor["volume"]),
            }
            self.big_trade_occurrences.append(occurrence)

    def _delta_confluences(self) -> list[ConfluencePoint]:
        ranked = sorted(
            self.qualified_delta_four,
            key=lambda bucket: (-abs(int(self.delta_four[bucket - int(self.base_four)])), bucket),
        )
        return [
            ConfluencePoint("delta_profile", "DELTA_4T_LOCAL_PROMINENCE", bucket * 4, bucket * 4, bucket * 4 + 3)
            for bucket in ranked
        ]

    def _selected_candidates(self) -> dict[str, AoiCandidate]:
        profile = self.current_profile
        if profile is None:
            return {}
        market = self._market_confluences()
        delta = self._delta_confluences()
        big = [
            ConfluencePoint(
                "big_trade",
                f"BIG_TRADE_{item['occurrence_id']}",
                int(item["price_tick"]),
                int(item["price_tick"]),
                int(item["price_tick"]),
            )
            for item in self.big_trade_occurrences
        ]
        categories = {"market": market, "delta_profile": delta, "big_trade": big}
        selected: dict[str, AoiCandidate] = {}
        for side, direction, anchor in (
            ("VAL", "long", int(profile["val_tick"])),
            ("VAH", "short", int(profile["vah_tick"])),
        ):
            candidate = _best_refined_aoi(side, direction, anchor, categories, self.cfg.max_aoi_width_ticks)
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
            previous_tick = int(self.price_ticks[index - 1])
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
        value = int(self.bar_delta_four[bucket - int(self.base_four)])
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
        if pending.bubble_bucket is None or pending.bubble_bar_id != self._bar_id(int(self.timestamp_ns[index])):
            return False
        value = int(self.bar_delta_four[pending.bubble_bucket - int(self.base_four)])
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


class YushOrderflowRangeEventStrategy(ExactYushRangeEventStrategy):
    def __init__(self, config: YushOrderflowRangeConfig | None = None):
        super().__init__(config or YushOrderflowRangeConfig(), news_events_by_session={})
        self.cfg: YushOrderflowRangeConfig

    def on_session_start(self, session: EventReplaySessionView, broker: EventReplayBroker) -> None:
        self.state = _YushOrderflowRangeState(session, self.cfg)

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
        fingerprint = _format_aoi_fingerprint(_aoi_fingerprint(lineage.candidate))
        midpoint_tick = (int(state.current_profile["vah_tick"]) + int(state.current_profile["val_tick"])) / 2.0
        super().on_entry_filled(order, position, event, broker)
        broker.annotate_position(
            entry_midpoint_tick=midpoint_tick,
            aoi_lineage_mode=self.cfg.aoi_lineage_mode,
            aoi_exact_fingerprint=fingerprint,
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
        midpoint = float(position.report_fields["entry_midpoint_tick"])
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
        super().after_event(
            event,
            broker,
            closed_this_event=False,
            opened_this_event=False,
            entries_blocked=entries_blocked,
        )

    def _state(self) -> _YushOrderflowRangeState:
        state = super()._state()
        if not isinstance(state, _YushOrderflowRangeState):
            raise TypeError("The revised strategy requires its revised session state.")
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
        state._apply_candidate(side, candidate, event.timestamp_ns, event.event_index)
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


def _format_aoi_fingerprint(fingerprint: tuple) -> str:
    side, direction, low, high, categories, confluences = fingerprint
    category_text = ",".join(categories)
    confluence_text = ";".join(
        f"{category}:{level_type}:{point_tick}:{interval_low}-{interval_high}"
        for category, level_type, point_tick, interval_low, interval_high in confluences
    )
    return f"{side}|{direction}|{low}-{high}|{category_text}|{confluence_text}"


def _best_refined_aoi(
    side: str,
    direction: str,
    anchor_tick: int,
    categories: dict[str, list[ConfluencePoint]],
    max_width_ticks: int,
) -> AoiCandidate | None:
    """Pick most categories, then narrowest envelope, then closest to anchor."""

    populated = tuple(name for name, points in categories.items() if points)
    for category_count in range(len(populated), 0, -1):
        choices = []
        for names in combinations(populated, category_count):
            for selected in product(*(categories[name] for name in names)):
                low = min(anchor_tick, *(point.interval_low_tick for point in selected))
                high = max(anchor_tick, *(point.interval_high_tick for point in selected))
                if high - low > max_width_ticks:
                    continue
                confluence_distance = sum(
                    0
                    if point.interval_low_tick <= anchor_tick <= point.interval_high_tick
                    else min(
                        abs(anchor_tick - point.interval_low_tick),
                        abs(anchor_tick - point.interval_high_tick),
                    )
                    for point in selected
                )
                preference_ranks = tuple(categories[name].index(point) for name, point in zip(names, selected, strict=True))
                canonical = tuple(
                    (point.category, point.level_type, point.point_tick, point.interval_low_tick, point.interval_high_tick)
                    for point in selected
                )
                key = (
                    high - low,
                    confluence_distance,
                    abs((low + high) / 2.0 - anchor_tick),
                    preference_ranks,
                    low,
                    canonical,
                )
                choices.append((key, names, selected, low, high))
        if choices:
            _, names, selected, low, high = min(choices, key=lambda item: item[0])
            return AoiCandidate(side, direction, anchor_tick, low, high, tuple(names), tuple(selected))
    return None
