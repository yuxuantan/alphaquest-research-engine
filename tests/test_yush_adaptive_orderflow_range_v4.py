from __future__ import annotations

from datetime import date
from types import MappingProxyType

import pandas as pd

from alphaquest.backtest.event_replay import CanonicalEvent, EventReplaySessionView
from alphaquest.data.databento_session_stream import RthSummary
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range_v3 import AdaptivePendingSignal
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range_v4 import (
    AdaptiveFrozenAoiV4,
    AdaptiveOrderflowRangeV4Config,
    AdaptiveOrderflowRangeV4EventStrategy,
    AdaptiveOrderflowRangeV4State,
    AdaptiveSweepEpisodeV4,
    _confirmation_level_is_valid,
    build_strategy,
)
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    AoiScore,
    Burst,
    CompletedBar,
    ProfileSnapshot,
    RegimeSnapshot,
    WorkingBar,
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


def _bar(
    index: int,
    *,
    close: int,
    low: int,
    high: int,
    delta_cells: dict[int, int] | None = None,
) -> CompletedBar:
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
        delta=sum((delta_cells or {}).values()),
        bin_volume={close: 1_000},
        bin_delta=delta_cells or {close: 0},
        true_range_ticks=high - low,
        atr_ticks=20.0,
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


def _event(timestamp: str, price_tick: int, event_index: int) -> CanonicalEvent:
    observed = pd.Timestamp(timestamp, tz="America/New_York")
    return CanonicalEvent(
        event_index=event_index,
        timestamp=observed,
        timestamp_ns=int(observed.value),
        source_ordinal=event_index,
        price=price_tick * 0.25,
        price_tick=price_tick,
        size=1,
        side="B",
        signed_size=1,
    )


def _market_aoi(direction: str) -> AoiScore:
    edge = 420 if direction == "short" else 380
    market = 418 if direction == "short" else 382
    return AoiScore(
        edge_tick=edge,
        institutional_footprint_kind="market_level",
        market_level_point=True,
        big_trade_point=False,
        delta_profile_point=False,
        nearest_market_level_type="PDC",
        nearest_market_level_tick=market,
        big_trade_burst_id=None,
    )


def _episode(direction: str = "short") -> AdaptiveSweepEpisodeV4:
    sweep_bar = _bar(6, close=420, low=377, high=423)
    return AdaptiveSweepEpisodeV4(
        episode_id=1,
        direction=direction,
        aoi=_market_aoi(direction),
        sweep_bar_index=6,
        sweep_bar_high_tick=423,
        sweep_bar_low_tick=377,
        highest_tick_since_sweep=423,
        lowest_tick_since_sweep=377,
        starting_profile=_profile(),
        starting_regime=_regime(),
        aoi_frozen_bar_index=5,
        aoi_frozen_at_ns=_bar(5, close=400, low=390, high=410).end_ns,
        aoi_id=f"rth:asof_bar=5:{direction}:market",
        sweep_distance_ticks=2,
        context_distance_ticks=7,
        profile_epoch="rth",
        sweep_observed_at_ns=int(pd.Timestamp("2026-05-14 09:50:30", tz="America/New_York").value),
        sweep_observed_event_index=9,
        sweep_completed_at_ns=sweep_bar.end_ns,
        sweep_completed_event_index=10,
        last_burst_id_at_sweep=1,
    )


def test_v04_factory_preserves_v03_defaults_under_a_new_strategy_identity() -> None:
    strategy = build_strategy({})

    assert isinstance(strategy, AdaptiveOrderflowRangeV4EventStrategy)
    assert isinstance(strategy.cfg, AdaptiveOrderflowRangeV4Config)
    assert strategy.cfg.entry_offset_ticks == 2
    assert strategy.cfg.context_distance_atr_fraction == 1 / 3


