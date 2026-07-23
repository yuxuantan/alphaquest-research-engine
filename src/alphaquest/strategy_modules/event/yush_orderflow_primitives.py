from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import math
import numpy as np
import pandas as pd

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    CanonicalEventReplayStrategy,
    EventEntryOrder,
    EventPositionView,
    EventPreExecution,
    EventReplayBroker,
    EventReplaySessionView,
    PositionDirective,
)
from alphaquest.backtest.metrics import daily_results


@dataclass(frozen=True)
class ExactYushRangeConfig:
    tick_size: float = 0.25
    point_value: float = 50.0
    contracts: int = 1
    commission_per_contract: float = 2.50
    max_trades_per_day: int = 3
    max_aoi_width_points: float = 3.0
    entry_offset_ticks: int = 2
    stop_offset_ticks: int = 2
    max_stop_points: float = 5.0
    value_area_fraction: float = 0.70
    range_expansion_fraction: float = 0.20
    delta_profile_min_abs: int = 300
    delta_bubble_threshold: int = 300
    big_trade_threshold: int = 200
    big_trade_window_ms: int = 100
    breakeven_offset_points: float = 1.25
    opening_range_seconds: int = 32
    bar_seconds: int = 180
    breakout_probe_ticks: int = 2
    initial_balance: float = 50_000.0

    @property
    def max_aoi_width_ticks(self) -> int:
        return int(round(self.max_aoi_width_points / self.tick_size))

@dataclass(frozen=True)
class ConfluencePoint:
    category: str
    level_type: str
    point_tick: int
    interval_low_tick: int
    interval_high_tick: int


@dataclass(frozen=True)
class AoiCandidate:
    side: str
    direction: str
    anchor_tick: int
    low_tick: int
    high_tick: int
    categories: tuple[str, ...]
    confluences: tuple[ConfluencePoint, ...]

    @property
    def width_ticks(self) -> int:
        return self.high_tick - self.low_tick


@dataclass
class PendingOrder:
    trigger_kind: str
    bubble_qualified_at_ns: int
    bubble_event_index: int
    armed_at_ns: int
    armed_event_index: int
    entry_tick: int
    stop_tick: int
    bubble_price_tick: int
    bubble_bar_id: int | None = None
    bubble_bucket: int | None = None
    bubble_value: int | None = None


@dataclass
class Visit:
    tapped_at_ns: int
    tapped_event_index: int
    low_tick: int
    high_tick: int
    confirmed_at_ns: int | None = None


@dataclass
class AoiLineage:
    lineage_id: int
    candidate: AoiCandidate
    eligible_at_ns: int
    eligible_event_index: int
    locked: bool = False
    visit: Visit | None = None
    pending: PendingOrder | None = None


