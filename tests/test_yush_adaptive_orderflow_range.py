from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from alphaquest.backtest.event_replay import EventReplaySessionView
from alphaquest.data.databento_session_stream import RthSummary
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range import (
    AdaptiveAtrSeed,
    YushAdaptiveOrderflowRangeConfig,
    YushAdaptiveOrderflowRangeEventStrategy,
    _AdaptiveOrderflowRangeState,
    _atr_seed_for_session,
    _big_trade_seed_for_session,
    _frozen_target_tick,
    build_strategy,
)
from alphaquest.strategy_modules.event.yush_orderflow_primitives import (
    AoiCandidate,
    AoiLineage,
    ConfluencePoint,
    PendingOrder,
    Visit,
)


def _context(tmp_path):
    path = tmp_path / "atr.parquet"
    pd.DataFrame(
        [
            {
                "session_date": "2026-05-04",
                "contract_symbol": "ESM26",
                "source_contract_symbol": "ESM6",
                "atr_lookback_bars": 14,
                "atr14_3m_seed_points": 2.0,
                "previous_close_points": 100.0,
                "last_seed_bar_open": pd.Timestamp(
                    "2026-05-04 09:27:00",
                    tz="America/New_York",
                ),
                "last_seed_bar_close": pd.Timestamp(
                    "2026-05-04 09:30:00",
                    tz="America/New_York",
                ),
            }
        ]
    ).to_parquet(path, index=False)
    big_trade_path = tmp_path / "big_trade.parquet"
    pd.DataFrame(
        [
            {
                "session_date": "2026-05-04",
                "contract_symbol": "ESM26",
                "lookback_sessions": 20,
                "reference_percentile": 0.999,
                "percentile_method": "nearest_rank_higher",
                "threshold_volume": 250,
                "reference_observation_count": 1_000_000,
                "reference_start_session": "2026-04-06",
                "reference_end_session": "2026-05-01",
                "aggregation_interval_ms": 100,
                "aggregation_price_ticks": 1,
                "aggregation_side_scope": "same_aggressor_side_A_or_B",
            }
        ]
    ).to_parquet(big_trade_path, index=False)
    return (
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        big_trade_path,
        hashlib.sha256(big_trade_path.read_bytes()).hexdigest(),
    )


def _config(tmp_path, **overrides):
    path, digest, big_trade_path, big_trade_digest = _context(tmp_path)
    return YushAdaptiveOrderflowRangeConfig(
        atr_context_path=str(path),
        atr_context_sha256=digest,
        big_trade_context_path=str(big_trade_path),
        big_trade_context_sha256=big_trade_digest,
        **overrides,
    )


def _view():
    return EventReplaySessionView(
        session_date=date(2026, 5, 4),
        contract_symbol="ESM26",
        metadata=MappingProxyType(
            {
                "previous_rth": RthSummary(
                    date(2026, 5, 1),
                    "ESM26",
                    105.0,
                    95.0,
                    100.0,
                ),
                "overnight_high": 103.0,
                "overnight_low": 97.0,
            }
        ),
        input_was_canonically_sorted=True,
    )


def _state(tmp_path, **overrides):
    config = _config(tmp_path, **overrides)
    seed = _atr_seed_for_session(date(2026, 5, 4), config)
    big_trade_seed = _big_trade_seed_for_session(date(2026, 5, 4), config)
    return _AdaptiveOrderflowRangeState(
        _view(),
        config,
        seed,
        big_trade_seed,
    )


def _candidate(direction="long", low=400, high=404):
    side = "VAL" if direction == "long" else "VAH"
    anchor = low if direction == "long" else high
    point = ConfluencePoint("market", "PDC", anchor, anchor, anchor)
    return AoiCandidate(
        side,
        direction,
        anchor,
        low,
        high,
        ("market",),
        (point,),
    )


def _set_internal_value_profile(
    state,
    *,
    val_tick=400,
    vah_tick=410,
    poc_tick=405,
    poc_volume=1_000,
    minimum_tick=404,
    minimum_volume=100,
):
    state.base_tick = val_tick
    state.top_tick = vah_tick
    state.profile_volume = np.full(
        vah_tick - val_tick + 1,
        200,
        dtype=np.int64,
    )
    state.profile_volume[poc_tick - val_tick] = poc_volume
    state.profile_volume[minimum_tick - val_tick] = minimum_volume
    state.current_profile = {
        "val_tick": val_tick,
        "vah_tick": vah_tick,
        "poc_tick": poc_tick,
    }
    state._refresh_internal_value_profile_state()