def test_v04_market_level_alone_can_form_each_value_edge_aoi() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    state.profile_delta = {}
    now = int(pd.Timestamp("2026-05-14 10:00", tz="America/New_York").value)

    short, short_id = state._current_aoi_identity(
        "short", _profile(), as_of_ns=now, context_distance_ticks=4, source_bar_index=9
    )
    long, long_id = state._current_aoi_identity(
        "long", _profile(), as_of_ns=now, context_distance_ticks=4, source_bar_index=9
    )

    assert short is not None and short.market_level_point
    assert long is not None and long.market_level_point
    assert short_id is not None and "market=" in short_id
    assert long_id is not None and "market=" in long_id


def test_v04_completed_sweep_waits_without_creating_an_entry_signal() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    bar = _bar(6, close=422, low=418, high=423)
    candidate = AdaptiveFrozenAoiV4(
        direction="short",
        aoi=_market_aoi("short"),
        profile=_profile(),
        regime=_regime(),
        frozen_bar_index=5,
        frozen_at_ns=_bar(5, close=400, low=390, high=410).end_ns,
        aoi_id="short-market-aoi",
        sweep_distance_ticks=2,
        context_distance_ticks=7,
        profile_epoch="rth",
        crossing_armed=True,
        sweep_observed_bar_index=6,
        sweep_event_high_tick=423,
        sweep_event_low_tick=418,
        aoi_low_tick=418,
        aoi_high_tick=420,
        sweep_observed_at_ns=int(pd.Timestamp("2026-05-14 09:50:30", tz="America/New_York").value),
        sweep_observed_event_index=9,
        last_burst_id_at_sweep=1,
    )
    state.last_event = _event("2026-05-14 09:51:00", 423, 10)

    state._detect_frozen_aoi_sweep(bar, candidate)

    assert state.pending == {}
    assert isinstance(state.episodes["short"], AdaptiveSweepEpisodeV4)
    assert state.diagnostics["sweeps_awaiting_separate_confirmation"] == 1
    assert state.diagnostics["reclaims_without_separate_confirmation"] == 0


def test_v04_confirmation_level_is_strictly_inside_reclaim_side_zone_boundary() -> None:
    short = _episode("short")
    long = _episode("long")

    assert not _confirmation_level_is_valid(short, 418)
    assert _confirmation_level_is_valid(short, 419)
    assert not _confirmation_level_is_valid(long, 382)
    assert _confirmation_level_is_valid(long, 381)


def test_v04_separate_confirmation_later_in_sweep_bar_is_staged_until_bar_completion() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    sweep_at = pd.Timestamp("2026-05-14 09:50:20", tz="America/New_York")
    confirm_event = _event("2026-05-14 09:50:40", 419, 12)
    candidate = AdaptiveFrozenAoiV4(
        direction="short",
        aoi=_market_aoi("short"),
        profile=_profile(),
        regime=_regime(),
        frozen_bar_index=5,
        frozen_at_ns=_bar(5, close=400, low=390, high=410).end_ns,
        aoi_id="short-market-aoi",
        sweep_distance_ticks=2,
        context_distance_ticks=7,
        profile_epoch="rth",
        crossing_armed=True,
        sweep_observed_bar_index=6,
        sweep_event_high_tick=423,
        sweep_event_low_tick=418,
        aoi_low_tick=418,
        aoi_high_tick=420,
        sweep_observed_at_ns=int(sweep_at.value),
        sweep_observed_event_index=10,
        last_burst_id_at_sweep=1,
    )
    state.bursts.append(
        Burst(
            2,
            "B",
            419,
            419,
            600,
            int((sweep_at + pd.Timedelta(seconds=1)).value),
            int((sweep_at + pd.Timedelta(seconds=2)).value),
            confirm_event.timestamp_ns,
        )
    )

    state._stage_candidate_confirmation(candidate, confirm_event)
    assert candidate.confirmation_kind == "big_trade"
    assert state.pending == {}

    state.completed_bars.append(_bar(6, close=422, low=418, high=423))
    state.last_event = _event("2026-05-14 09:51:00", 422, 20)
    state._detect_frozen_aoi_sweep(_bar(6, close=422, low=418, high=423), candidate)

    signal = state.pending.get("short_1")
    assert isinstance(signal, AdaptivePendingSignal)
    assert signal.activation_event_index == 20
    assert candidate.confirmation_event_index == 12


