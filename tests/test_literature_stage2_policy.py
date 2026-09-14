from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import itertools
from pathlib import Path
import socket
import subprocess

import pytest

from alphaquest.research.literature.contracts import (
    LiteratureIntegrityError,
    ResearchProtocolRevisionV1,
    SearchRunRevisionV1,
    canonical_json_bytes,
    intent_sha256,
    methodology_sha256,
    record_sha256,
)
from alphaquest.research.literature import stage2_policy as policy
from alphaquest.research.literature.store import LiteratureStore, _record_intent_material
from tests.test_literature_stage1 import _actor, _project, _protocol_payload, _search_result, NOW


def _record(cls, payload, previous=None):
    material = dict(payload)
    material.update(
        {
            "schema": cls.schema_literal,
            "append_sequence": previous.append_sequence + 1 if previous else 1,
            "previous_store_record_sha256": previous.record_sha256 if previous else None,
            "recorded_at": NOW,
            "actor": _actor().model_dump(mode="json"),
            "idempotency_key": material["record_id"],
            "intent_sha256": "0" * 64,
        }
    )
    material["record_sha256"] = record_sha256(material)
    provisional = cls.model_validate_json(canonical_json_bytes(material))
    material["intent_sha256"] = intent_sha256(_record_intent_material(provisional))
    material["record_sha256"] = record_sha256(material)
    return cls.model_validate_json(canonical_json_bytes(material))


def _protocol(providers=2, **first_lane):
    payload = _protocol_payload()
    for lane in payload["lanes"]:
        lane.update(
            provider_order=[f"provider.{i}" for i in range(1, providers + 1)],
            maximum_queries=1,
            adaptive_max_depth=0,
            saturation=None,
            minimum_capture_attempts=0,
            minimum_distinct_results_inspected=0,
            minimum_results_inspected_per_query=0,
            maximum_results=30,
            maximum_captures=10,
        )
    payload["lanes"][0].update(first_lane)
    payload.update(record_id="protocol.fixture.r000001", revision=1, previous_revision_sha256=None)
    payload["methodology_sha256"] = methodology_sha256(payload)
    return _record(ResearchProtocolRevisionV1, payload)


def _inspection(name, provider=1, rank=1, *, work=None):
    item = _search_result(f"https://synthetic.invalid/{name}", provider_rank=provider, result_rank=rank)
    if work is not None:
        item["work_identity_sha256"] = hashlib.sha256(work.encode()).hexdigest()
        item["result_identity_sha256"] = hashlib.sha256(
            canonical_json_bytes(
                {
                    "canonical_locator": item["canonical_locator"],
                    "work_identity_sha256": item["work_identity_sha256"],
                },
                trailing_lf=False,
            )
        ).hexdigest()
    return item


def _outcome(results=(), captures=(), status="SUCCEEDED"):
    return {
        "status": status,
        "inspected_results": list(results),
        "capture_attempt_records": [
            {
                "capture_attempt_id": f'capture.{item["provider_rank"]}.{ordinal}',
                "result_identity_sha256": item["result_identity_sha256"],
                "selection_ordinal": ordinal,
            }
            for ordinal, item in captures
        ],
        "bytes_retrieved": 0,
        "elapsed_seconds": 1,
        "saturation_claimed": False,
        "provider_trace_completeness": "PARTIAL_PROVIDER_TRACE" if status == "PARTIAL" else "COMPLETE_FOR_REQUEST",
        "failure_reason": "synthetic provider failure" if status in {"FAILED", "ABANDONED_AFTER_CRASH"} else None,
    }


def _proposals(protocol, outcomes):
    attempts = policy.admit_protocol(protocol).attempts
    previous = protocol
    proposals = []
    for i, (attempt, outcome) in enumerate(zip(attempts, outcomes, strict=False)):
        payload = {
            "search_run_id": f"search.{i}",
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": attempt.lane,
            "query": attempt.query,
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": attempt.provider_id,
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        }
        started = _record(
            SearchRunRevisionV1,
            LiteratureStore._started_search_material(
                payload, provider_attempt_ordinal=attempt.provider_attempt_ordinal
            ),
            previous,
        )
        terminal = _record(SearchRunRevisionV1, LiteratureStore._terminal_search_material(started, outcome), started)
        proposals.append(policy.Stage2SearchProposal(started, terminal))
        previous = terminal
    return tuple(proposals)