def test_reviewed_fixed_cost_risk_and_offsets_cannot_drift(tmp_path):
    config = _config(tmp_path)

    assert config.entry_offset_ticks == 1
    assert config.stop_offset_ticks == 1
    assert config.slippage_ticks == 0
    assert config.commission_per_contract == 1.55
    assert config.max_trades_per_day == 0
    assert config.max_stop_points == 5.0
    assert config.max_entry_to_far_aoi_edge_points == 5.0
    assert config.internal_lvn_poc_fraction == 0.10
    assert config.minimum_stop_points == 0.25
    assert config.aoi_atr_multiple == 1.5
    assert config.aoi_atr_max_points == 5.0
    assert config.target_mode == "midpoint"

    with pytest.raises(ValueError, match="fixed adaptive v02 mechanic drift"):
        YushAdaptiveOrderflowRangeConfig(
            atr_context_path=config.atr_context_path,
            atr_context_sha256=config.atr_context_sha256,
            slippage_ticks=1,
        )
    with pytest.raises(ValueError, match="unknown"):
        build_strategy({"big_trade_average_multiple": 12})
    with pytest.raises(ValueError, match="delta_average_multiple"):
        build_strategy({"delta_average_multiple": 7})
    with pytest.raises(ValueError, match="target_mode"):
        build_strategy({"target_mode": "moving_target"})

    expanded = build_strategy(
        {
            "delta_average_multiple": 6,
            "target_mode": "opposite_value_edge",
            "atr_context_path": config.atr_context_path,
            "atr_context_sha256": config.atr_context_sha256,
            "big_trade_context_path": config.big_trade_context_path,
            "big_trade_context_sha256": config.big_trade_context_sha256,
        }
    )
    assert expanded.cfg.delta_average_multiple == 6
    assert expanded.cfg.target_mode == "opposite_value_edge"


def test_atr_context_is_hash_bound_and_width_is_capped(tmp_path):
    config = _config(tmp_path)
    seed = _atr_seed_for_session(date(2026, 5, 4), config)
    big_trade_seed = _big_trade_seed_for_session(date(2026, 5, 4), config)
    state = _AdaptiveOrderflowRangeState(
        _view(),
        config,
        seed,
        big_trade_seed,
    )

    assert seed.atr_points == 2.0
    assert state.active_aoi_width_limit_ticks == 12  # 3.0 points

    capped = AdaptiveAtrSeed(
        atr_points=10.0,
        previous_close_tick=400,
        source_contract_symbol="ESM6",
        last_seed_bar_close=seed.last_seed_bar_close,
    )
    capped_state = _AdaptiveOrderflowRangeState(
        _view(),
        config,
        capped,
        big_trade_seed,
    )
    assert capped_state.active_aoi_width_limit_ticks == 20  # five points

    path = tmp_path / "atr.parquet"
    path.write_bytes(path.read_bytes() + b"drift")
    _atr_seed_for_session.cache_clear() if hasattr(_atr_seed_for_session, "cache_clear") else None
    from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range import (
        _load_atr_context,
    )

    _load_atr_context.cache_clear()
    with pytest.raises(ValueError, match="hash drift"):
        _atr_seed_for_session(date(2026, 5, 4), config)


def test_big_trade_context_is_hash_bound_and_strictly_prior(tmp_path):
    config = _config(tmp_path)
    seed = _big_trade_seed_for_session(date(2026, 5, 4), config)
    assert seed.threshold_volume == 250
    assert seed.reference_end_session == "2026-05-01"

    from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range import (
        _load_big_trade_context,
    )

    path = Path(config.big_trade_context_path)
    frame = pd.read_parquet(path)
    frame.loc[0, "reference_end_session"] = "2026-05-04"
    frame.to_parquet(path, index=False)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _load_big_trade_context.cache_clear()
    noncausal = YushAdaptiveOrderflowRangeConfig(
        atr_context_path=config.atr_context_path,
        atr_context_sha256=config.atr_context_sha256,
        big_trade_context_path=str(path),
        big_trade_context_sha256=digest,
    )
    with pytest.raises(ValueError, match="non-causal"):
        _big_trade_seed_for_session(date(2026, 5, 4), noncausal)

    path.write_bytes(path.read_bytes() + b"drift")
    _load_big_trade_context.cache_clear()
    with pytest.raises(ValueError, match="hash drift"):
        _big_trade_seed_for_session(date(2026, 5, 4), noncausal)


