from __future__ import annotations

from dataclasses import replace
from datetime import date
from types import MappingProxyType, SimpleNamespace

import pandas as pd
import pytest

from alphaquest.backtest.event_replay import CanonicalEvent, EventEntryOrder, EventReplaySessionView
from alphaquest.data.databento_session_stream import RthSummary
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range_v3 import (
    AdaptiveFrozenAoi,
    AdaptiveOrderflowRangeV3Config,
    AdaptiveOrderflowRangeV3EventStrategy,
    AdaptiveOrderflowRangeV3State,
    AdaptivePendingSignal,
    AdaptiveSweepEpisode,
    DELTA_AGGREGATION_METHOD,
    _adaptive_ticks,
    _atr_stop_limit_ticks,
    _motivewave_delta_cells,
    _poc_reward_r,
    build_strategy,
)
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    AoiScore,
    Burst,
    CompletedBar,
    ProfileSnapshot,
    RegimeSnapshot,
)


def _view() -> EventReplaySessionView:
    return EventReplaySessionView(
        session_date=date(2026, 5, 14),
        contract_symbol="ESM26",
        metadata=MappingProxyType(
            {
                "previous_rth": RthSummary(date(2026, 5, 13), "ESM26", 107.0, 93.0, 101.0),
                "overnight_high": 106.0,
                "overnight_low": 94.0,
            }
        ),
        input_was_canonically_sorted=True,
    )


def _bar(index: int, *, close: int, low: int, high: int, atr_ticks: float = 20.0) -> CompletedBar:
    start = pd.Timestamp("2026-05-14 09:30:00", tz="America/New_York") + pd.Timedelta(minutes=3 * index)
    return CompletedBar(
        index=index,
        start_ns=int(start.value),
        end_ns=int((start + pd.Timedelta(minutes=3)).value),
        open_tick=close,
        high_tick=high,
        low_tick=low,
        close_tick=close,
        volume=1_000,
        delta=0,
        bin_volume={close: 1_000},
        bin_delta={close: 0},
        true_range_ticks=high - low,
        atr_ticks=atr_ticks,
    )


def _profile() -> ProfileSnapshot:
    return ProfileSnapshot(
        poc_bin=100,
        val_bin=95,
        vah_bin=105,
        poc_tick=400,
        val_tick=380,
        vah_tick=420,
        midpoint_tick=400,
        poc_volume=1_000,
        total_volume=10_000,
    )


def _regime() -> RegimeSnapshot:
    return RegimeSnapshot(
        label="no_directional_breakout_trend",
        overlap=0.8,
        poc_a_tick=400,
        poc_b_tick=400,
        midpoint_a_tick=400,
        midpoint_b_tick=400,
        efficiency=0.2,
        close_tick=410,
    )


def _event(timestamp: str, price_tick: int, event_index: int, *, side: str = "B") -> CanonicalEvent:
    observed = pd.Timestamp(timestamp, tz="America/New_York")
    return CanonicalEvent(
        event_index=event_index,
        timestamp=observed,
        timestamp_ns=int(observed.value),
        source_ordinal=event_index,
        price=price_tick * 0.25,
        price_tick=price_tick,
        size=1,
        side=side,
        signed_size=1 if side == "B" else -1,
    )


def _aoi(edge_tick: int = 420, *, burst_id: int = 1) -> AoiScore:
    return AoiScore(
        edge_tick=edge_tick,
        institutional_footprint_kind="adaptive_large_execution",
        market_level_point=False,
        big_trade_point=True,
        delta_profile_point=False,
        nearest_market_level_type=None,
        nearest_market_level_tick=None,
        big_trade_burst_id=burst_id,
        big_trade_burst_side="B",
        big_trade_burst_low_tick=edge_tick,
        big_trade_burst_high_tick=edge_tick,
        big_trade_burst_size=300,
    )


def _candidate(*, direction: str = "short", source_bar: int = 5) -> AdaptiveFrozenAoi:
    edge = 420 if direction == "short" else 380
    bar = _bar(source_bar, close=418 if direction == "short" else 382, low=378, high=422)
    return AdaptiveFrozenAoi(
        direction=direction,
        aoi=_aoi(edge),
        profile=_profile(),
        regime=_regime(),
        frozen_bar_index=bar.index,
        frozen_at_ns=bar.end_ns,
        aoi_id=f"rth:asof_bar={source_bar}:{direction}:{edge}:sources=burst=1",
        expires_at_ns=0,
        last_close_tick=bar.close_tick,
        sweep_distance_ticks=2,
        context_distance_ticks=4,
        profile_epoch="rth",
        aoi_low_tick=edge,
        aoi_high_tick=edge,
    )


