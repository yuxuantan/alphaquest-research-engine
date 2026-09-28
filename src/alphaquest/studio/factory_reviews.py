"""Immutable human-review contracts for supervised factory proposals.

The Codex proposal schemas deliberately cannot assert human verification.  This
module adds a separate overlay which preserves the complete AI proposal while
recording what a named human actually checked.  Review artifacts remain
proposal-stage research records: they do not edit a campaign, approve strategy
mechanics, certify code, authorize testing, or promote a candidate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from alphaquest.studio.research_factory import (
    FactoryModel,
    HypothesisProposalV1,
    MechanicsIntentV1,
    SHA256_PATTERN,
    SourceEvidenceBundleV1,
    object_sha256,
)


SOURCE_METADATA_FIELDS = (
    "title",
    "authors",
    "year",
    "locator",
    "publication_type",
    "venue",
)
HYPOTHESIS_REVIEW_FIELDS = (
    "hypothesis_id",
    "edge_family_id",
    "instrument",
    "market_behavior",
    "causal_mechanism",
    "counterparty",
    "information_availability_timeline",
    "expected_holding_horizon",
    "null_hypothesis",
    "falsifying_observations",
    "confounders",
    "persistence_rationale",
    "expected_regimes",
    "transaction_cost_sensitivity",
    "capacity_assumptions",
    "required_data_fields",
    "source_bundle_sha256s",
    "source_claim_ids",
    "research_objectives_sha256",
    "unresolved_questions",
)
MECHANICS_REVIEW_FIELDS = (
    "mechanics_id",
    "hypothesis_id",
    "hypothesis_sha256",
    "variant_id",
    "execution_lane",
    "certified_strategy_id",
    "unsupported_reason",
    "signal_availability",
    "entry_state_machine",
    "entry_timing",
    "invalidation_condition",
    "stop_semantics",
    "target_and_exit_semantics",
    "session_boundaries",
    "reentry_policy",
    "position_limits",
    "required_data_fields",
    "parameters",
    "rationale",
)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("review timestamps must be timezone-aware")
    return value


def _nonblank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("review text must be non-empty")
    return normalized


def _exact_field_set(values: Sequence[str], expected: Sequence[str], *, label: str) -> list[str]:
    normalized = [_nonblank(value) for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must not contain duplicates")
    if set(normalized) != set(expected):
        missing = sorted(set(expected) - set(normalized))
        unexpected = sorted(set(normalized) - set(expected))
        raise ValueError(f"{label} is incomplete (missing={missing}, unexpected={unexpected})")
    return normalized


class SourceClaimHumanReviewV1(FactoryModel):
    """A human decision for exactly one AI-proposed source claim."""

    claim_id: str
    proposed_support: Literal["DIRECT", "CONFLICTING", "INFERENCE"]
    decision: Literal["ACCEPT", "REJECT"]
    evidence_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    verification_method: str
    notes: str

    @field_validator("claim_id", "verification_method", "notes")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @model_validator(mode="after")
    def _accepted_claim_has_captured_evidence(self) -> "SourceClaimHumanReviewV1":
        if self.decision == "ACCEPT" and self.evidence_sha256 is None:
            raise ValueError("an accepted source claim requires a captured evidence SHA-256")
        return self


class SourceEvidenceHumanVerificationV1(FactoryModel):
    """Explicit human verification required before source evidence may advance."""

    review_id: str
    reviewer: str
    reviewed_at: datetime
    decision: Literal["ACCEPT_FOR_HYPOTHESIS"] = "ACCEPT_FOR_HYPOTHESIS"
    verified_metadata_fields: list[str]
    source_identity_status: Literal["VERIFIED"] = "VERIFIED"
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    retraction_status: Literal["NOT_RETRACTED", "CORRECTED"]
    verification_method: str
    claim_reviews: list[SourceClaimHumanReviewV1] = Field(min_length=1)
    notes: str

    @field_validator("review_id", "reviewer", "verification_method", "notes")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("reviewed_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("verified_metadata_fields")
    @classmethod
    def _metadata_fields(cls, values: list[str]) -> list[str]:
        return _exact_field_set(values, SOURCE_METADATA_FIELDS, label="verified_metadata_fields")

    @model_validator(mode="after")
    def _at_least_one_supported_claim(self) -> "SourceEvidenceHumanVerificationV1":
        if not any(item.decision == "ACCEPT" for item in self.claim_reviews):
            raise ValueError("accepted source evidence requires at least one accepted claim")
        return self


class SourceFullTextCaptureBindingV1(FactoryModel):
    """Exact canonical full-text bytes selected for one source review."""

    work_id: str
    work_revision_sha256: str = Field(pattern=SHA256_PATTERN)
    source_version_id: str
    source_version_revision_sha256: str = Field(pattern=SHA256_PATTERN)
    source_version_resolution_sha256: str = Field(pattern=SHA256_PATTERN)
    source_reliability_state_sha256: str = Field(pattern=SHA256_PATTERN)
    capture_id: str
    capture_revision_sha256: str = Field(pattern=SHA256_PATTERN)
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    extracted_representation_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("work_id", "source_version_id", "capture_id")
    @classmethod
    def _identities(cls, value: str) -> str:
        return _nonblank(value)


class SourceEvidenceHumanVerificationV2(SourceEvidenceHumanVerificationV1):
    """Human source decision bound to a canonical, retained full-text capture."""

    capture_binding: SourceFullTextCaptureBindingV1

    @model_validator(mode="after")
    def _content_matches_capture(self) -> "SourceEvidenceHumanVerificationV2":
        if self.content_sha256 != self.capture_binding.content_sha256:
            raise ValueError("human verification content hash does not match the canonical capture")
        return self


class ReviewedSourceEvidenceArtifactV1(FactoryModel):
    """Complete AI source proposal plus its one-shot human verification."""

    schema_name: Literal["alphaquest.reviewed-source-evidence/v1"] = Field(
        default="alphaquest.reviewed-source-evidence/v1",
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    task_id: str
    proposal_id: str
    proposal_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    proposal_validation_sha256: str = Field(pattern=SHA256_PATTERN)
    source_evidence: SourceEvidenceBundleV1
    source_evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    human_verification: SourceEvidenceHumanVerificationV1
    campaign_mutations_performed: Literal[False] = False
    mechanics_approval_granted: Literal[False] = False
    testing_authorized: Literal[False] = False
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _integrity(self) -> "ReviewedSourceEvidenceArtifactV1":
        if self.source_evidence_sha256 != object_sha256(self.source_evidence):
            raise ValueError("source_evidence_sha256 does not match the preserved proposal")
        proposed = {item.claim_id: item for item in self.source_evidence.claims}
        reviewed = {item.claim_id: item for item in self.human_verification.claim_reviews}
        if len(reviewed) != len(self.human_verification.claim_reviews) or set(reviewed) != set(proposed):
            raise ValueError("human claim reviews must cover every proposed claim exactly once")
        for claim_id, review in reviewed.items():
            if review.proposed_support != proposed[claim_id].support:
                raise ValueError(f"claim review support is mismatched for {claim_id}")
        if self.artifact_sha256 != _artifact_sha256(self):
            raise ValueError("reviewed source artifact SHA-256 is invalid")
        return self


class ReviewedSourceEvidenceArtifactV2(FactoryModel):
    """New source review with immutable canonical full-text provenance."""

    schema_name: Literal["alphaquest.reviewed-source-evidence/v2"] = Field(
        default="alphaquest.reviewed-source-evidence/v2",
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    task_id: str
    proposal_id: str
    proposal_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    proposal_validation_sha256: str = Field(pattern=SHA256_PATTERN)
    source_evidence: SourceEvidenceBundleV1
    source_evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    human_verification: SourceEvidenceHumanVerificationV2
    campaign_mutations_performed: Literal[False] = False
    mechanics_approval_granted: Literal[False] = False
    testing_authorized: Literal[False] = False
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _integrity(self) -> "ReviewedSourceEvidenceArtifactV2":
        if self.source_evidence_sha256 != object_sha256(self.source_evidence):
            raise ValueError("source_evidence_sha256 does not match the preserved proposal")
        proposed = {item.claim_id: item for item in self.source_evidence.claims}
        reviewed = {item.claim_id: item for item in self.human_verification.claim_reviews}
        if len(reviewed) != len(self.human_verification.claim_reviews) or set(reviewed) != set(proposed):
            raise ValueError("human claim reviews must cover every proposed claim exactly once")
        for claim_id, review in reviewed.items():
            if review.proposed_support != proposed[claim_id].support:
                raise ValueError(f"claim review support is mismatched for {claim_id}")
        if self.artifact_sha256 != _artifact_sha256(self):
            raise ValueError("reviewed source artifact SHA-256 is invalid")
        return self


class HypothesisHumanAcceptanceV1(FactoryModel):
    """Human review of every substantive field in a hypothesis proposal."""

    review_id: str
    reviewer: str
    reviewed_at: datetime
    decision: Literal["ACCEPT_FOR_MECHANICS"] = "ACCEPT_FOR_MECHANICS"
    reviewed_fields: list[str]
    objective_alignment: Literal["PASS"] = "PASS"
    source_claim_alignment: Literal["PASS"] = "PASS"
    falsifiability: Literal["PASS"] = "PASS"
    information_timeline_no_lookahead: Literal["PASS"] = "PASS"
    execution_cost_awareness: Literal["PASS"] = "PASS"
    notes: str

    @field_validator("review_id", "reviewer", "notes")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("reviewed_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("reviewed_fields")
    @classmethod
    def _fields(cls, values: list[str]) -> list[str]:
        return _exact_field_set(values, HYPOTHESIS_REVIEW_FIELDS, label="reviewed_fields")


class ReviewedHypothesisArtifactV1(FactoryModel):
    """Complete hypothesis proposal accepted for non-executable mechanics design."""

    schema_name: Literal["alphaquest.reviewed-hypothesis/v1"] = Field(
        default="alphaquest.reviewed-hypothesis/v1",
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    task_id: str
    proposal_id: str
    proposal_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    proposal_validation_sha256: str = Field(pattern=SHA256_PATTERN)
    hypothesis: HypothesisProposalV1
    hypothesis_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewed_source_artifact_sha256s: list[str] = Field(min_length=1)
    human_acceptance: HypothesisHumanAcceptanceV1
    campaign_mutations_performed: Literal[False] = False
    mechanics_approval_granted: Literal[False] = False
    testing_authorized: Literal[False] = False
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("reviewed_source_artifact_sha256s")
    @classmethod
    def _hashes(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("reviewed source artifact hashes must be distinct")
        for value in values:
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("reviewed source artifact hashes must be lowercase SHA-256 values")
        return values

    @model_validator(mode="after")
    def _integrity(self) -> "ReviewedHypothesisArtifactV1":
        if self.hypothesis_sha256 != object_sha256(self.hypothesis):
            raise ValueError("hypothesis_sha256 does not match the preserved proposal")
        if self.hypothesis.edge_family_id != self.campaign_id:
            raise ValueError("reviewed hypothesis edge family must match its campaign identity")
        if self.artifact_sha256 != _artifact_sha256(self):
            raise ValueError("reviewed hypothesis artifact SHA-256 is invalid")
        return self


class EngineeringHandoffIntentHumanAcceptanceV1(FactoryModel):
    """Human confirmation that an unsupported mechanics intent needs engineering."""

    review_id: str
    reviewer: str
    reviewed_at: datetime
    decision: Literal["ACCEPT_FOR_ENGINEERING_HANDOFF"] = "ACCEPT_FOR_ENGINEERING_HANDOFF"
    reviewed_fields: list[str]
    hypothesis_alignment: Literal["PASS"] = "PASS"
    unsupported_scope_confirmed: Literal["PASS"] = "PASS"
    causal_timeline_reviewed: Literal["PASS"] = "PASS"
    notes: str

    @field_validator("review_id", "reviewer", "notes")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("reviewed_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("reviewed_fields")
    @classmethod
    def _fields(cls, values: list[str]) -> list[str]:
        return _exact_field_set(values, MECHANICS_REVIEW_FIELDS, label="reviewed_fields")


class ReviewedEngineeringHandoffIntentArtifactV1(FactoryModel):
    """Exact reviewed mechanics intent which may seed a proposal-only handoff."""

    schema_name: Literal["alphaquest.reviewed-engineering-handoff-intent/v1"] = Field(
        default="alphaquest.reviewed-engineering-handoff-intent/v1",
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    task_id: str
    proposal_id: str
    proposal_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    proposal_validation_sha256: str = Field(pattern=SHA256_PATTERN)
    mechanics_intent: MechanicsIntentV1
    mechanics_intent_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewed_hypothesis_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    human_acceptance: EngineeringHandoffIntentHumanAcceptanceV1
    campaign_mutations_performed: Literal[False] = False
    mechanics_approval_granted: Literal[False] = False
    testing_authorized: Literal[False] = False
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _integrity(self) -> "ReviewedEngineeringHandoffIntentArtifactV1":
        if self.mechanics_intent.execution_lane != "ENGINEERING_HANDOFF":
            raise ValueError("only an explicit ENGINEERING_HANDOFF intent may use this review")
        if self.mechanics_intent_sha256 != object_sha256(self.mechanics_intent):
            raise ValueError("mechanics_intent_sha256 does not match the preserved proposal")
        if self.artifact_sha256 != _artifact_sha256(self):
            raise ValueError("reviewed engineering-handoff intent SHA-256 is invalid")
        return self


def _artifact_sha256(value: FactoryModel | Mapping[str, Any]) -> str:
    payload = (
        value.model_dump(mode="json", by_alias=True)
        if isinstance(value, FactoryModel)
        else dict(value)
    )
    payload.pop("artifact_sha256", None)
    return object_sha256(payload)


def build_reviewed_source_evidence(
    *,
    campaign_id: str,
    task_id: str,
    proposal_id: str,
    proposal_payload_sha256: str,
    proposal_validation_sha256: str,
    source_evidence: SourceEvidenceBundleV1,
    human_verification: SourceEvidenceHumanVerificationV1,
) -> ReviewedSourceEvidenceArtifactV1:
    payload: dict[str, Any] = {
        "schema": "alphaquest.reviewed-source-evidence/v1",
        "campaign_id": campaign_id,
        "task_id": task_id,
        "proposal_id": proposal_id,
        "proposal_payload_sha256": proposal_payload_sha256,
        "proposal_validation_sha256": proposal_validation_sha256,
        "source_evidence": source_evidence,
        "source_evidence_sha256": object_sha256(source_evidence),
        "human_verification": human_verification,
        "campaign_mutations_performed": False,
        "mechanics_approval_granted": False,
        "testing_authorized": False,
    }
    payload["artifact_sha256"] = _artifact_sha256(payload)
    return ReviewedSourceEvidenceArtifactV1.model_validate(payload)


def build_reviewed_source_evidence_v2(
    *,
    campaign_id: str,
    task_id: str,
    proposal_id: str,
    proposal_payload_sha256: str,
    proposal_validation_sha256: str,
    source_evidence: SourceEvidenceBundleV1,
    human_verification: SourceEvidenceHumanVerificationV2,
) -> ReviewedSourceEvidenceArtifactV2:
    payload: dict[str, Any] = {
        "schema": "alphaquest.reviewed-source-evidence/v2",
        "campaign_id": campaign_id,
        "task_id": task_id,
        "proposal_id": proposal_id,
        "proposal_payload_sha256": proposal_payload_sha256,
        "proposal_validation_sha256": proposal_validation_sha256,
        "source_evidence": source_evidence,
        "source_evidence_sha256": object_sha256(source_evidence),
        "human_verification": human_verification,
        "campaign_mutations_performed": False,
        "mechanics_approval_granted": False,
        "testing_authorized": False,
    }
    payload["artifact_sha256"] = _artifact_sha256(payload)
    return ReviewedSourceEvidenceArtifactV2.model_validate(payload)


def build_reviewed_hypothesis(
    *,
    campaign_id: str,
    task_id: str,
    proposal_id: str,
    proposal_payload_sha256: str,
    proposal_validation_sha256: str,
    hypothesis: HypothesisProposalV1,
    reviewed_source_artifact_sha256s: Sequence[str],
    human_acceptance: HypothesisHumanAcceptanceV1,
) -> ReviewedHypothesisArtifactV1:
    payload: dict[str, Any] = {
        "schema": "alphaquest.reviewed-hypothesis/v1",
        "campaign_id": campaign_id,
        "task_id": task_id,
        "proposal_id": proposal_id,
        "proposal_payload_sha256": proposal_payload_sha256,
        "proposal_validation_sha256": proposal_validation_sha256,
        "hypothesis": hypothesis,
        "hypothesis_sha256": object_sha256(hypothesis),
        "reviewed_source_artifact_sha256s": list(reviewed_source_artifact_sha256s),
        "human_acceptance": human_acceptance,
        "campaign_mutations_performed": False,
        "mechanics_approval_granted": False,
        "testing_authorized": False,
    }
    payload["artifact_sha256"] = _artifact_sha256(payload)
    return ReviewedHypothesisArtifactV1.model_validate(payload)


def build_reviewed_engineering_handoff_intent(
    *,
    campaign_id: str,
    task_id: str,
    proposal_id: str,
    proposal_payload_sha256: str,
    proposal_validation_sha256: str,
    mechanics_intent: MechanicsIntentV1,
    reviewed_hypothesis_artifact_sha256: str,
    human_acceptance: EngineeringHandoffIntentHumanAcceptanceV1,
) -> ReviewedEngineeringHandoffIntentArtifactV1:
    payload: dict[str, Any] = {
        "schema": "alphaquest.reviewed-engineering-handoff-intent/v1",
        "campaign_id": campaign_id,
        "task_id": task_id,
        "proposal_id": proposal_id,
        "proposal_payload_sha256": proposal_payload_sha256,
        "proposal_validation_sha256": proposal_validation_sha256,
        "mechanics_intent": mechanics_intent,
        "mechanics_intent_sha256": object_sha256(mechanics_intent),
        "reviewed_hypothesis_artifact_sha256": reviewed_hypothesis_artifact_sha256,
        "human_acceptance": human_acceptance,
        "campaign_mutations_performed": False,
        "mechanics_approval_granted": False,
        "testing_authorized": False,
    }
    payload["artifact_sha256"] = _artifact_sha256(payload)
    return ReviewedEngineeringHandoffIntentArtifactV1.model_validate(payload)


__all__ = [
    "EngineeringHandoffIntentHumanAcceptanceV1",
    "HYPOTHESIS_REVIEW_FIELDS",
    "HypothesisHumanAcceptanceV1",
    "MECHANICS_REVIEW_FIELDS",
    "ReviewedEngineeringHandoffIntentArtifactV1",
    "ReviewedHypothesisArtifactV1",
    "ReviewedSourceEvidenceArtifactV1",
    "ReviewedSourceEvidenceArtifactV2",
    "SOURCE_METADATA_FIELDS",
    "SourceClaimHumanReviewV1",
    "SourceEvidenceHumanVerificationV1",
    "SourceEvidenceHumanVerificationV2",
    "SourceFullTextCaptureBindingV1",
    "build_reviewed_engineering_handoff_intent",
    "build_reviewed_hypothesis",
    "build_reviewed_source_evidence",
    "build_reviewed_source_evidence_v2",
]