def test_big_trade_threshold_is_frozen_from_prior_sessions(tmp_path):
    state = _state(tmp_path, delta_average_multiple=2.0)
    state.completed_abs_delta = 1_200
    state.completed_delta_occurrences = 5
    state.average_abs_delta_per_level = 240.0
    state._activate_thresholds()

    assert state.active_big_trade_threshold == 250
    assert state.big_trade_seed.reference_percentile == 0.999
    assert state.big_trade_seed.lookback_sessions == 20
    assert state.active_delta_threshold == 480.0


def test_same_frozen_threshold_governs_aoi_building_and_entry_trigger(tmp_path):
    state = _state(tmp_path)
    state.event_count = 1
    state.timestamp_ns[0] = state.open_ns
    state.price_ticks[0] = 401
    state.active_decision_bucket = 0
    state._decision_big_trade_volume = {
        (400, "B"): 249,
        (401, "B"): 250,
    }

    state._finalize_decision_interval(0)

    assert len(state.big_trade_occurrences) == 1
    occurrence = state.big_trade_occurrences[0]
    assert occurrence["price_tick"] == 401
    assert occurrence["volume"] == 250
    assert occurrence["configured_threshold"] == 250

    state.current_profile = {
        "val_tick": 400,
        "vah_tick": 500,
        "poc_tick": 450,
    }
    selected = state._selected_candidates()
    assert "big_trade" in selected["VAL"].categories
    assert any(
        point.category == "big_trade" and point.point_tick == 401
        for point in selected["VAL"].confluences
    )

    trigger = state._qualifying_entry_bubble(
        selected["VAL"],
        tap_event_index=-1,
        index=0,
    )
    assert trigger is not None
    assert trigger["kind"] == "adaptive_big_trade_100ms"
    assert trigger["value"] == 250
    assert trigger["threshold"] == 250


def test_aoi_uses_only_most_recent_big_trade_and_never_falls_back(tmp_path):
    state = _state(tmp_path)
    state.current_profile = {
        "val_tick": 400,
        "vah_tick": 500,
        "poc_tick": 450,
    }
    state.big_trade_occurrences = [
        {
            "occurrence_id": 1,
            "qualified_at_ns": state.open_ns,
            "qualified_event_index": 1,
            "price_tick": 401,
            "side": "A",
            "volume": 300,
            "configured_threshold": 250,
        },
        {
            "occurrence_id": 2,
            "qualified_at_ns": state.open_ns + 1,
            "qualified_event_index": 2,
            "price_tick": 402,
            "side": "B",
            "volume": 275,
            "configured_threshold": 250,
        },
        {
            "occurrence_id": 3,
            "qualified_at_ns": state.open_ns + 2,
            "qualified_event_index": 3,
            "price_tick": 499,
            "side": "A",
            "volume": 280,
            "configured_threshold": 250,
        },
    ]

    selected = state._selected_candidates()

    assert [
        point.point_tick
        for point in selected["VAL"].confluences
        if point.category == "big_trade"
    ] == [402]
    assert [
        point.point_tick
        for point in selected["VAH"].confluences
        if point.category == "big_trade"
    ] == [499]

    state._apply_candidate("VAL", selected["VAL"], state.open_ns + 3, 3)
    original_lineage = state.lineages["VAL"]
    assert original_lineage is not None
    state.big_trade_occurrences.append(
        {
            "occurrence_id": 4,
            "qualified_at_ns": state.open_ns + 4,
            "qualified_event_index": 4,
            "price_tick": 402,
            "side": "A",
            "volume": 310,
            "configured_threshold": 250,
        }
    )
    selected = state._selected_candidates()
    state._apply_candidate("VAL", selected["VAL"], state.open_ns + 4, 4)
    replacement_lineage = state.lineages["VAL"]
    assert replacement_lineage is not None
    assert replacement_lineage.lineage_id != original_lineage.lineage_id
    assert replacement_lineage.eligible_event_index == 4

    state._consumed_big_trade_occurrence_ids.add(4)
    state._consumed_big_trade_occurrence_ids.add(2)
    state._candidate_cache_keys["VAL"] = None
    state._candidate_cache["VAL"] = None
    selected = state._selected_candidates()
    assert "VAL" not in selected


