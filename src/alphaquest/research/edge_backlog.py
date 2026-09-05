"""Canonical pre-hypothesis Edge Backlog records and append-only storage.

The backlog is a discovery control surface.  It does not admit hypotheses,
create edge families or campaigns, or carry scientific verdicts.  Canonical
JSON files are authoritative; every index or presentation built from them is
derived.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading
from typing import Annotated, Any, Iterator, Literal, Mapping, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from alphaquest.research import duplicate_matching as duplicate_core
from alphaquest.research.edge_backlog_taxonomy import (
    ClassificationStatus,
    DIMENSION_FIELDS,
    EconomicConceptsV1,
    EconomicEdgeTaxonomyV1,
    FINGERPRINT_SCHEMA,
    TaxonomyRefV1,
    UnclassifiedReason,
    bundled_taxonomy_root,
    derived_display_label,
    fingerprint_sha256 as economic_fingerprint_sha256,
    load_taxonomy_catalog,
    matcher_dimensions,
    resolve_taxonomy,
    taxonomy_ref as build_taxonomy_ref,
    validate_concepts,
)
from alphaquest.research.storage import StorageLayout, display_path, load_storage_layout


OBSERVATION_SCHEMA = "alphaquest.edge-backlog-observation-revision/v1"
ENTRY_SCHEMA = "alphaquest.edge-backlog-entry-revision/v1"
DECISION_SCHEMA = "alphaquest.edge-backlog-decision/v1"
LINK_SCHEMA = "alphaquest.edge-backlog-link/v1"
DUPLICATE_SNAPSHOT_SCHEMA = "alphaquest.edge-backlog-duplicate-snapshot/v1"
HISTORY_INDEX_SCHEMA = "alphaquest.edge-backlog-history-index-record/v1"

IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,127}$"
SHA256_PATTERN = r"^[a-f0-9]{64}$"
Identifier = Annotated[str, Field(pattern=IDENTIFIER_PATTERN)]
RecordIdentifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,255}$")]
Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]
GitObjectId = Annotated[str, Field(pattern=r"^[a-f0-9]{40}(?:[a-f0-9]{24})?$")]
NonBlank = Annotated[str, Field(min_length=1)]

ActorClass = Literal[
    "CODEX",
    "HUMAN_OWNER_RESEARCHER",
    "ALPHAQUEST_DETERMINISTIC_ENGINE",
    "EXTERNAL_SYSTEM",
]
IntegrityLevel = Literal["HASH_BOUND", "LOCATOR_ONLY"]
StatementKind = Literal["SOURCE_QUOTE", "FAITHFUL_PARAPHRASE", "RESEARCHER_SUMMARY"]
ObservationRole = Literal["MOTIVATING", "SUPPORTING", "CONTRADICTING"]
Disposition = Literal["REVIEWED_CONTINUE", "REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"]
DuplicateResolution = Literal["SAME_EDGE", "RELATED_EDGE_FAMILY", "DISTINCT_EDGE", "UNRESOLVED"]
ReasonCode = Literal[
    "AMBIGUOUS_DUPLICATE",
    "CAUSAL_WEAKNESS",
    "DATA_UNAVAILABLE",
    "DUPLICATE_EDGE",
    "INSUFFICIENT_EVIDENCE",
    "NEW_INFORMATION",
    "OWNER_PRIORITY",
    "PRIOR_FAILURE",
    "SCOPE_MISMATCH",
    "SOURCE_QUALITY",
    "TEMPORARY_BLOCKER",
    "OTHER",
]
LinkRelationship = Literal[
    "HYPOTHESIS_PROPOSAL",
    "ADMITTED_HYPOTHESIS",
    "EDGE_FAMILY",
    "CAMPAIGN",
    "REVISIT_OF",
]
TargetKind = Literal["HYPOTHESIS", "EDGE_FAMILY", "CAMPAIGN", "EDGE_BACKLOG_ENTRY"]

_TERMINAL_DISPOSITIONS = frozenset({"REJECTED", "DUPLICATE"})
_IDENTITY_FIELDS = DIMENSION_FIELDS
_LINK_TARGETS: dict[str, str] = {
    "HYPOTHESIS_PROPOSAL": "HYPOTHESIS",
    "ADMITTED_HYPOTHESIS": "HYPOTHESIS",
    "EDGE_FAMILY": "EDGE_FAMILY",
    "CAMPAIGN": "CAMPAIGN",
    "REVISIT_OF": "EDGE_BACKLOG_ENTRY",
}
_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
_EMPTY_RECORD_CHAIN_SHA256 = hashlib.sha256(b"[]").hexdigest()
_EMPTY_HISTORICAL_UNIVERSE_SHA256 = hashlib.sha256(b"[]").hexdigest()


class EdgeBacklogError(RuntimeError):
    """Base class for Edge Backlog failures."""


class EdgeBacklogConflictError(EdgeBacklogError):
    """Raised when an append would overwrite or branch canonical history."""


class EdgeBacklogIntegrityError(EdgeBacklogError):
    """Raised when persisted canonical records fail validation."""


class EdgeBacklogAuthorityError(EdgeBacklogError):
    """Raised when an operation attempts to exercise reserved authority."""


class StrictBacklogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, populate_by_name=True)


class ActorProvenanceV1(StrictBacklogModel):
    actor_class: ActorClass
    actor_id: NonBlank
    task_id: NonBlank | None = None

    @field_validator("actor_id", "task_id")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class EvidenceReferenceV1(StrictBacklogModel):
    source_id: Identifier
    source_kind: Literal[
        "PAPER",
        "DATASET",
        "EXCHANGE_RESEARCH",
        "PRACTITIONER_RESEARCH",
        "MARKET_EVENT",
        "OTHER",
    ]
    locator: NonBlank
    claim_locator: NonBlank
    evidence_time: datetime
    integrity: IntegrityLevel
    content_sha256: Sha256 | None = None

    @field_validator("locator", "claim_locator")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _strip(value)

    @field_validator("evidence_time", mode="before")
    @classmethod
    def require_aware_time(cls, value: datetime | str) -> datetime:
        return _aware(_parse_datetime(value))

    @model_validator(mode="after")
    def validate_integrity(self) -> "EvidenceReferenceV1":
        if self.integrity == "HASH_BOUND" and self.content_sha256 is None:
            raise ValueError("HASH_BOUND evidence requires content_sha256")
        if self.integrity == "LOCATOR_ONLY" and self.content_sha256 is not None:
            raise ValueError("LOCATOR_ONLY evidence must not claim content_sha256")
        return self


class ObservationReferenceV1(StrictBacklogModel):
    observation_id: Identifier
    observation_revision_sha256: Sha256
    role: ObservationRole


class HashedRecord(StrictBacklogModel):
    record_id: RecordIdentifier
    append_sequence: Annotated[int, Field(ge=1)]
    recorded_at: datetime
    actor: ActorProvenanceV1
    record_sha256: Sha256

    @field_validator("recorded_at", mode="before")
    @classmethod
    def require_aware_recorded_at(cls, value: datetime | str) -> datetime:
        return _aware(_parse_datetime(value))

    @model_validator(mode="after")
    def validate_record_hash(self, info: ValidationInfo) -> "HashedRecord":
        if info.context and info.context.get("skip_record_hash"):
            return self
        actual = record_sha256(self)
        if self.record_sha256 != actual:
            raise ValueError("record_sha256 does not match canonical record content")
        return self


class ObservationRevisionV1(HashedRecord):
    schema_name: Literal[OBSERVATION_SCHEMA] = Field(
        default=OBSERVATION_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    observation_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    previous_revision_sha256: Sha256 | None = None
    statement: NonBlank
    statement_kind: StatementKind
    evidence_refs: Annotated[list[EvidenceReferenceV1], Field(min_length=1)]
    known_conflicts: list[NonBlank] = Field(default_factory=list)

    @field_validator("statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        return _strip(value)

    @field_validator("known_conflicts")
    @classmethod
    def normalize_conflicts(cls, values: list[str]) -> list[str]:
        return _unique_text(values, "known_conflicts")

    @model_validator(mode="after")
    def validate_revision_identity(self) -> "ObservationRevisionV1":
        _validate_revision(self.record_id, self.observation_id, self.revision, self.previous_revision_sha256)
        identities = [(item.source_id, item.claim_locator) for item in self.evidence_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("evidence_refs must not repeat a source_id/claim_locator pair")
        return self


class EdgeBacklogEntryRevisionV1(HashedRecord):
    schema_name: Literal[ENTRY_SCHEMA] = Field(
        default=ENTRY_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    entry_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    previous_revision_sha256: Sha256 | None = None
    classification_status: ClassificationStatus
    taxonomy_ref: TaxonomyRefV1
    governance_scope: Literal["PRE_HYPOTHESIS_BACKLOG_ONLY"]
    p1_evidence_eligibility: Literal["NOT_CURRENT_P1_EVIDENCE"]
    economic_concepts: EconomicConceptsV1 | None
    unclassified_reason: UnclassifiedReason | None
    observation_refs: Annotated[list[ObservationReferenceV1], Field(min_length=1)]
    fingerprint_schema: Literal[FINGERPRINT_SCHEMA] | None
    fingerprint_sha256: Sha256 | None

    @model_validator(mode="after")
    def validate_entry_identity(self, info: ValidationInfo) -> "EdgeBacklogEntryRevisionV1":
        _validate_revision(self.record_id, self.entry_id, self.revision, self.previous_revision_sha256)
        refs = [(item.observation_id, item.observation_revision_sha256, item.role) for item in self.observation_refs]
        if len(refs) != len(set(refs)):
            raise ValueError("observation_refs must be distinct")
        if self.classification_status == "CLASSIFIED":
            if self.economic_concepts is None or self.unclassified_reason is not None:
                raise ValueError("CLASSIFIED entries require complete concepts and no unclassified reason")
            if self.fingerprint_schema != FINGERPRINT_SCHEMA or self.fingerprint_sha256 is None:
                raise ValueError("CLASSIFIED entries require the final v1 economic fingerprint")
        else:
            if self.economic_concepts is not None:
                raise ValueError("NEEDS_CLASSIFICATION entries cannot carry economic concepts")
            if self.unclassified_reason is None:
                raise ValueError("NEEDS_CLASSIFICATION entries require an explicit reason")
            if self.fingerprint_schema is not None or self.fingerprint_sha256 is not None:
                raise ValueError("NEEDS_CLASSIFICATION entries cannot carry an economic fingerprint")
        skip_fingerprint = bool(info.context and info.context.get("skip_fingerprint"))
        if (
            not skip_fingerprint
            and self.classification_status == "CLASSIFIED"
            and self.fingerprint_sha256 != backlog_fingerprint(self)
        ):
            raise ValueError("fingerprint_sha256 does not match normalized economic identity")
        return self


class HistoricalEdgeIndexRecordV1(StrictBacklogModel):
    """One strict provenance-preserving projection from a historical source."""

    schema_name: Literal[HISTORY_INDEX_SCHEMA] = Field(
        default=HISTORY_INDEX_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    record_id: str = Field(pattern=r"^history\.[a-f0-9]{24}$")
    source_kind: Literal[
        "CAMPAIGN_DEFINITION",
        "RESEARCH_LEDGER_ROW",
        "EXPERIMENT_REGISTRY_EVENT",
        "RESEARCH_RESET_MANIFEST",
    ]
    source_path: str = Field(min_length=1)
    source_sha256: Sha256
    source_row_number: int | None = Field(default=None, ge=1)
    source_generation: Literal["CURRENT", "CONFIGURED_ARCHIVE", "CLEAN_SLATE_ARCHIVE"]
    archive_generation: str = Field(min_length=1)
    p1_evidence_eligibility: Literal["NOT_CURRENT_P1_EVIDENCE"]
    derived_index_use: Literal["DUPLICATE_RECALL_ONLY"]
    campaign_id: str | None = None
    variant_id: str | None = None
    attempt_id: str | None = None
    instrument: str | None = None
    timeframe: str | None = None
    raw_title: str | None = None
    raw_edge: str | None = None
    raw_hypothesis: str | None = None
    raw_edge_family: str | None = None
    raw_counterparty_transfer_rationale: str | None = None
    raw_information_availability: str | None = None
    raw_expected_effect: str | None = None
    raw_config_path: str | None = None
    raw_report_path: str | None = None
    legacy_fingerprint: dict[str, Any] | str | None = None
    raw_outcome: str | None = None
    raw_scientific_verdict: str | None = None
    raw_disposition: str | None = None
    raw_failure_reason: str | None = None
    extraction_completeness: Literal["COMPLETE", "PARTIAL", "INSUFFICIENT"]
    semantic_resolution: Literal["NEEDS_MANUAL_REVIEW"]
    record_sha256: Sha256

    @field_validator("source_path", "archive_generation")
    @classmethod
    def validate_provenance_text(cls, value: str, info: ValidationInfo) -> str:
        normalized = _strip(value)
        if info.field_name == "source_path":
            path = Path(normalized)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("historical source_path must be a project-relative path")
        return normalized

    @model_validator(mode="after")
    def validate_identity_and_hash(self) -> "HistoricalEdgeIndexRecordV1":
        row_kinds = {"RESEARCH_LEDGER_ROW", "EXPERIMENT_REGISTRY_EVENT"}
        if (self.source_kind in row_kinds) != (self.source_row_number is not None):
            raise ValueError("historical source_row_number does not match source_kind")
        if self.source_generation == "CURRENT" and self.archive_generation != "CURRENT":
            raise ValueError("CURRENT historical rows require archive_generation CURRENT")
        if self.source_generation != "CURRENT" and self.archive_generation == "CURRENT":
            raise ValueError("archive historical rows require explicit archive provenance")
        if self.record_id != _historical_record_id(self):
            raise ValueError("historical record_id does not match source provenance")
        if self.record_sha256 != record_sha256(self.model_dump(mode="json", by_alias=True)):
            raise ValueError("historical index record_sha256 mismatch")
        return self


class DuplicateCandidateV1(StrictBacklogModel):
    candidate_id: NonBlank
    candidate_kind: Literal["CANONICAL_BACKLOG_ENTRY", "DERIVED_HISTORICAL_RECORD"]
    candidate_record_sha256: Sha256
    candidate_decision_sha256: Sha256 | None = None
    candidate_link_chain_sha256: Sha256
    title: NonBlank
    state: str | None = None
    exact_fingerprint: bool
    taxonomy_score: Annotated[float, Field(ge=0.0, le=1.0)]
    dimension_scores: dict[str, Annotated[float, Field(ge=0.0, le=1.0)]]
    matched_dimensions: list[str]
    lexical_similarity: Annotated[float, Field(ge=0.0, le=1.0)]
    source_overlap: list[str]
    shared_link_targets: list[str]
    lineage_related: bool
    match_band: Literal[
        "EXACT_FINGERPRINT",
        "HIGH_STRUCTURED_SIMILARITY",
        "POSSIBLE_RELATED_EDGE",
        "LEXICAL_REVIEW",
    ]
    source_path: NonBlank | None = None
    archive_generation: NonBlank | None = None
    source_generation: Literal["CURRENT", "CONFIGURED_ARCHIVE", "CLEAN_SLATE_ARCHIVE"] | None = None
    p1_evidence_eligibility: Literal["NOT_CURRENT_P1_EVIDENCE"] | None = None
    derived_index_use: Literal["DUPLICATE_RECALL_ONLY"] | None = None
    semantic_resolution: Literal["NEEDS_MANUAL_REVIEW"] | None = None
    historical_scientific_verdict: str | None = None
    historical_disposition: str | None = None
    historical_record: HistoricalEdgeIndexRecordV1 | None = None

    @model_validator(mode="after")
    def validate_candidate_kind(self) -> "DuplicateCandidateV1":
        historical_fields = (
            self.source_path,
            self.archive_generation,
            self.source_generation,
            self.p1_evidence_eligibility,
            self.derived_index_use,
            self.semantic_resolution,
        )
        if self.candidate_kind == "DERIVED_HISTORICAL_RECORD":
            if any(value is None for value in historical_fields):
                raise ValueError("historical duplicate candidates require complete derived-index provenance")
            if self.historical_record is None:
                raise ValueError("historical duplicate candidates require the complete historical record")
            if self.candidate_id != f"history:{self.candidate_record_sha256}":
                raise ValueError("historical candidate_id must bind the complete record_sha256")
            if self.candidate_record_sha256 != self.historical_record.record_sha256:
                raise ValueError("historical candidate hash must match the embedded historical record")
            if self.candidate_decision_sha256 is not None:
                raise ValueError("historical candidates cannot claim a canonical decision")
            if self.candidate_link_chain_sha256 != _EMPTY_RECORD_CHAIN_SHA256:
                raise ValueError("historical candidates cannot claim a canonical link chain")
            expected = _historical_candidate_projection(self.historical_record)
            actual = {
                "title": self.title,
                "state": self.state,
                "source_path": self.source_path,
                "archive_generation": self.archive_generation,
                "source_generation": self.source_generation,
                "p1_evidence_eligibility": self.p1_evidence_eligibility,
                "derived_index_use": self.derived_index_use,
                "semantic_resolution": self.semantic_resolution,
                "historical_scientific_verdict": self.historical_scientific_verdict,
                "historical_disposition": self.historical_disposition,
            }
            if actual != expected:
                raise ValueError("historical candidate projection does not match its embedded record")
        else:
            if not _IDENTIFIER.fullmatch(self.candidate_id):
                raise ValueError("canonical candidate_id must be a backlog identifier")
            optional_history = (
                *historical_fields,
                self.historical_scientific_verdict,
                self.historical_disposition,
                self.historical_record,
            )
            if any(value is not None for value in optional_history):
                raise ValueError("canonical backlog candidates cannot carry historical-index fields")
        return self


class EdgeBacklogDecisionV1(HashedRecord):
    schema_name: Literal[DECISION_SCHEMA] = Field(
        default=DECISION_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    decision_id: Identifier
    entry_id: Identifier
    entry_revision_sha256: Sha256
    entry_link_chain_sha256: Sha256
    sequence: Annotated[int, Field(ge=1)]
    previous_decision_sha256: Sha256 | None = None
    disposition: Disposition
    duplicate_resolution: DuplicateResolution | None = None
    candidate_snapshot: list[DuplicateCandidateV1] = Field(default_factory=list)
    candidate_snapshot_sha256: Sha256 | None = None
    historical_source_commit: GitObjectId | None = None
    historical_universe_sha256: Sha256 | None = None
    canonical_entry_id: Identifier | None = None
    related_edge_family_ids: list[Identifier] = Field(default_factory=list)
    reason_codes: Annotated[list[ReasonCode], Field(min_length=1)]
    rationale: NonBlank
    revisit_conditions: list[NonBlank] = Field(default_factory=list)

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str) -> str:
        return _strip(value)

    @field_validator("revisit_conditions")
    @classmethod
    def normalize_text_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return _unique_text(values, info.field_name)

    @field_validator("related_edge_family_ids", "reason_codes")
    @classmethod
    def unique_enums(cls, values: list[Any], info: ValidationInfo) -> list[Any]:
        if len(values) != len(set(values)):
            raise ValueError(f"{info.field_name} entries must be distinct")
        return values

    @model_validator(mode="after")
    def validate_decision(self) -> "EdgeBacklogDecisionV1":
        if self.record_id != self.decision_id:
            raise ValueError("record_id must equal decision_id")
        if self.actor.actor_class != "HUMAN_OWNER_RESEARCHER":
            raise ValueError("backlog decisions require HUMAN_OWNER_RESEARCHER authority")
        if (self.sequence == 1) != (self.previous_decision_sha256 is None):
            raise ValueError("decision sequence and previous_decision_sha256 are inconsistent")
        if self.disposition == "RESUMED":
            if any(
                (
                    self.duplicate_resolution is not None,
                    bool(self.candidate_snapshot),
                    self.candidate_snapshot_sha256 is not None,
                    self.historical_source_commit is not None,
                    self.historical_universe_sha256 is not None,
                    self.canonical_entry_id is not None,
                    bool(self.related_edge_family_ids),
                    bool(self.revisit_conditions),
                )
            ):
                raise ValueError("RESUMED records cannot carry duplicate or revisit fields")
            return self
        if (
            self.duplicate_resolution is None
            or self.candidate_snapshot_sha256 is None
            or self.historical_universe_sha256 is None
        ):
            raise ValueError("review decisions require duplicate resolution and candidate snapshot")
        if (
            self.historical_universe_sha256 == _EMPTY_HISTORICAL_UNIVERSE_SHA256
        ) != (self.historical_source_commit is None):
            raise ValueError("historical source commit must be present exactly when the historical universe is nonempty")
        candidate_core = {
            "schema": DUPLICATE_SNAPSHOT_SCHEMA,
            "entry_id": self.entry_id,
            "entry_revision_sha256": self.entry_revision_sha256,
            "entry_link_chain_sha256": self.entry_link_chain_sha256,
            "historical_source_commit": self.historical_source_commit,
            "historical_universe_sha256": self.historical_universe_sha256,
            "candidates": [item.model_dump(mode="json", by_alias=True) for item in self.candidate_snapshot],
        }
        actual_snapshot_sha256 = hashlib.sha256(canonical_json_bytes(candidate_core)).hexdigest()
        if self.candidate_snapshot_sha256 != actual_snapshot_sha256:
            raise ValueError("candidate_snapshot_sha256 does not match candidate_snapshot")
        candidate_ids = [item.candidate_id for item in self.candidate_snapshot]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_snapshot contains duplicate candidate IDs")
        if self.disposition == "DUPLICATE":
            if self.duplicate_resolution != "SAME_EDGE" or self.canonical_entry_id is None:
                raise ValueError("DUPLICATE requires SAME_EDGE and canonical_entry_id")
            if self.canonical_entry_id == self.entry_id:
                raise ValueError("a duplicate cannot point to itself")
            if self.canonical_entry_id not in candidate_ids:
                raise ValueError("canonical_entry_id must be in the reviewed candidate snapshot")
            selected = next(item for item in self.candidate_snapshot if item.candidate_id == self.canonical_entry_id)
            if selected.candidate_kind != "CANONICAL_BACKLOG_ENTRY":
                raise ValueError("canonical_entry_id must identify a canonical backlog candidate")
        elif self.canonical_entry_id is not None:
            raise ValueError("canonical_entry_id is only valid for DUPLICATE")
        if self.duplicate_resolution == "SAME_EDGE" and self.disposition != "DUPLICATE":
            raise ValueError("SAME_EDGE requires DUPLICATE disposition")
        if self.disposition == "REVIEWED_CONTINUE" and self.duplicate_resolution == "UNRESOLVED":
            raise ValueError("UNRESOLVED cannot become REVIEWED_CONTINUE")
        if self.duplicate_resolution == "RELATED_EDGE_FAMILY":
            if not self.related_edge_family_ids:
                raise ValueError("RELATED_EDGE_FAMILY requires related_edge_family_ids")
        elif self.related_edge_family_ids:
            raise ValueError("related_edge_family_ids require RELATED_EDGE_FAMILY resolution")
        if self.disposition == "SUSPENDED" and not self.revisit_conditions:
            raise ValueError("SUSPENDED requires explicit resume conditions")
        return self


class EdgeBacklogLinkV1(HashedRecord):
    schema_name: Literal[LINK_SCHEMA] = Field(
        default=LINK_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    link_id: Identifier
    entry_id: Identifier
    entry_revision_sha256: Sha256
    sequence: Annotated[int, Field(ge=1)]
    previous_link_sha256: Sha256 | None = None
    relationship: LinkRelationship
    target_kind: TargetKind
    target_id: Identifier
    target_locator: NonBlank
    target_payload_sha256: Sha256
    authorizing_decision_id: Identifier | None = None
    rationale: NonBlank | None = None

    @field_validator("target_locator", "rationale")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def validate_link(self) -> "EdgeBacklogLinkV1":
        if self.record_id != self.link_id:
            raise ValueError("record_id must equal link_id")
        if (self.sequence == 1) != (self.previous_link_sha256 is None):
            raise ValueError("link sequence and previous_link_sha256 are inconsistent")
        expected_kind = _LINK_TARGETS[self.relationship]
        if self.target_kind != expected_kind:
            raise ValueError(f"{self.relationship} requires target_kind {expected_kind}")
        if self.relationship == "HYPOTHESIS_PROPOSAL":
            if self.actor.actor_class != "ALPHAQUEST_DETERMINISTIC_ENGINE":
                raise ValueError("HYPOTHESIS_PROPOSAL link creation belongs to ALPHAQUEST_DETERMINISTIC_ENGINE")
            if self.authorizing_decision_id is not None:
                raise ValueError("HYPOTHESIS_PROPOSAL does not require a P2 human decision")
        if self.relationship == "REVISIT_OF":
            if self.actor.actor_class != "HUMAN_OWNER_RESEARCHER":
                raise ValueError("REVISIT_OF requires HUMAN_OWNER_RESEARCHER authority")
            if self.target_id == self.entry_id:
                raise ValueError("an entry cannot revisit itself")
            if not self.rationale:
                raise ValueError("REVISIT_OF requires a material-trigger rationale")
        if self.relationship in {"ADMITTED_HYPOTHESIS", "EDGE_FAMILY", "CAMPAIGN"}:
            if self.authorizing_decision_id is None:
                raise ValueError(f"{self.relationship} requires later-phase governed authorization")
        return self


RecordType = TypeVar("RecordType", bound=HashedRecord)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole canonical encoding for P2 record identity."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")


def record_sha256(value: HashedRecord | Mapping[str, Any]) -> str:
    payload = value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else dict(value)
    payload.pop("record_sha256", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def backlog_fingerprint(value: EdgeBacklogEntryRevisionV1 | Mapping[str, Any]) -> str:
    payload = value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else dict(value)
    if payload.get("classification_status") != "CLASSIFIED" or payload.get("economic_concepts") is None:
        raise ValueError("NEEDS_CLASSIFICATION entries do not have an economic fingerprint")
    reference = TaxonomyRefV1.model_validate(payload.get("taxonomy_ref"))
    concepts = EconomicConceptsV1.model_validate(payload["economic_concepts"])
    return economic_fingerprint_sha256(reference.taxonomy_id, concepts)


def load_historical_edge_index_records(path: str | Path) -> list[HistoricalEdgeIndexRecordV1]:
    """Load one canonical, strictly ordered historical index through the shared contract."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"historical edge index not found: {source}")
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"could not read historical edge index: {exc}") from exc
    if data and not data.endswith(b"\n"):
        raise ValueError("historical edge index must end with a canonical newline")
    records: list[HistoricalEdgeIndexRecordV1] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    previous_key: tuple[str, int, str, str] | None = None
    for line_number, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line:
            raise ValueError(f"blank historical index line at {line_number}")
        try:
            record = HistoricalEdgeIndexRecordV1.model_validate_json(raw_line)
        except ValueError as exc:
            raise ValueError(f"invalid historical index row {line_number}: {exc}") from exc
        if raw_line != canonical_json_bytes(record):
            raise ValueError(f"historical index row {line_number} is not canonically serialized")
        if record.record_id in seen_ids:
            raise ValueError(f"duplicate historical record_id at row {line_number}: {record.record_id}")
        if record.record_sha256 in seen_hashes:
            raise ValueError(f"duplicate historical record_sha256 at row {line_number}")
        key = _historical_sort_key(record)
        if previous_key is not None and key <= previous_key:
            raise ValueError("historical edge index is not in strict deterministic order")
        records.append(record)
        seen_ids.add(record.record_id)
        seen_hashes.add(record.record_sha256)
        previous_key = key
    return records


