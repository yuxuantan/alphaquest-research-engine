"""Deterministic institutional-footprint range-edge failure mechanics.

The v02 signal is deliberately small: freeze a developing value edge only
after an adaptive large-execution or top-decile delta footprint exists there,
veto a direction-aligned breakout trend, then require a causal sweep and
completed close back inside value. Account-level daily limits remain outside
the signal so the core test measures the edge rather than a prop overlay.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, fields
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

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


STRATEGY_ID = "yush_adaptive_orderflow_range"
ENTRY_MODULE = STRATEGY_ID
STOP_MODULE = "event_sweep_structural_stop"
TARGET_MODULE = "event_value_area_scale_out"
BUY_SIDE = "B"
SELL_SIDE = "A"
REGIME_NON_TRENDING = "no_directional_breakout_trend"
REGIME_INSUFFICIENT = "insufficient_trend_history"
REGIME_BULLISH = "bullish_trend"
REGIME_BEARISH = "bearish_trend"
VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD = "motivewave_standard"
VALUE_AREA_PAIR_ROWS = 2
BIG_TRADE_AGGREGATION_FIXED_CELL = "fixed_cell_price_side"
BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE = "motivewave_consecutive"


@dataclass(frozen=True)
class ChartFanaticsRangeConfig:
    tick_size: float = 0.25
    point_value: float = 50.0
    commission_per_contract: float = 1.55
    bar_seconds: int = 180
    price_bin_ticks: int = 4
    value_area_fraction: float = 0.70
    value_area_method: str = VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD
    opening_range_seconds: int = 30
    aoi_level_distance_ticks: int = 4
    aoi_big_trade_lookback_minutes: int = 30
    big_trade_reference_percentile: float = 0.995
    big_trade_lookback_sessions: int = 20
    big_trade_interval_ms: int = 100
    big_trade_price_bucket_ticks: int = 1
    big_trade_aggregation_mode: str = BIG_TRADE_AGGREGATION_FIXED_CELL
    delta_profile_percentile: float = 0.90
    regime_window_bars: int = 10
    trend_midpoint_shift_ticks: int = 8
    trend_poc_shift_ticks: int = 8
    trend_overlap_maximum: float = 0.50
    trend_efficiency_minimum: float = 0.55
    sweep_minimum_ticks: int = 2
    failure_confirmation_bars: int = 3
    morning_entry_start: str = "09:33:00"
    morning_entry_end: str = "11:30:00"
    afternoon_entry_start: str = "13:30:00"
    afternoon_entry_end: str = "15:30:00"
    entry_offset_ticks: int = 1
    stop_offset_ticks: int = 2
    minimum_stop_ticks: int = 6
    maximum_stop_ticks: int = 60
    maximum_stop_atr_multiple: float = 1.25
    atr_lookback_bars: int = 14
    target_1_fraction: float = 0.50
    maximum_holding_bars: int = 12
    entry_expiry_bars: int = 2
    maximum_entries_per_aoi: int = 1
    risk_budget_dollars: float = 1600.0
    atr_context_path: str = (
        "research/datasets/"
        "es_sierra_yush_events_20110815_20260529_0930_1100_ny_inv02/"
        "atr14_3m_eth_context.parquet"
    )
    atr_context_sha256: str = "436529d23c3c1fd172139d945e080fab49e6c4eca092700fd18c9c07d6624de4"
    big_trade_context_path: str = (
        "research/datasets/"
        "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/"
        "big_trade_100ms_q995_prior20_context.parquet"
    )
    big_trade_context_sha256: str = "139f53eea8b3808390c891831c659ba8d9e5c659e8ae9b7ea17644d8fa481ca6"

    def __post_init__(self) -> None:
        fixed = {
            "tick_size": (self.tick_size, 0.25),
            "point_value": (self.point_value, 50.0),
            "commission_per_contract": (
                self.commission_per_contract,
                1.55,
            ),
            "bar_seconds": (self.bar_seconds, 180),
            "price_bin_ticks": (self.price_bin_ticks, 4),
            "value_area_fraction": (self.value_area_fraction, 0.70),
            "opening_range_seconds": (self.opening_range_seconds, 30),
            "aoi_level_distance_ticks": (
                self.aoi_level_distance_ticks,
                4,
            ),
            "aoi_big_trade_lookback_minutes": (
                self.aoi_big_trade_lookback_minutes,
                30,
            ),
            "big_trade_reference_percentile": (
                self.big_trade_reference_percentile,
                0.995,
            ),
            "big_trade_lookback_sessions": (
                self.big_trade_lookback_sessions,
                20,
            ),
            "big_trade_interval_ms": (
                self.big_trade_interval_ms,
                100,
            ),
            "big_trade_price_bucket_ticks": (
                self.big_trade_price_bucket_ticks,
                1,
            ),
            "delta_profile_percentile": (
                self.delta_profile_percentile,
                0.90,
            ),
            "regime_window_bars": (self.regime_window_bars, 10),
            "trend_midpoint_shift_ticks": (
                self.trend_midpoint_shift_ticks,
                8,
            ),
            "trend_poc_shift_ticks": (
                self.trend_poc_shift_ticks,
                8,
            ),
            "trend_overlap_maximum": (
                self.trend_overlap_maximum,
                0.50,
            ),
            "trend_efficiency_minimum": (
                self.trend_efficiency_minimum,
                0.55,
            ),
            "entry_offset_ticks": (self.entry_offset_ticks, 1),
            "stop_offset_ticks": (self.stop_offset_ticks, 2),
            "minimum_stop_ticks": (self.minimum_stop_ticks, 6),
            "maximum_stop_ticks": (self.maximum_stop_ticks, 60),
            "atr_lookback_bars": (self.atr_lookback_bars, 14),
            "target_1_fraction": (self.target_1_fraction, 0.50),
            "entry_expiry_bars": (self.entry_expiry_bars, 2),
            "maximum_entries_per_aoi": (
                self.maximum_entries_per_aoi,
                1,
            ),
            "risk_budget_dollars": (self.risk_budget_dollars, 1600.0),
        }
        drift = [
            name
            for name, (actual, expected) in fixed.items()
            if not math.isclose(
                float(actual),
                float(expected),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ]
        if drift:
            raise ValueError("fixed Chart Fanatics v02 mechanic drift: " + ", ".join(drift))
        tunable_choices = {
            "sweep_minimum_ticks": (self.sweep_minimum_ticks, {2, 4, 6}),
            "failure_confirmation_bars": (self.failure_confirmation_bars, {2, 3}),
            "maximum_stop_atr_multiple": (
                self.maximum_stop_atr_multiple,
                {1.0, 1.25, 1.5},
            ),
            "maximum_holding_bars": (self.maximum_holding_bars, {8, 12, 16}),
        }
        invalid_tunables = [
            name for name, (actual, choices) in tunable_choices.items() if actual not in choices
        ]
        if invalid_tunables:
            raise ValueError(
                "uncertified Chart Fanatics v02 tunable value: "
                + ", ".join(invalid_tunables)
            )
        if self.value_area_method != VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD:
            raise ValueError(
                "fixed Chart Fanatics v02 value-area method drift: "
                f"{self.value_area_method!r}"
            )
        if self.big_trade_aggregation_mode != BIG_TRADE_AGGREGATION_FIXED_CELL:
            raise ValueError(
                "fixed Chart Fanatics v02 big-trade aggregation drift: "
                f"{self.big_trade_aggregation_mode!r}"
            )
        expected_windows = {
            "morning_entry_start": "09:33:00",
            "morning_entry_end": "11:30:00",
            "afternoon_entry_start": "13:30:00",
            "afternoon_entry_end": "15:30:00",
        }
        window_drift = [name for name, expected in expected_windows.items() if getattr(self, name) != expected]
        if window_drift:
            raise ValueError("fixed Chart Fanatics v02 window drift: " + ", ".join(window_drift))
        if not self.atr_context_path or len(self.atr_context_sha256) != 64:
            raise ValueError("ATR context path and SHA-256 are required")
        if not self.big_trade_context_path or len(self.big_trade_context_sha256) != 64:
            raise ValueError("big-trade context path and SHA-256 are required")


_ACCEPTED_PARAMETERS = {item.name for item in fields(ChartFanaticsRangeConfig)}


def build_strategy(
    params: dict[str, Any],
) -> "ChartFanaticsRangeEventStrategy":
    unknown = sorted(set(params) - _ACCEPTED_PARAMETERS)
    if unknown:
        raise ValueError("unknown yush_adaptive_orderflow_range parameter(s): " + ", ".join(unknown))
    return ChartFanaticsRangeEventStrategy(ChartFanaticsRangeConfig(**params))


@dataclass(frozen=True)
class ProfileSnapshot:
    poc_bin: int
    val_bin: int
    vah_bin: int
    poc_tick: int
    val_tick: int
    vah_tick: int
    midpoint_tick: float
    poc_volume: int
    total_volume: int


@dataclass(frozen=True)
class RegimeSnapshot:
    label: str
    overlap: float
    poc_a_tick: int
    poc_b_tick: int
    midpoint_a_tick: float
    midpoint_b_tick: float
    efficiency: float
    close_tick: int


@dataclass
class CompletedBar:
    index: int
    start_ns: int
    end_ns: int
    open_tick: int
    high_tick: int
    low_tick: int
    close_tick: int
    volume: int
    delta: int
    bin_volume: dict[int, int]
    bin_delta: dict[int, int]
    true_range_ticks: int = 0
    atr_ticks: float | None = None

    @property
    def delta_ratio(self) -> float:
        return 0.0 if self.volume <= 0 else self.delta / self.volume

    @property
    def close_location(self) -> float | None:
        width = self.high_tick - self.low_tick
        if width <= 0:
            return None
        return (self.close_tick - self.low_tick) / width


@dataclass
class WorkingBar:
    index: int
    start_ns: int
    end_ns: int
    open_tick: int
    high_tick: int
    low_tick: int
    close_tick: int
    volume: int = 0
    delta: int = 0
    bin_volume: dict[int, int] = field(default_factory=dict)
    bin_delta: dict[int, int] = field(default_factory=dict)

    def update(self, event: CanonicalEvent, price_bin_ticks: int) -> None:
        tick = int(event.price_tick)
        size = int(event.size or 0)
        signed = int(event.signed_size or 0)
        self.high_tick = max(self.high_tick, tick)
        self.low_tick = min(self.low_tick, tick)
        self.close_tick = tick
        self.volume += size
        self.delta += signed
        bucket = math.floor(tick / price_bin_ticks)
        self.bin_volume[bucket] = self.bin_volume.get(bucket, 0) + size
        self.bin_delta[bucket] = self.bin_delta.get(bucket, 0) + signed

    def complete(self) -> CompletedBar:
        return CompletedBar(
            index=self.index,
            start_ns=self.start_ns,
            end_ns=self.end_ns,
            open_tick=self.open_tick,
            high_tick=self.high_tick,
            low_tick=self.low_tick,
            close_tick=self.close_tick,
            volume=self.volume,
            delta=self.delta,
            bin_volume=dict(self.bin_volume),
            bin_delta=dict(self.bin_delta),
        )


@dataclass
class Burst:
    burst_id: int
    side: str
    price_low_tick: int
    price_high_tick: int
    size: int
    started_at_ns: int
    ended_at_ns: int
    qualified_at_ns: int


@dataclass
class WorkingBurst:
    side: str
    price_low_tick: int
    price_high_tick: int
    size: int
    started_at_ns: int
    last_at_ns: int
    last_price_tick: int


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
class AoiScore:
    """Frozen value edge plus the institutional footprint that made it eligible."""

    edge_tick: int
    institutional_footprint_kind: str
    market_level_point: bool
    big_trade_point: bool
    delta_profile_point: bool
    nearest_market_level_type: str | None
    nearest_market_level_tick: int | None
    big_trade_burst_id: int | None
    big_trade_burst_side: str | None = None
    big_trade_burst_low_tick: int | None = None
    big_trade_burst_high_tick: int | None = None
    big_trade_burst_size: int | None = None
    big_trade_burst_qualified_at_ns: int | None = None
    delta_profile_bin_low_tick: int | None = None
    delta_profile_bin_high_tick: int | None = None
    delta_profile_abs_delta: int | None = None
    delta_profile_threshold: int | None = None
    delta_profile_signed_delta: int | None = None

    @property
    def institutional_footprint_count(self) -> int:
        return int(self.big_trade_point) + int(self.delta_profile_point)


@dataclass
class FrozenAoiCandidate:
    direction: str
    aoi: AoiScore
    profile: ProfileSnapshot
    regime: RegimeSnapshot
    frozen_bar_index: int
    frozen_at_ns: int


@dataclass
class SweepEpisode:
    episode_id: int
    direction: str
    aoi: AoiScore
    sweep_bar_index: int
    sweep_bar_high_tick: int
    sweep_bar_low_tick: int
    highest_tick_since_sweep: int
    lowest_tick_since_sweep: int
    starting_profile: ProfileSnapshot
    starting_regime: RegimeSnapshot
    aoi_frozen_bar_index: int | None = None
    aoi_frozen_at_ns: int | None = None
    expired: bool = False
    failure_bar_index: int | None = None


@dataclass
class PendingSignal:
    order_id: str
    episode: SweepEpisode
    direction: str
    entry_tick: int
    stop_tick: int
    target_1_tick: int
    target_2_tick: int
    risk_ticks: int
    failure_bar_index: int
    expiry_bar_index: int
    failure_bar: CompletedBar
    failure_profile: ProfileSnapshot
    failure_regime: RegimeSnapshot
    highest_tick_since_sweep: int
    lowest_tick_since_sweep: int
    submitted: bool = False
    cancelled: bool = False


@dataclass
class PositionPlan:
    signal: PendingSignal
    entry_bar_count: int
    target_1_done: bool = False


class ChartFanaticsRangeState:
    def __init__(
        self,
        session: EventReplaySessionView,
        config: ChartFanaticsRangeConfig,
    ) -> None:
        self.session = session
        self.cfg = config
        self.open_ns = int(
            pd.Timestamp(
                f"{session.session_date} 09:30:00",
                tz="America/New_York",
            ).value
        )
        self.or_end_ns = self.open_ns + config.opening_range_seconds * 1_000_000_000
        self.previous_rth = session.metadata.get("previous_rth")
        self.overnight_high = session.metadata.get("overnight_high")
        self.overnight_low = session.metadata.get("overnight_low")
        self.working_bar: WorkingBar | None = None
        self.completed_bars: list[CompletedBar] = []
        self.profile_volume: dict[int, int] = {}
        self.profile_delta: dict[int, int] = {}
        self.published_profile: ProfileSnapshot | None = None
        self.published_regime: RegimeSnapshot | None = None
        self.or_high_tick: int | None = None
        self.or_low_tick: int | None = None
        self.active_burst_bucket: int | None = None
        self.active_bursts: dict[tuple[str, int], WorkingBurst] = {}
        self.bursts: deque[Burst] = deque()
        self.burst_counter = 0
        self.episodes: dict[str, SweepEpisode | None] = {
            "long": None,
            "short": None,
        }
        self.frozen_aois: dict[str, FrozenAoiCandidate | None] = {
            "long": None,
            "short": None,
        }
        self.episode_counter = 0
        self.pending: dict[str, PendingSignal] = {}
        self.position_plans: dict[int, PositionPlan] = {}
        self.cancel_orders = False
        self.action_due = False
        self.last_event: CanonicalEvent | None = None
        self.consumed_aois: set[tuple[str, int]] = set()
        self.atr_points, self.atr_previous_close_tick = _atr_seed_for_session(
            session.session_date,
            config,
        )
        self.big_trade_seed = _big_trade_seed_for_session(
            session.session_date,
            config,
        )
        self.diagnostics = {
            "events": 0,
            "completed_3m_bars": 0,
            "big_trade_bursts": 0,
            "non_trending_regime_bars": 0,
            "insufficient_trend_history_bars": 0,
            "bullish_regime_bars": 0,
            "bearish_regime_bars": 0,
            "aoi_without_institutional_footprint": 0,
            "frozen_aoi_candidates": 0,
            "frozen_aoi_directional_trend_invalidations": 0,
            "aoi_already_consumed": 0,
            "qualified_aoi_without_sweep": 0,
            "sweep_episodes": 0,
            "sweep_invalidations": 0,
            "sweep_close_beyond_extreme_invalidations": 0,
            "sweep_breakout_trend_invalidations": 0,
            "sweep_expired_without_failure": 0,
            "failure_rule_misses": 0,
            "failure_confirmations": 0,
            "signal_stop_distance_rejections": 0,
            "signal_target_1_reward_rejections": 0,
            "signal_target_2_reward_rejections": 0,
            "orders_submitted": 0,
            "order_expirations": 0,
            "fill_rejections": 0,
            "target_1_exits": 0,
            "time_exits": 0,
            "adaptive_big_trade_threshold": (self.big_trade_seed.threshold_volume),
        }

    def ingest(self, event: CanonicalEvent) -> None:
        self.action_due = False
        self.cancel_orders = False
        self.last_event = _copy_event(event)
        self.diagnostics["events"] += 1
        self._advance_burst(event)
        self._advance_bar(event)
        self._advance_pending_extremes(event)
        self._expire_old_bursts(event.timestamp_ns)

    def _advance_burst(self, event: CanonicalEvent) -> None:
        bucket = int((event.timestamp_ns - self.open_ns) // (self.cfg.big_trade_interval_ms * 1_000_000))
        if bucket < 0:
            raise ValueError("range strategy received an event before RTH")
        if self.active_burst_bucket is None:
            self.active_burst_bucket = bucket
        elif bucket < self.active_burst_bucket:
            raise ValueError("big-trade aggregation order is not monotonic")
        elif bucket != self.active_burst_bucket:
            self._finalize_burst_bucket(event.timestamp_ns)
            self.active_burst_bucket = bucket
        side = str(event.side or "")
        if side not in {BUY_SIDE, SELL_SIDE}:
            return
        tick = int(event.price_tick)
        size = int(event.size or 0)
        price_bucket = (tick // self.cfg.big_trade_price_bucket_ticks) * self.cfg.big_trade_price_bucket_ticks
        key = (side, price_bucket)
        active = self.active_bursts.get(key)
        if active is None:
            self.active_bursts[key] = WorkingBurst(
                side=side,
                price_low_tick=price_bucket,
                price_high_tick=(price_bucket + self.cfg.big_trade_price_bucket_ticks - 1),
                size=size,
                started_at_ns=event.timestamp_ns,
                last_at_ns=event.timestamp_ns,
                last_price_tick=tick,
            )
            return
        active.size += size
        active.last_at_ns = event.timestamp_ns
        active.last_price_tick = tick

    def _finalize_burst_bucket(self, qualified_at_ns: int) -> None:
        for active in self.active_bursts.values():
            if active.size >= self.big_trade_seed.threshold_volume:
                self.burst_counter += 1
                self.bursts.append(
                    Burst(
                        burst_id=self.burst_counter,
                        side=active.side,
                        price_low_tick=active.price_low_tick,
                        price_high_tick=active.price_high_tick,
                        size=active.size,
                        started_at_ns=active.started_at_ns,
                        ended_at_ns=active.last_at_ns,
                        qualified_at_ns=int(qualified_at_ns),
                    )
                )
                self.diagnostics["big_trade_bursts"] += 1
        self.active_bursts.clear()

    def _advance_bar(self, event: CanonicalEvent) -> None:
        bar_id = int((event.timestamp_ns - self.open_ns) // (self.cfg.bar_seconds * 1_000_000_000))
        if bar_id < 0:
            raise ValueError("range strategy received an event before RTH")
        if self.working_bar is None:
            self.working_bar = _new_working_bar(
                bar_id,
                self.open_ns,
                self.cfg.bar_seconds,
                self.cfg.price_bin_ticks,
                event,
            )
        elif bar_id != self.working_bar.index:
            if bar_id < self.working_bar.index:
                raise ValueError("event bar order is not monotonic")
            completed = self.working_bar.complete()
            self._publish_bar(completed)
            self.working_bar = _new_working_bar(
                bar_id,
                self.open_ns,
                self.cfg.bar_seconds,
                self.cfg.price_bin_ticks,
                event,
            )
        else:
            self.working_bar.update(event, self.cfg.price_bin_ticks)
        if event.timestamp_ns < self.or_end_ns:
            tick = int(event.price_tick)
            self.or_high_tick = tick if self.or_high_tick is None else max(self.or_high_tick, tick)
            self.or_low_tick = tick if self.or_low_tick is None else min(self.or_low_tick, tick)

    def _publish_bar(self, bar: CompletedBar) -> None:
        previous_close = self.atr_previous_close_tick
        true_range = max(
            bar.high_tick - bar.low_tick,
            abs(bar.high_tick - previous_close),
            abs(bar.low_tick - previous_close),
        )
        bar.true_range_ticks = true_range
        true_range_points = true_range * self.cfg.tick_size
        self.atr_points = (
            self.atr_points * (self.cfg.atr_lookback_bars - 1) + true_range_points
        ) / self.cfg.atr_lookback_bars
        self.atr_previous_close_tick = bar.close_tick
        bar.atr_ticks = self.atr_points / self.cfg.tick_size
        self.completed_bars.append(bar)
        for bucket, volume in bar.bin_volume.items():
            self.profile_volume[bucket] = self.profile_volume.get(bucket, 0) + volume
        for bucket, delta in bar.bin_delta.items():
            self.profile_delta[bucket] = self.profile_delta.get(bucket, 0) + delta
        self.published_profile = _profile_snapshot(
            self.profile_volume,
            self.cfg.price_bin_ticks,
            self.cfg.value_area_fraction,
            self.cfg.value_area_method,
        )
        self.published_regime = _classify_regime(
            self.completed_bars,
            self.cfg,
        )
        self.diagnostics["completed_3m_bars"] += 1
        regime_key = {
            REGIME_NON_TRENDING: "non_trending_regime_bars",
            REGIME_INSUFFICIENT: "insufficient_trend_history_bars",
            REGIME_BULLISH: "bullish_regime_bars",
            REGIME_BEARISH: "bearish_regime_bars",
        }[self.published_regime.label]
        self.diagnostics[regime_key] += 1
        self._process_existing_episodes(bar)
        self._advance_frozen_aois(bar)
        self._expire_pending_after_bar(bar.index)

    def _advance_frozen_aois(self, bar: CompletedBar) -> None:
        profile = self.published_profile
        regime = self.published_regime
        if profile is None or regime is None:
            return
        for direction in ("short", "long"):
            candidate = self.frozen_aois[direction]
            if _directional_breakout_trend(direction, regime.label):
                if candidate is not None:
                    self.diagnostics["frozen_aoi_directional_trend_invalidations"] += 1
                    self.frozen_aois[direction] = None
                continue
            if candidate is not None:
                self._detect_frozen_aoi_sweep(bar, candidate)
            self._freeze_eligible_aoi(
                direction,
                bar,
                profile,
                regime,
            )

    def _freeze_eligible_aoi(
        self,
        direction: str,
        bar: CompletedBar,
        profile: ProfileSnapshot,
        regime: RegimeSnapshot,
    ) -> None:
        aoi = self._best_aoi(
            direction,
            profile,
            as_of_ns=bar.end_ns,
        )
        if aoi is None:
            self.diagnostics["aoi_without_institutional_footprint"] += 1
            return
        existing = self.frozen_aois[direction]
        if (
            existing is not None
            and existing.aoi.edge_tick == aoi.edge_tick
            and existing.aoi.institutional_footprint_kind == aoi.institutional_footprint_kind
        ):
            return
        self.frozen_aois[direction] = FrozenAoiCandidate(
            direction=direction,
            aoi=aoi,
            profile=profile,
            regime=regime,
            frozen_bar_index=bar.index,
            frozen_at_ns=bar.end_ns,
        )
        self.diagnostics["frozen_aoi_candidates"] += 1

    def _detect_frozen_aoi_sweep(
        self,
        bar: CompletedBar,
        candidate: FrozenAoiCandidate,
    ) -> None:
        if not self._within_signal_window(bar.end_ns):
            return
        if len(self.completed_bars) < 2:
            return
        direction = candidate.direction
        aoi = candidate.aoi
        current = self.episodes[direction]
        if current is not None and not current.expired:
            return
        if self._aoi_entry_count(direction, aoi.edge_tick) >= (self.cfg.maximum_entries_per_aoi):
            self.diagnostics["aoi_already_consumed"] += 1
            self.frozen_aois[direction] = None
            return
        swept = (
            bar.high_tick >= aoi.edge_tick + self.cfg.sweep_minimum_ticks
            if direction == "short"
            else bar.low_tick <= aoi.edge_tick - self.cfg.sweep_minimum_ticks
        )
        if not swept:
            self.diagnostics["qualified_aoi_without_sweep"] += 1
            return
        self.episode_counter += 1
        episode = SweepEpisode(
            episode_id=self.episode_counter,
            direction=direction,
            aoi=aoi,
            sweep_bar_index=bar.index,
            sweep_bar_high_tick=bar.high_tick,
            sweep_bar_low_tick=bar.low_tick,
            highest_tick_since_sweep=bar.high_tick,
            lowest_tick_since_sweep=bar.low_tick,
            starting_profile=candidate.profile,
            starting_regime=candidate.regime,
            aoi_frozen_bar_index=candidate.frozen_bar_index,
            aoi_frozen_at_ns=candidate.frozen_at_ns,
        )
        self.episodes[direction] = episode
        self.diagnostics["sweep_episodes"] += 1

    def _process_existing_episodes(self, bar: CompletedBar) -> None:
        profile = self.published_profile
        regime = self.published_regime
        if profile is None or regime is None:
            return
        for direction, episode in tuple(self.episodes.items()):
            if episode is None or episode.expired:
                continue
            if bar.index <= episode.sweep_bar_index:
                continue
            age = bar.index - episode.sweep_bar_index
            episode.highest_tick_since_sweep = max(
                episode.highest_tick_since_sweep,
                bar.high_tick,
            )
            episode.lowest_tick_since_sweep = min(
                episode.lowest_tick_since_sweep,
                bar.low_tick,
            )
            close_invalid = (
                bar.close_tick > episode.sweep_bar_high_tick
                if direction == "short"
                else bar.close_tick < episode.sweep_bar_low_tick
            )
            trend_invalid = regime.label == REGIME_BULLISH if direction == "short" else regime.label == REGIME_BEARISH
            if close_invalid or trend_invalid:
                episode.expired = True
                self.diagnostics["sweep_invalidations"] += 1
                if close_invalid:
                    self.diagnostics["sweep_close_beyond_extreme_invalidations"] += 1
                if trend_invalid:
                    self.diagnostics["sweep_breakout_trend_invalidations"] += 1
                continue
            if age > self.cfg.failure_confirmation_bars:
                episode.expired = True
                self.diagnostics["sweep_expired_without_failure"] += 1
                continue
            failure = _failure_closed_back_inside(episode, bar)
            if not failure:
                self.diagnostics["failure_rule_misses"] += 1
                continue
            signal = self._build_pending_signal(
                episode,
                bar,
                episode.starting_profile,
                regime,
            )
            episode.expired = True
            episode.failure_bar_index = bar.index
            if signal is None:
                continue
            self.pending[signal.order_id] = signal
            self.diagnostics["failure_confirmations"] += 1
            self.action_due = True

    def _build_pending_signal(
        self,
        episode: SweepEpisode,
        bar: CompletedBar,
        profile: ProfileSnapshot,
        regime: RegimeSnapshot,
    ) -> PendingSignal | None:
        direction = episode.direction
        entry_tick = (
            episode.aoi.edge_tick - self.cfg.entry_offset_ticks
            if direction == "short"
            else episode.aoi.edge_tick + self.cfg.entry_offset_ticks
        )
        stop_tick = (
            episode.highest_tick_since_sweep + self.cfg.stop_offset_ticks
            if direction == "short"
            else episode.lowest_tick_since_sweep - self.cfg.stop_offset_ticks
        )
        risk_ticks = stop_tick - entry_tick if direction == "short" else entry_tick - stop_tick
        maximum = min(
            self.cfg.maximum_stop_ticks,
            int(math.floor(float(bar.atr_ticks or 0.0) * self.cfg.maximum_stop_atr_multiple)),
        )
        if not self.cfg.minimum_stop_ticks <= risk_ticks <= maximum:
            self.diagnostics["signal_stop_distance_rejections"] += 1
            return None
        target_1 = _round_target_tick(
            profile.midpoint_tick,
            direction=direction,
        )
        target_2 = profile.val_tick if direction == "short" else profile.vah_tick
        reward_1 = entry_tick - target_1 if direction == "short" else target_1 - entry_tick
        reward_2 = entry_tick - target_2 if direction == "short" else target_2 - entry_tick
        if reward_1 < risk_ticks:
            self.diagnostics["signal_target_1_reward_rejections"] += 1
            return None
        if reward_2 < 2 * risk_ticks:
            self.diagnostics["signal_target_2_reward_rejections"] += 1
            return None
        return PendingSignal(
            order_id=f"{direction}_{episode.episode_id}",
            episode=episode,
            direction=direction,
            entry_tick=entry_tick,
            stop_tick=stop_tick,
            target_1_tick=target_1,
            target_2_tick=target_2,
            risk_ticks=risk_ticks,
            failure_bar_index=bar.index,
            expiry_bar_index=bar.index + self.cfg.entry_expiry_bars,
            failure_bar=bar,
            failure_profile=profile,
            failure_regime=regime,
            highest_tick_since_sweep=episode.highest_tick_since_sweep,
            lowest_tick_since_sweep=episode.lowest_tick_since_sweep,
        )

    def _aoi_entry_count(self, direction: str, edge_tick: int) -> int:
        return int((direction, int(edge_tick)) in self.consumed_aois)

    def record_aoi_entry(self, direction: str, edge_tick: int) -> None:
        self.consumed_aois.add((direction, int(edge_tick)))

    def _advance_pending_extremes(self, event: CanonicalEvent) -> None:
        for signal in self.pending.values():
            if signal.cancelled:
                continue
            before = signal.stop_tick
            signal.highest_tick_since_sweep = max(
                signal.highest_tick_since_sweep,
                int(event.price_tick),
            )
            signal.lowest_tick_since_sweep = min(
                signal.lowest_tick_since_sweep,
                int(event.price_tick),
            )
            signal.stop_tick = (
                signal.highest_tick_since_sweep + self.cfg.stop_offset_ticks
                if signal.direction == "short"
                else signal.lowest_tick_since_sweep - self.cfg.stop_offset_ticks
            )
            if signal.stop_tick != before:
                signal.risk_ticks = (
                    signal.stop_tick - signal.entry_tick
                    if signal.direction == "short"
                    else signal.entry_tick - signal.stop_tick
                )
                self.action_due = True

    def _expire_pending_after_bar(self, bar_index: int) -> None:
        for signal in self.pending.values():
            if not signal.cancelled and bar_index >= signal.expiry_bar_index:
                signal.cancelled = True
                self.cancel_orders = True
                self.diagnostics["order_expirations"] += 1

    def _best_aoi(
        self,
        direction: str,
        profile: ProfileSnapshot,
        *,
        as_of_ns: int,
    ) -> AoiScore | None:
        edge_tick = profile.vah_tick if direction == "short" else profile.val_tick
        candidate = self._score_price(
            edge_tick,
            profile,
            as_of_ns=as_of_ns,
        )
        return candidate if candidate.big_trade_point or candidate.delta_profile_point else None

    def _score_price(
        self,
        tick: int,
        profile: ProfileSnapshot,
        *,
        as_of_ns: int,
    ) -> AoiScore:
        levels = self._market_levels()
        near = [(name, level) for name, level in levels if abs(tick - level) <= self.cfg.aoi_level_distance_ticks]
        nearest = min(near, key=lambda item: (abs(tick - item[1]), item[0])) if near else None
        cutoff = as_of_ns - self.cfg.aoi_big_trade_lookback_minutes * 60 * 1_000_000_000
        big_candidates = [
            burst
            for burst in self.bursts
            if cutoff <= burst.ended_at_ns <= as_of_ns
            and burst.qualified_at_ns <= as_of_ns
            and _distance_to_interval(
                tick,
                burst.price_low_tick,
                burst.price_high_tick,
            )
            <= self.cfg.aoi_level_distance_ticks
        ]
        big = max(big_candidates, key=lambda item: item.ended_at_ns) if big_candidates else None
        delta_threshold = _nearest_rank(
            [abs(value) for value in self.profile_delta.values()],
            self.cfg.delta_profile_percentile,
        )
        bucket = (
            profile.vah_bin
            if tick == profile.vah_tick
            else profile.val_bin
            if tick == profile.val_tick
            else math.floor(tick / self.cfg.price_bin_ticks)
        )
        bucket_delta = int(self.profile_delta.get(bucket, 0))
        delta_point = bool(
            delta_threshold is not None
            and delta_threshold > 0
            and bucket in self.profile_delta
            and abs(bucket_delta) >= delta_threshold
        )
        footprint_kind = (
            "adaptive_large_execution_and_top_decile_delta"
            if big is not None and delta_point
            else "adaptive_large_execution"
            if big is not None
            else "top_decile_delta"
            if delta_point
            else "none"
        )
        return AoiScore(
            edge_tick=tick,
            institutional_footprint_kind=footprint_kind,
            market_level_point=bool(nearest),
            big_trade_point=big is not None,
            delta_profile_point=delta_point,
            nearest_market_level_type=(None if nearest is None else nearest[0]),
            nearest_market_level_tick=(None if nearest is None else nearest[1]),
            big_trade_burst_id=None if big is None else big.burst_id,
            big_trade_burst_side=None if big is None else big.side,
            big_trade_burst_low_tick=(None if big is None else big.price_low_tick),
            big_trade_burst_high_tick=(None if big is None else big.price_high_tick),
            big_trade_burst_size=None if big is None else big.size,
            big_trade_burst_qualified_at_ns=(None if big is None else big.qualified_at_ns),
            delta_profile_bin_low_tick=(bucket * self.cfg.price_bin_ticks),
            delta_profile_bin_high_tick=(bucket * self.cfg.price_bin_ticks + self.cfg.price_bin_ticks - 1),
            delta_profile_abs_delta=abs(bucket_delta),
            delta_profile_threshold=delta_threshold,
        )

    def _market_levels(self) -> list[tuple[str, int]]:
        values: list[tuple[str, float | None]] = []
        prior = self.previous_rth
        if prior is not None:
            values.extend(
                [
                    ("PDH", prior.high),
                    ("PDL", prior.low),
                    ("PDC", prior.close),
                ]
            )
        values.extend(
            [
                ("ONH", self.overnight_high),
                ("ONL", self.overnight_low),
            ]
        )
        if self.or_high_tick is not None and self.or_low_tick is not None:
            values.extend(
                [
                    (
                        "ORH",
                        self.or_high_tick * self.cfg.tick_size,
                    ),
                    (
                        "ORL",
                        self.or_low_tick * self.cfg.tick_size,
                    ),
                ]
            )
        return [
            (name, int(round(float(value) / self.cfg.tick_size)))
            for name, value in values
            if value is not None and math.isfinite(float(value))
        ]

    def _within_signal_window(self, timestamp_ns: int) -> bool:
        timestamp = pd.Timestamp(timestamp_ns, tz="UTC").tz_convert("America/New_York")
        seconds = timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
        windows = (
            (
                _time_to_seconds(self.cfg.morning_entry_start),
                _time_to_seconds(self.cfg.morning_entry_end),
            ),
            (
                _time_to_seconds(self.cfg.afternoon_entry_start),
                _time_to_seconds(self.cfg.afternoon_entry_end),
            ),
        )
        return any(start <= seconds <= end for start, end in windows)

    def _expire_old_bursts(self, timestamp_ns: int) -> None:
        cutoff = timestamp_ns - self.cfg.aoi_big_trade_lookback_minutes * 60 * 1_000_000_000
        while self.bursts and self.bursts[0].ended_at_ns < cutoff:
            self.bursts.popleft()

    def signal_is_fillable(
        self,
        signal: PendingSignal,
        event: CanonicalEvent,
    ) -> bool:
        if signal.cancelled:
            return False
        regime = self.published_regime
        if regime is None:
            return False
        if _directional_breakout_trend(signal.direction, regime.label):
            return False
        fill_reference = (
            max(signal.entry_tick, int(event.price_tick))
            if signal.direction == "long"
            else min(signal.entry_tick, int(event.price_tick))
        )
        filled_tick = fill_reference + 1 if signal.direction == "long" else fill_reference - 1
        risk_ticks = signal.stop_tick - filled_tick if signal.direction == "short" else filled_tick - signal.stop_tick
        maximum = min(
            self.cfg.maximum_stop_ticks,
            int(math.floor((self.atr_points / self.cfg.tick_size) * self.cfg.maximum_stop_atr_multiple)),
        )
        reward_1 = (
            filled_tick - signal.target_1_tick if signal.direction == "short" else signal.target_1_tick - filled_tick
        )
        reward_2 = (
            filled_tick - signal.target_2_tick if signal.direction == "short" else signal.target_2_tick - filled_tick
        )
        return bool(
            self.cfg.minimum_stop_ticks <= risk_ticks <= maximum
            and reward_1 >= risk_ticks
            and reward_2 >= 2 * risk_ticks
        )


class ChartFanaticsRangeEventStrategy(CanonicalEventReplayStrategy):
    required_event_columns = (
        "size",
        "side",
        "signed_size",
        "contract_symbol",
    )

    def __init__(self, config: ChartFanaticsRangeConfig | None = None) -> None:
        self.cfg = config or ChartFanaticsRangeConfig()
        self.state: ChartFanaticsRangeState | None = None

    def on_session_start(
        self,
        session: EventReplaySessionView,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        self.state = ChartFanaticsRangeState(session, self.cfg)

    def on_event_start(
        self,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        self._state().ingest(event)

    def pre_execution(
        self,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> EventPreExecution:
        del event, broker
        state = self._state()
        return EventPreExecution(
            cancel_entry_orders=state.cancel_orders,
        )

    def entry_order_is_live(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del event, broker
        signal = self._state().pending.get(order.order_id)
        return bool(signal is not None and not signal.cancelled)

    def entry_fill_allowed(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del broker
        state = self._state()
        signal = state.pending.get(order.order_id)
        passed = bool(signal is not None and state.signal_is_fillable(signal, event))
        if not passed:
            state.diagnostics["fill_rejections"] += 1
        return passed

    def on_order_cancelled(
        self,
        order: EventEntryOrder,
        reason: str,
        event: CanonicalEvent | None,
        broker: EventReplayBroker,
    ) -> None:
        del reason, event, broker
        signal = self._state().pending.get(order.order_id)
        if signal is not None:
            signal.cancelled = True

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        signal = state.pending.pop(order.order_id)
        signal.cancelled = True
        state.record_aoi_entry(
            signal.direction,
            signal.episode.aoi.edge_tick,
        )
        state.position_plans[position.trade_id] = PositionPlan(
            signal=signal,
            entry_bar_count=len(state.completed_bars),
        )
        aoi = signal.episode.aoi
        big_trade = state.big_trade_seed
        entry_regime = state.published_regime
        if entry_regime is None:
            raise AssertionError("filled entry has no published trend state")
        broker.annotate_position(
            setup_model="institutional_footprint_value_edge_failure",
            directional_trend_veto_passed=not _directional_breakout_trend(
                signal.direction,
                entry_regime.label,
            ),
            trend_state_at_failure=signal.failure_regime.label,
            trend_state_at_entry=entry_regime.label,
            regime_overlap_at_entry=entry_regime.overlap,
            regime_efficiency_at_entry=entry_regime.efficiency,
            rolling_poc_a_at_entry_price=(entry_regime.poc_a_tick * self.cfg.tick_size),
            rolling_poc_b_at_entry_price=(entry_regime.poc_b_tick * self.cfg.tick_size),
            rolling_midpoint_a_at_entry_price=(entry_regime.midpoint_a_tick * self.cfg.tick_size),
            rolling_midpoint_b_at_entry_price=(entry_regime.midpoint_b_tick * self.cfg.tick_size),
            aoi_edge_price=aoi.edge_tick * self.cfg.tick_size,
            aoi_frozen_bar_index=signal.episode.aoi_frozen_bar_index,
            aoi_frozen_at=(
                None
                if signal.episode.aoi_frozen_at_ns is None
                else pd.Timestamp(
                    signal.episode.aoi_frozen_at_ns,
                    tz="UTC",
                )
            ),
            institutional_footprint_kind=aoi.institutional_footprint_kind,
            institutional_big_trade_qualified=aoi.big_trade_point,
            institutional_delta_qualified=aoi.delta_profile_point,
            big_trade_reference_percentile=(big_trade.reference_percentile),
            big_trade_lookback_sessions=big_trade.lookback_sessions,
            big_trade_threshold_contracts=big_trade.threshold_volume,
            big_trade_reference_observation_count=(big_trade.reference_observation_count),
            big_trade_reference_start_session=(big_trade.reference_start_session),
            big_trade_reference_end_session=(big_trade.reference_end_session),
            selected_big_trade_burst_id=aoi.big_trade_burst_id,
            selected_big_trade_side=aoi.big_trade_burst_side,
            selected_big_trade_low_price=(
                None if aoi.big_trade_burst_low_tick is None else aoi.big_trade_burst_low_tick * self.cfg.tick_size
            ),
            selected_big_trade_high_price=(
                None if aoi.big_trade_burst_high_tick is None else aoi.big_trade_burst_high_tick * self.cfg.tick_size
            ),
            selected_big_trade_size=aoi.big_trade_burst_size,
            selected_big_trade_qualified_at=(
                None
                if aoi.big_trade_burst_qualified_at_ns is None
                else pd.Timestamp(
                    aoi.big_trade_burst_qualified_at_ns,
                    tz="UTC",
                )
            ),
            selected_delta_bin_low_price=(
                None
                if not aoi.delta_profile_point or aoi.delta_profile_bin_low_tick is None
                else aoi.delta_profile_bin_low_tick * self.cfg.tick_size
            ),
            selected_delta_bin_high_price=(
                None
                if not aoi.delta_profile_point or aoi.delta_profile_bin_high_tick is None
                else aoi.delta_profile_bin_high_tick * self.cfg.tick_size
            ),
            selected_delta_bin_abs_delta=(aoi.delta_profile_abs_delta if aoi.delta_profile_point else None),
            selected_delta_bin_threshold=(aoi.delta_profile_threshold if aoi.delta_profile_point else None),
            selected_delta_percentile=(self.cfg.delta_profile_percentile if aoi.delta_profile_point else None),
            sweep_bar_index=signal.episode.sweep_bar_index,
            sweep_high_price=signal.episode.sweep_bar_high_tick * self.cfg.tick_size,
            sweep_low_price=signal.episode.sweep_bar_low_tick * self.cfg.tick_size,
            sweep_minimum_ticks=self.cfg.sweep_minimum_ticks,
            failure_confirmation_bars=(self.cfg.failure_confirmation_bars),
            failure_bar_index=signal.failure_bar_index,
            failure_close_price=signal.failure_bar.close_tick * self.cfg.tick_size,
            failure_confirmation_rule=("Completed 3-minute close at least 1 tick inside " "the frozen value edge"),
            entry_trigger_rule=(
                "Stop entry 1 tick inside the frozen edge, active " "from the next ordered trade event"
            ),
            value_area_poc_price=signal.failure_profile.poc_tick * self.cfg.tick_size,
            value_area_vah_price=signal.failure_profile.vah_tick * self.cfg.tick_size,
            value_area_val_price=signal.failure_profile.val_tick * self.cfg.tick_size,
            target_1_price=signal.target_1_tick * self.cfg.tick_size,
            target_2_price=signal.target_2_tick * self.cfg.tick_size,
            target_1_fraction=self.cfg.target_1_fraction,
            maximum_holding_bars=self.cfg.maximum_holding_bars,
            risk_budget_dollars=self.cfg.risk_budget_dollars,
            planned_stop_ticks=signal.risk_ticks,
            entry_slippage_ticks=1,
            protective_stop_slippage_ticks=1,
            target_limit_slippage_ticks=0,
            round_trip_commission_per_contract=(2 * self.cfg.commission_per_contract),
            entry_fill_model=("Next-event stop market with 1 adverse tick; " "gaps fill at the trade-event price"),
            entry_windows_new_york=(
                f"{self.cfg.morning_entry_start}-"
                f"{self.cfg.morning_entry_end};"
                f"{self.cfg.afternoon_entry_start}-"
                f"{self.cfg.afternoon_entry_end}"
            ),
            profile_snapshot_timing=(
                "Frozen at the completed bar when the exact VAH or " "VAL gained a qualifying footprint"
            ),
            burst_definition=(
                "Fixed 100 ms cells aligned to 09:30, grouped by "
                "price tick and aggressor side; threshold is the "
                "prior-20-session 99.5th percentile"
            ),
        )

    def position_directive(
        self,
        event: CanonicalEvent,
        position: EventPositionView,
        broker: EventReplayBroker,
    ) -> PositionDirective:
        del broker
        state = self._state()
        plan = state.position_plans.get(position.trade_id)
        if plan is None:
            return PositionDirective()
        signal = plan.signal
        if len(state.completed_bars) >= plan.entry_bar_count + self.cfg.maximum_holding_bars:
            state.diagnostics["time_exits"] += 1
            return PositionDirective(
                flatten_reason="maximum_12_bar_time_exit",
                flatten_tick=event.price_tick,
            )
        if not plan.target_1_done:
            crossed = (
                event.price_tick <= signal.target_1_tick
                if position.direction == "short"
                else event.price_tick >= signal.target_1_tick
            )
            if crossed:
                plan.target_1_done = True
                quantity = max(
                    1,
                    int(math.floor(position.initial_contracts * self.cfg.target_1_fraction)),
                )
                quantity = min(quantity, position.contracts)
                breakeven_plus = _post_target_stop_tick(
                    entry_price=position.entry_price,
                    direction=position.direction,
                    tick_size=self.cfg.tick_size,
                )
                state.diagnostics["target_1_exits"] += 1
                target_2_crossed = (
                    event.price_tick <= signal.target_2_tick
                    if position.direction == "short"
                    else event.price_tick >= signal.target_2_tick
                )
                return PositionDirective(
                    partial_exit_contracts=quantity,
                    partial_exit_tick=signal.target_1_tick,
                    partial_exit_reason="target_1",
                    immediate_target_tick=(
                        signal.target_2_tick if target_2_crossed and quantity < position.contracts else None
                    ),
                    stop_tick=(breakeven_plus if quantity < position.contracts else None),
                    target_tick=(signal.target_2_tick if quantity < position.contracts else None),
                    stop_exit_reason="post_target_1_stop",
                    report_fields={
                        "target_1_activated": True,
                        "target_1_activated_at": pd.Timestamp(event.timestamp),
                    },
                )
        if plan.target_1_done:
            crossed = (
                event.price_tick <= signal.target_2_tick
                if position.direction == "short"
                else event.price_tick >= signal.target_2_tick
            )
            if crossed:
                return PositionDirective(
                    immediate_target_tick=signal.target_2_tick,
                    report_fields={"target_2_reached": True},
                )
        return PositionDirective()

    def after_event(
        self,
        event: CanonicalEvent,
        broker: EventReplayBroker,
        *,
        closed_this_event: bool,
        opened_this_event: bool,
        entries_blocked: bool,
    ) -> None:
        del event
        state = self._state()
        if opened_this_event:
            broker.cancel_all_entries(reason="position_opened_cancel_other_entries")
            return
        if closed_this_event or broker.position is not None or entries_blocked:
            return
        for order_id, signal in tuple(state.pending.items()):
            if signal.cancelled:
                if order_id in broker.orders:
                    broker.cancel_entry(order_id, reason="signal_cancelled")
                continue
            maximum = min(
                self.cfg.maximum_stop_ticks,
                int(math.floor((state.atr_points / self.cfg.tick_size) * self.cfg.maximum_stop_atr_multiple)),
            )
            if not (self.cfg.minimum_stop_ticks <= signal.risk_ticks <= maximum):
                signal.cancelled = True
                if order_id in broker.orders:
                    broker.cancel_entry(
                        order_id,
                        reason="dynamic_stop_distance_invalid",
                    )
                continue
            broker.submit_or_replace_entry(
                order_id=order_id,
                direction=signal.direction,
                entry_tick=signal.entry_tick,
                stop_tick=signal.stop_tick,
                target_tick=None,
                priority=-signal.episode.aoi.institutional_footprint_count,
                metadata={
                    "episode_id": signal.episode.episode_id,
                    "aoi_edge_tick": signal.episode.aoi.edge_tick,
                },
                report_fields={
                    "institutional_footprint_kind": (signal.episode.aoi.institutional_footprint_kind),
                    "target_1_price": signal.target_1_tick * self.cfg.tick_size,
                    "target_2_price": signal.target_2_tick * self.cfg.tick_size,
                },
            )
            if not signal.submitted:
                signal.submitted = True
                state.diagnostics["orders_submitted"] += 1

    def on_position_closed(
        self,
        position: EventPositionView,
        trade: Mapping[str, Any],
        broker: EventReplayBroker,
    ) -> None:
        del trade, broker
        state = self._state()
        state.position_plans.pop(position.trade_id, None)

    def session_audit(self) -> Mapping[str, Any]:
        state = self._state()
        return {
            **state.diagnostics,
            "active_atr_points": state.atr_points,
            "published_regime": (None if state.published_regime is None else state.published_regime.label),
            "published_poc_price": (
                None if state.published_profile is None else state.published_profile.poc_tick * self.cfg.tick_size
            ),
        }

    def _state(self) -> ChartFanaticsRangeState:
        if self.state is None:
            raise RuntimeError("Chart Fanatics strategy has not started.")
        return self.state


def _new_working_bar(
    bar_id: int,
    open_ns: int,
    bar_seconds: int,
    price_bin_ticks: int,
    event: CanonicalEvent,
) -> WorkingBar:
    start_ns = open_ns + bar_id * bar_seconds * 1_000_000_000
    bar = WorkingBar(
        index=bar_id,
        start_ns=start_ns,
        end_ns=start_ns + bar_seconds * 1_000_000_000,
        open_tick=int(event.price_tick),
        high_tick=int(event.price_tick),
        low_tick=int(event.price_tick),
        close_tick=int(event.price_tick),
    )
    bar.update(event, price_bin_ticks)
    return bar


def _profile_snapshot(
    volumes: Mapping[int, int],
    price_bin_ticks: int,
    value_area_fraction: float = 0.70,
    value_area_method: str = VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD,
) -> ProfileSnapshot | None:
    """Build a MotiveWave Standard developing volume-profile snapshot.

    Rows are half-open price intervals.  VAL is the lower boundary of the
    lowest included row and VAH is the upper boundary of the highest included
    row, matching the lines displayed by MotiveWave.  Standard expansion adds
    the higher-volume pair of rows adjacent to value; an exact pair-volume tie
    deterministically selects the lower pair because MotiveWave's public
    description does not publish a tie rule.
    """

    if value_area_method != VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD:
        raise ValueError(f"unsupported value-area method: {value_area_method!r}")
    positive = {int(bucket): int(volume) for bucket, volume in volumes.items() if int(volume) > 0}
    if not positive:
        return None
    poc_bin = min(
        positive,
        key=lambda bucket: (-positive[bucket], bucket),
    )
    total = sum(positive.values())
    target = total * value_area_fraction
    low = high = poc_bin
    accumulated = positive[poc_bin]
    observed_low = min(positive)
    observed_high = max(positive)
    while accumulated < target and (low > observed_low or high < observed_high):
        lower_bins = tuple(
            low - offset
            for offset in range(1, VALUE_AREA_PAIR_ROWS + 1)
            if low - offset >= observed_low
        )
        upper_bins = tuple(
            high + offset
            for offset in range(1, VALUE_AREA_PAIR_ROWS + 1)
            if high + offset <= observed_high
        )
        lower_volume = sum(positive.get(bucket, 0) for bucket in lower_bins)
        upper_volume = sum(positive.get(bucket, 0) for bucket in upper_bins)
        choose_lower = bool(lower_bins) and (
            not upper_bins or lower_volume >= upper_volume
        )
        selected = lower_bins if choose_lower else upper_bins
        if not selected:
            break
        accumulated += sum(positive.get(bucket, 0) for bucket in selected)
        if choose_lower:
            low = min(selected)
        else:
            high = max(selected)
    val_tick = low * price_bin_ticks
    vah_tick = (high + 1) * price_bin_ticks
    poc_tick = poc_bin * price_bin_ticks
    return ProfileSnapshot(
        poc_bin=poc_bin,
        val_bin=low,
        vah_bin=high,
        poc_tick=poc_tick,
        val_tick=val_tick,
        vah_tick=vah_tick,
        midpoint_tick=(val_tick + vah_tick) / 2.0,
        poc_volume=positive[poc_bin],
        total_volume=total,
    )


def _classify_regime(
    bars: list[CompletedBar],
    config: ChartFanaticsRangeConfig,
) -> RegimeSnapshot:
    width = config.regime_window_bars
    if len(bars) < 2 * width:
        return RegimeSnapshot(
            label=REGIME_INSUFFICIENT,
            overlap=0.0,
            poc_a_tick=0,
            poc_b_tick=0,
            midpoint_a_tick=0.0,
            midpoint_b_tick=0.0,
            efficiency=0.0,
            close_tick=bars[-1].close_tick,
        )
    window_a = bars[-width:]
    window_b = bars[-2 * width : -width]
    profile_a = _profile_snapshot(
        _sum_bar_profile(window_a),
        config.price_bin_ticks,
        config.value_area_fraction,
        config.value_area_method,
    )
    profile_b = _profile_snapshot(
        _sum_bar_profile(window_b),
        config.price_bin_ticks,
        config.value_area_fraction,
        config.value_area_method,
    )
    if profile_a is None or profile_b is None:
        raise AssertionError("completed regime windows have no volume")
    intersection = max(
        0,
        min(profile_a.vah_tick, profile_b.vah_tick) - max(profile_a.val_tick, profile_b.val_tick),
    )
    width_a = profile_a.vah_tick - profile_a.val_tick
    width_b = profile_b.vah_tick - profile_b.val_tick
    overlap = intersection / min(width_a, width_b)
    closes = [
        bars[-width - 1].close_tick,
        *(bar.close_tick for bar in window_a),
    ]
    path = sum(abs(right - left) for left, right in zip(closes, closes[1:]))
    efficiency = 0.0 if path <= 0 else abs(closes[-1] - closes[0]) / path
    close = window_a[-1].close_tick
    bullish = (
        profile_a.midpoint_tick >= profile_b.midpoint_tick + config.trend_midpoint_shift_ticks
        and profile_a.poc_tick >= profile_b.poc_tick + config.trend_poc_shift_ticks
        and overlap <= config.trend_overlap_maximum
        and efficiency >= config.trend_efficiency_minimum
        and close > profile_b.vah_tick
    )
    bearish = (
        profile_a.midpoint_tick <= profile_b.midpoint_tick - config.trend_midpoint_shift_ticks
        and profile_a.poc_tick <= profile_b.poc_tick - config.trend_poc_shift_ticks
        and overlap <= config.trend_overlap_maximum
        and efficiency >= config.trend_efficiency_minimum
        and close < profile_b.val_tick
    )
    label = REGIME_BULLISH if bullish else REGIME_BEARISH if bearish else REGIME_NON_TRENDING
    return RegimeSnapshot(
        label=label,
        overlap=overlap,
        poc_a_tick=profile_a.poc_tick,
        poc_b_tick=profile_b.poc_tick,
        midpoint_a_tick=profile_a.midpoint_tick,
        midpoint_b_tick=profile_b.midpoint_tick,
        efficiency=efficiency,
        close_tick=close,
    )


def _sum_bar_profile(bars: list[CompletedBar]) -> dict[int, int]:
    result: dict[int, int] = {}
    for bar in bars:
        for bucket, volume in bar.bin_volume.items():
            result[bucket] = result.get(bucket, 0) + volume
    return result


def _nearest_rank(
    values: list[int] | tuple[int, ...],
    percentile: float,
) -> int | None:
    if not values:
        return None
    ordered = sorted(int(value) for value in values)
    rank = max(1, int(math.ceil(percentile * len(ordered))))
    return ordered[rank - 1]


def _failure_closed_back_inside(
    episode: SweepEpisode,
    bar: CompletedBar,
) -> bool:
    """Confirm rejection solely from a completed close back inside value."""
    if episode.direction == "short":
        return bar.close_tick <= episode.aoi.edge_tick - 1
    return bar.close_tick >= episode.aoi.edge_tick + 1


def _directional_breakout_trend(
    direction: str,
    regime_label: str,
) -> bool:
    return regime_label == REGIME_BULLISH if direction == "short" else regime_label == REGIME_BEARISH


def _time_to_seconds(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"expected HH:MM:SS, got {value!r}")
    hour, minute, second = (int(part) for part in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError(f"invalid time of day: {value!r}")
    return hour * 3600 + minute * 60 + second


def _distance_to_interval(tick: int, low: int, high: int) -> int:
    if low <= tick <= high:
        return 0
    return low - tick if tick < low else tick - high


def _round_target_tick(midpoint: float, *, direction: str) -> int:
    return math.ceil(midpoint) if direction == "short" else math.floor(midpoint)


def _post_target_stop_tick(
    *,
    entry_price: float,
    direction: str,
    tick_size: float,
) -> int:
    filled_entry_tick = int(round(float(entry_price) / float(tick_size)))
    return filled_entry_tick - 1 if direction == "short" else filled_entry_tick + 1


def _copy_event(event: CanonicalEvent) -> CanonicalEvent:
    return CanonicalEvent(
        event_index=event.event_index,
        timestamp=pd.Timestamp(event.timestamp),
        timestamp_ns=event.timestamp_ns,
        source_ordinal=event.source_ordinal,
        price=event.price,
        price_tick=event.price_tick,
        size=event.size,
        side=event.side,
        signed_size=event.signed_size,
    )


@lru_cache(maxsize=8)
def _load_atr_context(path_text: str, expected_sha256: str) -> pd.DataFrame:
    path = Path(path_text).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"ATR context is missing: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError("ATR context hash drift: " f"expected {expected_sha256}, got {actual}")
    frame = pd.read_parquet(path)
    required = {
        "session_date",
        "atr14_3m_seed_points",
        "previous_close_points",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("ATR context is missing columns: " + ", ".join(missing))
    if frame["session_date"].astype(str).duplicated().any():
        raise ValueError("ATR context has duplicate session dates")
    return frame.assign(session_date=frame["session_date"].astype(str)).set_index("session_date", drop=False)


def _atr_seed_for_session(
    session_date: object,
    config: ChartFanaticsRangeConfig,
) -> tuple[float, int]:
    frame = _load_atr_context(
        config.atr_context_path,
        config.atr_context_sha256,
    )
    key = str(session_date)
    if key not in frame.index:
        raise ValueError(f"ATR context has no seed for session {key}")
    row = frame.loc[key]
    if isinstance(row, pd.DataFrame):
        raise ValueError(f"ATR context is ambiguous for session {key}")
    atr_points = float(row["atr14_3m_seed_points"])
    previous_close = float(row["previous_close_points"])
    if not math.isfinite(atr_points) or atr_points <= 0:
        raise ValueError(f"ATR context seed is invalid for session {key}")
    return (
        atr_points,
        int(round(previous_close / config.tick_size)),
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
        raise ValueError("big-trade context hash drift: " f"expected {expected_sha256}, got {actual}")
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
        raise ValueError("big-trade context is missing columns: " + ", ".join(missing))
    if frame["session_date"].astype(str).duplicated().any():
        raise ValueError("big-trade context has duplicate session dates")
    return frame.assign(session_date=frame["session_date"].astype(str)).set_index("session_date", drop=False)


def _big_trade_seed_for_session(
    session_date: object,
    config: ChartFanaticsRangeConfig,
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
    aggregation_mode = str(
        row.get("aggregation_sequence_scope", BIG_TRADE_AGGREGATION_FIXED_CELL)
    )
    fixed_semantics = (
        lookback == config.big_trade_lookback_sessions
        and math.isclose(
            percentile,
            config.big_trade_reference_percentile,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and str(row["percentile_method"]) == "nearest_rank_higher"
        and int(row["aggregation_interval_ms"]) == config.big_trade_interval_ms
        and int(row["aggregation_price_ticks"]) == config.big_trade_price_bucket_ticks
        and str(row["aggregation_side_scope"]) == "same_aggressor_side_A_or_B"
        and aggregation_mode == config.big_trade_aggregation_mode
    )
    if not fixed_semantics:
        raise ValueError(f"big-trade context semantics drift for session {key}")
    reference_start = str(row["reference_start_session"])
    reference_end = str(row["reference_end_session"])
    if threshold <= 0 or observations <= 0 or not reference_start < reference_end < key:
        raise ValueError(f"big-trade context seed is invalid for session {key}")
    return BigTradeThresholdSeed(
        threshold_volume=threshold,
        reference_percentile=percentile,
        lookback_sessions=lookback,
        reference_observation_count=observations,
        reference_start_session=reference_start,
        reference_end_session=reference_end,
        percentile_method=str(row["percentile_method"]),
    )