def test_aoi_building_big_trade_is_consumed_on_first_directed_retest(tmp_path):
    state = _state(tmp_path)
    state.current_profile = {
        "val_tick": 400,
        "vah_tick": 500,
        "poc_tick": 450,
    }
    state.big_trade_occurrences = [
        {
            "occurrence_id": 1,
            "qualified_at_ns": state.open_ns,
            "qualified_event_index": 0,
            "price_tick": 401,
            "side": "B",
            "volume": 300,
            "configured_threshold": 250,
        }
    ]
    selected = state._selected_candidates()
    state._apply_candidate("VAL", selected["VAL"], state.open_ns, 0)
    lineage = state.lineages["VAL"]
    assert lineage is not None

    state.event_count = 3
    state.timestamp_ns[:3] = [
        state.open_ns,
        state.open_ns + 1,
        state.open_ns + 2,
    ]
    state.price_ticks[:3] = [
        selected["VAL"].high_tick + 1,
        selected["VAL"].high_tick + 1,
        selected["VAL"].high_tick,
    ]
    state.previous_decision_event_index = 1
    state._update_visit_and_order(lineage, 2)

    assert lineage.visit is not None
    assert state._consumed_big_trade_occurrence_ids == {1}
    assert state.diagnostics["adaptive_big_trade_aoi_consumed"] == 1


def test_completed_bar_updates_delta_average_and_wilder_atr(tmp_path):
    state = _state(tmp_path)
    state.base_four = 100
    state.top_four = 104
    state.bar_delta_four = np.array([200, -50, 100, -150, 700], dtype=np.int64)
    state.delta_four = state.bar_delta_four.copy()
    state.traded_four = np.ones(5, dtype=np.bool_)
    state._current_bar_buckets = {100, 101, 102, 103, 104}
    state._current_bar_low_tick = 396
    state._current_bar_high_tick = 412
    state._current_bar_last_tick = 408
    state._atr_previous_close_tick = 400

    state._complete_adaptive_bar()

    assert state.average_abs_delta_per_level == 240.0
    # Seed ATR=2.0; completed true range=4.0 points; Wilder update is causal.
    assert state.active_atr_points == pytest.approx((2.0 * 13 + 4.0) / 14)
    assert state._atr_previous_close_tick == 408


def test_structural_stop_is_one_tick_outside_and_risk_is_capped(tmp_path):
    state = _state(tmp_path)
    state.event_count = 2
    state.price_ticks[:2] = [405, 406]
    state.timestamp_ns[:2] = [state.open_ns, state.open_ns + 1]
    state.cumulative_low[:2] = [390, 390]
    state.cumulative_high[:2] = [440, 440]
    state.current_profile = {"val_tick": 400, "vah_tick": 500, "poc_tick": 450}
    state.active_profile_poc_volume = 1_000
    state.active_internal_value_level_count = 99
    state.active_internal_value_min_volume = 100
    state.active_internal_value_min_volume_tick = 425
    candidate = _candidate("long", 400, 404)
    visit = Visit(state.open_ns, 0, 400, 404)
    lineage = AoiLineage(1, candidate, state.open_ns - 1, -1, visit=visit)
    state._qualifying_entry_bubble = lambda *_: {
        "kind": "adaptive_big_trade_100ms",
        "qualified_at_ns": state.open_ns + 1,
        "qualified_event_index": 1,
        "price_tick": 400,
        "value": 200,
    }
    state._preorder_range_gate = lambda *_: True

    state._update_visit_and_order(lineage, 1)

    assert lineage.pending is not None
    assert lineage.pending.entry_tick == 405
    assert lineage.pending.stop_tick == 399
    state.reversals["VAL"].append(
        Visit(state.open_ns - 2, -2, 400, 404, state.open_ns - 1)
    )
    state._range_and_profile_pass = lambda *_: True
    assert state._fill_gate_passes(1, lineage)

    state.price_ticks[1] = 420  # edge distance is 5.0, but stop risk is 5.25
    assert not state._fill_gate_passes(1, lineage)
    assert state.diagnostics["stop_limit_rejections"] == 1