class _YushSessionState:
    def __init__(
        self,
        session: EventReplaySessionView,
        config: ExactYushRangeConfig,
        news_releases: tuple[pd.Timestamp, ...] = (),
    ):
        self.session = session
        self.cfg = config
        self.news_release_ns = tuple(sorted(int(pd.Timestamp(value).value) for value in news_releases))
        self.news_reset_done: set[int] = set()
        self.previous_rth = session.metadata.get("previous_rth")
        self.overnight_high = session.metadata.get("overnight_high")
        self.overnight_low = session.metadata.get("overnight_low")
        self._capacity = 4096
        self.event_count = 0
        self.timestamp_ns = np.empty(self._capacity, dtype=np.int64)
        self.price_ticks = np.empty(self._capacity, dtype=np.int64)
        self.cumulative_low = np.empty(self._capacity, dtype=np.int64)
        self.cumulative_high = np.empty(self._capacity, dtype=np.int64)
        self.neutral_side_events = 0
        self.base_tick: int | None = None
        self.top_tick: int | None = None
        self.profile_volume = np.zeros(0, dtype=np.int64)
        self.delta_one = np.zeros(0, dtype=np.int64)
        self.traded_one = np.zeros(0, dtype=np.bool_)
        self.base_four: int | None = None
        self.top_four: int | None = None
        self.delta_four = np.zeros(0, dtype=np.int64)
        self.bar_delta_four = np.zeros(0, dtype=np.int64)
        self.traded_four = np.zeros(0, dtype=np.bool_)
        self.qualified_delta_one: set[int] = set()
        self.qualified_delta_four: set[int] = set()
        self.big_trade_snapshots: dict[int, dict] = {}
        self.big_anchor: dict | None = None
        self.lineages: dict[str, AoiLineage | None] = {"VAL": None, "VAH": None}
        self.lineage_counter = 0
        self.reversals: dict[str, list[Visit]] = {"VAL": [], "VAH": []}
        self.required_direction: str | None = None
        self.observed_low_tick: int | None = None
        self.observed_high_tick: int | None = None
        self.completed_bars: list[tuple[int, int]] = []
        self.current_bar_id: int | None = None
        self.current_bar_last_tick: int | None = None
        self.current_profile: dict | None = None
        self.candidate_fingerprint: tuple | None = None
        self.candidate_cache: dict[str, AoiCandidate] = {}
        self.open_ns = int(pd.Timestamp(f"{session.session_date} 09:30:00", tz="America/New_York").value)
        self.last_timestamp_ns = self.open_ns
        self.opening_range_end_ns = self.open_ns + config.opening_range_seconds * 1_000_000_000
        self.or_high_tick: int | None = None
        self.or_low_tick: int | None = None
        self.diagnostics = {
            "events": 0,
            "neutral_side_events": 0,
            "aoi_eligible_events": 0,
            "taps": 0,
            "delta_bubbles": 0,
            "big_trade_bubbles": 0,
            "orders_armed": 0,
            "fill_gate_rejections": 0,
            "target_guard_exits": 0,
            "news_resets": 0,
            "news_flatten_trades": 0,
        }

    def _ingest_event(self, event: CanonicalEvent) -> None:
        if event.event_index != self.event_count:
            raise AssertionError("Yush event indices must be contiguous from session start.")
        if event.timestamp_ns < self.open_ns:
            raise ValueError("The exact Yush strategy requires replay events at or after the 09:30 RTH anchor.")
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
        self.current_profile = self._profile()

    def _ensure_capacity(self, required: int) -> None:
        if required <= self._capacity:
            return
        new_capacity = self._capacity
        while new_capacity < required:
            new_capacity *= 2
        for name in ("timestamp_ns", "price_ticks", "cumulative_low", "cumulative_high"):
            current = getattr(self, name)
            expanded = np.empty(new_capacity, dtype=np.int64)
            expanded[: self.event_count] = current[: self.event_count]
            setattr(self, name, expanded)
        self._capacity = new_capacity

    def _update_market_state(self, index: int, volume: int, signed: int) -> None:
        price_tick = int(self.price_ticks[index])
        four_bucket = math.floor(price_tick / 4)
        self._ensure_price_capacity(price_tick, four_bucket)
        one_index = price_tick - int(self.base_tick)
        four_index = four_bucket - int(self.base_four)
        self.profile_volume[one_index] += volume
        self.delta_one[one_index] += signed
        self.traded_one[one_index] = True
        self.delta_four[four_index] += signed
        self.bar_delta_four[four_index] += signed
        self.traded_four[four_index] = True
        self.observed_low_tick = price_tick if self.observed_low_tick is None else min(self.observed_low_tick, price_tick)
        self.observed_high_tick = price_tick if self.observed_high_tick is None else max(self.observed_high_tick, price_tick)
        self.cumulative_low[index] = int(self.observed_low_tick)
        self.cumulative_high[index] = int(self.observed_high_tick)
        self._refresh_delta_qualifications(price_tick, four_bucket)
        timestamp_ns = int(self.timestamp_ns[index])
        if timestamp_ns < self.opening_range_end_ns:
            self.or_high_tick = price_tick if self.or_high_tick is None else max(self.or_high_tick, price_tick)
            self.or_low_tick = price_tick if self.or_low_tick is None else min(self.or_low_tick, price_tick)

    def _ensure_price_capacity(self, price_tick: int, four_bucket: int) -> None:
        if self.base_tick is None or self.top_tick is None:
            self.base_tick = price_tick - 64
            self.top_tick = price_tick + 64
            length = self.top_tick - self.base_tick + 1
            self.profile_volume = np.zeros(length, dtype=np.int64)
            self.delta_one = np.zeros(length, dtype=np.int64)
            self.traded_one = np.zeros(length, dtype=np.bool_)
        elif price_tick < self.base_tick or price_tick > self.top_tick:
            new_base = min(self.base_tick, price_tick - 64)
            new_top = max(self.top_tick, price_tick + 64)
            offset = self.base_tick - new_base
            length = new_top - new_base + 1
            profile = np.zeros(length, dtype=np.int64)
            delta = np.zeros(length, dtype=np.int64)
            traded = np.zeros(length, dtype=np.bool_)
            profile[offset : offset + len(self.profile_volume)] = self.profile_volume
            delta[offset : offset + len(self.delta_one)] = self.delta_one
            traded[offset : offset + len(self.traded_one)] = self.traded_one
            self.base_tick, self.top_tick = new_base, new_top
            self.profile_volume, self.delta_one, self.traded_one = profile, delta, traded

        if self.base_four is None or self.top_four is None:
            self.base_four = four_bucket - 16
            self.top_four = four_bucket + 16
            length = self.top_four - self.base_four + 1
            self.delta_four = np.zeros(length, dtype=np.int64)
            self.bar_delta_four = np.zeros(length, dtype=np.int64)
            self.traded_four = np.zeros(length, dtype=np.bool_)
        elif four_bucket < self.base_four or four_bucket > self.top_four:
            new_base = min(self.base_four, four_bucket - 16)
            new_top = max(self.top_four, four_bucket + 16)
            offset = self.base_four - new_base
            length = new_top - new_base + 1
            delta = np.zeros(length, dtype=np.int64)
            bar_delta = np.zeros(length, dtype=np.int64)
            traded = np.zeros(length, dtype=np.bool_)
            delta[offset : offset + len(self.delta_four)] = self.delta_four
            bar_delta[offset : offset + len(self.bar_delta_four)] = self.bar_delta_four
            traded[offset : offset + len(self.traded_four)] = self.traded_four
            self.base_four, self.top_four = new_base, new_top
            self.delta_four, self.bar_delta_four, self.traded_four = delta, bar_delta, traded

    def _refresh_delta_qualifications(self, one_tick: int, four_bucket: int) -> None:
        for center in range(one_tick - 2, one_tick + 3):
            if self._delta_level_qualifies(self.delta_one, self.traded_one, center, int(self.base_tick)):
                self.qualified_delta_one.add(center)
            else:
                self.qualified_delta_one.discard(center)
        for center in range(four_bucket - 2, four_bucket + 3):
            if self._delta_level_qualifies(self.delta_four, self.traded_four, center, int(self.base_four)):
                self.qualified_delta_four.add(center)
            else:
                self.qualified_delta_four.discard(center)

    def _delta_level_qualifies(
        self,
        delta: np.ndarray,
        traded: np.ndarray,
        center_tick: int,
        base_tick: int,
    ) -> bool:
        center = center_tick - base_tick
        if center - 2 < 0 or center + 2 >= len(delta):
            return False
        neighbours = (center - 2, center - 1, center + 1, center + 2)
        if not bool(traded[center]) or not all(bool(traded[index]) for index in neighbours):
            return False
        magnitude = abs(int(delta[center]))
        if magnitude < self.cfg.delta_profile_min_abs:
            return False
        return all(magnitude >= 2 * abs(int(delta[index])) for index in neighbours)

    def _update_big_trade(self, index: int, side: str, size: int) -> None:
        timestamp_ns = int(self.timestamp_ns[index])
        price_tick = int(self.price_ticks[index])
        anchor = self.big_anchor
        matches = bool(
            anchor is not None
            and timestamp_ns - int(anchor["timestamp_ns"]) <= self.cfg.big_trade_window_ms * 1_000_000
            and price_tick == int(anchor["price_tick"])
            and side == anchor["side"]
        )
        if not matches:
            anchor = {
                "timestamp_ns": timestamp_ns,
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
            self.big_trade_snapshots.setdefault(
                price_tick,
                {
                    "qualified_at_ns": timestamp_ns,
                    "qualified_event_index": index,
                    "price_tick": price_tick,
                    "side": side,
                    "volume": int(anchor["volume"]),
                },
            )

    def _profile(self) -> dict | None:
        if self.observed_low_tick is None or self.observed_high_tick is None:
            return None
        low_index = self.observed_low_tick - int(self.base_tick)
        high_index = self.observed_high_tick - int(self.base_tick)
        volumes = self.profile_volume[low_index : high_index + 1]
        if int(volumes.sum()) <= 0 or np.count_nonzero(volumes) < 3:
            return None
        poc_relative = int(np.argmax(volumes))
        poc_relative_index = poc_relative
        target = float(volumes.sum()) * self.cfg.value_area_fraction
        lower = upper = poc_relative_index
        accumulated = int(volumes[poc_relative_index])
        while accumulated < target and (lower > 0 or upper < len(volumes) - 1):
            lower_volume = int(volumes[lower - 1]) if lower > 0 else -1
            upper_volume = int(volumes[upper + 1]) if upper < len(volumes) - 1 else -1
            if lower_volume > upper_volume:
                lower -= 1
                accumulated += lower_volume
            elif upper_volume > lower_volume:
                upper += 1
                accumulated += upper_volume
            else:
                if lower > 0:
                    lower -= 1
                    accumulated += lower_volume
                if accumulated < target and upper < len(volumes) - 1:
                    upper += 1
                    accumulated += upper_volume
        return {
            "poc_tick": self.observed_low_tick + poc_relative_index,
            "val_tick": self.observed_low_tick + lower,
            "vah_tick": self.observed_low_tick + upper,
            "total_volume": int(volumes.sum()),
        }

    def _selected_candidates(self) -> dict[str, AoiCandidate]:
        profile = self.current_profile
        if profile is None:
            return {}
        opening_range = (
            self.or_high_tick if self.last_timestamp_ns >= self.opening_range_end_ns else None,
            self.or_low_tick if self.last_timestamp_ns >= self.opening_range_end_ns else None,
        )
        fingerprint = (
            int(profile["val_tick"]),
            int(profile["vah_tick"]),
            opening_range,
            tuple(sorted(self.qualified_delta_one)),
            tuple(sorted(self.qualified_delta_four)),
            tuple(sorted(self.big_trade_snapshots)),
        )
        if fingerprint == self.candidate_fingerprint:
            return self.candidate_cache
        market = self._market_confluences()
        delta = self._delta_confluences()
        big = [
            ConfluencePoint("big_trade", "BIG_TRADE", tick, tick, tick)
            for tick in sorted(self.big_trade_snapshots)
        ]
        categories = {"market": market, "delta_profile": delta, "big_trade": big}
        out = {}
        for side, direction, anchor in (
            ("VAL", "long", int(profile["val_tick"])),
            ("VAH", "short", int(profile["vah_tick"])),
        ):
            candidate = _best_aoi(side, direction, anchor, categories, self.cfg.max_aoi_width_ticks)
            if candidate is not None:
                out[side] = candidate
        self.candidate_fingerprint = fingerprint
        self.candidate_cache = out
        return out

    def _market_confluences(self) -> list[ConfluencePoint]:
        values: list[tuple[str, float | None]] = []
        prior = self.previous_rth
        if prior is not None:
            values.extend([("PDH", prior.high), ("PDL", prior.low), ("PDC", prior.close)])
        values.extend([("ONH", self.overnight_high), ("ONL", self.overnight_low)])
        if self.or_high_tick is not None and self.last_timestamp_ns >= self.opening_range_end_ns:
            values.extend(
                [
                    ("ORH", self.or_high_tick * self.cfg.tick_size),
                    ("ORL", self.or_low_tick * self.cfg.tick_size if self.or_low_tick is not None else None),
                ]
            )
        out = []
        for level_type, value in values:
            if value is None or not math.isfinite(float(value)):
                continue
            tick = int(round(float(value) / self.cfg.tick_size))
            out.append(ConfluencePoint("market", level_type, tick, tick, tick))
        return out

    def _delta_confluences(self) -> list[ConfluencePoint]:
        out = []
        for tick in sorted(self.qualified_delta_one):
            out.append(ConfluencePoint("delta_profile", "DELTA_1T", tick, tick, tick))
        for bucket in sorted(self.qualified_delta_four):
            low = bucket * 4
            high = low + 3
            out.append(ConfluencePoint("delta_profile", "DELTA_4T", low, low, high))
            out.append(ConfluencePoint("delta_profile", "DELTA_4T", high, low, high))
        return out

    def _apply_candidate(
        self,
        side: str,
        candidate: AoiCandidate | None,
        timestamp_ns: int,
        event_index: int,
    ) -> None:
        current = self.lineages[side]
        if candidate is None:
            self.lineages[side] = None
            return
        if current is not None and _overlap(
            current.candidate.low_tick,
            current.candidate.high_tick,
            candidate.low_tick,
            candidate.high_tick,
        ):
            current.candidate = candidate
            if current.pending is not None:
                current.pending.entry_tick = _entry_tick(candidate, self.cfg.entry_offset_ticks)
                current.pending.stop_tick = _stop_tick(candidate, self.cfg.stop_offset_ticks)
            return
        self.lineage_counter += 1
        self.lineages[side] = AoiLineage(
            lineage_id=self.lineage_counter,
            candidate=candidate,
            eligible_at_ns=timestamp_ns,
            eligible_event_index=event_index,
        )
        self.diagnostics["aoi_eligible_events"] += 1

    def _update_visit_and_order(self, lineage: AoiLineage, index: int) -> None:
        timestamp_ns = int(self.timestamp_ns[index])
        price_tick = int(self.price_ticks[index])
        candidate = lineage.candidate
        direction = candidate.direction
        if lineage.visit is None:
            if timestamp_ns <= lineage.eligible_at_ns or not _tapped(candidate, price_tick):
                return
            lineage.visit = Visit(timestamp_ns, index, candidate.low_tick, candidate.high_tick)
            self.diagnostics["taps"] += 1
            return

        visit = lineage.visit
        if timestamp_ns <= visit.tapped_at_ns:
            return
        bubble = self._qualifying_entry_bubble(
            candidate,
            visit.tapped_event_index,
            index,
        )
        if bubble is not None and lineage.pending is None and self._preorder_range_gate(index, lineage):
            lineage.pending = PendingOrder(
                trigger_kind=bubble["kind"],
                bubble_qualified_at_ns=int(bubble["qualified_at_ns"]),
                bubble_event_index=int(bubble["qualified_event_index"]),
                armed_at_ns=timestamp_ns,
                armed_event_index=index,
                entry_tick=_entry_tick(candidate, self.cfg.entry_offset_ticks),
                stop_tick=_stop_tick(candidate, self.cfg.stop_offset_ticks),
                bubble_price_tick=int(bubble["price_tick"]),
                bubble_bar_id=bubble.get("bar_id"),
                bubble_bucket=bubble.get("bucket"),
                bubble_value=int(bubble["value"]),
            )
            self.diagnostics["orders_armed"] += 1

        hypothetical_entry = _entry_tick(candidate, self.cfg.entry_offset_ticks)
        if _entry_crossed(direction, hypothetical_entry, price_tick):
            if visit.confirmed_at_ns is None:
                visit.confirmed_at_ns = timestamp_ns
                self.reversals[candidate.side].append(
                    Visit(
                        visit.tapped_at_ns,
                        visit.tapped_event_index,
                        visit.low_tick,
                        visit.high_tick,
                        timestamp_ns,
                    )
                )
                if lineage.pending is None:
                    lineage.visit = None

    def _qualifying_entry_bubble(
        self,
        candidate: AoiCandidate,
        tap_event_index: int,
        index: int,
    ) -> dict | None:
        timestamp_ns = int(self.timestamp_ns[index])
        price_tick = int(self.price_ticks[index])
        bar_id = self._bar_id(timestamp_ns)
        bucket = math.floor(price_tick / 4)
        value = int(self.bar_delta_four[bucket - int(self.base_four)])
        if (
            index > tap_event_index
            and abs(value) > self.cfg.delta_bubble_threshold
            and _price_in_or_beyond(candidate, bucket * 4, bucket * 4 + 3)
        ):
            self.diagnostics["delta_bubbles"] += 1
            return {
                "kind": "delta_4tick_3m",
                "price_tick": price_tick,
                "bar_id": bar_id,
                "bucket": bucket,
                "value": value,
                "qualified_at_ns": timestamp_ns,
                "qualified_event_index": index,
            }
        eligible = [
            snapshot
            for snapshot in self.big_trade_snapshots.values()
            if int(snapshot["qualified_event_index"]) > tap_event_index
            and int(snapshot["qualified_event_index"]) <= index
            and _point_in_or_beyond(candidate, int(snapshot["price_tick"]))
        ]
        if eligible:
            snapshot = max(eligible, key=lambda item: int(item["qualified_at_ns"]))
            self.diagnostics["big_trade_bubbles"] += 1
            return {
                "kind": "big_trade_100ms",
                "price_tick": int(snapshot["price_tick"]),
                "value": int(snapshot["volume"]),
                "qualified_at_ns": int(snapshot["qualified_at_ns"]),
                "qualified_event_index": int(snapshot["qualified_event_index"]),
            }
        return None

    def _pending_is_live(self, pending: PendingOrder, candidate: AoiCandidate, index: int) -> bool:
        if pending.trigger_kind == "big_trade_100ms":
            return True
        timestamp_ns = int(self.timestamp_ns[index])
        if pending.bubble_bar_id != self._bar_id(timestamp_ns) or pending.bubble_bucket is None:
            return False
        value = int(self.bar_delta_four[pending.bubble_bucket - int(self.base_four)])
        if abs(value) <= self.cfg.delta_bubble_threshold:
            return False
        return _price_in_or_beyond(candidate, pending.bubble_bucket * 4, pending.bubble_bucket * 4 + 3)

    def _preorder_range_gate(self, index: int, lineage: AoiLineage) -> bool:
        return self._range_and_profile_pass(index) and self._breakout_gate(index) and self._has_prior_reversal(index, lineage)

    def _fill_gate_passes(self, index: int, lineage: AoiLineage) -> bool:
        if self.required_direction and lineage.candidate.direction != self.required_direction:
            return False
        if not self._range_and_profile_pass(index) or not self._breakout_gate(index):
            return False
        if not self._has_prior_reversal(index, lineage):
            return False
        entry_tick = lineage.pending.entry_tick if lineage.pending is not None else _entry_tick(
            lineage.candidate, self.cfg.entry_offset_ticks
        )
        stop_tick = lineage.pending.stop_tick if lineage.pending is not None else _stop_tick(
            lineage.candidate, self.cfg.stop_offset_ticks
        )
        if self.current_profile is None:
            return False
        target_tick = (
            int(self.current_profile["vah_tick"])
            if lineage.candidate.direction == "long"
            else int(self.current_profile["val_tick"])
        )
        if lineage.candidate.direction == "long" and target_tick <= entry_tick:
            return False
        if lineage.candidate.direction == "short" and target_tick >= entry_tick:
            return False
        risk_points = abs(entry_tick - stop_tick) * self.cfg.tick_size
        return 0 < risk_points <= self.cfg.max_stop_points

    def _range_and_profile_pass(self, index: int) -> bool:
        profile = self.current_profile
        if profile is None or index <= 0:
            return False
        now_ns = int(self.timestamp_ns[index])
        reference_ns = self.open_ns + int((now_ns - self.open_ns) * (2.0 / 3.0))
        reference_index = int(np.searchsorted(self.timestamp_ns[: index + 1], reference_ns, side="right") - 1)
        if reference_index < 0:
            return False
        reference_range = int(self.cumulative_high[reference_index] - self.cumulative_low[reference_index])
        current_range = int(self.cumulative_high[index] - self.cumulative_low[index])
        if reference_range <= 0 or current_range > reference_range * (1.0 + self.cfg.range_expansion_fraction):
            return False
        session_low = int(self.cumulative_low[index])
        session_high = int(self.cumulative_high[index])
        width = session_high - session_low
        if width <= 0:
            return False
        poc = int(profile["poc_tick"])
        return session_low + width / 3.0 <= poc <= session_low + 2.0 * width / 3.0

    def _has_prior_reversal(self, index: int, lineage: AoiLineage) -> bool:
        now_ns = int(self.timestamp_ns[index])
        reference_ns = self.open_ns + int((now_ns - self.open_ns) * (2.0 / 3.0))
        candidate = lineage.candidate
        return any(
            visit.confirmed_at_ns is not None
            and visit.confirmed_at_ns >= reference_ns
            and visit.confirmed_at_ns < now_ns
            and (lineage.visit is None or visit.tapped_at_ns != lineage.visit.tapped_at_ns)
            and _overlap(visit.low_tick, visit.high_tick, candidate.low_tick, candidate.high_tick)
            for visit in self.reversals[candidate.side]
        )

    def _breakout_gate(self, index: int) -> bool:
        now_ns = int(self.timestamp_ns[index])
        reference_ns = self.open_ns + int((now_ns - self.open_ns) * (2.0 / 3.0))
        reference_index = int(np.searchsorted(self.timestamp_ns[: index + 1], reference_ns, side="right") - 1)
        if reference_index < 0:
            return False
        high_ref = int(self.cumulative_high[reference_index])
        low_ref = int(self.cumulative_low[reference_index])
        probe = self.cfg.breakout_probe_ticks
        upper = _one_side_breakout_pass(
            self.timestamp_ns,
            self.price_ticks,
            reference_index + 1,
            index,
            high_ref + probe,
            high_ref - probe,
            self.completed_bars,
            upper=True,
        )
        lower = _one_side_breakout_pass(
            self.timestamp_ns,
            self.price_ticks,
            reference_index + 1,
            index,
            low_ref - probe,
            low_ref + probe,
            self.completed_bars,
            upper=False,
        )
        return upper and lower

    def _finalize_completed_bar(self, timestamp_ns: int, price_tick: int) -> None:
        bar_id = self._bar_id(timestamp_ns)
        if self.current_bar_id is None:
            self.current_bar_id = bar_id
        elif bar_id != self.current_bar_id:
            close_ns = self.open_ns + (self.current_bar_id + 1) * self.cfg.bar_seconds * 1_000_000_000
            if self.current_bar_last_tick is not None:
                self.completed_bars.append((close_ns, self.current_bar_last_tick))
            self.current_bar_id = bar_id
            self.bar_delta_four.fill(0)
        self.current_bar_last_tick = price_tick

    def _bar_id(self, timestamp_ns: int) -> int:
        return int((timestamp_ns - self.open_ns) // (self.cfg.bar_seconds * 1_000_000_000))

class ExactYushRangeEventStrategy(CanonicalEventReplayStrategy):
    """Yush market-state adapter for BacktestEngine's canonical event lane.

    Developing profiles, AOIs, bubbles, and entry gates remain strategy-owned.
    Orders, positions, fills, brackets, costs, and trade IDs are owned by the
    engine-facing broker.
    """

    required_event_columns = ("size", "side", "signed_size", "contract_symbol")

    def __init__(
        self,
        config: ExactYushRangeConfig | None = None,
        news_events_by_session: dict[object, tuple[pd.Timestamp, ...]] | None = None,
    ):
        self.cfg = config or ExactYushRangeConfig()
        self.news_events_by_session = news_events_by_session or {}
        self.state: _YushSessionState | None = None

    def on_replay_start(self, broker: EventReplayBroker) -> None:
        self.state = None

    def on_session_start(self, session: EventReplaySessionView, broker: EventReplayBroker) -> None:
        self.state = _YushSessionState(
            session,
            self.cfg,
            news_releases=self.news_events_by_session.get(session.session_date, ()),
        )

    def on_event_start(self, event: CanonicalEvent, broker: EventReplayBroker) -> None:
        state = self._state()
        state.last_timestamp_ns = event.timestamp_ns
        state._ingest_event(event)

    def pre_execution(self, event: CanonicalEvent, broker: EventReplayBroker) -> EventPreExecution:
        state = self._state()
        blocked = False
        reset = False
        flatten_reason = None
        five_minutes_ns = 5 * 60 * 1_000_000_000
        for release_ns in state.news_release_ns:
            window_start_ns = release_ns - five_minutes_ns
            if event.timestamp_ns >= window_start_ns and release_ns not in state.news_reset_done:
                for lineage in state.lineages.values():
                    if lineage is not None:
                        lineage.visit = None
                        lineage.pending = None
                if broker.position is not None:
                    flatten_reason = "news_flatten"
                    state.diagnostics["news_flatten_trades"] += 1
                state.news_reset_done.add(release_ns)
                state.diagnostics["news_resets"] += 1
                reset = True
            if window_start_ns <= event.timestamp_ns <= release_ns:
                blocked = True
        return EventPreExecution(
            block_entries=blocked,
            cancel_entry_orders=reset,
            flatten_reason=flatten_reason,
            flatten_tick=event.price_tick if flatten_reason else None,
        )

    def entry_order_is_live(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        lineage = self._lineage_for_order(order)
        if lineage is None or lineage.pending is None or lineage.locked:
            return False
        return self._state()._pending_is_live(lineage.pending, lineage.candidate, event.event_index)

    def entry_order_is_suspended(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del event, broker
        lineage = self._lineage_for_order(order)
        if lineage is None or lineage.pending is None or lineage.locked:
            return False
        required = self._state().required_direction
        return bool(required and lineage.candidate.direction != required)

    def entry_fill_allowed(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        lineage = self._lineage_for_order(order)
        if lineage is None or lineage.pending is None:
            return False
        return self._state()._fill_gate_passes(event.event_index, lineage)

    def on_order_cancelled(
        self,
        order: EventEntryOrder,
        reason: str,
        event: CanonicalEvent | None,
        broker: EventReplayBroker,
    ) -> None:
        lineage = self._lineage_for_order(order)
        if lineage is None:
            return
        lineage.pending = None
        if reason == "fill_gate_rejected":
            lineage.visit = None
            self._state().diagnostics["fill_gate_rejections"] += 1

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        lineage = self._lineage_for_order(order)
        if lineage is None or lineage.pending is None or lineage.visit is None or state.current_profile is None:
            raise AssertionError("A Yush entry filled without complete AOI lineage evidence.")
        pending = lineage.pending
        visit = lineage.visit
        if not (
            lineage.eligible_event_index
            < visit.tapped_event_index
            < pending.bubble_event_index
            <= pending.armed_event_index
            < event.event_index
        ):
            raise AssertionError("AOI eligibility, tap, bubble, order, and fill events are not causal.")
        candidate = lineage.candidate
        profile = dict(state.current_profile)
        broker.annotate_position(
            aoi_side=candidate.side,
            aoi_lineage_id=lineage.lineage_id,
            aoi_box_low=candidate.low_tick * self.cfg.tick_size,
            aoi_box_high=candidate.high_tick * self.cfg.tick_size,
            aoi_width_points=candidate.width_ticks * self.cfg.tick_size,
            aoi_additional_category_count=len(candidate.categories),
            aoi_categories=",".join(candidate.categories),
            aoi_confluences=",".join(point.level_type for point in candidate.confluences),
            trigger_kind=pending.trigger_kind,
            trigger_value=int(pending.bubble_value or 0),
            aoi_eligible_timestamp=pd.Timestamp(lineage.eligible_at_ns, tz="UTC").tz_convert("America/New_York"),
            aoi_eligible_event_index=lineage.eligible_event_index,
            aoi_tap_timestamp=pd.Timestamp(visit.tapped_at_ns, tz="UTC").tz_convert("America/New_York"),
            aoi_tap_event_index=visit.tapped_event_index,
            bubble_qualified_timestamp=pd.Timestamp(pending.bubble_qualified_at_ns, tz="UTC").tz_convert(
                "America/New_York"
            ),
            bubble_qualified_event_index=pending.bubble_event_index,
            order_armed_timestamp=pd.Timestamp(pending.armed_at_ns, tz="UTC").tz_convert("America/New_York"),
            order_armed_event_index=pending.armed_event_index,
            entry_profile_poc=profile["poc_tick"] * self.cfg.tick_size,
            entry_profile_vah=profile["vah_tick"] * self.cfg.tick_size,
            entry_profile_val=profile["val_tick"] * self.cfg.tick_size,
            midpoint_activated=False,
            midpoint_activated_at=None,
            source_quality_label="Direct Databento GLBX trades messages; active outright; not MBO.",
            fill_model="user_directed_exact_trigger_price_zero_slippage",
        )
        lineage.locked = True
        lineage.pending = None
        if state.required_direction == candidate.direction:
            state.required_direction = None

    def position_directive(
        self,
        event: CanonicalEvent,
        position: EventPositionView,
        broker: EventReplayBroker,
    ) -> PositionDirective:
        state = self._state()
        if bool(position.report_fields.get("midpoint_activated")) or state.current_profile is None:
            return PositionDirective()
        midpoint = (int(state.current_profile["vah_tick"]) + int(state.current_profile["val_tick"])) / 2.0
        offset_ticks = int(round(self.cfg.breakeven_offset_points / self.cfg.tick_size))
        desired_stop = (
            position.entry_reference_tick + offset_ticks
            if position.direction == "long"
            else position.entry_reference_tick - offset_ticks
        )
        midpoint_reached = event.price_tick >= midpoint if position.direction == "long" else event.price_tick <= midpoint
        stop_level_traded = (
            event.price_tick >= desired_stop if position.direction == "long" else event.price_tick <= desired_stop
        )
        if not (midpoint_reached and stop_level_traded):
            return PositionDirective()
        target = (
            int(state.current_profile["vah_tick"])
            if position.direction == "long"
            else int(state.current_profile["val_tick"])
        )
        valid = target > position.entry_reference_tick if position.direction == "long" else target < position.entry_reference_tick
        if not valid:
            state.diagnostics["target_guard_exits"] += 1
            return PositionDirective(flatten_reason="invalid_target_guard", flatten_tick=event.price_tick)
        inverted_oco = desired_stop >= target if position.direction == "long" else desired_stop <= target
        target_already_reached = event.price_tick >= target if position.direction == "long" else event.price_tick <= target
        return PositionDirective(
            stop_tick=desired_stop,
            target_tick=target,
            stop_exit_reason="managed_stop",
            report_fields={
                "midpoint_activated": True,
                "midpoint_activated_at": pd.Timestamp(event.timestamp),
                "managed_bracket_inverted_at_activation": inverted_oco,
                "managed_target_already_reached_at_activation": target_already_reached,
            },
            # These flags preserve the already-frozen exact-run behavior. They
            # are exported explicitly because this legacy OCO rule is materially
            # different from the event lane's safe default.
            allow_inverted_oco=True,
            allow_marketable_bracket=True,
        )

    def on_position_closed(
        self,
        position: EventPositionView,
        trade: dict,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        if trade["exit_reason"] == "initial_stop" and not bool(position.report_fields.get("midpoint_activated")):
            state.required_direction = "short" if position.direction == "long" else "long"

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
        candidates = state._selected_candidates()
        for side in ("VAL", "VAH"):
            self._apply_candidate_and_sync(side, candidates.get(side), event, broker)

        if (
            entries_blocked
            or broker.position is not None
            or closed_this_event
            or opened_this_event
            or broker.trades_today >= self.cfg.max_trades_per_day
        ):
            return
        for side in ("VAL", "VAH"):
            lineage = state.lineages[side]
            if lineage is None or lineage.locked:
                continue
            pending_before = lineage.pending
            state._update_visit_and_order(lineage, event.event_index)
            if lineage.pending is not None and lineage.pending is not pending_before:
                self._sync_pending_order(side, lineage, broker)

    def finish_session(self, session: EventReplaySessionView, broker: EventReplayBroker) -> None:
        pass

    def session_audit(self) -> dict:
        state = self._state()
        return {
            "previous_rth_available": state.previous_rth is not None,
            "overnight_available": state.overnight_high is not None and state.overnight_low is not None,
            **state.diagnostics,
        }

    def _apply_candidate_and_sync(
        self,
        side: str,
        candidate: AoiCandidate | None,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        current = state.lineages[side]
        preserves_lineage = bool(
            candidate is not None
            and current is not None
            and _overlap(
                current.candidate.low_tick,
                current.candidate.high_tick,
                candidate.low_tick,
                candidate.high_tick,
            )
        )
        if current is not None and current.pending is not None and not preserves_lineage:
            broker.cancel_entry(side, reason="aoi_replaced")
        state._apply_candidate(side, candidate, event.timestamp_ns, event.event_index)
        updated = state.lineages[side]
        if updated is not None and updated.pending is not None:
            self._sync_pending_order(side, updated, broker)

    def _sync_pending_order(
        self,
        side: str,
        lineage: AoiLineage,
        broker: EventReplayBroker,
    ) -> None:
        pending = lineage.pending
        if pending is None:
            return
        broker.submit_or_replace_entry(
            order_id=side,
            direction=lineage.candidate.direction,
            entry_tick=pending.entry_tick,
            stop_tick=pending.stop_tick,
            priority=0 if side == "VAL" else 1,
            metadata={"side": side, "lineage_id": lineage.lineage_id},
        )

    def _lineage_for_order(self, order: EventEntryOrder) -> AoiLineage | None:
        side = str(order.metadata.get("side") or order.order_id)
        lineage = self._state().lineages.get(side)
        if lineage is None or int(order.metadata.get("lineage_id", -1)) != lineage.lineage_id:
            return None
        return lineage

    def _state(self) -> _YushSessionState:
        if self.state is None:
            raise RuntimeError("Yush event strategy has not started a session.")
        return self.state


def _best_aoi(
    side: str,
    direction: str,
    anchor_tick: int,
    categories: dict[str, list[ConfluencePoint]],
    max_width_ticks: int,
) -> AoiCandidate | None:
    names = tuple(categories)
    for score in range(len(names), 0, -1):
        choices = []
        for required in combinations(names, score):
            points = [point for name in required for point in categories[name]]
            lower_bounds = {anchor_tick, *(point.point_tick for point in points if point.point_tick <= anchor_tick)}
            upper_bounds = {anchor_tick, *(point.point_tick for point in points if point.point_tick >= anchor_tick)}
            for low in lower_bounds:
                for high in upper_bounds:
                    if high - low > max_width_ticks:
                        continue
                    selected = []
                    for name in required:
                        available = [point for point in categories[name] if low <= point.point_tick <= high]
                        if not available:
                            break
                        selected.append(
                            min(
                                available,
                                key=lambda point: (
                                    abs(point.point_tick - anchor_tick),
                                    point.point_tick,
                                    point.level_type,
                                    point.interval_low_tick,
                                ),
                            )
                        )
                    else:
                        canonical = tuple(
                            (point.category, point.level_type, point.point_tick, point.interval_low_tick)
                            for point in selected
                        )
                        key = (high - low, abs((low + high) / 2.0 - anchor_tick), low, canonical)
                        choices.append((key, required, tuple(selected), low, high))
        if choices:
            _, required, selected, low, high = min(choices, key=lambda item: item[0])
            return AoiCandidate(side, direction, anchor_tick, low, high, tuple(required), selected)
    return None


def _entry_tick(candidate: AoiCandidate, offset: int) -> int:
    return candidate.high_tick + offset if candidate.direction == "long" else candidate.low_tick - offset


def _stop_tick(candidate: AoiCandidate, offset: int) -> int:
    return candidate.low_tick - offset if candidate.direction == "long" else candidate.high_tick + offset


def _tapped(candidate: AoiCandidate, price_tick: int) -> bool:
    return price_tick <= candidate.high_tick if candidate.direction == "long" else price_tick >= candidate.low_tick


def _entry_crossed(direction: str, entry_tick: int, price_tick: int) -> bool:
    return price_tick >= entry_tick if direction == "long" else price_tick <= entry_tick


def _point_in_or_beyond(candidate: AoiCandidate, point_tick: int) -> bool:
    return point_tick <= candidate.high_tick if candidate.direction == "long" else point_tick >= candidate.low_tick


def _price_in_or_beyond(candidate: AoiCandidate, low_tick: int, high_tick: int) -> bool:
    return low_tick <= candidate.high_tick if candidate.direction == "long" else high_tick >= candidate.low_tick


def _overlap(left_low: int, left_high: int, right_low: int, right_high: int) -> bool:
    return max(left_low, right_low) <= min(left_high, right_high)


def _one_side_breakout_pass(
    timestamp_ns: np.ndarray,
    prices: np.ndarray,
    start_index: int,
    end_index: int,
    attempt_level: int,
    return_level: int,
    completed_bars: list[tuple[int, int]],
    *,
    upper: bool,
) -> bool:
    cursor = start_index
    attempted = False
    while cursor <= end_index:
        if upper:
            matches = np.flatnonzero(prices[cursor : end_index + 1] >= attempt_level)
        else:
            matches = np.flatnonzero(prices[cursor : end_index + 1] <= attempt_level)
        if len(matches) == 0:
            return True
        attempt_index = cursor + int(matches[0])
        attempted = True
        later = prices[attempt_index + 1 : end_index + 1]
        returns = np.flatnonzero(later <= return_level if upper else later >= return_level)
        return_index = attempt_index + 1 + int(returns[0]) if len(returns) else None
        limit_ns = int(timestamp_ns[return_index]) if return_index is not None else int(timestamp_ns[end_index]) + 1
        closes = [
            close
            for close_ns, close in completed_bars
            if int(timestamp_ns[attempt_index]) < close_ns < limit_ns
        ]
        consecutive = 0
        for close in closes:
            beyond = close >= attempt_level if upper else close <= attempt_level
            consecutive = consecutive + 1 if beyond else 0
            if consecutive >= 2:
                return False
        if return_index is None:
            return False
        cursor = return_index + 1
    return True


def _extended_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "expectancy_per_trade": 0.0,
            "average_trade_duration_minutes": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "average_win_loss_ratio": 0.0,
            "largest_winning_trade_contribution": 0.0,
            "daily_sharpe": 0.0,
            "daily_sortino": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "managed_bracket_inverted_trades": 0,
            "managed_target_already_reached_trades": 0,
        }
    entry = pd.to_datetime(trades["entry_timestamp"], utc=True)
    exit_ = pd.to_datetime(trades["exit_timestamp"], utc=True)
    wins = trades.loc[trades["net_pnl"] > 0, "net_pnl"]
    losses = trades.loc[trades["net_pnl"] < 0, "net_pnl"]
    total_positive = float(wins.sum())
    daily_pnl = daily_results(trades)["net_pnl"].astype(float)
    daily_std = float(daily_pnl.std(ddof=1)) if len(daily_pnl) > 1 else 0.0
    downside_deviation = float(np.sqrt(np.mean(np.minimum(daily_pnl.to_numpy(), 0.0) ** 2)))
    daily_mean = float(daily_pnl.mean())
    average_win = float(wins.mean()) if len(wins) else 0.0
    average_loss = float(losses.mean()) if len(losses) else 0.0
    inverted = trades.get("managed_bracket_inverted_at_activation", pd.Series(False, index=trades.index))
    marketable_target = trades.get(
        "managed_target_already_reached_at_activation",
        pd.Series(False, index=trades.index),
    )
    return {
        "expectancy_per_trade": float(trades["net_pnl"].mean()),
        "average_trade_duration_minutes": float((exit_ - entry).dt.total_seconds().mean() / 60.0),
        "average_win": average_win,
        "average_loss": average_loss,
        "average_win_loss_ratio": average_win / abs(average_loss) if average_loss else 0.0,
        "largest_winning_trade_contribution": float(wins.max() / total_positive) if total_positive > 0 else 0.0,
        "daily_sharpe": math.sqrt(252.0) * daily_mean / daily_std if daily_std > 0 else 0.0,
        "daily_sortino": math.sqrt(252.0) * daily_mean / downside_deviation if downside_deviation > 0 else 0.0,
        "long_trades": int(trades["direction"].eq("long").sum()),
        "short_trades": int(trades["direction"].eq("short").sum()),
        "managed_bracket_inverted_trades": int(inverted.fillna(False).astype(bool).sum()),
        "managed_target_already_reached_trades": int(marketable_target.fillna(False).astype(bool).sum()),
    }
