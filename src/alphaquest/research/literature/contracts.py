"""Strict canonical contracts for the offline P3 literature layer.

P3 records are pre-hypothesis research memory.  They never carry campaign,
execution, PnL, scientific-verdict, or deployment authority.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from alphaquest.research.edge_backlog_taxonomy import EconomicConceptsV1, TaxonomyRefV1


SHA256_PATTERN = r"^[a-f0-9]{64}$"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,127}$"
RECORD_IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,255}$"
Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]
Identifier = Annotated[str, Field(pattern=IDENTIFIER_PATTERN)]
RecordIdentifier = Annotated[str, Field(pattern=RECORD_IDENTIFIER_PATTERN)]
NonBlank = Annotated[str, Field(min_length=1)]

REQUIRED_SEARCH_LANES = (
    "SUPPORTING_OR_MOTIVATING",
    "NULL_OR_CONTRARY",
    "FAILED_REPLICATION",
    "REGIME_DEPENDENCE",
    "TRANSACTION_COST_OR_EXECUTION_OBJECTION",
    "ALTERNATIVE_EXPLANATION",
    "DATA_MINING_OR_MULTIPLE_TESTING",
)
SearchLane = Literal[
    "SUPPORTING_OR_MOTIVATING",
    "NULL_OR_CONTRARY",
    "FAILED_REPLICATION",
    "REGIME_DEPENDENCE",
    "TRANSACTION_COST_OR_EXECUTION_OBJECTION",
    "ALTERNATIVE_EXPLANATION",
    "DATA_MINING_OR_MULTIPLE_TESTING",
]
_TRUSTED_CANONICAL_WRITER_CONTEXT = object()


class LiteratureError(RuntimeError):
    """Base P3 contract or persistence failure."""


class LiteratureIntegrityError(LiteratureError):
    """Persisted P3 state is malformed or no longer verifiable."""


class LiteratureConflictError(LiteratureError):
    """An idempotency, revision, reservation, or lifecycle conflict."""


class LiteratureAuthorityError(LiteratureError):
    """A caller attempted authority that P3 does not own."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, populate_by_name=True)


class ActorProvenanceV1(StrictModel):
    actor_class: Literal["CODEX", "HUMAN_OWNER_RESEARCHER", "ALPHAQUEST_DETERMINISTIC_ENGINE"]
    actor_id: Identifier
    task_id: Identifier | None = None