def test_v04_new_big_trade_after_sweep_arms_signal_but_equal_boundary_does_not() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    episode = _episode("short")
    state.episodes["short"] = episode
    state.completed_bars.append(_bar(6, close=422, low=418, high=423))
    confirmation_event = _event("2026-05-14 09:51:02", 419, 12)
    boundary_burst = Burst(
        2,
        "B",
        418,
        418,
        500,
        int(pd.Timestamp("2026-05-14 09:51:01", tz="America/New_York").value),
        int(pd.Timestamp("2026-05-14 09:51:01", tz="America/New_York").value),
        confirmation_event.timestamp_ns,
    )
    state.bursts.append(boundary_burst)
    state._observe_big_trade_confirmations(confirmation_event)
    assert state.pending == {}

    valid_event = _event("2026-05-14 09:51:04", 419, 14)
    state.bursts.append(
        Burst(
            3,
            "A",
            419,
            419,
            600,
            int(pd.Timestamp("2026-05-14 09:51:03", tz="America/New_York").value),
            int(pd.Timestamp("2026-05-14 09:51:03", tz="America/New_York").value),
            valid_event.timestamp_ns,
        )
    )
    state._observe_big_trade_confirmations(valid_event)

    signal = state.pending.get("short_1")
    assert isinstance(signal, AdaptivePendingSignal)
    assert signal.entry_tick == 416
    assert signal.target_2_tick == 378
    assert signal.activation_event_index == 14
    assert episode.confirmation_kind == "big_trade"
    assert state.diagnostics["entry_confirmations_big_trade"] == 1


def _working_bar(
    index: int,
    *,
    close: int,
    low: int,
    high: int,
    delta_cells: dict[int, int],
) -> WorkingBar:
    completed = _bar(
        index,
        close=close,
        low=low,
        high=high,
        delta_cells=delta_cells,
    )
    return WorkingBar(
        index=completed.index,
        start_ns=completed.start_ns,
        end_ns=completed.end_ns,
        open_tick=completed.open_tick,
        high_tick=completed.high_tick,
        low_tick=completed.low_tick,
        close_tick=completed.close_tick,
        volume=completed.volume,
        delta=completed.delta,
        bin_volume=dict(completed.bin_volume),
        bin_delta=dict(completed.bin_delta),
    )


def test_v04_developing_bar_delta_uses_completed_bar_cell_imprints_only() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    episode = _episode("long")
    state.episodes["long"] = episode
    state.completed_bars.append(_bar(6, close=378, low=377, high=382))
    state.completed_delta_imprints = list(range(1, 11))
    state.working_bar = _working_bar(
        7,
        close=380,
        low=379,
        high=383,
        delta_cells={380: -10},
    )
    state.last_event = _event("2026-05-14 09:51:02", 380, 20)

    state._observe_big_trade_confirmations(state.last_event)

    signal = state.pending.get("long_1")
    assert isinstance(signal, AdaptivePendingSignal)
    assert signal.entry_tick == 384
    assert signal.target_2_tick == 422
    assert episode.confirmation_kind == "delta_imprint"
    assert episode.confirmation_price_tick == 380
    assert episode.confirmation_value == -10
    assert episode.confirmation_threshold == 9
    assert episode.confirmation_id == "bar=7:event=20:cell=380"
    assert episode.confirmation_bar_index == 7
    assert episode.confirmation_reference_count == 10
    assert state.diagnostics["entry_confirmations_delta_imprint"] == 1


