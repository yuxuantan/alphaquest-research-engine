"""ATR-adaptive Yush AOI range-reversal mechanics.

This is the v02 replacement requested after the failed-auction mechanic was
retired.  It preserves v01's exact AOI lineage, tap, prior-reversal, and
post-tap confirmation sequence while replacing absolute AOI/order-flow
thresholds and midpoint management with causal adaptive mechanics.  Large
trades use one session-frozen threshold derived exclusively from the previous
twenty completed RTH sessions.  Each value edge retains only its newest
qualifying institutional level; the first directed retest consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from functools import lru_cache
import math
from pathlib import Path
from typing import Any

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
    ExactYushRangeEventStrategy,
    PendingOrder,
    _entry_crossed,
    _entry_tick,
    _overlap,
    _point_in_or_beyond,
    _price_in_or_beyond,
)
from alphaquest.strategy_modules.event.yush_orderflow_range import (
    YushOrderflowRangeConfig,
    YushOrderflowRangeEventStrategy,
    _YushOrderflowRangeState,
    _aoi_fingerprint,
    _format_aoi_fingerprint,
    _point_signature,
)


STRATEGY_ID = "yush_adaptive_orderflow_range"
ENTRY_MODULE = STRATEGY_ID
STOP_MODULE = "event_aoi_structural_stop"
TARGET_MODULE = "event_frozen_value_target_choice"
MINIMUM_DELTA_MULTIPLE = 2.0
TARGET_MODES = {"midpoint", "opposite_value_edge"}


@dataclass(frozen=True)
class YushAdaptiveOrderflowRangeConfig(YushOrderflowRangeConfig):
    """Reviewed v02 defaults and fixed execution assumptions."""

    commission_per_contract: float = 1.55
    max_trades_per_day: int = 0
    max_aoi_width_points: float = field(default=5.0, init=False, repr=False)
    entry_offset_ticks: int = 1
    stop_offset_ticks: int = 1
    max_stop_points: float = 5.0
    max_entry_to_far_aoi_edge_points: float = 5.0
    internal_lvn_poc_fraction: float = 0.10
    delta_profile_min_abs: int = field(default=1, init=False, repr=False)
    delta_bubble_threshold: int = field(default=1, init=False, repr=False)
    big_trade_threshold: int = field(default=1, init=False, repr=False)
    breakeven_offset_points: float = field(default=0.0, init=False, repr=False)
    minimum_stop_points: float = 0.25
    slippage_ticks: int = 0
    aoi_atr_multiple: float = 1.5
    aoi_atr_lookback_bars: int = 14
    aoi_atr_max_points: float = 5.0
    big_trade_reference_percentile: float = 0.999
    big_trade_lookback_sessions: int = 20
    delta_average_multiple: float = 3.0
    target_mode: str = "midpoint"
    atr_context_path: str = (
        "research/datasets/"
        "es_sierra_yush_events_20110815_20260529_0930_1100_ny_inv02/"
        "atr14_3m_eth_context.parquet"
    )
    atr_context_sha256: str = (
        "436529d23c3c1fd172139d945e080fab49e6c4eca092700fd18c9c07d6624de4"
    )
    big_trade_context_path: str = (
        "research/datasets/"
        "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/"
        "big_trade_100ms_q999_prior20_context.parquet"
    )
    big_trade_context_sha256: str = (
        "e5a4ceafa83dad1f663bb277ae5f5b7d99183e4ea16d0f07cd12b9bd49e610fa"
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        fixed = {
            "commission_per_contract": (self.commission_per_contract, 1.55),
            "max_trades_per_day": (self.max_trades_per_day, 0),
            "entry_offset_ticks": (self.entry_offset_ticks, 1),
            "stop_offset_ticks": (self.stop_offset_ticks, 1),
            "max_stop_points": (self.max_stop_points, 5.0),
            "max_entry_to_far_aoi_edge_points": (
                self.max_entry_to_far_aoi_edge_points,
                5.0,
            ),
            "internal_lvn_poc_fraction": (
                self.internal_lvn_poc_fraction,
                0.10,
            ),
            "minimum_stop_points": (self.minimum_stop_points, self.tick_size),
            "slippage_ticks": (self.slippage_ticks, 0),
            "aoi_atr_multiple": (self.aoi_atr_multiple, 1.5),
            "aoi_atr_lookback_bars": (self.aoi_atr_lookback_bars, 14),
            "aoi_atr_max_points": (self.aoi_atr_max_points, 5.0),
            "big_trade_reference_percentile": (
                self.big_trade_reference_percentile,
                0.999,
            ),
            "big_trade_lookback_sessions": (
                self.big_trade_lookback_sessions,
                20,
            ),
        }
        drift = [
            name
            for name, (actual, expected) in fixed.items()
            if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-12)
        ]
        if drift:
            raise ValueError("fixed adaptive v02 mechanic drift: " + ", ".join(drift))
        if self.delta_average_multiple not in {2.0, 3.0, 4.0, 5.0, 6.0}:
            raise ValueError("delta_average_multiple must be 2, 3, 4, 5, or 6")
        if self.target_mode not in TARGET_MODES:
            raise ValueError("target_mode must be midpoint or opposite_value_edge")
        if not self.atr_context_path or len(self.atr_context_sha256) != 64:
            raise ValueError("ATR context path and SHA-256 are required")
        if (
            not self.big_trade_context_path
            or len(self.big_trade_context_sha256) != 64
        ):
            raise ValueError("big-trade context path and SHA-256 are required")

    @property
    def max_entry_to_far_aoi_edge_ticks(self) -> int:
        return int(
            round(self.max_entry_to_far_aoi_edge_points / self.tick_size)
        )


_ACCEPTED_PARAMETERS = {
    "tick_size",
    "point_value",
    "contracts",
    "commission_per_contract",
    "max_trades_per_day",
    "entry_offset_ticks",
    "stop_offset_ticks",
    "max_stop_points",
    "max_entry_to_far_aoi_edge_points",
    "internal_lvn_poc_fraction",
    "value_area_fraction",
    "range_expansion_fraction",
    "big_trade_window_ms",
    "opening_range_seconds",
    "bar_seconds",
    "breakout_probe_ticks",
    "initial_balance",
    "minimum_stop_points",
    "slippage_ticks",
    "delta_neighbour_multiple",
    "decision_interval_ms",
    "aoi_lineage_mode",
    "aoi_atr_multiple",
    "aoi_atr_lookback_bars",
    "aoi_atr_max_points",
    "big_trade_reference_percentile",
    "big_trade_lookback_sessions",
    "delta_average_multiple",
    "target_mode",
    "atr_context_path",
    "atr_context_sha256",
    "big_trade_context_path",
    "big_trade_context_sha256",
}


def build_strategy(params: dict[str, Any]) -> "YushAdaptiveOrderflowRangeEventStrategy":
    unknown = sorted(set(params) - _ACCEPTED_PARAMETERS)
    if unknown:
        raise ValueError(
            "unknown yush_adaptive_orderflow_range parameter(s): "
            + ", ".join(unknown)
        )
    return YushAdaptiveOrderflowRangeEventStrategy(
        YushAdaptiveOrderflowRangeConfig(**params)
    )


@dataclass(frozen=True)
class AdaptiveAtrSeed:
    atr_points: float
    previous_close_tick: int
    source_contract_symbol: str
    last_seed_bar_close: pd.Timestamp


@dataclass(frozen=True)
class BigTradeThresholdSeed:
    threshold_volume: int
    reference_percentile: float
    lookback_sessions: int
    reference_observation_count: int
    reference_start_session: str
    reference_end_session: str
    percentile_method: str


@dataclass(frozen=True)
class AdaptiveDecisionSnapshot:
    event_index: int
    previous_decision_event_index: int | None
    current_profile: dict | None
    decision_bar_delta_values: dict[int, int]
    dirty_bar_delta_values: dict[int, int]
    raw_delta_candidates: tuple[tuple[int, int], ...]
    raw_big_trade_candidates: tuple[dict[str, Any], ...]
    market_confluences: tuple[ConfluencePoint, ...]
    or_high_tick: int | None
    or_low_tick: int | None
    atr_points: float
    aoi_width_limit_ticks: int
    average_abs_delta_per_level: float | None
    profile_poc_volume: int
    internal_value_level_count: int
    internal_value_min_volume: int | None
    internal_value_min_volume_tick: int | None


@dataclass(frozen=True)
class AdaptiveSessionFeatureTape:
    session_date: object
    timestamp_ns: np.ndarray
    price_ticks: np.ndarray
    cumulative_low: np.ndarray
    cumulative_high: np.ndarray
    neutral_cumulative: np.ndarray
    completed_bars: tuple[tuple[int, int], ...]
    decision_snapshots: dict[int, AdaptiveDecisionSnapshot]
    candidate_cache: dict[tuple, AoiCandidate | None] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )


class _AdaptiveOrderflowRangeState(_YushOrderflowRangeState):
    def __init__(
        self,
        session: EventReplaySessionView,
        config: YushAdaptiveOrderflowRangeConfig,
        atr_seed: AdaptiveAtrSeed,
        big_trade_seed: BigTradeThresholdSeed,
    ) -> None:
        super().__init__(session, config)
        self.cfg = config
        self.atr_seed = atr_seed
        self.big_trade_seed = big_trade_seed
        self.active_atr_points = float(atr_seed.atr_points)
        self.active_aoi_width_limit_ticks = self._aoi_width_ticks(
            self.active_atr_points
        )
        self.average_abs_delta_per_level: float | None = None
        self.active_big_trade_threshold = int(big_trade_seed.threshold_volume)
        self.active_delta_threshold: float | None = None
        self.last_decision_atr_points = self.active_atr_points
        self.last_decision_aoi_width_limit_ticks = (
            self.active_aoi_width_limit_ticks
        )
        self.last_decision_average_abs_delta_per_level: float | None = None
        self.completed_abs_delta = 0
        self.completed_delta_occurrences = 0
        self._current_bar_buckets: set[int] = set()
        self._current_bar_high_tick: int | None = None
        self._current_bar_low_tick: int | None = None
        self._current_bar_last_tick: int | None = None
        self._atr_previous_close_tick = int(atr_seed.previous_close_tick)
        self.last_interval_big_candidates: tuple[dict[str, Any], ...] = ()
        self.last_dirty_bar_delta_values: dict[int, int] = {}
        self.last_raw_delta_candidates: tuple[tuple[int, int], ...] = ()
        self.raw_qualified_delta_four: set[int] = set()
        self.pending_context: dict[int, dict[str, Any]] = {}
        self._selected_big_trade_by_side: dict[str, dict[str, Any]] = {}
        self._lineage_big_trade_occurrence: dict[int, int] = {}
        self._consumed_big_trade_occurrence_ids: set[int] = set()
        self.active_profile_poc_volume = 0
        self.active_internal_value_level_count = 0
        self.active_internal_value_min_volume: int | None = None
        self.active_internal_value_min_volume_tick: int | None = None
        self.diagnostics.update(
            {
                "adaptive_midpoint_target_rejections": 0,
                "adaptive_atr_context_available": 1,
                "adaptive_delta_threshold_unavailable_decisions": 0,
                "adaptive_aoi_edge_distance_rejections": 0,
                "adaptive_internal_lvn_rejections": 0,
                "adaptive_big_trade_aoi_consumed": 0,
                "adaptive_big_trade_threshold": int(
                    big_trade_seed.threshold_volume
                ),
            }
        )

    def advance_feature_event(self, event: CanonicalEvent) -> None:
        tape = self.feature_tape
        if tape is None:
            super().advance_feature_event(event)
            return
        if event.event_index != self.event_count:
            raise AssertionError("Adaptive Yush feature-tape events must be contiguous.")
        if int(tape.timestamp_ns[event.event_index]) != event.timestamp_ns:
            raise AssertionError("Adaptive Yush feature tape timestamp drifted.")
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
            and self._feature_decision_indices[self._feature_decision_cursor]
            <= event.event_index
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
        self.or_high_tick = snapshot.or_high_tick
        self.or_low_tick = snapshot.or_low_tick
        self.active_atr_points = float(snapshot.atr_points)
        self.active_aoi_width_limit_ticks = int(snapshot.aoi_width_limit_ticks)
        self.average_abs_delta_per_level = snapshot.average_abs_delta_per_level
        self.active_profile_poc_volume = int(snapshot.profile_poc_volume)
        self.active_internal_value_level_count = int(
            snapshot.internal_value_level_count
        )
        self.active_internal_value_min_volume = (
            None
            if snapshot.internal_value_min_volume is None
            else int(snapshot.internal_value_min_volume)
        )
        self.active_internal_value_min_volume_tick = (
            None
            if snapshot.internal_value_min_volume_tick is None
            else int(snapshot.internal_value_min_volume_tick)
        )
        self._activate_thresholds()
        self._activate_delta_crossings(snapshot)
        self.qualified_delta_four = {
            int(bucket)
            for bucket, value in snapshot.raw_delta_candidates
            if self.active_delta_threshold is not None
            and abs(int(value)) >= self.active_delta_threshold
        }
        for raw in snapshot.raw_big_trade_candidates:
            occurrence = dict(raw)
            occurrence["occurrence_id"] = len(self.big_trade_occurrences) + 1
            occurrence["configured_threshold"] = self.active_big_trade_threshold
            self.big_trade_occurrences.append(occurrence)
        self.decision_due = True
        self.diagnostics["decision_intervals"] += 1

    def _activate_delta_crossings(
        self,
        snapshot: AdaptiveDecisionSnapshot,
    ) -> None:
        threshold = self.active_delta_threshold
        if threshold is None:
            self.diagnostics["adaptive_delta_threshold_unavailable_decisions"] += 1
            return
        bar_id = self._bar_id(int(self.timestamp_ns[snapshot.event_index]))
        for bucket, value in snapshot.dirty_bar_delta_values.items():
            key = (bar_id, int(bucket))
            before = int(self._last_decision_bar_delta.get(key, 0))
            if abs(before) < threshold <= abs(int(value)):
                self.delta_threshold_crossings[key] = snapshot.event_index
            self._last_decision_bar_delta[key] = int(value)

    def _ingest_idle_batch(self, batch: CanonicalEventBatch) -> None:
        super()._ingest_idle_batch(batch)
        prices = np.asarray(batch.price_ticks, dtype=np.int64)
        self._current_bar_buckets.update(
            int(value) for value in np.unique(np.floor_divide(prices, 4))
        )
        low = int(prices.min())
        high = int(prices.max())
        self._current_bar_low_tick = (
            low
            if self._current_bar_low_tick is None
            else min(self._current_bar_low_tick, low)
        )
        self._current_bar_high_tick = (
            high
            if self._current_bar_high_tick is None
            else max(self._current_bar_high_tick, high)
        )
        self._current_bar_last_tick = int(prices[-1])

    def _update_market_state(self, index: int, volume: int, signed: int) -> None:
        super()._update_market_state(index, volume, signed)
        price_tick = int(self.price_ticks[index])
        self._current_bar_buckets.add(math.floor(price_tick / 4))
        self._current_bar_low_tick = (
            price_tick
            if self._current_bar_low_tick is None
            else min(self._current_bar_low_tick, price_tick)
        )
        self._current_bar_high_tick = (
            price_tick
            if self._current_bar_high_tick is None
            else max(self._current_bar_high_tick, price_tick)
        )
        self._current_bar_last_tick = price_tick

    def _finalize_completed_bar(self, timestamp_ns: int, price_tick: int) -> None:
        incoming_bar_id = self._bar_id(timestamp_ns)
        if self.current_bar_id is not None and incoming_bar_id != self.current_bar_id:
            self._complete_adaptive_bar()
        super()._finalize_completed_bar(timestamp_ns, price_tick)

    def _complete_adaptive_bar(self) -> None:
        if self.base_four is not None:
            for bucket in self._current_bar_buckets:
                index = int(bucket) - int(self.base_four)
                if 0 <= index < len(self.bar_delta_four):
                    self.completed_abs_delta += abs(int(self.bar_delta_four[index]))
                    self.completed_delta_occurrences += 1
        if self.completed_delta_occurrences:
            self.average_abs_delta_per_level = (
                self.completed_abs_delta / self.completed_delta_occurrences
            )

        if (
            self._current_bar_high_tick is not None
            and self._current_bar_low_tick is not None
            and self._current_bar_last_tick is not None
        ):
            true_range_ticks = max(
                self._current_bar_high_tick - self._current_bar_low_tick,
                abs(self._current_bar_high_tick - self._atr_previous_close_tick),
                abs(self._current_bar_low_tick - self._atr_previous_close_tick),
            )
            true_range_points = true_range_ticks * self.cfg.tick_size
            lookback = int(self.cfg.aoi_atr_lookback_bars)
            self.active_atr_points = (
                (self.active_atr_points * (lookback - 1)) + true_range_points
            ) / lookback
            self._atr_previous_close_tick = int(self._current_bar_last_tick)
            self.active_aoi_width_limit_ticks = self._aoi_width_ticks(
                self.active_atr_points
            )

        self._current_bar_buckets.clear()
        self._current_bar_high_tick = None
        self._current_bar_low_tick = None
        self._current_bar_last_tick = None

    def _finalize_decision_interval(self, event_index: int) -> None:
        if event_index < 0:
            return
        timestamp_ns = int(self.timestamp_ns[event_index])
        bar_id = self._bar_id(timestamp_ns)
        self._activate_thresholds()
        self.last_decision_atr_points = self.active_atr_points
        self.last_decision_aoi_width_limit_ticks = (
            self.active_aoi_width_limit_ticks
        )
        self.last_decision_average_abs_delta_per_level = (
            self.average_abs_delta_per_level
        )

        dirty = tuple(sorted(self._dirty_four_buckets))
        self.last_dirty_bar_delta_values = {}
        threshold = self.active_delta_threshold
        if threshold is None:
            self.diagnostics["adaptive_delta_threshold_unavailable_decisions"] += 1
        for bucket in dirty:
            if self.base_four is None or not self.base_four <= bucket <= int(self.top_four):
                continue
            value = int(self.bar_delta_four[bucket - int(self.base_four)])
            self.last_dirty_bar_delta_values[int(bucket)] = value
            key = (bar_id, bucket)
            before = int(self._last_decision_bar_delta.get(key, 0))
            if threshold is not None and abs(before) < threshold <= abs(value):
                self.delta_threshold_crossings[key] = event_index
            self._last_decision_bar_delta[key] = value

        for center in {
            candidate for bucket in dirty for candidate in range(bucket - 2, bucket + 3)
        }:
            if self._delta_level_qualifies_at_multiple(
                center,
                MINIMUM_DELTA_MULTIPLE,
            ):
                self.raw_qualified_delta_four.add(center)
            else:
                self.raw_qualified_delta_four.discard(center)
            if self._delta_level_qualifies_at_multiple(
                center,
                self.cfg.delta_average_multiple,
            ):
                self.qualified_delta_four.add(center)
            else:
                self.qualified_delta_four.discard(center)
        self.last_raw_delta_candidates = tuple(
            (
                int(center),
                int(self.delta_four[center - int(self.base_four)]),
            )
            for center in sorted(self.raw_qualified_delta_four)
        )
        self.qualified_delta_one.clear()
        self._dirty_four_buckets.clear()

        raw_big: list[dict[str, Any]] = []
        for (price_tick, side), volume in sorted(
            self._decision_big_trade_volume.items()
        ):
            if side not in {"A", "B"}:
                continue
            if int(volume) < self.active_big_trade_threshold:
                continue
            raw = {
                "qualified_at_ns": timestamp_ns,
                "qualified_event_index": event_index,
                "price_tick": int(price_tick),
                "side": side,
                "volume": int(volume),
                "configured_threshold": int(
                    self.active_big_trade_threshold
                ),
                "reference_percentile": (
                    self.big_trade_seed.reference_percentile
                ),
                "lookback_sessions": (
                    self.big_trade_seed.lookback_sessions
                ),
            }
            raw_big.append(raw)
            occurrence = {
                **raw,
                "occurrence_id": len(self.big_trade_occurrences) + 1,
            }
            self.big_trade_occurrences.append(occurrence)
        self.last_interval_big_candidates = tuple(raw_big)

        self.current_profile = self._profile()
        self._refresh_internal_value_profile_state()
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

    def _activate_thresholds(self) -> None:
        self.active_big_trade_threshold = int(
            self.big_trade_seed.threshold_volume
        )
        self.active_delta_threshold = (
            None
            if self.average_abs_delta_per_level is None
            else self.average_abs_delta_per_level
            * self.cfg.delta_average_multiple
        )

    def _refresh_internal_value_profile_state(self) -> None:
        """Freeze causal developing-profile continuity at a decision boundary."""

        profile = self.current_profile
        base_tick = self.base_tick
        if profile is None or base_tick is None or not len(self.profile_volume):
            self.active_profile_poc_volume = 0
            self.active_internal_value_level_count = 0
            self.active_internal_value_min_volume = None
            self.active_internal_value_min_volume_tick = None
            return

        val_tick = int(profile["val_tick"])
        vah_tick = int(profile["vah_tick"])
        poc_tick = int(profile["poc_tick"])
        poc_index = poc_tick - int(base_tick)
        if not 0 <= poc_index < len(self.profile_volume):
            raise AssertionError("developing POC lies outside the causal profile")
        self.active_profile_poc_volume = int(self.profile_volume[poc_index])

        interior_low = val_tick + 1
        interior_high = vah_tick - 1
        if interior_high < interior_low:
            self.active_internal_value_level_count = 0
            self.active_internal_value_min_volume = None
            self.active_internal_value_min_volume_tick = None
            return
        start = interior_low - int(base_tick)
        stop = interior_high - int(base_tick) + 1
        if start < 0 or stop > len(self.profile_volume):
            raise AssertionError("developing value area lies outside the causal profile")
        interior = self.profile_volume[start:stop]
        minimum_offset = int(np.argmin(interior))
        self.active_internal_value_level_count = int(len(interior))
        self.active_internal_value_min_volume = int(interior[minimum_offset])
        self.active_internal_value_min_volume_tick = (
            interior_low + minimum_offset
        )

    def _internal_value_profile_passes(self, *, record_rejection: bool) -> bool:
        """Reject a strict interior LVN below 10% of developing POC volume."""

        poc_volume = int(self.active_profile_poc_volume)
        level_count = int(self.active_internal_value_level_count)
        minimum = self.active_internal_value_min_volume
        passed = (
            poc_volume > 0
            and (
                level_count == 0
                or (
                    minimum is not None
                    and float(minimum)
                    >= poc_volume * self.cfg.internal_lvn_poc_fraction
                )
            )
        )
        if not passed and record_rejection:
            self.diagnostics["adaptive_internal_lvn_rejections"] += 1
        return passed

    def _aoi_width_ticks(self, atr_points: float) -> int:
        points = min(
            self.cfg.aoi_atr_max_points,
            float(atr_points) * self.cfg.aoi_atr_multiple,
        )
        return max(1, int(math.floor(points / self.cfg.tick_size + 1e-12)))

    def _delta_level_qualifies_at_multiple(
        self,
        center_tick: int,
        multiple: float,
    ) -> bool:
        if (
            self.average_abs_delta_per_level is None
            or self.base_four is None
        ):
            return False
        center = center_tick - int(self.base_four)
        if center - 2 < 0 or center + 2 >= len(self.delta_four):
            return False
        neighbours = (center - 2, center - 1, center + 1, center + 2)
        if not bool(self.traded_four[center]) or not all(
            bool(self.traded_four[item]) for item in neighbours
        ):
            return False
        magnitude = abs(int(self.delta_four[center]))
        neighbour_mean = sum(
            abs(int(self.delta_four[item])) for item in neighbours
        ) / 4.0
        return (
            magnitude >= self.average_abs_delta_per_level * multiple
            and magnitude >= self.cfg.delta_neighbour_multiple * neighbour_mean
        )

    def _selected_candidates(self) -> dict[str, AoiCandidate]:
        profile = self.current_profile
        if profile is None:
            return {}
        snapshot = (
            self.active_feature_snapshot
            if self.feature_tape is not None
            else None
        )
        market = (
            list(snapshot.market_confluences)
            if isinstance(snapshot, AdaptiveDecisionSnapshot)
            else self._market_confluences()
        )
        delta = self._delta_confluences()
        tape = self.feature_tape
        selected: dict[str, AoiCandidate] = {}
        self._selected_big_trade_by_side = {}
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
            big_occurrence = self._latest_active_big_trade_near(anchor)
            if big_occurrence is None:
                self._candidate_cache_keys[side] = None
                self._candidate_cache[side] = None
                continue
            self._selected_big_trade_by_side[side] = big_occurrence
            price_tick = int(big_occurrence["price_tick"])
            categories = {
                "market": market,
                "delta_profile": delta,
                "big_trade": [
                    ConfluencePoint(
                        "big_trade",
                        "BIG_TRADE_LEVEL",
                        price_tick,
                        price_tick,
                        price_tick,
                    )
                ],
            }
            signature = tuple(
                _point_signature(point)
                for name in categories
                for point in categories[name]
            )
            key = (anchor, self.active_aoi_width_limit_ticks, signature)
            if self._candidate_cache_keys[side] == key:
                candidate = self._candidate_cache[side]
                self.diagnostics["aoi_cache_hits"] += 1
            else:
                shared_key = (side, direction, *key)
                if tape is not None and shared_key in tape.candidate_cache:
                    candidate = tape.candidate_cache[shared_key]
                else:
                    candidate = _best_required_big_trade_cluster_aoi(
                        side,
                        direction,
                        anchor,
                        categories,
                        self.active_aoi_width_limit_ticks,
                    )
                    if tape is not None:
                        tape.candidate_cache[shared_key] = candidate
                self._candidate_cache_keys[side] = key
                self._candidate_cache[side] = candidate
                self.diagnostics["aoi_cache_misses"] += 1
            if candidate is not None:
                selected[side] = candidate
        return selected

    def _latest_active_big_trade_near(
        self,
        anchor_tick: int,
    ) -> dict[str, Any] | None:
        eligible = [
            item
            for item in self.big_trade_occurrences
            if abs(int(item["price_tick"]) - int(anchor_tick))
            <= self.active_aoi_width_limit_ticks
        ]
        if not eligible:
            return None
        latest = max(
            eligible,
            key=lambda item: (
                int(item["qualified_event_index"]),
                int(item["occurrence_id"]),
            ),
        )
        if (
            int(latest["occurrence_id"])
            in self._consumed_big_trade_occurrence_ids
        ):
            return None
        return latest

    def _apply_candidate(
        self,
        side: str,
        candidate: AoiCandidate | None,
        timestamp_ns: int,
        event_index: int,
    ) -> None:
        current = self.lineages[side]
        occurrence = self._selected_big_trade_by_side.get(side)
        previous_occurrence_id = (
            None
            if current is None
            else self._lineage_big_trade_occurrence.get(current.lineage_id)
        )
        next_occurrence_id = (
            None if occurrence is None else int(occurrence["occurrence_id"])
        )
        if (
            current is not None
            and current.visit is None
            and next_occurrence_id is not None
            and previous_occurrence_id is not None
            and next_occurrence_id != previous_occurrence_id
        ):
            self.lineages[side] = None
            self.diagnostics["aoi_fingerprint_resets"] += 1
        super()._apply_candidate(side, candidate, timestamp_ns, event_index)
        lineage = self.lineages[side]
        if lineage is not None and occurrence is not None:
            self._lineage_big_trade_occurrence[lineage.lineage_id] = int(
                occurrence["occurrence_id"]
            )

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
        value = int(self.decision_bar_delta_values.get(bucket, 0))
        crossed_at = self.delta_threshold_crossings.get((bar_id, bucket))
        if (
            self.active_delta_threshold is not None
            and crossed_at is not None
            and tap_event_index < crossed_at <= index
            and abs(value) >= self.active_delta_threshold
            and _price_in_or_beyond(candidate, bucket * 4, bucket * 4 + 3)
        ):
            self.diagnostics["delta_bubbles"] += 1
            return {
                "kind": "adaptive_delta_4tick_3m",
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
        if not eligible:
            return None
        item = max(eligible, key=lambda raw: int(raw["qualified_event_index"]))
        self.diagnostics["big_trade_bubbles"] += 1
        return {
            "kind": "adaptive_big_trade_100ms",
            "price_tick": int(item["price_tick"]),
            "value": int(item["volume"]),
            "side": str(item["side"]),
            "threshold": int(item["configured_threshold"]),
            "qualified_at_ns": int(item["qualified_at_ns"]),
            "qualified_event_index": int(item["qualified_event_index"]),
        }

    def _pending_is_live(
        self,
        pending: PendingOrder,
        candidate: AoiCandidate,
        index: int,
    ) -> bool:
        if not self._internal_value_profile_passes(record_rejection=True):
            return False
        anchor = self._current_anchor(candidate.side)
        if anchor is None or not candidate.low_tick <= anchor <= candidate.high_tick:
            return False
        if pending.trigger_kind == "adaptive_big_trade_100ms":
            return True
        decision_index = self.decision_event_index
        if (
            decision_index is None
            or pending.bubble_bucket is None
            or pending.bubble_bar_id
            != self._bar_id(int(self.timestamp_ns[decision_index]))
            or self.active_delta_threshold is None
        ):
            return False
        value = int(self.decision_bar_delta_values.get(pending.bubble_bucket, 0))
        return abs(value) >= self.active_delta_threshold

    def _preorder_range_gate(
        self,
        index: int,
        lineage: AoiLineage,
    ) -> bool:
        return (
            self._internal_value_profile_passes(record_rejection=True)
            and super()._preorder_range_gate(index, lineage)
        )

    def _update_visit_and_order(self, lineage: AoiLineage, index: int) -> None:
        visit_before = lineage.visit
        before = lineage.pending
        super()._update_visit_and_order(lineage, index)
        if visit_before is None and lineage.visit is not None:
            occurrence_id = self._lineage_big_trade_occurrence.get(
                lineage.lineage_id
            )
            if occurrence_id is not None:
                self._consumed_big_trade_occurrence_ids.add(occurrence_id)
                self.diagnostics["adaptive_big_trade_aoi_consumed"] += 1
        if lineage.pending is not None and lineage.pending is not before:
            occurrence_id = self._lineage_big_trade_occurrence.get(
                lineage.lineage_id
            )
            occurrence = next(
                (
                    item
                    for item in self.big_trade_occurrences
                    if int(item["occurrence_id"]) == occurrence_id
                ),
                None,
            )
            trigger_occurrence = next(
                (
                    item
                    for item in self.big_trade_occurrences
                    if lineage.pending is not None
                    and lineage.pending.trigger_kind
                    == "adaptive_big_trade_100ms"
                    and int(item["qualified_event_index"])
                    == int(lineage.pending.bubble_event_index)
                    and int(item["price_tick"])
                    == int(lineage.pending.bubble_price_tick)
                    and int(item["volume"])
                    == int(lineage.pending.bubble_value or 0)
                ),
                None,
            )
            self.pending_context[lineage.lineage_id] = {
                "aoi_atr_points": self.active_atr_points,
                "aoi_atr_multiple": self.cfg.aoi_atr_multiple,
                "aoi_width_limit_points": (
                    self.active_aoi_width_limit_ticks * self.cfg.tick_size
                ),
                "big_trade_threshold": int(
                    self.active_big_trade_threshold
                ),
                "big_trade_reference_percentile": (
                    self.big_trade_seed.reference_percentile
                ),
                "big_trade_lookback_sessions": (
                    self.big_trade_seed.lookback_sessions
                ),
                "big_trade_reference_observation_count": (
                    self.big_trade_seed.reference_observation_count
                ),
                "big_trade_reference_start_session": (
                    self.big_trade_seed.reference_start_session
                ),
                "big_trade_reference_end_session": (
                    self.big_trade_seed.reference_end_session
                ),
                "big_trade_percentile_method": (
                    self.big_trade_seed.percentile_method
                ),
                "aoi_big_trade_price": (
                    None
                    if occurrence is None
                    else int(occurrence["price_tick"])
                    * self.cfg.tick_size
                ),
                "aoi_big_trade_volume": (
                    None
                    if occurrence is None
                    else int(occurrence["volume"])
                ),
                "aoi_big_trade_side": (
                    None if occurrence is None else str(occurrence["side"])
                ),
                "aoi_big_trade_qualified_timestamp": (
                    None
                    if occurrence is None
                    else pd.Timestamp(
                        int(occurrence["qualified_at_ns"]),
                        tz="UTC",
                    ).tz_convert("America/New_York")
                ),
                "entry_big_trade_price": (
                    None
                    if trigger_occurrence is None
                    else int(trigger_occurrence["price_tick"])
                    * self.cfg.tick_size
                ),
                "entry_big_trade_volume": (
                    None
                    if trigger_occurrence is None
                    else int(trigger_occurrence["volume"])
                ),
                "entry_big_trade_side": (
                    None
                    if trigger_occurrence is None
                    else str(trigger_occurrence["side"])
                ),
                "entry_big_trade_threshold": (
                    None
                    if trigger_occurrence is None
                    else int(trigger_occurrence["configured_threshold"])
                ),
                "average_abs_delta_per_level": self.average_abs_delta_per_level,
                "delta_average_multiple": self.cfg.delta_average_multiple,
                "delta_threshold": self.active_delta_threshold,
                "profile_poc_volume": self.active_profile_poc_volume,
                "internal_value_level_count": (
                    self.active_internal_value_level_count
                ),
                "internal_value_min_volume": (
                    self.active_internal_value_min_volume
                ),
                "internal_value_min_volume_price": (
                    None
                    if self.active_internal_value_min_volume_tick is None
                    else self.active_internal_value_min_volume_tick
                    * self.cfg.tick_size
                ),
                "internal_value_min_volume_ratio_to_poc": (
                    None
                    if not self.active_profile_poc_volume
                    or self.active_internal_value_min_volume is None
                    else self.active_internal_value_min_volume
                    / self.active_profile_poc_volume
                ),
                "internal_lvn_poc_fraction": (
                    self.cfg.internal_lvn_poc_fraction
                ),
                "internal_lvn_present": False,
            }

    def _fill_gate_passes(self, index: int, lineage: AoiLineage) -> bool:
        pending = lineage.pending
        profile = self.current_profile
        if pending is None or profile is None:
            return False
        if not self._internal_value_profile_passes(record_rejection=True):
            return False
        candidate = lineage.candidate
        anchor = self._current_anchor(candidate.side)
        if anchor is None or not candidate.low_tick <= anchor <= candidate.high_tick:
            return False
        if self.required_direction and candidate.direction != self.required_direction:
            return False
        if (
            not self._range_and_profile_pass(index)
            or not self._has_prior_reversal(index, lineage)
        ):
            return False
        event_tick = int(self.price_ticks[index])
        reference_fill = (
            max(pending.entry_tick, event_tick)
            if candidate.direction == "long"
            else min(pending.entry_tick, event_tick)
        )
        risk_ticks = (
            reference_fill - pending.stop_tick
            if candidate.direction == "long"
            else pending.stop_tick - reference_fill
        )
        far_aoi_edge_tick = (
            candidate.low_tick
            if candidate.direction == "long"
            else candidate.high_tick
        )
        entry_to_far_aoi_edge_ticks = (
            reference_fill - far_aoi_edge_tick
            if candidate.direction == "long"
            else far_aoi_edge_tick - reference_fill
        )
        if (
            entry_to_far_aoi_edge_ticks < 0
            or entry_to_far_aoi_edge_ticks
            > self.cfg.max_entry_to_far_aoi_edge_ticks
        ):
            self.diagnostics["adaptive_aoi_edge_distance_rejections"] += 1
            return False
        target_tick = _frozen_target_tick(
            profile,
            direction=candidate.direction,
            target_mode=self.cfg.target_mode,
        )
        target_favorable = (
            target_tick > reference_fill
            if candidate.direction == "long"
            else target_tick < reference_fill
        )
        if not target_favorable:
            self.diagnostics["adaptive_midpoint_target_rejections"] += 1
            return False
        if risk_ticks <= 0 or risk_ticks > self.cfg.max_stop_ticks:
            self.diagnostics["stop_limit_rejections"] += 1
            return False
        return True


def build_adaptive_session_feature_tape(
    session: CanonicalEventSession,
    config: YushAdaptiveOrderflowRangeConfig,
) -> AdaptiveSessionFeatureTape:
    seed = _atr_seed_for_session(session.session_date, config)
    big_trade_seed = _big_trade_seed_for_session(session.session_date, config)
    state = _AdaptiveOrderflowRangeState(
        session.public_view(),
        config,
        seed,
        big_trade_seed,
    )
    events = session.events
    timestamp_values = events["timestamp"].array
    timestamp_ns = events["_canonical_timestamp_ns"].to_numpy(
        dtype=np.int64,
        copy=False,
    )
    source_ordinals = events["source_ordinal"].to_numpy(
        dtype=np.int64,
        copy=False,
    )
    price_ticks = events["event_price_tick"].to_numpy(
        dtype=np.int64,
        copy=False,
    )
    sizes = events["size"].to_numpy(dtype=np.int64, copy=False)
    sides = events["side"].astype(str).to_numpy(copy=False)
    signed = events["signed_size"].to_numpy(dtype=np.int64, copy=False)
    snapshots: dict[int, AdaptiveDecisionSnapshot] = {}

    index = 0
    while index < len(events):
        if state.active_decision_bucket is not None:
            first_bucket = int(
                (int(timestamp_ns[index]) - state.open_ns)
                // state.decision_interval_ns
            )
            if first_bucket == state.active_decision_bucket:
                boundary_ns = (
                    state.open_ns
                    + (first_bucket + 1) * state.decision_interval_ns
                )
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
            snapshots[index] = AdaptiveDecisionSnapshot(
                event_index=int(state.decision_event_index),
                previous_decision_event_index=state.previous_decision_event_index,
                current_profile=(
                    None
                    if state.current_profile is None
                    else dict(state.current_profile)
                ),
                decision_bar_delta_values=dict(state.decision_bar_delta_values),
                dirty_bar_delta_values=dict(
                    state.last_dirty_bar_delta_values
                ),
                raw_delta_candidates=tuple(state.last_raw_delta_candidates),
                raw_big_trade_candidates=tuple(
                    dict(value)
                    for value in state.last_interval_big_candidates
                ),
                market_confluences=tuple(state._market_confluences()),
                or_high_tick=state.or_high_tick,
                or_low_tick=state.or_low_tick,
                atr_points=state.last_decision_atr_points,
                aoi_width_limit_ticks=(
                    state.last_decision_aoi_width_limit_ticks
                ),
                average_abs_delta_per_level=(
                    state.last_decision_average_abs_delta_per_level
                ),
                profile_poc_volume=state.active_profile_poc_volume,
                internal_value_level_count=(
                    state.active_internal_value_level_count
                ),
                internal_value_min_volume=(
                    state.active_internal_value_min_volume
                ),
                internal_value_min_volume_tick=(
                    state.active_internal_value_min_volume_tick
                ),
            )
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
    return AdaptiveSessionFeatureTape(
        session_date=session.session_date,
        timestamp_ns=arrays[0],
        price_ticks=arrays[1],
        cumulative_low=arrays[2],
        cumulative_high=arrays[3],
        neutral_cumulative=arrays[4],
        completed_bars=tuple(state.completed_bars),
        decision_snapshots=snapshots,
    )


class YushAdaptiveOrderflowRangeEventStrategy(YushOrderflowRangeEventStrategy):
    """Certified adapter using the generic canonical event replay broker."""

    def __init__(
        self,
        config: YushAdaptiveOrderflowRangeConfig | None = None,
    ) -> None:
        super().__init__(config or YushAdaptiveOrderflowRangeConfig())
        self.cfg: YushAdaptiveOrderflowRangeConfig

    def prepare_session_features(
        self,
        session: CanonicalEventSession,
    ) -> AdaptiveSessionFeatureTape:
        return build_adaptive_session_feature_tape(session, self.cfg)

    def on_session_start(
        self,
        session: EventReplaySessionView,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        seed = _atr_seed_for_session(session.session_date, self.cfg)
        big_trade_seed = _big_trade_seed_for_session(
            session.session_date,
            self.cfg,
        )
        self.state = _AdaptiveOrderflowRangeState(
            session,
            self.cfg,
            seed,
            big_trade_seed,
        )
        tape = self._session_feature_tapes.get(str(session.session_date))
        if tape is not None:
            if not isinstance(tape, AdaptiveSessionFeatureTape):
                raise TypeError("adaptive v02 requires its parameter-invariant tape")
            self._state().bind_feature_tape(tape)

    def _sync_pending_order(
        self,
        side: str,
        lineage: AoiLineage,
        broker: EventReplayBroker,
    ) -> None:
        pending = lineage.pending
        state = self._state()
        if pending is None or state.current_profile is None:
            return
        target_tick = _frozen_target_tick(
            state.current_profile,
            direction=lineage.candidate.direction,
            target_mode=self.cfg.target_mode,
        )
        valid = (
            target_tick > pending.entry_tick
            if lineage.candidate.direction == "long"
            else target_tick < pending.entry_tick
        )
        if not valid:
            state.diagnostics["adaptive_midpoint_target_rejections"] += 1
            lineage.pending = None
            broker.cancel_entry(side, reason="midpoint_not_favorable")
            return
        broker.submit_or_replace_entry(
            order_id=side,
            direction=lineage.candidate.direction,
            entry_tick=pending.entry_tick,
            stop_tick=pending.stop_tick,
            target_tick=target_tick,
            priority=0 if side == "VAL" else 1,
            metadata={"side": side, "lineage_id": lineage.lineage_id},
            report_fields={
                "target_mode": self.cfg.target_mode,
                "frozen_target_price": target_tick * self.cfg.tick_size,
            },
        )

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        lineage = self._lineage_for_order(order)
        if lineage is None:
            raise AssertionError("Adaptive AOI lineage must exist at fill.")
        context = dict(state.pending_context.get(lineage.lineage_id) or {})
        fingerprint = _format_aoi_fingerprint(
            _aoi_fingerprint(lineage.candidate),
            self.cfg.tick_size,
        )
        ExactYushRangeEventStrategy.on_entry_filled(
            self,
            order,
            position,
            event,
            broker,
        )
        source_quality_label = str(
            state.session.metadata.get(
                "source_quality_label",
                "Governed canonical trade events; source identity is hash-bound.",
            )
        )
        broker.annotate_position(
            **context,
            aoi_lineage_mode=self.cfg.aoi_lineage_mode,
            aoi_exact_fingerprint=fingerprint,
            target_mode=self.cfg.target_mode,
            frozen_target_price=(
                None
                if order.target_tick is None
                else order.target_tick * self.cfg.tick_size
            ),
            target_mechanic=(
                "frozen_developing_value_midpoint_no_breakeven"
                if self.cfg.target_mode == "midpoint"
                else "frozen_opposite_developing_value_edge_no_breakeven"
            ),
            risk_cap_dollars=250.0,
            entry_to_far_aoi_edge_points=(
                (
                    position.entry_reference_tick - lineage.candidate.low_tick
                    if position.direction == "long"
                    else lineage.candidate.high_tick - position.entry_reference_tick
                )
                * self.cfg.tick_size
            ),
            max_entry_to_far_aoi_edge_points=(
                self.cfg.max_entry_to_far_aoi_edge_points
            ),
            planned_risk_dollars=(
                position.risk_points
                * self.cfg.point_value
                * self.cfg.contracts
            ),
            round_trip_commission_per_contract=(
                2.0 * self.cfg.commission_per_contract
            ),
            source_quality_label=source_quality_label,
            fill_model="next_trade_stop_market_zero_slippage",
        )

    def position_batch_stop(
        self,
        price_ticks: np.ndarray,
        *,
        start: int,
        stop: int,
        position: EventPositionView,
    ) -> int:
        boundary = int(stop)
        active_start = max(
            int(start),
            int(position.bracket_active_from_event_index),
        )
        if active_start >= boundary:
            return boundary
        values = price_ticks[active_start:boundary]
        stop_crossed = (
            values <= int(position.stop_tick)
            if position.direction == "long"
            else values >= int(position.stop_tick)
        )
        stop_locations = np.flatnonzero(stop_crossed)
        if len(stop_locations):
            boundary = min(
                boundary,
                active_start + int(stop_locations[0]),
            )
        if position.target_tick is not None:
            target_crossed = (
                values >= int(position.target_tick)
                if position.direction == "long"
                else values <= int(position.target_tick)
            )
            target_locations = np.flatnonzero(target_crossed)
            if len(target_locations):
                boundary = min(
                    boundary,
                    active_start + int(target_locations[0]),
                )
        return boundary

    def position_directive(
        self,
        event: CanonicalEvent,
        position: EventPositionView,
        broker: EventReplayBroker,
    ) -> PositionDirective:
        del event, position, broker
        return PositionDirective()

    def _state(self) -> _AdaptiveOrderflowRangeState:
        state = self.state
        if not isinstance(state, _AdaptiveOrderflowRangeState):
            raise RuntimeError("Adaptive Yush strategy has not started a session.")
        return state


def _best_required_big_trade_cluster_aoi(
    side: str,
    direction: str,
    anchor_tick: int,
    categories: dict[str, list[ConfluencePoint]],
    max_width_ticks: int,
) -> AoiCandidate | None:
    """Select the best bounded cluster while requiring its one big-trade level."""

    big_points = tuple(categories.get("big_trade") or ())
    if len(big_points) != 1:
        return None
    local = {
        name: tuple(
            point
            for point in points
            if max(anchor_tick, point.interval_high_tick)
            - min(anchor_tick, point.interval_low_tick)
            <= max_width_ticks
        )
        for name, points in categories.items()
    }
    big = big_points[0]
    if big not in local["big_trade"]:
        return None

    best: tuple[
        tuple,
        tuple[str, ...],
        tuple[ConfluencePoint, ...],
        int,
        int,
    ] | None = None
    for low in range(anchor_tick - max_width_ticks, anchor_tick + 1):
        for high in range(
            anchor_tick,
            min(anchor_tick + max_width_ticks, low + max_width_ticks) + 1,
        ):
            if not (
                low <= big.interval_low_tick
                and big.interval_high_tick <= high
            ):
                continue
            selected_by_category = {
                name: tuple(
                    point
                    for point in points
                    if low <= point.interval_low_tick
                    and point.interval_high_tick <= high
                )
                for name, points in local.items()
            }
            names = tuple(
                name for name in categories if selected_by_category[name]
            )
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
    return AoiCandidate(
        side,
        direction,
        anchor_tick,
        low,
        high,
        names,
        selected,
    )


def _frozen_target_tick(
    profile: dict[str, int],
    *,
    direction: str,
    target_mode: str,
) -> int:
    if target_mode == "opposite_value_edge":
        return (
            int(profile["vah_tick"])
            if direction == "long"
            else int(profile["val_tick"])
        )
    raw_midpoint = (
        int(profile["vah_tick"]) + int(profile["val_tick"])
    ) / 2.0
    return (
        math.floor(raw_midpoint)
        if direction == "long"
        else math.ceil(raw_midpoint)
    )


@lru_cache(maxsize=8)
def _load_atr_context(path_text: str, expected_sha256: str) -> pd.DataFrame:
    path = Path(path_text).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"adaptive ATR context is missing: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            "adaptive ATR context hash drift: "
            f"expected {expected_sha256}, got {actual}"
        )
    frame = pd.read_parquet(path)
    required = {
        "session_date",
        "source_contract_symbol",
        "atr14_3m_seed_points",
        "previous_close_points",
        "last_seed_bar_close",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            "adaptive ATR context is missing columns: " + ", ".join(missing)
        )
    if frame["session_date"].astype(str).duplicated().any():
        raise ValueError("adaptive ATR context has duplicate session dates")
    return frame.assign(
        session_date=frame["session_date"].astype(str)
    ).set_index("session_date", drop=False)


def _atr_seed_for_session(
    session_date: object,
    config: YushAdaptiveOrderflowRangeConfig,
) -> AdaptiveAtrSeed:
    frame = _load_atr_context(
        config.atr_context_path,
        config.atr_context_sha256,
    )
    key = str(session_date)
    if key not in frame.index:
        raise ValueError(f"adaptive ATR context has no seed for session {key}")
    row = frame.loc[key]
    if isinstance(row, pd.DataFrame):
        raise ValueError(f"adaptive ATR context is ambiguous for session {key}")
    atr_points = float(row["atr14_3m_seed_points"])
    previous_close = float(row["previous_close_points"])
    if not math.isfinite(atr_points) or atr_points <= 0:
        raise ValueError(f"adaptive ATR seed is invalid for session {key}")
    return AdaptiveAtrSeed(
        atr_points=atr_points,
        previous_close_tick=int(round(previous_close / config.tick_size)),
        source_contract_symbol=str(row["source_contract_symbol"]),
        last_seed_bar_close=pd.Timestamp(row["last_seed_bar_close"]),
    )


@lru_cache(maxsize=8)
def _load_big_trade_context(
    path_text: str,
    expected_sha256: str,
) -> pd.DataFrame:
    path = Path(path_text).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"big-trade context is missing: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            "big-trade context hash drift: "
            f"expected {expected_sha256}, got {actual}"
        )
    frame = pd.read_parquet(path)
    required = {
        "session_date",
        "lookback_sessions",
        "reference_percentile",
        "percentile_method",
        "threshold_volume",
        "reference_observation_count",
        "reference_start_session",
        "reference_end_session",
        "aggregation_interval_ms",
        "aggregation_price_ticks",
        "aggregation_side_scope",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            "big-trade context is missing columns: " + ", ".join(missing)
        )
    if frame["session_date"].astype(str).duplicated().any():
        raise ValueError("big-trade context has duplicate session dates")
    return frame.assign(
        session_date=frame["session_date"].astype(str)
    ).set_index("session_date", drop=False)


def _big_trade_seed_for_session(
    session_date: object,
    config: YushAdaptiveOrderflowRangeConfig,
) -> BigTradeThresholdSeed:
    frame = _load_big_trade_context(
        config.big_trade_context_path,
        config.big_trade_context_sha256,
    )
    key = str(session_date)
    if key not in frame.index:
        raise ValueError(f"big-trade context has no seed for session {key}")
    row = frame.loc[key]
    if isinstance(row, pd.DataFrame):
        raise ValueError(f"big-trade context is ambiguous for session {key}")
    percentile = float(row["reference_percentile"])
    lookback = int(row["lookback_sessions"])
    threshold = int(row["threshold_volume"])
    observations = int(row["reference_observation_count"])
    fixed_semantics = (
        lookback == config.big_trade_lookback_sessions
        and math.isclose(
            percentile,
            config.big_trade_reference_percentile,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and str(row["percentile_method"]) == "nearest_rank_higher"
        and int(row["aggregation_interval_ms"]) == 100
        and int(row["aggregation_price_ticks"]) == 1
        and str(row["aggregation_side_scope"])
        == "same_aggressor_side_A_or_B"
    )
    if not fixed_semantics:
        raise ValueError(
            f"big-trade context semantics drift for session {key}"
        )
    if threshold <= 0 or observations <= 0:
        raise ValueError(f"big-trade context seed is invalid for session {key}")
    reference_start = str(row["reference_start_session"])
    reference_end = str(row["reference_end_session"])
    if not reference_start < reference_end < key:
        raise ValueError(
            f"big-trade context is non-causal for session {key}"
        )
    return BigTradeThresholdSeed(
        threshold_volume=threshold,
        reference_percentile=percentile,
        lookback_sessions=lookback,
        reference_observation_count=observations,
        reference_start_session=reference_start,
        reference_end_session=reference_end,
        percentile_method=str(row["percentile_method"]),
    )
