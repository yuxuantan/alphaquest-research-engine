from __future__ import annotations

from dataclasses import asdict
from datetime import date
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd

import alphaquest.strategy_modules.event.runner as event_runner
from alphaquest.research.core_grid import run_core_grid
from alphaquest.strategy_modules.event.runner import iter_event_sessions, replay_event_sessions
from alphaquest.backtest.event_replay import CanonicalEvent, EventReplaySessionView
from alphaquest.strategy_modules.event.yush_orderflow_primitives import (
    AoiCandidate,
    AoiLineage,
    ConfluencePoint,
    PendingOrder,
    Visit,
)
from alphaquest.strategy_modules.event.yush_orderflow_range import (
    YushOrderflowRangeConfig,
    YushOrderflowRangeEventStrategy,
    _YushOrderflowRangeState,
    _aoi_fingerprint,
    _best_refined_aoi,
)
from alphaquest.data.databento_session_stream import DatabentoTradeSession, RthSummary


def _session(prices=(100.0, 100.25, 100.5), sizes=None, sides=None, offsets_ms=None):
    sizes = sizes or tuple(1 for _ in prices)
    sides = sides or tuple("B" for _ in prices)
    offsets_ms = offsets_ms or tuple(range(len(prices)))
    timestamps = [
        pd.Timestamp("2026-05-04 09:30:00", tz="America/New_York") + pd.Timedelta(milliseconds=value)
        for value in offsets_ms
    ]
    events = pd.DataFrame(
        {
            "timestamp": timestamps,
            "source_ordinal": range(len(prices)),
            "sequence": range(len(prices)),
            "symbol": "ES",
            "contract_symbol": "ESM6",
            "price": prices,
            "size": sizes,
            "side": sides,
            "signed_size": [size if side == "B" else -size for size, side in zip(sizes, sides, strict=True)],
        }
    )
    return DatabentoTradeSession(
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        previous_rth=RthSummary(date(2026, 5, 1), "ESM6", 101.0, 99.0, 100.0),
        overnight_high=100.75,
        overnight_low=99.25,
        events=events,
    )


def _state(session=None):
    session = session or _session()
    view = EventReplaySessionView(
        session_date=session.session_date,
        contract_symbol=session.contract_symbol,
        metadata=MappingProxyType(dict(session.event_replay_metadata)),
        input_was_canonically_sorted=True,
    )
    return _YushOrderflowRangeState(view, YushOrderflowRangeConfig())


def _config():
    mechanics = asdict(YushOrderflowRangeConfig())
    return {
        "strategy_name": "yush_orderflow_range",
        "engine_lane": "canonical_event_replay",
        "timezone": "America/New_York",
        "strategy": {"event": {"module": "yush_orderflow_range", "params": mechanics}},
        "core": {
            "initial_balance": 50_000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "contracts": 1,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "max_trades_per_day": 3,
            "entry_start": "09:30:00",
            "latest_entry_time": "10:59:59",
            "flatten_time": "11:00:00",
            "event_stop_market_fill_policy": "trade_event_price_on_gap",
        },
    }


def _ingest(state, session):
    for index, row in session.events.reset_index(drop=True).iterrows():
        state.last_timestamp_ns = int(pd.Timestamp(row.timestamp).value)
        state._ingest_event(
            CanonicalEvent(
                event_index=index,
                timestamp=row.timestamp,
                timestamp_ns=int(pd.Timestamp(row.timestamp).value),
                source_ordinal=int(row.source_ordinal),
                price=float(row.price),
                price_tick=int(round(float(row.price) / 0.25)),
                size=int(row["size"]),
                side=str(row.side),
                signed_size=int(row.signed_size),
            )
        )


def _candidate(direction="long", low=400, high=404):
    side = "VAL" if direction == "long" else "VAH"
    anchor = low if direction == "long" else high
    confluence = ConfluencePoint("market", "PDC", anchor, anchor, anchor)
    return AoiCandidate(side, direction, anchor, low, high, ("market",), (confluence,))