def _plan(protocol, proposals):
    return policy.plan_publication(protocol, (proposals[0].started,), proposals)


def _assert_rejected(plan, match=None):
    assert plan.status == "UNSUPPORTED_PUBLICATION_SCHEDULE"
    assert not plan.steps and not plan.next_capture_attempts
    assert plan.reason
    if match:
        assert match in plan.reason


@pytest.fixture
def store(tmp_path):
    return LiteratureStore(_project(tmp_path))


def _publish_protocol(store, protocol):
    actual = store.append_protocol(
        _record_intent_material(protocol), actor=_actor(), idempotency_key=protocol.idempotency_key, recorded_at=NOW
    )
    assert actual == protocol


def _publish_start(store, proposal):
    actual = store.start_search(
        _record_intent_material(proposal.started),
        actor=_actor(),
        idempotency_key=proposal.started.idempotency_key,
        recorded_at=NOW,
    )
    assert actual == proposal.started


def _publish_terminal(store, proposal):
    payload = {key: getattr(proposal.terminal, key) for key in _outcome()}
    actual = store.finish_search(
        proposal.started.search_run_id,
        payload,
        actor=_actor(),
        idempotency_key=proposal.terminal.idempotency_key,
        recorded_at=NOW,
    )
    assert actual == proposal.terminal


def _assert_prefix_parity(store, protocol, proposals):
    records = [protocol]
    for proposal in proposals:
        records.append(proposal.started)
        assert store._validate_cross_record_state(records) is None
        records.append(proposal.terminal)
        assert store._validate_cross_record_state(records) is None
        store._validate_protocol_search_history(records)


@pytest.mark.parametrize("providers", [1, 2, 3])
def test_admission_exact_frozen_order_and_seven_lanes(providers):
    protocol = _protocol(providers)
    before = canonical_json_bytes(protocol)
    admitted = policy.admit_protocol(protocol)
    assert admitted.external_concurrency == 1
    assert len(admitted.attempts) == 7 * providers
    assert [(x.lane, x.query, x.provider_id, x.provider_attempt_ordinal) for x in admitted.attempts] == [
        (lane.lane, lane.required_initial_queries[0], provider, rank)
        for lane in protocol.lanes
        for rank, provider in enumerate(lane.provider_order, 1)
    ]
    assert canonical_json_bytes(protocol) == before


@pytest.mark.parametrize(
    "change",
    [
        {"required_initial_queries": ["one", "two"], "maximum_queries": 2},
        {"maximum_queries": 2},
        {"adaptive_max_depth": 1},
        {"saturation": {"enabled": True, "minimum_queries_before_check": 1, "consecutive_queries_without_new_work": 1}},
    ],
)
def test_reject_unsupported_canonical_profile_without_mutation(change):
    protocol = _protocol(**change)
    before = canonical_json_bytes(protocol)
    with pytest.raises(policy.Stage2UnsupportedProfile):
        policy.admit_protocol(protocol)
    assert ResearchProtocolRevisionV1.model_validate_json(before) == protocol
    assert canonical_json_bytes(protocol) == before


def test_reject_extension_lineage_without_invalidating_canonical_contract():
    material = _record_intent_material(_protocol())
    material.update(
        lineage_kind="RESULT_INFORMED_EXTENSION",
        parent_execution_lineage_id="parent",
        observed_result_set_sha256="a" * 64,
        revision=1,
        previous_revision_sha256=None,
        record_id="protocol.fixture.r000001",
    )
    material["methodology_sha256"] = methodology_sha256(material)
    protocol = _record(ResearchProtocolRevisionV1, material)
    with pytest.raises(policy.Stage2UnsupportedProfile, match="PRE_RESULT_PROTOCOL"):
        policy.admit_protocol(protocol)


def test_reject_loose_dictionary_and_hash_drift():
    protocol = _protocol()
    with pytest.raises(policy.Stage2UnsupportedProfile):
        policy.admit_protocol(protocol.model_dump(mode="json"))
    protocol.lanes[0].provider_order.reverse()
    with pytest.raises(policy.Stage2UnsupportedProfile, match="invalid exact protocol"):
        policy.admit_protocol(protocol)


def test_explicit_disabled_saturation_is_supported():
    policy.admit_protocol(
        _protocol(
            saturation={
                "enabled": False,
                "minimum_queries_before_check": 1,
                "consecutive_queries_without_new_work": 1,
            }
        )
    )


