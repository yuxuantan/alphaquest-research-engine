"""Supervised, one-shot OpenAlex pilot; no general dispatch or recovery service."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Callable
import hashlib
import math
from pathlib import Path
import time

import httpx

from alphaquest.research.edge_backlog_io import repository_file_lock
from .contracts import (
    ActorProvenanceV1,
    CanonicalRecordV1,
    LiteratureConflictError,
    P2EmissionOperationRevisionV1,
    ResearchProtocolRevisionV1,
    SearchRunRevisionV1,
    canonical_json_bytes,
    intent_sha256,
    record_sha256,
)
from .providers import openalex
from . import stage2_policy as policy
from .store import LiteratureStore, _record_intent_material

ACTOR = ActorProvenanceV1(actor_class="ALPHAQUEST_DETERMINISTIC_ENGINE", actor_id="p3-openalex-pilot")
OPENALEX_LOCAL_ONLY_POLICY_V1 = "OPENALEX_LOCAL_ONLY_POLICY_V1"
OPENALEX_STAGE3_PROCESSING_POLICY_V1 = "OPENALEX_STAGE3_PROCESSING_POLICY_V1"
STAGE3_CAPTURE_ACTOR = ActorProvenanceV1(
    actor_class="ALPHAQUEST_DETERMINISTIC_ENGINE", actor_id="p3-openalex-stage3-policy-v1"
)


class PilotManualReconciliation(LiteratureConflictError):
    """One-shot execution cannot safely resume or redispatch this state."""


def admit(protocol: ResearchProtocolRevisionV1) -> policy.Stage2AdmissionResult:
    admission = policy.admit_protocol(protocol)
    for lane in protocol.lanes:
        if lane.provider_order != ["openalex"] or lane.minimum_provider_attempts != 1:
            raise policy.Stage2UnsupportedProfile("pilot requires exactly one OpenAlex attempt per lane")
        limit = min(openalex.MAX_RESULTS_PER_LANE, lane.maximum_results)
        if (
            max(
                lane.minimum_results_inspected_per_query,
                lane.minimum_distinct_results_inspected,
                lane.minimum_capture_attempts,
            )
            > limit
        ):
            raise policy.Stage2UnsupportedProfile("frozen minima exceed the pilot result cap")
        try:
            openalex.request_url(lane.required_initial_queries[0], limit)
        except openalex.OpenAlexError as exc:
            raise policy.Stage2UnsupportedProfile(str(exc)) from exc
    return admission


def _snapshot(store: LiteratureStore) -> list[CanonicalRecordV1]:
    with store.lock(exclusive=False):
        records = store._load_and_validate_p3_intrinsic_snapshot()
    if any(isinstance(record, P2EmissionOperationRevisionV1) for record in records):
        raise policy.Stage2UnsupportedProfile(
            "pilot requires a dedicated P3 store without P2 emissions; full Stage 1 validation is unchanged"
        )
    return records


def _proposal(
    started: SearchRunRevisionV1, outcome: dict, head: CanonicalRecordV1, now: datetime
) -> policy.Stage2SearchProposal:
    material = LiteratureStore._terminal_search_material(started, outcome)
    material.update(
        schema=SearchRunRevisionV1.schema_literal,
        append_sequence=head.append_sequence + 1,
        previous_store_record_sha256=head.record_sha256,
        recorded_at=now,
        actor=ACTOR.model_dump(mode="json"),
        idempotency_key=started.search_run_id + ".finish",
        intent_sha256="0" * 64,
    )
    material["record_sha256"] = record_sha256(material)
    record = SearchRunRevisionV1.model_validate_json(canonical_json_bytes(material))
    material["intent_sha256"] = intent_sha256(_record_intent_material(record))
    material["record_sha256"] = record_sha256(material)
    return policy.Stage2SearchProposal(started, SearchRunRevisionV1.model_validate_json(canonical_json_bytes(material)))


def _approve(
    store: LiteratureStore, protocol: ResearchProtocolRevisionV1, proposal: policy.Stage2SearchProposal
) -> policy.Stage2PublicationPlan:
    plan = policy.plan_publication(store, protocol.record_sha256, (proposal,))
    if plan.status != "CAPTURE_RETRIEVAL_ALLOWED":
        raise PilotManualReconciliation("F4 rejected publication; manual reconciliation required: " + str(plan.reason))
    records = _snapshot(store)
    if (records[-1].append_sequence, records[-1].record_sha256) != (
        plan.snapshot_append_sequence,
        plan.snapshot_head_record_sha256,
    ):
        raise PilotManualReconciliation("F4 snapshot became stale; no automatic retry")
    return plan


def _failure(reason: str, *, received: int = 0, elapsed: int = 0) -> dict:
    return dict(
        status="FAILED",
        inspected_results=[],
        capture_attempt_records=[],
        bytes_retrieved=received,
        elapsed_seconds=elapsed,
        saturation_claimed=False,
        provider_trace_completeness="UNAVAILABLE",
        failure_reason=reason,
    )


def _publish_capture(
    store: LiteratureStore,
    work: openalex.Work,
    capture_id: str,
    request: str,
    now: datetime,
    authorize: Callable[[], None],
    processing_policy: str = OPENALEX_LOCAL_ONLY_POLICY_V1,
) -> None:
    """Publish only a first-step capture already approved by F4; no retrieval here."""
    work_id = "work.openalex." + work.inspection.work_identity_sha256
    identifiers = {"openalex": work.openalex_id}
    if work.doi:
        identifiers["doi"] = work.doi
    metadata = dict(
        work_id=work_id,
        source_category="ACADEMIC",
        title=work.title,
        authors=list(work.authors),
        strong_identifiers=identifiers,
        locators=list(dict.fromkeys((work.inspection.canonical_locator, work.openalex_id))),
        identity_status="PROVISIONAL",
        change_reason="OpenAlex-reported metadata",
    )
    metadata_hash = hashlib.sha256(canonical_json_bytes(metadata)).hexdigest()
    source = store.append_work(metadata, actor=ACTOR, idempotency_key="oa.work." + metadata_hash, recorded_at=now)
    digest = hashlib.sha256(work.raw).hexdigest()
    version_id = "version.openalex." + digest
    version = store.append_source_version(
        dict(
            source_version_id=version_id,
            work_id=source.work_id,
            work_revision_sha256=source.record_sha256,
            version_kind="OTHER",
            version_label="OpenAlex metadata snapshot " + digest,
            strong_identifiers=identifiers,
            identity_status="PROVISIONAL",
            change_reason="OpenAlex snapshot, not a paper revision",
            public_availability=dict(
                original_value=work.publication_date,
                parsed_value=None,
                precision="DAY" if work.publication_date else "UNKNOWN",
                verification="SOURCE_REPORTED_UNVERIFIED" if work.publication_date else "UNKNOWN",
                timezone_basis=None,
                provenance_record_ids=[],
            ),
        ),
        actor=ACTOR,
        idempotency_key="oa.version." + digest,
        recorded_at=now,
    )
    capture = dict(
        capture_id=capture_id,
        source_version_id=version.source_version_id,
        source_version_revision_sha256=version.record_sha256,
        retrieval_locator=request,
        captured_at=now,
        access_basis="OPEN_PUBLIC",
        local_retention_permission="ALLOWED",
        redistribution_permission="ALLOWED",
        external_model_processing_permission=(
            "ALLOWED_EXTERNAL_PROCESSOR"
            if processing_policy == OPENALEX_STAGE3_PROCESSING_POLICY_V1
            else "LOCAL_ONLY"
        ),
    )
    authorize()  # Work/version appends changed the snapshot: replan before retention/publication.
    if work.abstract is not None:
        capture.update(
            status="GENUINE_ABSTRACT_CAPTURED",
            media_type="application/json",
            content_sha256=store.put_artifact(work.raw, kind="artifacts"),
            content_bytes=len(work.raw),
            extracted_representation_sha256=store.put_artifact(work.abstract, kind="extracted"),
            extracted_bytes=len(work.abstract),
            extractor_id="openalex-inverted-index",
            extractor_version="1",
            extractor_config_sha256=hashlib.sha256(
                b"contiguous-unique-zero-based-positions;utf8;space-join;v1"
            ).hexdigest(),
        )
    elif work.abstract_error:
        capture.update(status="FAILED", failure_reason="Malformed OpenAlex abstract index; no evidence retained")
    else:
        capture.update(status="LOCATOR_METADATA_ONLY")
    store.append_capture(
        capture,
        actor=STAGE3_CAPTURE_ACTOR if processing_policy == OPENALEX_STAGE3_PROCESSING_POLICY_V1 else ACTOR,
        idempotency_key=capture_id,
        recorded_at=now,
    )


def run_openalex_pilot(
    project_root: str | Path, protocol_revision_sha: str, *,
    processing_policy: str = OPENALEX_LOCAL_ONLY_POLICY_V1,
    _transport: httpx.BaseTransport | None = None,
) -> dict:
    """Execute the seven frozen lanes once in an operator-exclusive P3 store.

    An ephemeral file lock serializes pilot invocations in this store. It is not
    a reservation. Any prior search in this lineage refuses the whole run,
    including orphaned STARTED and partially completed workflows. No resume.
    """
    if processing_policy not in {OPENALEX_LOCAL_ONLY_POLICY_V1, OPENALEX_STAGE3_PROCESSING_POLICY_V1}:
        raise policy.Stage2UnsupportedProfile("unknown fixed OpenAlex processing policy")
    store = LiteratureStore(project_root)
    with repository_file_lock(store.project_root, "run-store/literature/openalex-pilot.lock", exclusive=True):
        records = _snapshot(store)
        protocol = next(
            (
                r
                for r in records
                if isinstance(r, ResearchProtocolRevisionV1) and r.record_sha256 == protocol_revision_sha
            ),
            None,
        )
        if protocol is None:
            raise policy.Stage2UnsupportedProfile("missing exact canonical protocol revision")
        admission = admit(protocol)
        # The choice is frozen in the protocol before the first provider response.
        # No result, DOI, title, or capture quality participates in this decision.
        declared = OPENALEX_STAGE3_PROCESSING_POLICY_V1 in protocol.inclusion_rules
        if declared != (processing_policy == OPENALEX_STAGE3_PROCESSING_POLICY_V1):
            raise policy.Stage2UnsupportedProfile("processing mode must match the predeclared protocol policy")
        if any(
            isinstance(r, SearchRunRevisionV1) and r.execution_lineage_id == protocol.execution_lineage_id
            for r in records
        ):
            raise PilotManualReconciliation("lineage already has search history; no redispatch or automatic recovery")
        if any(
            isinstance(r, SearchRunRevisionV1)
            and r.status == "STARTED"
            and not any(
                isinstance(t, SearchRunRevisionV1) and t.previous_revision_sha256 == r.record_sha256 for t in records
            )
            for r in records
        ):
            raise PilotManualReconciliation("store contains orphaned STARTED work; reconcile manually")
        output = []
        for attempt, lane in zip(admission.attempts, protocol.lanes, strict=True):
            records = _snapshot(store)
            search_id = (
                "search.openalex."
                + hashlib.sha256(
                    canonical_json_bytes([protocol.execution_lineage_id, lane.lane, attempt.query, "openalex"])
                ).hexdigest()
            )
            now = datetime.now(timezone.utc)
            started = store.start_search(
                dict(
                    search_run_id=search_id,
                    protocol_id=protocol.protocol_id,
                    protocol_revision_sha256=protocol.record_sha256,
                    execution_lineage_id=protocol.execution_lineage_id,
                    lane=lane.lane,
                    query=attempt.query,
                    query_kind="INITIAL",
                    parent_search_run_id=None,
                    adaptive_depth=0,
                    provider_id="openalex",
                    provider_trace_completeness="UNAVAILABLE",
                ),
                actor=ACTOR,
                idempotency_key=search_id + ".start",
                recorded_at=now,
            )
            # Before dispatch, test the exact serial step with a zero-capture
            # failure contingency. This authorizes no captures and is never
            # published as an invented outcome. Actual results need a new plan.
            head = _snapshot(store)[-1]
            _approve(store, protocol, _proposal(started, _failure("pre-dispatch structural contingency"), head, now))
            limit = min(openalex.MAX_RESULTS_PER_LANE, lane.maximum_results)
            url = openalex.request_url(attempt.query, limit)
            before = time.monotonic()
            works: tuple[openalex.Work, ...] = ()
            received = 0
            try:
                body = openalex.fetch(
                    attempt.query,
                    limit,
                    byte_limit=lane.maximum_bytes,
                    elapsed_limit=lane.maximum_elapsed_seconds,
                    transport=_transport,
                )
                received = len(body)
                works = openalex.normalize(body, limit)
            except openalex.OpenAlexError as exc:
                received = max(received, exc.bytes_received)
                outcome = _failure(str(exc), received=received)
            else:
                inspections = [w.inspection.model_dump(mode="json") for w in works]
                # One provider and one query: returned ranks already form the
                # canonical order. F4 validates this prefix; no alternate ranker.
                captures = [
                    dict(
                        capture_attempt_id="capture.openalex."
                        + hashlib.sha256(f"{search_id}|{w.inspection.result_identity_sha256}".encode()).hexdigest(),
                        result_identity_sha256=w.inspection.result_identity_sha256,
                        selection_ordinal=i,
                    )
                    for i, w in enumerate(works[: lane.maximum_captures], 1)
                ]
                outcome = dict(
                    status="SUCCEEDED",
                    inspected_results=inspections,
                    capture_attempt_records=captures,
                    bytes_retrieved=received,
                    elapsed_seconds=0,
                    saturation_claimed=False,
                    provider_trace_completeness="COMPLETE_FOR_REQUEST",
                    failure_reason=None,
                )
            outcome["elapsed_seconds"] = math.ceil(time.monotonic() - before)
            if received > lane.maximum_bytes or outcome["elapsed_seconds"] > lane.maximum_elapsed_seconds:
                # Never clamp counters or invent a canonical outcome that hides
                # an overrun. Leave STARTED for explicit manual reconciliation.
                raise PilotManualReconciliation(
                    "provider exceeded frozen budget; STARTED requires manual reconciliation"
                )
            records = _snapshot(store)
            if records[-1].record_sha256 != head.record_sha256:
                raise PilotManualReconciliation("canonical state changed during request; reconcile STARTED manually")

            def current_plan() -> policy.Stage2PublicationPlan:
                current = _snapshot(store)
                proposed = _proposal(started, outcome, current[-1], datetime.now(timezone.utc))
                return _approve(store, protocol, proposed)

            plan = current_plan()
            by_identity = {w.inspection.result_identity_sha256: w for w in works}
            for capture in plan.next_capture_attempts:

                def authorize_capture() -> None:
                    fresh = current_plan()
                    if capture not in fresh.next_capture_attempts:
                        raise PilotManualReconciliation("capture is not authorized by the current F4 first step")

                _publish_capture(
                    store,
                    by_identity[capture.result_identity_sha256],
                    capture.capture_attempt_id,
                    url,
                    datetime.now(timezone.utc),
                    authorize_capture,
                    processing_policy,
                )
            # Capture metadata appends invalidate earlier plans. Publish only
            # the newly planned exact terminal after all selected captures.
            final_plan = current_plan()
            planned_terminal = SearchRunRevisionV1.model_validate_json(final_plan.steps[0].terminal_record_json)
            terminal = store.finish_search(
                search_id,
                outcome,
                actor=ACTOR,
                idempotency_key=search_id + ".finish",
                recorded_at=planned_terminal.recorded_at,
            )
            if canonical_json_bytes(terminal) != final_plan.steps[0].terminal_record_json:
                raise PilotManualReconciliation("published terminal differs from planned snapshot; reconcile manually")
            output.append(
                dict(
                    search_run_id=search_id,
                    status=terminal.status,
                    results=terminal.results_inspected,
                    capture_attempts=terminal.capture_attempts,
                    record_sha256=terminal.record_sha256,
                )
            )
            if terminal.status == "FAILED":
                break
        completions = store._derive_lane_completions(protocol, _snapshot(store))
        return dict(
            protocol_revision_sha256=protocol.record_sha256,
            searches=output,
            lane_completions=completions,
            complete=all(item["obligation_status"] == "SATISFIED" for item in completions),
        )
