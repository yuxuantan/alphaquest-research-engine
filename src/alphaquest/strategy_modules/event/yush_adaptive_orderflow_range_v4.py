"""V04 per-bar value-edge mechanics with post-sweep order-flow confirmation.

V04 preserves the certified V03 profile, ordered-sweep, stop-entry, fill-time
structural stop, and frozen scale-out mechanics.  It changes two entry-state
boundaries only:

* a prior-session, overnight, or opening-range market level may independently
  qualify a value-edge AOI when it lies inside the same causal one-third-ATR
  context window used by the order-flow sources; and
* completing an ordered sweep creates a waiting episode, not an entry order.
  A distinct large execution or a qualifying developing three-minute,
  four-tick delta imprint must be observed after the ordered sweep event before
  the reclaim stop order is armed.  The delta imprint covers the whole current
  three-minute bar and is compared with the absolute imprints of every
  four-tick cell from earlier completed RTH bars; it is never reset at the
  sweep.
  For shorts its labelled price must be strictly above the frozen AOI-zone
  bottom; for longs it must be strictly below the frozen AOI-zone top.

Exact event ordering prevents an observation at or before the sweep from being
reused as its confirmation. A later observation in the same bar is valid, but
the order still cannot exist before that sweep bar completes.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    EventEntryOrder,
    EventPositionView,
    EventReplayBroker,
    EventReplaySessionView,
)
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range_v3 import (
    AdaptiveFrozenAoi,
    AdaptiveOrderflowRangeV3Config,
    AdaptiveOrderflowRangeV3EventStrategy,
    AdaptiveOrderflowRangeV3State,
    AdaptivePendingSignal,
    AdaptiveSweepEpisode,
    BURST_DEFINITION,
    DELTA_AGGREGATION_METHOD,
    DELTA_PROFILE_DEFINITION,
    _adaptive_ticks,
    _atr_stop_limit_ticks,
    _motivewave_delta_cells,
    _poc_reward_r,
    _same_value,
    _timestamp_label,
)
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    AoiScore,
    Burst,
    CompletedBar,
    FrozenAoiCandidate,
    ProfileSnapshot,
    RegimeSnapshot,
    VALUE_AREA_METHOD_MOTIVEWAVE_STANDARD,
    _nearest_rank,
    _round_target_tick,
)


STRATEGY_ID = "yush_adaptive_orderflow_range_v4"
ENTRY_MODULE = STRATEGY_ID
STOP_MODULE = "event_fill_time_sweep_to_entry_extreme_stop"
TARGET_MODULE = "event_frozen_midpoint_two_ticks_outside_opposite_value_area_scale_out"
FINAL_TARGET_OUTSIDE_TICKS = 2
MARKET_LEVEL_DEFINITION = (
    "PDH, PDL, PDC, ONH, ONL, ORH, or ORL may independently qualify the latest "
    "VAH or VAL as an AOI when the level lies within one-third of causal ATR "
    "above or below that value edge"
)
POST_SWEEP_CONFIRMATION_DEFINITION = (
    "After the ordered sweep event, require a newly started and causally qualified "
    "q99.9 MotiveWave-compatible large execution or observe a sign-agnostic developing "
    "three-minute, four-tick delta imprint whose absolute value strictly exceeds the "
    "nearest-rank 90th percentile of all earlier completed three-minute, four-tick "
    "RTH imprints; the developing imprint begins at the bar boundary, not the sweep; "
    "the confirmation label must be strictly above the AOI-zone bottom for a "
    "short and strictly below the AOI-zone top for a long"
)


@dataclass(frozen=True)
class AdaptiveOrderflowRangeV4Config(AdaptiveOrderflowRangeV3Config):
    """Governed V04 defaults; V03 numeric assumptions remain frozen."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if not _same_value(self.context_distance_atr_fraction, 1.0 / 3.0):
            raise ValueError("fixed adaptive orderflow range v04 context distance drift")