@pytest.mark.parametrize("providers", [1, 2, 3])
@pytest.mark.parametrize("first_status", ["SUCCEEDED", "PARTIAL", "FAILED", "ABANDONED_AFTER_CRASH"])
def test_serial_public_append_and_replanning_parity(store, providers, first_status):
    protocol = _protocol(providers, minimum_capture_attempts=1)
    outcomes = []
    ordinal = 0
    for i in range(providers):
        status = first_status if i == 0 else "SUCCEEDED"
        item = _inspection(f"result.{i}", i + 1)
        captures = []
        if status in {"SUCCEEDED", "PARTIAL"}:
            ordinal += 1
            captures = [(ordinal, item)]
        outcomes.append(_outcome([item], captures, status))
    proposals = _proposals(protocol, outcomes)
    _assert_prefix_parity(store, protocol, proposals)
    _publish_protocol(store, protocol)
    history = []
    for i, proposal in enumerate(proposals):
        _publish_start(store, proposal)
        history.append(proposal.started)
        plan = policy.plan_publication(protocol, tuple(history), proposals[i:])
        assert plan.status == "CAPTURE_RETRIEVAL_ALLOWED"
        assert plan.next_capture_attempts == tuple(proposal.terminal.capture_attempt_records)
        assert len(plan.steps) == len(proposals) - i
        _publish_terminal(store, proposal)
        history.append(proposal.terminal)
        store.validate(verify_artifacts=False)


@pytest.mark.parametrize("first_has_results", [False, True])
def test_zero_captures_later_provider_can_supply_minimum(store, first_has_results):
    protocol = _protocol(minimum_capture_attempts=1, maximum_captures=1)
    first = _inspection("duplicate", 1)
    # When first leaves an inspected result uncaptured, the next capture must
    # cover that same prefix identity. A different later result cannot fill it.
    second = _inspection("duplicate" if first_has_results else "new", 2)
    proposals = _proposals(
        protocol,
        [
            _outcome([first] if first_has_results else []),
            _outcome([second], [(1, second)]),
        ],
    )
    assert _plan(protocol, proposals).status == "CAPTURE_RETRIEVAL_ALLOWED"
    _assert_prefix_parity(store, protocol, proposals)
    assert store._validate_lane_search_proof(protocol.lanes[0], [p.terminal for p in proposals])


def test_missing_earlier_identity_cannot_be_skipped_for_later_minima():
    protocol = _protocol(minimum_capture_attempts=1)
    first, second = _inspection("old", 1), _inspection("new", 2)
    proposals = _proposals(protocol, [_outcome([first]), _outcome([second], [(1, second)])])
    _assert_rejected(_plan(protocol, proposals), "deterministic selection rule")
    # The known first outcome itself can terminalize with a declared shortfall.
    assert _plan(protocol, proposals[:1]).status == "CAPTURE_RETRIEVAL_ALLOWED"


@pytest.mark.parametrize("interaction", ["duplicate", "same-work", "same-locator", "reverse-hash"])
def test_result_identity_interactions_preserve_prior_prefix(store, interaction):
    protocol = _protocol()
    first = _inspection("z", 1, work="shared")
    if interaction == "duplicate":
        second = _inspection("z", 2, work="shared")
        second_captures = []
    else:
        second = _inspection(
            "z" if interaction == "same-locator" else "a",
            2,
            work="different" if interaction == "same-locator" else "shared",
        )
        if interaction == "reverse-hash":
            options = [_inspection(str(i), 2) for i in range(100)]
            second = min(options, key=lambda x: x["locator_sha256"])
            assert second["locator_sha256"] < first["locator_sha256"]
        second_captures = [(2, second)]
    proposals = _proposals(protocol, [_outcome([first], [(1, first)]), _outcome([second], second_captures)])
    assert _plan(protocol, proposals).status == "CAPTURE_RETRIEVAL_ALLOWED"
    _assert_prefix_parity(store, protocol, proposals)