def _end_to_end_trade_session():
    rows = []
    base = pd.Timestamp("2026-05-04 09:30:00", tz="America/New_York")
    ordinal = 0
    counts = {400: 5, 405: 5, 410: 10, 415: 5, 420: 5}
    remaining = counts.copy()
    side_count = {tick: 0 for tick in counts}
    while any(remaining.values()):
        for tick in counts:
            if not remaining[tick]:
                continue
            side = "B" if side_count[tick] % 2 == 0 else "A"
            rows.append((base + pd.Timedelta(milliseconds=200 * ordinal), tick, 100, side))
            ordinal += 1
            remaining[tick] -= 1
            side_count[tick] += 1
    # First tap/reversal, move back above, second tap, qualifying bubble,
    # stop-entry fill, frozen midpoint, management activation, target cross.
    for tick, size, side in (
        (400, 1, "A"),
        (402, 1, "B"),
        (420, 1, "A"),
        (400, 1, "A"),
        (400, 101, "B"),
        (400, 100, "B"),
        (402, 1, "B"),
        (408, 1, "B"),
        (415, 1, "B"),
        (420, 1, "B"),
    ):
        rows.append((base + pd.Timedelta(milliseconds=200 * ordinal), tick, size, side))
        ordinal += 1
    events = pd.DataFrame(
        {
            "timestamp": [row[0] for row in rows],
            "source_ordinal": range(len(rows)),
            "sequence": range(len(rows)),
            "symbol": "ES",
            "contract_symbol": "ESM6",
            "price": [row[1] * 0.25 for row in rows],
            "size": [row[2] for row in rows],
            "side": [row[3] for row in rows],
        }
    )
    events["signed_size"] = [
        size if side == "B" else -size
        for size, side in zip(events["size"], events["side"], strict=True)
    ]
    return DatabentoTradeSession(
        session_date=date(2026, 5, 4),
        contract_symbol="ESM6",
        previous_rth=RthSummary(date(2026, 5, 1), "ESM6", 101.0, 99.0, 100.0),
        overnight_high=105.0,
        overnight_low=98.0,
        events=events,
    )


def test_runner_uses_realistic_gap_fills_one_tick_slippage_and_eleven_flatten():
    result = replay_event_sessions(_config(), [_session()])

    execution = result["reproducibility"]["execution_assumptions"]
    assert execution["slippage_ticks"] == 1
    assert result["reproducibility"]["engine_lane"] == "canonical_event_replay"
    assert result["trades"].empty


def test_each_trade_event_updates_volume_and_delta_exactly_once():
    session = _session(prices=(100.0,), sizes=(7,), sides=("B",))
    state = _state(session)

    _ingest(state, session)

    one_tick_index = 400 - int(state.base_tick)
    four_tick_index = 100 - int(state.base_four)
    assert state.event_count == 1
    assert int(state.profile_volume[one_tick_index]) == 7
    assert int(state.delta_one[one_tick_index]) == 7
    assert int(state.delta_four[four_tick_index]) == 7
    assert int(state.bar_delta_four[four_tick_index]) == 7


def test_revised_session_loader_fixes_eth_start_at_1600(monkeypatch):
    received = {}

    def fake_loader(*args, **kwargs):
        received.update(kwargs)
        return iter(())

    monkeypatch.setattr(event_runner, "iter_databento_trade_sessions", fake_loader)
    config = {
        "symbol": "ES",
        "data": {
            "execution_data": {
                "source": "databento_zip_trades",
                "archive": "archive",
                "roll_calendar": "rolls",
                "overnight_start": "16:00:00",
            }
        },
    }
    assert list(iter_event_sessions(config, {"start_date": "2026-01-01", "end_date": "2026-01-02"})) == []
    assert received["overnight_start"] == "16:00:00"


def test_generic_event_runner_routes_governed_sierra_source(monkeypatch):
    received = {}

    def fake_loader(config, *, start_date, end_date):
        received["config"] = config
        received["start_date"] = start_date
        received["end_date"] = end_date
        return iter(())

    monkeypatch.setattr(event_runner, "iter_sierra_trade_sessions", fake_loader)
    execution = {
        "source": "sierra_scid_records",
        "raw_dir": "scid",
        "session_levels": "levels.parquet",
        "quality_manifest": "quality.csv",
    }
    config = {"symbol": "ES", "data": {"execution_data": execution}}

    assert list(
        iter_event_sessions(
            config,
            {"start_date": "2026-01-01", "end_date": "2026-01-02"},
        )
    ) == []
    assert received == {
        "config": execution,
        "start_date": "2026-01-01",
        "end_date": "2026-01-02",
    }


def test_end_to_end_replay_builds_second_reversal_then_fills_manages_and_targets():
    result = replay_event_sessions(_config(), [_end_to_end_trade_session()])

    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert trade["aoi_side"] == "VAL"
    assert trade["aoi_confluences"] == "PDC"
    assert trade["aoi_lineage_mode"] == "exact_fingerprint"
    assert trade["aoi_exact_fingerprint"].startswith("VAL|long|")
    assert (
        trade["aoi_eligible_event_index"]
        < trade["aoi_tap_event_index"]
        < trade["bubble_qualified_event_index"]
        < trade["entry_event_index"]
    )
    assert trade["risk_points"] == 2.25
    assert bool(trade["midpoint_activated"])
    assert trade["exit_reason"] == "target"
    assert trade["exit_event_index"] == 39


