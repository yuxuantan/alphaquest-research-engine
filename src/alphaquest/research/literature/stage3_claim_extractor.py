"""Supervised, one-shot OpenAlex abstract extraction. Stops at canonical claims."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from alphaquest.research.edge_backlog_io import repository_file_lock
from . import stage3_model as model
from .contracts import (
    ActorProvenanceV1, CanonicalRecordV1, ClaimExtractionRevisionV1, ClaimLocationV1,
    CodexTaskAttemptRevisionV1, LiteratureAuthorityError, LiteratureConflictError,
    LiteratureIntegrityError, ResearchProtocolRevisionV1, SearchRunRevisionV1,
    SearchCaptureAttemptV1, SearchResultInspectionV1,
    SourceCaptureRevisionV1, SourceIdentityRevisionV1, SourceVersionIdentityRevisionV1,
    canonical_json_bytes,
)
from .providers import openalex
from .stage2_runner import (
    OPENALEX_STAGE3_PROCESSING_POLICY_V1, STAGE3_CAPTURE_ACTOR, PilotManualReconciliation, _snapshot, admit,
)
from .store import LiteratureStore

ACTOR_ID = "p3-stage3-claim-extractor"
CONTROLLER = ActorProvenanceV1(actor_class="ALPHAQUEST_DETERMINISTIC_ENGINE", actor_id=ACTOR_ID)
CLAIM_PREFIX = "claim.stage3."


def reference(record: CanonicalRecordV1) -> dict:
    return {"record_id": record.record_id, "record_sha256": record.record_sha256}


def representation_key(capture: SourceCaptureRevisionV1, work_id: str) -> str:
    return model.sha(canonical_json_bytes([
        work_id, capture.source_version_id, capture.content_sha256,
        capture.extracted_representation_sha256, capture.extractor_id,
        capture.extractor_version, capture.extractor_config_sha256,
    ]))


def _exact(records, digest, expected):
    record = next((r for r in records if r.record_sha256 == digest), None)
    if not isinstance(record, expected):
        raise LiteratureIntegrityError("missing exact Stage 3 provenance record")
    return record


def _permission(capture: SourceCaptureRevisionV1) -> None:
    if capture.status != "GENUINE_ABSTRACT_CAPTURED":
        raise LiteratureAuthorityError("Stage 3 supports only genuine abstract captures")
    if capture.external_model_processing_permission != "ALLOWED_EXTERNAL_PROCESSOR":
        raise LiteratureAuthorityError("capture processing permission forbids model invocation")
    if capture.actor != STAGE3_CAPTURE_ACTOR:
        raise LiteratureAuthorityError("capture is outside the fixed owner-authorized OpenAlex policy")


@dataclass(frozen=True)
class AcquisitionBinding:
    search: SearchRunRevisionV1
    capture_attempt: SearchCaptureAttemptV1
    inspection: SearchResultInspectionV1


def _lineage_captures(protocol, records):
    heads = {}
    for record in records:
        if isinstance(record, SearchRunRevisionV1) and record.execution_lineage_id == protocol.execution_lineage_id:
            heads[record.search_run_id] = record
    if not heads or any(r.status == "STARTED" for r in heads.values()):
        raise LiteratureConflictError("acquisition must be terminal before extraction")
    bindings = {}
    for search in heads.values():
        if search.status not in {"SUCCEEDED", "PARTIAL"}:
            continue
        for attempt in search.capture_attempt_records:
            matches = [r for r in search.inspected_results
                       if r.result_identity_sha256 == attempt.result_identity_sha256]
            expected_id = "capture.openalex." + model.sha(
                f"{search.search_run_id}|{attempt.result_identity_sha256}".encode("utf-8")
            )
            if (
                len(matches) != 1 or attempt.capture_attempt_id != expected_id
                or attempt.capture_attempt_id in bindings
            ):
                raise LiteratureIntegrityError("ambiguous or invalid acquisition-result binding")
            bindings[attempt.capture_attempt_id] = AcquisitionBinding(search, attempt, matches[0])
    return bindings


@dataclass(frozen=True)
class PreparedExtraction:
    request: bytes
    input_manifest: bytes
    boundary_manifest: bytes
    references: tuple[dict, ...]
    abstract: bytes
    capture: SourceCaptureRevisionV1
    version: SourceVersionIdentityRevisionV1
    work: SourceIdentityRevisionV1
    attempt_id: str


def prepare_extraction(
    protocol: ResearchProtocolRevisionV1,
    capture: SourceCaptureRevisionV1,
    records: list[CanonicalRecordV1],
    read_artifact: Callable[..., bytes],
) -> PreparedExtraction:
    """Allowlisted construction only; permission precedes every evidence-byte read."""
    _permission(capture)
    admit(protocol)
    if OPENALEX_STAGE3_PROCESSING_POLICY_V1 not in protocol.inclusion_rules:
        raise LiteratureAuthorityError("protocol lacks the frozen owner processing policy")
    binding = _lineage_captures(protocol, records).get(capture.capture_id)
    if binding is None:
        raise LiteratureAuthorityError("capture is outside the exact acquisition lineage")
    version = _exact(records, capture.source_version_revision_sha256, SourceVersionIdentityRevisionV1)
    work = _exact(records, version.work_revision_sha256, SourceIdentityRevisionV1)
    if version.source_version_id != capture.source_version_id or version.work_id != work.work_id:
        raise LiteratureIntegrityError("capture provenance mismatch")
    raw = read_artifact(str(capture.content_sha256), kind="artifacts")
    abstract = read_artifact(str(capture.extracted_representation_sha256), kind="extracted")
    if (
        len(raw) != capture.content_bytes or model.sha(raw) != capture.content_sha256
        or len(abstract) != capture.extracted_bytes or model.sha(abstract) != capture.extracted_representation_sha256
    ):
        raise LiteratureIntegrityError("capture artifact mismatch")
    # Establish the owner policy's data basis, not merely an asserted permission.
    try:
        (normalized,) = openalex.normalize(b'{"results":[' + raw + b']}', 1)
    except openalex.OpenAlexError:
        raise LiteratureIntegrityError("capture is not bounded OpenAlex API data") from None
    if (
        normalized.raw != raw or normalized.abstract != abstract
        or capture.extractor_id != "openalex-inverted-index" or capture.extractor_version != "1"
        or capture.extractor_config_sha256 != model.sha(b"contiguous-unique-zero-based-positions;utf8;space-join;v1")
        or version.source_version_id != "version.openalex." + model.sha(raw)
        or work.work_id != "work.openalex." + normalized.inspection.work_identity_sha256
        or work.title != normalized.title or work.authors != list(normalized.authors)
    ):
        raise LiteratureIntegrityError("OpenAlex representation provenance mismatch")
    identity_fields = ("result_identity_sha256", "work_identity_sha256", "canonical_locator", "locator_sha256")
    if any(getattr(normalized.inspection, field) != getattr(binding.inspection, field) for field in identity_fields):
        raise LiteratureIntegrityError("retained OpenAlex result differs from exact acquisition inspection")
    identifiers = {"openalex": normalized.openalex_id}
    if normalized.doi:
        identifiers["doi"] = normalized.doi
    refs = tuple(reference(r) for r in (protocol, work, version, capture, binding.search))
    logical = dict(
        research_question=protocol.research_question, market_scope=protocol.market_scope,
        inclusion_rules=protocol.inclusion_rules, exclusion_rules=protocol.exclusion_rules,
        source=dict(
            title=work.title, authors=work.authors, identifiers=identifiers,
            work_id=work.work_id, source_version_id=version.source_version_id, capture_id=capture.capture_id,
            work_revision_sha256=work.record_sha256, source_version_revision_sha256=version.record_sha256,
            capture_revision_sha256=capture.record_sha256,
        ),
        abstract=abstract.decode("utf-8"),
    )
    request = model.prepare_request(logical)
    manifest = canonical_json_bytes(dict(
        request_sha256=model.sha(request), abstract_sha256=model.sha(abstract), referenced_records=refs,
    ))
    boundary = canonical_json_bytes(dict(
        isolation_backend=model.BACKEND, filesystem_workspace="NONE",
        input_manifest_sha256=model.sha(manifest), request_sha256=model.sha(request),
        tools=[], conversation_continuation=False,
    ))
    attempt_id = "attempt.stage3." + model.sha(canonical_json_bytes([
        protocol.execution_lineage_id, representation_key(capture, work.work_id),
    ]))
    return PreparedExtraction(request, manifest, boundary, refs, abstract, capture, version, work, attempt_id)


def claim_payloads(prepared: PreparedExtraction, output: model.ExtractionOutput) -> list[dict]:
    result = []
    for index, claim in enumerate(output.claims):
        location = dict(
            representation_kind="PLAIN_TEXT", page_number=None, section_anchor=None, block_ordinal=None,
            byte_start=claim.byte_start, byte_end=claim.byte_end,
            span_sha256=model.sha(prepared.abstract[claim.byte_start:claim.byte_end]),
        )
        location["locator_sha256"] = model.sha(canonical_json_bytes(location, trailing_lf=False))
        ClaimLocationV1.model_validate(location)
        result.append(dict(
            claim_id=CLAIM_PREFIX + model.sha(canonical_json_bytes([prepared.attempt_id, index])),
            work_id=prepared.work.work_id, work_revision_sha256=prepared.work.record_sha256,
            source_version_id=prepared.version.source_version_id,
            source_version_revision_sha256=prepared.version.record_sha256,
            capture_id=prepared.capture.capture_id, capture_revision_sha256=prepared.capture.record_sha256,
            content_sha256=prepared.capture.content_sha256,
            extracted_representation_sha256=prepared.capture.extracted_representation_sha256,
            location=location, statement=claim.quote, statement_kind="SOURCE_QUOTE",
            source_epistemic_form=claim.source_epistemic_form, reliability="ACTIVE",
            correction_reason=None, conflict_refs=[],
        ))
    return result


def _verify_attempt_inputs(attempt, prepared, read_artifact) -> None:
    expected = dict(
        task_type="CLAIM_EXTRACTOR", model=model.MODEL, settings_sha256=model.sha(model.settings_bytes()),
        prompt_sha256=model.sha(model.PROMPT.encode("utf-8")),
        input_manifest_sha256=model.sha(prepared.input_manifest),
        workspace_manifest_sha256=model.sha(prepared.boundary_manifest),
        referenced_records=list(prepared.references), isolation_backend=model.BACKEND,
    )
    actual = attempt.model_dump(mode="json")
    if attempt.attempt_id != prepared.attempt_id or any(actual[k] != v for k, v in expected.items()):
        raise LiteratureIntegrityError("Stage 3 attempt input identity mismatch")
    for field, content in (
        ("settings_sha256", model.settings_bytes()), ("prompt_sha256", model.PROMPT.encode("utf-8")),
        ("input_manifest_sha256", prepared.input_manifest), ("workspace_manifest_sha256", prepared.boundary_manifest),
    ):
        if read_artifact(actual[field], kind="codex-io") != content:
            raise LiteratureIntegrityError("Stage 3 attempt artifact mismatch")
    if read_artifact(model.sha(prepared.request), kind="codex-io") != prepared.request:
        raise LiteratureIntegrityError("Stage 3 exact request mismatch")


@dataclass(frozen=True)
class ResponseOutcome:
    status: str
    failure_reason: str | None
    output: model.ExtractionOutput | None = None


def classify_response(response: bytes, abstract: bytes) -> ResponseOutcome:
    """One semantic classification for runtime terminalization and persisted evidence."""
    try:
        output = model.validate_response(response, abstract)
    except model.InvalidModelOutput:
        return ResponseOutcome("INVALID_OUTPUT", "INVALID_EXTRACTION_OUTPUT")
    except model.ModelFailure:
        return ResponseOutcome("FAILED", "REFUSAL_OR_INCOMPLETE_RESPONSE")
    return ResponseOutcome("SUCCEEDED", None, output)


_NO_RESPONSE_OUTCOMES = frozenset({
    ("STARTED", None),
    ("INVALID_OUTPUT", "INVALID_RESPONSE_BYTES"),
    ("FAILED", "MODEL_INVOCATION_FAILED_NO_RETRY"),
    ("ABANDONED_AFTER_CRASH", "ORPHANED_ATTEMPT_NO_REDISPATCH"),
})


def _verify_attempt_outcome(attempt, prepared, read_artifact) -> model.ExtractionOutput | None:
    if attempt.output_sha256 is None:
        if (attempt.status, attempt.failure_reason) not in _NO_RESPONSE_OUTCOMES:
            raise LiteratureIntegrityError("invalid Stage 3 outcome without retained response")
        return None
    response = read_artifact(attempt.output_sha256, kind="codex-io")
    if type(response) is not bytes or len(response) > model.MAX_RESPONSE_BYTES or model.sha(response) != attempt.output_sha256:
        raise LiteratureIntegrityError("invalid Stage 3 response artifact")
    outcome = classify_response(response, prepared.abstract)
    if (attempt.status, attempt.failure_reason) != (outcome.status, outcome.failure_reason):
        raise LiteratureIntegrityError("Stage 3 terminal outcome contradicts retained response")
    return outcome.output


def _verify_attempt(attempt, prepared, read_artifact) -> model.ExtractionOutput:
    _verify_attempt_inputs(attempt, prepared, read_artifact)
    output = _verify_attempt_outcome(attempt, prepared, read_artifact)
    if attempt.status != "SUCCEEDED" or output is None:
        raise LiteratureIntegrityError("Stage 3 publication requires SUCCEEDED")
    return output


def _is_stage3_attempt(attempt: CodexTaskAttemptRevisionV1) -> bool:
    return attempt.isolation_backend == model.BACKEND or attempt.attempt_id.startswith("attempt.stage3.")


def _attempt_representation(attempt, records, read_artifact) -> tuple[str, PreparedExtraction]:
    bound = [_exact(records, ref.record_sha256, CanonicalRecordV1) for ref in attempt.referenced_records]
    protocols = [r for r in bound if isinstance(r, ResearchProtocolRevisionV1)]
    captures = [r for r in bound if isinstance(r, SourceCaptureRevisionV1)]
    if len(protocols) != 1 or len(captures) != 1 or attempt.actor != CONTROLLER:
        raise LiteratureIntegrityError("invalid Stage 3 attempt authority or provenance")
    prepared = prepare_extraction(protocols[0], captures[0], records, read_artifact)
    _verify_attempt_inputs(attempt, prepared, read_artifact)
    return representation_key(prepared.capture, prepared.work.work_id), prepared


@dataclass(frozen=True)
class AttemptHistory:
    attempt_id: str
    revisions: tuple[CodexTaskAttemptRevisionV1, ...]


def _stage3_dispatch_index(records, read_artifact) -> dict[str, AttemptHistory]:
    """Reconstruct every prior invocation and enforce one owner per representation."""
    grouped: dict[str, list[CodexTaskAttemptRevisionV1]] = {}
    for record in records:
        if isinstance(record, CodexTaskAttemptRevisionV1) and _is_stage3_attempt(record):
            grouped.setdefault(record.attempt_id, []).append(record)
    result = {}
    terminals = {"SUCCEEDED", "FAILED", "INVALID_OUTPUT", "ABANDONED_AFTER_CRASH"}
    for attempt_id, revisions in grouped.items():
        revisions.sort(key=lambda item: item.append_sequence)
        if (
            len(revisions) not in {1, 2}
            or revisions[0].status != "STARTED"
            or (len(revisions) == 2 and revisions[1].status not in terminals)
        ):
            raise LiteratureIntegrityError("invalid Stage 3 attempt invocation history")
        first = revisions[0]
        first_prefix = [r for r in records if r.append_sequence < first.append_sequence]
        key, prepared = _attempt_representation(first, first_prefix, read_artifact)
        _verify_attempt_outcome(first, prepared, read_artifact)
        for revision in revisions[1:]:
            prefix = [r for r in records if r.append_sequence < revision.append_sequence]
            revision_key, revision_prepared = _attempt_representation(revision, prefix, read_artifact)
            if revision_key != key:
                raise LiteratureIntegrityError("Stage 3 attempt representation changed across revisions")
            _verify_attempt_outcome(revision, revision_prepared, read_artifact)
        owner = result.get(key)
        if owner is not None and owner.attempt_id != attempt_id:
            raise LiteratureIntegrityError("Stage 3 representation has multiple invoked attempt owners")
        result[key] = AttemptHistory(attempt_id, tuple(revisions))
    return result


def validate_published_attempt(attempt, records, read_artifact) -> None:
    """Verify even zero-claim attempts and STARTED manifests on append/reload."""
    before = [r for r in records if r.append_sequence < attempt.append_sequence]
    key, prepared = _attempt_representation(attempt, before, read_artifact)
    _verify_attempt_outcome(attempt, prepared, read_artifact)
    owner = _stage3_dispatch_index(before, read_artifact).get(key)
    if attempt.status == "STARTED":
        if owner is not None:
            raise LiteratureIntegrityError("Stage 3 representation was already invoked")
        return
    if owner is None or owner.attempt_id != attempt.attempt_id or len(owner.revisions) != 1:
        raise LiteratureIntegrityError("invalid Stage 3 terminal self-transition")


def validate_published_claim(claim, records, read_artifact) -> None:
    """Store append/reload guard for this pilot; human/local extraction is unchanged."""
    if claim.actor.actor_id != ACTOR_ID and not claim.claim_id.startswith(CLAIM_PREFIX):
        return
    before = [r for r in records if r.append_sequence < claim.append_sequence]
    attempts = [r for r in before if isinstance(r, CodexTaskAttemptRevisionV1) and r.attempt_id == claim.actor.task_id]
    if not attempts:
        raise LiteratureIntegrityError("Stage 3 claim has no preceding model attempt")
    attempt = attempts[-1]
    capture = _exact(before, claim.capture_revision_sha256, SourceCaptureRevisionV1)
    protocols = [
        r for r in before if isinstance(r, ResearchProtocolRevisionV1)
        and reference(r) in [ref.model_dump(mode="json") for ref in attempt.referenced_records]
    ]
    if len(protocols) != 1:
        raise LiteratureIntegrityError("Stage 3 attempt requires one exact protocol")
    prepared = prepare_extraction(protocols[0], capture, before, read_artifact)
    output = _verify_attempt(attempt, prepared, read_artifact)
    expected = next((p for p in claim_payloads(prepared, output) if p["claim_id"] == claim.claim_id), None)
    actor = ActorProvenanceV1(actor_class="CODEX", actor_id=ACTOR_ID, task_id=attempt.attempt_id)
    if (
        expected is None or claim.actor != actor or claim.revision != 1
        or claim.idempotency_key != claim.claim_id
        or claim.model_dump(mode="json", include=set(expected)) != expected
    ):
        raise LiteratureIntegrityError("Stage 3 claim differs from the validated attempt output")


def _terminal(store, started, status, *, output_sha=None, reason=None):
    payload = started.model_dump(mode="json", include={
        "attempt_id", "task_type", "model", "settings_sha256", "prompt_sha256", "input_manifest_sha256",
        "workspace_manifest_sha256", "referenced_records", "isolation_backend",
    })
    payload.update(status=status, output_sha256=output_sha, failure_reason=reason)
    return store.append_codex_attempt(payload, actor=CONTROLLER, idempotency_key=started.attempt_id + ".terminal")


def _preflight_extraction_plan(planned, records, read_artifact) -> list[AttemptHistory | None]:
    """Admit the complete batch before the controller writes or invokes anything."""
    groups = list(planned)
    keys = []
    for group in groups:
        if not group:
            raise LiteratureIntegrityError("invalid Stage 3 planned extraction group")
        group_keys = {
            representation_key(item.capture, item.work.work_id) for item in group
        }
        if len(group_keys) != 1:
            raise LiteratureIntegrityError("planned extraction group mixes representations")
        keys.append(group_keys.pop())
    if len(keys) != len(set(keys)):
        raise PilotManualReconciliation("representation already planned in this batch; no redispatch")

    index = _stage3_dispatch_index(records, read_artifact)
    claims = {r.claim_id for r in records if isinstance(r, ClaimExtractionRevisionV1)}
    histories = []
    for key, group in zip(keys, groups, strict=True):
        prepared = group[0]
        history = index.get(key)
        if history is None:
            histories.append(None)
            continue
        if history.attempt_id != prepared.attempt_id:
            raise PilotManualReconciliation("representation already invoked in this store; no redispatch")
        _verify_attempt_inputs(history.revisions[0], prepared, read_artifact)
        latest = history.revisions[-1]
        if latest.status == "SUCCEEDED":
            output = _verify_attempt(latest, prepared, read_artifact)
            expected = claim_payloads(prepared, output)
            if any(payload["claim_id"] not in claims for payload in expected):
                raise PilotManualReconciliation("partial claim publication; reconcile without a model call")
        elif latest.status != "STARTED":
            raise PilotManualReconciliation("terminal model failure; no automatic retry")
        histories.append(history)
    return histories


def _run_one(store, prepared, history, client):
    if history is not None:
        attempt = history.revisions[-1]
        if attempt.status == "STARTED":
            # The outer process lock is held: the prior controller is no longer running.
            _terminal(store, attempt, "ABANDONED_AFTER_CRASH", reason="ORPHANED_ATTEMPT_NO_REDISPATCH")
            raise PilotManualReconciliation("orphaned model attempt; no redispatch")
        output = _verify_attempt(attempt, prepared, store.verify_artifact)
        payloads = claim_payloads(prepared, output)
        return dict(attempt_id=attempt.attempt_id, status=attempt.status, relevance=output.relevance,
                    claim_ids=[p["claim_id"] for p in payloads], reused=True)
    for artifact in (prepared.request, prepared.input_manifest, prepared.boundary_manifest,
                     model.settings_bytes(), model.PROMPT.encode("utf-8")):
        store.put_artifact(artifact, kind="codex-io")
    started = store.append_codex_attempt(dict(
        attempt_id=prepared.attempt_id, task_type="CLAIM_EXTRACTOR", status="STARTED", model=model.MODEL,
        settings_sha256=model.sha(model.settings_bytes()), prompt_sha256=model.sha(model.PROMPT.encode("utf-8")),
        input_manifest_sha256=model.sha(prepared.input_manifest),
        workspace_manifest_sha256=model.sha(prepared.boundary_manifest), output_sha256=None,
        referenced_records=list(prepared.references), isolation_backend=model.BACKEND, failure_reason=None,
    ), actor=CONTROLLER, idempotency_key=prepared.attempt_id + ".start")
    try:
        response = client(prepared.request)
    except Exception:
        # Provider exception text may contain credentials. Persist only a fixed category.
        attempt = _terminal(store, started, "FAILED", reason="MODEL_INVOCATION_FAILED_NO_RETRY")
        return dict(attempt_id=attempt.attempt_id, status=attempt.status, claim_ids=[], reused=False)
    if type(response) is not bytes or len(response) > model.MAX_RESPONSE_BYTES:
        attempt = _terminal(store, started, "INVALID_OUTPUT", reason="INVALID_RESPONSE_BYTES")
        return dict(attempt_id=attempt.attempt_id, status=attempt.status, claim_ids=[], reused=False)
    output_sha = store.put_artifact(response, kind="codex-io")
    outcome = classify_response(response, prepared.abstract)
    if outcome.output is None:
        attempt = _terminal(store, started, outcome.status, output_sha=output_sha, reason=outcome.failure_reason)
        return dict(attempt_id=attempt.attempt_id, status=attempt.status, claim_ids=[], reused=False)
    output = outcome.output
    payloads = claim_payloads(prepared, output)  # validate the entire output before any append
    attempt = _terminal(store, started, outcome.status, output_sha=output_sha, reason=outcome.failure_reason)
    _verify_attempt(attempt, prepared, store.verify_artifact)
    actor = ActorProvenanceV1(actor_class="CODEX", actor_id=ACTOR_ID, task_id=attempt.attempt_id)
    try:
        for payload in payloads:
            store.append_claim(payload, actor=actor, idempotency_key=payload["claim_id"])
    except Exception:
        raise PilotManualReconciliation("claim publication interrupted; preserve prefix and reconcile without redispatch") from None
    return dict(attempt_id=attempt.attempt_id, status=attempt.status, relevance=output.relevance,
                claim_ids=[p["claim_id"] for p in payloads], reused=False)


def run_claim_extraction_pilot(
    project_root: str | Path, protocol_revision_sha: str, *, _client: Callable[[bytes], bytes] | None = None,
) -> dict:
    """Process one terminal acquisition lineage serially; stop at the first failure.

    Only this controller receives a store root. The model client receives bytes.
    Reentry never redispatches an existing attempt, including failed/crashed ones.
    """
    store = LiteratureStore(project_root)
    with repository_file_lock(store.project_root, "run-store/literature/stage3-claims.lock", exclusive=True):
        records = _snapshot(store)
        protocol = _exact(records, protocol_revision_sha, ResearchProtocolRevisionV1)
        admit(protocol)
        if OPENALEX_STAGE3_PROCESSING_POLICY_V1 not in protocol.inclusion_rules:
            raise LiteratureAuthorityError("protocol lacks the frozen owner processing policy")
        selected = _lineage_captures(protocol, records)
        captures = {}
        for r in records:
            if isinstance(r, SourceCaptureRevisionV1) and r.capture_id in selected:
                captures[r.capture_id] = r
        if set(selected) != set(captures):
            raise LiteratureIntegrityError("acquisition capture records are missing")
        unique = {}
        skipped = []
        for capture in sorted(captures.values(), key=lambda c: c.capture_id):
            if capture.status in {"LOCATOR_METADATA_ONLY", "FAILED"}:
                skipped.append(capture.capture_id)
                continue
            _permission(capture)  # check all permissions before any model invocation
            version = _exact(records, capture.source_version_revision_sha256, SourceVersionIdentityRevisionV1)
            key = representation_key(capture, version.work_id)
            unique.setdefault(key, []).append(capture)
        # Every occurrence, including duplicates, must pass before the first dispatch.
        prepared_captures = {
            capture.capture_id: prepare_extraction(protocol, capture, records, store.verify_artifact)
            for group in unique.values() for capture in group
        }
        planned = [
            tuple(prepared_captures[capture.capture_id] for capture in group)
            for group in unique.values()
        ]
        histories = _preflight_extraction_plan(planned, records, store.verify_artifact)
        orphan_index = next((index for index, history in enumerate(histories)
                             if history is not None and history.revisions[-1].status == "STARTED"), None)
        if orphan_index is not None:
            _run_one(store, planned[orphan_index][0], histories[orphan_index], _client or model.ResponsesClient())
        attempts = []
        for group, history in zip(planned, histories, strict=True):
            outcome = _run_one(store, group[0], history, _client or model.ResponsesClient())
            outcome["capture_ids"] = [item.capture.capture_id for item in group]
            attempts.append(outcome)
            if outcome["status"] != "SUCCEEDED":
                break
            records = _snapshot(store)
        return dict(
            protocol_revision_sha256=protocol.record_sha256, attempts=attempts, skipped_capture_ids=skipped,
            unique_eligible_representations=len(unique),
            complete=len(attempts) == len(unique) and all(a["status"] == "SUCCEEDED" for a in attempts),
        )