@pytest.mark.parametrize("maximum,selected,expected", [(0, 0, True), (1, 1, True), (2, 2, True), (1, 2, False)])
def test_capture_bounds_and_fewer_than_minimum_results(store, maximum, selected, expected):
    protocol = _protocol(
        1, maximum_captures=maximum, minimum_capture_attempts=maximum, minimum_distinct_results_inspected=10
    )
    results = [_inspection(str(i), 1, i + 1) for i in range(3)]
    proposals = _proposals(protocol, [_outcome(results, list(enumerate(results[:selected], 1)))])
    plan = _plan(protocol, proposals)
    if expected:
        assert plan.status == "CAPTURE_RETRIEVAL_ALLOWED"
        _assert_prefix_parity(store, protocol, proposals)
        assert not store._validate_lane_search_proof(protocol.lanes[0], [proposals[0].terminal])
    else:
        _assert_rejected(plan, "capture budget")


def test_unrestricted_f4_and_restricted_duplicate_f4_are_rejected_before_retrieval(store):
    for restricted in (False, True):
        protocol = _protocol(2 if restricted else 1, minimum_capture_attempts=4, minimum_distinct_results_inspected=4)
        if not restricted:
            material = _record_intent_material(protocol)
            material.update(record_id=protocol.record_id, revision=1, previous_revision_sha256=None)
            material["lanes"][0].update(required_initial_queries=["query.a", "query.b"], maximum_queries=2)
            material["methodology_sha256"] = methodology_sha256(material)
            protocol = _record(ResearchProtocolRevisionV1, material)
        locators = sorted(range(8), key=lambda i: _inspection(str(i))["locator_sha256"])
        a = [_inspection(str(locators[i]), 1, i + 1) for i in range(3)]
        if restricted:
            b = [_inspection(str(locators[1]), 2), _inspection(str(locators[3]), 2, 2)]
            a_captures = [(1, a[0]), (3, a[2])]
            proposals = _proposals(protocol, [_outcome(a, a_captures), _outcome(b, [(2, b[0]), (4, b[1])])])
        else:
            # One provider, two queries; locator hashes interleave equal result ranks.
            a = [_inspection(str(locators[0]), 1, 1), _inspection(str(locators[2]), 1, 2)]
            b = [_inspection(str(locators[1]), 1, 1), _inspection(str(locators[3]), 1, 2)]
            proposals = []
            previous = protocol
            for i, (results, ordinals) in enumerate([(a, [1, 3]), (b, [2, 4])]):
                started = _record(
                    SearchRunRevisionV1,
                    LiteratureStore._started_search_material(
                        {
                            "search_run_id": f"search.{i}",
                            "protocol_id": protocol.protocol_id,
                            "protocol_revision_sha256": protocol.record_sha256,
                            "execution_lineage_id": protocol.execution_lineage_id,
                            "lane": protocol.lanes[0].lane,
                            "query": protocol.lanes[0].required_initial_queries[i],
                            "query_kind": "INITIAL",
                            "adaptive_depth": 0,
                            "parent_search_run_id": None,
                            "provider_id": "provider.1",
                            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
                        },
                        provider_attempt_ordinal=1,
                    ),
                    previous,
                )
                terminal = _record(
                    SearchRunRevisionV1,
                    LiteratureStore._terminal_search_material(
                        started, _outcome(results, list(zip(ordinals, results, strict=True)))
                    ),
                    started,
                )
                proposals.append(policy.Stage2SearchProposal(started, terminal))
                previous = terminal
            proposals = tuple(proposals)
        combined = [protocol, *(r for p in proposals for r in (p.started, p.terminal))]
        assert store._validate_cross_record_state(combined) is None
        assert store._validate_lane_search_proof(protocol.lanes[0], [p.terminal for p in proposals])
        for i in range(2):
            prefix = [protocol, *(p.started for p in proposals), proposals[i].terminal]
            with pytest.raises(LiteratureIntegrityError, match="capture selection ordinals"):
                store._validate_cross_record_state(prefix)
        retrievals = []
        if restricted:
            plan = _plan(protocol, proposals)
            if plan.status == "CAPTURE_RETRIEVAL_ALLOWED":
                retrievals.extend(plan.next_capture_attempts)
            _assert_rejected(plan, "capture selection ordinals")
        else:
            with pytest.raises(policy.Stage2UnsupportedProfile):
                _plan(protocol, proposals)
        assert retrievals == []


