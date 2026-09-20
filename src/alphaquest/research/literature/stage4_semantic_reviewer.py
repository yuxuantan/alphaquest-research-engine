"""Synthetic-only P3 Slice A semantic eligibility and methodology review.

The canonical product is the two-revision Codex attempt.  Derived advisory use
is returned or reloaded, never appended as a claim, relation, dossier, P2
object, hypothesis, campaign, or result.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Mapping, NoReturn

from pydantic import Field

from alphaquest.research.edge_backlog_io import repository_file_lock

from . import stage3_claim_extractor as stage3
from . import stage4_semantic_model as model
from .contracts import (
    ActorProvenanceV1,
    CanonicalRecordV1,
    ClaimExtractionRevisionV1,
    CodexTaskAttemptRevisionV1,
    LiteratureAuthorityError,
    LiteratureConflictError,
    LiteratureIntegrityError,
    RecordReferenceV1,
    ResearchProtocolRevisionV1,
    Sha256,
    SourceCaptureRevisionV1,
    SourceIdentityRevisionV1,
    SourceRelationshipRevisionV1,
    SourceVersionIdentityRevisionV1,
    StrictModel,
    canonical_json_bytes,
)
from .mapper import effective_claim_reliability
from .stage2_runner import (
    OPENALEX_STAGE3_PROCESSING_POLICY_V1,
    PilotManualReconciliation,
    admit,
)
from .store import LiteratureStore

CONTROLLER = ActorProvenanceV1(
    actor_class=model.ACTOR_CLASS,
    actor_id=model.ACTOR_ID,
)
_TERMINAL_STATUSES = {
    "SUCCEEDED", "FAILED", "INVALID_OUTPUT", "ABANDONED_AFTER_CRASH"
}


def reference(record: CanonicalRecordV1) -> dict:
    return {"record_id": record.record_id, "record_sha256": record.record_sha256}


def _exact(records, digest, expected):
    matches = [record for record in records if record.record_sha256 == digest]
    if len(matches) != 1 or not isinstance(matches[0], expected):
        raise LiteratureIntegrityError("missing exact Stage 4 provenance record")
    return matches[0]


def _snapshot(store: LiteratureStore) -> list[CanonicalRecordV1]:
    with store.lock(exclusive=False):
        return store._load_and_validate_p3_intrinsic_snapshot()


class PlannedContextV1(StrictModel):
    review_context_sha256: Sha256
    claim_ref: RecordReferenceV1
    request_sha256: Sha256


class ReusedOwnerBindingV1(StrictModel):
    review_context_sha256: Sha256
    owner_attempt_id: str
    terminal_attempt_sha256: Sha256
    owner_receipt_sha256: Sha256


class FreshFixtureBindingV1(StrictModel):
    review_context_sha256: Sha256
    request_sha256: Sha256
    fixture_response_sha256: Sha256
    fixture_response_byte_count: Annotated[int, Field(ge=0)]


class RequestResponseBindingV1(StrictModel):
    request_sha256: Sha256
    fixture_response_sha256: Sha256


class SyntheticSemanticQualificationReceiptV1(StrictModel):
    schema_name: Literal[
        "alphaquest.synthetic-semantic-qualification-receipt/v1"
    ] = Field(alias="schema", serialization_alias="schema")
    qualification_class: Literal["SYNTHETIC_FIXTURE_ONLY"]
    review_policy_id: Literal["P3_ABSTRACT_CLAIM_SEMANTIC_REVIEW_V1"]
    backend: Literal["SYNTHETIC_RESPONSES_FIXTURE_SEMANTIC_REVIEW_V1"]
    initial_store_head_record_sha256: Sha256 | None
    protocol_revision_sha256: Sha256
    claim_refs: list[RecordReferenceV1]
    batch_key_sha256: Sha256
    planned_contexts: list[PlannedContextV1]
    reused_owner_bindings: list[ReusedOwnerBindingV1]
    fresh_fixture_bindings: list[FreshFixtureBindingV1]
    request_response_bindings: list[RequestResponseBindingV1]
    fixture_set_sha256: Sha256
    receipt_sha256: Sha256


class SyntheticSemanticReviewEvidenceV1(StrictModel):
    qualification_class: Literal["SYNTHETIC_FIXTURE_ONLY"]
    review_policy_id: Literal["P3_ABSTRACT_CLAIM_SEMANTIC_REVIEW_V1"]
    attempt_id: str
    terminal_attempt_sha256: Sha256
    claim_id: str
    claim_revision_sha256: Sha256
    review_context_sha256: Sha256
    receipt_sha256: Sha256
    p3_advisory_use: Literal[
        "ELIGIBLE_DIRECT",
        "ELIGIBLE_CONTEXT_ONLY",
        "AMBIGUOUS_EXCLUDED",
        "INELIGIBLE_EXCLUDED",
    ]
    current: bool


@dataclass(frozen=True)
class PreparedSemanticReview:
    protocol: ResearchProtocolRevisionV1
    claim: ClaimExtractionRevisionV1
    work: SourceIdentityRevisionV1
    version: SourceVersionIdentityRevisionV1
    capture: SourceCaptureRevisionV1
    extraction_attempt: CodexTaskAttemptRevisionV1
    abstract: bytes
    request: bytes
    request_sha256: str
    semantic_subject_sha256: str
    research_context_sha256: str
    review_context_sha256: str
    attempt_id: str
    references: tuple[dict, ...]


@dataclass(frozen=True)
class ReconstructedAttempt:
    prepared: PreparedSemanticReview
    receipt: SyntheticSemanticQualificationReceiptV1
    receipt_artifact_sha256: str
    output: model.SemanticReviewOutputV1 | None


@dataclass(frozen=True)
class AttemptHistory:
    attempt_id: str
    review_context_sha256: str
    receipt_sha256: str
    revisions: tuple[CodexTaskAttemptRevisionV1, ...]
    prepared: PreparedSemanticReview


def _research_context(protocol: ResearchProtocolRevisionV1) -> dict:
    return {
        "schema": "P3_RESEARCH_SEMANTIC_CONTEXT_V1",
        "research_question": protocol.research_question,
        "market_scope": protocol.market_scope,
        "inclusion_rules": protocol.inclusion_rules,
        "exclusion_rules": protocol.exclusion_rules,
    }


def _semantic_subject_sha256(claim: ClaimExtractionRevisionV1) -> str:
    return model.sha(
        canonical_json_bytes(
            [
                "P3_CLAIM_SEMANTIC_SUBJECT_V1",
                claim.work_id,
                claim.source_version_id,
                claim.content_sha256,
                claim.extracted_representation_sha256,
                claim.location.locator_sha256,
                claim.statement,
                claim.statement_kind,
                claim.source_epistemic_form,
            ]
        )
    )


def _review_context_sha256(
    semantic_subject_sha256: str, research_context_sha256: str
) -> str:
    return model.sha(
        canonical_json_bytes(
            [
                "P3_ABSTRACT_CLAIM_SEMANTIC_REVIEW_BASE_CONTEXT_V1",
                semantic_subject_sha256,
                research_context_sha256,
            ]
        )
    )


def _claim_currentness_issue(
    claim: ClaimExtractionRevisionV1, records: list[CanonicalRecordV1]
) -> str | None:
    heads = LiteratureStore._claim_heads(records)
    head = heads.get(claim.claim_id)
    if head is None or head.record_sha256 != claim.record_sha256:
        return "STALE_STAGE3_CLAIM"
    if claim.revision != 1:
        return "STAGE3_CLAIM_REVISION_NOT_ONE"
    if claim.reliability != "ACTIVE":
        return "STAGE3_CLAIM_NOT_ACTIVE"
    relationships = [
        record for record in records if isinstance(record, SourceRelationshipRevisionV1)
    ]
    if effective_claim_reliability(claim, relationships) != "ACTIVE":
        return "STAGE3_CLAIM_EFFECTIVELY_INELIGIBLE"
    return None


def _stage3_terminal_for_claim(
    claim: ClaimExtractionRevisionV1, records: list[CanonicalRecordV1]
) -> CodexTaskAttemptRevisionV1:
    if (
        claim.actor.actor_class != "CODEX"
        or claim.actor.actor_id != stage3.ACTOR_ID
        or claim.actor.task_id is None
        or not claim.claim_id.startswith(stage3.CLAIM_PREFIX)
    ):
        raise LiteratureAuthorityError("claim is not an exact Stage 3 pilot claim")
    attempts = [
        record
        for record in records
        if isinstance(record, CodexTaskAttemptRevisionV1)
        and record.attempt_id == claim.actor.task_id
        and record.append_sequence < claim.append_sequence
    ]
    attempts.sort(key=lambda item: item.append_sequence)
    if (
        len(attempts) != 2
        or attempts[0].status != "STARTED"
        or attempts[1].status != "SUCCEEDED"
    ):
        raise LiteratureIntegrityError(
            "Stage 4 claim requires one exact preceding successful extraction attempt"
        )
    return attempts[1]


def _prepare_claim(
    protocol: ResearchProtocolRevisionV1,
    claim: ClaimExtractionRevisionV1,
    records: list[CanonicalRecordV1],
    read_artifact,
) -> PreparedSemanticReview:
    issue = _claim_currentness_issue(claim, records)
    if issue is not None:
        raise LiteratureAuthorityError(f"Stage 4 claim is not currently eligible: {issue}")
    terminal = _stage3_terminal_for_claim(claim, records)
    bound = [
        _exact(records, item.record_sha256, CanonicalRecordV1)
        for item in terminal.referenced_records
    ]
    protocols = [item for item in bound if isinstance(item, ResearchProtocolRevisionV1)]
    captures = [item for item in bound if isinstance(item, SourceCaptureRevisionV1)]
    if len(protocols) != 1 or len(captures) != 1:
        raise LiteratureIntegrityError("Stage 3 claim has ambiguous extraction provenance")
    if protocols[0].record_sha256 != protocol.record_sha256:
        raise LiteratureAuthorityError(
            "selected protocol is not the exact Stage 3 extraction protocol"
        )
    stage3.validate_published_attempt(terminal, records, read_artifact)
    stage3.validate_published_claim(claim, records, read_artifact)
    prepared_extraction = stage3.prepare_extraction(
        protocol, captures[0], records, read_artifact
    )
    extraction_output = stage3._verify_attempt(
        terminal, prepared_extraction, read_artifact
    )
    expected_claims = stage3.claim_payloads(prepared_extraction, extraction_output)
    expected = next(
        (item for item in expected_claims if item["claim_id"] == claim.claim_id), None
    )
    if expected is None:
        raise LiteratureIntegrityError("Stage 4 claim is absent from retained extraction output")
    if claim.model_dump(mode="json", include=set(expected)) != expected:
        raise LiteratureIntegrityError("Stage 4 claim differs from retained extraction output")
    start, end = claim.location.byte_start, claim.location.byte_end
    try:
        quoted = prepared_extraction.abstract[start:end].decode("utf-8")
    except UnicodeError:
        raise LiteratureIntegrityError("Stage 4 claim splits a UTF-8 sequence") from None
    if quoted != claim.statement:
        raise LiteratureIntegrityError("Stage 4 exact claim quote does not reconstruct")

    semantic_subject_sha256 = _semantic_subject_sha256(claim)
    research_context = _research_context(protocol)
    research_context_sha256 = model.sha(canonical_json_bytes(research_context))
    review_context_sha256 = _review_context_sha256(
        semantic_subject_sha256, research_context_sha256
    )
    logical_input = {
        "schema": "alphaquest.claim-semantic-review-input/v1",
        "review_policy_id": model.REVIEW_POLICY_ID,
        "research_context": {
            "research_question": protocol.research_question,
            "market_scope": protocol.market_scope,
            "inclusion_rules": protocol.inclusion_rules,
            "exclusion_rules": protocol.exclusion_rules,
        },
        "source_context": {
            "title": prepared_extraction.work.title,
            "authors": prepared_extraction.work.authors,
            "abstract": prepared_extraction.abstract.decode("utf-8"),
        },
        "claim": {
            "byte_start": start,
            "byte_end": end,
            "quote": claim.statement,
            "source_epistemic_form": claim.source_epistemic_form,
        },
    }
    request = model.prepare_request(logical_input)
    refs = tuple(
        reference(item)
        for item in (
            protocol,
            claim,
            prepared_extraction.work,
            prepared_extraction.version,
            prepared_extraction.capture,
            terminal,
        )
    )
    return PreparedSemanticReview(
        protocol=protocol,
        claim=claim,
        work=prepared_extraction.work,
        version=prepared_extraction.version,
        capture=prepared_extraction.capture,
        extraction_attempt=terminal,
        abstract=prepared_extraction.abstract,
        request=request,
        request_sha256=model.sha(request),
        semantic_subject_sha256=semantic_subject_sha256,
        research_context_sha256=research_context_sha256,
        review_context_sha256=review_context_sha256,
        attempt_id=model.ATTEMPT_PREFIX + review_context_sha256,
        references=refs,
    )


def _prepare_plan(
    protocol: ResearchProtocolRevisionV1,
    records: list[CanonicalRecordV1],
    read_artifact,
) -> list[PreparedSemanticReview]:
    admit(protocol)
    if OPENALEX_STAGE3_PROCESSING_POLICY_V1 not in protocol.inclusion_rules:
        raise LiteratureAuthorityError("protocol lacks the frozen Stage 3 processing policy")
    heads = LiteratureStore._claim_heads(records)
    stage3_heads = [
        claim
        for claim in heads.values()
        if claim.actor.actor_id == stage3.ACTOR_ID
        or claim.claim_id.startswith(stage3.CLAIM_PREFIX)
    ]
    selected_claims = []
    for claim in stage3_heads:
        terminal = _stage3_terminal_for_claim(claim, records)
        if any(
            item.record_sha256 == protocol.record_sha256
            for item in terminal.referenced_records
        ):
            selected_claims.append(claim)
    planned = [
        _prepare_claim(protocol, claim, records, read_artifact)
        for claim in selected_claims
    ]
    planned.sort(key=lambda item: (item.semantic_subject_sha256, item.claim.claim_id))
    contexts = [item.review_context_sha256 for item in planned]
    if len(contexts) != len(set(contexts)):
        raise LiteratureConflictError(
            "one semantic review context appears more than once in the current plan"
        )
    return planned


def prepare_semantic_review_requests(
    project_root: str | Path,
    protocol_revision_sha: str,
) -> dict[str, bytes]:
    """Read-only helper returning exact request-hash keys for synthetic fixtures."""

    store = LiteratureStore(project_root)
    records = _snapshot(store)
    protocol = _exact(records, protocol_revision_sha, ResearchProtocolRevisionV1)
    planned = _prepare_plan(protocol, records, store.verify_artifact)
    return {item.request_sha256: item.request for item in planned}


def _input_manifest(prepared: PreparedSemanticReview, receipt_sha256: str) -> bytes:
    return canonical_json_bytes(
        {
            "schema": "alphaquest.semantic-review-input-manifest/v1",
            "qualification_class": model.QUALIFICATION_CLASS,
            "review_policy_id": model.REVIEW_POLICY_ID,
            "synthetic_qualification_receipt_sha256": receipt_sha256,
            "protocol_revision_sha256": prepared.protocol.record_sha256,
            "claim_revision_sha256": prepared.claim.record_sha256,
            "work_revision_sha256": prepared.work.record_sha256,
            "source_version_revision_sha256": prepared.version.record_sha256,
            "capture_revision_sha256": prepared.capture.record_sha256,
            "terminal_extraction_attempt_sha256": prepared.extraction_attempt.record_sha256,
            "request_sha256": prepared.request_sha256,
            "abstract_sha256": model.sha(prepared.abstract),
            "semantic_subject_sha256": prepared.semantic_subject_sha256,
            "research_context_sha256": prepared.research_context_sha256,
            "review_context_sha256": prepared.review_context_sha256,
            "referenced_records": list(prepared.references),
        }
    )


def _boundary_manifest(prepared: PreparedSemanticReview, receipt_sha256: str) -> bytes:
    input_manifest = _input_manifest(prepared, receipt_sha256)
    return canonical_json_bytes(
        {
            "schema": "alphaquest.semantic-review-boundary-manifest/v1",
            "filesystem_workspace": "NONE",
            "tools": [],
            "conversation_continuation": False,
            "qualification_class": model.QUALIFICATION_CLASS,
            "synthetic_qualification_receipt_sha256": receipt_sha256,
            "isolation_backend": model.BACKEND,
            "input_manifest_sha256": model.sha(input_manifest),
            "request_sha256": prepared.request_sha256,
        }
    )


def _receipt_material(
    protocol: ResearchProtocolRevisionV1,
    planned: list[PreparedSemanticReview],
    records: list[CanonicalRecordV1],
    reused: list[dict],
    fresh: list[dict],
) -> bytes:
    contexts = [item.review_context_sha256 for item in planned]
    research_context_sha256 = (
        planned[0].research_context_sha256
        if planned
        else model.sha(canonical_json_bytes(_research_context(protocol)))
    )
    batch_key_sha256 = model.sha(
        canonical_json_bytes(
            ["P3_SYNTHETIC_SEMANTIC_BATCH_V1", research_context_sha256, contexts]
        )
    )
    request_response = [
        {
            "request_sha256": item["request_sha256"],
            "fixture_response_sha256": item["fixture_response_sha256"],
        }
        for item in fresh
    ]
    material = {
        "schema": "alphaquest.synthetic-semantic-qualification-receipt/v1",
        "qualification_class": model.QUALIFICATION_CLASS,
        "review_policy_id": model.REVIEW_POLICY_ID,
        "backend": model.BACKEND,
        "initial_store_head_record_sha256": (
            records[-1].record_sha256 if records else None
        ),
        "protocol_revision_sha256": protocol.record_sha256,
        "claim_refs": [reference(item.claim) for item in planned],
        "batch_key_sha256": batch_key_sha256,
        "planned_contexts": [
            {
                "review_context_sha256": item.review_context_sha256,
                "claim_ref": reference(item.claim),
                "request_sha256": item.request_sha256,
            }
            for item in planned
        ],
        "reused_owner_bindings": reused,
        "fresh_fixture_bindings": fresh,
        "request_response_bindings": request_response,
        "fixture_set_sha256": model.sha(canonical_json_bytes(fresh)),
    }
    material["receipt_sha256"] = model.sha(
        canonical_json_bytes(material, trailing_lf=False)
    )
    receipt = SyntheticSemanticQualificationReceiptV1.model_validate(material)
    return canonical_json_bytes(receipt)


def _parse_receipt(
    receipt_sha256: str,
    records: list[CanonicalRecordV1],
    read_artifact,
) -> SyntheticSemanticQualificationReceiptV1:
    try:
        data = read_artifact(receipt_sha256, kind="codex-io")
        if model.sha(data) != receipt_sha256:
            raise LiteratureIntegrityError("semantic receipt artifact hash mismatch")
        raw = model.parse_json(data)
        receipt = SyntheticSemanticQualificationReceiptV1.model_validate(raw)
    except LiteratureIntegrityError:
        raise
    except Exception:
        raise LiteratureIntegrityError("invalid synthetic semantic receipt") from None
    material = receipt.model_dump(mode="json", by_alias=True)
    embedded = material.pop("receipt_sha256")
    if embedded != model.sha(canonical_json_bytes(material, trailing_lf=False)):
        raise LiteratureIntegrityError("synthetic semantic receipt self-hash mismatch")
    if receipt.fixture_set_sha256 != model.sha(
        canonical_json_bytes(
            [item.model_dump(mode="json") for item in receipt.fresh_fixture_bindings]
        )
    ):
        raise LiteratureIntegrityError("synthetic semantic fixture-set hash mismatch")
    fresh_pairs = [
        {
            "request_sha256": item.request_sha256,
            "fixture_response_sha256": item.fixture_response_sha256,
        }
        for item in receipt.fresh_fixture_bindings
    ]
    if fresh_pairs != [
        item.model_dump(mode="json") for item in receipt.request_response_bindings
    ]:
        raise LiteratureIntegrityError("synthetic receipt request/response bindings disagree")
    contexts = [item.review_context_sha256 for item in receipt.planned_contexts]
    if len(contexts) != len(set(contexts)):
        raise LiteratureIntegrityError("synthetic receipt has duplicate planned contexts")
    bound_contexts = [item.review_context_sha256 for item in receipt.reused_owner_bindings]
    bound_contexts += [item.review_context_sha256 for item in receipt.fresh_fixture_bindings]
    if len(bound_contexts) != len(set(bound_contexts)) or set(bound_contexts) != set(contexts):
        raise LiteratureIntegrityError("synthetic receipt does not partition planned contexts")
    planned_by_context = {
        item.review_context_sha256: item for item in receipt.planned_contexts
    }
    protocol = _exact(
        records, receipt.protocol_revision_sha256, ResearchProtocolRevisionV1
    )
    expected_batch_key = model.sha(
        canonical_json_bytes(
            [
                "P3_SYNTHETIC_SEMANTIC_BATCH_V1",
                model.sha(canonical_json_bytes(_research_context(protocol))),
                contexts,
            ]
        )
    )
    if receipt.batch_key_sha256 != expected_batch_key:
        raise LiteratureIntegrityError("synthetic semantic batch key mismatch")
    for item in receipt.fresh_fixture_bindings:
        planned = planned_by_context[item.review_context_sha256]
        if planned.request_sha256 != item.request_sha256:
            raise LiteratureIntegrityError("synthetic fixture request binding mismatch")
        response = read_artifact(item.fixture_response_sha256, kind="codex-io")
        if (
            type(response) is not bytes
            or len(response) != item.fixture_response_byte_count
            or len(response) > model.MAX_RESPONSE_BYTES
            or model.sha(response) != item.fixture_response_sha256
        ):
            raise LiteratureIntegrityError("synthetic fixture artifact binding mismatch")
    for item in receipt.reused_owner_bindings:
        owner = _exact(records, item.terminal_attempt_sha256, CodexTaskAttemptRevisionV1)
        if owner.attempt_id != item.owner_attempt_id or owner.status != "SUCCEEDED":
            raise LiteratureIntegrityError("synthetic reused-owner terminal mismatch")
        owner_manifest = _parse_input_manifest(owner, read_artifact)
        if (
            owner_manifest["review_context_sha256"] != item.review_context_sha256
            or owner_manifest["synthetic_qualification_receipt_sha256"]
            != item.owner_receipt_sha256
        ):
            raise LiteratureIntegrityError("synthetic reused-owner receipt binding mismatch")
        read_artifact(item.owner_receipt_sha256, kind="codex-io")
    if receipt.initial_store_head_record_sha256 is None:
        raise LiteratureIntegrityError(
            "nonempty synthetic semantic receipt requires an exact initial head"
        )
    anchors = [
        item
        for item in records
        if item.record_sha256 == receipt.initial_store_head_record_sha256
    ]
    if len(anchors) != 1:
        raise LiteratureIntegrityError(
            "synthetic receipt initial head is not an exact current-store ancestor"
        )
    frozen_prefix = [
        item for item in records if item.append_sequence <= anchors[0].append_sequence
    ]
    if (
        not frozen_prefix
        or frozen_prefix[-1].record_sha256
        != receipt.initial_store_head_record_sha256
    ):
        raise LiteratureIntegrityError("synthetic receipt initial prefix is not contiguous")
    frozen_protocol = _exact(
        frozen_prefix, receipt.protocol_revision_sha256, ResearchProtocolRevisionV1
    )
    frozen_plan = _prepare_plan(frozen_protocol, frozen_prefix, read_artifact)
    expected_planned = [
        {
            "review_context_sha256": item.review_context_sha256,
            "claim_ref": reference(item.claim),
            "request_sha256": item.request_sha256,
        }
        for item in frozen_plan
    ]
    if expected_planned != [
        item.model_dump(mode="json") for item in receipt.planned_contexts
    ]:
        raise LiteratureIntegrityError(
            "synthetic receipt does not reconstruct the complete frozen-prefix plan"
        )
    frozen_index = _dispatch_index(frozen_prefix, read_artifact)
    expected_reused_contexts = [
        item.review_context_sha256
        for item in receipt.planned_contexts
        if item.review_context_sha256 in frozen_index
    ]
    if expected_reused_contexts != [
        item.review_context_sha256 for item in receipt.reused_owner_bindings
    ]:
        raise LiteratureIntegrityError(
            "synthetic receipt reused owners do not match its exact initial prefix"
        )
    expected_fresh_contexts = [
        item.review_context_sha256
        for item in receipt.planned_contexts
        if item.review_context_sha256 not in frozen_index
    ]
    if expected_fresh_contexts != [
        item.review_context_sha256 for item in receipt.fresh_fixture_bindings
    ]:
        raise LiteratureIntegrityError(
            "synthetic receipt fresh contexts do not match its exact initial prefix"
        )
    for item in receipt.reused_owner_bindings:
        frozen_owner = frozen_index.get(item.review_context_sha256)
        if (
            frozen_owner is None
            or frozen_owner.attempt_id != item.owner_attempt_id
            or frozen_owner.receipt_sha256 != item.owner_receipt_sha256
            or frozen_owner.revisions[-1].record_sha256
            != item.terminal_attempt_sha256
        ):
            raise LiteratureIntegrityError(
                "synthetic receipt reused owner is absent from its frozen prefix"
            )
    for claim_ref in receipt.claim_refs:
        claim = _exact(records, claim_ref.record_sha256, ClaimExtractionRevisionV1)
        if claim.record_id != claim_ref.record_id:
            raise LiteratureIntegrityError("synthetic receipt claim reference mismatch")
    if [item.claim_ref for item in receipt.planned_contexts] != receipt.claim_refs:
        raise LiteratureIntegrityError("synthetic receipt planned claims are not exact and ordered")
    return receipt


def _parse_input_manifest(attempt, read_artifact) -> dict:
    try:
        data = read_artifact(attempt.input_manifest_sha256, kind="codex-io")
        if model.sha(data) != attempt.input_manifest_sha256:
            raise LiteratureIntegrityError("semantic input manifest artifact hash mismatch")
        value = model.parse_json(data)
    except LiteratureIntegrityError:
        raise
    except Exception:
        raise LiteratureIntegrityError("invalid semantic input manifest") from None
    expected = {
        "schema",
        "qualification_class",
        "review_policy_id",
        "synthetic_qualification_receipt_sha256",
        "protocol_revision_sha256",
        "claim_revision_sha256",
        "work_revision_sha256",
        "source_version_revision_sha256",
        "capture_revision_sha256",
        "terminal_extraction_attempt_sha256",
        "request_sha256",
        "abstract_sha256",
        "semantic_subject_sha256",
        "research_context_sha256",
        "review_context_sha256",
        "referenced_records",
    }
    if type(value) is not dict or set(value) != expected:
        raise LiteratureIntegrityError("semantic input manifest field mismatch")
    return value


def _classify_response(
    response: bytes, prepared: PreparedSemanticReview
) -> tuple[str, str | None, model.SemanticReviewOutputV1 | None]:
    try:
        output = model.validate_response(
            response,
            prepared.abstract,
            claim_byte_start=prepared.claim.location.byte_start,
            claim_byte_end=prepared.claim.location.byte_end,
            claim_quote=prepared.claim.statement,
        )
    except model.InvalidSemanticReviewOutput:
        return "INVALID_OUTPUT", "INVALID_SEMANTIC_REVIEW_OUTPUT", None
    except model.SemanticReviewFailure:
        return "FAILED", "REFUSAL_OR_INCOMPLETE_RESPONSE", None
    return "SUCCEEDED", None, output


def derive_advisory_use(
    output: model.SemanticReviewOutputV1,
    source_epistemic_form: str,
) -> str:
    if (
        output.support_assessment == "EXACTLY_SUPPORTED"
        and output.scope_assessment == "DIRECTLY_RELEVANT"
        and output.epistemic_form_assessment == "CONSISTENT"
    ):
        return "ELIGIBLE_DIRECT"
    if (
        output.support_assessment == "EXACTLY_SUPPORTED"
        and output.scope_assessment == "BACKGROUND_RELEVANT"
        and output.epistemic_form_assessment == "CONSISTENT"
        and source_epistemic_form in {"METHODOLOGY_FACT", "LIMITATION", "OTHER"}
    ):
        return "ELIGIBLE_CONTEXT_ONLY"
    if (
        "AMBIGUOUS"
        in {
            output.support_assessment,
            output.scope_assessment,
            output.epistemic_form_assessment,
        }
        or output.scope_assessment == "INSUFFICIENT_CONTEXT"
    ):
        return "AMBIGUOUS_EXCLUDED"
    return "INELIGIBLE_EXCLUDED"


def _verify_attempt_identity(
    attempt: CodexTaskAttemptRevisionV1,
    prepared: PreparedSemanticReview,
    receipt_sha256: str,
    read_artifact,
) -> None:
    input_manifest = _input_manifest(prepared, receipt_sha256)
    boundary_manifest = _boundary_manifest(prepared, receipt_sha256)
    expected = {
        "task_type": model.TASK_TYPE,
        "model": model.MODEL_CONTRACT,
        "settings_sha256": model.sha(model.settings_bytes()),
        "prompt_sha256": model.sha(model.PROMPT.encode("utf-8")),
        "input_manifest_sha256": model.sha(input_manifest),
        "workspace_manifest_sha256": model.sha(boundary_manifest),
        "referenced_records": list(prepared.references),
        "isolation_backend": model.BACKEND,
    }
    actual = attempt.model_dump(mode="json")
    if (
        attempt.attempt_id != prepared.attempt_id
        or attempt.actor != CONTROLLER
        or any(actual[key] != value for key, value in expected.items())
    ):
        raise LiteratureIntegrityError("Stage 4 semantic attempt input identity mismatch")
    for field, content in (
        ("settings_sha256", model.settings_bytes()),
        ("prompt_sha256", model.PROMPT.encode("utf-8")),
        ("input_manifest_sha256", input_manifest),
        ("workspace_manifest_sha256", boundary_manifest),
    ):
        if read_artifact(actual[field], kind="codex-io") != content:
            raise LiteratureIntegrityError("Stage 4 semantic attempt artifact mismatch")
    if read_artifact(prepared.request_sha256, kind="codex-io") != prepared.request:
        raise LiteratureIntegrityError("Stage 4 exact semantic request mismatch")


def _reconstruct_attempt(
    attempt: CodexTaskAttemptRevisionV1,
    records: list[CanonicalRecordV1],
    read_artifact,
) -> ReconstructedAttempt:
    if (
        attempt.task_type != model.TASK_TYPE
        or attempt.isolation_backend != model.BACKEND
        or not attempt.attempt_id.startswith(model.ATTEMPT_PREFIX)
        or attempt.actor != CONTROLLER
    ):
        raise LiteratureIntegrityError("invalid reserved Stage 4 task/backend/prefix/actor tuple")
    manifest = _parse_input_manifest(attempt, read_artifact)
    if (
        manifest["schema"] != "alphaquest.semantic-review-input-manifest/v1"
        or manifest["qualification_class"] != model.QUALIFICATION_CLASS
        or manifest["review_policy_id"] != model.REVIEW_POLICY_ID
    ):
        raise LiteratureIntegrityError("invalid synthetic semantic manifest authority")
    protocol = _exact(
        records, manifest["protocol_revision_sha256"], ResearchProtocolRevisionV1
    )
    claim = _exact(records, manifest["claim_revision_sha256"], ClaimExtractionRevisionV1)
    prepared = _prepare_claim(protocol, claim, records, read_artifact)
    receipt_sha256 = manifest["synthetic_qualification_receipt_sha256"]
    receipt = _parse_receipt(receipt_sha256, records, read_artifact)
    if receipt.protocol_revision_sha256 != protocol.record_sha256:
        raise LiteratureIntegrityError("semantic receipt protocol binding mismatch")
    planned = next(
        (
            item
            for item in receipt.planned_contexts
            if item.review_context_sha256 == prepared.review_context_sha256
        ),
        None,
    )
    fresh = next(
        (
            item
            for item in receipt.fresh_fixture_bindings
            if item.review_context_sha256 == prepared.review_context_sha256
        ),
        None,
    )
    if (
        planned is None
        or fresh is None
        or planned.request_sha256 != prepared.request_sha256
        or planned.claim_ref != RecordReferenceV1.model_validate(reference(claim))
        or fresh.request_sha256 != prepared.request_sha256
    ):
        raise LiteratureIntegrityError("semantic attempt is not fresh-owned by its receipt")
    if (
        attempt.revision == 1
        and receipt.fresh_fixture_bindings[0].review_context_sha256
        == prepared.review_context_sha256
        and attempt.previous_store_record_sha256
        != receipt.initial_store_head_record_sha256
    ):
        raise LiteratureIntegrityError(
            "first receipt-owned STARTED does not immediately follow the frozen prefix"
        )
    _verify_attempt_identity(attempt, prepared, receipt_sha256, read_artifact)
    if manifest != model.parse_json(_input_manifest(prepared, receipt_sha256)):
        raise LiteratureIntegrityError("semantic input manifest reconstruction mismatch")
    output = None
    if attempt.output_sha256 is None:
        if (attempt.status, attempt.failure_reason) not in {
            ("STARTED", None),
            ("ABANDONED_AFTER_CRASH", "ORPHANED_ATTEMPT_NO_REDISPATCH"),
        }:
            raise LiteratureIntegrityError("invalid Stage 4 outcome without retained response")
    else:
        response = read_artifact(attempt.output_sha256, kind="codex-io")
        if (
            type(response) is not bytes
            or len(response) > model.MAX_RESPONSE_BYTES
            or model.sha(response) != attempt.output_sha256
            or attempt.output_sha256 != fresh.fixture_response_sha256
        ):
            raise LiteratureIntegrityError("invalid Stage 4 retained response artifact")
        status, reason, output = _classify_response(response, prepared)
        if (attempt.status, attempt.failure_reason) != (status, reason):
            raise LiteratureIntegrityError(
                "Stage 4 terminal outcome contradicts retained response"
            )
    return ReconstructedAttempt(prepared, receipt, receipt_sha256, output)


def _stage4_attempt(record: CodexTaskAttemptRevisionV1) -> bool:
    return (
        record.isolation_backend == model.BACKEND
        or record.attempt_id.startswith(model.ATTEMPT_PREFIX)
    )


def _dispatch_index(records, read_artifact) -> dict[str, AttemptHistory]:
    grouped: dict[str, list[CodexTaskAttemptRevisionV1]] = {}
    for record in records:
        if isinstance(record, CodexTaskAttemptRevisionV1) and _stage4_attempt(record):
            grouped.setdefault(record.attempt_id, []).append(record)
    by_context: dict[str, AttemptHistory] = {}
    for attempt_id, revisions in grouped.items():
        revisions.sort(key=lambda item: item.append_sequence)
        if (
            len(revisions) not in {1, 2}
            or revisions[0].status != "STARTED"
            or (len(revisions) == 2 and revisions[1].status not in _TERMINAL_STATUSES)
        ):
            raise LiteratureIntegrityError("invalid Stage 4 semantic attempt history")
        reconstructed = []
        for revision in revisions:
            prefix = [
                item for item in records if item.append_sequence < revision.append_sequence
            ]
            reconstructed.append(_reconstruct_attempt(revision, prefix, read_artifact))
        first = reconstructed[0]
        if any(
            item.prepared.review_context_sha256
            != first.prepared.review_context_sha256
            or item.receipt_artifact_sha256 != first.receipt_artifact_sha256
            for item in reconstructed[1:]
        ):
            raise LiteratureIntegrityError("Stage 4 attempt changed context or receipt")
        context = first.prepared.review_context_sha256
        owner = by_context.get(context)
        if owner is not None and owner.attempt_id != attempt_id:
            raise LiteratureIntegrityError(
                "Stage 4 semantic context has multiple attempt owners"
            )
        by_context[context] = AttemptHistory(
            attempt_id=attempt_id,
            review_context_sha256=context,
            receipt_sha256=first.receipt_artifact_sha256,
            revisions=tuple(revisions),
            prepared=first.prepared,
        )
    return by_context


def validate_published_semantic_review_attempt(attempt, records, read_artifact) -> None:
    """Append/reload guard for every reserved Slice A attempt revision."""

    before = [item for item in records if item.append_sequence < attempt.append_sequence]
    reconstructed = _reconstruct_attempt(attempt, before, read_artifact)
    index = _dispatch_index(before, read_artifact)
    owner = index.get(reconstructed.prepared.review_context_sha256)
    if attempt.status == "STARTED":
        if owner is not None:
            raise LiteratureIntegrityError("Stage 4 semantic context was already consumed")
        return
    if (
        owner is None
        or owner.attempt_id != attempt.attempt_id
        or len(owner.revisions) != 1
        or owner.revisions[0].status != "STARTED"
    ):
        raise LiteratureIntegrityError("invalid Stage 4 semantic terminal transition")


def _terminal(store, started, status, *, output_sha=None, reason=None):
    payload = started.model_dump(
        mode="json",
        include={
            "attempt_id",
            "task_type",
            "model",
            "settings_sha256",
            "prompt_sha256",
            "input_manifest_sha256",
            "workspace_manifest_sha256",
            "referenced_records",
            "isolation_backend",
        },
    )
    payload.update(status=status, output_sha256=output_sha, failure_reason=reason)
    return store.append_codex_attempt(
        payload,
        actor=CONTROLLER,
        idempotency_key=started.attempt_id + ".terminal",
    )


def _attempt_result(
    history: AttemptHistory,
    reconstructed: ReconstructedAttempt,
    *,
    reused: bool,
) -> dict:
    attempt = history.revisions[-1]
    advisory = (
        derive_advisory_use(
            reconstructed.output, reconstructed.prepared.claim.source_epistemic_form
        )
        if attempt.status == "SUCCEEDED" and reconstructed.output is not None
        else None
    )
    return {
        "claim_id": reconstructed.prepared.claim.claim_id,
        "claim_revision_sha256": reconstructed.prepared.claim.record_sha256,
        "review_context_sha256": reconstructed.prepared.review_context_sha256,
        "attempt_id": attempt.attempt_id,
        "owning_receipt_sha256": reconstructed.receipt_artifact_sha256,
        "status": attempt.status,
        "p3_advisory_use": advisory,
        "reused": reused,
        "current": True,
    }


def _fresh_started_payload(
    prepared: PreparedSemanticReview, receipt_sha256: str
) -> dict:
    input_manifest = _input_manifest(prepared, receipt_sha256)
    boundary_manifest = _boundary_manifest(prepared, receipt_sha256)
    return {
        "attempt_id": prepared.attempt_id,
        "task_type": model.TASK_TYPE,
        "status": "STARTED",
        "model": model.MODEL_CONTRACT,
        "settings_sha256": model.sha(model.settings_bytes()),
        "prompt_sha256": model.sha(model.PROMPT.encode("utf-8")),
        "input_manifest_sha256": model.sha(input_manifest),
        "workspace_manifest_sha256": model.sha(boundary_manifest),
        "output_sha256": None,
        "referenced_records": list(prepared.references),
        "isolation_backend": model.BACKEND,
        "failure_reason": None,
    }


def _snapshot_fixture_mapping(mapping: Mapping[str, bytes]) -> dict[str, bytes]:
    snapshot = dict(mapping)
    for key, value in snapshot.items():
        if (
            type(key) is not str
            or len(key) != 64
            or any(character not in "0123456789abcdef" for character in key)
            or type(value) is not bytes
            or len(value) > model.MAX_RESPONSE_BYTES
        ):
            raise ValueError("invalid bounded synthetic fixture mapping")
    return snapshot


def _result(protocol, attempts: list[dict], planned_count: int) -> dict:
    decisions = [item["p3_advisory_use"] for item in attempts if item["status"] == "SUCCEEDED"]
    receipt_refs = list(
        dict.fromkeys(item["owning_receipt_sha256"] for item in attempts)
    )
    return {
        "review_policy_id": model.REVIEW_POLICY_ID,
        "protocol_revision_sha256": protocol.record_sha256,
        "qualification_class": model.QUALIFICATION_CLASS,
        "synthetic_fixture_only": True,
        "synthetic_qualification_receipt_sha256": (
            receipt_refs[0] if len(receipt_refs) == 1 else None
        ),
        "receipt_refs": receipt_refs,
        "attempts": attempts,
        "eligible_direct_count": decisions.count("ELIGIBLE_DIRECT"),
        "eligible_context_count": decisions.count("ELIGIBLE_CONTEXT_ONLY"),
        "excluded_count": sum(
            decision in {"AMBIGUOUS_EXCLUDED", "INELIGIBLE_EXCLUDED"}
            for decision in decisions
        ),
        "complete": (
            len(attempts) == planned_count
            and all(item["status"] == "SUCCEEDED" for item in attempts)
        ),
    }


def run_semantic_review_synthetic(
    project_root: str | Path,
    protocol_revision_sha: str,
    *,
    response_by_request_sha256: Mapping[str, bytes],
    qualification_class: Literal["SYNTHETIC_FIXTURE_ONLY"],
) -> dict:
    """Run one fully preflighted, retained-fixture-only semantic review batch."""

    if type(qualification_class) is not str or qualification_class != model.QUALIFICATION_CLASS:
        raise LiteratureAuthorityError(
            "synthetic semantic review requires the literal SYNTHETIC_FIXTURE_ONLY"
        )
    fixtures = _snapshot_fixture_mapping(response_by_request_sha256)
    store = LiteratureStore(project_root)
    lock_name = "run-store/literature/stage4-semantic-review.lock"
    with repository_file_lock(store.project_root, lock_name, exclusive=True):
        records = _snapshot(store)
        protocol = _exact(records, protocol_revision_sha, ResearchProtocolRevisionV1)
        planned = _prepare_plan(protocol, records, store.verify_artifact)
        if not planned:
            if fixtures:
                raise ValueError("zero-claim semantic review requires an empty fixture mapping")
            return _result(protocol, [], 0)

        index = _dispatch_index(records, store.verify_artifact)
        histories = [index.get(item.review_context_sha256) for item in planned]

        # Whole-batch conflict scan precedes every new artifact or fresh STARTED.
        for prepared, history in zip(planned, histories, strict=True):
            if history is None:
                continue
            if history.attempt_id != prepared.attempt_id:
                raise LiteratureIntegrityError(
                    "semantic review context owner attempt identity mismatch"
                )
            latest = history.revisions[-1]
            if latest.status in {"FAILED", "INVALID_OUTPUT", "ABANDONED_AFTER_CRASH"}:
                if fixtures:
                    raise PilotManualReconciliation(
                        "terminal semantic review consumed context; alternative fixture rejected"
                    )
                reconstructed = _reconstruct_attempt(
                    latest,
                    [r for r in records if r.append_sequence < latest.append_sequence],
                    store.verify_artifact,
                )
                prior = []
                for earlier, earlier_history in zip(planned, histories, strict=True):
                    if earlier.review_context_sha256 == prepared.review_context_sha256:
                        break
                    if earlier_history is None:
                        continue
                    terminal = earlier_history.revisions[-1]
                    rebuilt = _reconstruct_attempt(
                        terminal,
                        [r for r in records if r.append_sequence < terminal.append_sequence],
                        store.verify_artifact,
                    )
                    prior.append(_attempt_result(earlier_history, rebuilt, reused=True))
                prior.append(_attempt_result(history, reconstructed, reused=True))
                return _result(protocol, prior, len(planned))

        orphans = [
            history
            for history in histories
            if history is not None and history.revisions[-1].status == "STARTED"
        ]
        if orphans:
            if fixtures:
                raise PilotManualReconciliation(
                    "orphaned semantic review rejects alternative fixture mapping"
                )
            # Every history and receipt was reconstructed above before this sole write.
            orphan = orphans[0]
            _terminal(
                store,
                orphan.revisions[-1],
                "ABANDONED_AFTER_CRASH",
                reason="ORPHANED_ATTEMPT_NO_REDISPATCH",
            )
            raise PilotManualReconciliation(
                "orphaned semantic review abandoned; no redispatch or later progress"
            )

        # Select a frozen partially progressed receipt before considering new data.
        partial_receipts: set[str] = set()
        for history in histories:
            if history is None:
                continue
            receipt = _parse_receipt(history.receipt_sha256, records, store.verify_artifact)
            current_contexts = {item.review_context_sha256 for item in planned}
            receipt_contexts = {
                item.review_context_sha256 for item in receipt.planned_contexts
            }
            owned_contexts = set(index)
            if (receipt_contexts & current_contexts) - owned_contexts:
                partial_receipts.add(history.receipt_sha256)
        if len(partial_receipts) > 1:
            raise LiteratureIntegrityError(
                "partially progressed semantic batch names multiple frozen receipts"
            )

        selected_receipt_sha256: str | None = None
        selected_receipt: SyntheticSemanticQualificationReceiptV1 | None = None
        runnable_contexts: set[str] = set()
        if partial_receipts:
            if fixtures:
                raise ValueError("frozen-receipt reentry requires an empty fixture mapping")
            selected_receipt_sha256 = next(iter(partial_receipts))
            selected_receipt = _parse_receipt(
                selected_receipt_sha256, records, store.verify_artifact
            )
            anchor = next(
                item
                for item in records
                if item.record_sha256
                == selected_receipt.initial_store_head_record_sha256
            )
            for record in records:
                if (
                    not isinstance(record, CodexTaskAttemptRevisionV1)
                    or not _stage4_attempt(record)
                    or record.append_sequence <= anchor.append_sequence
                ):
                    continue
                manifest = _parse_input_manifest(record, store.verify_artifact)
                if (
                    manifest["synthetic_qualification_receipt_sha256"]
                    != selected_receipt_sha256
                ):
                    raise LiteratureIntegrityError(
                        "intervening Slice A attempt disagrees with frozen partial receipt"
                    )
            current_contexts = {item.review_context_sha256 for item in planned}
            declared = [
                item.review_context_sha256 for item in selected_receipt.planned_contexts
            ]
            if not set(declared).issubset(current_contexts):
                raise LiteratureIntegrityError(
                    "frozen semantic receipt contains a stale or missing planned context"
                )
            runnable_contexts = set(declared)
        else:
            fresh = [
                item for item, history in zip(planned, histories, strict=True)
                if history is None
            ]
            if not fresh:
                if fixtures:
                    raise ValueError("all-success reentry requires an empty fixture mapping")
            else:
                expected_keys = {item.request_sha256 for item in fresh}
                if set(fixtures) != expected_keys:
                    raise ValueError(
                        "synthetic fixture keys must exactly match every fresh request"
                    )
                reused_bindings = []
                for history in histories:
                    if history is None:
                        continue
                    terminal = history.revisions[-1]
                    if terminal.status != "SUCCEEDED":
                        raise LiteratureIntegrityError(
                            "non-success semantic owner cannot be skipped by a new receipt"
                        )
                    reused_bindings.append(
                        {
                            "review_context_sha256": history.review_context_sha256,
                            "owner_attempt_id": history.attempt_id,
                            "terminal_attempt_sha256": terminal.record_sha256,
                            "owner_receipt_sha256": history.receipt_sha256,
                        }
                    )
                fresh_bindings = [
                    {
                        "review_context_sha256": item.review_context_sha256,
                        "request_sha256": item.request_sha256,
                        "fixture_response_sha256": model.sha(fixtures[item.request_sha256]),
                        "fixture_response_byte_count": len(fixtures[item.request_sha256]),
                    }
                    for item in fresh
                ]
                receipt_bytes = _receipt_material(
                    protocol, planned, records, reused_bindings, fresh_bindings
                )
                selected_receipt_sha256 = model.sha(receipt_bytes)

                # Fixed publication order: all raw responses, then receipt, then inputs.
                for item in fresh:
                    store.put_artifact(fixtures[item.request_sha256], kind="codex-io")
                if store.put_artifact(receipt_bytes, kind="codex-io") != selected_receipt_sha256:
                    raise LiteratureIntegrityError("semantic receipt publication hash mismatch")
                for item in fresh:
                    for artifact in (
                        model.settings_bytes(),
                        model.PROMPT.encode("utf-8"),
                        item.request,
                        _input_manifest(item, selected_receipt_sha256),
                        _boundary_manifest(item, selected_receipt_sha256),
                    ):
                        store.put_artifact(artifact, kind="codex-io")
                records = _snapshot(store)
                selected_receipt = _parse_receipt(
                    selected_receipt_sha256, records, store.verify_artifact
                )
                runnable_contexts = {item.review_context_sha256 for item in fresh}

        execution_items = list(zip(planned, histories, strict=True))
        if partial_receipts:
            by_context = {
                item.review_context_sha256: (item, history)
                for item, history in execution_items
            }
            execution_items = [
                by_context[item.review_context_sha256]
                for item in selected_receipt.planned_contexts
            ]

        attempts: list[dict] = []
        for prepared, history in execution_items:
            if history is not None:
                terminal = history.revisions[-1]
                rebuilt = _reconstruct_attempt(
                    terminal,
                    [r for r in records if r.append_sequence < terminal.append_sequence],
                    store.verify_artifact,
                )
                attempts.append(_attempt_result(history, rebuilt, reused=True))
                continue
            if prepared.review_context_sha256 not in runnable_contexts:
                break
            if selected_receipt is None or selected_receipt_sha256 is None:
                raise LiteratureIntegrityError("fresh semantic context has no receipt")

            # Recheck exact currentness immediately before STARTED.
            current_records = _snapshot(store)
            current_protocol = _exact(
                current_records, protocol.record_sha256, ResearchProtocolRevisionV1
            )
            current = _prepare_claim(
                current_protocol, prepared.claim, current_records, store.verify_artifact
            )
            if (
                current.review_context_sha256 != prepared.review_context_sha256
                or current.request != prepared.request
                or current.references != prepared.references
            ):
                raise LiteratureIntegrityError(
                    "semantic review input drifted before STARTED"
                )
            fixture = next(
                item
                for item in selected_receipt.fresh_fixture_bindings
                if item.review_context_sha256 == prepared.review_context_sha256
            )
            started = store.append_codex_attempt(
                _fresh_started_payload(prepared, selected_receipt_sha256),
                actor=CONTROLLER,
                idempotency_key=prepared.attempt_id + ".start",
            )
            response = store.verify_artifact(
                fixture.fixture_response_sha256, kind="codex-io"
            )
            status, reason, output = _classify_response(response, prepared)
            terminal = _terminal(
                store,
                started,
                status,
                output_sha=fixture.fixture_response_sha256,
                reason=reason,
            )
            current_records = _snapshot(store)
            rebuilt = _reconstruct_attempt(
                terminal,
                [r for r in current_records if r.append_sequence < terminal.append_sequence],
                store.verify_artifact,
            )
            new_history = AttemptHistory(
                attempt_id=prepared.attempt_id,
                review_context_sha256=prepared.review_context_sha256,
                receipt_sha256=selected_receipt_sha256,
                revisions=(started, terminal),
                prepared=prepared,
            )
            attempts.append(_attempt_result(new_history, rebuilt, reused=False))
            if output is None:
                break
        return _result(protocol, attempts, len(planned))


def load_synthetic_semantic_review_evidence(
    store: LiteratureStore,
    attempt_id: str,
    *,
    required_receipt_sha256: str,
) -> SyntheticSemanticReviewEvidenceV1:
    records = _snapshot(store)
    revisions = [
        item
        for item in records
        if isinstance(item, CodexTaskAttemptRevisionV1)
        and item.attempt_id == attempt_id
    ]
    if len(revisions) != 2 or revisions[-1].status != "SUCCEEDED":
        raise LiteratureAuthorityError("synthetic semantic evidence is not successful")
    terminal = revisions[-1]
    prefix = [item for item in records if item.append_sequence < terminal.append_sequence]
    rebuilt = _reconstruct_attempt(terminal, prefix, store.verify_artifact)
    if rebuilt.receipt_artifact_sha256 != required_receipt_sha256:
        raise LiteratureAuthorityError("synthetic semantic receipt identity mismatch")
    if rebuilt.output is None:
        raise LiteratureIntegrityError("successful synthetic semantic evidence has no output")
    current = _claim_currentness_issue(rebuilt.prepared.claim, records) is None
    return SyntheticSemanticReviewEvidenceV1(
        qualification_class=model.QUALIFICATION_CLASS,
        review_policy_id=model.REVIEW_POLICY_ID,
        attempt_id=terminal.attempt_id,
        terminal_attempt_sha256=terminal.record_sha256,
        claim_id=rebuilt.prepared.claim.claim_id,
        claim_revision_sha256=rebuilt.prepared.claim.record_sha256,
        review_context_sha256=rebuilt.prepared.review_context_sha256,
        receipt_sha256=rebuilt.receipt_artifact_sha256,
        p3_advisory_use=derive_advisory_use(
            rebuilt.output, rebuilt.prepared.claim.source_epistemic_form
        ),
        current=current,
    )


def require_production_semantic_review(
    evidence: SyntheticSemanticReviewEvidenceV1,
) -> NoReturn:
    if evidence.qualification_class != model.QUALIFICATION_CLASS:  # pragma: no cover
        raise LiteratureAuthorityError("unsupported semantic evidence class")
    raise LiteratureAuthorityError(
        "synthetic semantic review is not production eligibility"
    )