def test_fill_rejects_entry_more_than_five_points_from_far_aoi_edge(tmp_path):
    state = _state(tmp_path)
    state.event_count = 1
    state.timestamp_ns[0] = state.open_ns
    state.cumulative_low[0] = 390
    state.cumulative_high[0] = 440
    state.current_profile = {"val_tick": 400, "vah_tick": 500, "poc_tick": 450}
    state.active_profile_poc_volume = 1_000
    state.active_internal_value_level_count = 99
    state.active_internal_value_min_volume = 100
    state.active_internal_value_min_volume_tick = 425
    state.reversals["VAL"].append(
        Visit(state.open_ns - 2, -2, 400, 404, state.open_ns - 1)
    )
    state._range_and_profile_pass = lambda *_: True
    candidate = _candidate("long", 400, 404)
    lineage = AoiLineage(
        1,
        candidate,
        state.open_ns - 1,
        -1,
        visit=Visit(state.open_ns - 1, -1, 400, 404),
        pending=PendingOrder(
            "adaptive_big_trade_100ms",
            state.open_ns,
            0,
            state.open_ns,
            0,
            405,
            402,
            400,
        ),
    )

    state.price_ticks[0] = 420  # exactly five points above the long AOI far edge
    assert state._fill_gate_passes(0, lineage)

    state.price_ticks[0] = 421
    assert not state._fill_gate_passes(0, lineage)
    assert state.diagnostics["adaptive_aoi_edge_distance_rejections"] == 1


def test_internal_value_lvn_below_ten_percent_blocks_order_pending_and_fill(
    tmp_path,
):
    state = _state(tmp_path)
    _set_internal_value_profile(state, minimum_volume=99)

    assert state.active_profile_poc_volume == 1_000
    assert state.active_internal_value_min_volume == 99
    assert state.active_internal_value_min_volume_tick == 404
    assert not state._internal_value_profile_passes(record_rejection=False)

    candidate = _candidate("long", 400, 404)
    pending = PendingOrder(
        "adaptive_big_trade_100ms",
        state.open_ns,
        0,
        state.open_ns,
        0,
        405,
        399,
        400,
    )
    lineage = AoiLineage(
        1,
        candidate,
        state.open_ns,
        0,
        visit=Visit(state.open_ns, 0, 400, 404),
        pending=pending,
    )
    assert not state._pending_is_live(pending, candidate, 0)
    assert not state._fill_gate_passes(0, lineage)
    assert state.diagnostics["adaptive_internal_lvn_rejections"] == 2

    _set_internal_value_profile(state, minimum_volume=100)
    assert state._internal_value_profile_passes(record_rejection=False)


def test_new_aoi_at_current_price_requires_leave_retap_and_new_trigger(
    tmp_path,
):
    state = _state(tmp_path)
    state.event_count = 4
    state.timestamp_ns[:4] = [
        state.open_ns,
        state.open_ns + 1,
        state.open_ns + 2,
        state.open_ns + 3,
    ]
    # A short AOI is created while price is inside it, price then leaves below
    # the zone, retaps from below, and only a later trigger may arm the entry.
    state.price_ticks[:4] = [400, 399, 400, 400]
    candidate = _candidate("short", 400, 404)
    state._apply_candidate("VAH", candidate, state.open_ns, 0)
    lineage = state.lineages["VAH"]
    assert lineage is not None
    state.big_trade_occurrences = [
        {
            "occurrence_id": 1,
            "qualified_at_ns": state.open_ns,
            "qualified_event_index": 0,
            "price_tick": 400,
            "side": "B",
            "volume": 1_000,
            "configured_threshold": 250,
        }
    ]
    state._preorder_range_gate = lambda *_: True

    state._update_visit_and_order(lineage, 0)
    assert lineage.visit is None
    assert lineage.pending is None

    state.previous_decision_event_index = 0
    state._update_visit_and_order(lineage, 1)
    assert lineage.visit is None

    state.previous_decision_event_index = 1
    state._update_visit_and_order(lineage, 2)
    assert lineage.visit is not None
    assert lineage.visit.tapped_event_index == 2
    assert lineage.pending is None

    state.big_trade_occurrences.append(
        {
            "occurrence_id": 2,
            "qualified_at_ns": state.open_ns + 3,
            "qualified_event_index": 3,
            "price_tick": 400,
            "side": "B",
            "volume": 1_001,
            "configured_threshold": 250,
        }
    )
    state.previous_decision_event_index = 2
    state._update_visit_and_order(lineage, 3)

    assert lineage.pending is not None
    assert lineage.pending.bubble_event_index == 3
    assert lineage.pending.bubble_value == 1_001