def _episode(*, direction: str = "short") -> AdaptiveSweepEpisode:
    edge = 420 if direction == "short" else 380
    return AdaptiveSweepEpisode(
        episode_id=1,
        direction=direction,
        aoi=_aoi(edge),
        sweep_bar_index=6,
        sweep_bar_high_tick=423,
        sweep_bar_low_tick=377 if direction == "long" else 418,
        highest_tick_since_sweep=423,
        lowest_tick_since_sweep=377 if direction == "long" else 418,
        starting_profile=_profile(),
        starting_regime=_regime(),
        aoi_frozen_bar_index=5,
        aoi_frozen_at_ns=_bar(5, close=418, low=416, high=419).end_ns,
        aoi_id=f"rth:asof_bar=5:{direction}:{edge}:sources=burst=1",
        sweep_distance_ticks=2,
        context_distance_ticks=4,
        profile_epoch="rth",
    )


def test_v27_factory_keeps_reviewed_parameters_and_retires_confirmation_controls() -> None:
    strategy = build_strategy({})

    assert isinstance(strategy, AdaptiveOrderflowRangeV3EventStrategy)
    assert strategy.cfg.context_distance_atr_fraction == pytest.approx(1 / 3)
    assert strategy.cfg.delta_profile_price_bin_ticks == 4
    assert strategy.cfg.entry_offset_ticks == 2
    assert strategy.cfg.stop_offset_ticks == 2
    assert strategy.cfg.afternoon_profile_reset == "disabled"
    retired_values = {
        "failure_confirmation_bars": 3,
        "confirmation_delta_reference_percentile": 0.9,
        "confirmation_delta_lookback_sessions": 20,
        "confirmation_delta_context_path": "retired.parquet",
    }
    for retired, retired_value in retired_values.items():
        with pytest.raises(ValueError, match="unknown yush_adaptive_orderflow_range_v3 parameter"):
            build_strategy({retired: retired_value})


def test_v27_adaptive_distances_and_four_tick_delta_are_deterministic() -> None:
    config = AdaptiveOrderflowRangeV3Config()
    assert _adaptive_ticks(1 / 3, 20.0, floor=1) == 7
    assert _atr_stop_limit_ticks(config, 1.0) == config.minimum_stop_ticks
    assert _poc_reward_r(10, 5) == 2.0
    assert DELTA_AGGREGATION_METHOD == "motivewave_fixed_tick_interval_floor"
    assert _motivewave_delta_cells({420: -699, 421: -274, 422: -6, 423: 70}, 4) == {420: -909}


def test_v27_big_trade_or_four_tick_delta_can_build_either_edge_within_one_third_atr() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    now = int(pd.Timestamp("2026-05-14 10:00", tz="America/New_York").value)
    state.bursts.extend(
        [
            Burst(1, "A", 426, 426, 300, now - 2, now - 2, now - 1),
            Burst(2, "B", 374, 374, 300, now - 2, now - 2, now - 1),
        ]
    )
    state.profile_delta = {420: -900, 380: 900, 400: 100}

    short, _ = state._current_aoi_identity(
        "short", _profile(), as_of_ns=now, context_distance_ticks=7, source_bar_index=9
    )
    long, _ = state._current_aoi_identity(
        "long", _profile(), as_of_ns=now, context_distance_ticks=7, source_bar_index=9
    )

    assert short is not None and short.big_trade_point and short.delta_profile_point
    assert long is not None and long.big_trade_point and long.delta_profile_point


def test_v27_market_level_alone_cannot_build_an_aoi() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    now = int(pd.Timestamp("2026-05-14 10:00", tz="America/New_York").value)
    state.profile_delta = {}

    short, short_id = state._current_aoi_identity(
        "short", _profile(), as_of_ns=now, context_distance_ticks=4, source_bar_index=9
    )
    long, long_id = state._current_aoi_identity(
        "long", _profile(), as_of_ns=now, context_distance_ticks=4, source_bar_index=9
    )

    assert short is None and short_id is None
    assert long is None and long_id is None


