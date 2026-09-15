"""Restricted Stage 2 planning from a trusted, complete canonical store snapshot.

Read-only controller operation; no provider execution or durable reservation.
The existing Stage 1 validators remain the canonical authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import ValidationError

from .contracts import (
    CanonicalRecordV1,
    LiteratureConflictError,
    LiteratureIntegrityError,
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
    snapshot_append_sequence: int
    snapshot_head_record_sha256: str | None
    steps: tuple[Stage2PublicationStep, ...] = ()
    # Permission concerns ONLY the already-STARTED first step's exact captures.
    next_capture_attempts: tuple[SearchCaptureAttemptV1, ...] = ()
    reason: str | None = None


class _UnsupportedProposal(ValueError):
    """An intentionally classified invalid proposal or execution schedule."""


R = TypeVar("R", bound=CanonicalRecordV1)


def _exact_copy(record: R, expected: type[R]) -> R:
    if type(record) is not expected:
        raise _UnsupportedProposal(f"expected exact {expected.__name__} record")
    copied = expected.model_validate_json(canonical_json_bytes(record))
    if copied.intent_sha256 != intent_sha256(_record_intent_material(copied)):
        raise _UnsupportedProposal("canonical record intent hash mismatch")
    return copied


def admit_protocol(protocol: ResearchProtocolRevisionV1) -> Stage2AdmissionResult:
    """Admit an exact canonical revision without changing its methodology."""
    try:
        protocol = _exact_copy(protocol, ResearchProtocolRevisionV1)
    except (_UnsupportedProposal, ValidationError) as exc:
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
    """Check execution policy only; canonical authority sees the full snapshot."""
    active: SearchRunRevisionV1 | None = None
    cursor = 0
    for search in searches:
        if search.protocol_revision_sha256 != protocol.record_sha256:
            raise _UnsupportedProposal("search must bind the exact admitted protocol revision")
        if search.query_kind != "INITIAL" or search.adaptive_depth != 0:
            raise _UnsupportedProposal("initial Stage 2 prohibits adaptive query execution")
        if search.revision == 1:
            if active is not None:
                raise _UnsupportedProposal("external concurrency=1: terminalize the current provider first")
            if cursor >= len(admission.attempts):
                raise _UnsupportedProposal("search exceeds the frozen execution plan")
            expected = admission.attempts[cursor]
            actual = Stage2ProviderAttempt(
                search.lane, search.query, search.provider_id, search.provider_attempt_ordinal
            )
            if actual != expected:
                raise _UnsupportedProposal("search does not follow the frozen lane/query/provider execution order")
            active = search
        else:
            if active is None or search.search_run_id != active.search_run_id:
                raise _UnsupportedProposal("terminal search is not the current serial provider attempt")
            if search.previous_revision_sha256 != active.record_sha256:
                raise _UnsupportedProposal("terminal search predecessor does not match exact STARTED revision")
            active = None
            cursor += 1
    return active


def plan_publication(
    store: LiteratureStore,
    protocol_revision_sha256: str,
    proposals: tuple[Stage2SearchProposal, ...],
) -> Stage2PublicationPlan:
    """Simulate publication against complete trusted canonical state.

    Only the controller supplies the store and converts bounded provider results
    into proposals. Persisted validation failures propagate before proposal
    classification begins. Every simulated append uses the existing global and
    cross-record validators. No canonical files are written.

    Permission covers only the current STARTED step and becomes stale after any
    canonical append. Snapshot identity is evidence, not an F3 reservation.
    """
    with store.lock(exclusive=False):
        records = store._load_and_validate()
        # Keep persisted-state authority failures outside proposal classification.
        recoverable_tail = store._recoverable_completion_tail(records)
        protocol = next(
            (
                record for record in records
                if isinstance(record, ResearchProtocolRevisionV1)
                and record.record_sha256 == protocol_revision_sha256
            ),
            None,
        )
        if protocol is None:
            raise Stage2UnsupportedProfile("missing exact canonical protocol revision")
        admission = admit_protocol(protocol)
        snapshot_sequence = records[-1].append_sequence if records else 0
        snapshot_head = records[-1].record_sha256 if records else None
        history = tuple(
            record for record in records
            if isinstance(record, SearchRunRevisionV1)
            and record.execution_lineage_id == protocol.execution_lineage_id
        )

        def append_proposal(record: SearchRunRevisionV1) -> None:
            # Full original history and every prior proposal stay in the prefix.
            prefix = [*records, record]
            try:
                store._validate_canonical_sequence(prefix)
                new_tail = store._validate_cross_record_state(prefix)
            except (LiteratureIntegrityError, LiteratureConflictError) as exc:
                # This boundary surrounds hypothetical validation only. Runtime,
                # TypeError and unexpected ValueError defects still propagate.
                raise _UnsupportedProposal(str(exc)) from exc
            if new_tail is not None:
                raise _UnsupportedProposal("hypothetical append requires completion reconciliation")
            records.append(record)

        try:
            if recoverable_tail is not None:
                raise _UnsupportedProposal("recoverable completion tail must be reconciled before append")
            active = _validate_sequence(protocol, admission, history)
            if not proposals:
                raise _UnsupportedProposal("no known terminal outcome to authorize")
            if active is None:
                raise _UnsupportedProposal("the next search must already have a canonical STARTED revision")
            steps: list[Stage2PublicationStep] = []
            next_captures: tuple[SearchCaptureAttemptV1, ...] = ()
            for index, proposal in enumerate(proposals):
                if type(proposal) is not Stage2SearchProposal:
                    raise _UnsupportedProposal("expected a typed Stage2SearchProposal")
                started = _exact_copy(proposal.started, SearchRunRevisionV1)
                terminal = _exact_copy(proposal.terminal, SearchRunRevisionV1)
                if started.status != "STARTED" or terminal.status == "STARTED":
                    raise _UnsupportedProposal("proposal must contain a STARTED and terminal pair")
                if index == 0:
                    if canonical_json_bytes(started) != canonical_json_bytes(active):
                        raise _UnsupportedProposal("first proposal must match the current exact STARTED revision")
                else:
                    history = (*history, started)
                    _validate_sequence(protocol, admission, history)
                    append_proposal(started)
                history = (*history, terminal)
                _validate_sequence(protocol, admission, history)
                append_proposal(terminal)
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
                snapshot_sequence,
                snapshot_head,
                tuple(steps),
                next_captures,
            )
        except (_UnsupportedProposal, ValidationError) as exc:
            return Stage2PublicationPlan(
                "UNSUPPORTED_PUBLICATION_SCHEDULE",
                admission.protocol_revision_sha256,
                snapshot_sequence,
                snapshot_head,
                reason=str(exc),
            )