def test_zero_daily_trade_limit_means_unlimited(tmp_path):
    strategy = YushAdaptiveOrderflowRangeEventStrategy(_config(tmp_path))
    state = _state(tmp_path)
    strategy.state = state
    state.decision_due = True
    state.decision_event_index = 0
    selected = []
    state._selected_candidates = lambda: selected.append(True) or {}
    broker = SimpleNamespace(
        position=None,
        trades_today=10_000,
        cancel_all_entries=lambda **_kwargs: None,
    )
    event = SimpleNamespace()

    strategy.after_event(
        event,
        broker,
        closed_this_event=False,
        opened_this_event=False,
        entries_blocked=False,
    )

    assert selected == [True]


def test_midpoint_is_initial_fixed_target_and_never_activates_breakeven(tmp_path):
    strategy = YushAdaptiveOrderflowRangeEventStrategy(_config(tmp_path))
    state = _state(tmp_path)
    strategy.state = state
    state.current_profile = {"val_tick": 400, "vah_tick": 421, "poc_tick": 410}
    candidate = _candidate("long", 400, 404)
    pending = PendingOrder(
        "adaptive_big_trade_100ms",
        state.open_ns,
        0,
        state.open_ns,
        0,
        405,
        399,
        400,
    )
    lineage = AoiLineage(1, candidate, state.open_ns, 0, pending=pending)
    broker = SimpleNamespace(
        submitted=None,
        submit_or_replace_entry=lambda **kwargs: setattr(
            broker,
            "submitted",
            kwargs,
        ),
        cancel_entry=lambda *_args, **_kwargs: None,
    )

    strategy._sync_pending_order("VAL", lineage, broker)

    assert broker.submitted["target_tick"] == 410  # conservative half-tick floor
    directive = strategy.position_directive(None, None, None)
    assert directive.stop_tick is None
    assert directive.target_tick is None


def test_target_choice_freezes_midpoint_or_opposite_value_edge(tmp_path):
    profile = {"val_tick": 400, "vah_tick": 421, "poc_tick": 410}
    assert _frozen_target_tick(
        profile,
        direction="long",
        target_mode="midpoint",
    ) == 410
    assert _frozen_target_tick(
        profile,
        direction="short",
        target_mode="midpoint",
    ) == 411
    assert _frozen_target_tick(
        profile,
        direction="long",
        target_mode="opposite_value_edge",
    ) == 421
    assert _frozen_target_tick(
        profile,
        direction="short",
        target_mode="opposite_value_edge",
    ) == 400

    strategy = YushAdaptiveOrderflowRangeEventStrategy(
        _config(tmp_path, target_mode="opposite_value_edge")
    )
    state = _state(tmp_path, target_mode="opposite_value_edge")
    strategy.state = state
    state.current_profile = profile
    candidate = _candidate("long", 400, 404)
    pending = PendingOrder(
        "adaptive_big_trade_100ms",
        state.open_ns,
        0,
        state.open_ns,
        0,
        405,
        399,
        400,
    )
    lineage = AoiLineage(1, candidate, state.open_ns, 0, pending=pending)
    broker = SimpleNamespace(
        submitted=None,
        submit_or_replace_entry=lambda **kwargs: setattr(
            broker,
            "submitted",
            kwargs,
        ),
        cancel_entry=lambda *_args, **_kwargs: None,
    )

    strategy._sync_pending_order("VAL", lineage, broker)

    assert broker.submitted["target_tick"] == 421
    assert broker.submitted["report_fields"] == {
        "target_mode": "opposite_value_edge",
        "frozen_target_price": 105.25,
    }
