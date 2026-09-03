"""Canonical pre-hypothesis Edge Backlog records and append-only storage.

The backlog is a discovery control surface.  It does not admit hypotheses,
create edge families or campaigns, or carry scientific verdicts.  Canonical
JSON files are authoritative; every index or presentation built from them is
derived.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Annotated, Any, Literal, Mapping, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from alphaquest.research.storage import StorageLayout, display_path, load_storage_layout
from alphaquest.research.duplicate_matching import (
    economic_dimension_match,
    economic_tokens,
    match_band,
    token_jaccard,
)


OBSERVATION_SCHEMA = "alphaquest.edge-backlog-observation-revision/v1"
ENTRY_SCHEMA = "alphaquest.edge-backlog-entry-revision/v1"
DECISION_SCHEMA = "alphaquest.edge-backlog-decision/v1"
LINK_SCHEMA = "alphaquest.edge-backlog-link/v1"
FINGERPRINT_SCHEMA = "alphaquest.edge-backlog-fingerprint/v1"
DUPLICATE_SNAPSHOT_SCHEMA = "alphaquest.edge-backlog-duplicate-snapshot/v1"

IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,127}$"
SHA256_PATTERN = r"^[a-f0-9]{64}$"
Identifier = Annotated[str, Field(pattern=IDENTIFIER_PATTERN)]
RecordIdentifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,255}$")]
Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]
NonBlank = Annotated[str, Field(min_length=1)]

ActorClass = Literal[
    "CODEX",
    "HUMAN_OWNER_RESEARCHER",
    "ALPHAQUEST_DETERMINISTIC_ENGINE",
    "EXTERNAL_SYSTEM",
]
IntegrityLevel = Literal["HASH_BOUND", "LOCATOR_ONLY"]
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
_IDENTITY_FIELDS = (
    "instruments",
    "market_behavior",
    "causal_mechanism",
    "counterparty_transfer_rationale",
    "information_inputs",
    "information_availability",
    "expected_effect",
    "holding_horizon",
    "market_context",
)
_LINK_TARGETS: dict[str, str] = {
    "HYPOTHESIS_PROPOSAL": "HYPOTHESIS",
    "ADMITTED_HYPOTHESIS": "HYPOTHESIS",
    "EDGE_FAMILY": "EDGE_FAMILY",
    "CAMPAIGN": "CAMPAIGN",
    "REVISIT_OF": "EDGE_BACKLOG_ENTRY",
}
_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)


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
    title: NonBlank
    instruments: Annotated[list[NonBlank], Field(min_length=1)]
    market_behavior: NonBlank
    causal_mechanism: NonBlank
    counterparty_transfer_rationale: NonBlank
    information_inputs: Annotated[list[NonBlank], Field(min_length=1)]
    information_availability: NonBlank
    expected_effect: NonBlank
    holding_horizon: NonBlank
    market_context: NonBlank
    observation_refs: Annotated[list[ObservationReferenceV1], Field(min_length=1)]
    open_questions: list[NonBlank] = Field(default_factory=list)
    fingerprint_version: Literal[FINGERPRINT_SCHEMA] = FINGERPRINT_SCHEMA
    fingerprint_sha256: Sha256

    @field_validator(
        "title",
        "market_behavior",
        "causal_mechanism",
        "counterparty_transfer_rationale",
        "information_availability",
        "expected_effect",
        "holding_horizon",
        "market_context",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _strip(value)

    @field_validator("instruments", "information_inputs", "open_questions")
    @classmethod
    def normalize_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return _unique_text(values, info.field_name)

    @model_validator(mode="after")
    def validate_entry_identity(self, info: ValidationInfo) -> "EdgeBacklogEntryRevisionV1":
        _validate_revision(self.record_id, self.entry_id, self.revision, self.previous_revision_sha256)
        refs = [(item.observation_id, item.observation_revision_sha256, item.role) for item in self.observation_refs]
        if len(refs) != len(set(refs)):
            raise ValueError("observation_refs must be distinct")
        skip_fingerprint = bool(info.context and info.context.get("skip_fingerprint"))
        if not skip_fingerprint and self.fingerprint_sha256 != backlog_fingerprint(self):
            raise ValueError("fingerprint_sha256 does not match normalized economic identity")
        return self


class DuplicateCandidateV1(StrictBacklogModel):
    candidate_id: NonBlank
    candidate_kind: Literal["CANONICAL_BACKLOG_ENTRY", "DERIVED_HISTORICAL_RECORD"]
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
    source_path: str | None = None
    archive_generation: str | None = None
    evidence_eligibility: str | None = None
    semantic_resolution: str | None = None
    historical_scientific_verdict: str | None = None
    historical_disposition: str | None = None


class EdgeBacklogDecisionV1(HashedRecord):
    schema_name: Literal[DECISION_SCHEMA] = Field(
        default=DECISION_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    decision_id: Identifier
    entry_id: Identifier
    entry_revision_sha256: Sha256
    sequence: Annotated[int, Field(ge=1)]
    previous_decision_sha256: Sha256 | None = None
    disposition: Disposition
    duplicate_resolution: DuplicateResolution | None = None
    candidate_snapshot: list[DuplicateCandidateV1] = Field(default_factory=list)
    candidate_snapshot_sha256: Sha256 | None = None
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
                    self.canonical_entry_id is not None,
                    bool(self.related_edge_family_ids),
                    bool(self.revisit_conditions),
                )
            ):
                raise ValueError("RESUMED records cannot carry duplicate or revisit fields")
            return self
        if self.duplicate_resolution is None or self.candidate_snapshot_sha256 is None:
            raise ValueError("review decisions require duplicate resolution and candidate snapshot")
        candidate_core = {
            "schema": DUPLICATE_SNAPSHOT_SCHEMA,
            "entry_id": self.entry_id,
            "entry_revision_sha256": self.entry_revision_sha256,
            "candidates": [item.model_dump(mode="json") for item in self.candidate_snapshot],
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
    normalized: dict[str, Any] = {"schema": FINGERPRINT_SCHEMA}
    for field in _IDENTITY_FIELDS:
        raw = payload.get(field)
        if isinstance(raw, list):
            normalized[field] = sorted({_normalize_phrase(str(item)) for item in raw})
        else:
            normalized[field] = _normalize_phrase(str(raw or ""))
    return hashlib.sha256(canonical_json_bytes(normalized)).hexdigest()


class EdgeBacklogStore:
    """Append-only access to canonical backlog JSON records."""

    def __init__(self, project_root: str | Path = ".", *, layout: StorageLayout | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = layout or load_storage_layout(self.project_root)
        self.root = self.layout.edge_backlog_root

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

    def create_entry(
        self,
        payload: Mapping[str, Any],
        *,
        actor_id: str,
        task_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> EdgeBacklogEntryRevisionV1:
        self.validate()
        entry_id = _require_identifier(payload.get("entry_id"), "entry_id")
        if self._entry_paths(entry_id):
            raise EdgeBacklogConflictError(f"entry {entry_id!r} already exists; append a revision instead")
        return self._append_entry(
            payload,
            entry_id=entry_id,
            actor=_codex_actor(actor_id, task_id),
            recorded_at=recorded_at,
            previous=None,
        )

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
            canonical_entry_id=canonical_entry_id,
            related_edge_family_ids=related_edge_family_ids,
            reason_codes=reason_codes,
            rationale=rationale,
            revisit_conditions=revisit_conditions,
            reviewer_id=reviewer_id,
            decision_id=decision_id,
            recorded_at=recorded_at,
        )

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
            canonical_entry_id=None,
            related_edge_family_ids=(),
            reason_codes=reason_codes,
            rationale=rationale,
            revisit_conditions=(),
            reviewer_id=reviewer_id,
            decision_id=decision_id,
            recorded_at=recorded_at,
        )

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

    def latest_observation(self, observation_id: str) -> ObservationRevisionV1:
        paths = self._observation_paths(_require_identifier(observation_id, "observation_id"))
        if not paths:
            raise FileNotFoundError(f"observation not found: {observation_id}")
        return self._load_record(paths[-1], ObservationRevisionV1)

    def latest_entry(self, entry_id: str) -> EdgeBacklogEntryRevisionV1:
        paths = self._entry_paths(_require_identifier(entry_id, "entry_id"))
        if not paths:
            raise FileNotFoundError(f"edge backlog entry not found: {entry_id}")
        return self._load_record(paths[-1], EdgeBacklogEntryRevisionV1)

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

    def decision(self, entry_id: str, decision_id: str) -> EdgeBacklogDecisionV1:
        for item in self.decisions(entry_id):
            if item.decision_id == decision_id:
                return item
        raise FileNotFoundError(f"decision not found: {entry_id}/{decision_id}")

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

    def entry_state(self, entry_id: str) -> str:
        entry = self.latest_entry(entry_id)
        history = self.decisions(entry_id)
        if not history or history[-1].entry_revision_sha256 != entry.record_sha256:
            return "UNREVIEWED"
        return history[-1].disposition

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
                    "title": entry.title,
                    "instruments": entry.instruments,
                    "state": self.entry_state(entry.entry_id),
                    "fingerprint_sha256": entry.fingerprint_sha256,
                    "hypothesis_proposed": any(link.relationship == "HYPOTHESIS_PROPOSAL" for link in links),
                    "downstream_relationships": sorted({link.relationship for link in links}),
                }
            )
        return entries

    def show(self, entry_id: str) -> dict[str, Any]:
        entry = self.latest_entry(entry_id)
        return {
            "entry": entry.model_dump(mode="json", by_alias=True),
            "state": self.entry_state(entry_id),
            "decisions": [item.model_dump(mode="json", by_alias=True) for item in self.decisions(entry_id)],
            "links": [item.model_dump(mode="json", by_alias=True) for item in self.links(entry_id)],
        }

    def search(self, query: str | None = None, *, state: str | None = None) -> list[dict[str, Any]]:
        query_tokens = economic_tokens(query or "")
        rows = []
        for summary in self.list_entries():
            if state and summary["state"] != state:
                continue
            entry = self.latest_entry(summary["entry_id"])
            haystack = " ".join(
                str(value)
                for value in (
                    entry.entry_id,
                    entry.title,
                    *entry.instruments,
                    entry.market_behavior,
                    entry.causal_mechanism,
                    entry.counterparty_transfer_rationale,
                    *entry.information_inputs,
                    entry.information_availability,
                    entry.expected_effect,
                    entry.holding_horizon,
                    entry.market_context,
                )
            )
            if query_tokens and not query_tokens.intersection(economic_tokens(haystack)):
                continue
            rows.append(summary)
        return rows

    def duplicate_snapshot(self, entry_id: str) -> dict[str, Any]:
        entry = self.latest_entry(entry_id)
        candidates = [
            DuplicateCandidateV1.model_validate(item).model_dump(mode="json")
            for item in self.duplicate_candidates(entry_id)
        ]
        core = {
            "schema": DUPLICATE_SNAPSHOT_SCHEMA,
            "entry_id": entry.entry_id,
            "entry_revision_sha256": entry.record_sha256,
            "candidates": candidates,
        }
        return {**core, "snapshot_sha256": hashlib.sha256(canonical_json_bytes(core)).hexdigest()}

    def duplicate_candidates(self, entry_id: str) -> list[dict[str, Any]]:
        query = self.latest_entry(entry_id)
        query_text = _entry_text(query)
        query_tokens = economic_tokens(query_text)
        query_sources = self._entry_source_ids(query)
        query_links = self.links(query.entry_id)
        rows: list[dict[str, Any]] = []
        for summary in self.list_entries():
            if summary["entry_id"] == entry_id:
                continue
            candidate = self.latest_entry(summary["entry_id"])
            comparison = economic_dimension_match(
                _economic_payload(query),
                _economic_payload(candidate),
                fields=_IDENTITY_FIELDS,
            )
            lexical = token_jaccard(query_tokens, economic_tokens(_entry_text(candidate)))
            source_overlap = sorted(query_sources & self._entry_source_ids(candidate))
            candidate_links = self.links(candidate.entry_id)
            related_targets = _shared_link_targets(query_links, candidate_links)
            lineage = _lineage_related(query.entry_id, candidate.entry_id, query_links, candidate_links)
            exact = query.fingerprint_sha256 == candidate.fingerprint_sha256
            if not (
                exact
                or comparison["taxonomy_score"] >= 0.3
                or lexical >= 0.12
                or source_overlap
                or related_targets
                or lineage
            ):
                continue
            rows.append(
                {
                    "candidate_id": candidate.entry_id,
                    "candidate_kind": "CANONICAL_BACKLOG_ENTRY",
                    "title": candidate.title,
                    "state": summary["state"],
                    "exact_fingerprint": exact,
                    "taxonomy_score": comparison["taxonomy_score"],
                    "dimension_scores": comparison["dimension_scores"],
                    "matched_dimensions": comparison["matched_dimensions"],
                    "lexical_similarity": round(lexical, 4),
                    "source_overlap": source_overlap,
                    "shared_link_targets": related_targets,
                    "lineage_related": lineage,
                    "match_band": match_band(
                        exact=exact,
                        structured=comparison["taxonomy_score"],
                        lexical=lexical,
                    ),
                }
            )
        rows.extend(self._historical_candidates(query, query_tokens))
        return sorted(
            rows,
            key=lambda item: (
                not bool(item["exact_fingerprint"]),
                -float(item["taxonomy_score"]),
                -float(item["lexical_similarity"]),
                item["candidate_id"],
            ),
        )

    def validate(self) -> dict[str, Any]:
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
                "observation_id": observation_id,
                "revision": revision,
                "previous_revision_sha256": previous.record_sha256 if previous else None,
                "actor": actor.model_dump(mode="json"),
                "recorded_at": recorded_at or _now(),
            }
        )
        record = _seal(ObservationRevisionV1, material)
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
        if supplied_id is not None and supplied_id != entry_id:
            raise EdgeBacklogConflictError("entry revision cannot change entry_id")
        revision = 1 if previous is None else previous.revision + 1
        material = _without_managed_fields(payload)
        material.update(
            {
                "schema": ENTRY_SCHEMA,
                "record_id": _revision_record_id(entry_id, revision),
                "entry_id": entry_id,
                "revision": revision,
                "previous_revision_sha256": previous.record_sha256 if previous else None,
                "actor": actor.model_dump(mode="json"),
                "recorded_at": recorded_at or _now(),
                "fingerprint_version": FINGERPRINT_SCHEMA,
                "fingerprint_sha256": "0" * 64,
            }
        )
        draft = EdgeBacklogEntryRevisionV1.model_validate(
            {**material, "record_sha256": "0" * 64},
            context={"skip_record_hash": True, "skip_fingerprint": True},
        )
        material = draft.model_dump(mode="json", by_alias=True, exclude={"record_sha256"})
        material["fingerprint_sha256"] = backlog_fingerprint(material)
        record = _seal(EdgeBacklogEntryRevisionV1, material)
        self._validate_observation_refs(record.observation_refs)
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
            "decision_id": identifier,
            "entry_id": entry.entry_id,
            "entry_revision_sha256": entry.record_sha256,
            "sequence": sequence,
            "previous_decision_sha256": history[-1].record_sha256 if history else None,
            "disposition": disposition,
            "duplicate_resolution": duplicate_resolution,
            "candidate_snapshot": list(candidate_snapshot),
            "candidate_snapshot_sha256": candidate_snapshot_sha256,
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
        self._validate_decision_history(entry, [*history, record])
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
        history = self.links(entry.entry_id)
        sequence = len(history) + 1
        identifier = link_id or _generated_id("link", entry.entry_id, sequence, recorded_at)
        material = {
            "schema": LINK_SCHEMA,
            "record_id": identifier,
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
                if (
                    path.name != f"{expected_revision:06d}.json"
                    or record.entry_id != entry_dir.name
                    or record.revision != expected_revision
                ):
                    raise EdgeBacklogIntegrityError(f"entry path identity mismatch: {path}")
                if record.previous_revision_sha256 != (previous.record_sha256 if previous else None):
                    raise EdgeBacklogIntegrityError(f"broken entry revision chain: {path}")
                self._validate_observation_refs(record.observation_refs)
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
        revisions = {item.record_sha256: item for item in self._all_entry_revisions(entry.entry_id)}
        for expected_sequence, decision in enumerate(decisions, start=1):
            if decision.entry_id != entry.entry_id or decision.sequence != expected_sequence:
                raise EdgeBacklogIntegrityError("decision path/sequence does not match entry")
            if decision.previous_decision_sha256 != (previous.record_sha256 if previous else None):
                raise EdgeBacklogIntegrityError("broken decision hash chain")
            if decision.entry_revision_sha256 not in revisions:
                raise EdgeBacklogIntegrityError("decision references a missing entry revision")
            if previous:
                if previous.disposition in _TERMINAL_DISPOSITIONS:
                    raise EdgeBacklogIntegrityError("terminal decision has later history")
                if previous.disposition == "SUSPENDED" and decision.disposition != "RESUMED":
                    raise EdgeBacklogIntegrityError("SUSPENDED may only transition to RESUMED")
                if decision.disposition == "RESUMED" and previous.disposition != "SUSPENDED":
                    raise EdgeBacklogIntegrityError("RESUMED requires a current SUSPENDED decision")
            elif decision.disposition == "RESUMED":
                raise EdgeBacklogIntegrityError("RESUMED cannot be the first decision")
            if decision.disposition == "DUPLICATE":
                try:
                    self.latest_entry(str(decision.canonical_entry_id))
                except FileNotFoundError as exc:
                    raise EdgeBacklogIntegrityError("DUPLICATE canonical entry does not exist") from exc
            previous = decision
        if decisions:
            latest = decisions[-1]
            if latest.disposition in _TERMINAL_DISPOSITIONS and latest.entry_revision_sha256 != entry.record_sha256:
                raise EdgeBacklogIntegrityError("a terminal decision does not seal the latest entry revision")
            if latest.disposition == "SUSPENDED":
                suspended_revision = revisions[latest.entry_revision_sha256]
                if entry.revision != suspended_revision.revision:
                    raise EdgeBacklogIntegrityError("entry was revised without a human resume")

    def _validate_link_history(
        self,
        entry: EdgeBacklogEntryRevisionV1,
        links: Sequence[EdgeBacklogLinkV1],
    ) -> None:
        previous: EdgeBacklogLinkV1 | None = None
        revisions = {item.record_sha256 for item in self._all_entry_revisions(entry.entry_id)}
        for expected_sequence, link in enumerate(links, start=1):
            if link.entry_id != entry.entry_id or link.sequence != expected_sequence:
                raise EdgeBacklogIntegrityError("link path/sequence does not match entry")
            if link.previous_link_sha256 != (previous.record_sha256 if previous else None):
                raise EdgeBacklogIntegrityError("broken link hash chain")
            if link.entry_revision_sha256 not in revisions:
                raise EdgeBacklogIntegrityError("link references a missing entry revision")
            target = self._target_file(link.target_locator)
            if link.relationship == "REVISIT_OF":
                target_sha256 = self._load_record(target, EdgeBacklogEntryRevisionV1).record_sha256
                if link.authorizing_decision_id is not None:
                    try:
                        self.decision(link.target_id, link.authorizing_decision_id)
                    except FileNotFoundError as exc:
                        raise EdgeBacklogIntegrityError(
                            "REVISIT_OF authorizing decision does not exist on the prior entry"
                        ) from exc
            elif link.relationship in {"ADMITTED_HYPOTHESIS", "EDGE_FAMILY", "CAMPAIGN"}:
                raise EdgeBacklogAuthorityError(f"{link.relationship} is reserved and cannot be materialized by P2")
            else:
                target_sha256 = _file_sha256(target)
            if target_sha256 != link.target_payload_sha256:
                raise EdgeBacklogIntegrityError("link target hash does not match its locator")
            previous = link

    def _validate_source_identities(self, observations: Mapping[str, ObservationRevisionV1]) -> None:
        identities: dict[str, tuple[str, str, str | None]] = {}
        for observation_id in observations:
            for revision in self._all_observation_revisions(observation_id):
                for source in revision.evidence_refs:
                    identity = (source.source_kind, source.locator, source.content_sha256)
                    previous = identities.get(source.source_id)
                    if previous is None:
                        identities[source.source_id] = identity
                        continue
                    _assert_source_identity_compatible(source.source_id, previous, identity)
                    if previous[2] is None and identity[2] is not None:
                        identities[source.source_id] = identity

    def _validate_new_source_identities(self, record: ObservationRevisionV1) -> None:
        identities: dict[str, tuple[str, str, str | None]] = {}
        for observation_dir in sorted((self.root / "observations").glob("*")):
            if not observation_dir.is_dir():
                continue
            for revision in self._all_observation_revisions(observation_dir.name):
                for source in revision.evidence_refs:
                    identities.setdefault(
                        source.source_id,
                        (source.source_kind, source.locator, source.content_sha256),
                    )
        for source in record.evidence_refs:
            previous = identities.get(source.source_id)
            if previous is not None:
                _assert_source_identity_compatible(
                    source.source_id,
                    previous,
                    (source.source_kind, source.locator, source.content_sha256),
                )
                if previous[2] is None and source.content_sha256 is not None:
                    identities[source.source_id] = (
                        source.source_kind,
                        source.locator,
                        source.content_sha256,
                    )

    def _validate_observation_refs(self, refs: Sequence[ObservationReferenceV1]) -> None:
        for ref in refs:
            path = self.root / "observations" / ref.observation_id / "revisions"
            found = False
            for candidate in sorted(path.glob("*.json")):
                observation = self._load_record(candidate, ObservationRevisionV1)
                if observation.record_sha256 == ref.observation_revision_sha256:
                    found = True
                    break
            if not found:
                raise EdgeBacklogIntegrityError(
                    f"missing observation revision {ref.observation_id}/{ref.observation_revision_sha256}"
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
        path = self.layout.edge_backlog_history_index
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise EdgeBacklogIntegrityError(f"could not read historical backlog index: {exc}") from exc
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EdgeBacklogIntegrityError(f"invalid historical backlog index: {exc}") from exc
            raw = _historical_economic_payload(record)
            comparison = economic_dimension_match(
                _economic_payload(query),
                raw,
                fields=_IDENTITY_FIELDS,
                available_only=True,
            )
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
            lexical = token_jaccard(query_tokens, economic_tokens(history_text))
            exact = False
            legacy = record.get("legacy_fingerprint")
            if isinstance(legacy, dict):
                exact = _legacy_matches_backlog(query, legacy)
            if not (exact or comparison["taxonomy_score"] >= 0.3 or lexical >= 0.12):
                continue
            rows.append(
                {
                    "candidate_id": f"history:{str(record.get('record_sha256'))[:16]}",
                    "candidate_kind": "DERIVED_HISTORICAL_RECORD",
                    "title": record.get("raw_title") or record.get("campaign_id") or "historical record",
                    "state": record.get("raw_outcome") or record.get("semantic_resolution"),
                    "exact_fingerprint": exact,
                    "taxonomy_score": comparison["taxonomy_score"],
                    "dimension_scores": comparison["dimension_scores"],
                    "matched_dimensions": comparison["matched_dimensions"],
                    "lexical_similarity": round(lexical, 4),
                    "source_overlap": [],
                    "shared_link_targets": [],
                    "lineage_related": False,
                    "match_band": match_band(
                        exact=exact,
                        structured=comparison["taxonomy_score"],
                        lexical=lexical,
                    ),
                    "source_path": record.get("source_path"),
                    "archive_generation": record.get("archive_generation"),
                    "evidence_eligibility": record.get("evidence_eligibility"),
                    "semantic_resolution": record.get("semantic_resolution"),
                    "historical_scientific_verdict": record.get("raw_scientific_verdict"),
                    "historical_disposition": record.get("raw_disposition"),
                }
            )
        return rows

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
            return model.model_validate_json(path.read_bytes())
        except (OSError, ValueError) as exc:
            raise EdgeBacklogIntegrityError(f"invalid canonical backlog record {path}: {exc}") from exc

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

    def _would_create_revisit_cycle(self, entry_id: str, target_id: str) -> bool:
        graph = self._revisit_graph()
        graph.setdefault(entry_id, set()).add(target_id)
        return _graph_has_cycle(graph)

    def _validate_revisit_cycles(self) -> None:
        if _graph_has_cycle(self._revisit_graph()):
            raise EdgeBacklogIntegrityError("REVISIT_OF lineage contains a cycle")

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
        "revision",
        "previous_revision_sha256",
        "actor",
        "recorded_at",
        "record_sha256",
        "fingerprint_version",
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


def _normalize_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


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


def _economic_payload(value: EdgeBacklogEntryRevisionV1) -> dict[str, Any]:
    return {field: getattr(value, field) for field in _IDENTITY_FIELDS}


def _entry_text(value: EdgeBacklogEntryRevisionV1) -> str:
    payload = value.model_dump(mode="json")
    return " ".join(
        str(item)
        for field in _IDENTITY_FIELDS
        for item in (payload[field] if isinstance(payload[field], list) else [payload[field]])
    )


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


def _historical_economic_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    legacy = record.get("legacy_fingerprint")
    legacy = legacy if isinstance(legacy, dict) else {}
    return {
        "instruments": [record.get("instrument")] if record.get("instrument") else [],
        "market_behavior": legacy.get("market_behavior") or record.get("raw_edge") or "",
        "causal_mechanism": legacy.get("causal_mechanism") or record.get("raw_hypothesis") or "",
        "counterparty_transfer_rationale": record.get("raw_counterparty_transfer_rationale") or "",
        "information_inputs": legacy.get("signal_inputs") or [],
        "information_availability": record.get("raw_information_availability") or "",
        "expected_effect": record.get("raw_expected_effect") or "",
        "holding_horizon": legacy.get("holding_period") or record.get("timeframe") or "",
        "market_context": legacy.get("market_context") or "",
    }


def _legacy_matches_backlog(query: EdgeBacklogEntryRevisionV1, legacy: Mapping[str, Any]) -> bool:
    mappings = {
        "market_behavior": query.market_behavior,
        "causal_mechanism": query.causal_mechanism,
        "signal_inputs": query.information_inputs,
        "market_context": query.market_context,
        "holding_period": query.holding_horizon,
    }
    for field, current in mappings.items():
        historical = legacy.get(field)
        if historical is None:
            return False
        left = economic_tokens(" ".join(current) if isinstance(current, list) else str(current))
        right = economic_tokens(" ".join(historical) if isinstance(historical, list) else str(historical))
        if left != right:
            return False
    return True


def _assert_source_identity_compatible(
    source_id: str,
    previous: tuple[str, str, str | None],
    current: tuple[str, str, str | None],
) -> None:
    if previous[:2] != current[:2]:
        raise EdgeBacklogIntegrityError(f"source_id {source_id!r} was reused with conflicting identity")
    previous_hash, current_hash = previous[2], current[2]
    if previous_hash and current_hash and previous_hash != current_hash:
        raise EdgeBacklogIntegrityError(f"source_id {source_id!r} was reused with conflicting content hash")


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
    "EvidenceReferenceV1",
    "ObservationReferenceV1",
    "ObservationRevisionV1",
    "backlog_fingerprint",
    "canonical_json_bytes",
    "record_sha256",
]