_ACCEPTED_PARAMETERS = {item.name for item in fields(AdaptiveOrderflowRangeV4Config)} - {
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


def build_strategy(params: dict[str, Any]) -> "AdaptiveOrderflowRangeV4EventStrategy":
    unknown = sorted(set(params) - _ACCEPTED_PARAMETERS)
    if unknown:
        raise ValueError("unknown yush_adaptive_orderflow_range_v4 parameter(s): " + ", ".join(unknown))
    return AdaptiveOrderflowRangeV4EventStrategy(AdaptiveOrderflowRangeV4Config(**params))


@dataclass
class AdaptiveSweepEpisodeV4(AdaptiveSweepEpisode):
    sweep_observed_at_ns: int = 0
    sweep_observed_event_index: int = 0
    sweep_completed_at_ns: int = 0
    sweep_completed_event_index: int = 0
    last_burst_id_at_sweep: int = 0
    confirmation_kind: str | None = None
    confirmation_id: str | None = None
    confirmation_at_ns: int | None = None
    confirmation_event_index: int | None = None
    confirmation_price_tick: int | None = None
    confirmation_bin_low_tick: int | None = None
    confirmation_bin_high_tick: int | None = None
    confirmation_value: int | None = None
    confirmation_threshold: int | None = None
    confirmation_bar_index: int | None = None
    confirmation_bar_start_ns: int | None = None
    confirmation_bar_end_ns: int | None = None
    confirmation_reference_count: int | None = None


@dataclass
class AdaptiveFrozenAoiV4(AdaptiveFrozenAoi):
    sweep_observed_at_ns: int = 0
    sweep_observed_event_index: int = 0
    last_burst_id_at_sweep: int = 0
    confirmation_kind: str | None = None
    confirmation_id: str | None = None
    confirmation_at_ns: int | None = None
    confirmation_event_index: int | None = None
    confirmation_price_tick: int | None = None
    confirmation_bin_low_tick: int | None = None
    confirmation_bin_high_tick: int | None = None
    confirmation_value: int | None = None
    confirmation_threshold: int | None = None
    confirmation_bar_index: int | None = None
    confirmation_bar_start_ns: int | None = None
    confirmation_bar_end_ns: int | None = None
    confirmation_reference_count: int | None = None


class AdaptiveOrderflowRangeV4State(AdaptiveOrderflowRangeV3State):
    def __init__(
        self,
        session: EventReplaySessionView,
        config: AdaptiveOrderflowRangeV4Config,
    ) -> None:
        super().__init__(session, config)
        self.cfg = config
        self.completed_delta_imprints: list[int] = []
        self.diagnostics.update(
            {
                "sweeps_awaiting_separate_confirmation": 0,
                "confirmation_level_rejections": 0,
                "confirmation_before_or_at_sweep_rejections": 0,
                "completed_delta_imprint_observations": 0,
                "developing_delta_confirmation_evaluations": 0,
                "entry_confirmations_delta_imprint": 0,
            }
        )

    def ingest(self, event: CanonicalEvent) -> None:
        super().ingest(event)
        self._advance_waiting_episode_extremes(event)
        self._observe_big_trade_confirmations(event)

    def _observe_event_crossings(self, event: CanonicalEvent) -> None:
        before = {
            direction: candidate.sweep_observed_bar_index
            for direction, candidate in self.frozen_aois.items()
            if isinstance(candidate, AdaptiveFrozenAoiV4)
        }
        super()._observe_event_crossings(event)
        for direction, candidate in self.frozen_aois.items():
            if not isinstance(candidate, AdaptiveFrozenAoiV4):
                continue
            if before.get(direction) is None and candidate.sweep_observed_bar_index is not None:
                candidate.sweep_observed_at_ns = int(event.timestamp_ns)
                candidate.sweep_observed_event_index = int(event.event_index)
                candidate.last_burst_id_at_sweep = int(self.burst_counter)
            if candidate.sweep_observed_bar_index is None or candidate.confirmation_kind:
                continue
            self._stage_candidate_confirmation(candidate, event)

    def _publish_bar(self, bar: CompletedBar) -> None:
        super()._publish_bar(bar)
        completed_cells = _motivewave_delta_cells(bar.bin_delta, self.cfg.delta_profile_price_bin_ticks)
        self.completed_delta_imprints.extend(int(value) for value in completed_cells.values())
        self.diagnostics["completed_delta_imprint_observations"] = len(self.completed_delta_imprints)

    def _advance_waiting_episode_extremes(self, event: CanonicalEvent) -> None:
        price_tick = int(event.price_tick)
        for episode in self.episodes.values():
            if not isinstance(episode, AdaptiveSweepEpisodeV4) or episode.expired:
                continue
            episode.highest_tick_since_sweep = max(int(episode.highest_tick_since_sweep), price_tick)
            episode.lowest_tick_since_sweep = min(int(episode.lowest_tick_since_sweep), price_tick)

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
            self.frozen_aois[direction] = AdaptiveFrozenAoiV4(
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
                source_observed_at_ns=_aoi_source_observed_at_ns(current_aoi, fallback_ns=bar.end_ns),
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
            f"{direction}:{edge_tick}:sources={_aoi_source_fingerprint(score)}"
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
        base = super()._score_price(
            tick,
            profile,
            direction=direction,
            as_of_ns=as_of_ns,
            context_distance_ticks=context_distance_ticks,
        )
        nearby_levels = [
            (name, level)
            for name, level in self._market_levels()
            if abs(int(level) - int(tick)) <= context_distance_ticks
        ]
        nearest = min(nearby_levels, key=lambda item: (abs(item[1] - tick), item[0])) if nearby_levels else None
        source_names: list[str] = []
        if nearest is not None:
            source_names.append("market_level")
        if base.big_trade_point:
            source_names.append("adaptive_large_execution")
        if base.delta_profile_point:
            source_names.append("sign_agnostic_top_decile_delta")
        return AoiScore(
            edge_tick=base.edge_tick,
            institutional_footprint_kind=("_and_".join(source_names) if source_names else "none"),
            market_level_point=nearest is not None,
            big_trade_point=base.big_trade_point,
            delta_profile_point=base.delta_profile_point,
            nearest_market_level_type=None if nearest is None else nearest[0],
            nearest_market_level_tick=None if nearest is None else nearest[1],
            big_trade_burst_id=base.big_trade_burst_id,
            big_trade_burst_side=base.big_trade_burst_side,
            big_trade_burst_low_tick=base.big_trade_burst_low_tick,
            big_trade_burst_high_tick=base.big_trade_burst_high_tick,
            big_trade_burst_size=base.big_trade_burst_size,
            big_trade_burst_qualified_at_ns=base.big_trade_burst_qualified_at_ns,
            delta_profile_bin_low_tick=base.delta_profile_bin_low_tick,
            delta_profile_bin_high_tick=base.delta_profile_bin_high_tick,
            delta_profile_abs_delta=base.delta_profile_abs_delta,
            delta_profile_threshold=base.delta_profile_threshold,
            delta_profile_signed_delta=base.delta_profile_signed_delta,
        )

    def _stage_candidate_confirmation(
        self,
        candidate: AdaptiveFrozenAoiV4,
        event: CanonicalEvent,
    ) -> None:
        if int(event.event_index) <= candidate.sweep_observed_event_index:
            return
        newly_qualified = [
            burst
            for burst in self.bursts
            if int(burst.qualified_at_ns) == int(event.timestamp_ns)
            and burst.burst_id > candidate.last_burst_id_at_sweep
            and int(burst.started_at_ns) > candidate.sweep_observed_at_ns
        ]
        for burst in sorted(newly_qualified, key=lambda item: item.burst_id):
            level_tick = int(burst.price_low_tick) if candidate.direction == "short" else int(burst.price_high_tick)
            if not _confirmation_level_is_valid(candidate, level_tick):
                self.diagnostics["confirmation_level_rejections"] += 1
                continue
            _store_confirmation(
                candidate,
                kind="big_trade",
                confirmation_id=f"burst={burst.burst_id}",
                observed_at_ns=int(event.timestamp_ns),
                event_index=int(event.event_index),
                level_tick=level_tick,
                bin_low_tick=int(burst.price_low_tick),
                bin_high_tick=int(burst.price_high_tick),
                value=int(burst.size),
                threshold=int(self.big_trade_seed.threshold_volume),
            )
            return
        self._stage_developing_delta_confirmation(candidate, event)

    def _stage_developing_delta_confirmation(
        self,
        holder: AdaptiveFrozenAoiV4 | AdaptiveSweepEpisodeV4,
        event: CanonicalEvent,
    ) -> None:
        working = self.working_bar
        if working is None:
            return
        threshold = _nearest_rank(
            [abs(value) for value in self.completed_delta_imprints],
            self.cfg.delta_profile_percentile,
        )
        if threshold is None:
            return
        self.diagnostics["developing_delta_confirmation_evaluations"] += 1
        bar_cells = _motivewave_delta_cells(working.bin_delta, self.cfg.delta_profile_price_bin_ticks)
        candidates = [
            (
                int(low_tick),
                int(low_tick) + self.cfg.delta_profile_price_bin_ticks - 1,
                int(value),
            )
            for low_tick, value in bar_cells.items()
            if abs(int(value)) > int(threshold) and _confirmation_level_is_valid(holder, int(low_tick))
        ]
        if not candidates:
            if any(abs(int(value)) > int(threshold) for value in bar_cells.values()):
                self.diagnostics["confirmation_level_rejections"] += 1
            return
        selected = max(
            candidates,
            key=lambda item: (
                abs(item[2]),
                -abs(item[0] - holder.aoi.edge_tick),
                -item[0],
            ),
        )
        _store_confirmation(
            holder,
            kind="delta_imprint",
            confirmation_id=(f"bar={working.index}:event={event.event_index}:cell={selected[0]}"),
            observed_at_ns=int(event.timestamp_ns),
            event_index=int(event.event_index),
            level_tick=selected[0],
            bin_low_tick=selected[0],
            bin_high_tick=selected[1],
            value=selected[2],
            threshold=int(threshold),
            bar_index=int(working.index),
            bar_start_ns=int(working.start_ns),
            bar_end_ns=int(working.end_ns),
            reference_count=len(self.completed_delta_imprints),
        )

    def _detect_frozen_aoi_sweep(
        self,
        bar: CompletedBar,
        candidate: FrozenAoiCandidate,
    ) -> None:
        if not isinstance(candidate, AdaptiveFrozenAoiV4):
            raise TypeError("v04 requires an AdaptiveFrozenAoiV4")
        if not self._within_signal_window(bar.end_ns):
            return
        current = self.episodes[candidate.direction]
        if current is not None and not current.expired:
            return
        swept_in_bar = candidate.sweep_observed_bar_index == bar.index
        if not swept_in_bar:
            geometric_sweep = (
                bar.high_tick >= candidate.aoi.edge_tick + candidate.sweep_distance_ticks
                if candidate.direction == "short"
                else bar.low_tick <= candidate.aoi.edge_tick - candidate.sweep_distance_ticks
            )
            self.diagnostics["sweep_crossing_misses" if geometric_sweep else "qualified_aoi_without_sweep"] += 1
            return
        sweep_high_tick = max(bar.high_tick, int(candidate.sweep_event_high_tick or bar.high_tick))
        sweep_low_tick = min(bar.low_tick, int(candidate.sweep_event_low_tick or bar.low_tick))
        self.episode_counter += 1
        episode = AdaptiveSweepEpisodeV4(
            episode_id=self.episode_counter,
            direction=candidate.direction,
            aoi=candidate.aoi,
            sweep_bar_index=bar.index,
            sweep_bar_high_tick=sweep_high_tick,
            sweep_bar_low_tick=sweep_low_tick,
            highest_tick_since_sweep=sweep_high_tick,
            lowest_tick_since_sweep=sweep_low_tick,
            starting_profile=candidate.profile,
            starting_regime=candidate.regime,
            aoi_frozen_bar_index=candidate.frozen_bar_index,
            aoi_frozen_at_ns=candidate.frozen_at_ns,
            aoi_id=candidate.aoi_id,
            sweep_distance_ticks=candidate.sweep_distance_ticks,
            context_distance_ticks=candidate.context_distance_ticks,
            profile_epoch=candidate.profile_epoch,
            aoi_expires_at_ns=candidate.expires_at_ns,
            sweep_observed_at_ns=int(candidate.sweep_observed_at_ns),
            sweep_observed_event_index=int(candidate.sweep_observed_event_index),
            sweep_completed_at_ns=int(bar.end_ns),
            sweep_completed_event_index=int(self.last_event.event_index if self.last_event is not None else 0),
            last_burst_id_at_sweep=int(candidate.last_burst_id_at_sweep),
            confirmation_kind=candidate.confirmation_kind,
            confirmation_id=candidate.confirmation_id,
            confirmation_at_ns=candidate.confirmation_at_ns,
            confirmation_event_index=candidate.confirmation_event_index,
            confirmation_price_tick=candidate.confirmation_price_tick,
            confirmation_bin_low_tick=candidate.confirmation_bin_low_tick,
            confirmation_bin_high_tick=candidate.confirmation_bin_high_tick,
            confirmation_value=candidate.confirmation_value,
            confirmation_threshold=candidate.confirmation_threshold,
            confirmation_bar_index=candidate.confirmation_bar_index,
            confirmation_bar_start_ns=candidate.confirmation_bar_start_ns,
            confirmation_bar_end_ns=candidate.confirmation_bar_end_ns,
            confirmation_reference_count=candidate.confirmation_reference_count,
        )
        self.episodes[candidate.direction] = episode
        self.diagnostics["sweep_episodes"] += 1
        self.diagnostics["sweeps_awaiting_separate_confirmation"] += 1
        self._record_signal_lifecycle(
            episode,
            bar,
            event="sweep_waiting_confirmation",
            reason=(
                "completed_ordered_sweep_requires_later_big_trade_or_" "qualifying_developing_delta_imprint_observation"
            ),
            entry_window_open=True,
            observed_event_ns=bar.end_ns,
        )
        if episode.confirmation_kind is not None:
            self._activate_confirmed_episode(
                episode,
                kind=episode.confirmation_kind,
                confirmation_id=str(episode.confirmation_id),
                observed_at_ns=int(episode.confirmation_at_ns or 0),
                event_index=int(episode.confirmation_event_index or 0),
                level_tick=int(episode.confirmation_price_tick or 0),
                bin_low_tick=int(episode.confirmation_bin_low_tick or 0),
                bin_high_tick=int(episode.confirmation_bin_high_tick or 0),
                value=int(episode.confirmation_value or 0),
                threshold=int(episode.confirmation_threshold or 0),
                bar_index=episode.confirmation_bar_index,
                bar_start_ns=episode.confirmation_bar_start_ns,
                bar_end_ns=episode.confirmation_bar_end_ns,
                reference_count=episode.confirmation_reference_count,
            )

    def _observe_big_trade_confirmations(self, event: CanonicalEvent) -> None:
        newly_qualified = [burst for burst in self.bursts if int(burst.qualified_at_ns) == int(event.timestamp_ns)]
        for episode in tuple(self.episodes.values()):
            if not isinstance(episode, AdaptiveSweepEpisodeV4) or episode.expired:
                continue
            for burst in sorted(newly_qualified, key=lambda item: item.burst_id):
                if burst.burst_id <= episode.last_burst_id_at_sweep or (
                    int(burst.started_at_ns) <= episode.sweep_observed_at_ns
                ):
                    self.diagnostics["confirmation_before_or_at_sweep_rejections"] += 1
                    continue
                level_tick = int(burst.price_low_tick) if episode.direction == "short" else int(burst.price_high_tick)
                if not _confirmation_level_is_valid(episode, level_tick):
                    self.diagnostics["confirmation_level_rejections"] += 1
                    continue
                self._activate_confirmed_episode(
                    episode,
                    kind="big_trade",
                    confirmation_id=f"burst={burst.burst_id}",
                    observed_at_ns=int(event.timestamp_ns),
                    event_index=int(event.event_index),
                    level_tick=level_tick,
                    bin_low_tick=int(burst.price_low_tick),
                    bin_high_tick=int(burst.price_high_tick),
                    value=int(burst.size),
                    threshold=int(self.big_trade_seed.threshold_volume),
                )
                break
            if not episode.expired and episode.confirmation_kind is None:
                self._stage_developing_delta_confirmation(episode, event)
                if episode.confirmation_kind is not None:
                    self._activate_confirmed_episode(
                        episode,
                        kind=episode.confirmation_kind,
                        confirmation_id=str(episode.confirmation_id),
                        observed_at_ns=int(episode.confirmation_at_ns or 0),
                        event_index=int(episode.confirmation_event_index or 0),
                        level_tick=int(episode.confirmation_price_tick or 0),
                        bin_low_tick=int(episode.confirmation_bin_low_tick or 0),
                        bin_high_tick=int(episode.confirmation_bin_high_tick or 0),
                        value=int(episode.confirmation_value or 0),
                        threshold=int(episode.confirmation_threshold or 0),
                        bar_index=episode.confirmation_bar_index,
                        bar_start_ns=episode.confirmation_bar_start_ns,
                        bar_end_ns=episode.confirmation_bar_end_ns,
                        reference_count=episode.confirmation_reference_count,
                    )

    def _activate_confirmed_episode(
        self,
        episode: AdaptiveSweepEpisodeV4,
        *,
        kind: str,
        confirmation_id: str,
        observed_at_ns: int,
        event_index: int,
        level_tick: int,
        bin_low_tick: int,
        bin_high_tick: int,
        value: int,
        threshold: int,
        bar_index: int | None = None,
        bar_start_ns: int | None = None,
        bar_end_ns: int | None = None,
        reference_count: int | None = None,
    ) -> None:
        if episode.expired:
            return
        if event_index <= episode.sweep_observed_event_index or (observed_at_ns <= episode.sweep_observed_at_ns):
            self.diagnostics["confirmation_before_or_at_sweep_rejections"] += 1
            return
        if not self._within_signal_window(observed_at_ns):
            self.diagnostics["reclaims_outside_entry_window"] += 1
            return
        episode.confirmation_kind = kind
        episode.confirmation_id = confirmation_id
        episode.confirmation_at_ns = observed_at_ns
        episode.confirmation_event_index = event_index
        episode.confirmation_price_tick = level_tick
        episode.confirmation_bin_low_tick = bin_low_tick
        episode.confirmation_bin_high_tick = bin_high_tick
        episode.confirmation_value = value
        episode.confirmation_threshold = threshold
        episode.confirmation_bar_index = bar_index
        episode.confirmation_bar_start_ns = bar_start_ns
        episode.confirmation_bar_end_ns = bar_end_ns
        episode.confirmation_reference_count = reference_count
        decision_bar = self.completed_bars[-1]
        signal = self._build_pending_signal(episode, decision_bar)
        episode.expired = True
        episode.failure_bar_index = decision_bar.index
        self._retire_episode(episode)
        if signal is None:
            return
        activation_timestamp_ns = max(
            observed_at_ns,
            int(self.last_event.timestamp_ns if self.last_event is not None else observed_at_ns),
        )
        activation_event_index = max(
            event_index,
            int(self.last_event.event_index if self.last_event is not None else event_index),
        )
        signal.activation_timestamp_ns = activation_timestamp_ns
        signal.activation_event_index = activation_event_index
        signal.entry_decision_event_index = activation_event_index
        self.pending[signal.order_id] = signal
        self.diagnostics["signals_created"] += 1
        self.diagnostics[f"entry_confirmations_{kind}"] += 1
        for source_kind in _aoi_source_kinds(episode.aoi):
            self.diagnostics[f"signals_from_{source_kind}_aoi"] += 1
        self._record_signal_lifecycle(
            episode,
            decision_bar,
            event="signal_created",
            reason=f"separate_post_sweep_{kind}_confirmation_armed_stop_entry",
            entry_window_open=True,
            observed_event_ns=observed_at_ns,
        )
        self.action_due = True

    def _build_pending_signal(
        self,
        episode: AdaptiveSweepEpisode,
        bar: CompletedBar,
    ) -> AdaptivePendingSignal | None:
        signal = super()._build_pending_signal(episode, bar)
        if signal is None:
            return None
        zone_low, zone_high = _score_bounds(episode.aoi)
        boundary = zone_low if episode.direction == "short" else zone_high
        entry_tick = (
            boundary - self.cfg.entry_offset_ticks
            if episode.direction == "short"
            else boundary + self.cfg.entry_offset_ticks
        )
        signal.aoi_zone_low_tick = zone_low
        signal.aoi_zone_high_tick = zone_high
        signal.entry_zone_boundary_tick = boundary
        signal.entry_tick = entry_tick
        signal.planned_fill_tick = entry_tick
        signal.target_2_tick = (
            episode.starting_profile.val_tick - FINAL_TARGET_OUTSIDE_TICKS
            if episode.direction == "short"
            else episode.starting_profile.vah_tick + FINAL_TARGET_OUTSIDE_TICKS
        )
        return signal

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
        typed = episode if isinstance(episode, AdaptiveSweepEpisodeV4) else None
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
                "aoi_id": getattr(episode, "aoi_id", ""),
                "decision_bar_end": _timestamp_label(bar.end_ns),
                "order_activation_at": (
                    None
                    if typed is None or typed.confirmation_at_ns is None
                    else _timestamp_label(typed.confirmation_at_ns)
                ),
                "next_observed_event": (None if next_event_ns is None else _timestamp_label(next_event_ns)),
                "entry_window_open": entry_window_open,
                "risk_ticks": risk_ticks,
                "maximum_stop_ticks": maximum_stop_ticks,
                "midpoint_reward_r": poc_reward_r,
                "confirmation_kind": None if typed is None else typed.confirmation_kind,
                "confirmation_id": None if typed is None else typed.confirmation_id,
                "confirmation_at": (
                    None
                    if typed is None or typed.confirmation_at_ns is None
                    else _timestamp_label(typed.confirmation_at_ns)
                ),
                "confirmation_price": (
                    None
                    if typed is None or typed.confirmation_price_tick is None
                    else typed.confirmation_price_tick * self.cfg.tick_size
                ),
                "confirmation_value": None if typed is None else typed.confirmation_value,
                "confirmation_threshold": (None if typed is None else typed.confirmation_threshold),
                "confirmation_bar_index": (None if typed is None else typed.confirmation_bar_index),
                "confirmation_bar_start": (
                    None
                    if typed is None or typed.confirmation_bar_start_ns is None
                    else _timestamp_label(typed.confirmation_bar_start_ns)
                ),
                "confirmation_bar_end": (
                    None
                    if typed is None or typed.confirmation_bar_end_ns is None
                    else _timestamp_label(typed.confirmation_bar_end_ns)
                ),
                "confirmation_reference_count": (None if typed is None else typed.confirmation_reference_count),
            }
        )