def test_research_core_grid_routes_registered_strategy_through_event_replay(monkeypatch):
    seen = {}

    def fake_sessions(config, subset):
        seen["subset"] = subset
        return [_end_to_end_trade_session()]

    monkeypatch.setattr(event_runner, "iter_event_sessions", fake_sessions)
    market = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-05-04 09:30:00", tz="America/New_York")],
            "session_date": ["2026-05-04"],
        }
    )

    results, summary = run_core_grid(
        market,
        _config(),
        {"parameters": {}, "parallel": {"enabled": False}},
        {},
    )

    assert len(results) == 1
    assert int(results.iloc[0]["total_trades"]) == 1
    assert summary["total_combinations_tested"] == 1
    assert seen["subset"] == {
        "start_date": "2026-05-04",
        "end_date": "2026-05-04",
        "session_dates": ["2026-05-04"],
    }


def test_delta_profile_uses_only_four_tick_bucket_and_local_mean_prominence():
    state = _state()
    state.base_four = 98
    state.delta_four = np.array([0, 0, 100, 250, 300, 250, 0, 0, 0], dtype=np.int64)
    state.traded_four = np.ones(9, dtype=np.bool_)

    # Neighbour mean is 150, so 300 is significant even though it is not 2x
    # each individual neighbour. This is the explicitly reviewed mean rule.
    assert state._delta_level_qualifies(state.delta_four, state.traded_four, 102, state.base_four)
    state.delta_four[4] = 299
    assert not state._delta_level_qualifies(state.delta_four, state.traded_four, 102, state.base_four)
    state.delta_four[4] = 300
    state.traded_four[6] = False
    assert not state._delta_level_qualifies(state.delta_four, state.traded_four, 102, state.base_four)


def test_aoi_allows_tiny_envelope_but_includes_entire_delta_bucket_and_caps_three_points():
    tiny = _best_refined_aoi(
        "VAL",
        "long",
        400,
        {"market": [ConfluencePoint("market", "PDC", 400, 400, 400)]},
        max_width_ticks=12,
    )
    assert tiny is not None
    assert tiny.width_ticks == 0

    delta = ConfluencePoint("delta_profile", "DELTA_4T_LOCAL_PROMINENCE", 400, 400, 403)
    full_bucket = _best_refined_aoi("VAL", "long", 399, {"delta_profile": [delta]}, max_width_ticks=12)
    assert full_bucket is not None
    assert (full_bucket.low_tick, full_bucket.high_tick) == (399, 403)

    assert _best_refined_aoi("VAL", "long", 390, {"delta_profile": [delta]}, max_width_ticks=12) is None


def test_aoi_selection_maximizes_categories_then_minimizes_width():
    categories = {
        "market": [ConfluencePoint("market", "PDC", 401, 401, 401)],
        "delta_profile": [ConfluencePoint("delta_profile", "DELTA", 402, 400, 403)],
        "big_trade": [ConfluencePoint("big_trade", "BIG_1", 404, 404, 404)],
    }
    candidate = _best_refined_aoi("VAL", "long", 400, categories, 12)
    assert candidate is not None
    assert candidate.categories == ("market", "delta_profile", "big_trade")
    assert (candidate.low_tick, candidate.high_tick) == (400, 404)


def test_equal_aoi_tie_uses_declared_confluence_preference_order():
    preferred = ConfluencePoint("delta_profile", "HIGHER_MAGNITUDE", 404, 404, 407)
    other = ConfluencePoint("delta_profile", "LOWER_MAGNITUDE", 400, 397, 400)
    candidate = _best_refined_aoi(
        "VAL",
        "long",
        402,
        {"delta_profile": [preferred, other]},
        max_width_ticks=12,
    )
    assert candidate is not None
    assert candidate.confluences == (preferred,)


def test_big_trade_occurrences_are_not_deduplicated_by_price_and_trigger_must_follow_tap():
    session = _session(
        prices=(100.0, 100.0, 100.0, 100.0),
        sizes=(101, 100, 101, 100),
        sides=("B", "B", "B", "B"),
        offsets_ms=(0, 50, 200, 250),
    )
    state = _state(session)
    _ingest(state, session)

    assert [item["qualified_event_index"] for item in state.big_trade_occurrences] == [1, 3]
    state.delta_threshold_crossings.clear()
    candidate = _candidate(low=399, high=400)
    assert state._qualifying_entry_bubble(candidate, tap_event_index=1, index=1) is None
    trigger = state._qualifying_entry_bubble(candidate, tap_event_index=1, index=3)
    assert trigger is not None
    assert trigger["qualified_event_index"] == 3