def test_v27_builds_independent_vah_and_val_aois_for_each_new_bar() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.published_profile = _profile()
    state.published_regime = _regime()
    now = _bar(5, close=400, low=390, high=410).end_ns
    state.bursts.extend(
        [
            Burst(1, "B", 420, 420, 300, now - 2, now - 2, now - 1),
            Burst(2, "A", 380, 380, 300, now - 2, now - 2, now - 1),
        ]
    )

    state._advance_frozen_aois(_bar(5, close=400, low=390, high=410))
    first_short = state.frozen_aois["short"]
    first_long = state.frozen_aois["long"]
    state._advance_frozen_aois(_bar(6, close=400, low=390, high=410))
    second_short = state.frozen_aois["short"]
    second_long = state.frozen_aois["long"]

    assert isinstance(first_short, AdaptiveFrozenAoi)
    assert isinstance(first_long, AdaptiveFrozenAoi)
    assert isinstance(second_short, AdaptiveFrozenAoi)
    assert isinstance(second_long, AdaptiveFrozenAoi)
    assert first_short.aoi_id != second_short.aoi_id
    assert first_long.aoi_id != second_long.aoi_id
    assert "asof_bar=5" in first_short.aoi_id
    assert "asof_bar=6" in second_short.aoi_id
    assert first_short.aoi_id in state.retired_aoi_ids
    assert first_long.aoi_id in state.retired_aoi_ids


def test_v27_missing_confluence_removes_that_edge_aoi_at_next_boundary() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.published_profile = _profile()
    state.published_regime = _regime()
    state.frozen_aois["short"] = _candidate()
    state._current_aoi_identity = lambda *_args, **_kwargs: (None, None)  # type: ignore[method-assign]

    state._advance_frozen_aois(_bar(6, close=400, low=390, high=410))

    assert state.frozen_aois["short"] is None


def test_v27_ordered_inside_then_outside_events_are_required_for_a_sweep() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    candidate = _candidate()
    state.frozen_aois["short"] = candidate
    state.working_bar = SimpleNamespace(index=6)

    state._observe_event_crossings(CanonicalEvent(price_tick=423))
    assert candidate.sweep_observed_bar_index is None
    state._observe_event_crossings(CanonicalEvent(price_tick=420))
    state._observe_event_crossings(CanonicalEvent(price_tick=423))

    assert candidate.crossing_armed
    assert candidate.sweep_observed_bar_index == 6


def test_v27_completed_sweep_immediately_arms_zone_reclaim_without_confirmation() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    candidate = _candidate()
    candidate.crossing_armed = True
    candidate.sweep_observed_bar_index = 6
    candidate.sweep_event_high_tick = 423
    candidate.sweep_event_low_tick = 418
    state.last_event = _event("2026-05-14 09:50:59", 423, 10)

    state._detect_frozen_aoi_sweep(_bar(6, close=422, low=418, high=423), candidate)

    signal = state.pending.get("short_1")
    assert isinstance(signal, AdaptivePendingSignal)
    assert signal.entry_tick == 418
    assert signal.stop_tick == 0
    assert signal.resolved_stop_tick is None
    assert state.diagnostics["reclaims_without_separate_confirmation"] == 1
    assert state.diagnostics["entry_confirmations_big_trade"] == 0
    assert state.diagnostics["entry_confirmations_delta_profile"] == 0


def test_v27_pending_order_is_not_invalidated_by_a_pre_fill_intended_stop() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.last_event = _event("2026-05-14 09:50:59", 423, 10)
    signal = state._build_pending_signal(_episode(), _bar(6, close=422, low=418, high=423))
    assert isinstance(signal, AdaptivePendingSignal)
    state.pending[signal.order_id] = signal

    state._advance_pending_extremes(_event("2026-05-14 09:51:00", 450, 11))

    assert not signal.cancelled
    assert signal.highest_tick_since_sweep == 450
    assert signal.stop_tick == 0
    assert state.diagnostics["pre_fill_stop_invalidations"] == 0


def test_v27_stop_is_resolved_from_sweep_through_entry_event_and_then_risk_checked() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.last_event = _event("2026-05-14 09:50:59", 423, 10)
    signal = state._build_pending_signal(_episode(), _bar(6, close=422, low=418, high=423, atr_ticks=20))
    assert isinstance(signal, AdaptivePendingSignal)
    state.pending[signal.order_id] = signal
    entry_event = _event("2026-05-14 09:51:02", 418, 12)
    state._advance_pending_extremes(_event("2026-05-14 09:51:01", 430, 11))
    state._advance_pending_extremes(entry_event)

    assert state.signal_is_fillable(signal, entry_event)
    assert signal.resolved_stop_tick == 432
    assert signal.stop_resolution_event_index == 12
    assert signal.risk_ticks == 15