class AdaptiveOrderflowRangeV4EventStrategy(AdaptiveOrderflowRangeV3EventStrategy):
    def __init__(self, config: AdaptiveOrderflowRangeV4Config | None = None) -> None:
        self.cfg = config or AdaptiveOrderflowRangeV4Config()
        self.state: AdaptiveOrderflowRangeV4State | None = None

    def on_session_start(
        self,
        session: EventReplaySessionView,
        broker: EventReplayBroker,
    ) -> None:
        del broker
        self.state = AdaptiveOrderflowRangeV4State(session, self.cfg)

    def on_entry_filled(
        self,
        order: EventEntryOrder,
        position: EventPositionView,
        event: CanonicalEvent,
        broker: EventReplayBroker,
    ) -> None:
        signal = self._state().pending.get(order.order_id)
        if not isinstance(signal, AdaptivePendingSignal) or not isinstance(signal.episode, AdaptiveSweepEpisodeV4):
            raise AssertionError("v04 fill has no confirmed adaptive pending signal")
        episode = signal.episode
        super().on_entry_filled(order, position, event, broker)
        broker.annotate_position(
            setup_model="per_bar_orderflow_value_edge_sweep_confirmed_reclaim",
            aoi_source_kinds=",".join(_aoi_source_kinds(episode.aoi)),
            market_level_qualified=episode.aoi.market_level_point,
            entry_confirmation_kind=episode.confirmation_kind,
            entry_confirmation_id=episode.confirmation_id,
            entry_confirmation_at=(
                None if episode.confirmation_at_ns is None else _timestamp_label(episode.confirmation_at_ns)
            ),
            entry_confirmation_price=(
                None
                if episode.confirmation_price_tick is None
                else episode.confirmation_price_tick * self.cfg.tick_size
            ),
            entry_confirmation_bin_low_price=(
                None
                if episode.confirmation_bin_low_tick is None
                else episode.confirmation_bin_low_tick * self.cfg.tick_size
            ),
            entry_confirmation_bin_high_price=(
                None
                if episode.confirmation_bin_high_tick is None
                else episode.confirmation_bin_high_tick * self.cfg.tick_size
            ),
            entry_confirmation_value=episode.confirmation_value,
            entry_confirmation_threshold=episode.confirmation_threshold,
            entry_confirmation_bar_index=episode.confirmation_bar_index,
            entry_confirmation_bar_start=(
                None
                if episode.confirmation_bar_start_ns is None
                else _timestamp_label(episode.confirmation_bar_start_ns)
            ),
            entry_confirmation_bar_end=(
                None if episode.confirmation_bar_end_ns is None else _timestamp_label(episode.confirmation_bar_end_ns)
            ),
            entry_confirmation_reference_count=episode.confirmation_reference_count,
            entry_confirmation_percentile_method="nearest_rank",
            entry_confirmation_comparison="strict_absolute_greater_than",
            market_level_definition=MARKET_LEVEL_DEFINITION,
            failure_confirmation_rule=POST_SWEEP_CONFIRMATION_DEFINITION,
            burst_direction_rule=(
                "AOI and confirmation big-trade aggressor sides are unrestricted; "
                "the confirmation must be a distinct sequence started after the sweep"
            ),
            entry_trigger_rule=(
                "Only after a separate post-sweep big-trade or developing three-minute "
                "four-tick delta-imprint confirmation, "
                "arm a stop-market entry two ticks beyond the reclaim-side AOI-zone "
                "boundary; short uses zone low minus two ticks and long uses zone "
                "high plus two ticks"
            ),
            footprint_definition=(
                "AOI context is the latest value edge plus any nearby PDH, PDL, PDC, "
                "ONH, ONL, ORH, ORL, q99.9 large execution, or sign-agnostic top-decile "
                "absolute four-tick delta cell within one-third ATR"
            ),
            burst_definition=BURST_DEFINITION,
            delta_profile_definition=DELTA_PROFILE_DEFINITION,
            delta_aggregation_method=DELTA_AGGREGATION_METHOD,
            target_2_definition=("frozen_opposite_value_area_edge_plus_two_ticks_outside"),
            final_target_outside_ticks=FINAL_TARGET_OUTSIDE_TICKS,
            profile_snapshot_timing=(
                "One RTH profile accumulates continuously from 09:30; VAH and VAL "
                "AOIs are rebuilt at each completed three-minute boundary; exact "
                "event ordering permits a later same-bar confirmation from the whole "
                "developing bar imprint but never submits its stop entry before the "
                "sweep bar completes; completed-bar imprint history excludes the "
                "currently developing bar"
            ),
        )

    def _state(self) -> AdaptiveOrderflowRangeV4State:
        if self.state is None:
            raise RuntimeError("Adaptive orderflow range v04 has not started")
        return self.state