def test_delta_trigger_qualifies_at_exactly_300_and_only_after_tap():
    session = _session(prices=(100.0, 100.0), sizes=(150, 150), offsets_ms=(0, 1))
    state = _state(session)
    _ingest(state, session)
    candidate = _candidate(low=399, high=400)

    assert state._qualifying_entry_bubble(candidate, tap_event_index=1, index=1) is None
    trigger = state._qualifying_entry_bubble(candidate, tap_event_index=0, index=1)
    assert trigger is not None
    assert trigger["kind"] == "delta_4tick_3m"
    assert trigger["value"] == 300


def test_tap_requires_val_from_above_and_vah_from_below():
    long_session = _session(prices=(101.25, 101.0), offsets_ms=(0, 1))
    long_state = _state(long_session)
    _ingest(long_state, long_session)
    long_lineage = AoiLineage(1, _candidate("long", 400, 404), long_state.open_ns, 0)
    long_state._update_visit_and_order(long_lineage, 1)
    assert long_lineage.visit is not None

    wrong_session = _session(prices=(100.75, 101.0), offsets_ms=(0, 1))
    wrong_state = _state(wrong_session)
    _ingest(wrong_state, wrong_session)
    wrong_lineage = AoiLineage(1, _candidate("long", 400, 404), wrong_state.open_ns, 0)
    wrong_state._update_visit_and_order(wrong_lineage, 1)
    assert wrong_lineage.visit is None

    short_session = _session(prices=(99.75, 100.0), offsets_ms=(0, 1))
    short_state = _state(short_session)
    _ingest(short_state, short_session)
    short_lineage = AoiLineage(1, _candidate("short", 400, 404), short_state.open_ns, 0)
    short_state._update_visit_and_order(short_lineage, 1)
    assert short_lineage.visit is not None


def test_untapped_aoi_resets_eligibility_when_exact_fingerprint_changes():
    state = _state()
    original = _candidate("long", 400, 404)
    state._apply_candidate("VAL", original, state.open_ns, 0)
    first = state.lineages["VAL"]
    assert first is not None

    same_identity = AoiCandidate(
        "VAL",
        "long",
        402,
        400,
        404,
        original.categories,
        original.confluences,
    )
    state._apply_candidate("VAL", same_identity, state.open_ns + 1, 1)
    assert state.lineages["VAL"].lineage_id == first.lineage_id
    assert state.lineages["VAL"].eligible_event_index == 0
    assert _aoi_fingerprint(original) == _aoi_fingerprint(same_identity)

    shifted = _candidate("long", 401, 405)
    state._apply_candidate("VAL", shifted, state.open_ns + 2, 2)
    replacement = state.lineages["VAL"]
    assert replacement is not None
    assert replacement.lineage_id != first.lineage_id
    assert replacement.eligible_event_index == 2
    assert replacement.eligible_at_ns == state.open_ns + 2
    assert replacement.visit is None
    assert state.diagnostics["aoi_fingerprint_resets"] == 1


def test_event_that_changes_exact_aoi_cannot_also_be_its_tap():
    session = _session(prices=(101.25, 101.0), offsets_ms=(0, 1))
    state = _state(session)
    _ingest(state, session)
    original = _candidate("long", 400, 404)
    state._apply_candidate("VAL", original, int(state.timestamp_ns[0]), 0)
    updated = AoiCandidate(
        "VAL",
        "long",
        400,
        400,
        404,
        ("market",),
        (ConfluencePoint("market", "ORH", 400, 400, 400),),
    )

    state._apply_candidate("VAL", updated, int(state.timestamp_ns[1]), 1)
    lineage = state.lineages["VAL"]
    assert lineage is not None
    state._update_visit_and_order(lineage, 1)

    assert lineage.eligible_event_index == 1
    assert lineage.visit is None


def test_tapped_aoi_freezes_and_invalidates_when_developing_anchor_leaves_box():
    state = _state()
    frozen = _candidate("long", 400, 404)
    lineage = AoiLineage(1, frozen, state.open_ns, 0, visit=Visit(state.open_ns + 1, 1, 400, 404))
    state.lineages["VAL"] = lineage
    state.lineage_counter = lineage.lineage_id
    state.current_profile = {"val_tick": 402, "vah_tick": 420, "poc_tick": 410}
    replacement = _candidate("long", 401, 405)
    state._apply_candidate("VAL", replacement, state.open_ns + 2, 2)
    assert state.lineages["VAL"].candidate == frozen

    state.current_profile["val_tick"] = 399
    new_candidate = _candidate("long", 399, 403)
    state._apply_candidate("VAL", new_candidate, state.open_ns + 3, 3)
    rebuilt = state.lineages["VAL"]
    assert rebuilt is not None
    assert rebuilt.lineage_id != lineage.lineage_id
    assert rebuilt.candidate == new_candidate
    assert rebuilt.eligible_event_index == 3
    assert rebuilt.visit is None
    assert state.diagnostics["aoi_anchor_invalidations"] == 1