def test_v27_fill_gate_rejects_stop_that_exceeds_atr_bound() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.last_event = _event("2026-05-14 09:50:59", 423, 10)
    signal = state._build_pending_signal(_episode(), _bar(6, close=422, low=418, high=423, atr_ticks=4))
    assert isinstance(signal, AdaptivePendingSignal)
    state.pending[signal.order_id] = signal
    state._advance_pending_extremes(_event("2026-05-14 09:51:01", 450, 11))
    entry_event = _event("2026-05-14 09:51:02", 418, 12)
    state._advance_pending_extremes(entry_event)

    assert not state.signal_is_fillable(signal, entry_event)
    assert signal.resolved_stop_tick is None
    assert state.diagnostics["actual_fill_stop_distance_rejections"] == 1


def test_v27_midpoint_gate_includes_certified_adverse_entry_slippage() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.last_event = _event("2026-05-14 09:50:59", 423, 10)
    signal = state._build_pending_signal(_episode(), _bar(6, close=422, low=418, high=423, atr_ticks=20))
    assert isinstance(signal, AdaptivePendingSignal)
    state.pending[signal.order_id] = signal
    # At the 418 trigger, midpoint reward and structural risk would both be 18
    # ticks. The certified one-tick adverse short fill is 417, making reward 17
    # and risk 19, so the declared 1:1 gate must reject it.
    state._advance_pending_extremes(_event("2026-05-14 09:51:01", 434, 11))
    entry_event = _event("2026-05-14 09:51:02", 418, 12)
    state._advance_pending_extremes(entry_event)

    assert not state.signal_is_fillable(signal, entry_event)
    assert signal.resolved_stop_tick is None
    assert state.diagnostics["actual_fill_midpoint_reward_rejections"] == 1


def test_v27_strategy_submits_deferred_stop_and_returns_fill_time_resolution() -> None:
    strategy = AdaptiveOrderflowRangeV3EventStrategy()
    strategy.on_session_start(_view(), SimpleNamespace())
    state = strategy._state()
    state.last_event = _event("2026-05-14 09:50:59", 423, 10)
    signal = state._build_pending_signal(_episode(), _bar(6, close=422, low=418, high=423, atr_ticks=20))
    assert isinstance(signal, AdaptivePendingSignal)
    state.pending[signal.order_id] = signal

    submitted: list[dict] = []
    broker = SimpleNamespace(
        position=None,
        orders={},
        submit_or_replace_entry=lambda **kwargs: submitted.append(kwargs),
    )
    strategy.after_event(
        _event("2026-05-14 09:51:00", 423, 11),
        broker,
        closed_this_event=False,
        opened_this_event=False,
        entries_blocked=False,
    )

    assert submitted[0]["stop_tick"] is None
    fill_event = _event("2026-05-14 09:51:02", 418, 12)
    state._advance_pending_extremes(fill_event)
    assert state.signal_is_fillable(signal, fill_event)
    order = EventEntryOrder("short_1", "short", 418, None)
    assert strategy.entry_fill_stop_tick(order, fill_event, broker) == 425


def test_v27_afternoon_window_does_not_reset_profile_or_pending_setup() -> None:
    state = AdaptiveOrderflowRangeV3State(_view(), AdaptiveOrderflowRangeV3Config())
    state.profile_volume = {400: 100}
    state.profile_delta = {400: 25}
    state.pending["short_1"] = AdaptivePendingSignal(
        order_id="short_1",
        episode=_episode(),
        direction="short",
        entry_tick=418,
        stop_tick=0,
        target_1_tick=400,
        target_2_tick=380,
        risk_ticks=0,
        failure_bar_index=6,
        expiry_bar_index=6,
        failure_bar=_bar(6, close=422, low=418, high=423),
        failure_profile=_profile(),
        failure_regime=_regime(),
        highest_tick_since_sweep=423,
        lowest_tick_since_sweep=418,
    )

    state._expire_pending_after_bar(100)

    assert state.profile_volume == {400: 100}
    assert state.profile_delta == {400: 25}
    assert not state.pending["short_1"].cancelled