def _confirmation_level_is_valid(
    episode: AdaptiveFrozenAoiV4 | AdaptiveSweepEpisodeV4,
    level_tick: int,
) -> bool:
    zone_low, zone_high = _score_bounds(episode.aoi)
    return int(level_tick) > zone_low if episode.direction == "short" else int(level_tick) < zone_high


def _store_confirmation(
    holder: AdaptiveFrozenAoiV4 | AdaptiveSweepEpisodeV4,
    *,
    kind: str,
    confirmation_id: str,
    observed_at_ns: int,
    event_index: int,
    level_tick: int,
    bin_low_tick: int,
    bin_high_tick: int,
    value: int,
    threshold: int,
    bar_index: int | None = None,
    bar_start_ns: int | None = None,
    bar_end_ns: int | None = None,
    reference_count: int | None = None,
) -> None:
    holder.confirmation_kind = kind
    holder.confirmation_id = confirmation_id
    holder.confirmation_at_ns = observed_at_ns
    holder.confirmation_event_index = event_index
    holder.confirmation_price_tick = level_tick
    holder.confirmation_bin_low_tick = bin_low_tick
    holder.confirmation_bin_high_tick = bin_high_tick
    holder.confirmation_value = value
    holder.confirmation_threshold = threshold
    holder.confirmation_bar_index = bar_index
    holder.confirmation_bar_start_ns = bar_start_ns
    holder.confirmation_bar_end_ns = bar_end_ns
    holder.confirmation_reference_count = reference_count