def test_generated_prefix_implication_against_full_store_validator(store):
    # 432 deterministic combinations, including duplicate ownership, partial/
    # failed outcomes, omitted selections, rank overlap, and capture ceilings.
    approved = rejected = 0
    for statuses, selections, maximum in itertools.product(
        itertools.product(["SUCCEEDED", "PARTIAL", "FAILED"], repeat=3),
        itertools.product([False, True], repeat=3),
        [1, 3],
    ):
        protocol = _protocol(3, maximum_captures=maximum)
        results = [[_inspection("shared", 1)], [_inspection("shared", 2)], [_inspection("later", 3)]]
        eligible = [r[0] for r, status in zip(results, statuses) if status != "FAILED"]
        identity_order = list(dict.fromkeys(x["result_identity_sha256"] for x in eligible))
        outcomes = []
        for r, status, select in zip(results, statuses, selections):
            captures = []
            if select and status != "FAILED":
                captures = [(identity_order.index(r[0]["result_identity_sha256"]) + 1, r[0])]
            outcomes.append(_outcome(r, captures, status))
        proposals = _proposals(protocol, outcomes)
        plan = _plan(protocol, proposals)
        try:
            _assert_prefix_parity(store, protocol, proposals)
        except LiteratureIntegrityError:
            rejected += 1
            _assert_rejected(plan)
        else:
            approved += 1
            assert plan.status == "CAPTURE_RETRIEVAL_ALLOWED"
    assert approved > 0 and rejected > 0 and approved + rejected == 432


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("reorder", "current exact STARTED"),
        ("concurrent", "concurrency=1"),
        ("missing-start", "already have a canonical STARTED"),
        ("stale-terminal", "record_sha256"),
        ("wrong-parent", "predecessor"),
        ("wrong-query", "frozen lane/query/provider"),
        ("reverse-provider", "frozen lane/query/provider"),
        ("partial-history", "frozen lane/query/provider"),
    ],
)
def test_fail_closed_order_history_and_identity(mutation, match):
    protocol = _protocol()
    proposals = _proposals(protocol, [_outcome(), _outcome()])
    history = (proposals[0].started,)
    if mutation == "reorder":
        proposals = proposals[::-1]
    elif mutation == "concurrent":
        history = (proposals[0].started, proposals[1].started)
    elif mutation == "missing-start":
        history = ()
    elif mutation == "partial-history":
        history = (proposals[1].started,)
        proposals = proposals[1:]
    elif mutation == "stale-terminal":
        bad = proposals[0].terminal.model_copy(update={"bytes_retrieved": 100})
        proposals = (replace(proposals[0], terminal=bad),)
    else:
        started, terminal = proposals[0].started, proposals[0].terminal
        if mutation == "wrong-parent":
            material = terminal.model_dump(mode="json", by_alias=True)
            material["previous_revision_sha256"] = protocol.record_sha256
            terminal = _record(SearchRunRevisionV1, material, started)
        else:
            material = started.model_dump(mode="json", by_alias=True)
            material["query" if mutation == "wrong-query" else "provider_id"] = "not-frozen"
            started = _record(SearchRunRevisionV1, material, protocol)
            terminal = _record(
                SearchRunRevisionV1, LiteratureStore._terminal_search_material(started, _outcome()), started
            )
            history = (started,)
        proposals = (policy.Stage2SearchProposal(started, terminal),)
    _assert_rejected(policy.plan_publication(protocol, history, proposals), match)


def test_adaptive_search_and_false_saturation_rejected():
    protocol = _protocol()
    proposals = _proposals(protocol, [_outcome()])
    started = proposals[0].started
    material = started.model_dump(mode="json", by_alias=True)
    material.update(query_kind="ADAPTIVE", adaptive_depth=1, parent_search_run_id="search.parent")
    bad_start = _record(SearchRunRevisionV1, material, protocol)
    _assert_rejected(policy.plan_publication(protocol, (bad_start,), proposals), "adaptive")
    terminal = _record(
        SearchRunRevisionV1,
        LiteratureStore._terminal_search_material(started, {**_outcome(), "saturation_claimed": True}),
        started,
    )
    _assert_rejected(_plan(protocol, (policy.Stage2SearchProposal(started, terminal),)), "saturation")