def _fillable_state(midpoint_vah=424, event_tick=406):
    state = _state()
    state.event_count = 2
    state.price_ticks[:2] = [405, event_tick]
    state.timestamp_ns[:2] = [state.open_ns, state.open_ns + 1]
    state.cumulative_low[:2] = [390, 390]
    state.cumulative_high[:2] = [430, 430]
    state.current_profile = {"val_tick": 400, "vah_tick": midpoint_vah, "poc_tick": 410}
    candidate = _candidate("long", 400, 404)
    visit = Visit(state.open_ns + 1, 1, 400, 404)
    pending = PendingOrder("big_trade_100ms", state.open_ns + 1, 1, state.open_ns + 1, 1, 406, 398, 400)
    lineage = AoiLineage(2, candidate, state.open_ns, 0, visit=visit, pending=pending)
    state.reversals["VAL"].append(Visit(state.open_ns, 0, 400, 404, state.open_ns + 1))
    return state, lineage


def test_fill_gate_requires_midpoint_strictly_more_than_1_25_points_and_caps_gap_risk():
    too_close, lineage = _fillable_state(midpoint_vah=424, event_tick=406)  # midpoint 412; exactly 5 ticks from fill
    assert not too_close._fill_gate_passes(1, lineage)
    assert too_close.diagnostics["midpoint_distance_rejections"] == 1

    valid, lineage = _fillable_state(midpoint_vah=426, event_tick=406)
    assert valid._fill_gate_passes(1, lineage)
    assert lineage.pending.stop_tick == 398  # two points from the 406 entry trigger

    gapped, lineage = _fillable_state(midpoint_vah=460, event_tick=420)
    assert not gapped._fill_gate_passes(1, lineage)
    assert gapped.diagnostics["stop_limit_rejections"] == 1


def test_order_stop_is_farther_of_opposite_edge_buffer_or_two_points_from_entry():
    session = _session(prices=(100.0, 100.0), offsets_ms=(0, 1))
    state = _state(session)
    _ingest(state, session)
    candidate = _candidate("long", 400, 400)
    lineage = AoiLineage(
        1,
        candidate,
        state.open_ns - 1,
        -1,
        visit=Visit(state.open_ns, 0, 400, 400),
    )
    state._qualifying_entry_bubble = lambda *_: {
        "kind": "big_trade_100ms",
        "qualified_at_ns": state.open_ns + 1,
        "qualified_event_index": 1,
        "price_tick": 400,
        "value": 201,
    }
    state._preorder_range_gate = lambda *_: True

    state._update_visit_and_order(lineage, 1)

    assert lineage.pending is not None
    assert lineage.pending.entry_tick == 402
    assert lineage.pending.stop_tick == 394


def test_last_net_losing_trade_blocks_only_same_direction():
    strategy = YushOrderflowRangeEventStrategy()
    strategy.state = _state()
    strategy.on_position_closed(SimpleNamespace(direction="long"), {"net_pnl": -10.0}, None)
    assert strategy.state.required_direction == "short"
    strategy.on_position_closed(SimpleNamespace(direction="short"), {"net_pnl": 20.0}, None)
    assert strategy.state.required_direction is None


def test_management_freezes_entry_midpoint_and_uses_immediate_target_fill_if_already_crossed():
    strategy = YushOrderflowRangeEventStrategy()
    strategy.state = _state()
    strategy.state.current_profile = {"val_tick": 400, "vah_tick": 420, "poc_tick": 410}
    position = SimpleNamespace(
        direction="long",
        entry_reference_tick=402,
        entry_price=100.75,
        report_fields={"midpoint_activated": False, "entry_midpoint_tick": 410.0},
    )
    event = CanonicalEvent(
        event_index=10,
        timestamp=pd.Timestamp("2026-05-04 09:45:00", tz="America/New_York"),
        timestamp_ns=int(pd.Timestamp("2026-05-04 09:45:00", tz="America/New_York").value),
        price_tick=421,
    )
    directive = strategy.position_directive(event, position, None)
    assert directive.immediate_target_tick == 420
    assert directive.report_fields["midpoint_activated"] is True