def test_v04_delta_confirmation_is_strictly_greater_than_nearest_rank_threshold() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    episode = _episode("long")
    state.episodes["long"] = episode
    state.completed_bars.append(_bar(6, close=378, low=377, high=382))
    state.completed_delta_imprints = list(range(1, 11))
    state.working_bar = _working_bar(
        7,
        close=380,
        low=379,
        high=383,
        delta_cells={380: -9},
    )
    equal_event = _event("2026-05-14 09:51:02", 380, 20)
    state.last_event = equal_event

    state._observe_big_trade_confirmations(equal_event)

    assert state.pending == {}
    assert episode.confirmation_kind is None

    state.working_bar.bin_delta[380] = -10
    state.working_bar.delta = -10
    greater_event = _event("2026-05-14 09:51:03", 380, 21)
    state.last_event = greater_event
    state._observe_big_trade_confirmations(greater_event)

    assert isinstance(state.pending.get("long_1"), AdaptivePendingSignal)
    assert episode.confirmation_value == -10
    assert episode.confirmation_threshold == 9


def test_v04_delta_confirmation_uses_whole_developing_bar_not_post_sweep_delta() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    episode = _episode("short")
    state.episodes["short"] = episode
    state.completed_bars.append(_bar(6, close=422, low=418, high=423))
    state.completed_delta_imprints = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110]
    state.working_bar = _working_bar(
        7,
        close=424,
        low=419,
        high=425,
        delta_cells={424: 120},
    )
    # Only one contract is observed after the sweep, but the whole developing
    # bar imprint is already 120 and strictly exceeds q90=100.
    confirmation_event = _event("2026-05-14 09:51:02", 424, 20)
    state.last_event = confirmation_event

    state._observe_big_trade_confirmations(confirmation_event)

    assert isinstance(state.pending.get("short_1"), AdaptivePendingSignal)
    assert episode.confirmation_value == 120
    assert episode.confirmation_threshold == 100


def test_v04_developing_delta_cannot_confirm_on_the_ordered_sweep_event() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    sweep_event = _event("2026-05-14 09:50:30", 424, 20)
    candidate = AdaptiveFrozenAoiV4(
        direction="short",
        aoi=_market_aoi("short"),
        profile=_profile(),
        regime=_regime(),
        frozen_bar_index=5,
        frozen_at_ns=_bar(5, close=400, low=390, high=410).end_ns,
        aoi_id="short-market-aoi",
        sweep_distance_ticks=2,
        context_distance_ticks=7,
        profile_epoch="rth",
        crossing_armed=True,
        sweep_observed_bar_index=6,
        sweep_event_high_tick=424,
        sweep_event_low_tick=418,
        aoi_low_tick=418,
        aoi_high_tick=420,
        sweep_observed_at_ns=sweep_event.timestamp_ns,
        sweep_observed_event_index=sweep_event.event_index,
        last_burst_id_at_sweep=1,
    )
    state.completed_delta_imprints = list(range(1, 11))
    state.working_bar = _working_bar(
        6,
        close=424,
        low=418,
        high=424,
        delta_cells={424: 10},
    )

    state._stage_candidate_confirmation(candidate, sweep_event)
    assert candidate.confirmation_kind is None

    later_event = _event("2026-05-14 09:50:31", 424, 21)
    state._stage_candidate_confirmation(candidate, later_event)

    assert candidate.confirmation_kind == "delta_imprint"
    assert candidate.confirmation_event_index == 21
    assert candidate.confirmation_value == 10
    assert candidate.confirmation_threshold == 9


def test_v04_completed_bar_cells_are_retained_as_separate_reference_observations() -> None:
    state = AdaptiveOrderflowRangeV4State(_view(), AdaptiveOrderflowRangeV4Config())
    first = _bar(
        0,
        close=384,
        low=380,
        high=387,
        delta_cells={380: 10, 381: -5, 384: 7},
    )
    second = _bar(
        1,
        close=384,
        low=380,
        high=387,
        delta_cells={380: -3, 382: -4, 384: 9},
    )

    state._publish_bar(first)
    state._publish_bar(second)

    # The 380-383 cell appears once per completed bar: +5, then -7.  The
    # 384-387 cell likewise contributes +7 and +9 as distinct observations.
    assert state.completed_delta_imprints == [5, 7, -7, 9]
    assert state.diagnostics["completed_delta_imprint_observations"] == 4