def test_no_network_files_credentials_or_worker_and_pnl_noninterference(tmp_path, monkeypatch):
    protocol = _protocol()
    item = _inspection("first")
    proposals = _proposals(protocol, [_outcome([item], [(1, item)])])
    expected = _plan(protocol, proposals)
    for outcome in ["PASS", "FAIL", "NEEDS MANUAL REVIEW"]:
        (tmp_path / "unrelated-pnl.csv").write_text(f"verdict,pnl\n{outcome},123456\n")
        monkeypatch.chdir(tmp_path)
        with monkeypatch.context() as blocked:

            def forbidden(*args, **kwargs):
                raise AssertionError("external or repository state accessed")

            blocked.setattr(socket, "socket", forbidden)
            blocked.setattr(socket, "getaddrinfo", forbidden)
            blocked.setattr(subprocess, "Popen", forbidden)
            blocked.setattr("builtins.open", forbidden)
            blocked.setattr(Path, "open", forbidden)
            blocked.setattr("os.getenv", forbidden)
            assert _plan(protocol, proposals) == expected
    tree = ast.parse(Path(policy.__file__).read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"__future__", "dataclasses", "typing", "contracts", "store"}
    assert {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} == {
        "hashlib"
    }


def test_plans_snapshot_mutable_inputs_and_reject_changed_outcomes():
    protocol = _protocol()
    first, second = _inspection("a"), _inspection("b", 2)
    proposals = _proposals(protocol, [_outcome([first], [(1, first)]), _outcome([second], [(2, second)])])
    plan = _plan(protocol, proposals)
    assert plan.status == "CAPTURE_RETRIEVAL_ALLOWED"
    assert [x.selection_ordinal for x in plan.next_capture_attempts] == [1]
    saved = plan.steps[0].terminal_record_json
    proposals[0].terminal.capture_attempt_records.clear()
    assert plan.steps[0].terminal_record_json == saved
    assert [x.selection_ordinal for x in plan.next_capture_attempts] == [1]
    _assert_rejected(_plan(protocol, proposals))


def test_later_invalid_step_withholds_all_current_capture_permission():
    protocol = _protocol()
    first, second = _inspection("a"), _inspection("b", 2)
    proposals = _proposals(protocol, [_outcome([first], [(1, first)]), _outcome([second], [(3, second)])])
    assert _plan(protocol, proposals[:1]).status == "CAPTURE_RETRIEVAL_ALLOWED"
    _assert_rejected(_plan(protocol, proposals), "gap-free")


def test_minimum_capture_obligations_span_three_providers(store):
    protocol = _protocol(3, minimum_provider_attempts=3, minimum_capture_attempts=3, maximum_captures=3)
    outcomes = []
    for i in range(3):
        item = _inspection(str(i), i + 1)
        outcomes.append(_outcome([item], [(i + 1, item)]))
    proposals = _proposals(protocol, outcomes)
    assert _plan(protocol, proposals).status == "CAPTURE_RETRIEVAL_ALLOWED"
    _assert_prefix_parity(store, protocol, proposals)
    for count in (1, 2, 3):
        assert store._validate_lane_search_proof(protocol.lanes[0], [p.terminal for p in proposals[:count]]) == (
            count == 3
        )


def test_all_seven_lanes_and_all_providers_remain_in_execution_plan(store):
    protocol = _protocol(3)
    proposals = _proposals(protocol, [_outcome() for _ in range(21)])
    assert len(proposals) == 21
    plan = _plan(protocol, proposals)
    assert plan.status == "CAPTURE_RETRIEVAL_ALLOWED"
    assert len(plan.steps) == 21
    _assert_prefix_parity(store, protocol, proposals)
    # Skipping the remaining providers in lane one is not allowed.
    _assert_rejected(_plan(protocol, (proposals[0], proposals[3])), "frozen lane/query/provider")


def test_empty_proposals_and_completed_history_cannot_authorize_capture():
    protocol = _protocol(1)
    proposals = _proposals(protocol, [_outcome()])
    _assert_rejected(policy.plan_publication(protocol, (proposals[0].started,), ()), "no known terminal")
    _assert_rejected(
        policy.plan_publication(protocol, (proposals[0].started, proposals[0].terminal), proposals),
        "already have a canonical STARTED",
    )


@pytest.mark.parametrize("bound", ["maximum_results", "maximum_bytes", "maximum_elapsed_seconds"])
def test_known_outcome_exceeding_canonical_budget_is_rejected(bound):
    protocol = _protocol(1, **{bound: 1})
    results = [_inspection("a"), _inspection("b", rank=2)]
    outcome = _outcome(results)
    if bound == "maximum_bytes":
        outcome["bytes_retrieved"] = 2
    if bound == "maximum_elapsed_seconds":
        outcome["elapsed_seconds"] = 2
    _assert_rejected(_plan(protocol, _proposals(protocol, [outcome])), "budget")