def _transactional(*, exclusive: bool):
    def decorate(method):
        @wraps(method)
        def locked(self: "EdgeBacklogStore", *args: Any, **kwargs: Any):
            with self._transaction(exclusive=exclusive):
                return method(self, *args, **kwargs)

        return locked

    return decorate


class EdgeBacklogStore:
    """Append-only access to canonical backlog JSON records."""

    def __init__(
        self,
        project_root: str | Path = ".",
        *,
        layout: StorageLayout | None = None,
        taxonomy_root: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = layout or load_storage_layout(self.project_root)
        self.root = self.layout.edge_backlog_root
        configured_taxonomy_root = self.root / "contracts"
        self.taxonomy_root = Path(taxonomy_root).resolve() if taxonomy_root else (
            configured_taxonomy_root if configured_taxonomy_root.is_dir() else bundled_taxonomy_root()
        )
        self._lock_path = self.layout.studio_runtime_root / "edge-backlog.lock"
        self._thread_lock = threading.RLock()
        self._transaction_state = threading.local()

    @contextmanager
    def _transaction(self, *, exclusive: bool) -> Iterator[None]:
        depth = int(getattr(self._transaction_state, "depth", 0))
        if depth:
            held_exclusive = bool(getattr(self._transaction_state, "exclusive", False))
            if exclusive and not held_exclusive:
                raise EdgeBacklogIntegrityError("cannot upgrade a shared backlog transaction")
            self._transaction_state.depth = depth + 1
            try:
                yield
            finally:
                self._transaction_state.depth -= 1
            return
        with self._thread_lock:
            with backlog_file_lock(self._lock_path, exclusive=exclusive):
                self._transaction_state.depth = 1
                self._transaction_state.exclusive = exclusive
                try:
                    yield
                finally:
                    self._transaction_state.depth = 0
                    self._transaction_state.exclusive = False

    @_transactional(exclusive=True)
    def capture_observation(
        self,
        payload: Mapping[str, Any],
        *,
        actor_id: str,
        task_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> ObservationRevisionV1:
        self.validate()
        observation_id = _require_identifier(payload.get("observation_id"), "observation_id")
        if self._observation_paths(observation_id):
            raise EdgeBacklogConflictError(f"observation {observation_id!r} already exists; append a revision instead")
        return self._append_observation(
            payload,
            observation_id=observation_id,
            actor=_codex_actor(actor_id, task_id),
            recorded_at=recorded_at,
            previous=None,
        )

    @_transactional(exclusive=True)
    def revise_observation(
        self,
        observation_id: str,
        payload: Mapping[str, Any],
        *,
        actor_id: str,
        task_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> ObservationRevisionV1:
        self.validate()
        previous = self.latest_observation(observation_id)
        return self._append_observation(
            payload,
            observation_id=observation_id,
            actor=_codex_actor(actor_id, task_id),
            recorded_at=recorded_at,
            previous=previous,
        )

    @_transactional(exclusive=True)
    def create_entry(
        self,
        payload: Mapping[str, Any],
        *,
        actor_id: str,
        task_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogEntryRevisionV1:
        self.validate()
        if "entry_id" in payload:
            raise EdgeBacklogConflictError("entry_id is engine-generated and cannot be supplied")
        entry_id = self._new_entry_id()
        return self._append_entry(
            payload,
            entry_id=entry_id,
            actor=_codex_actor(actor_id, task_id),
            recorded_at=recorded_at,
            previous=None,
        )

    @_transactional(exclusive=False)
    def current_taxonomy_ref(self) -> TaxonomyRefV1:
        catalog = self._taxonomy_catalog()
        return build_taxonomy_ref(catalog[max(catalog)])

    @_transactional(exclusive=True)
    def revise_entry(
        self,
        entry_id: str,
        payload: Mapping[str, Any],
        *,
        actor_id: str,
        task_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogEntryRevisionV1:
        self.validate()
        previous = self.latest_entry(entry_id)
        decisions = self.decisions(entry_id)
        if decisions:
            current = decisions[-1].disposition
            if current in _TERMINAL_DISPOSITIONS:
                raise EdgeBacklogConflictError(f"entry {entry_id!r} is terminally sealed by {current}")
            if current == "SUSPENDED":
                raise EdgeBacklogConflictError(
                    f"entry {entry_id!r} is suspended; HUMAN_OWNER_RESEARCHER resume is required"
                )
        return self._append_entry(
            payload,
            entry_id=entry_id,
            actor=_codex_actor(actor_id, task_id),
            recorded_at=recorded_at,
            previous=previous,
        )

    @_transactional(exclusive=True)
    def record_human_decision(
        self,
        entry_id: str,
        *,
        disposition: Disposition,
        duplicate_resolution: DuplicateResolution,
        candidate_snapshot_sha256: str,
        reason_codes: Sequence[ReasonCode],
        rationale: str,
        reviewer_id: str,
        canonical_entry_id: str | None = None,
        related_edge_family_ids: Sequence[str] = (),
        revisit_conditions: Sequence[str] = (),
        decision_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogDecisionV1:
        self.validate()
        if disposition == "RESUMED":
            raise EdgeBacklogAuthorityError("use resume_entry for a human-governed resume")
        entry = self.latest_entry(entry_id)
        history = self.decisions(entry_id)
        if history and history[-1].disposition in _TERMINAL_DISPOSITIONS:
            raise EdgeBacklogConflictError(f"entry {entry_id!r} is terminally sealed by {history[-1].disposition}")
        if history and history[-1].disposition == "SUSPENDED":
            raise EdgeBacklogConflictError(f"entry {entry_id!r} is suspended; resume it before another review")
        snapshot = self.duplicate_snapshot(entry_id)
        if candidate_snapshot_sha256 != snapshot["snapshot_sha256"]:
            raise EdgeBacklogConflictError("duplicate candidate snapshot is stale or does not match")
        return self._append_decision(
            entry,
            history,
            disposition=disposition,
            duplicate_resolution=duplicate_resolution,
            candidate_snapshot=snapshot["candidates"],
            candidate_snapshot_sha256=candidate_snapshot_sha256,
            historical_source_commit=snapshot["historical_source_commit"],
            historical_universe_sha256=snapshot["historical_universe_sha256"],
            canonical_entry_id=canonical_entry_id,
            related_edge_family_ids=related_edge_family_ids,
            reason_codes=reason_codes,
            rationale=rationale,
            revisit_conditions=revisit_conditions,
            reviewer_id=reviewer_id,
            decision_id=decision_id,
            recorded_at=recorded_at,
        )

    @_transactional(exclusive=True)
    def resume_entry(
        self,
        entry_id: str,
        *,
        reason_codes: Sequence[ReasonCode],
        rationale: str,
        reviewer_id: str,
        decision_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogDecisionV1:
        self.validate()
        entry = self.latest_entry(entry_id)
        history = self.decisions(entry_id)
        if not history or history[-1].disposition != "SUSPENDED":
            raise EdgeBacklogConflictError(f"entry {entry_id!r} is not currently suspended")
        return self._append_decision(
            entry,
            history,
            disposition="RESUMED",
            duplicate_resolution=None,
            candidate_snapshot=(),
            candidate_snapshot_sha256=None,
            historical_source_commit=None,
            historical_universe_sha256=None,
            canonical_entry_id=None,
            related_edge_family_ids=(),
            reason_codes=reason_codes,
            rationale=rationale,
            revisit_conditions=(),
            reviewer_id=reviewer_id,
            decision_id=decision_id,
            recorded_at=recorded_at,
        )

    @_transactional(exclusive=True)
    def record_hypothesis_proposal_link(
        self,
        entry_id: str,
        *,
        hypothesis_id: str,
        target_locator: str | Path,
        actor_id: str,
        task_id: str | None = None,
        link_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogLinkV1:
        self.validate()
        entry = self.latest_entry(entry_id)
        state = self.entry_state(entry_id)
        if state in {"REJECTED", "DUPLICATE", "SUSPENDED"}:
            raise EdgeBacklogConflictError(f"entry {entry_id!r} cannot propose a hypothesis while {state}")
        target = self._target_file(target_locator)
        return self._append_link(
            entry,
            relationship="HYPOTHESIS_PROPOSAL",
            target_kind="HYPOTHESIS",
            target_id=_require_identifier(hypothesis_id, "hypothesis_id"),
            target_locator=display_path(target, self.project_root),
            target_payload_sha256=_file_sha256(target),
            actor=ActorProvenanceV1(
                actor_class="ALPHAQUEST_DETERMINISTIC_ENGINE",
                actor_id=actor_id,
                task_id=task_id,
            ),
            authorizing_decision_id=None,
            rationale=None,
            link_id=link_id,
            recorded_at=recorded_at,
        )

    @_transactional(exclusive=True)
    def record_revisit_link(
        self,
        entry_id: str,
        *,
        prior_entry_id: str,
        rationale: str,
        reviewer_id: str,
        authorizing_decision_id: str | None = None,
        link_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogLinkV1:
        self.validate()
        entry = self.latest_entry(entry_id)
        prior = self.latest_entry(prior_entry_id)
        if authorizing_decision_id is not None:
            decision = self.decision(prior_entry_id, authorizing_decision_id)
            if decision.disposition not in {"REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"}:
                raise EdgeBacklogConflictError("revisit authorization must reference a prior disposition")
        link = self._append_link(
            entry,
            relationship="REVISIT_OF",
            target_kind="EDGE_BACKLOG_ENTRY",
            target_id=prior.entry_id,
            target_locator=display_path(self._entry_path(prior.entry_id, prior.revision), self.project_root),
            target_payload_sha256=prior.record_sha256,
            actor=ActorProvenanceV1(
                actor_class="HUMAN_OWNER_RESEARCHER",
                actor_id=reviewer_id,
            ),
            authorizing_decision_id=authorizing_decision_id,
            rationale=rationale,
            link_id=link_id,
            recorded_at=recorded_at,
        )
        return link

    def record_reserved_downstream_link(self, *_args: Any, **_kwargs: Any) -> None:
        raise EdgeBacklogAuthorityError(
            "ADMITTED_HYPOTHESIS, EDGE_FAMILY, and CAMPAIGN links are reserved for P3-P5 governed transitions"
        )

    @_transactional(exclusive=False)
    def latest_observation(self, observation_id: str) -> ObservationRevisionV1:
        paths = self._observation_paths(_require_identifier(observation_id, "observation_id"))
        if not paths:
            raise FileNotFoundError(f"observation not found: {observation_id}")
        return self._load_record(paths[-1], ObservationRevisionV1)

    @_transactional(exclusive=False)
    def latest_entry(self, entry_id: str) -> EdgeBacklogEntryRevisionV1:
        paths = self._entry_paths(_require_identifier(entry_id, "entry_id"))
        if not paths:
            raise FileNotFoundError(f"edge backlog entry not found: {entry_id}")
        return self._load_record(paths[-1], EdgeBacklogEntryRevisionV1)

    @_transactional(exclusive=False)
    def decisions(self, entry_id: str) -> list[EdgeBacklogDecisionV1]:
        _require_identifier(entry_id, "entry_id")
        directory = self.root / "entries" / entry_id / "decisions"
        records = []
        for path in sorted(directory.glob("*.json")):
            record = self._load_record(path, EdgeBacklogDecisionV1)
            if path.name != f"{record.sequence:06d}.json":
                raise EdgeBacklogIntegrityError(f"decision filename does not match sequence: {path}")
            records.append(record)
        return records

    @_transactional(exclusive=False)
    def decision(self, entry_id: str, decision_id: str) -> EdgeBacklogDecisionV1:
        for item in self.decisions(entry_id):
            if item.decision_id == decision_id:
                return item
        raise FileNotFoundError(f"decision not found: {entry_id}/{decision_id}")

    @_transactional(exclusive=False)
    def links(self, entry_id: str) -> list[EdgeBacklogLinkV1]:
        _require_identifier(entry_id, "entry_id")
        directory = self.root / "entries" / entry_id / "links"
        records = []
        for path in sorted(directory.glob("*.json")):
            record = self._load_record(path, EdgeBacklogLinkV1)
            if path.name != f"{record.sequence:06d}.json":
                raise EdgeBacklogIntegrityError(f"link filename does not match sequence: {path}")
            records.append(record)
        return records

    @_transactional(exclusive=False)
    def entry_state(self, entry_id: str) -> str:
        entry = self.latest_entry(entry_id)
        history = self.decisions(entry_id)
        if not history or history[-1].entry_revision_sha256 != entry.record_sha256:
            return "UNREVIEWED"
        return history[-1].disposition

    @_transactional(exclusive=False)
    def list_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        directory = self.root / "entries"
        if not directory.is_dir():
            return entries
        for path in sorted(item for item in directory.iterdir() if item.is_dir()):
            entry = self.latest_entry(path.name)
            links = self.links(entry.entry_id)
            entries.append(
                {
                    "entry_id": entry.entry_id,
                    "revision": entry.revision,
                    "record_sha256": entry.record_sha256,
                    "title": self._entry_display_label(entry),
                    "classification_status": entry.classification_status,
                    "instrument_ids": (
                        entry.economic_concepts.instrument_ids if entry.economic_concepts else []
                    ),
                    "state": self.entry_state(entry.entry_id),
                    "fingerprint_sha256": entry.fingerprint_sha256,
                    "hypothesis_proposed": any(link.relationship == "HYPOTHESIS_PROPOSAL" for link in links),
                    "downstream_relationships": sorted({link.relationship for link in links}),
                }
            )
        return entries

    @_transactional(exclusive=False)
    def show(self, entry_id: str) -> dict[str, Any]:
        entry = self.latest_entry(entry_id)
        return {
            "entry": entry.model_dump(mode="json", by_alias=True),
            "display_label": self._entry_display_label(entry),
            "state": self.entry_state(entry_id),
            "decisions": [item.model_dump(mode="json", by_alias=True) for item in self.decisions(entry_id)],
            "links": [item.model_dump(mode="json", by_alias=True) for item in self.links(entry_id)],
        }

    @_transactional(exclusive=False)
    def search(self, query: str | None = None, *, state: str | None = None) -> list[dict[str, Any]]:
        self._historical_index_records()
        query_tokens = duplicate_core.economic_tokens(query or "")
        rows = []
        for summary in self.list_entries():
            if state and summary["state"] != state:
                continue
            entry = self.latest_entry(summary["entry_id"])
            haystack = f"{entry.entry_id} {self._entry_text(entry)}"
            if query_tokens and not query_tokens.intersection(duplicate_core.economic_tokens(haystack)):
                continue
            rows.append(summary)
        return rows

    @_transactional(exclusive=False)
    def duplicate_snapshot(self, entry_id: str) -> dict[str, Any]:
        entry = self.latest_entry(entry_id)
        entry_link_chain_sha256 = _record_chain_sha256(self.links(entry.entry_id))
        historical_records, historical_source_commit, historical_universe_sha256 = (
            self._historical_snapshot_universe()
        )
        candidates = [
            DuplicateCandidateV1.model_validate(item).model_dump(mode="json", by_alias=True)
            for item in self._duplicate_candidates(
                entry,
                historical_records=historical_records,
            )
        ]
        core = {
            "schema": DUPLICATE_SNAPSHOT_SCHEMA,
            "entry_id": entry.entry_id,
            "entry_revision_sha256": entry.record_sha256,
            "entry_link_chain_sha256": entry_link_chain_sha256,
            "historical_source_commit": historical_source_commit,
            "historical_universe_sha256": historical_universe_sha256,
            "candidates": candidates,
        }
        return {**core, "snapshot_sha256": hashlib.sha256(canonical_json_bytes(core)).hexdigest()}

    @_transactional(exclusive=False)
    def duplicate_candidates(self, entry_id: str) -> list[dict[str, Any]]:
        query = self.latest_entry(entry_id)
        historical_records, _commit, _universe_sha256 = self._historical_snapshot_universe()
        return self._duplicate_candidates(query, historical_records=historical_records)

    def _duplicate_candidates(
        self,
        query: EdgeBacklogEntryRevisionV1,
        *,
        historical_records: Sequence[HistoricalEdgeIndexRecordV1],
        before_append_sequence: int | None = None,
        reviewing_recorded_at: datetime | None = None,
        query_links: Sequence[EdgeBacklogLinkV1] | None = None,
    ) -> list[dict[str, Any]]:
        query_text = self._entry_text(query)
        query_tokens = duplicate_core.economic_tokens(query_text)
        bound_query_links = list(query_links) if query_links is not None else self.links(query.entry_id)
        rows: list[dict[str, Any]] = []
        for summary in self.list_entries():
            candidate_id = summary["entry_id"]
            if candidate_id == query.entry_id:
                continue
            revision_history = self._all_entry_revisions(candidate_id)
            revisions = revision_history
            if before_append_sequence is not None:
                revisions = [item for item in revisions if item.append_sequence < before_append_sequence]
                self._validate_candidate_prefix_chronology(
                    included=revisions,
                    reviewing_at=reviewing_recorded_at,
                )
            if not revisions:
                continue
            candidate = revisions[-1]
            link_history = self.links(candidate.entry_id)
            decision_history = self.decisions(candidate.entry_id)
            candidate_links = link_history
            candidate_decisions = decision_history
            if before_append_sequence is not None:
                candidate_links = [
                    item for item in candidate_links if item.append_sequence < before_append_sequence
                ]
                candidate_decisions = [
                    item for item in candidate_decisions if item.append_sequence < before_append_sequence
                ]
                self._validate_candidate_prefix_chronology(
                    included=candidate_links,
                    reviewing_at=reviewing_recorded_at,
                )
                self._validate_candidate_prefix_chronology(
                    included=candidate_decisions,
                    reviewing_at=reviewing_recorded_at,
                )
            rows.append(
                self._canonical_candidate_material(
                    query,
                    bound_query_links,
                    candidate,
                    candidate_decisions,
                    candidate_links,
                )
            )
        rows.extend(
            self._historical_candidate_material(query, query_tokens, record)
            for record in historical_records
        )
        return duplicate_core.rank_duplicate_candidates(
            rows,
            identity_field="candidate_id",
            lexical_field="lexical_similarity",
            minimum_similarity=0.12,
        )

    def _canonical_candidate_material(
        self,
        query: EdgeBacklogEntryRevisionV1,
        query_links: Sequence[EdgeBacklogLinkV1],
        candidate: EdgeBacklogEntryRevisionV1,
        candidate_decisions: Sequence[EdgeBacklogDecisionV1],
        candidate_links: Sequence[EdgeBacklogLinkV1],
    ) -> dict[str, Any]:
        score = duplicate_core.deterministic_duplicate_score(
            query_tokens=duplicate_core.economic_tokens(self._entry_text(query)),
            candidate_tokens=duplicate_core.economic_tokens(self._entry_text(candidate)),
            query_fingerprint=query.fingerprint_sha256,
            candidate_fingerprint=candidate.fingerprint_sha256,
            query_dimensions=self._entry_match_dimensions(query),
            candidate_dimensions=self._entry_match_dimensions(candidate),
            dimension_fields=_IDENTITY_FIELDS,
            dimension_tokenizer=_backlog_dimension_tokens,
            taxonomy_schema="alphaquest.edge-backlog-duplicate-taxonomy/v1",
        )
        source_overlap = sorted(self._entry_source_ids(query) & self._entry_source_ids(candidate))
        related_targets = _shared_link_targets(query_links, candidate_links)
        lineage = _lineage_related(query.entry_id, candidate.entry_id, query_links, candidate_links)
        state = (
            candidate_decisions[-1].disposition
            if candidate_decisions
            and candidate_decisions[-1].entry_revision_sha256 == candidate.record_sha256
            else "UNREVIEWED"
        )
        return {
            "candidate_id": candidate.entry_id,
            "candidate_kind": "CANONICAL_BACKLOG_ENTRY",
            "candidate_record_sha256": candidate.record_sha256,
            "candidate_decision_sha256": (
                candidate_decisions[-1].record_sha256 if candidate_decisions else None
            ),
            "candidate_link_chain_sha256": _record_chain_sha256(candidate_links),
            "title": self._entry_display_label(candidate),
            "state": state,
            "exact_fingerprint": score["exact_fingerprint"],
            "taxonomy_score": score["taxonomy_score"],
            "dimension_scores": score["dimension_scores"],
            "matched_dimensions": score["matched_dimensions"],
            "lexical_similarity": score["lexical_similarity"],
            "source_overlap": source_overlap,
            "shared_link_targets": related_targets,
            "lineage_related": lineage,
            "_force_recall": bool(source_overlap or related_targets or lineage),
        }

    @_transactional(exclusive=False)
    def validate(self) -> dict[str, Any]:
        self._taxonomy_catalog()
        self._historical_index_records()
        observations = self._validate_observations()
        entries = self._validate_entries()
        decision_count = 0
        link_count = 0
        for entry in entries.values():
            decisions = self.decisions(entry.entry_id)
            self._validate_decision_history(entry, decisions)
            decision_count += len(decisions)
            links = self.links(entry.entry_id)
            self._validate_link_history(entry, links)
            link_count += len(links)
        self._validate_source_identities(observations)
        self._validate_revisit_cycles()
        self._validate_duplicate_state()
        self._validate_append_order()
        return {
            "schema": "alphaquest.edge-backlog-validation/v1",
            "status": "PASS",
            "observations": len(observations),
            "entries": len(entries),
            "decisions": decision_count,
            "links": link_count,
        }

    def _append_observation(
        self,
        payload: Mapping[str, Any],
        *,
        observation_id: str,
        actor: ActorProvenanceV1,
        recorded_at: datetime | None,
        previous: ObservationRevisionV1 | None,
    ) -> ObservationRevisionV1:
        supplied_id = payload.get("observation_id")
        if supplied_id is not None and supplied_id != observation_id:
            raise EdgeBacklogConflictError("observation revision cannot change observation_id")
        revision = 1 if previous is None else previous.revision + 1
        material = _without_managed_fields(payload)
        material.update(
            {
                "schema": OBSERVATION_SCHEMA,
                "record_id": _revision_record_id(observation_id, revision),
                "append_sequence": self._next_append_sequence(),
                "observation_id": observation_id,
                "revision": revision,
                "previous_revision_sha256": previous.record_sha256 if previous else None,
                "actor": actor.model_dump(mode="json"),
                "recorded_at": recorded_at or _now(),
            }
        )
        record = _seal(ObservationRevisionV1, material)
        if previous and record.recorded_at < previous.recorded_at:
            raise EdgeBacklogConflictError("observation revision recorded_at cannot move backward")
        if previous:
            missing_conflicts = set(previous.known_conflicts) - set(record.known_conflicts)
            if missing_conflicts:
                raise EdgeBacklogConflictError(
                    "known conflicting evidence cannot disappear during observation revision"
                )
        self._validate_new_source_identities(record)
        self._exclusive_write(self._observation_path(observation_id, revision), record)
        return record

    def _append_entry(
        self,
        payload: Mapping[str, Any],
        *,
        entry_id: str,
        actor: ActorProvenanceV1,
        recorded_at: datetime | None,
        previous: EdgeBacklogEntryRevisionV1 | None,
    ) -> EdgeBacklogEntryRevisionV1:
        supplied_id = payload.get("entry_id")
        if supplied_id is not None:
            raise EdgeBacklogConflictError("entry_id is managed and cannot be supplied in an entry revision")
        revision = 1 if previous is None else previous.revision + 1
        material = _without_managed_fields(payload)
        material.update(
            {
                "schema": ENTRY_SCHEMA,
                "record_id": _revision_record_id(entry_id, revision),
                "append_sequence": self._next_append_sequence(),
                "entry_id": entry_id,
                "revision": revision,
                "previous_revision_sha256": previous.record_sha256 if previous else None,
                "actor": actor.model_dump(mode="json"),
                "recorded_at": recorded_at or _now(),
            }
        )
        classification_status = material.get("classification_status")
        material["fingerprint_schema"] = (
            FINGERPRINT_SCHEMA if classification_status == "CLASSIFIED" else None
        )
        material["fingerprint_sha256"] = "0" * 64 if classification_status == "CLASSIFIED" else None
        draft = EdgeBacklogEntryRevisionV1.model_validate(
            {**material, "record_sha256": "0" * 64},
            context={"skip_record_hash": True, "skip_fingerprint": True},
        )
        material = draft.model_dump(mode="json", by_alias=True, exclude={"record_sha256"})
        self._validate_entry_taxonomy(draft, check_fingerprint=False)
        if draft.classification_status == "CLASSIFIED":
            material["fingerprint_sha256"] = backlog_fingerprint(material)
        record = _seal(EdgeBacklogEntryRevisionV1, material)
        if previous and record.recorded_at < previous.recorded_at:
            raise EdgeBacklogConflictError("entry revision recorded_at cannot move backward")
        decision_history = self.decisions(entry_id) if previous else []
        if decision_history and record.recorded_at < decision_history[-1].recorded_at:
            raise EdgeBacklogConflictError("entry revision cannot precede the latest decision")
        self._validate_observation_refs(
            record.observation_refs,
            recorded_at=record.recorded_at,
            append_sequence=record.append_sequence,
        )
        if previous:
            previous_contradictions = {
                (item.observation_id, item.observation_revision_sha256)
                for item in previous.observation_refs
                if item.role == "CONTRADICTING"
            }
            current_contradictions = {
                (item.observation_id, item.observation_revision_sha256)
                for item in record.observation_refs
                if item.role == "CONTRADICTING"
            }
            if not previous_contradictions.issubset(current_contradictions):
                raise EdgeBacklogConflictError(
                    "contradicting observation references cannot disappear during entry revision"
                )
        self._exclusive_write(self._entry_path(entry_id, revision), record)
        return record

    def _append_decision(
        self,
        entry: EdgeBacklogEntryRevisionV1,
        history: Sequence[EdgeBacklogDecisionV1],
        *,
        disposition: Disposition,
        duplicate_resolution: DuplicateResolution | None,
        candidate_snapshot: Sequence[Mapping[str, Any]],
        candidate_snapshot_sha256: str | None,
        historical_source_commit: str | None,
        historical_universe_sha256: str | None,
        canonical_entry_id: str | None,
        related_edge_family_ids: Sequence[str],
        reason_codes: Sequence[ReasonCode],
        rationale: str,
        revisit_conditions: Sequence[str],
        reviewer_id: str,
        decision_id: str | None,
        recorded_at: datetime | None,
    ) -> EdgeBacklogDecisionV1:
        sequence = len(history) + 1
        identifier = decision_id or _generated_id("decision", entry.entry_id, sequence, recorded_at)
        material = {
            "schema": DECISION_SCHEMA,
            "record_id": identifier,
            "append_sequence": self._next_append_sequence(),
            "decision_id": identifier,
            "entry_id": entry.entry_id,
            "entry_revision_sha256": entry.record_sha256,
            "entry_link_chain_sha256": _record_chain_sha256(self.links(entry.entry_id)),
            "sequence": sequence,
            "previous_decision_sha256": history[-1].record_sha256 if history else None,
            "disposition": disposition,
            "duplicate_resolution": duplicate_resolution,
            "candidate_snapshot": list(candidate_snapshot),
            "candidate_snapshot_sha256": candidate_snapshot_sha256,
            "historical_source_commit": historical_source_commit,
            "historical_universe_sha256": historical_universe_sha256,
            "canonical_entry_id": canonical_entry_id,
            "related_edge_family_ids": list(related_edge_family_ids),
            "reason_codes": list(reason_codes),
            "rationale": rationale,
            "revisit_conditions": list(revisit_conditions),
            "recorded_at": recorded_at or _now(),
            "actor": {
                "actor_class": "HUMAN_OWNER_RESEARCHER",
                "actor_id": reviewer_id,
                "task_id": None,
            },
        }
        record = _seal(EdgeBacklogDecisionV1, material)
        if history and record.recorded_at < history[-1].recorded_at:
            raise EdgeBacklogConflictError("decision recorded_at cannot move backward")
        self._validate_decision_history(entry, [*history, record])
        try:
            self._validate_duplicate_state(pending=record)
        except EdgeBacklogIntegrityError as exc:
            raise EdgeBacklogConflictError(str(exc)) from exc
        path = self.root / "entries" / entry.entry_id / "decisions" / f"{sequence:06d}.json"
        self._exclusive_write(path, record)
        return record

    def _append_link(
        self,
        entry: EdgeBacklogEntryRevisionV1,
        *,
        relationship: LinkRelationship,
        target_kind: TargetKind,
        target_id: str,
        target_locator: str,
        target_payload_sha256: str,
        actor: ActorProvenanceV1,
        authorizing_decision_id: str | None,
        rationale: str | None,
        link_id: str | None,
        recorded_at: datetime | None,
    ) -> EdgeBacklogLinkV1:
        state = self.entry_state(entry.entry_id)
        if state in {*_TERMINAL_DISPOSITIONS, "SUSPENDED"}:
            raise EdgeBacklogConflictError(f"entry {entry.entry_id!r} cannot append a link while {state}")
        history = self.links(entry.entry_id)
        sequence = len(history) + 1
        identifier = link_id or _generated_id("link", entry.entry_id, sequence, recorded_at)
        material = {
            "schema": LINK_SCHEMA,
            "record_id": identifier,
            "append_sequence": self._next_append_sequence(),
            "link_id": identifier,
            "entry_id": entry.entry_id,
            "entry_revision_sha256": entry.record_sha256,
            "sequence": sequence,
            "previous_link_sha256": history[-1].record_sha256 if history else None,
            "relationship": relationship,
            "target_kind": target_kind,
            "target_id": target_id,
            "target_locator": target_locator,
            "target_payload_sha256": target_payload_sha256,
            "authorizing_decision_id": authorizing_decision_id,
            "rationale": rationale,
            "recorded_at": recorded_at or _now(),
            "actor": actor.model_dump(mode="json"),
        }
        record = _seal(EdgeBacklogLinkV1, material)
        if history and record.recorded_at < history[-1].recorded_at:
            raise EdgeBacklogConflictError("link recorded_at cannot move backward")
        decision_history = self.decisions(entry.entry_id)
        if decision_history and record.recorded_at < decision_history[-1].recorded_at:
            raise EdgeBacklogConflictError("link cannot precede the latest source-entry decision")
        self._validate_link_history(entry, [*history, record])
        if relationship == "REVISIT_OF" and self._would_create_revisit_cycle(entry.entry_id, target_id):
            raise EdgeBacklogConflictError("REVISIT_OF would create a lineage cycle")
        path = self.root / "entries" / entry.entry_id / "links" / f"{sequence:06d}.json"
        self._exclusive_write(path, record)
        return record

    def _validate_observations(self) -> dict[str, ObservationRevisionV1]:
        latest: dict[str, ObservationRevisionV1] = {}
        directory = self.root / "observations"
        if not directory.is_dir():
            return latest
        for observation_dir in sorted(item for item in directory.iterdir() if item.is_dir()):
            previous: ObservationRevisionV1 | None = None
            paths = self._observation_paths(observation_dir.name)
            for expected_revision, path in enumerate(paths, start=1):
                record = self._load_record(path, ObservationRevisionV1)
                if (
                    path.name != f"{expected_revision:06d}.json"
                    or record.observation_id != observation_dir.name
                    or record.revision != expected_revision
                ):
                    raise EdgeBacklogIntegrityError(f"observation path identity mismatch: {path}")
                if record.previous_revision_sha256 != (previous.record_sha256 if previous else None):
                    raise EdgeBacklogIntegrityError(f"broken observation revision chain: {path}")
                if previous and record.recorded_at < previous.recorded_at:
                    raise EdgeBacklogIntegrityError(f"observation revision chronology moved backward at {path}")
                if previous and record.append_sequence <= previous.append_sequence:
                    raise EdgeBacklogIntegrityError(f"observation append order moved backward at {path}")
                if previous and not set(previous.known_conflicts).issubset(record.known_conflicts):
                    raise EdgeBacklogIntegrityError(f"observation conflicts were removed at {path}")
                previous = record
            if previous:
                latest[previous.observation_id] = previous
        return latest

    def _validate_entries(self) -> dict[str, EdgeBacklogEntryRevisionV1]:
        latest: dict[str, EdgeBacklogEntryRevisionV1] = {}
        directory = self.root / "entries"
        if not directory.is_dir():
            return latest
        for entry_dir in sorted(item for item in directory.iterdir() if item.is_dir()):
            previous: EdgeBacklogEntryRevisionV1 | None = None
            paths = self._entry_paths(entry_dir.name)
            for expected_revision, path in enumerate(paths, start=1):
                record = self._load_record(path, EdgeBacklogEntryRevisionV1)
                self._validate_entry_taxonomy(record)
                if (
                    path.name != f"{expected_revision:06d}.json"
                    or record.entry_id != entry_dir.name
                    or record.revision != expected_revision
                ):
                    raise EdgeBacklogIntegrityError(f"entry path identity mismatch: {path}")
                if record.previous_revision_sha256 != (previous.record_sha256 if previous else None):
                    raise EdgeBacklogIntegrityError(f"broken entry revision chain: {path}")
                if previous and record.recorded_at < previous.recorded_at:
                    raise EdgeBacklogIntegrityError(f"entry revision chronology moved backward at {path}")
                if previous and record.append_sequence <= previous.append_sequence:
                    raise EdgeBacklogIntegrityError(f"entry append order moved backward at {path}")
                self._validate_observation_refs(
                    record.observation_refs,
                    recorded_at=record.recorded_at,
                    append_sequence=record.append_sequence,
                )
                if previous:
                    old = {
                        (item.observation_id, item.observation_revision_sha256)
                        for item in previous.observation_refs
                        if item.role == "CONTRADICTING"
                    }
                    new = {
                        (item.observation_id, item.observation_revision_sha256)
                        for item in record.observation_refs
                        if item.role == "CONTRADICTING"
                    }
                    if not old.issubset(new):
                        raise EdgeBacklogIntegrityError(f"contradicting evidence was removed at {path}")
                previous = record
            if previous:
                latest[previous.entry_id] = previous
        return latest

    def _validate_decision_history(
        self,
        entry: EdgeBacklogEntryRevisionV1,
        decisions: Sequence[EdgeBacklogDecisionV1],
    ) -> None:
        previous: EdgeBacklogDecisionV1 | None = None
        revision_history = self._all_entry_revisions(entry.entry_id)
        revisions = {item.record_sha256: item for item in revision_history}
        revision_positions = {item.record_sha256: position for position, item in enumerate(revision_history, start=1)}
        link_history = self.links(entry.entry_id)
        link_prefixes = {
            _record_chain_sha256(link_history[:prefix_length]): prefix_length
            for prefix_length in range(len(link_history) + 1)
        }
        previous_revision_position = 0
        previous_link_prefix = 0
        for expected_sequence, decision in enumerate(decisions, start=1):
            if decision.entry_id != entry.entry_id or decision.sequence != expected_sequence:
                raise EdgeBacklogIntegrityError("decision path/sequence does not match entry")
            if decision.previous_decision_sha256 != (previous.record_sha256 if previous else None):
                raise EdgeBacklogIntegrityError("broken decision hash chain")
            if previous and decision.recorded_at < previous.recorded_at:
                raise EdgeBacklogIntegrityError("decision chronology moved backward")
            if previous and decision.append_sequence <= previous.append_sequence:
                raise EdgeBacklogIntegrityError("decision append order moved backward")
            if decision.entry_revision_sha256 not in revisions:
                raise EdgeBacklogIntegrityError("decision references a missing entry revision")
            bound_revision = revisions[decision.entry_revision_sha256]
            revision_position = revision_positions[decision.entry_revision_sha256]
            if revision_position < previous_revision_position:
                raise EdgeBacklogIntegrityError("decision entry-revision binding moved backward")
            if decision.recorded_at < bound_revision.recorded_at:
                raise EdgeBacklogIntegrityError("decision precedes its bound entry revision")
            if decision.append_sequence <= bound_revision.append_sequence:
                raise EdgeBacklogIntegrityError("decision append order precedes its bound entry revision")
            if any(
                later.append_sequence < decision.append_sequence
                for later in revision_history[revision_position:]
            ):
                raise EdgeBacklogIntegrityError("decision omits an entry revision that preceded it in append order")
            if any(
                later.recorded_at < decision.recorded_at
                for later in revision_history[revision_position:]
            ):
                raise EdgeBacklogIntegrityError("a later entry revision is backdated before its preceding decision")
            link_prefix = link_prefixes.get(decision.entry_link_chain_sha256)
            if link_prefix is None:
                raise EdgeBacklogIntegrityError("decision entry_link_chain_sha256 is not an exact historical prefix")
            if link_prefix < previous_link_prefix:
                raise EdgeBacklogIntegrityError("decision link-chain binding moved backward")
            if any(link.recorded_at > decision.recorded_at for link in link_history[:link_prefix]):
                raise EdgeBacklogIntegrityError("decision precedes a link included in its bound link-chain prefix")
            if any(link.append_sequence >= decision.append_sequence for link in link_history[:link_prefix]):
                raise EdgeBacklogIntegrityError("decision includes a link appended after the decision")
            if any(link.append_sequence < decision.append_sequence for link in link_history[link_prefix:]):
                raise EdgeBacklogIntegrityError("decision omits a link that preceded it in append order")
            if any(link.recorded_at < decision.recorded_at for link in link_history[link_prefix:]):
                raise EdgeBacklogIntegrityError("a later link is backdated before its preceding decision")
            if decision.disposition != "RESUMED":
                self._validate_persisted_candidate_snapshot(
                    reviewing_entry=bound_revision,
                    reviewing_links=link_history[:link_prefix],
                    reviewing_decision=decision,
                )
            if previous:
                if previous.disposition in _TERMINAL_DISPOSITIONS:
                    raise EdgeBacklogIntegrityError("terminal decision has later history")
                if previous.disposition == "SUSPENDED" and decision.disposition != "RESUMED":
                    raise EdgeBacklogIntegrityError("SUSPENDED may only transition to RESUMED")
                if decision.disposition == "RESUMED" and previous.disposition != "SUSPENDED":
                    raise EdgeBacklogIntegrityError("RESUMED requires a current SUSPENDED decision")
                if previous.disposition == "SUSPENDED" and (
                    revision_position != previous_revision_position or link_prefix != previous_link_prefix
                ):
                    raise EdgeBacklogIntegrityError("SUSPENDED interval contains a prohibited entry or link change")
            elif decision.disposition == "RESUMED":
                raise EdgeBacklogIntegrityError("RESUMED cannot be the first decision")
            if decision.disposition == "DUPLICATE":
                try:
                    self.latest_entry(str(decision.canonical_entry_id))
                except FileNotFoundError as exc:
                    raise EdgeBacklogIntegrityError("DUPLICATE canonical entry does not exist") from exc
            previous = decision
            previous_revision_position = revision_position
            previous_link_prefix = link_prefix
        if decisions:
            latest = decisions[-1]
            if latest.disposition in _TERMINAL_DISPOSITIONS and latest.entry_revision_sha256 != entry.record_sha256:
                raise EdgeBacklogIntegrityError("a terminal decision does not seal the latest entry revision")
            if latest.disposition in _TERMINAL_DISPOSITIONS and previous_link_prefix != len(link_history):
                raise EdgeBacklogIntegrityError("a terminal decision does not seal the complete link history")
            if latest.disposition == "SUSPENDED":
                suspended_revision = revisions[latest.entry_revision_sha256]
                if entry.revision != suspended_revision.revision:
                    raise EdgeBacklogIntegrityError("entry was revised without a human resume")
                if previous_link_prefix != len(link_history):
                    raise EdgeBacklogIntegrityError("entry received a link without a human resume")

    def _validate_persisted_candidate_snapshot(
        self,
        *,
        reviewing_entry: EdgeBacklogEntryRevisionV1,
        reviewing_links: Sequence[EdgeBacklogLinkV1],
        reviewing_decision: EdgeBacklogDecisionV1,
    ) -> None:
        if reviewing_decision.historical_source_commit is None:
            historical_records: list[HistoricalEdgeIndexRecordV1] = []
        else:
            from alphaquest.research.edge_backlog_bootstrap import (
                historical_records_for_repository_commit,
                repository_commit_recorded_at,
            )

            commit, historical_records = historical_records_for_repository_commit(
                self.project_root,
                reviewing_decision.historical_source_commit,
            )
            if commit != reviewing_decision.historical_source_commit:
                raise EdgeBacklogIntegrityError("historical source commit did not resolve exactly")
            if repository_commit_recorded_at(self.project_root, commit) > reviewing_decision.recorded_at:
                raise EdgeBacklogIntegrityError(
                    "historical matcher universe commit is later than the reviewing decision"
                )
        actual_universe_sha256 = _historical_universe_sha256(historical_records)
        if actual_universe_sha256 != reviewing_decision.historical_universe_sha256:
            raise EdgeBacklogIntegrityError(
                "historical matcher universe does not match its immutable source commit"
            )
        expected = [
            DuplicateCandidateV1.model_validate(item).model_dump(mode="json", by_alias=True)
            for item in self._duplicate_candidates(
                reviewing_entry,
                historical_records=historical_records,
                before_append_sequence=reviewing_decision.append_sequence,
                reviewing_recorded_at=reviewing_decision.recorded_at,
                query_links=reviewing_links,
            )
        ]
        actual = [
            item.model_dump(mode="json", by_alias=True)
            for item in reviewing_decision.candidate_snapshot
        ]
        if expected != actual:
            raise EdgeBacklogIntegrityError(
                "candidate snapshot is not the complete deterministic universe at the review append sequence"
            )

    @staticmethod
    def _validate_candidate_prefix_chronology(
        *,
        included: Sequence[HashedRecord],
        reviewing_at: datetime | None,
    ) -> None:
        if reviewing_at is None:
            return
        if any(item.recorded_at > reviewing_at for item in included):
            raise EdgeBacklogIntegrityError(
                "candidate snapshot contains activity timestamped after the reviewing decision"
            )

    def _validate_link_history(
        self,
        entry: EdgeBacklogEntryRevisionV1,
        links: Sequence[EdgeBacklogLinkV1],
    ) -> None:
        previous: EdgeBacklogLinkV1 | None = None
        revision_history = self._all_entry_revisions(entry.entry_id)
        revisions = {item.record_sha256: item for item in revision_history}
        positions = {item.record_sha256: position for position, item in enumerate(revision_history, start=1)}
        previous_revision_position = 0
        for expected_sequence, link in enumerate(links, start=1):
            if link.entry_id != entry.entry_id or link.sequence != expected_sequence:
                raise EdgeBacklogIntegrityError("link path/sequence does not match entry")
            if link.previous_link_sha256 != (previous.record_sha256 if previous else None):
                raise EdgeBacklogIntegrityError("broken link hash chain")
            if previous and link.recorded_at < previous.recorded_at:
                raise EdgeBacklogIntegrityError("link chronology moved backward")
            if previous and link.append_sequence <= previous.append_sequence:
                raise EdgeBacklogIntegrityError("link append order moved backward")
            if link.entry_revision_sha256 not in revisions:
                raise EdgeBacklogIntegrityError("link references a missing entry revision")
            bound_revision = revisions[link.entry_revision_sha256]
            revision_position = positions[link.entry_revision_sha256]
            if revision_position < previous_revision_position:
                raise EdgeBacklogIntegrityError("link entry-revision binding moved backward")
            if link.recorded_at < bound_revision.recorded_at:
                raise EdgeBacklogIntegrityError("link precedes its bound entry revision")
            if link.append_sequence <= bound_revision.append_sequence:
                raise EdgeBacklogIntegrityError("link append order precedes its bound entry revision")
            target = self._target_file(link.target_locator)
            if link.relationship == "REVISIT_OF":
                target_record = self._load_record(target, EdgeBacklogEntryRevisionV1)
                target_sha256 = target_record.record_sha256
                expected_target = self._entry_path(link.target_id, target_record.revision).resolve()
                if target.resolve() != expected_target or target_record.entry_id != link.target_id:
                    raise EdgeBacklogIntegrityError(
                        "REVISIT_OF locator, target_id, and loaded entry revision do not identify one target"
                    )
                if link.recorded_at < target_record.recorded_at:
                    raise EdgeBacklogIntegrityError(
                        "REVISIT_OF link precedes its exact targeted prior-entry revision"
                    )
                if link.append_sequence <= target_record.append_sequence:
                    raise EdgeBacklogIntegrityError(
                        "REVISIT_OF link append order precedes its exact target revision"
                    )
                if link.authorizing_decision_id is not None:
                    try:
                        authorization = self.decision(link.target_id, link.authorizing_decision_id)
                    except FileNotFoundError as exc:
                        raise EdgeBacklogIntegrityError(
                            "REVISIT_OF authorizing decision does not exist on the prior entry"
                        ) from exc
                    if link.recorded_at < authorization.recorded_at:
                        raise EdgeBacklogIntegrityError("link precedes its authorizing decision")
                    if link.append_sequence <= authorization.append_sequence:
                        raise EdgeBacklogIntegrityError("link append order precedes its authorizing decision")
                    if authorization.disposition not in {"REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"}:
                        raise EdgeBacklogIntegrityError(
                            "REVISIT_OF authorization must be a prior disposition on the exact target entry"
                        )
            elif link.relationship in {"ADMITTED_HYPOTHESIS", "EDGE_FAMILY", "CAMPAIGN"}:
                raise EdgeBacklogAuthorityError(f"{link.relationship} is reserved and cannot be materialized by P2")
            else:
                target_sha256 = _file_sha256(target)
            if target_sha256 != link.target_payload_sha256:
                raise EdgeBacklogIntegrityError("link target hash does not match its locator")
            previous = link
            previous_revision_position = revision_position

    def _validate_source_identities(self, observations: Mapping[str, ObservationRevisionV1]) -> None:
        self._source_identity_state(tuple(observations))

    def _validate_new_source_identities(self, record: ObservationRevisionV1) -> None:
        identities = self._source_identity_state()
        for source in record.evidence_refs:
            identity = (source.source_kind, source.locator, source.content_sha256)
            previous = identities.get(source.source_id)
            if previous is not None:
                _assert_source_identity_compatible(source.source_id, previous, identity)
            _remember_source_identity(identities, source)
        self._source_identity_state(additional_records=(record,))

    def _source_identity_state(
        self,
        observation_ids: Sequence[str] | None = None,
        *,
        additional_records: Sequence[ObservationRevisionV1] = (),
    ) -> dict[str, tuple[str, str, str | None]]:
        identities: dict[str, tuple[str, str, str | None]] = {}
        events: list[tuple[datetime, EvidenceReferenceV1]] = []
        identifiers = observation_ids
        if identifiers is None:
            identifiers = tuple(item.name for item in sorted((self.root / "observations").glob("*")) if item.is_dir())
        for observation_id in identifiers:
            for revision in self._all_observation_revisions(observation_id):
                for source in revision.evidence_refs:
                    _remember_source_identity(identities, source)
                    events.append((revision.recorded_at, source))
        for revision in additional_records:
            for source in revision.evidence_refs:
                _remember_source_identity(identities, source)
                events.append((revision.recorded_at, source))
        hash_bound_at: dict[str, datetime] = {}
        for recorded_at, source in events:
            if source.content_sha256 is not None:
                previous = hash_bound_at.get(source.source_id)
                hash_bound_at[source.source_id] = min(previous, recorded_at) if previous else recorded_at
        for recorded_at, source in events:
            bound_at = hash_bound_at.get(source.source_id)
            if bound_at is not None and source.content_sha256 is None and recorded_at >= bound_at:
                raise EdgeBacklogIntegrityError(
                    f"source_id {source.source_id!r} has LOCATOR_ONLY evidence that is not strictly earlier "
                    "than its first HASH_BOUND occurrence"
                )
        return identities

    def _validate_observation_refs(
        self,
        refs: Sequence[ObservationReferenceV1],
        *,
        recorded_at: datetime,
        append_sequence: int,
    ) -> None:
        for ref in refs:
            path = self.root / "observations" / ref.observation_id / "revisions"
            found: ObservationRevisionV1 | None = None
            for candidate in sorted(path.glob("*.json")):
                observation = self._load_record(candidate, ObservationRevisionV1)
                if observation.record_sha256 == ref.observation_revision_sha256:
                    found = observation
                    break
            if found is None:
                raise EdgeBacklogIntegrityError(
                    f"missing observation revision {ref.observation_id}/{ref.observation_revision_sha256}"
                )
            if recorded_at < found.recorded_at:
                raise EdgeBacklogIntegrityError(
                    f"entry precedes referenced observation revision {ref.observation_id}/{ref.observation_revision_sha256}"
                )
            if append_sequence <= found.append_sequence:
                raise EdgeBacklogIntegrityError(
                    f"entry append order precedes referenced observation revision "
                    f"{ref.observation_id}/{ref.observation_revision_sha256}"
                )

    def _entry_source_ids(self, entry: EdgeBacklogEntryRevisionV1) -> set[str]:
        sources: set[str] = set()
        for ref in entry.observation_refs:
            for revision in self._all_observation_revisions(ref.observation_id):
                if revision.record_sha256 == ref.observation_revision_sha256:
                    sources.update(item.source_id for item in revision.evidence_refs)
        return sources

    def _historical_candidates(
        self,
        query: EdgeBacklogEntryRevisionV1,
        query_tokens: set[str],
    ) -> list[dict[str, Any]]:
        return [
            self._historical_candidate_material(query, query_tokens, record)
            for record in self._historical_index_records()
        ]

    def _historical_candidate_material(
        self,
        query: EdgeBacklogEntryRevisionV1,
        query_tokens: set[str],
        historical_record: HistoricalEdgeIndexRecordV1,
    ) -> dict[str, Any]:
        record = historical_record.model_dump(mode="json", by_alias=True)
        history_text = " ".join(
            str(record.get(key) or "")
            for key in (
                "campaign_id",
                "raw_title",
                "raw_edge",
                "raw_hypothesis",
                "raw_edge_family",
                "raw_failure_reason",
            )
        )
        score = duplicate_core.deterministic_duplicate_score(
            query_tokens=query_tokens,
            candidate_tokens=duplicate_core.economic_tokens(history_text),
            query_fingerprint=None,
            candidate_fingerprint=None,
            query_dimensions=None,
            candidate_dimensions=None,
            dimension_fields=_IDENTITY_FIELDS,
            dimension_tokenizer=_backlog_dimension_tokens,
            taxonomy_schema="alphaquest.edge-backlog-duplicate-taxonomy/v1",
            available_only=True,
        )
        return {
            "candidate_id": f"history:{historical_record.record_sha256}",
            "candidate_kind": "DERIVED_HISTORICAL_RECORD",
            "candidate_record_sha256": historical_record.record_sha256,
            "candidate_decision_sha256": None,
            "candidate_link_chain_sha256": _EMPTY_RECORD_CHAIN_SHA256,
            **_historical_candidate_projection(historical_record),
            "exact_fingerprint": score["exact_fingerprint"],
            "taxonomy_score": score["taxonomy_score"],
            "dimension_scores": score["dimension_scores"],
            "matched_dimensions": score["matched_dimensions"],
            "lexical_similarity": score["lexical_similarity"],
            "source_overlap": [],
            "shared_link_targets": [],
            "lineage_related": False,
            "historical_record": record,
        }

    def _historical_index_records(self) -> list[HistoricalEdgeIndexRecordV1]:
        path = self.layout.edge_backlog_history_index
        if not path.is_file():
            return []
        try:
            records = load_historical_edge_index_records(path)
            from alphaquest.research.edge_backlog_bootstrap import validate_historical_records_provenance

            validate_historical_records_provenance(
                records,
                project_root=self.project_root,
                layout=self.layout,
            )
            return records
        except (OSError, ValueError) as exc:
            raise EdgeBacklogIntegrityError(f"invalid configured historical backlog index {path}: {exc}") from exc

    def _historical_snapshot_universe(
        self,
    ) -> tuple[list[HistoricalEdgeIndexRecordV1], str | None, str]:
        records = self._historical_index_records()
        if not records:
            return [], None, _EMPTY_HISTORICAL_UNIVERSE_SHA256
        from alphaquest.research.edge_backlog_bootstrap import historical_records_for_repository_commit

        try:
            commit, committed_records = historical_records_for_repository_commit(self.project_root)
        except (OSError, ValueError) as exc:
            raise EdgeBacklogIntegrityError(
                f"historical matcher universe is not bound to an immutable repository source state: {exc}"
            ) from exc
        if [item.model_dump(mode="json", by_alias=True) for item in records] != [
            item.model_dump(mode="json", by_alias=True) for item in committed_records
        ]:
            raise EdgeBacklogIntegrityError(
                "configured historical index does not equal the complete repository-bound source extraction"
            )
        return records, commit, _historical_universe_sha256(records)

    def _taxonomy_catalog(self) -> dict[int, EconomicEdgeTaxonomyV1]:
        try:
            return load_taxonomy_catalog(self.taxonomy_root)
        except (OSError, ValueError) as exc:
            raise EdgeBacklogIntegrityError(
                f"invalid configured economic-edge taxonomy under {self.taxonomy_root}: {exc}"
            ) from exc

    def _taxonomy_for_entry(self, entry: EdgeBacklogEntryRevisionV1) -> EconomicEdgeTaxonomyV1:
        try:
            return resolve_taxonomy(self._taxonomy_catalog(), entry.taxonomy_ref)
        except ValueError as exc:
            raise EdgeBacklogIntegrityError(f"entry taxonomy_ref is invalid: {exc}") from exc

    def _validate_entry_taxonomy(
        self,
        entry: EdgeBacklogEntryRevisionV1,
        *,
        check_fingerprint: bool = True,
    ) -> None:
        taxonomy = self._taxonomy_for_entry(entry)
        if entry.economic_concepts is None:
            return
        try:
            validate_concepts(taxonomy, entry.economic_concepts)
        except ValueError as exc:
            raise EdgeBacklogIntegrityError(f"entry economic concepts are invalid: {exc}") from exc
        if check_fingerprint and entry.fingerprint_sha256 != economic_fingerprint_sha256(
            taxonomy.taxonomy_id,
            entry.economic_concepts,
        ):
            raise EdgeBacklogIntegrityError("entry fingerprint does not match its bound economic concepts")

    def _entry_display_label(self, entry: EdgeBacklogEntryRevisionV1) -> str:
        if entry.economic_concepts is None:
            return f"Needs classification · {entry.entry_id}"
        taxonomy = self._taxonomy_for_entry(entry)
        return derived_display_label(taxonomy, entry.economic_concepts)

    def _entry_match_dimensions(self, entry: EdgeBacklogEntryRevisionV1) -> dict[str, Any] | None:
        if entry.economic_concepts is None:
            return None
        taxonomy = self._taxonomy_for_entry(entry)
        return matcher_dimensions(taxonomy, entry.economic_concepts)

    def _entry_text(self, entry: EdgeBacklogEntryRevisionV1) -> str:
        dimensions = self._entry_match_dimensions(entry)
        if dimensions is not None:
            return " ".join(term for field in _IDENTITY_FIELDS for term in dimensions[field])
        statements: list[str] = []
        for ref in entry.observation_refs:
            for revision in self._all_observation_revisions(ref.observation_id):
                if revision.record_sha256 == ref.observation_revision_sha256:
                    statements.append(revision.statement)
                    statements.extend(revision.known_conflicts)
                    break
        return " ".join(statements)

    def _new_entry_id(self) -> str:
        for _attempt in range(128):
            candidate = f"edge.{secrets.token_hex(16)}"
            if not self._entry_paths(candidate):
                return candidate
        raise EdgeBacklogConflictError("could not allocate a unique opaque entry_id")

    def _all_observation_revisions(self, observation_id: str) -> list[ObservationRevisionV1]:
        return [self._load_record(path, ObservationRevisionV1) for path in self._observation_paths(observation_id)]

    def _all_entry_revisions(self, entry_id: str) -> list[EdgeBacklogEntryRevisionV1]:
        return [self._load_record(path, EdgeBacklogEntryRevisionV1) for path in self._entry_paths(entry_id)]

    def _observation_paths(self, observation_id: str) -> list[Path]:
        return sorted((self.root / "observations" / observation_id / "revisions").glob("*.json"))

    def _entry_paths(self, entry_id: str) -> list[Path]:
        return sorted((self.root / "entries" / entry_id / "revisions").glob("*.json"))

    def _observation_path(self, observation_id: str, revision: int) -> Path:
        return self.root / "observations" / observation_id / "revisions" / f"{revision:06d}.json"

    def _entry_path(self, entry_id: str, revision: int) -> Path:
        return self.root / "entries" / entry_id / "revisions" / f"{revision:06d}.json"

    def _load_record(self, path: Path, model: type[RecordType]) -> RecordType:
        try:
            data = path.read_bytes()
            record = model.model_validate_json(data)
        except (OSError, ValueError) as exc:
            raise EdgeBacklogIntegrityError(f"invalid canonical backlog record {path}: {exc}") from exc
        expected = canonical_json_bytes(record) + b"\n"
        if data != expected:
            raise EdgeBacklogIntegrityError(
                f"canonical backlog record is not byte-canonically serialized: {path}"
            )
        return record

    def _target_file(self, locator: str | Path) -> Path:
        path = Path(locator)
        resolved = path.resolve() if path.is_absolute() else (self.project_root / path).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise EdgeBacklogIntegrityError("link target must stay inside project_root") from exc
        if not resolved.is_file():
            raise FileNotFoundError(f"link target not found: {resolved}")
        return resolved

    def _exclusive_write(self, path: Path, record: HashedRecord) -> None:
        if not bool(getattr(self._transaction_state, "exclusive", False)):
            raise EdgeBacklogIntegrityError("canonical backlog writes require an exclusive transaction")
        # Re-read and revalidate every existing canonical and configured index
        # record while the cross-process lock is still held, immediately before
        # allocating the exclusive append target.
        self.validate()
        expected_append_sequence = self._next_append_sequence()
        if record.append_sequence != expected_append_sequence:
            raise EdgeBacklogConflictError(
                "canonical append sequence became stale before exclusive write"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        data = canonical_json_bytes(record) + b"\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(path, flags, 0o644)
        except FileExistsError as exc:
            raise EdgeBacklogConflictError(f"canonical record already exists: {path}") from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_directory(path.parent)
        except Exception:
            # A failed first write is not a valid canonical record.  Removing
            # only the file created by this operation is transaction cleanup,
            # not a public deletion facility.
            path.unlink(missing_ok=True)
            raise

    def _canonical_records(self) -> list[HashedRecord]:
        records: list[HashedRecord] = []
        observations = self.root / "observations"
        if observations.is_dir():
            for object_dir in sorted(item for item in observations.iterdir() if item.is_dir()):
                records.extend(self._all_observation_revisions(object_dir.name))
        entries = self.root / "entries"
        if entries.is_dir():
            for object_dir in sorted(item for item in entries.iterdir() if item.is_dir()):
                records.extend(self._all_entry_revisions(object_dir.name))
                records.extend(self.decisions(object_dir.name))
                records.extend(self.links(object_dir.name))
        return records

    def _next_append_sequence(self) -> int:
        return len(self._canonical_records()) + 1

    def _validate_append_order(self) -> None:
        records = self._canonical_records()
        actual = sorted(item.append_sequence for item in records)
        expected = list(range(1, len(records) + 1))
        if actual != expected:
            raise EdgeBacklogIntegrityError(
                "canonical append_sequence values must be globally unique and gap-free"
            )

    def _would_create_revisit_cycle(self, entry_id: str, target_id: str) -> bool:
        graph = self._revisit_graph()
        graph.setdefault(entry_id, set()).add(target_id)
        return _graph_has_cycle(graph)

    def _validate_revisit_cycles(self) -> None:
        if _graph_has_cycle(self._revisit_graph()):
            raise EdgeBacklogIntegrityError("REVISIT_OF lineage contains a cycle")

    def _validate_duplicate_state(self, pending: EdgeBacklogDecisionV1 | None = None) -> None:
        """Validate one complete current/prospective canonicalization graph."""

        latest_decisions: dict[str, EdgeBacklogDecisionV1] = {}
        directory = self.root / "entries"
        if directory.is_dir():
            for entry_dir in sorted(item for item in directory.iterdir() if item.is_dir()):
                history = self.decisions(entry_dir.name)
                if history:
                    latest_decisions[entry_dir.name] = history[-1]
        if pending is not None:
            latest_decisions[pending.entry_id] = pending
        graph: dict[str, str] = {}
        for entry_id, decision in latest_decisions.items():
            if decision.disposition == "DUPLICATE":
                if decision.canonical_entry_id is None:
                    raise EdgeBacklogIntegrityError("DUPLICATE decision is missing canonical_entry_id")
                graph[entry_id] = decision.canonical_entry_id
        graph_sets = {source: {target} for source, target in graph.items()}
        if _graph_has_cycle(graph_sets):
            message = (
                "DUPLICATE canonicalization cycle"
                if pending is not None
                else "DUPLICATE canonicalization contains a cycle"
            )
            raise EdgeBacklogIntegrityError(message)
        if pending is not None and pending.disposition == "DUPLICATE":
            pending_target = str(pending.canonical_entry_id)
            target_decision = latest_decisions.get(pending_target)
            if target_decision is not None and target_decision.disposition == "DUPLICATE":
                raise EdgeBacklogIntegrityError("DUPLICATE canonical target is already duplicate")
        if set(graph).intersection(graph.values()):
            raise EdgeBacklogIntegrityError("DUPLICATE canonicalization multi-hop chains are not allowed")
        for target in graph.values():
            try:
                self.latest_entry(target)
            except FileNotFoundError as exc:
                raise EdgeBacklogIntegrityError("DUPLICATE canonical entry does not exist") from exc
            target_decision = latest_decisions.get(target)
            target_state = target_decision.disposition if target_decision is not None else "UNREVIEWED"
            if target_state == "REJECTED":
                raise EdgeBacklogIntegrityError("DUPLICATE canonical target is terminally rejected")
            if target_state == "DUPLICATE":
                raise EdgeBacklogIntegrityError("DUPLICATE canonical target is already duplicate")

    def _revisit_graph(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {}
        for summary in self.list_entries():
            graph.setdefault(summary["entry_id"], set())
            for link in self.links(summary["entry_id"]):
                if link.relationship == "REVISIT_OF":
                    graph[summary["entry_id"]].add(link.target_id)
        return graph


def _seal(model: type[RecordType], payload: Mapping[str, Any]) -> RecordType:
    provisional = model.model_validate(
        {**dict(payload), "record_sha256": "0" * 64},
        context={"skip_record_hash": True},
    )
    normalized = provisional.model_dump(mode="json", by_alias=True)
    normalized.pop("record_sha256", None)
    normalized["record_sha256"] = record_sha256(normalized)
    return model.model_validate(normalized)


def _revision_record_id(identifier: str, revision: int) -> str:
    return f"{identifier}.r{revision:06d}"


def _validate_revision(record_id: str, identifier: str, revision: int, previous: str | None) -> None:
    if record_id != _revision_record_id(identifier, revision):
        raise ValueError("record_id does not match object identity and revision")
    if (revision == 1) != (previous is None):
        raise ValueError("revision and previous_revision_sha256 are inconsistent")


def _without_managed_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    managed = {
        "schema",
        "record_id",
        "append_sequence",
        "revision",
        "previous_revision_sha256",
        "actor",
        "recorded_at",
        "record_sha256",
        "fingerprint_schema",
        "fingerprint_sha256",
    }
    unexpected = managed.intersection(payload)
    if unexpected:
        raise EdgeBacklogConflictError(
            "managed fields cannot be supplied by capture/revision operations: " + ", ".join(sorted(unexpected))
        )
    return dict(payload)


def _codex_actor(actor_id: str, task_id: str | None) -> ActorProvenanceV1:
    return ActorProvenanceV1(actor_class="CODEX", actor_id=actor_id, task_id=task_id)


def _generated_id(prefix: str, entry_id: str, sequence: int, recorded_at: datetime | None) -> str:
    timestamp = (recorded_at or _now()).astimezone(timezone.utc).isoformat()
    suffix = hashlib.sha256(f"{prefix}|{entry_id}|{sequence}|{timestamp}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}.{entry_id[:64]}.{sequence:06d}.{suffix}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string or datetime")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp must be valid ISO-8601") from exc


def _strip(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must be non-empty")
    return normalized


def _strip_optional(value: str | None) -> str | None:
    return None if value is None else _strip(value)


def _unique_text(values: Sequence[str], label: str) -> list[str]:
    normalized = [_strip(value) for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} entries must be distinct")
    return normalized


def _historical_candidate_projection(record: HistoricalEdgeIndexRecordV1) -> dict[str, Any]:
    return {
        "title": record.raw_title or record.campaign_id or "historical record",
        "state": record.raw_outcome or record.semantic_resolution,
        "source_path": record.source_path,
        "archive_generation": record.archive_generation,
        "source_generation": record.source_generation,
        "p1_evidence_eligibility": record.p1_evidence_eligibility,
        "derived_index_use": record.derived_index_use,
        "semantic_resolution": record.semantic_resolution,
        "historical_scientific_verdict": record.raw_scientific_verdict,
        "historical_disposition": record.raw_disposition,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def _require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EdgeBacklogError(f"invalid {label}: {value!r}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _backlog_dimension_tokens(_field: str, value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value or "")
    return duplicate_core.economic_tokens(text)


def _record_chain_sha256(records: Sequence[HashedRecord]) -> str:
    return hashlib.sha256(canonical_json_bytes([item.record_sha256 for item in records])).hexdigest()


def _historical_record_id(value: HistoricalEdgeIndexRecordV1 | Mapping[str, Any]) -> str:
    payload = value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else dict(value)
    identity_material = {
        "source_kind": payload.get("source_kind"),
        "source_path": payload.get("source_path"),
        "source_sha256": payload.get("source_sha256"),
        "source_row_number": payload.get("source_row_number"),
    }
    return "history." + hashlib.sha256(canonical_json_bytes(identity_material)).hexdigest()[:24]


def _historical_sort_key(record: HistoricalEdgeIndexRecordV1) -> tuple[str, int, str, str]:
    return (
        record.source_path,
        record.source_row_number or 0,
        record.source_kind,
        record.record_id,
    )


def _historical_universe_sha256(records: Sequence[HistoricalEdgeIndexRecordV1]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            [item.model_dump(mode="json", by_alias=True) for item in records]
        )
    ).hexdigest()


@contextmanager
def backlog_file_lock(path: str | Path, *, exclusive: bool) -> Iterator[None]:
    """Hold the repository backlog lock across processes."""

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _shared_link_targets(left: Sequence[EdgeBacklogLinkV1], right: Sequence[EdgeBacklogLinkV1]) -> list[str]:
    left_targets = {(item.target_kind, item.target_id) for item in left}
    right_targets = {(item.target_kind, item.target_id) for item in right}
    return sorted(f"{kind}:{identifier}" for kind, identifier in left_targets & right_targets)


def _lineage_related(
    left_id: str,
    right_id: str,
    left: Sequence[EdgeBacklogLinkV1],
    right: Sequence[EdgeBacklogLinkV1],
) -> bool:
    return any(item.relationship == "REVISIT_OF" and item.target_id == right_id for item in left) or any(
        item.relationship == "REVISIT_OF" and item.target_id == left_id for item in right
    )


def _assert_source_identity_compatible(
    source_id: str,
    previous: tuple[str, str, str | None],
    current: tuple[str, str, str | None],
) -> None:
    if previous[:2] != current[:2]:
        raise EdgeBacklogIntegrityError(f"source_id {source_id!r} was reused with conflicting identity")
    previous_hash, current_hash = previous[2], current[2]
    if previous_hash and current_hash != previous_hash:
        raise EdgeBacklogIntegrityError(f"source_id {source_id!r} was reused with conflicting content hash")


def _remember_source_identity(
    identities: dict[str, tuple[str, str, str | None]],
    source: EvidenceReferenceV1,
) -> None:
    identity = (source.source_kind, source.locator, source.content_sha256)
    previous = identities.get(source.source_id)
    if previous is None:
        identities[source.source_id] = identity
        return
    if previous[:2] != identity[:2]:
        raise EdgeBacklogIntegrityError(f"source_id {source.source_id!r} was reused with conflicting identity")
    if previous[2] is not None and identity[2] is not None and previous[2] != identity[2]:
        raise EdgeBacklogIntegrityError(f"source_id {source.source_id!r} was reused with conflicting content hash")
    if previous[2] is None and identity[2] is not None:
        identities[source.source_id] = identity


def _graph_has_cycle(graph: Mapping[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in graph.get(node, set()):
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


__all__ = [
    "ActorProvenanceV1",
    "EdgeBacklogAuthorityError",
    "EdgeBacklogConflictError",
    "EdgeBacklogDecisionV1",
    "EdgeBacklogEntryRevisionV1",
    "EdgeBacklogError",
    "EdgeBacklogIntegrityError",
    "EdgeBacklogLinkV1",
    "EdgeBacklogStore",
    "DuplicateCandidateV1",
    "EvidenceReferenceV1",
    "HISTORY_INDEX_SCHEMA",
    "HistoricalEdgeIndexRecordV1",
    "ObservationReferenceV1",
    "ObservationRevisionV1",
    "backlog_file_lock",
    "backlog_fingerprint",
    "canonical_json_bytes",
    "load_historical_edge_index_records",
    "record_sha256",
]