def _score_bounds(score: AoiScore) -> tuple[int, int]:
    lows = [int(score.edge_tick)]
    highs = [int(score.edge_tick)]
    if score.market_level_point and score.nearest_market_level_tick is not None:
        lows.append(int(score.nearest_market_level_tick))
        highs.append(int(score.nearest_market_level_tick))
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
    if score.market_level_point:
        values.append("market_level")
    if score.big_trade_point:
        values.append("big_trade")
    if score.delta_profile_point:
        values.append("delta_profile")
    return tuple(values)


def _aoi_source_fingerprint(score: AoiScore) -> str:
    values: list[str] = []
    if score.market_level_point:
        values.append(f"market={score.nearest_market_level_type}:{score.nearest_market_level_tick}")
    if score.big_trade_point:
        values.append(f"burst={score.big_trade_burst_id or 0}")
    if score.delta_profile_point:
        sign = "positive" if int(score.delta_profile_signed_delta or 0) > 0 else "negative"
        values.append("delta=" f"{score.delta_profile_bin_low_tick}:{score.delta_profile_bin_high_tick}:{sign}")
    return "+".join(values)


def _aoi_source_observed_at_ns(score: AoiScore, *, fallback_ns: int) -> int:
    return int(score.big_trade_burst_qualified_at_ns or fallback_ns)


__all__ = [
    "AdaptiveFrozenAoiV4",
    "AdaptiveOrderflowRangeV4Config",
    "AdaptiveOrderflowRangeV4EventStrategy",
    "AdaptiveOrderflowRangeV4State",
    "AdaptiveSweepEpisodeV4",
    "build_strategy",
]
