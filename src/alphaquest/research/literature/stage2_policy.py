"""Pure initial-Stage-2 admission and search-publication planning.

This is execution policy, not a canonical contract or a live executor. Inputs
are the exact protocol and the complete, validated search-history projection
for that protocol. The store still owns validation and durable publication.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal, TypeVar

from .contracts import (
    CanonicalRecordV1,
    LiteratureError,
    ResearchProtocolRevisionV1,
    SearchCaptureAttemptV1,
    SearchRunRevisionV1,
    canonical_json_bytes,
    intent_sha256,
)
from .store import LiteratureStore, _record_intent_material


class Stage2UnsupportedProfile(ValueError):
    """A valid canonical protocol is unsupported by the initial executor."""


@dataclass(frozen=True)
class Stage2ProviderAttempt:
    lane: str
    query: str
    provider_id: str
    provider_attempt_ordinal: int


@dataclass(frozen=True)
class Stage2AdmissionResult:
    protocol_revision_sha256: str
    attempts: tuple[Stage2ProviderAttempt, ...]
    # Execution policy only; not a field added to a canonical methodology.
    external_concurrency: Literal[1] = 1


@dataclass(frozen=True)
class Stage2SearchProposal:
    """Exact STARTED/terminal pair, including inspected results and selections.

    The first STARTED must already be in the validated history. Later pairs
    are hypothetical serial steps, not permission to dispatch them early.
    Terminal records are proposals; this module never publishes them.
    """

    started: SearchRunRevisionV1
    terminal: SearchRunRevisionV1


@dataclass(frozen=True)
class Stage2PublicationStep:
    search_run_id: str
    provider_id: str
    started_record_sha256: str
    # Bytes avoid retaining shallowly frozen canonical models with mutable lists.
    terminal_record_json: bytes


@dataclass(frozen=True)
class Stage2PublicationPlan:
    status: Literal["CAPTURE_RETRIEVAL_ALLOWED", "UNSUPPORTED_PUBLICATION_SCHEDULE"]
    protocol_revision_sha256: str
    search_history_sha256: str
    steps: tuple[Stage2PublicationStep, ...] = ()
    # Permission concerns ONLY the already-STARTED first step's exact captures.
    next_capture_attempts: tuple[SearchCaptureAttemptV1, ...] = ()
    reason: str | None = None


class _CanonicalSearchValidator:
    """Bind the existing pure search validator without constructing a store.

    Only its two static dependencies are exposed. No filesystem, P2, or other
    store capability is available here. Canonical search semantics are reused
    unchanged, with full-store parity tested at each proposed publication.
    """

    _current_searches = staticmethod(LiteratureStore._current_searches)
    _validate_lane_search_proof = staticmethod(LiteratureStore._validate_lane_search_proof)
    validate = LiteratureStore._validate_protocol_search_history


R = TypeVar("R", bound=CanonicalRecordV1)


def _exact_copy(record: R, expected: type[R]) -> R:
    if type(record) is not expected:
        raise ValueError(f"expected exact {expected.__name__} record")
    copied = expected.model_validate_json(canonical_json_bytes(record))
    if copied.intent_sha256 != intent_sha256(_record_intent_material(copied)):
        raise ValueError("canonical record intent hash mismatch")
    return copied


def admit_protocol(protocol: ResearchProtocolRevisionV1) -> Stage2AdmissionResult:
    """Admit an exact canonical revision without changing its methodology."""
    try:
        protocol = _exact_copy(protocol, ResearchProtocolRevisionV1)
    except (TypeError, ValueError) as exc:
        raise Stage2UnsupportedProfile(f"invalid exact protocol: {exc}") from exc
    if protocol.lineage_kind != "PRE_RESULT_PROTOCOL":
        raise Stage2UnsupportedProfile("initial Stage 2 requires PRE_RESULT_PROTOCOL")
    for lane in protocol.lanes:
        if (
            len(lane.required_initial_queries) != 1
            or lane.maximum_queries != 1
            or lane.adaptive_max_depth != 0
            or (lane.saturation is not None and lane.saturation.enabled)
        ):
            raise Stage2UnsupportedProfile(
                f"{lane.lane}: require one initial query, maximum_queries=1, "
                "adaptive_max_depth=0, and disabled saturation"
            )
    return Stage2AdmissionResult(
        protocol.record_sha256,
        tuple(
            Stage2ProviderAttempt(lane.lane, lane.required_initial_queries[0], provider, rank)
            for lane in protocol.lanes
            for rank, provider in enumerate(lane.provider_order, 1)
        ),
    )


def _validate_sequence(
    protocol: ResearchProtocolRevisionV1,
    admission: Stage2AdmissionResult,
    searches: tuple[SearchRunRevisionV1, ...],
) -> SearchRunRevisionV1 | None:
    """Check serial execution policy and replay every canonical search prefix."""
    validator = _CanonicalSearchValidator()
    records: list[CanonicalRecordV1] = [protocol]
    active: SearchRunRevisionV1 | None = None
    cursor = 0
    seen_ids = {protocol.record_id}
    seen_keys = {protocol.idempotency_key}
    for search in searches:
        if search.append_sequence <= records[-1].append_sequence:
            raise ValueError("search history must retain canonical append order")
        # Other canonical families can occur between these projected records.
        if (
            search.append_sequence == records[-1].append_sequence + 1
            and search.previous_store_record_sha256 != records[-1].record_sha256
        ):
            raise ValueError("adjacent canonical predecessor hash mismatch")
        if search.record_id in seen_ids or search.idempotency_key in seen_keys:
            raise ValueError("duplicate search record or idempotency key")
        seen_ids.add(search.record_id)
        seen_keys.add(search.idempotency_key)
        if search.protocol_revision_sha256 != protocol.record_sha256:
            raise ValueError("search must bind the exact admitted protocol revision")
        if search.query_kind != "INITIAL" or search.adaptive_depth != 0:
            raise ValueError("initial Stage 2 prohibits adaptive query execution")
        if search.revision == 1:
            if active is not None:
                raise ValueError("external concurrency=1: terminalize the current provider first")
            if cursor >= len(admission.attempts):
                raise ValueError("search exceeds the frozen execution plan")
            expected = admission.attempts[cursor]
            actual = Stage2ProviderAttempt(
                search.lane, search.query, search.provider_id, search.provider_attempt_ordinal
            )
            if actual != expected:
                raise ValueError("search does not follow the frozen lane/query/provider execution order")
            active = search
        else:
            if active is None or search.search_run_id != active.search_run_id:
                raise ValueError("terminal search is not the current serial provider attempt")
            if search.previous_revision_sha256 != active.record_sha256:
                raise ValueError("terminal search predecessor does not match exact STARTED revision")
            active = None
            cursor += 1
        records.append(search)
        validator.validate(records)
    return active


def plan_publication(
    protocol: ResearchProtocolRevisionV1,
    search_history: tuple[SearchRunRevisionV1, ...],
    proposals: tuple[Stage2SearchProposal, ...],
) -> Stage2PublicationPlan:
    """Check all proposed prefixes before allowing the next capture selection.

    Search history is the complete ordered projection from a currently validated
    canonical snapshot for this exact protocol, not arbitrary worker testimony.
    Later STARTED/terminal pairs are simulated in frozen serial order. Any failed
    step rejects the entire plan and returns no capture identities or steps.

    This is an F4 ordering decision for the exact inputs, not a durable token,
    resource/retention approval, or permission for external execution. A changed
    snapshot/outcome requires replanning. After the first terminal is published,
    read fresh history and plan again before any later provider's retrieval.
    """
    admission = admit_protocol(protocol)
    protocol = _exact_copy(protocol, ResearchProtocolRevisionV1)
    history_hash = hashlib.sha256(canonical_json_bytes(search_history)).hexdigest()
    try:
        history = tuple(_exact_copy(item, SearchRunRevisionV1) for item in search_history)
        active = _validate_sequence(protocol, admission, history)
        if not proposals:
            raise ValueError("no known terminal outcome to authorize")
        if active is None:
            raise ValueError("the next search must already have a canonical STARTED revision")
        steps: list[Stage2PublicationStep] = []
        next_captures: tuple[SearchCaptureAttemptV1, ...] = ()
        for index, proposal in enumerate(proposals):
            if type(proposal) is not Stage2SearchProposal:
                raise ValueError("expected a typed Stage2SearchProposal")
            started = _exact_copy(proposal.started, SearchRunRevisionV1)
            terminal = _exact_copy(proposal.terminal, SearchRunRevisionV1)
            if started.status != "STARTED" or terminal.status == "STARTED":
                raise ValueError("proposal must contain a STARTED and terminal pair")
            if index == 0:
                if canonical_json_bytes(started) != canonical_json_bytes(active):
                    raise ValueError("first proposal must match the current exact STARTED revision")
            else:
                history = (*history, started)
                _validate_sequence(protocol, admission, history)
            history = (*history, terminal)
            _validate_sequence(protocol, admission, history)
            steps.append(
                Stage2PublicationStep(
                    terminal.search_run_id,
                    terminal.provider_id,
                    started.record_sha256,
                    canonical_json_bytes(terminal),
                )
            )
            if index == 0:
                next_captures = tuple(terminal.capture_attempt_records)
        return Stage2PublicationPlan(
            "CAPTURE_RETRIEVAL_ALLOWED",
            admission.protocol_revision_sha256,
            history_hash,
            tuple(steps),
            next_captures,
        )
    except (LiteratureError, TypeError, ValueError) as exc:
        return Stage2PublicationPlan(
            "UNSUPPORTED_PUBLICATION_SCHEDULE",
            admission.protocol_revision_sha256,
            history_hash,
            reason=str(exc),
        )