def canonical_json_bytes(value: Any, *, trailing_lf: bool = True) -> bytes:
    """Return the sole P3 canonical JSON representation."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)

    def normalize(node: Any) -> Any:
        if isinstance(node, datetime):
            if node.tzinfo is None or node.utcoffset() is None:
                raise ValueError("canonical datetime values must be timezone-aware")
            return node.isoformat().replace("+00:00", "Z")
        if isinstance(node, BaseModel):
            return normalize(node.model_dump(mode="json", by_alias=True))
        if isinstance(node, dict):
            return {key: normalize(child) for key, child in node.items()}
        if isinstance(node, (list, tuple)):
            return [normalize(child) for child in node]
        if isinstance(node, Enum):
            return node.value
        return node

    value = normalize(value)

    def reject_noncanonical(node: Any) -> None:
        if isinstance(node, float) and not math.isfinite(node):
            raise ValueError("non-finite numbers are not canonical JSON")
        if isinstance(node, dict):
            if not all(isinstance(key, str) for key in node):
                raise ValueError("canonical JSON object keys must be strings")
            for child in node.values():
                reject_noncanonical(child)
        elif isinstance(node, list):
            for child in node:
                reject_noncanonical(child)

    reject_noncanonical(value)
    body = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return body + (b"\n" if trailing_lf else b"")


def record_sha256(value: BaseModel | dict[str, Any]) -> str:
    material = value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else dict(value)
    material.pop("record_sha256", None)
    return hashlib.sha256(canonical_json_bytes(material, trailing_lf=False)).hexdigest()


class CanonicalRecordV1(StrictModel):
    schema_name: str = Field(alias="schema", serialization_alias="schema")
    record_id: RecordIdentifier
    append_sequence: Annotated[int, Field(ge=1)]
    previous_store_record_sha256: Sha256 | None = None
    recorded_at: datetime
    actor: ActorProvenanceV1
    idempotency_key: Identifier
    intent_sha256: Sha256
    record_sha256: Sha256

    family: ClassVar[str]
    schema_literal: ClassVar[str]

    @field_validator("recorded_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_envelope(self, info: ValidationInfo) -> "CanonicalRecordV1":
        if self.schema_name != self.schema_literal:
            raise ValueError(f"schema must be {self.schema_literal!r}")
        if (self.append_sequence == 1) != (self.previous_store_record_sha256 is None):
            raise ValueError("store predecessor must be null exactly for append_sequence 1")
        if info.context is not _TRUSTED_CANONICAL_WRITER_CONTEXT and self.record_sha256 != record_sha256(self):
            raise ValueError("record_sha256 does not match canonical record content")
        return self


class RevisionRecordV1(CanonicalRecordV1):
    revision: Annotated[int, Field(ge=1)]
    previous_revision_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def validate_revision(self) -> "RevisionRecordV1":
        if (self.revision == 1) != (self.previous_revision_sha256 is None):
            raise ValueError("revision predecessor must be null exactly for revision 1")
        return self


class SaturationCriterionV1(StrictModel):
    enabled: bool
    minimum_queries_before_check: Annotated[int, Field(ge=1)]
    consecutive_queries_without_new_work: Annotated[int, Field(ge=1)]


class SearchLaneProtocolV1(StrictModel):
    lane: SearchLane
    required_initial_queries: Annotated[list[NonBlank], Field(min_length=1)]
    provider_order: Annotated[list[Identifier], Field(min_length=1)]
    minimum_provider_attempts: Annotated[int, Field(ge=1)]
    minimum_results_inspected_per_query: Annotated[int, Field(ge=0)]
    minimum_distinct_results_inspected: Annotated[int, Field(ge=0)]
    minimum_capture_attempts: Annotated[int, Field(ge=0)]
    capture_selection_rule: Literal["PROVIDER_RANK_THEN_RESULT_RANK_THEN_LOCATOR_HASH"]
    adaptive_max_depth: Annotated[int, Field(ge=0)]
    maximum_queries: Annotated[int, Field(ge=1)]
    maximum_results: Annotated[int, Field(ge=1)]
    maximum_captures: Annotated[int, Field(ge=0)]
    maximum_bytes: Annotated[int, Field(ge=1)]
    maximum_elapsed_seconds: Annotated[int, Field(ge=1)]
    saturation: SaturationCriterionV1 | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "SearchLaneProtocolV1":
        if len(self.required_initial_queries) != len(set(self.required_initial_queries)):
            raise ValueError("required_initial_queries must be unique")
        if len(self.provider_order) != len(set(self.provider_order)):
            raise ValueError("provider_order must be unique")
        if self.maximum_queries < len(self.required_initial_queries):
            raise ValueError("maximum_queries cannot be below required initial query count")
        if self.maximum_captures < self.minimum_capture_attempts:
            raise ValueError("maximum_captures cannot be below minimum_capture_attempts")
        return self


class ResearchProtocolRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "protocols"
    schema_literal: ClassVar[str] = "alphaquest.literature-research-protocol-revision/v1"
    protocol_id: Identifier
    execution_lineage_id: Identifier
    lineage_kind: Literal["PRE_RESULT_PROTOCOL", "RESULT_INFORMED_EXTENSION"]
    parent_execution_lineage_id: Identifier | None = None
    observed_result_set_sha256: Sha256 | None = None
    research_question: NonBlank
    market_scope: Annotated[list[NonBlank], Field(min_length=1)]
    inclusion_rules: list[NonBlank]
    exclusion_rules: list[NonBlank]
    lanes: Annotated[list[SearchLaneProtocolV1], Field(min_length=7, max_length=7)]
    administrative_annotations: list[NonBlank] = Field(default_factory=list)
    change_reason: NonBlank
    methodology_sha256: Sha256

    @model_validator(mode="after")
    def validate_protocol(self) -> "ResearchProtocolRevisionV1":
        if self.record_id != f"{self.protocol_id}.r{self.revision:06d}":
            raise ValueError("protocol record_id does not match protocol identity/revision")
        if tuple(sorted(item.lane for item in self.lanes)) != tuple(sorted(REQUIRED_SEARCH_LANES)):
            raise ValueError("protocol must contain every mandatory search lane exactly once")
        extension = self.lineage_kind == "RESULT_INFORMED_EXTENSION"
        if extension != (self.parent_execution_lineage_id is not None):
            raise ValueError("result-informed lineage requires one parent lineage")
        if extension != (self.observed_result_set_sha256 is not None):
            raise ValueError("result-informed lineage requires observed result-set provenance")
        if self.methodology_sha256 != methodology_sha256(self.model_dump(mode="json")):
            raise ValueError("methodology_sha256 does not bind the complete execution contract")
        return self


class SearchResultInspectionV1(StrictModel):
    """One stable inspected-result identity with deterministic provider ranking."""

    result_identity_sha256: Sha256
    work_identity_sha256: Sha256
    canonical_locator: NonBlank
    locator_sha256: Sha256
    provider_rank: Annotated[int, Field(ge=1)]
    result_rank: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def validate_result_identity(self) -> "SearchResultInspectionV1":
        locator_hash = hashlib.sha256(self.canonical_locator.encode("utf-8")).hexdigest()
        if self.locator_sha256 != locator_hash:
            raise ValueError("search result locator_sha256 does not match canonical_locator")
        identity = hashlib.sha256(
            canonical_json_bytes(
                {
                    "canonical_locator": self.canonical_locator,
                    "work_identity_sha256": self.work_identity_sha256,
                },
                trailing_lf=False,
            )
        ).hexdigest()
        if self.result_identity_sha256 != identity:
            raise ValueError("search result identity is not derived from stable work/locator identity")
        return self


class SearchCaptureAttemptV1(StrictModel):
    capture_attempt_id: Identifier
    result_identity_sha256: Sha256
    selection_ordinal: Annotated[int, Field(ge=1)]


class SearchRunRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "searches"
    schema_literal: ClassVar[str] = "alphaquest.literature-search-run-revision/v1"
    search_run_id: Identifier
    protocol_id: Identifier
    protocol_revision_sha256: Sha256
    execution_lineage_id: Identifier
    lane: SearchLane
    query: NonBlank
    query_kind: Literal["INITIAL", "ADAPTIVE"]
    parent_search_run_id: Identifier | None = None
    adaptive_depth: Annotated[int, Field(ge=0)]
    provider_id: Identifier
    provider_attempt_ordinal: Annotated[int, Field(ge=1)]
    status: Literal["STARTED", "SUCCEEDED", "PARTIAL", "FAILED", "ABANDONED_AFTER_CRASH"]
    results_inspected: Annotated[int, Field(ge=0)] = 0
    capture_attempts: Annotated[int, Field(ge=0)] = 0
    inspected_results: list[SearchResultInspectionV1] = Field(default_factory=list)
    capture_attempt_records: list[SearchCaptureAttemptV1] = Field(default_factory=list)
    bytes_retrieved: Annotated[int, Field(ge=0)] = 0
    elapsed_seconds: Annotated[int, Field(ge=0)] = 0
    result_set_sha256: Sha256 | None = None
    saturation_claimed: bool = False
    provider_trace_completeness: Literal[
        "COMPLETE_FOR_REQUEST", "PARTIAL_PROVIDER_TRACE", "AGENT_REPORTED_ONLY", "UNAVAILABLE", "UNKNOWN"
    ]
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_search(self) -> "SearchRunRevisionV1":
        if self.record_id != f"{self.search_run_id}.r{self.revision:06d}":
            raise ValueError("search record_id does not match search identity/revision")
        if (self.query_kind == "ADAPTIVE") != (self.parent_search_run_id is not None):
            raise ValueError("adaptive queries require exactly one parent search run")
        if self.query_kind == "INITIAL" and self.adaptive_depth != 0:
            raise ValueError("initial queries require adaptive_depth 0")
        if self.status == "STARTED" and self.revision != 1:
            raise ValueError("only the first search revision may be STARTED")
        if self.results_inspected != len(self.inspected_results):
            raise ValueError("results_inspected must equal the exact inspected-result record count")
        if self.capture_attempts != len(self.capture_attempt_records):
            raise ValueError("capture_attempts must equal the exact capture-attempt record count")
        if len({item.result_identity_sha256 for item in self.inspected_results}) != len(self.inspected_results):
            raise ValueError("one search run cannot inspect the same stable result identity twice")
        if len({item.capture_attempt_id for item in self.capture_attempt_records}) != len(self.capture_attempt_records):
            raise ValueError("capture attempt identities must be unique inside one search run")
        if self.status == "STARTED" and any(
            (
                self.results_inspected,
                self.capture_attempts,
                self.inspected_results,
                self.capture_attempt_records,
                self.bytes_retrieved,
                self.elapsed_seconds,
                self.result_set_sha256,
                self.saturation_claimed,
            )
        ):
            raise ValueError("STARTED search cannot claim results")
        if self.status != "STARTED":
            expected_result_set = hashlib.sha256(
                canonical_json_bytes(self.inspected_results, trailing_lf=False)
            ).hexdigest()
            if self.result_set_sha256 != expected_result_set:
                raise ValueError("terminal result_set_sha256 must bind the exact inspected-result records")
        if self.status in {"FAILED", "ABANDONED_AFTER_CRASH"} and not self.failure_reason:
            raise ValueError("failed search requires failure_reason")
        return self


class PublicAvailabilityV1(StrictModel):
    original_value: NonBlank | None = None
    parsed_value: datetime | None = None
    precision: Literal["EXACT_INSTANT", "DAY", "MONTH", "YEAR", "UNKNOWN"]
    verification: Literal["VERIFIED", "SOURCE_REPORTED_UNVERIFIED", "CONFLICTING", "UNKNOWN"]
    timezone_basis: NonBlank | None = None
    provenance_record_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_availability(self) -> "PublicAvailabilityV1":
        exact = self.precision == "EXACT_INSTANT" and self.verification == "VERIFIED"
        if exact:
            if self.parsed_value is None or self.parsed_value.tzinfo is None or self.parsed_value.utcoffset() is None:
                raise ValueError("verified exact availability requires a timezone-aware instant")
        elif self.parsed_value is not None and self.precision == "UNKNOWN":
            raise ValueError("UNKNOWN precision cannot carry a parsed instant")
        return self


class SourceIdentityRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "source-works"
    schema_literal: ClassVar[str] = "alphaquest.literature-source-identity-revision/v1"
    work_id: Identifier
    source_category: Literal[
        "ACADEMIC", "WORKING_PAPER", "EXCHANGE", "REGULATOR", "PRACTITIONER", "MARKET_MICROSTRUCTURE", "OTHER"
    ]
    title: NonBlank
    authors: list[NonBlank]
    strong_identifiers: dict[Identifier, NonBlank] = Field(default_factory=dict)
    locators: Annotated[list[NonBlank], Field(min_length=1)]
    identity_status: Literal["VERIFIED_STRONG", "PROVISIONAL", "AMBIGUOUS"]
    change_reason: NonBlank

    @model_validator(mode="after")
    def validate_work(self) -> "SourceIdentityRevisionV1":
        if self.record_id != f"{self.work_id}.r{self.revision:06d}":
            raise ValueError("work record_id does not match work identity/revision")
        if len(self.locators) != len(set(self.locators)):
            raise ValueError("source locators must be unique")
        return self


class SourceVersionIdentityRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "source-versions"
    schema_literal: ClassVar[str] = "alphaquest.literature-source-version-identity-revision/v1"
    source_version_id: Identifier
    work_id: Identifier
    work_revision_sha256: Sha256
    version_kind: Literal[
        "ORIGINAL", "WORKING_PAPER_REVISION", "PUBLISHED_SUCCESSOR", "CORRECTION_NOTICE", "RETRACTION_NOTICE", "OTHER"
    ]
    version_label: NonBlank
    strong_identifiers: dict[Identifier, NonBlank] = Field(default_factory=dict)
    public_availability: PublicAvailabilityV1
    identity_status: Literal["VERIFIED_STRONG", "PROVISIONAL", "AMBIGUOUS"]
    change_reason: NonBlank

    @model_validator(mode="after")
    def validate_version(self) -> "SourceVersionIdentityRevisionV1":
        if self.record_id != f"{self.source_version_id}.r{self.revision:06d}":
            raise ValueError("version record_id does not match version identity/revision")
        return self


class RecordReferenceV1(StrictModel):
    record_id: RecordIdentifier
    record_sha256: Sha256


class SourceRelationshipRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "source-relationships"
    schema_literal: ClassVar[str] = "alphaquest.literature-source-relationship-revision/v1"
    relationship_id: Identifier
    subject_kind: Literal["WORK", "SOURCE_VERSION"]
    subject_id: Identifier
    predicate: Literal[
        "POSSIBLE_SAME_WORK",
        "POSSIBLE_SAME_VERSION",
        "SAME_WORK_AS",
        "SAME_VERSION_AS",
        "REVISION_OF",
        "PUBLISHED_SUCCESSOR_OF",
        "CORRECTS",
        "RETRACTS",
    ]
    object_kind: Literal["WORK", "SOURCE_VERSION"]
    object_id: Identifier
    status: Literal["ACTIVE", "RETRACTED", "SUPERSEDED"]
    assertion_evidence_refs: list[RecordReferenceV1] = Field(default_factory=list)
    superseded_by_relationship_id: Identifier | None = None
    change_reason: NonBlank

    @model_validator(mode="after")
    def validate_relationship(self) -> "SourceRelationshipRevisionV1":
        if self.record_id != f"{self.relationship_id}.r{self.revision:06d}":
            raise ValueError("relationship record_id does not match identity/revision")
        if self.subject_id == self.object_id:
            raise ValueError("source relationship cannot target itself")
        if (self.status == "SUPERSEDED") != (self.superseded_by_relationship_id is not None):
            raise ValueError("SUPERSEDED requires one replacement relationship")
        if self.revision == 1 and self.status != "ACTIVE":
            raise ValueError("first relationship revision must be ACTIVE")
        if self.predicate in {"SAME_WORK_AS", "SAME_VERSION_AS"} and self.actor.actor_class != "HUMAN_OWNER_RESEARCHER":
            raise ValueError("authoritative identity equivalence is human-owned")
        work_relation = self.predicate in {"POSSIBLE_SAME_WORK", "SAME_WORK_AS"}
        if work_relation and (self.subject_kind != "WORK" or self.object_kind != "WORK"):
            raise ValueError("work-equivalence relationships require two WORK identities")
        if not work_relation and (self.subject_kind != "SOURCE_VERSION" or self.object_kind != "SOURCE_VERSION"):
            raise ValueError("version relationships require two SOURCE_VERSION identities")
        return self


class SourceCaptureRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "captures"
    schema_literal: ClassVar[str] = "alphaquest.literature-source-capture-revision/v1"
    capture_id: Identifier
    source_version_id: Identifier
    source_version_revision_sha256: Sha256
    retrieval_locator: NonBlank
    status: Literal[
        "STARTED", "FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED", "LOCATOR_METADATA_ONLY", "FAILED"
    ]
    captured_at: datetime
    access_basis: Literal["OPEN_PUBLIC", "AUTHORIZED_LOCAL_RETENTION", "OWNER_PROVIDED", "INACCESSIBLE"]
    local_retention_permission: Literal["ALLOWED", "UNKNOWN", "PROHIBITED"]
    redistribution_permission: Literal["ALLOWED", "RESTRICTED", "UNKNOWN", "PROHIBITED"]
    external_model_processing_permission: Literal[
        "ALLOWED_EXTERNAL_PROCESSOR", "LOCAL_ONLY", "UNKNOWN", "PROHIBITED"
    ]
    media_type: NonBlank | None = None
    content_sha256: Sha256 | None = None
    content_bytes: Annotated[int, Field(ge=0)] | None = None
    extracted_representation_sha256: Sha256 | None = None
    extracted_bytes: Annotated[int, Field(ge=0)] | None = None
    extractor_id: Identifier | None = None
    extractor_version: NonBlank | None = None
    extractor_config_sha256: Sha256 | None = None
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_capture(self) -> "SourceCaptureRevisionV1":
        if self.record_id != f"{self.capture_id}.r{self.revision:06d}":
            raise ValueError("capture record_id does not match capture identity/revision")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        evidence = self.status in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}
        required = (
            self.content_sha256,
            self.content_bytes,
            self.extracted_representation_sha256,
            self.extracted_bytes,
            self.extractor_id,
            self.extractor_version,
            self.extractor_config_sha256,
        )
        if evidence and any(value is None for value in required):
            raise ValueError("captured evidence requires complete artifact/extractor provenance")
        if evidence and self.local_retention_permission != "ALLOWED":
            raise ValueError("captured evidence requires explicit local retention permission")
        if evidence and self.access_basis == "INACCESSIBLE":
            raise ValueError("inaccessible locator metadata cannot claim captured evidence")
        if not evidence and any(value is not None for value in required):
            raise ValueError("non-evidence capture cannot claim inspectable artifact provenance")
        if self.status == "STARTED" and self.revision != 1:
            raise ValueError("only first capture revision may be STARTED")
        if self.status == "FAILED" and not self.failure_reason:
            raise ValueError("failed capture requires failure_reason")
        return self


class ClaimLocationV1(StrictModel):
    representation_kind: Literal["PDF", "HTML", "STRUCTURED_ABSTRACT", "PLAIN_TEXT"]
    page_number: Annotated[int, Field(ge=1)] | None = None
    section_anchor: str | None = None
    block_ordinal: Annotated[int, Field(ge=0)] | None = None
    byte_start: Annotated[int, Field(ge=0)]
    byte_end: Annotated[int, Field(ge=1)]
    span_sha256: Sha256
    locator_sha256: Sha256

    @model_validator(mode="after")
    def validate_location(self) -> "ClaimLocationV1":
        if self.byte_end <= self.byte_start:
            raise ValueError("claim byte range must be non-empty")
        if self.representation_kind == "PDF" and self.page_number is None:
            raise ValueError("PDF claim requires page_number")
        if self.representation_kind != "PDF" and self.page_number is not None:
            raise ValueError("only PDF claims may carry page_number")
        material = self.model_dump(mode="json", exclude={"locator_sha256"})
        actual = hashlib.sha256(canonical_json_bytes(material, trailing_lf=False)).hexdigest()
        if self.locator_sha256 != actual:
            raise ValueError("locator_sha256 does not match location")
        return self


class ClaimExtractionRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "claims"
    schema_literal: ClassVar[str] = "alphaquest.literature-claim-extraction-revision/v1"
    claim_id: Identifier
    work_id: Identifier
    work_revision_sha256: Sha256
    source_version_id: Identifier
    source_version_revision_sha256: Sha256
    capture_id: Identifier
    capture_revision_sha256: Sha256
    content_sha256: Sha256
    extracted_representation_sha256: Sha256
    location: ClaimLocationV1
    statement: NonBlank
    statement_kind: Literal["SOURCE_QUOTE", "FAITHFUL_PARAPHRASE"]
    source_epistemic_form: Literal[
        "ASSOCIATION_REPORTED",
        "CAUSALITY_ASSERTED_BY_SOURCE",
        "MECHANISM_PROPOSED_BY_SOURCE",
        "NULL_RESULT",
        "LIMITATION",
        "METHODOLOGY_FACT",
        "OTHER",
    ]
    reliability: Literal["ACTIVE", "CORRECTED", "WITHDRAWN_INVALID", "SOURCE_RETRACTED"]
    correction_reason: str | None = None
    conflict_refs: list[RecordReferenceV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_claim(self) -> "ClaimExtractionRevisionV1":
        if self.record_id != f"{self.claim_id}.r{self.revision:06d}":
            raise ValueError("claim record_id does not match claim identity/revision")
        if self.reliability != "ACTIVE" and not self.correction_reason:
            raise ValueError("non-active claim requires correction_reason")
        return self


class FactualDescriptorV1(StrictModel):
    descriptor: Identifier
    value: NonBlank | None = None
    verification: Literal["VERIFIED", "UNVERIFIED", "UNKNOWN", "NOT_STATED", "NOT_APPLICABLE"]
    basis_claims: list[RecordReferenceV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_descriptor(self) -> "FactualDescriptorV1":
        if self.verification == "VERIFIED" and (self.value is None or not self.basis_claims):
            raise ValueError("verified descriptor requires a value and claim provenance")
        if self.verification in {"UNKNOWN", "NOT_STATED", "NOT_APPLICABLE"} and self.value is not None:
            raise ValueError("unknown/not-stated/not-applicable descriptor cannot invent a value")
        return self


class EvidenceRelationRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "evidence-relations"
    schema_literal: ClassVar[str] = "alphaquest.literature-evidence-relation-revision/v1"
    evidence_relation_id: Identifier
    relationship: Literal[
        "REPLICATES", "FAILS_TO_REPLICATE", "CONTRADICTS", "EXTENDS", "REGIME_QUALIFIES", "ALTERNATIVE_EXPLANATION"
    ]
    claim_refs: Annotated[list[RecordReferenceV1], Field(min_length=2)]
    relationship_basis: Literal["SOURCE_STATED", "ALPHAQUEST_EXPLICIT_INFERENCE"]
    rationale: NonBlank
    status: Literal["ACTIVE", "RETRACTED", "SUPERSEDED"]
    superseded_by_relation_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_evidence_relation(self) -> "EvidenceRelationRevisionV1":
        if self.record_id != f"{self.evidence_relation_id}.r{self.revision:06d}":
            raise ValueError("evidence relation record_id mismatch")
        if len({(item.record_id, item.record_sha256) for item in self.claim_refs}) != len(self.claim_refs):
            raise ValueError("evidence relation claim refs must be distinct")
        if (self.status == "SUPERSEDED") != (self.superseded_by_relation_id is not None):
            raise ValueError("SUPERSEDED evidence relation requires replacement")
        if self.revision == 1 and self.status != "ACTIVE":
            raise ValueError("first evidence-relation revision must be ACTIVE")
        return self


class LaneCompletionV1(StrictModel):
    lane: SearchLane
    execution_status: Literal["TERMINAL", "NONTERMINAL"]
    obligation_status: Literal["SATISFIED", "UNSATISFIED_PROVIDER_FAILURE", "UNSATISFIED_RESOURCE_OR_SAFETY_LIMIT"]
    search_run_refs: list[RecordReferenceV1]
    gap_reason: str | None = None

    @model_validator(mode="after")
    def validate_completion(self) -> "LaneCompletionV1":
        if self.obligation_status != "SATISFIED" and not self.gap_reason:
            raise ValueError("unsatisfied lane requires gap_reason")
        return self


class DossierClaimRefV1(StrictModel):
    claim_id: Identifier
    claim_revision_sha256: Sha256
    p2_role: Literal["MOTIVATING", "SUPPORTING", "CONTRADICTING"]


class MaterialStatementV1(StrictModel):
    statement_id: Identifier
    text: NonBlank
    basis: Literal["CLAIM_LINKED", "ALPHAQUEST_EXPLICIT_INFERENCE"]
    claim_refs: Annotated[list[RecordReferenceV1], Field(min_length=1)]
    inference_rationale: str | None = None

    @model_validator(mode="after")
    def validate_statement(self) -> "MaterialStatementV1":
        inferred = self.basis == "ALPHAQUEST_EXPLICIT_INFERENCE"
        if inferred != (self.inference_rationale is not None):
            raise ValueError("only explicit inference statements require inference_rationale")
        return self


class TaxonomyDimensionMappingV1(StrictModel):
    dimension: Identifier
    taxonomy_codes: Annotated[list[NonBlank], Field(min_length=1)]
    mapping_basis: Literal["SOURCE_STATED", "ALPHAQUEST_EXPLICIT_INFERENCE"]
    basis_claims: Annotated[list[RecordReferenceV1], Field(min_length=1)]
    rationale: NonBlank


class TaxonomyProposalV1(StrictModel):
    classification_status: Literal["CLASSIFIED", "NEEDS_CLASSIFICATION"]
    taxonomy_ref: TaxonomyRefV1
    economic_concepts: EconomicConceptsV1 | None = None
    unclassified_reason: Literal[
        "AMBIGUOUS_CAUSAL_MECHANISM",
        "CONFLICTING_OBSERVATIONS",
        "INSUFFICIENT_SOURCE_CONTEXT",
        "MIXED_ECONOMIC_PHENOMENA",
        "NOVEL_CONCEPT_NOT_IN_TAXONOMY",
    ] | None = None
    dimension_mappings: list[TaxonomyDimensionMappingV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "TaxonomyProposalV1":
        if self.classification_status == "CLASSIFIED":
            if self.economic_concepts is None or self.unclassified_reason is not None:
                raise ValueError("CLASSIFIED proposal requires concepts and no unclassified reason")
        elif self.economic_concepts is not None or self.unclassified_reason is None:
            raise ValueError("NEEDS_CLASSIFICATION requires reason and no concepts")
        return self


class EdgeDossierRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "dossiers"
    schema_literal: ClassVar[str] = "alphaquest.literature-edge-dossier-revision/v1"
    dossier_id: Identifier
    protocol_revision_sha256: Sha256
    execution_lineage_id: Identifier
    search_completion_status: Literal["COMPLETE_WITHIN_DECLARED_BOUNDS", "TERMINATED_WITH_DECLARED_GAPS"]
    lane_completions: Annotated[list[LaneCompletionV1], Field(min_length=7, max_length=7)]
    claim_refs: Annotated[list[DossierClaimRefV1], Field(min_length=1)]
    evidence_relation_refs: list[RecordReferenceV1] = Field(default_factory=list)
    quality_descriptors: list[FactualDescriptorV1] = Field(default_factory=list)
    material_statements: Annotated[list[MaterialStatementV1], Field(min_length=1)]
    taxonomy_proposal: TaxonomyProposalV1
    p2_entry_id: Identifier | None = None
    prior_emission_receipt_sha256: Sha256 | None = None
    scientific_validation_status: Literal["NOT_PERFORMED_IN_P3"] = "NOT_PERFORMED_IN_P3"
    hypothesis_status: Literal["NOT_CREATED_IN_P3"] = "NOT_CREATED_IN_P3"
    causal_admission_status: Literal["NOT_ASSESSED_IN_P3"] = "NOT_ASSESSED_IN_P3"
    change_reason: NonBlank

    @model_validator(mode="after")
    def validate_dossier(self) -> "EdgeDossierRevisionV1":
        if self.record_id != f"{self.dossier_id}.r{self.revision:06d}":
            raise ValueError("dossier record_id does not match identity/revision")
        if tuple(sorted(item.lane for item in self.lane_completions)) != tuple(sorted(REQUIRED_SEARCH_LANES)):
            raise ValueError("dossier requires exactly one completion for every lane")
        claim_identities = [(item.claim_id, item.claim_revision_sha256) for item in self.claim_refs]
        if len(claim_identities) != len(set(claim_identities)):
            raise ValueError("dossier claim refs must be ordered and unique")
        relation_identities = [(item.record_id, item.record_sha256) for item in self.evidence_relation_refs]
        if len(relation_identities) != len(set(relation_identities)):
            raise ValueError("dossier evidence-relation refs must be ordered and unique")
        all_satisfied = all(item.obligation_status == "SATISFIED" for item in self.lane_completions)
        if (self.search_completion_status == "COMPLETE_WITHIN_DECLARED_BOUNDS") != all_satisfied:
            raise ValueError("complete search status requires all obligations satisfied")
        if (self.p2_entry_id is None) != (self.prior_emission_receipt_sha256 is None):
            raise ValueError("P2 entry and prior receipt bindings must appear together")
        return self


class DossierFreezeV1(CanonicalRecordV1):
    family: ClassVar[str] = "dossier-freezes"
    schema_literal: ClassVar[str] = "alphaquest.literature-dossier-freeze/v1"
    freeze_id: Identifier
    dossier_id: Identifier
    dossier_revision_sha256: Sha256
    protocol_revision_sha256: Sha256
    execution_lineage_id: Identifier
    lane_completions: Annotated[list[LaneCompletionV1], Field(min_length=7, max_length=7)]
    claim_refs: Annotated[list[DossierClaimRefV1], Field(min_length=1)]
    evidence_relation_refs: list[RecordReferenceV1]
    quality_descriptors: list[FactualDescriptorV1]
    material_statements: Annotated[list[MaterialStatementV1], Field(min_length=1)]
    search_completion_status: Literal["COMPLETE_WITHIN_DECLARED_BOUNDS", "TERMINATED_WITH_DECLARED_GAPS"]
    unsatisfied_lanes: list[SearchLane]
    taxonomy_proposal: TaxonomyProposalV1
    p2_entry_id: Identifier | None = None
    prior_emission_receipt_sha256: Sha256 | None = None
    scientific_validation_status: Literal["NOT_PERFORMED_IN_P3"] = "NOT_PERFORMED_IN_P3"
    hypothesis_status: Literal["NOT_CREATED_IN_P3"] = "NOT_CREATED_IN_P3"
    causal_admission_status: Literal["NOT_ASSESSED_IN_P3"] = "NOT_ASSESSED_IN_P3"

    @model_validator(mode="after")
    def validate_freeze(self) -> "DossierFreezeV1":
        if self.record_id != self.freeze_id:
            raise ValueError("freeze record_id must equal freeze_id")
        if self.search_completion_status == "COMPLETE_WITHIN_DECLARED_BOUNDS" and self.unsatisfied_lanes:
            raise ValueError("complete freeze cannot report unsatisfied lanes")
        claim_identities = [(item.claim_id, item.claim_revision_sha256) for item in self.claim_refs]
        if len(claim_identities) != len(set(claim_identities)):
            raise ValueError("freeze claim refs must be ordered and unique")
        return self


class CodexTaskAttemptRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "codex-attempts"
    schema_literal: ClassVar[str] = "alphaquest.literature-codex-task-attempt-revision/v1"
    attempt_id: Identifier
    task_type: Literal[
        "LITERATURE_PROTOCOL_PROPOSER",
        "LITERATURE_SEARCH_OPERATOR",
        "ADAPTIVE_QUERY_PROPOSER",
        "CLAIM_EXTRACTOR",
        "METHODOLOGY_DESCRIPTOR",
        "DOSSIER_SYNTHESIZER",
        "DUPLICATE_EXPLAINER",
    ]
    status: Literal["STARTED", "SUCCEEDED", "FAILED", "REJECTED_PROCESSING_PERMISSION", "INVALID_OUTPUT", "ABANDONED_AFTER_CRASH"]
    model: str | None = None
    settings_sha256: Sha256
    prompt_sha256: Sha256
    input_manifest_sha256: Sha256
    workspace_manifest_sha256: Sha256 | None = None
    output_sha256: Sha256 | None = None
    referenced_records: list[RecordReferenceV1]
    isolation_backend: NonBlank
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> "CodexTaskAttemptRevisionV1":
        if self.record_id != f"{self.attempt_id}.r{self.revision:06d}":
            raise ValueError("attempt record_id mismatch")
        if self.status != "SUCCEEDED" and self.status != "STARTED" and not self.failure_reason:
            raise ValueError("failed/rejected attempt requires failure_reason")
        return self


class EvidenceTimeBindingV1(StrictModel):
    evidence_time: datetime
    basis: Literal["VERIFIED_PUBLIC_AVAILABILITY", "CAPTURE_FALLBACK_COARSE_OR_UNCERTAIN"]

    @field_validator("evidence_time")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence_time must be timezone-aware")
        return value


class P2EvidenceReservationV1(StrictModel):
    canonical_source_version_id: Identifier
    relationship_state_sha256: Sha256
    p2_source_id: Identifier
    source_kind: Literal["PAPER", "DATASET", "EXCHANGE_RESEARCH", "PRACTITIONER_RESEARCH", "MARKET_EVENT", "OTHER"]
    canonical_locator: NonBlank
    capture_id: Identifier
    terminal_capture_revision_sha256: Sha256
    content_sha256: Sha256
    extracted_representation_sha256: Sha256
    evidence_time: EvidenceTimeBindingV1
    reservation_operation_id: Identifier


class P2ObservationPlanV1(StrictModel):
    claim_id: Identifier
    claim_revision_sha256: Sha256
    observation_id: Identifier
    prior_observation_revision_sha256: Sha256 | None = None
    role: Literal["MOTIVATING", "SUPPORTING", "CONTRADICTING"]
    withdrawn_from_current_support: bool = False
    payload_sha256: Sha256
    payload: "P2ObservationPayloadV1"


class P2EvidenceReferencePlanV1(StrictModel):
    source_id: Identifier
    source_kind: Literal["PAPER", "DATASET", "EXCHANGE_RESEARCH", "PRACTITIONER_RESEARCH", "MARKET_EVENT", "OTHER"]
    locator: NonBlank
    claim_locator: NonBlank
    evidence_time: datetime
    integrity: Literal["HASH_BOUND"]
    content_sha256: Sha256

    @field_validator("evidence_time")
    @classmethod
    def validate_evidence_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planned P2 evidence_time must be timezone-aware")
        return value


class P2ObservationPayloadV1(StrictModel):
    observation_id: Identifier
    statement: NonBlank
    statement_kind: Literal["SOURCE_QUOTE", "FAITHFUL_PARAPHRASE"]
    evidence_refs: Annotated[list[P2EvidenceReferencePlanV1], Field(min_length=1)]
    known_conflicts: list[NonBlank] = Field(default_factory=list)


class P2ObservationRolePlanV1(StrictModel):
    observation_id: Identifier
    role: Literal["MOTIVATING", "SUPPORTING", "CONTRADICTING"]
    frozen_revision_sha256: Sha256 | None = None


class P2EntryPlanV1(StrictModel):
    classification_status: Literal["CLASSIFIED", "NEEDS_CLASSIFICATION"]
    taxonomy_ref: TaxonomyRefV1
    governance_scope: Literal["PRE_HYPOTHESIS_BACKLOG_ONLY"]
    p1_evidence_eligibility: Literal["NOT_CURRENT_P1_EVIDENCE"]
    economic_concepts: EconomicConceptsV1 | None
    unclassified_reason: Literal[
        "AMBIGUOUS_CAUSAL_MECHANISM",
        "CONFLICTING_OBSERVATIONS",
        "INSUFFICIENT_SOURCE_CONTEXT",
        "MIXED_ECONOMIC_PHENOMENA",
        "NOVEL_CONCEPT_NOT_IN_TAXONOMY",
    ] | None
    observation_roles: Annotated[list[P2ObservationRolePlanV1], Field(min_length=1)]


class P2DependencyImpactV1(StrictModel):
    affected_observation_id: Identifier
    affected_observation_revision_sha256: Sha256
    dependent_entry_id: Identifier
    dependent_entry_revision_sha256: Sha256
    dependent_entry_state: Literal[
        "UNREVIEWED", "REVIEWED_CONTINUE", "REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"
    ]
    relevant_link_chain_sha256: Sha256
    impact_status: Literal["PLANNED_MUTABLE_REVISION", "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"]
    inability_reason: str | None = None
    prior_staled_decision_sha256: Sha256 | None = None
    entry_plan: P2EntryPlanV1 | None = None

    @model_validator(mode="after")
    def validate_dependency_impact(self) -> "P2DependencyImpactV1":
        mutable = self.impact_status == "PLANNED_MUTABLE_REVISION"
        if mutable != (self.entry_plan is not None):
            raise ValueError("mutable dependency impact requires exactly one deterministic entry plan")
        if mutable == (self.inability_reason is not None):
            raise ValueError("only unresolved dependency impacts require an inability reason")
        return self


class P2RecordBindingV1(StrictModel):
    record_id: RecordIdentifier
    record_sha256: Sha256


class DuplicateCandidateBindingV1(StrictModel):
    candidate_id: NonBlank
    candidate_record_sha256: Sha256
    candidate_decision_sha256: Sha256 | None = None
    candidate_link_chain_sha256: Sha256


class DuplicateSnapshotBindingV1(StrictModel):
    entry_id: Identifier
    entry_revision_sha256: Sha256
    before_append_sequence: Annotated[int, Field(ge=1)]
    entry_link_chain_sha256: Sha256
    historical_source_commit: str | None = None
    historical_universe_sha256: Sha256
    snapshot_sha256: Sha256
    candidate_bindings: list[DuplicateCandidateBindingV1]


class P2EmissionOperationRevisionV1(RevisionRecordV1):
    family: ClassVar[str] = "p2-emissions"
    schema_literal: ClassVar[str] = "alphaquest.literature-p2-emission-operation-revision/v1"
    operation_id: Identifier
    freeze_id: Identifier
    freeze_record_sha256: Sha256
    target_entry_id: Identifier | None = None
    target_entry_revision_sha256: Sha256 | None = None
    target_entry_state: Literal["UNREVIEWED", "REVIEWED_CONTINUE", "REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"] | None = None
    target_entry_link_chain_sha256: Sha256 | None = None
    p2_snapshot_before_append_sequence: Annotated[int, Field(ge=1)]
    emission_action: Literal["CREATE_NEW_ENTRY", "REVISE_SAME_ENTRY", "BLOCKED"]
    state: Literal[
        "PREPARED", "OBSERVATIONS_WRITTEN", "ENTRY_WRITTEN", "SNAPSHOT_BOUND", "COMPLETED", "BLOCKED", "CONFLICT"
    ]
    reservations: Annotated[list[P2EvidenceReservationV1], Field(min_length=1)]
    observation_plans: Annotated[list[P2ObservationPlanV1], Field(min_length=1)]
    entry_plan: P2EntryPlanV1
    dependency_impacts: list[P2DependencyImpactV1] = Field(default_factory=list)
    search_completion_status: Literal["COMPLETE_WITHIN_DECLARED_BOUNDS", "TERMINATED_WITH_DECLARED_GAPS"]
    unsatisfied_lanes: list[SearchLane]
    observation_bindings: list[P2RecordBindingV1] = Field(default_factory=list)
    entry_binding: P2RecordBindingV1 | None = None
    dependency_entry_bindings: list[P2RecordBindingV1] = Field(default_factory=list)
    duplicate_snapshot: DuplicateSnapshotBindingV1 | None = None
    prior_staled_decision_sha256: Sha256 | None = None
    receipt_record_sha256: Sha256 | None = None
    blocked_reason: str | None = None
    conflict_reason: str | None = None
    operational_status: Literal["CLEAN", "NEEDS_MANUAL_REVIEW"] = "CLEAN"

    @model_validator(mode="after")
    def validate_operation(self) -> "P2EmissionOperationRevisionV1":
        if self.record_id != f"{self.operation_id}.r{self.revision:06d}":
            raise ValueError("emission operation record_id mismatch")
        if (self.target_entry_id is None) != (self.target_entry_revision_sha256 is None):
            raise ValueError("target entry identity and exact revision must appear together")
        target_fields = (
            self.target_entry_id,
            self.target_entry_revision_sha256,
            self.target_entry_state,
            self.target_entry_link_chain_sha256,
        )
        if any(item is None for item in target_fields) and any(item is not None for item in target_fields):
            raise ValueError("target entry identity, revision, state, and link chain must appear together")
        unresolved = any(
            item.impact_status == "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"
            for item in self.dependency_impacts
        )
        if (self.operational_status == "NEEDS_MANUAL_REVIEW") != unresolved:
            raise ValueError("operational status must expose unresolved invalid-evidence dependencies")
        if self.state == "BLOCKED" and not self.blocked_reason:
            raise ValueError("blocked operation requires reason")
        if (self.state == "BLOCKED") != (self.emission_action == "BLOCKED"):
            raise ValueError("BLOCKED state and emission action must agree")
        if self.state == "CONFLICT" and not self.conflict_reason:
            raise ValueError("conflicted operation requires reason")
        if self.state == "COMPLETED" and self.receipt_record_sha256 is None:
            raise ValueError("completed operation requires receipt binding")
        return self


class P2EmissionReceiptV1(CanonicalRecordV1):
    family: ClassVar[str] = "p2-emission-receipts"
    schema_literal: ClassVar[str] = "alphaquest.literature-p2-emission-receipt/v1"
    receipt_id: Identifier
    operation_id: Identifier
    operation_revision_sha256: Sha256
    freeze_id: Identifier
    freeze_record_sha256: Sha256
    reservations: Annotated[list[P2EvidenceReservationV1], Field(min_length=1)]
    observation_bindings: Annotated[list[P2RecordBindingV1], Field(min_length=1)]
    entry_binding: P2RecordBindingV1
    duplicate_snapshot: DuplicateSnapshotBindingV1
    dependency_impacts: list[P2DependencyImpactV1] = Field(default_factory=list)
    dependency_entry_bindings: list[P2RecordBindingV1] = Field(default_factory=list)
    prior_staled_decision_sha256: Sha256 | None = None
    search_completion_status: Literal["COMPLETE_WITHIN_DECLARED_BOUNDS", "TERMINATED_WITH_DECLARED_GAPS"]
    unsatisfied_lanes: list[SearchLane]
    operational_status: Literal["CLEAN", "NEEDS_MANUAL_REVIEW"] = "CLEAN"

    @model_validator(mode="after")
    def validate_receipt(self) -> "P2EmissionReceiptV1":
        if self.record_id != self.receipt_id:
            raise ValueError("receipt record_id must equal receipt_id")
        return self


CANONICAL_RECORD_TYPES: tuple[type[CanonicalRecordV1], ...] = (
    ResearchProtocolRevisionV1,
    SearchRunRevisionV1,
    SourceIdentityRevisionV1,
    SourceVersionIdentityRevisionV1,
    SourceRelationshipRevisionV1,
    SourceCaptureRevisionV1,
    ClaimExtractionRevisionV1,
    EvidenceRelationRevisionV1,
    EdgeDossierRevisionV1,
    DossierFreezeV1,
    CodexTaskAttemptRevisionV1,
    P2EmissionOperationRevisionV1,
    P2EmissionReceiptV1,
)
SCHEMA_TYPES = {item.schema_literal: item for item in CANONICAL_RECORD_TYPES}
FAMILY_TYPES = {item.family: item for item in CANONICAL_RECORD_TYPES}


def methodology_sha256(payload: dict[str, Any]) -> str:
    fields = {
        key: payload[key]
        for key in (
            "execution_lineage_id",
            "lineage_kind",
            "parent_execution_lineage_id",
            "observed_result_set_sha256",
            "research_question",
            "market_scope",
            "inclusion_rules",
            "exclusion_rules",
            "lanes",
        )
    }
    return hashlib.sha256(canonical_json_bytes(fields, trailing_lf=False)).hexdigest()


def intent_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload, trailing_lf=False)).hexdigest()


def generated_identifier(prefix: str, material: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", prefix):
        raise ValueError("invalid identifier prefix")
    return f"{prefix}.{hashlib.sha256(material.encode('utf-8')).hexdigest()[:32]}"


class CanonicalFamily(str, Enum):
    PROTOCOL = "protocols"
    SEARCH = "searches"
    WORK = "source-works"
    VERSION = "source-versions"
    SOURCE_RELATIONSHIP = "source-relationships"
    CAPTURE = "captures"
    CLAIM = "claims"
    EVIDENCE_RELATION = "evidence-relations"
    DOSSIER = "dossiers"
    FREEZE = "dossier-freezes"
    CODEX_ATTEMPT = "codex-attempts"
    P2_EMISSION = "p2-emissions"
    P2_RECEIPT = "p2-emission-receipts"


__all__ = [
    "CANONICAL_RECORD_TYPES",
    "FAMILY_TYPES",
    "SCHEMA_TYPES",
    "ActorProvenanceV1",
    "CanonicalFamily",
    "CanonicalRecordV1",
    "ClaimExtractionRevisionV1",
    "DossierFreezeV1",
    "DuplicateSnapshotBindingV1",
    "EdgeDossierRevisionV1",
    "EvidenceRelationRevisionV1",
    "EvidenceTimeBindingV1",
    "LiteratureAuthorityError",
    "LiteratureConflictError",
    "LiteratureError",
    "LiteratureIntegrityError",
    "P2EmissionOperationRevisionV1",
    "P2EmissionReceiptV1",
    "P2EvidenceReservationV1",
    "P2ObservationPlanV1",
    "P2RecordBindingV1",
    "ResearchProtocolRevisionV1",
    "SearchRunRevisionV1",
    "SourceCaptureRevisionV1",
    "SourceIdentityRevisionV1",
    "SourceRelationshipRevisionV1",
    "SourceVersionIdentityRevisionV1",
    "canonical_json_bytes",
    "generated_identifier",
    "intent_sha256",
    "methodology_sha256",
    "record_sha256",
]
