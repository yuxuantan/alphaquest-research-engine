"""Per-bar value-edge auction-failure mechanics.

At every completed three-minute boundary, the strategy causally publishes the
latest MotiveWave Standard developing profile and independently attempts one
VAH AOI and one VAL AOI for the next bar.  An AOI exists only when an
exceptional MotiveWave-compatible large execution or a sign-agnostic top-decile
absolute four-tick session delta-profile cell lies within one-third ATR above or
below that edge.  The edge, selected source bounds, midpoint, and opposite edge
are held only for the next bar's sweep decision; both AOIs are rebuilt again at
the following boundary.

An ordered inside-to-outside sweep immediately arms a stop-market reclaim entry
two ticks beyond the reclaim-side AOI-zone boundary.  There is no separate
three-bar order-flow confirmation and no intended-stop invalidation while the
entry is pending.  On the causal fill event, the protective stop is resolved two
ticks beyond the adverse extreme observed from the sweep bar through that entry
event, then validated before sizing and before the position is created.  The
AOI-time midpoint and opposite edge remain the equal scale-out targets.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from typing import Any, Mapping

import pandas as pd

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    EventEntryOrder,
    EventPositionView,
    EventReplayBroker,
    EventReplaySessionView,
)
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    AoiScore,
    Burst,
    ChartFanaticsRangeConfig,
    ChartFanaticsRangeEventStrategy,
    ChartFanaticsRangeState,
    CompletedBar,
    FrozenAoiCandidate,
    PendingSignal,
    PositionPlan,
    ProfileSnapshot,
    BUY_SIDE,
    BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
    REGIME_NON_TRENDING,
    RegimeSnapshot,
    SELL_SIDE,
    SweepEpisode,
    VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD,
    WorkingBurst,
    _nearest_rank,
    _profile_snapshot,
    _round_target_tick,
)


STRATEGY_ID = "yush_adaptive_orderflow_range_v3"
ENTRY_MODULE = STRATEGY_ID
STOP_MODULE = "event_fill_time_sweep_to_entry_extreme_stop"
TARGET_MODULE = "event_frozen_midpoint_opposite_edge_scale_out"
BURST_DEFINITION = (
    "MotiveWave-compatible consecutive executions at one price tick and aggressor "
    "side within 100 ms of the sequence's first execution; any intervening nonmatching "
    "execution ends the sequence; threshold is the causal prior-20-session 99.9th percentile"
)
DELTA_PROFILE_DEFINITION = (
    "Sign-agnostic developing profile delta in a MotiveWave-style four-tick "
    "fixed price interval within one-third "
    "of frozen causal three-minute ATR above or below the value edge for AOI creation; "
    "the interval's lower-bound MotiveWave price label is its location; "
    "absolute magnitude must be at or above the causal cross-sectional 90th percentile "
    "of the session-anchored four-tick profile cells"
)
MARKET_LEVEL_DEFINITION = (
    "Market levels are not AOI-qualifying sources in this per-bar AOI mechanic"
)
PROTECTIVE_STOP_SLIPPAGE_TICKS = 1
ENTRY_SLIPPAGE_TICKS = 1
DELTA_AGGREGATION_METHOD = "motivewave_fixed_tick_interval_floor"
DELTA_DEFINITION = "ask_volume_minus_bid_volume"


@dataclass(frozen=True)
class AdaptiveOrderflowRangeV3Config(ChartFanaticsRangeConfig):
    """Governed v03 correction defaults and predeclared tunable dimensions."""

    atr_context_path: str = (
        "research/datasets/es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/" "atr14_3m_eth_context.parquet"
    )
    point_value: float = 5.0
    commission_per_contract: float = 0.51
    price_bin_ticks: int = 1
    delta_profile_price_bin_ticks: int = 4
    big_trade_reference_percentile: float = 0.999
    big_trade_aggregation_mode: str = BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE
    big_trade_context_path: str = (
        "research/datasets/es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/"
        "big_trade_100ms_motivewave_consecutive_q999_prior20_context.parquet"
    )
    big_trade_context_sha256: str = "1dec5cfd0b4ed4ca5782298932d833527c80dd8a83e92a75c9f7558db8c4d51f"
    context_distance_atr_fraction: float = 1.0 / 3.0
    burst_freshness_scope: str = "current_rth_session"
    sweep_minimum_ticks: int = 2
    morning_entry_start: str = "09:39:00"
    afternoon_entry_start: str = "13:39:00"
    entry_offset_ticks: int = 2
    stop_at_sweep_extreme: bool = False
    stop_offset_ticks: int = 2
    minimum_stop_ticks: int = 2
    maximum_stop_atr_multiple: float = 1.75
    target_1_fraction: float = 0.50
    maximum_entries_per_aoi: int = 1
    max_trades_per_day: int = 0
    sweep_atr_fraction: float = 0.20
    minimum_midpoint_reward_r: float = 1.00
    profile_warmup_bars: int = 3
    afternoon_profile_reset: str = "disabled"

    def __post_init__(self) -> None:
        fixed: dict[str, Any] = {
            "tick_size": 0.25,
            "point_value": 5.0,
            "commission_per_contract": 0.51,
            "bar_seconds": 180,
            "price_bin_ticks": 1,
            "delta_profile_price_bin_ticks": 4,
            "value_area_fraction": 0.70,
            "value_area_method": VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD,
            "opening_range_seconds": 30,
            "aoi_big_trade_lookback_minutes": 30,
            "big_trade_reference_percentile": 0.999,
            "big_trade_lookback_sessions": 20,
            "big_trade_interval_ms": 100,
            "big_trade_price_bucket_ticks": 1,
            "big_trade_aggregation_mode": BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
            "delta_profile_percentile": 0.90,
            "regime_window_bars": 10,
            "trend_midpoint_shift_ticks": 8,
            "trend_poc_shift_ticks": 8,
            "trend_overlap_maximum": 0.50,
            "trend_efficiency_minimum": 0.55,
            "sweep_minimum_ticks": 2,
            "morning_entry_start": "09:39:00",
            "morning_entry_end": "11:30:00",
            "afternoon_entry_start": "13:39:00",
            "afternoon_entry_end": "15:30:00",
            "entry_offset_ticks": 2,
            "context_distance_atr_fraction": 1.0 / 3.0,
            "burst_freshness_scope": "current_rth_session",
            "stop_at_sweep_extreme": False,
            "stop_offset_ticks": 2,
            "minimum_stop_ticks": 2,
            "atr_lookback_bars": 14,
            "target_1_fraction": 0.50,
            "maximum_holding_bars": 12,
            "maximum_entries_per_aoi": 1,
            "max_trades_per_day": 0,
            "minimum_midpoint_reward_r": 1.00,
            "profile_warmup_bars": 3,
            "afternoon_profile_reset": "disabled",
        }
        drift = [name for name, expected in fixed.items() if not _same_value(getattr(self, name), expected)]
        if drift:
            raise ValueError("fixed adaptive orderflow range v03 mechanic drift: " + ", ".join(drift))
        choices = {
            "sweep_atr_fraction": {0.10, 0.15, 0.20, 0.25, 0.30},
            "maximum_stop_atr_multiple": {1.25, 1.50, 1.75},
        }
        invalid = [
            name
            for name, values in choices.items()
            if not any(_same_value(getattr(self, name), value) for value in values)
        ]
        if invalid:
            raise ValueError("uncertified adaptive orderflow range v03 tunable value: " + ", ".join(invalid))
        if not self.atr_context_path or len(self.atr_context_sha256) != 64:
            raise ValueError("ATR context path and SHA-256 are required")
        if not self.big_trade_context_path or len(self.big_trade_context_sha256) != 64:
            raise ValueError("big-trade context path and SHA-256 are required")


_RETIRED_PARAMETERS = {
    "aoi_level_distance_ticks",
    "aoi_big_trade_lookback_minutes",
    "burst_freshness_bars",
    "footprint_grace_bars",
    "maximum_edge_drift_ticks",
    "maximum_stop_ticks",
    "minimum_weighted_reward_r",
    "reclaim_atr_fraction",
    "regime_window_bars",
    "risk_budget_dollars",
    "stop_buffer_atr_fraction",
    "trend_efficiency_minimum",
    "trend_midpoint_shift_ticks",
    "trend_overlap_maximum",
    "trend_poc_shift_ticks",
    "trend_shift_atr_fraction",
    "drawdown_allowance_dollars",
    "drawdown_reserve_dollars",
    "survival_stopouts",
    "minimum_poc_reward_r",
    "minimum_net_reward_to_worst_case_loss",
    "event_reclaim_hold_seconds",
    "entry_expiry_bars",
    "aoi_ttl_minutes",
    "opening_range_seconds",
    "stop_at_sweep_extreme",
    "failure_confirmation_bars",
    "confirmation_delta_reference_percentile",
    "confirmation_delta_lookback_sessions",
    "confirmation_delta_context_path",
    "confirmation_delta_context_sha256",
}
_ACCEPTED_PARAMETERS = {
    item.name for item in fields(AdaptiveOrderflowRangeV3Config)
} - _RETIRED_PARAMETERS


def build_strategy(
    params: dict[str, Any],
) -> "AdaptiveOrderflowRangeV3EventStrategy":
    unknown = sorted(set(params) - _ACCEPTED_PARAMETERS)
    if unknown:
        raise ValueError("unknown yush_adaptive_orderflow_range_v3 parameter(s): " + ", ".join(unknown))
    return AdaptiveOrderflowRangeV3EventStrategy(AdaptiveOrderflowRangeV3Config(**params))


@dataclass
class AdaptiveFrozenAoi(FrozenAoiCandidate):
    aoi_id: str = ""
    expires_at_ns: int = 0
    last_close_tick: int = 0
    sweep_distance_ticks: int = 2
    context_distance_ticks: int = 1
    profile_epoch: str = "rth"
    footprint_missing_bars: int = 0
    crossing_armed: bool = False
    sweep_observed_bar_index: int | None = None
    sweep_event_high_tick: int | None = None
    sweep_event_low_tick: int | None = None
    aoi_low_tick: int | None = None
    aoi_high_tick: int | None = None
    source_fingerprint: str = ""
    source_observed_at_ns: int = 0


@dataclass
class AdaptiveSweepEpisode(SweepEpisode):
    aoi_id: str = ""
    sweep_distance_ticks: int = 2
    context_distance_ticks: int = 1
    profile_epoch: str = "rth"
    aoi_expires_at_ns: int = 0


@dataclass
class AdaptivePendingSignal(PendingSignal):
    planned_fill_tick: int = 0
    aoi_id: str = ""
    aoi_zone_low_tick: int = 0
    aoi_zone_high_tick: int = 0
    entry_zone_boundary_tick: int = 0
    profile_epoch: str = "rth"
    submission_block_reported: bool = False
    activation_timestamp_ns: int = 0
    activation_event_index: int = 0
    entry_decision_event_index: int = 0
    resolved_stop_tick: int | None = None
    stop_resolution_event_index: int | None = None


class AdaptiveOrderflowRangeV3State(ChartFanaticsRangeState):
    def __init__(
        self,
        session: EventReplaySessionView,
        config: AdaptiveOrderflowRangeV3Config,
    ) -> None:
        super().__init__(session, config)
        self.cfg = config
        self.active_motivewave_burst: WorkingBurst | None = None
        self.profile_epoch = "rth"
        self.profile_epoch_bars = 0
        self.retired_aoi_ids: set[str] = set()
        self.filled_aoi_ids: set[str] = set()
        self.aoi_supersession_audits: list[dict[str, Any]] = []
        self.signal_lifecycle_audits: list[dict[str, Any]] = []
        self.diagnostics.update(
            {
                "profile_epoch_resets": 0,
                "aoi_expirations": 0,
                "aoi_edge_invalidations": 0,
                "aoi_footprint_invalidations": 0,
                "aoi_identity_retirements": 0,
                "aoi_rearms": 0,
                "aoi_supersessions": 0,
                "sweep_crossing_misses": 0,
                "event_crossing_arms": 0,
                "event_crossing_sweeps": 0,
                "aoi_footprint_grace_bars": 0,
                "signal_poc_reward_rejections": 0,
                "geometric_reclaims": 0,
                "event_reclaim_confirmations": 0,
                "event_reclaim_target_invalidations": 0,
                "event_reclaim_aoi_expirations": 0,
                "reclaims_outside_entry_window": 0,
                "signals_created": 0,
                "signal_submissions_blocked": 0,
                "next_event_entry_orders": 0,
                "next_event_entry_expirations": 0,
                "pre_fill_stop_invalidations": 0,
                "actual_fill_stop_distance_rejections": 0,
                "actual_fill_payoff_rejections": 0,
                "midpoint_reward_rejections": 0,
                "immediate_confirmation_activations": 0,
                "actual_fill_midpoint_reward_rejections": 0,
                "actual_fill_approvals": 0,
                "aoi_armed_big_trade": 0,
                "aoi_armed_delta_profile": 0,
                "aoi_armed_market_level": 0,
                "aoi_armed_multi_source": 0,
                "entry_confirmations_big_trade": 0,
                "entry_confirmations_delta_profile": 0,
                "historical_bar_delta_threshold": None,
                "reclaims_without_separate_confirmation": 0,
                "signals_from_big_trade_aoi": 0,
                "signals_from_delta_profile_aoi": 0,
                "signals_from_market_level_aoi": 0,
            }
        )

    def _advance_burst(self, event: CanonicalEvent) -> None:
        """Aggregate consecutive MotiveWave-style same-price/aggressor sequences."""

        side = str(event.side or "")
        tick = int(event.price_tick)
        price_bucket = (
            tick // self.cfg.big_trade_price_bucket_ticks
        ) * self.cfg.big_trade_price_bucket_ticks
        active = self.active_motivewave_burst
        if active is not None and event.timestamp_ns < active.last_at_ns:
            raise ValueError("MotiveWave burst aggregation order is not monotonic")
        matches = bool(
            active is not None
            and side in {BUY_SIDE, SELL_SIDE}
            and side == active.side
            and price_bucket == active.price_low_tick
            and event.timestamp_ns - active.started_at_ns
            <= self.cfg.big_trade_interval_ms * 1_000_000
        )
        if active is not None and not matches:
            self._finalize_motivewave_burst(event.timestamp_ns)
            active = None
        if side not in {BUY_SIDE, SELL_SIDE}:
            return
        size = int(event.size or 0)
        if active is None:
            self.active_motivewave_burst = WorkingBurst(
                side=side,
                price_low_tick=price_bucket,
                price_high_tick=(
                    price_bucket + self.cfg.big_trade_price_bucket_ticks - 1
                ),
                size=size,
                started_at_ns=event.timestamp_ns,
                last_at_ns=event.timestamp_ns,
                last_price_tick=tick,
            )
            return
        active.size += size
        active.last_at_ns = event.timestamp_ns
        active.last_price_tick = tick

    def _finalize_motivewave_burst(self, qualified_at_ns: int) -> None:
        active = self.active_motivewave_burst
        if active is None:
            return
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
        self.active_motivewave_burst = None

    def ingest(self, event: CanonicalEvent) -> None:
        super().ingest(event)
        self._observe_event_crossings(event)

    def _observe_event_crossings(self, event: CanonicalEvent) -> None:
        """Remember causal inside-to-outside crossings at canonical-event resolution.

        A completed-bar high/low cannot prove that price first traded inside the
        frozen edge and only then swept outside it.  This state is therefore
        armed by an ordered trade event at or inside the edge and fired once by
        a later ordered event at the adaptive sweep distance.  The episode is
        still published only when that event's three-minute bar completes.
        """

        working = self.working_bar
        if working is None:
            return
        price_tick = int(event.price_tick)
        for direction in ("short", "long"):
            candidate = self.frozen_aois.get(direction)
            if not isinstance(candidate, AdaptiveFrozenAoi):
                continue
            if candidate.sweep_observed_bar_index is not None:
                candidate.sweep_event_high_tick = max(
                    int(candidate.sweep_event_high_tick or price_tick),
                    price_tick,
                )
                candidate.sweep_event_low_tick = min(
                    int(candidate.sweep_event_low_tick or price_tick),
                    price_tick,
                )
                continue
            edge = candidate.aoi.edge_tick
            inside = price_tick <= edge if direction == "short" else price_tick >= edge
            if inside and not candidate.crossing_armed:
                candidate.crossing_armed = True
                self.diagnostics["event_crossing_arms"] += 1
            swept = (
                price_tick >= edge + candidate.sweep_distance_ticks
                if direction == "short"
                else price_tick <= edge - candidate.sweep_distance_ticks
            )
            if candidate.crossing_armed and swept:
                candidate.sweep_observed_bar_index = working.index
                candidate.sweep_event_high_tick = price_tick
                candidate.sweep_event_low_tick = price_tick
                self.diagnostics["event_crossing_sweeps"] += 1

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
        self.profile_epoch_bars += 1
        for bucket, volume in bar.bin_volume.items():
            self.profile_volume[bucket] = self.profile_volume.get(bucket, 0) + volume
        for bucket, delta in _motivewave_delta_cells(
            bar.bin_delta,
            self.cfg.delta_profile_price_bin_ticks,
        ).items():
            self.profile_delta[bucket] = self.profile_delta.get(bucket, 0) + delta
        self.published_profile = _profile_snapshot(
            self.profile_volume,
            self.cfg.price_bin_ticks,
            self.cfg.value_area_fraction,
            self.cfg.value_area_method,
        )
        # V03-simple has no independent trend-state hypothesis.  Keep a
        # neutral snapshot only because the generic event report schema
        # records a regime object with each trade.
        self.published_regime = RegimeSnapshot(
            label=REGIME_NON_TRENDING,
            overlap=0.0,
            poc_a_tick=0,
            poc_b_tick=0,
            midpoint_a_tick=0.0,
            midpoint_b_tick=0.0,
            efficiency=0.0,
            close_tick=bar.close_tick,
        )
        self.diagnostics["completed_3m_bars"] += 1
        self.diagnostics["non_trending_regime_bars"] += 1
        if self.profile_epoch_bars >= self.cfg.profile_warmup_bars:
            self._advance_frozen_aois(bar)
        self._expire_pending_after_bar(bar.index)

    def _advance_frozen_aois(self, bar: CompletedBar) -> None:
        profile = self.published_profile
        regime = self.published_regime
        if profile is None or regime is None:
            return
        context_distance_ticks = _adaptive_ticks(
            self.cfg.context_distance_atr_fraction,
            float(bar.atr_ticks or 0.0),
            floor=1,
        )
        for direction in ("short", "long"):
            # The candidate visible during ``bar`` was built from the profile
            # published at the prior boundary.  Evaluate its ordered sweep once,
            # then retire it regardless of whether the latest value edge moved.
            candidate = self.frozen_aois.get(direction)
            if isinstance(candidate, AdaptiveFrozenAoi):
                self._detect_frozen_aoi_sweep(bar, candidate)
                self._retire_candidate(direction, candidate)

            current_aoi, aoi_id = self._current_aoi_identity(
                direction,
                profile,
                as_of_ns=bar.end_ns,
                context_distance_ticks=context_distance_ticks,
                source_bar_index=bar.index,
            )
            if current_aoi is None or aoi_id is None:
                self.diagnostics["aoi_without_institutional_footprint"] += 1
                continue
            aoi_low, aoi_high = _score_bounds(current_aoi)
            self.frozen_aois[direction] = AdaptiveFrozenAoi(
                direction=direction,
                aoi=current_aoi,
                profile=profile,
                regime=regime,
                frozen_bar_index=bar.index,
                frozen_at_ns=bar.end_ns,
                aoi_id=aoi_id,
                expires_at_ns=0,
                last_close_tick=bar.close_tick,
                sweep_distance_ticks=_adaptive_ticks(
                    self.cfg.sweep_atr_fraction,
                    float(bar.atr_ticks or 0.0),
                    floor=self.cfg.sweep_minimum_ticks,
                ),
                context_distance_ticks=context_distance_ticks,
                profile_epoch=self.profile_epoch,
                aoi_low_tick=aoi_low,
                aoi_high_tick=aoi_high,
                source_fingerprint=_aoi_source_fingerprint(current_aoi),
                source_observed_at_ns=_aoi_source_observed_at_ns(
                    current_aoi,
                    fallback_ns=bar.end_ns,
                ),
            )
            self.diagnostics["frozen_aoi_candidates"] += 1
            source_kinds = _aoi_source_kinds(current_aoi)
            for source_kind in source_kinds:
                self.diagnostics[f"aoi_armed_{source_kind}"] += 1
            if len(source_kinds) > 1:
                self.diagnostics["aoi_armed_multi_source"] += 1
            self.diagnostics["aoi_rearms"] += int(bar.index > self.cfg.profile_warmup_bars - 1)

    def _current_aoi_identity(
        self,
        direction: str,
        profile: ProfileSnapshot,
        *,
        as_of_ns: int,
        context_distance_ticks: int,
        source_bar_index: int | None = None,
    ) -> tuple[AoiScore | None, str | None]:
        edge_tick = profile.vah_tick if direction == "short" else profile.val_tick
        score = self._score_price(
            edge_tick,
            profile,
            direction=direction,
            as_of_ns=as_of_ns,
            context_distance_ticks=context_distance_ticks,
        )
        if not _aoi_source_kinds(score):
            return None, None
        identity = (
            f"{self.profile_epoch}:asof_bar={source_bar_index}:"
            f"{direction}:{edge_tick}:"
            f"sources={_aoi_source_fingerprint(score)}"
        )
        return score, identity

    def _score_price(
        self,
        tick: int,
        profile: ProfileSnapshot,
        *,
        direction: str,
        as_of_ns: int,
        context_distance_ticks: int,
    ) -> AoiScore:
        """Qualify an edge with causal order-flow or structural context."""

        if direction not in {"short", "long"}:
            raise ValueError(f"unsupported AOI direction: {direction!r}")
        expected_edge = profile.vah_tick if direction == "short" else profile.val_tick
        if tick != expected_edge:
            raise ValueError("AOI score tick must equal the direction's current value edge")
        def symmetric_location_matches(burst: Any) -> bool:
            return (
                tick - context_distance_ticks <= burst.price_low_tick
                and burst.price_high_tick <= tick + context_distance_ticks
            )

        candidates = [
            burst
            for burst in self.bursts
            if burst.ended_at_ns <= as_of_ns
            and burst.qualified_at_ns <= as_of_ns
            and symmetric_location_matches(burst)
        ]
        burst = (
            max(candidates, key=lambda item: (item.ended_at_ns, item.size, item.burst_id))
            if candidates
            else None
        )
        delta_threshold = _nearest_rank(
            [abs(value) for value in self.profile_delta.values()],
            self.cfg.delta_profile_percentile,
        )
        delta_candidates = [
            (
                int(bucket),
                int(bucket) + self.cfg.delta_profile_price_bin_ticks - 1,
                int(value),
            )
            for bucket, value in self.profile_delta.items()
            if delta_threshold is not None
            and delta_threshold > 0
            and abs(int(value)) >= delta_threshold
            and tick - context_distance_ticks
            <= int(bucket)
            <= tick + context_distance_ticks
        ]
        selected_delta = (
            max(
                delta_candidates,
                key=lambda item: (
                    abs(item[2]),
                    -abs(item[0] - tick),
                    -item[0],
                ),
            )
            if delta_candidates
            else None
        )
        source_names = []
        if burst is not None:
            source_names.append("adaptive_large_execution")
        if selected_delta is not None:
            source_names.append("sign_agnostic_top_decile_delta")
        return AoiScore(
            edge_tick=tick,
            institutional_footprint_kind=("_and_".join(source_names) if source_names else "none"),
            market_level_point=False,
            big_trade_point=burst is not None,
            delta_profile_point=selected_delta is not None,
            nearest_market_level_type=None,
            nearest_market_level_tick=None,
            big_trade_burst_id=None if burst is None else burst.burst_id,
            big_trade_burst_side=None if burst is None else burst.side,
            big_trade_burst_low_tick=None if burst is None else burst.price_low_tick,
            big_trade_burst_high_tick=None if burst is None else burst.price_high_tick,
            big_trade_burst_size=None if burst is None else burst.size,
            big_trade_burst_qualified_at_ns=None if burst is None else burst.qualified_at_ns,
            delta_profile_bin_low_tick=(None if selected_delta is None else selected_delta[0]),
            delta_profile_bin_high_tick=(None if selected_delta is None else selected_delta[1]),
            delta_profile_abs_delta=(None if selected_delta is None else abs(selected_delta[2])),
            delta_profile_threshold=delta_threshold,
            delta_profile_signed_delta=(None if selected_delta is None else selected_delta[2]),
        )

    def _expire_old_bursts(self, timestamp_ns: int) -> None:
        # State is recreated at each RTH session start, so retaining this deque
        # makes every qualifying burst from the current session available.
        del timestamp_ns

    def _expire_pending_after_bar(self, bar_index: int) -> None:
        # A swept setup's stop-entry has no clock expiry.  Its protective stop
        # does not exist until the fill event, so there is no pre-fill stop
        # invalidation either.
        del bar_index

    def _detect_frozen_aoi_sweep(
        self,
        bar: CompletedBar,
        candidate: FrozenAoiCandidate,
    ) -> None:
        typed = _adaptive_candidate(candidate)
        if not self._within_signal_window(bar.end_ns):
            return
        current = self.episodes[typed.direction]
        if current is not None and not current.expired:
            return
        swept_in_bar = typed.sweep_observed_bar_index == bar.index
        if not swept_in_bar:
            geometric_sweep = (
                bar.high_tick >= typed.aoi.edge_tick + typed.sweep_distance_ticks
                if typed.direction == "short"
                else bar.low_tick <= typed.aoi.edge_tick - typed.sweep_distance_ticks
            )
            self.diagnostics[
                "sweep_crossing_misses" if geometric_sweep else "qualified_aoi_without_sweep"
            ] += 1
            return
        sweep_high_tick = max(bar.high_tick, int(typed.sweep_event_high_tick or bar.high_tick))
        sweep_low_tick = min(bar.low_tick, int(typed.sweep_event_low_tick or bar.low_tick))
        self.episode_counter += 1
        episode = AdaptiveSweepEpisode(
            episode_id=self.episode_counter,
            direction=typed.direction,
            aoi=typed.aoi,
            sweep_bar_index=bar.index,
            sweep_bar_high_tick=sweep_high_tick,
            sweep_bar_low_tick=sweep_low_tick,
            highest_tick_since_sweep=sweep_high_tick,
            lowest_tick_since_sweep=sweep_low_tick,
            starting_profile=typed.profile,
            starting_regime=typed.regime,
            aoi_frozen_bar_index=typed.frozen_bar_index,
            aoi_frozen_at_ns=typed.frozen_at_ns,
            aoi_id=typed.aoi_id,
            sweep_distance_ticks=typed.sweep_distance_ticks,
            context_distance_ticks=typed.context_distance_ticks,
            profile_epoch=typed.profile_epoch,
            aoi_expires_at_ns=typed.expires_at_ns,
        )
        self.episodes[typed.direction] = episode
        self.diagnostics["sweep_episodes"] += 1
        self._activate_swept_episode(
            episode,
            decision_bar=bar,
            observed_event_ns=bar.end_ns,
        )

    def _activate_swept_episode(
        self,
        episode: AdaptiveSweepEpisode,
        *,
        decision_bar: CompletedBar,
        observed_event_ns: int,
    ) -> None:
        if episode.expired:
            return
        entry_window_open = self._within_signal_window(observed_event_ns)
        if not entry_window_open:
            self.diagnostics["reclaims_outside_entry_window"] += 1
            self._record_signal_lifecycle(
                episode,
                decision_bar,
                event="signal_rejected",
                reason="completed_sweep_outside_declared_entry_window",
                entry_window_open=False,
                observed_event_ns=observed_event_ns,
            )
            signal = None
        else:
            signal = self._build_pending_signal(
                episode,
                decision_bar,
            )
        episode.expired = True
        episode.failure_bar_index = decision_bar.index
        self._retire_episode(episode)
        if signal is None:
            return
        self.pending[signal.order_id] = signal
        self.diagnostics["signals_created"] += 1
        self.diagnostics["reclaims_without_separate_confirmation"] += 1
        for source_kind in _aoi_source_kinds(episode.aoi):
            self.diagnostics[f"signals_from_{source_kind}_aoi"] += 1
        self._record_signal_lifecycle(
            episode,
            decision_bar,
            event="signal_created",
            reason="completed_ordered_sweep_armed_reclaim_side_aoi_zone_stop_immediately",
            entry_window_open=True,
            risk_ticks=None,
            poc_reward_r=None,
            observed_event_ns=observed_event_ns,
        )
        self.action_due = True

    def _build_pending_signal(
        self,
        episode: SweepEpisode,
        bar: CompletedBar,
    ) -> AdaptivePendingSignal | None:
        typed = _adaptive_episode(episode)
        direction = typed.direction
        aoi_zone_low_tick, aoi_zone_high_tick = _score_bounds(typed.aoi)
        entry_zone_boundary_tick = (
            aoi_zone_low_tick if direction == "short" else aoi_zone_high_tick
        )
        # A completed ordered sweep arms a stop-market trigger two ticks beyond
        # the reclaim-side boundary of this bar's AOI zone.  The protective
        # stop is deliberately unresolved until the causal fill event.
        entry_tick = (
            entry_zone_boundary_tick - self.cfg.entry_offset_ticks
            if direction == "short"
            else entry_zone_boundary_tick + self.cfg.entry_offset_ticks
        )
        planned_fill_tick = entry_tick
        profile = typed.starting_profile
        regime = self.published_regime or typed.starting_regime
        midpoint = (profile.vah_tick + profile.val_tick) / 2.0
        target_1 = _round_target_tick(midpoint, direction=direction)
        target_2 = profile.val_tick if direction == "short" else profile.vah_tick
        return AdaptivePendingSignal(
            order_id=f"{direction}_{typed.episode_id}",
            episode=typed,
            direction=direction,
            entry_tick=entry_tick,
            stop_tick=0,
            target_1_tick=target_1,
            target_2_tick=target_2,
            risk_ticks=0,
            failure_bar_index=bar.index,
            expiry_bar_index=bar.index,
            failure_bar=bar,
            failure_profile=profile,
            failure_regime=regime,
            highest_tick_since_sweep=typed.highest_tick_since_sweep,
            lowest_tick_since_sweep=typed.lowest_tick_since_sweep,
            planned_fill_tick=planned_fill_tick,
            aoi_id=typed.aoi_id,
            aoi_zone_low_tick=aoi_zone_low_tick,
            aoi_zone_high_tick=aoi_zone_high_tick,
            entry_zone_boundary_tick=entry_zone_boundary_tick,
            profile_epoch=typed.profile_epoch,
            activation_timestamp_ns=int(bar.end_ns),
            activation_event_index=int(self.last_event.event_index if self.last_event is not None else 0),
            entry_decision_event_index=int(self.last_event.event_index if self.last_event is not None else 0) + 1,
        )

    def _record_signal_lifecycle(
        self,
        episode: AdaptiveSweepEpisode,
        bar: CompletedBar,
        *,
        event: str,
        reason: str,
        entry_window_open: bool,
        risk_ticks: int | None = None,
        maximum_stop_ticks: int | None = None,
        poc_reward_r: float | None = None,
        observed_event_ns: int | None = None,
    ) -> None:
        next_event_ns = (
            observed_event_ns
            if observed_event_ns is not None
            else (None if self.last_event is None else int(self.last_event.timestamp_ns))
        )
        self.signal_lifecycle_audits.append(
            {
                "event": event,
                "reason": reason,
                "direction": episode.direction,
                "episode_id": episode.episode_id,
                "aoi_id": episode.aoi_id,
                "decision_bar_end": _timestamp_label(bar.end_ns),
                "order_activation_at": _timestamp_label(bar.end_ns),
                "next_observed_event": (
                    None if next_event_ns is None else _timestamp_label(next_event_ns)
                ),
                "entry_window_open": entry_window_open,
                "risk_ticks": risk_ticks,
                "maximum_stop_ticks": maximum_stop_ticks,
                "midpoint_reward_r": poc_reward_r,
                "confirmation_kind": "not_required",
                "confirmation_id": None,
                "confirmation_at": None,
                "confirmation_price": None,
                "confirmation_value": None,
            }
        )

    def _advance_pending_extremes(self, event: CanonicalEvent) -> None:
        price_tick = int(event.price_tick)
        for signal in self.pending.values():
            if signal.cancelled:
                continue
            signal.highest_tick_since_sweep = max(
                int(signal.highest_tick_since_sweep),
                price_tick,
            )
            signal.lowest_tick_since_sweep = min(
                int(signal.lowest_tick_since_sweep),
                price_tick,
            )

    def signal_is_fillable(
        self,
        signal: PendingSignal,
        event: CanonicalEvent,
    ) -> bool:
        if signal.cancelled or not isinstance(signal, AdaptivePendingSignal):
            return False
        # ``ingest`` has already included this exact crossing event in the
        # sweep-to-entry extremes.  Resolve the stop here, on the causal fill
        # event, but before the engine sizes or commits the position.
        resolved_stop_tick = (
            int(signal.highest_tick_since_sweep) + self.cfg.stop_offset_ticks
            if signal.direction == "short"
            else int(signal.lowest_tick_since_sweep) - self.cfg.stop_offset_ticks
        )
        fill_reference_tick = (
            min(int(signal.entry_tick), int(event.price_tick))
            if signal.direction == "short"
            else max(int(signal.entry_tick), int(event.price_tick))
        )
        modeled_fill_tick = (
            fill_reference_tick - ENTRY_SLIPPAGE_TICKS
            if signal.direction == "short"
            else fill_reference_tick + ENTRY_SLIPPAGE_TICKS
        )
        risk_ticks = (
            resolved_stop_tick - modeled_fill_tick
            if signal.direction == "short"
            else modeled_fill_tick - resolved_stop_tick
        )
        maximum = _atr_stop_limit_ticks(
            self.cfg,
            float(signal.failure_bar.atr_ticks or 0.0),
        )
        reward_1 = (
            modeled_fill_tick - signal.target_1_tick
            if signal.direction == "short"
            else signal.target_1_tick - modeled_fill_tick
        )
        midpoint_reward_r = _poc_reward_r(reward_1, risk_ticks)
        stop_valid = self.cfg.minimum_stop_ticks <= risk_ticks <= maximum
        payoff_valid = reward_1 > 0 and midpoint_reward_r >= self.cfg.minimum_midpoint_reward_r
        if not stop_valid:
            self.diagnostics["actual_fill_stop_distance_rejections"] += 1
            reason = "aoi_zone_stop_entry_fill_outside_certified_atr_stop_bounds"
        elif not payoff_valid:
            self.diagnostics["actual_fill_payoff_rejections"] += 1
            self.diagnostics["actual_fill_midpoint_reward_rejections"] += 1
            reason = "aoi_zone_stop_entry_midpoint_gross_reward_to_risk_below_one"
        else:
            self.diagnostics["actual_fill_approvals"] += 1
            reason = "aoi_zone_stop_entry_passed_stop_and_midpoint_gross_payoff_gates"
            signal.resolved_stop_tick = int(resolved_stop_tick)
            signal.stop_resolution_event_index = int(event.event_index)
            signal.stop_tick = int(resolved_stop_tick)
            signal.risk_ticks = int(risk_ticks)
        self._record_signal_lifecycle(
            _adaptive_episode(signal.episode),
            signal.failure_bar,
            event=("actual_fill_approved" if stop_valid and payoff_valid else "actual_fill_rejected"),
            reason=reason,
            entry_window_open=self._within_signal_window(event.timestamp_ns),
            risk_ticks=risk_ticks,
            maximum_stop_ticks=maximum,
            poc_reward_r=midpoint_reward_r,
            observed_event_ns=event.timestamp_ns,
        )
        return stop_valid and payoff_valid

    def record_aoi_entry(self, direction: str, edge_tick: int) -> None:
        del direction, edge_tick

    def _retire_candidate(
        self,
        direction: str,
        candidate: FrozenAoiCandidate,
    ) -> None:
        typed = _adaptive_candidate(candidate)
        self.retired_aoi_ids.add(typed.aoi_id)
        self.frozen_aois[direction] = None
        self.diagnostics["aoi_identity_retirements"] += 1

    def _cancel_pending_for_aoi(self, aoi_id: str) -> None:
        cancelled = False
        for signal in self.pending.values():
            if isinstance(signal, AdaptivePendingSignal) and signal.aoi_id == aoi_id and not signal.cancelled:
                signal.cancelled = True
                cancelled = True
        if cancelled:
            self.cancel_orders = True

    def _retire_episode(self, episode: AdaptiveSweepEpisode) -> None:
        self.retired_aoi_ids.add(episode.aoi_id)
        candidate = self.frozen_aois.get(episode.direction)
        if isinstance(candidate, AdaptiveFrozenAoi) and candidate.aoi_id == episode.aoi_id:
            self.frozen_aois[episode.direction] = None
        self.diagnostics["aoi_identity_retirements"] += 1


class AdaptiveOrderflowRangeV3EventStrategy(ChartFanaticsRangeEventStrategy):
    def __init__(
        self,
        config: AdaptiveOrderflowRangeV3Config | None = None,
    ) -> None:
        self.cfg = config or AdaptiveOrderflowRangeV3Config()
        self.state: AdaptiveOrderflowRangeV3State | None = None

    def on_session_start(
        self,
        session: EventReplaySessionView,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        self.state = AdaptiveOrderflowRangeV3State(session, self.cfg)

    def entry_order_is_live(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> bool:
        del event, broker
        signal = self._state().pending.get(order.order_id)
        return bool(
            isinstance(signal, AdaptivePendingSignal)
            and not signal.cancelled
        )

    def entry_fill_stop_tick(
        self,
        order: EventEntryOrder,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> int | None:
        del event, broker
        signal = self._state().pending.get(order.order_id)
        if not isinstance(signal, AdaptivePendingSignal):
            return None
        return signal.resolved_stop_tick

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        state = self._state()
        signal = state.pending.get(order.order_id)
        if not isinstance(signal, AdaptivePendingSignal):
            raise AssertionError("v03 fill has no adaptive pending signal")
        aoi_id = signal.aoi_id
        profile_epoch = signal.profile_epoch
        typed_episode = _adaptive_episode(signal.episode)
        sweep_distance = typed_episode.sweep_distance_ticks
        super().on_entry_filled(order, position, event, broker)
        state.filled_aoi_ids.add(aoi_id)
        filled_tick = int(round(position.entry_price / self.cfg.tick_size))
        risk_ticks = int(round(position.risk_points / self.cfg.tick_size))
        reward_1_ticks = (
            filled_tick - signal.target_1_tick
            if signal.direction == "short"
            else signal.target_1_tick - filled_tick
        )
        broker.annotate_position(
            setup_model="per_bar_orderflow_value_edge_sweep_reclaim",
            aoi_identity=aoi_id,
            aoi_source_kinds=",".join(_aoi_source_kinds(signal.episode.aoi)),
            aoi_zone_low_price=signal.aoi_zone_low_tick * self.cfg.tick_size,
            aoi_zone_high_price=signal.aoi_zone_high_tick * self.cfg.tick_size,
            entry_zone_boundary_price=(
                signal.entry_zone_boundary_tick * self.cfg.tick_size
            ),
            market_level_qualified=signal.episode.aoi.market_level_point,
            selected_market_level_type=signal.episode.aoi.nearest_market_level_type,
            selected_market_level_price=(
                None
                if signal.episode.aoi.nearest_market_level_tick is None
                else signal.episode.aoi.nearest_market_level_tick * self.cfg.tick_size
            ),
            selected_delta_signed_delta=signal.episode.aoi.delta_profile_signed_delta,
            entry_confirmation_kind="not_required",
            entry_confirmation_id=None,
            entry_confirmation_at=None,
            entry_confirmation_price=None,
            entry_confirmation_bin_low_price=None,
            entry_confirmation_bin_high_price=None,
            entry_confirmation_value=None,
            entry_confirmation_threshold=None,
            profile_epoch=profile_epoch,
            sweep_atr_fraction=self.cfg.sweep_atr_fraction,
            sweep_distance_ticks=sweep_distance,
            context_distance_atr_fraction=self.cfg.context_distance_atr_fraction,
            context_distance_ticks=typed_episode.context_distance_ticks,
            burst_freshness_scope=self.cfg.burst_freshness_scope,
            order_activation_at=_timestamp_label(signal.activation_timestamp_ns),
            order_activation_event_index=signal.activation_event_index,
            order_activation_price=signal.failure_bar.close_tick * self.cfg.tick_size,
            entry_decision_event_index=signal.entry_decision_event_index,
            actual_fill_gate_passed=True,
            maximum_stop_atr_multiple=self.cfg.maximum_stop_atr_multiple,
            profile_price_bin_ticks=self.cfg.price_bin_ticks,
            delta_profile_price_bin_ticks=self.cfg.delta_profile_price_bin_ticks,
            delta_aggregation_method=DELTA_AGGREGATION_METHOD,
            stop_offset_ticks=self.cfg.stop_offset_ticks,
            stop_determined_at_entry=True,
            stop_resolution_event_index=signal.stop_resolution_event_index,
            sweep_to_entry_high_price=(
                signal.highest_tick_since_sweep * self.cfg.tick_size
            ),
            sweep_to_entry_low_price=(
                signal.lowest_tick_since_sweep * self.cfg.tick_size
            ),
            resolved_stop_price=order.stop_tick * self.cfg.tick_size,
            burst_reference_percentile=self.cfg.big_trade_reference_percentile,
            burst_definition=BURST_DEFINITION,
            burst_direction_rule="aoi_big_trade_side_unrestricted;no_separate_confirmation",
            burst_location_rule=(
                "AOI source may lie within one-third ATR above or below the latest edge"
            ),
            delta_profile_definition=DELTA_PROFILE_DEFINITION,
            market_level_definition=MARKET_LEVEL_DEFINITION,
            minimum_midpoint_reward_r=self.cfg.minimum_midpoint_reward_r,
            midpoint_reward_r=_poc_reward_r(reward_1_ticks, risk_ticks),
            worst_case_stop_loss_dollars_per_contract=(
                _worst_case_stop_loss_dollars(self.cfg, risk_ticks)
            ),
            target_1_definition="frozen_value_area_midpoint_half_exit",
            target_2_definition="frozen_opposite_value_edge_remainder_exit",
            target_1_fraction=self.cfg.target_1_fraction,
            directional_trend_veto_passed=None,
            trend_state_at_failure=None,
            trend_state_at_entry=None,
            risk_budget_dollars=None,
            signal_instrument="ES",
            execution_instrument="MES",
            execution_risk_fraction_net_liq=0.004,
            minimum_contract_affordability_rule=(
                "Reject only when one MES including modeled stop slippage and "
                "round-turn commission exceeds 0.4% of current net liquidation"
            ),
            entry_order_type="reclaim_side_aoi_zone_stop_market",
            entry_reference_price=position.entry_reference_tick * self.cfg.tick_size,
            entry_trigger_rule=(
                "After a completed ordered sweep, immediately arm a stop-market entry "
                "two ticks beyond the reclaim-side boundary of that bar's AOI zone; "
                "short uses zone low minus two ticks "
                "and long uses zone high plus two ticks"
            ),
            entry_fill_model=(
                "Canonical gap-aware stop-market entry on the first ordered crossing; "
                "no intended-stop invalidation exists before fill"
            ),
            failure_confirmation_rule=(
                "No separate post-sweep big-trade or delta confirmation is required"
            ),
            failure_confirmation_bars=None,
            sweep_crossing_rule=(
                "For the AOI rebuilt at the prior three-minute boundary, an ordered event "
                "at or inside the exact edge arms "
                "the crossing; one later ordered event at the adaptive distance starts "
                "one sweep episode when its three-minute bar completes"
            ),
            profile_snapshot_timing=(
                "One RTH profile accumulates continuously from 09:30 with no 13:30 reset; "
                "VAH and VAL AOIs are rebuilt independently at every completed three-minute "
                "boundary; the midpoint and opposite edge attached to a swept setup remain fixed"
            ),
            footprint_definition=(
                "AOI context is the latest value edge plus q99.9 aggressive volume of either "
                "side and/or sign-agnostic top-decile absolute session-anchored four-tick "
                "profile delta within one-third ATR above or below the edge; a market level "
                "alone cannot create an AOI"
            ),
            protective_stop_rule=(
                "Resolve only on the fill event at two ticks beyond the adverse extreme "
                "from the sweep bar through the entry event, inclusive"
            ),
        )

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
        if closed_this_event or broker.position is not None:
            return
        if entries_blocked:
            for signal in state.pending.values():
                typed = _adaptive_pending(signal)
                if signal.cancelled or typed.submission_block_reported:
                    continue
                typed.submission_block_reported = True
                signal.cancelled = True
                state.diagnostics["signal_submissions_blocked"] += 1
                state._record_signal_lifecycle(
                    typed.episode,
                    typed.failure_bar,
                    event="signal_submission_blocked",
                    reason=_entry_block_reason(state, event.timestamp_ns),
                    entry_window_open=state._within_signal_window(event.timestamp_ns),
                    risk_ticks=typed.risk_ticks,
                    maximum_stop_ticks=_atr_stop_limit_ticks(
                        self.cfg,
                        float(typed.failure_bar.atr_ticks or 0.0),
                    ),
                    poc_reward_r=_poc_reward_r(
                        (
                            typed.planned_fill_tick - typed.target_1_tick
                            if typed.direction == "short"
                            else typed.target_1_tick - typed.planned_fill_tick
                        ),
                        typed.risk_ticks,
                    ),
                    observed_event_ns=event.timestamp_ns,
                )
            return
        for order_id, signal in tuple(state.pending.items()):
            if signal.cancelled:
                if order_id in broker.orders:
                    broker.cancel_entry(order_id, reason="signal_cancelled")
                continue
            if signal.submitted:
                continue
            broker.submit_or_replace_entry(
                order_id=order_id,
                direction=signal.direction,
                entry_tick=signal.entry_tick,
                stop_tick=None,
                target_tick=None,
                order_type="stop_market",
                priority=-signal.episode.aoi.institutional_footprint_count,
                metadata={
                    "episode_id": signal.episode.episode_id,
                    "aoi_edge_tick": signal.episode.aoi.edge_tick,
                    "aoi_identity": _adaptive_pending(signal).aoi_id,
                    "entry_order_type": "reclaim_side_aoi_zone_stop_market",
                },
                report_fields={
                    "institutional_footprint_kind": (signal.episode.aoi.institutional_footprint_kind),
                    "target_1_price": signal.target_1_tick * self.cfg.tick_size,
                    "target_2_price": signal.target_2_tick * self.cfg.tick_size,
                    "entry_order_type": "reclaim_side_aoi_zone_stop_market",
                },
            )
            signal.submitted = True
            state.diagnostics["orders_submitted"] += 1
            state._record_signal_lifecycle(
                _adaptive_episode(signal.episode),
                signal.failure_bar,
                event="order_submitted",
                reason="reclaim_side_aoi_zone_stop_market_armed_immediately_after_sweep",
                entry_window_open=True,
                risk_ticks=signal.risk_ticks,
                maximum_stop_ticks=_atr_stop_limit_ticks(
                    self.cfg,
                    float(signal.failure_bar.atr_ticks or 0.0),
                ),
                poc_reward_r=_poc_reward_r(
                    (
                        signal.planned_fill_tick - signal.target_1_tick
                        if signal.direction == "short"
                        else signal.target_1_tick - signal.planned_fill_tick
                    ),
                    signal.risk_ticks,
                ),
                observed_event_ns=event.timestamp_ns,
            )

    def on_order_cancelled(
        self,
        order: EventEntryOrder,
        reason: str,
        event: CanonicalEvent | None,
        broker: EventReplayBroker,
    ) -> None:
        super().on_order_cancelled(order, reason, event, broker)

    def session_audit(self) -> Mapping[str, Any]:
        values = dict(super().session_audit())
        state = self._state()
        values.update(
            {
                "profile_epoch": state.profile_epoch,
                "profile_epoch_bars": state.profile_epoch_bars,
                "retired_aoi_identities": len(state.retired_aoi_ids),
                "filled_aoi_identities": len(state.filled_aoi_ids),
                "aoi_supersession_audits_json": json.dumps(
                    state.aoi_supersession_audits,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "signal_lifecycle_audits_json": json.dumps(
                    state.signal_lifecycle_audits,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
        )
        return values

    def _state(self) -> AdaptiveOrderflowRangeV3State:
        if self.state is None:
            raise RuntimeError("Adaptive orderflow range v03 has not started")
        return self.state


def _motivewave_delta_cells(
    one_tick_delta: Mapping[int, int],
    price_bin_ticks: int,
) -> dict[int, int]:
    """Aggregate exact price rows into fixed MotiveWave tick intervals.

    Keys are the lower tick of a globally aligned interval.  With ES and four
    ticks, 7380.00 through 7380.75 therefore share the 7380.00 cell.
    """

    if price_bin_ticks <= 0:
        raise ValueError("delta price-bin ticks must be positive")
    cells: dict[int, int] = {}
    for price_tick, delta in one_tick_delta.items():
        low_tick = math.floor(int(price_tick) / price_bin_ticks) * price_bin_ticks
        cells[low_tick] = cells.get(low_tick, 0) + int(delta)
    return cells


def _adaptive_ticks(fraction: float, atr_ticks: float, *, floor: int) -> int:
    return max(int(floor), int(math.floor(float(fraction) * float(atr_ticks) + 0.5)))


def _timestamp_label(timestamp_ns: int) -> str:
    return pd.Timestamp(int(timestamp_ns), tz="UTC").tz_convert(
        "America/New_York"
    ).isoformat()


def _entry_block_reason(
    state: AdaptiveOrderflowRangeV3State,
    timestamp_ns: int,
) -> str:
    timestamp = pd.Timestamp(timestamp_ns, tz="UTC").tz_convert(
        "America/New_York"
    )
    seconds = timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
    morning_start = _clock_seconds(state.cfg.morning_entry_start)
    morning_end = _clock_seconds(state.cfg.morning_entry_end)
    afternoon_start = _clock_seconds(state.cfg.afternoon_entry_start)
    afternoon_end = _clock_seconds(state.cfg.afternoon_entry_end)
    if seconds < morning_start:
        return "next_event_before_morning_entry_start"
    if morning_end < seconds < afternoon_start:
        return "next_event_between_declared_entry_windows"
    if seconds > afternoon_end:
        return "next_event_after_latest_entry_cutoff"
    return "engine_entry_blocked_inside_strategy_window"


def _clock_seconds(value: str) -> int:
    hour, minute, second = (int(item) for item in value.split(":"))
    return hour * 3600 + minute * 60 + second


def _atr_stop_limit_ticks(
    config: AdaptiveOrderflowRangeV3Config,
    atr_ticks: float,
) -> int:
    adaptive = int(math.floor(float(atr_ticks) * config.maximum_stop_atr_multiple))
    return max(config.minimum_stop_ticks, adaptive)


def _poc_reward_r(reward_ticks: int, risk_ticks: int) -> float:
    if risk_ticks <= 0:
        return -math.inf
    return float(reward_ticks) / float(risk_ticks)


def _net_target_reward_dollars(
    config: AdaptiveOrderflowRangeV3Config,
    reward_ticks: float,
) -> float:
    tick_value = float(config.tick_size) * float(config.point_value)
    return float(reward_ticks) * tick_value - 2.0 * float(config.commission_per_contract)


def _worst_case_stop_loss_dollars(
    config: AdaptiveOrderflowRangeV3Config,
    risk_ticks: int,
) -> float:
    tick_value = float(config.tick_size) * float(config.point_value)
    return (
        float(risk_ticks + PROTECTIVE_STOP_SLIPPAGE_TICKS) * tick_value
        + 2.0 * float(config.commission_per_contract)
    )


def _net_reward_to_worst_case_loss(
    config: AdaptiveOrderflowRangeV3Config,
    reward_ticks: float,
    risk_ticks: int,
) -> float:
    worst_case_loss = _worst_case_stop_loss_dollars(config, risk_ticks)
    if risk_ticks <= 0 or worst_case_loss <= 0:
        return -math.inf
    return _net_target_reward_dollars(config, reward_ticks) / worst_case_loss


def _score_bounds(score: AoiScore) -> tuple[int, int]:
    lows = [int(score.edge_tick)]
    highs = [int(score.edge_tick)]
    if score.big_trade_point:
        if score.big_trade_burst_low_tick is not None:
            lows.append(int(score.big_trade_burst_low_tick))
        if score.big_trade_burst_high_tick is not None:
            highs.append(int(score.big_trade_burst_high_tick))
    if score.delta_profile_point:
        if score.delta_profile_bin_low_tick is not None:
            lows.append(int(score.delta_profile_bin_low_tick))
        if score.delta_profile_bin_high_tick is not None:
            highs.append(int(score.delta_profile_bin_high_tick))
    return min(lows), max(highs)


def _aoi_source_kinds(score: AoiScore) -> tuple[str, ...]:
    values: list[str] = []
    if score.big_trade_point:
        values.append("big_trade")
    if score.delta_profile_point:
        values.append("delta_profile")
    return tuple(values)


def _aoi_source_fingerprint(score: AoiScore) -> str:
    values: list[str] = []
    if score.big_trade_point:
        values.append(f"burst={score.big_trade_burst_id or 0}")
    if score.delta_profile_point:
        sign = (
            "positive"
            if int(score.delta_profile_signed_delta or 0) > 0
            else "negative"
        )
        values.append(
            "delta="
            f"{score.delta_profile_bin_low_tick}:{score.delta_profile_bin_high_tick}:{sign}"
        )
    return "+".join(values)


def _aoi_source_observed_at_ns(score: AoiScore, *, fallback_ns: int) -> int:
    return int(score.big_trade_burst_qualified_at_ns or fallback_ns)


def _frozen_aoi_bounds(candidate: AdaptiveFrozenAoi) -> tuple[int, int]:
    if candidate.aoi_low_tick is not None and candidate.aoi_high_tick is not None:
        return int(candidate.aoi_low_tick), int(candidate.aoi_high_tick)
    return _score_bounds(candidate.aoi)


def _adaptive_candidate(candidate: FrozenAoiCandidate) -> AdaptiveFrozenAoi:
    if not isinstance(candidate, AdaptiveFrozenAoi):
        raise TypeError("v03 requires an AdaptiveFrozenAoi")
    return candidate


def _adaptive_episode(episode: SweepEpisode) -> AdaptiveSweepEpisode:
    if not isinstance(episode, AdaptiveSweepEpisode):
        raise TypeError("v03 requires an AdaptiveSweepEpisode")
    return episode


def _adaptive_pending(signal: PendingSignal) -> AdaptivePendingSignal:
    if not isinstance(signal, AdaptivePendingSignal):
        raise TypeError("v03 requires an AdaptivePendingSignal")
    return signal


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-12)
    return actual == expected


__all__ = [
    "AdaptiveFrozenAoi",
    "AdaptiveOrderflowRangeV3Config",
    "AdaptiveOrderflowRangeV3EventStrategy",
    "AdaptiveOrderflowRangeV3State",
    "AdaptivePendingSignal",
    "AdaptiveSweepEpisode",
    "build_strategy",
]
