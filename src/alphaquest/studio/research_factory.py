"""Fail-closed domain contracts for a supervised local research factory.

This module deliberately contains no subprocess, network, campaign publication,
approval, or evidence-writing code.  Codex output is untrusted proposal material;
the deterministic AlphaQuest controller owns workflow transitions, freshness,
information-access accounting, budgets, and the scientific verdict branch.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


SHA256_PATTERN = r"^[0-9a-f]{64}$"
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
VARIANT_PATTERN = r"^v[0-9]{2}$"


class ResearchFactoryError(RuntimeError):
    """Base class for deterministic research-factory failures."""


class InvalidFactoryTransitionError(ResearchFactoryError):
    """A controller attempted a state transition not present in policy."""


class StaleProposalError(ResearchFactoryError):
    """A Codex proposal no longer matches its immutable task inputs."""


class InvalidProposalError(ResearchFactoryError):
    """A Codex proposal failed its declared strict output contract."""


class BudgetExceededError(ResearchFactoryError):
    """A proposed research action exceeds a predeclared research budget."""


class FactoryModel(BaseModel):
    """Strict immutable base for research-factory documents."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
    )


def _nonblank(value: str, *, label: str = "value") -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value


def _nonblank_items(values: Sequence[str], *, label: str) -> list[str]:
    normalized = [_nonblank(str(value), label=f"{label} item") for value in values]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} entries must be distinct")
    return normalized


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        # Match Pydantic's JSON-mode UTC representation so a document hashes
        # identically immediately before and after strict model validation.
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True)
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole canonical encoding used by the factory contracts."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")


def object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class SourceClaimV1(FactoryModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_id: str = Field(pattern=IDENTIFIER_PATTERN)
    statement: str = Field(min_length=20)
    source_location: str = Field(min_length=1)
    support: Literal["DIRECT", "CONFLICTING", "INFERENCE"]
    evidence_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)

    @field_validator("statement", "source_location")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)


class SourceEvidenceBundleV1(FactoryModel):
    """Verified source identity plus claim-level support; never a campaign."""

    schema_name: Literal["alphaquest.source-evidence-bundle/v1"] = Field(
        default="alphaquest.source-evidence-bundle/v1",
        alias="schema",
        serialization_alias="schema",
    )
    bundle_id: str = Field(pattern=IDENTIFIER_PATTERN)
    title: str = Field(min_length=3)
    authors: list[str] = Field(min_length=1)
    year: int = Field(ge=1800, le=2100)
    locator: str = Field(min_length=4)
    publication_type: Literal[
        "PEER_REVIEWED",
        "WORKING_PAPER",
        "EXCHANGE_RESEARCH",
        "PRACTITIONER_RESEARCH",
        "PRIMARY_DATA_DOCUMENTATION",
        "OTHER",
    ]
    venue: str | None
    retrieved_at: datetime
    content_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    verification_status: Literal["PARTIAL", "REJECTED"]
    retraction_status: Literal["NOT_RETRACTED", "RETRACTED", "CORRECTED", "UNKNOWN"]
    claims: list[SourceClaimV1] = Field(min_length=1)
    conflicting_evidence: list[str]
    inference_notes: list[str]
    created_by: str = Field(min_length=1)
    confirmed: Literal[False] = False

    @field_validator("title", "locator", "created_by")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("authors", "conflicting_evidence", "inference_notes")
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)

    @field_validator("retrieved_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _claim_integrity(self) -> "SourceEvidenceBundleV1":
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("source claim identifiers must be distinct")
        if self.verification_status == "PARTIAL" and self.content_sha256 is not None:
            raise ValueError(
                "an AI source proposal cannot assert a verified content hash; deterministic capture is required"
            )
        if self.verification_status == "PARTIAL" and self.retraction_status != "UNKNOWN":
            raise ValueError(
                "an AI source proposal must leave retraction status UNKNOWN until independently checked"
            )
        if self.retraction_status == "RETRACTED" and self.verification_status != "REJECTED":
            raise ValueError("a retracted source must be rejected")
        return self


class HypothesisProposalV1(FactoryModel):
    """Falsifiable economic hypothesis frozen before mechanics selection."""

    schema_name: Literal["alphaquest.hypothesis-proposal/v1"] = Field(
        default="alphaquest.hypothesis-proposal/v1",
        alias="schema",
        serialization_alias="schema",
    )
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    edge_family_id: str = Field(pattern=IDENTIFIER_PATTERN)
    instrument: str = Field(min_length=1)
    market_behavior: str = Field(min_length=20)
    causal_mechanism: str = Field(min_length=20)
    counterparty: str = Field(min_length=10)
    information_availability_timeline: list[str] = Field(min_length=1)
    expected_holding_horizon: str = Field(min_length=3)
    null_hypothesis: str = Field(min_length=20)
    falsifying_observations: list[str] = Field(min_length=1)
    confounders: list[str] = Field(min_length=1)
    persistence_rationale: str = Field(min_length=20)
    expected_regimes: list[str] = Field(min_length=1)
    transaction_cost_sensitivity: str = Field(min_length=10)
    capacity_assumptions: str = Field(min_length=10)
    required_data_fields: list[str] = Field(min_length=1)
    source_bundle_sha256s: list[str] = Field(min_length=1)
    source_claim_ids: list[str] = Field(min_length=1)
    research_objectives_sha256: str = Field(pattern=SHA256_PATTERN)
    unresolved_questions: list[str]
    status: Literal["PROPOSAL"] = "PROPOSAL"
    confirmed: Literal[False] = False

    @field_validator(
        "instrument",
        "market_behavior",
        "causal_mechanism",
        "counterparty",
        "expected_holding_horizon",
        "null_hypothesis",
        "persistence_rationale",
        "transaction_cost_sensitivity",
        "capacity_assumptions",
    )
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator(
        "information_availability_timeline",
        "falsifying_observations",
        "confounders",
        "expected_regimes",
        "required_data_fields",
        "source_bundle_sha256s",
        "source_claim_ids",
        "unresolved_questions",
    )
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        normalized = _nonblank_items(values, label=info.field_name)
        if info.field_name == "source_bundle_sha256s":
            for value in normalized:
                if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                    raise ValueError("source_bundle_sha256s entries must be lowercase SHA-256 values")
        return normalized


class ParameterIntentV1(FactoryModel):
    parameter_id: str = Field(pattern=IDENTIFIER_PATTERN)
    methodology_category: Literal["entry", "sl", "tp"]
    reviewed_default: bool | int | float | str
    candidate_values: list[bool | int | float | str] = Field(min_length=1)
    tunable: bool
    rationale: str = Field(min_length=10)

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str) -> str:
        return _nonblank(value)

    @model_validator(mode="after")
    def _default_is_predeclared(self) -> "ParameterIntentV1":
        candidates = [canonical_json_bytes(value) for value in self.candidate_values]
        if len(set(candidates)) != len(candidates):
            raise ValueError("candidate parameter values must be distinct")
        if canonical_json_bytes(self.reviewed_default) not in candidates:
            raise ValueError("the reviewed default must be present in candidate_values")
        if not self.tunable and len(self.candidate_values) != 1:
            raise ValueError("a fixed parameter must contain only its reviewed default")
        return self


class MechanicsIntentV1(FactoryModel):
    """Non-executable strategy intent constrained to an approved action space."""

    schema_name: Literal["alphaquest.mechanics-intent/v1"] = Field(
        default="alphaquest.mechanics-intent/v1",
        alias="schema",
        serialization_alias="schema",
    )
    mechanics_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_sha256: str = Field(pattern=SHA256_PATTERN)
    variant_id: str = Field(pattern=VARIANT_PATTERN)
    execution_lane: Literal[
        "CERTIFIED_RECIPE",
        "SAFE_COMPLETED_BAR_RULE",
        "CERTIFIED_EVENT_PACKAGE",
        "ENGINEERING_HANDOFF",
    ]
    certified_strategy_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    unsupported_reason: str | None
    signal_availability: str = Field(min_length=10)
    entry_state_machine: list[str] = Field(min_length=1)
    entry_timing: str = Field(min_length=10)
    invalidation_condition: str = Field(min_length=10)
    stop_semantics: str = Field(min_length=10)
    target_and_exit_semantics: str = Field(min_length=10)
    session_boundaries: str = Field(min_length=10)
    reentry_policy: str = Field(min_length=10)
    position_limits: str = Field(min_length=10)
    required_data_fields: list[str] = Field(min_length=1)
    parameters: list[ParameterIntentV1]
    rationale: str = Field(min_length=20)
    status: Literal["PROPOSAL"] = "PROPOSAL"
    confirmed: Literal[False] = False

    @field_validator(
        "signal_availability",
        "entry_timing",
        "invalidation_condition",
        "stop_semantics",
        "target_and_exit_semantics",
        "session_boundaries",
        "reentry_policy",
        "position_limits",
        "rationale",
    )
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("entry_state_machine", "required_data_fields")
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)

    @model_validator(mode="after")
    def _certified_action_space(self) -> "MechanicsIntentV1":
        if self.execution_lane in {"CERTIFIED_RECIPE", "CERTIFIED_EVENT_PACKAGE"}:
            if self.certified_strategy_id is None:
                raise ValueError("a certified execution lane requires certified_strategy_id")
            if self.unsupported_reason is not None:
                raise ValueError("a certified execution lane cannot declare unsupported_reason")
        elif self.execution_lane == "ENGINEERING_HANDOFF":
            if self.certified_strategy_id is not None:
                raise ValueError("an engineering handoff cannot claim a certified strategy")
            if self.unsupported_reason is None or not self.unsupported_reason.strip():
                raise ValueError("an engineering handoff requires unsupported_reason")
        elif self.certified_strategy_id is not None or self.unsupported_reason is not None:
            raise ValueError("a safe completed-bar rule cannot claim a certification or unsupported mechanic")

        parameter_ids = [parameter.parameter_id for parameter in self.parameters]
        if len(set(parameter_ids)) != len(parameter_ids):
            raise ValueError("mechanics parameters must have distinct identifiers")
        tunable = [parameter for parameter in self.parameters if parameter.tunable]
        limits = {"entry": 2, "sl": 1, "tp": 1}
        for category, limit in limits.items():
            if sum(parameter.methodology_category == category for parameter in tunable) > limit:
                raise ValueError(f"tunable {category} parameter budget exceeds {limit}")
        combinations = 1
        for parameter in tunable:
            combinations *= len(parameter.candidate_values)
        if tunable and not 8 <= combinations <= 120:
            raise ValueError("a tunable mechanics proposal must declare 8 to 120 combinations")
        return self


class EngineeringHandoffProposalV1(FactoryModel):
    schema_name: Literal["alphaquest.engineering-handoff-proposal/v1"] = Field(
        default="alphaquest.engineering-handoff-proposal/v1",
        alias="schema",
        serialization_alias="schema",
    )
    handoff_id: str = Field(pattern=IDENTIFIER_PATTERN)
    campaign_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypothesis_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewed_hypothesis_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    mechanics_intent_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewed_mechanics_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    proposed_variant_id: str = Field(pattern=VARIANT_PATTERN)
    reason_unsupported: str = Field(min_length=20)
    causal_timeline: list[str] = Field(min_length=1)
    required_data_granularity: str = Field(min_length=3)
    fill_and_ambiguity_rules: list[str] = Field(min_length=1)
    required_module_contract: list[str] = Field(min_length=1)
    required_tests: list[str] = Field(min_length=1)
    proposed_mechanic: str = Field(min_length=20)
    status: Literal["NEEDS MANUAL REVIEW"] = "NEEDS MANUAL REVIEW"
    confirmed: Literal[False] = False

    @field_validator("reason_unsupported", "required_data_granularity", "proposed_mechanic")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator(
        "causal_timeline",
        "fill_and_ambiguity_rules",
        "required_module_contract",
        "required_tests",
    )
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)


class StageKind(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    WFA_IN_SAMPLE = "WFA_IN_SAMPLE"
    WFA_OOS = "WFA_OOS"
    LOCKED_HOLDOUT = "LOCKED_HOLDOUT"
    STRESS = "STRESS"
    FINAL_ACCEPTANCE = "FINAL_ACCEPTANCE"
    FORWARD = "FORWARD"
    ACCOUNT_ASSESSMENT = "ACCOUNT_ASSESSMENT"
    UNKNOWN = "UNKNOWN"


class CriterionOutcomeV1(FactoryModel):
    criterion_id: str = Field(pattern=IDENTIFIER_PATTERN)
    metric: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    passed: bool
    actual: float | int | str | None
    threshold: float | int | str | None
    comparator: str | None
    evidence_ref: str = Field(min_length=1)
    near_threshold: bool = False

    @field_validator("metric", "stage", "evidence_ref")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)


class ResultSummaryV1(FactoryModel):
    schema_name: Literal["alphaquest.factory-result-summary/v1"] = Field(
        default="alphaquest.factory-result-summary/v1",
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str = Field(pattern=IDENTIFIER_PATTERN)
    variant_id: str = Field(pattern=VARIANT_PATTERN)
    result_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    failed_stage: str | None
    stage_kind: StageKind
    criteria: list[CriterionOutcomeV1]
    data_quality_issues: list[str]
    mechanics_issues: list[str]
    operational_issues: list[str]
    pnl_generated: bool

    @field_validator("data_quality_issues", "mechanics_issues", "operational_issues")
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)

    @model_validator(mode="after")
    def _verdict_consistency(self) -> "ResultSummaryV1":
        failed = [criterion for criterion in self.criteria if not criterion.passed]
        if self.verdict == "PASS" and (failed or self.failed_stage is not None):
            raise ValueError("PASS cannot contain a failed stage or failed criterion")
        if self.verdict == "FAIL" and not failed:
            raise ValueError("FAIL requires at least one failed criterion")
        return self


class FailureClass(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DATA_QUALITY = "DATA_QUALITY"
    MECHANICS_DEFECT = "MECHANICS_DEFECT"
    EDGE_ABSENT = "EDGE_ABSENT"
    COST_SENSITIVE = "COST_SENSITIVE"
    TRADE_DENSITY = "TRADE_DENSITY"
    PARAMETER_INSTABILITY = "PARAMETER_INSTABILITY"
    WFA_INSTABILITY = "WFA_INSTABILITY"
    REGIME_DEPENDENCE = "REGIME_DEPENDENCE"
    TAIL_RISK = "TAIL_RISK"
    ACCOUNT_UNSUITABLE = "ACCOUNT_UNSUITABLE"


class FailureDiagnosisV1(FactoryModel):
    schema_name: Literal["alphaquest.failure-diagnosis/v1"] = Field(
        default="alphaquest.failure-diagnosis/v1",
        alias="schema",
        serialization_alias="schema",
    )
    diagnosis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    campaign_id: str = Field(pattern=IDENTIFIER_PATTERN)
    variant_id: str = Field(pattern=VARIANT_PATTERN)
    result_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    failed_stage: str | None
    stage_kind: StageKind
    classifications: list[FailureClass]
    failed_criteria: list[CriterionOutcomeV1]
    near_failed_criteria: list[CriterionOutcomeV1]
    evidence_refs: list[str]
    competing_diagnoses: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    deterministic: Literal[True] = True
    human_approval_required: Literal[True] = True

    @field_validator("evidence_refs", "competing_diagnoses")
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)

    @model_validator(mode="after")
    def _verdict_classes(self) -> "FailureDiagnosisV1":
        if self.verdict == "PASS" and (self.classifications or self.failed_criteria):
            raise ValueError("PASS cannot contain failure classifications")
        if self.verdict != "PASS" and not self.classifications:
            raise ValueError("a non-PASS diagnosis requires at least one classification")
        return self


_FAILURE_KEYWORDS: tuple[tuple[FailureClass, tuple[str, ...]], ...] = (
    (FailureClass.COST_SENSITIVE, ("cost", "slippage", "commission", "net_after_cost")),
    (FailureClass.TRADE_DENSITY, ("trade_count", "trades_per", "density", "sample_size")),
    (FailureClass.PARAMETER_INSTABILITY, ("parameter", "neighbour", "neighbor", "plateau")),
    (FailureClass.WFA_INSTABILITY, ("walk_forward", "wfa", "stitched_oos", "oos_stability")),
    (FailureClass.REGIME_DEPENDENCE, ("regime", "yearly", "monthly", "session_breakdown")),
    (
        FailureClass.TAIL_RISK,
        ("drawdown", "mar", "ruin", "breach", "losing_streak", "tail", "largest_winner"),
    ),
    (FailureClass.ACCOUNT_UNSUITABLE, ("account", "destination", "prop_rule", "daily_loss")),
)


def classify_result_failure(
    summary: ResultSummaryV1,
    *,
    diagnosis_id: str,
) -> FailureDiagnosisV1:
    """Classify a strict result summary without model interpretation or mutation."""

    failed = [criterion for criterion in summary.criteria if not criterion.passed]
    near = [criterion for criterion in summary.criteria if criterion.passed and criterion.near_threshold]
    classifications: list[FailureClass] = []
    if summary.verdict == "NEEDS MANUAL REVIEW":
        if summary.data_quality_issues:
            classifications.append(FailureClass.DATA_QUALITY)
        if summary.mechanics_issues:
            classifications.append(FailureClass.MECHANICS_DEFECT)
        if not classifications:
            classifications.append(FailureClass.INSUFFICIENT_EVIDENCE)
    elif summary.verdict == "FAIL":
        searchable = " ".join(
            f"{criterion.metric} {criterion.criterion_id} {criterion.stage}".casefold()
            for criterion in failed
        )
        for classification, tokens in _FAILURE_KEYWORDS:
            if any(token in searchable for token in tokens):
                classifications.append(classification)
        if not classifications:
            classifications.append(FailureClass.EDGE_ABSENT)

    evidence_refs = [criterion.evidence_ref for criterion in failed + near]
    evidence_refs.extend(summary.data_quality_issues)
    evidence_refs.extend(summary.mechanics_issues)
    evidence_refs.extend(summary.operational_issues)
    evidence_refs = list(dict.fromkeys(evidence_refs))
    confidence = 1.0 if summary.verdict == "PASS" else (0.9 if failed else 0.75)
    return FailureDiagnosisV1(
        diagnosis_id=diagnosis_id,
        campaign_id=summary.campaign_id,
        variant_id=summary.variant_id,
        result_bundle_sha256=summary.result_bundle_sha256,
        verdict=summary.verdict,
        failed_stage=summary.failed_stage,
        stage_kind=summary.stage_kind,
        classifications=classifications,
        failed_criteria=failed,
        near_failed_criteria=near,
        evidence_refs=evidence_refs,
        competing_diagnoses=[],
        confidence=confidence,
    )


class NextAction(str, Enum):
    REPAIR_SAME_VARIANT = "REPAIR_SAME_VARIANT"
    OBTAIN_MANUAL_REVIEW = "OBTAIN_MANUAL_REVIEW"
    ABANDON_EDGE = "ABANDON_EDGE"
    PROPOSE_SUCCESSOR = "PROPOSE_SUCCESSOR"
    START_NEW_RESEARCH_GENERATION = "START_NEW_RESEARCH_GENERATION"
    ASSESS_OTHER_DESTINATION = "ASSESS_OTHER_DESTINATION"
    BEGIN_CANDIDATE_REVIEW = "BEGIN_CANDIDATE_REVIEW"
    BEGIN_FORWARD_INCUBATION = "BEGIN_FORWARD_INCUBATION"
    STOP_NO_FRESH_HOLDOUT = "STOP_NO_FRESH_HOLDOUT"


class RankedNextActionV1(FactoryModel):
    rank: int = Field(ge=1)
    action: NextAction
    rationale: str = Field(min_length=30)
    evidence_refs: list[str] = Field(min_length=1)
    expected_information_gain: str = Field(min_length=20)

    @field_validator("rationale", "expected_information_gain")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("evidence_refs")
    @classmethod
    def _evidence(cls, values: list[str]) -> list[str]:
        return _nonblank_items(values, label="evidence_refs")


class NextActionRankingProposalV1(FactoryModel):
    """Unconfirmed ranking over controller-approved actions only.

    This proposal deliberately carries no successor mechanics.  A later
    ``NextExperimentProposalV1`` remains the hash-bound artifact that may name
    successor mechanics after human review and a separate mechanics proposal.
    """

    schema_name: Literal["alphaquest.next-action-ranking-proposal/v1"] = Field(
        default="alphaquest.next-action-ranking-proposal/v1",
        alias="schema",
        serialization_alias="schema",
    )
    proposal_id: str = Field(pattern=IDENTIFIER_PATTERN)
    eligibility_sha256: str = Field(pattern=SHA256_PATTERN)
    diagnosis_sha256: str = Field(pattern=SHA256_PATTERN)
    predecessor_result_sha256: str = Field(pattern=SHA256_PATTERN)
    predecessor_verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    recommendations: list[RankedNextActionV1] = Field(min_length=1)
    confirmed: Literal[False] = False

    @model_validator(mode="after")
    def _ordered_unique(self) -> "NextActionRankingProposalV1":
        ranks = [item.rank for item in self.recommendations]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("next-action recommendations must use contiguous rank order starting at one")
        actions = [item.action for item in self.recommendations]
        if len(actions) != len(set(actions)):
            raise ValueError("next-action recommendations must be unique")
        return self


class NextExperimentProposalV1(FactoryModel):
    schema_name: Literal["alphaquest.next-experiment-proposal/v1"] = Field(
        default="alphaquest.next-experiment-proposal/v1",
        alias="schema",
        serialization_alias="schema",
    )
    proposal_id: str = Field(pattern=IDENTIFIER_PATTERN)
    diagnosis_sha256: str = Field(pattern=SHA256_PATTERN)
    predecessor_result_sha256: str = Field(pattern=SHA256_PATTERN)
    predecessor_verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    action: NextAction
    rationale: str = Field(min_length=30)
    evidence_refs: list[str] = Field(min_length=1)
    expected_information_gain: str = Field(min_length=20)
    proposed_variant_id: str | None = Field(default=None, pattern=VARIANT_PATTERN)
    mechanics_intent_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    fresh_confirmation_window_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    status: Literal["PROPOSAL"] = "PROPOSAL"
    confirmed: Literal[False] = False

    @field_validator("rationale", "expected_information_gain")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("evidence_refs")
    @classmethod
    def _evidence(cls, values: list[str]) -> list[str]:
        return _nonblank_items(values, label="evidence_refs")

    @model_validator(mode="after")
    def _branch_policy(self) -> "NextExperimentProposalV1":
        allowed = {
            "PASS": {NextAction.BEGIN_CANDIDATE_REVIEW, NextAction.ASSESS_OTHER_DESTINATION},
            "NEEDS MANUAL REVIEW": {NextAction.OBTAIN_MANUAL_REVIEW, NextAction.REPAIR_SAME_VARIANT},
            "FAIL": {
                NextAction.ABANDON_EDGE,
                NextAction.PROPOSE_SUCCESSOR,
                NextAction.START_NEW_RESEARCH_GENERATION,
                NextAction.ASSESS_OTHER_DESTINATION,
                NextAction.STOP_NO_FRESH_HOLDOUT,
            },
        }
        if self.action not in allowed[self.predecessor_verdict]:
            raise ValueError(f"{self.action.value} is not legal after {self.predecessor_verdict}")
        if self.action == NextAction.PROPOSE_SUCCESSOR:
            if self.proposed_variant_id is None or self.mechanics_intent_sha256 is None:
                raise ValueError("a successor proposal requires a variant and mechanics-intent hash")
        elif self.proposed_variant_id is not None or self.mechanics_intent_sha256 is not None:
            raise ValueError("variant mechanics fields are reserved for PROPOSE_SUCCESSOR")
        if self.action == NextAction.START_NEW_RESEARCH_GENERATION:
            if self.fresh_confirmation_window_id is None:
                raise ValueError("a new research generation requires a fresh confirmation window")
        elif self.fresh_confirmation_window_id is not None:
            raise ValueError("fresh_confirmation_window_id is reserved for a new research generation")
        return self


class CandidateDueDiligenceSummaryV1(FactoryModel):
    schema_name: Literal["alphaquest.candidate-due-diligence-summary/v1"] = Field(
        default="alphaquest.candidate-due-diligence-summary/v1",
        alias="schema",
        serialization_alias="schema",
    )
    summary_id: str = Field(pattern=IDENTIFIER_PATTERN)
    campaign_id: str = Field(pattern=IDENTIFIER_PATTERN)
    variant_id: str = Field(pattern=VARIANT_PATTERN)
    result_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    mechanics_approval_sha256: str = Field(pattern=SHA256_PATTERN)
    scientific_verdict: Literal["PASS"] = "PASS"
    robustness_evidence: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    unresolved_risks: list[str] = Field(min_length=1)
    forward_requirements: list[str] = Field(min_length=1)
    recommendation: Literal["ELIGIBLE_FOR_HUMAN_REVIEW", "REJECT"]
    automatic_deployment_permitted: Literal[False] = False
    human_approval_required: Literal[True] = True

    @field_validator("robustness_evidence", "limitations", "unresolved_risks", "forward_requirements")
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)


class FactoryState(str, Enum):
    READY_FOR_RESEARCH = "READY_FOR_RESEARCH"
    CODEX_TASK_PREPARED = "CODEX_TASK_PREPARED"
    WAITING_FOR_CODEX = "WAITING_FOR_CODEX"
    CODEX_RUNNING = "CODEX_RUNNING"
    PROPOSAL_READY = "PROPOSAL_READY"
    PROPOSAL_INVALID = "PROPOSAL_INVALID"
    WAITING_FOR_RESEARCH_APPROVAL = "WAITING_FOR_RESEARCH_APPROVAL"
    WAITING_FOR_MECHANICS_APPROVAL = "WAITING_FOR_MECHANICS_APPROVAL"
    READY_FOR_TESTING = "READY_FOR_TESTING"
    TESTING = "TESTING"
    RESULT_READY_FOR_DIAGNOSIS = "RESULT_READY_FOR_DIAGNOSIS"
    NEXT_ACTION_READY = "NEXT_ACTION_READY"
    TERMINAL_PASS = "TERMINAL_PASS"
    TERMINAL_FAIL = "TERMINAL_FAIL"
    NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"


class FactoryEvent(str, Enum):
    PREPARE_CODEX_TASK = "PREPARE_CODEX_TASK"
    QUEUE_CODEX = "QUEUE_CODEX"
    START_CODEX = "START_CODEX"
    CODEX_UNAVAILABLE = "CODEX_UNAVAILABLE"
    ACCEPT_CODEX_OUTPUT = "ACCEPT_CODEX_OUTPUT"
    REJECT_CODEX_OUTPUT = "REJECT_CODEX_OUTPUT"
    RETRY_INVALID_PROPOSAL = "RETRY_INVALID_PROPOSAL"
    ROUTE_RESEARCH_REVIEW = "ROUTE_RESEARCH_REVIEW"
    APPROVE_RESEARCH = "APPROVE_RESEARCH"
    REVISE_RESEARCH = "REVISE_RESEARCH"
    ROUTE_MECHANICS_REVIEW = "ROUTE_MECHANICS_REVIEW"
    APPROVE_MECHANICS = "APPROVE_MECHANICS"
    REJECT_MECHANICS = "REJECT_MECHANICS"
    START_TESTING = "START_TESTING"
    RECORD_RESULT = "RECORD_RESULT"
    RECORD_UNREVIEWABLE_RESULT = "RECORD_UNREVIEWABLE_RESULT"
    ROUTE_NEXT_ACTION = "ROUTE_NEXT_ACTION"
    PROMOTE_PASS = "PROMOTE_PASS"
    ABANDON_FAIL = "ABANDON_FAIL"
    PREPARE_SUCCESSOR = "PREPARE_SUCCESSOR"
    REQUIRE_MANUAL_REVIEW = "REQUIRE_MANUAL_REVIEW"


LEGAL_FACTORY_TRANSITIONS: dict[tuple[FactoryState, FactoryEvent], FactoryState] = {
    (FactoryState.READY_FOR_RESEARCH, FactoryEvent.PREPARE_CODEX_TASK): FactoryState.CODEX_TASK_PREPARED,
    (FactoryState.CODEX_TASK_PREPARED, FactoryEvent.QUEUE_CODEX): FactoryState.WAITING_FOR_CODEX,
    (FactoryState.WAITING_FOR_CODEX, FactoryEvent.START_CODEX): FactoryState.CODEX_RUNNING,
    (FactoryState.CODEX_RUNNING, FactoryEvent.CODEX_UNAVAILABLE): FactoryState.WAITING_FOR_CODEX,
    (FactoryState.CODEX_RUNNING, FactoryEvent.ACCEPT_CODEX_OUTPUT): FactoryState.PROPOSAL_READY,
    (FactoryState.CODEX_RUNNING, FactoryEvent.REJECT_CODEX_OUTPUT): FactoryState.PROPOSAL_INVALID,
    (FactoryState.PROPOSAL_INVALID, FactoryEvent.RETRY_INVALID_PROPOSAL): FactoryState.CODEX_TASK_PREPARED,
    (FactoryState.PROPOSAL_READY, FactoryEvent.ROUTE_RESEARCH_REVIEW): FactoryState.WAITING_FOR_RESEARCH_APPROVAL,
    (FactoryState.WAITING_FOR_RESEARCH_APPROVAL, FactoryEvent.APPROVE_RESEARCH): FactoryState.READY_FOR_RESEARCH,
    (FactoryState.WAITING_FOR_RESEARCH_APPROVAL, FactoryEvent.REVISE_RESEARCH): FactoryState.READY_FOR_RESEARCH,
    (FactoryState.PROPOSAL_READY, FactoryEvent.ROUTE_MECHANICS_REVIEW): FactoryState.WAITING_FOR_MECHANICS_APPROVAL,
    (FactoryState.WAITING_FOR_MECHANICS_APPROVAL, FactoryEvent.APPROVE_MECHANICS): FactoryState.READY_FOR_TESTING,
    (FactoryState.WAITING_FOR_MECHANICS_APPROVAL, FactoryEvent.REJECT_MECHANICS): FactoryState.NEEDS_MANUAL_REVIEW,
    (FactoryState.READY_FOR_TESTING, FactoryEvent.START_TESTING): FactoryState.TESTING,
    (FactoryState.TESTING, FactoryEvent.RECORD_RESULT): FactoryState.RESULT_READY_FOR_DIAGNOSIS,
    (FactoryState.TESTING, FactoryEvent.RECORD_UNREVIEWABLE_RESULT): FactoryState.NEEDS_MANUAL_REVIEW,
    (FactoryState.RESULT_READY_FOR_DIAGNOSIS, FactoryEvent.PREPARE_CODEX_TASK): FactoryState.CODEX_TASK_PREPARED,
    (FactoryState.PROPOSAL_READY, FactoryEvent.ROUTE_NEXT_ACTION): FactoryState.NEXT_ACTION_READY,
    (FactoryState.NEXT_ACTION_READY, FactoryEvent.PROMOTE_PASS): FactoryState.TERMINAL_PASS,
    (FactoryState.NEXT_ACTION_READY, FactoryEvent.ABANDON_FAIL): FactoryState.TERMINAL_FAIL,
    (FactoryState.NEXT_ACTION_READY, FactoryEvent.PREPARE_SUCCESSOR): FactoryState.READY_FOR_RESEARCH,
}

for _state in FactoryState:
    if _state not in {FactoryState.TERMINAL_PASS, FactoryState.TERMINAL_FAIL, FactoryState.NEEDS_MANUAL_REVIEW}:
        LEGAL_FACTORY_TRANSITIONS.setdefault(
            (_state, FactoryEvent.REQUIRE_MANUAL_REVIEW),
            FactoryState.NEEDS_MANUAL_REVIEW,
        )


def transition_factory_state(current: FactoryState, event: FactoryEvent) -> FactoryState:
    try:
        return LEGAL_FACTORY_TRANSITIONS[(current, event)]
    except KeyError as exc:
        raise InvalidFactoryTransitionError(
            f"factory transition {current.value} + {event.value} is not legal"
        ) from exc


class CodexTaskType(str, Enum):
    SOURCE_RESEARCH = "SOURCE_RESEARCH"
    HYPOTHESIS_PROPOSAL = "HYPOTHESIS_PROPOSAL"
    DUPLICATE_ASSESSMENT = "DUPLICATE_ASSESSMENT"
    MECHANICS_INTENT = "MECHANICS_INTENT"
    ENGINEERING_HANDOFF = "ENGINEERING_HANDOFF"
    RESULT_DIAGNOSIS = "RESULT_DIAGNOSIS"
    NEXT_EXPERIMENT = "NEXT_EXPERIMENT"
    SUCCESSOR_MECHANICS_PROPOSAL = "SUCCESSOR_MECHANICS_PROPOSAL"
    NEW_RESEARCH_GENERATION_PROPOSAL = "NEW_RESEARCH_GENERATION_PROPOSAL"
    CANDIDATE_DUE_DILIGENCE = "CANDIDATE_DUE_DILIGENCE"


class InformationCategory(str, Enum):
    SOURCE = "SOURCE"
    RESEARCH_INVENTORY = "RESEARCH_INVENTORY"
    CERTIFIED_CATALOG = "CERTIFIED_CATALOG"
    DATASET_METADATA = "DATASET_METADATA"
    DEVELOPMENT_RESULT = "DEVELOPMENT_RESULT"
    WFA_RESULT = "WFA_RESULT"
    LOCKED_HOLDOUT_RESULT = "LOCKED_HOLDOUT_RESULT"
    FORWARD_RESULT = "FORWARD_RESULT"
    CAMPAIGN_POLICY = "CAMPAIGN_POLICY"


class InformationGranularity(str, Enum):
    METADATA = "METADATA"
    AGGREGATE = "AGGREGATE"
    TRADE_LEVEL = "TRADE_LEVEL"
    RAW_MARKET_DATA = "RAW_MARKET_DATA"


class InformationGrantV1(FactoryModel):
    artifact_name: str = Field(pattern=IDENTIFIER_PATTERN)
    category: InformationCategory
    granularity: InformationGranularity
    allowed_use: str = Field(min_length=10)
    data_window_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    locked_holdout: bool = False

    @field_validator("allowed_use")
    @classmethod
    def _use(cls, value: str) -> str:
        return _nonblank(value)

    @model_validator(mode="after")
    def _holdout_identity(self) -> "InformationGrantV1":
        if self.locked_holdout and self.data_window_id is None:
            raise ValueError("locked-holdout information requires data_window_id")
        if self.category == InformationCategory.LOCKED_HOLDOUT_RESULT and not self.locked_holdout:
            raise ValueError("locked-holdout result categories must be marked locked_holdout")
        return self


class ContextArtifactV1(FactoryModel):
    artifact_name: str = Field(pattern=IDENTIFIER_PATTERN)
    source_kind: Literal["MAPPING", "SEQUENCE", "TEXT", "FILE"]
    source_path: str | None
    media_type: str = Field(min_length=1)
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    content: Any


class ContextPacketV1(FactoryModel):
    schema_name: Literal["alphaquest.codex-context-packet/v1"] = Field(
        default="alphaquest.codex-context-packet/v1",
        alias="schema",
        serialization_alias="schema",
    )
    task_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_type: CodexTaskType
    objective: str = Field(min_length=20)
    built_at: datetime
    artifacts: list[ContextArtifactV1] = Field(min_length=1)
    allowed_information: list[InformationGrantV1] = Field(min_length=1)
    forbidden_information: list[str] = Field(min_length=1)
    artifact_hashes: dict[str, str]
    inputs_sha256: str = Field(pattern=SHA256_PATTERN)
    packet_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("objective")
    @classmethod
    def _objective(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("forbidden_information")
    @classmethod
    def _forbidden(cls, values: list[str]) -> list[str]:
        return _nonblank_items(values, label="forbidden_information")

    @field_validator("built_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> "ContextPacketV1":
        names = [artifact.artifact_name for artifact in self.artifacts]
        grant_names = [grant.artifact_name for grant in self.allowed_information]
        if len(set(names)) != len(names) or set(names) != set(grant_names):
            raise ValueError("every context artifact requires exactly one information grant")
        expected_hashes = {artifact.artifact_name: artifact.content_sha256 for artifact in self.artifacts}
        if self.artifact_hashes != expected_hashes:
            raise ValueError("artifact_hashes do not match context artifacts")
        expected_inputs = _context_inputs_sha256(
            artifact_hashes=expected_hashes,
            allowed_information=self.allowed_information,
            forbidden_information=self.forbidden_information,
        )
        if self.inputs_sha256 != expected_inputs:
            raise ValueError("context inputs_sha256 does not match its declared inputs")
        expected_packet = _context_packet_sha256(self)
        if self.packet_sha256 != expected_packet:
            raise ValueError("context packet_sha256 does not match packet content")
        return self


ContextInput = Mapping[str, Any] | Sequence[Any] | str | Path


def _context_inputs_sha256(
    *,
    artifact_hashes: Mapping[str, str],
    allowed_information: Sequence[InformationGrantV1],
    forbidden_information: Sequence[str],
) -> str:
    return object_sha256(
        {
            "artifact_hashes": dict(artifact_hashes),
            "allowed_information": [
                grant.model_dump(mode="json", by_alias=True) for grant in allowed_information
            ],
            "forbidden_information": list(forbidden_information),
        }
    )


def _context_packet_sha256(packet: ContextPacketV1 | Mapping[str, Any]) -> str:
    payload = (
        packet.model_dump(mode="json", by_alias=True)
        if isinstance(packet, ContextPacketV1)
        else dict(packet)
    )
    payload.pop("packet_sha256", None)
    return object_sha256(payload)


_DESIGN_TASK_TYPES = {
    CodexTaskType.HYPOTHESIS_PROPOSAL,
    CodexTaskType.DUPLICATE_ASSESSMENT,
    CodexTaskType.MECHANICS_INTENT,
    CodexTaskType.ENGINEERING_HANDOFF,
    CodexTaskType.NEXT_EXPERIMENT,
    CodexTaskType.SUCCESSOR_MECHANICS_PROPOSAL,
    CodexTaskType.NEW_RESEARCH_GENERATION_PROPOSAL,
}


def _path_is_within(path: Path, roots: Sequence[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _snapshot_context_artifact(
    name: str,
    value: ContextInput,
    *,
    allowed_roots: Sequence[Path] | None,
    maximum_file_bytes: int,
) -> ContextArtifactV1:
    if isinstance(value, Path):
        path = value.resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"context path is not a regular file: {path}")
        roots = [root.resolve() for root in allowed_roots or []]
        if roots and not _path_is_within(path, roots):
            raise ValueError(f"context path is outside allowed roots: {path}")
        logical_path = path.name
        for root in roots:
            if _path_is_within(path, [root]):
                logical_path = path.relative_to(root).as_posix()
                break
        raw = path.read_bytes()
        if len(raw) > maximum_file_bytes:
            raise ValueError(f"context file exceeds {maximum_file_bytes} bytes: {path}")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"context files must be UTF-8 text: {path}") from exc
        media_type = "application/json" if path.suffix.casefold() == ".json" else "text/plain"
        if media_type == "application/json":
            try:
                content: Any = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON context file: {path}") from exc
        else:
            content = text
        return ContextArtifactV1(
            artifact_name=name,
            source_kind="FILE",
            source_path=logical_path,
            media_type=media_type,
            content_sha256=hashlib.sha256(raw).hexdigest(),
            content=content,
        )
    if isinstance(value, Mapping):
        content = json.loads(canonical_json_bytes(dict(value)).decode("utf-8"))
        return ContextArtifactV1(
            artifact_name=name,
            source_kind="MAPPING",
            source_path=None,
            media_type="application/json",
            content_sha256=object_sha256(content),
            content=content,
        )
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return ContextArtifactV1(
            artifact_name=name,
            source_kind="TEXT",
            source_path=None,
            media_type="text/plain",
            content_sha256=hashlib.sha256(raw).hexdigest(),
            content=value,
        )
    if isinstance(value, Sequence):
        content = json.loads(canonical_json_bytes(list(value)).decode("utf-8"))
        return ContextArtifactV1(
            artifact_name=name,
            source_kind="SEQUENCE",
            source_path=None,
            media_type="application/json",
            content_sha256=object_sha256(content),
            content=content,
        )
    raise TypeError(f"unsupported context input for {name}: {type(value).__name__}")


def build_context_packet(
    *,
    task_id: str,
    task_type: CodexTaskType,
    objective: str,
    artifacts: Mapping[str, ContextInput],
    allowed_information: Sequence[InformationGrantV1],
    forbidden_information: Sequence[str],
    built_at: datetime | None = None,
    allowed_roots: Sequence[str | Path] | None = None,
    maximum_file_bytes: int = 5_000_000,
) -> ContextPacketV1:
    """Create a detached, read-only, hash-bound snapshot from explicit inputs."""

    if not artifacts:
        raise ValueError("at least one context artifact is required")
    if maximum_file_bytes < 1:
        raise ValueError("maximum_file_bytes must be positive")
    grants = list(allowed_information)
    if task_type in _DESIGN_TASK_TYPES and any(grant.locked_holdout for grant in grants):
        raise ValueError("locked-holdout information cannot enter hypothesis, mechanics, or next-test design")
    resolved_roots = [Path(root) for root in allowed_roots or []]
    snapshots = [
        _snapshot_context_artifact(
            name,
            value,
            allowed_roots=resolved_roots,
            maximum_file_bytes=maximum_file_bytes,
        )
        for name, value in sorted(artifacts.items())
    ]
    artifact_hashes = {artifact.artifact_name: artifact.content_sha256 for artifact in snapshots}
    inputs_sha256 = _context_inputs_sha256(
        artifact_hashes=artifact_hashes,
        allowed_information=grants,
        forbidden_information=forbidden_information,
    )
    payload = {
        "schema": "alphaquest.codex-context-packet/v1",
        "task_id": task_id,
        "task_type": task_type,
        "objective": objective,
        "built_at": built_at or datetime.now(UTC),
        "artifacts": snapshots,
        "allowed_information": grants,
        "forbidden_information": list(forbidden_information),
        "artifact_hashes": artifact_hashes,
        "inputs_sha256": inputs_sha256,
    }
    payload["packet_sha256"] = _context_packet_sha256(payload)
    return ContextPacketV1.model_validate(payload)


class CodexTaskV1(FactoryModel):
    schema_name: Literal["alphaquest.codex-task/v1"] = Field(
        default="alphaquest.codex-task/v1",
        alias="schema",
        serialization_alias="schema",
    )
    task_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_type: CodexTaskType
    objective: str = Field(min_length=20)
    context_packet_sha256: str = Field(pattern=SHA256_PATTERN)
    inputs_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_hashes: dict[str, str]
    expected_output_schema: str = Field(min_length=1)
    created_at: datetime
    read_only: Literal[True] = True
    permitted_action: Literal["PROPOSE_ONLY"] = "PROPOSE_ONLY"
    task_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("objective", "expected_output_schema")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("created_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> "CodexTaskV1":
        if self.task_sha256 != _codex_task_sha256(self):
            raise ValueError("task_sha256 does not match task content")
        return self


def _codex_task_sha256(task: CodexTaskV1 | Mapping[str, Any]) -> str:
    payload = task.model_dump(mode="json", by_alias=True) if isinstance(task, CodexTaskV1) else dict(task)
    payload.pop("task_sha256", None)
    return object_sha256(payload)


def build_codex_task(
    context: ContextPacketV1,
    *,
    expected_output_schema: str,
    created_at: datetime | None = None,
) -> CodexTaskV1:
    payload = {
        "schema": "alphaquest.codex-task/v1",
        "task_id": context.task_id,
        "task_type": context.task_type,
        "objective": context.objective,
        "context_packet_sha256": context.packet_sha256,
        "inputs_sha256": context.inputs_sha256,
        "artifact_hashes": dict(context.artifact_hashes),
        "expected_output_schema": expected_output_schema,
        "created_at": created_at or datetime.now(UTC),
        "read_only": True,
        "permitted_action": "PROPOSE_ONLY",
    }
    payload["task_sha256"] = _codex_task_sha256(payload)
    return CodexTaskV1.model_validate(payload)


class CodexRunProvenanceV1(FactoryModel):
    schema_name: Literal["alphaquest.codex-proposal-run-provenance/v1"] = Field(
        default="alphaquest.codex-proposal-run-provenance/v1",
        alias="schema",
        serialization_alias="schema",
    )
    run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=IDENTIFIER_PATTERN)
    model: str | None = Field(default=None, min_length=1)
    codex_version: str | None = Field(default=None, min_length=1)
    authentication_mode: Literal["CHATGPT_SUBSCRIPTION"] = "CHATGPT_SUBSCRIPTION"
    runtime_request_sha256: str = Field(pattern=SHA256_PATTERN)
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    output_schema_sha256: str = Field(pattern=SHA256_PATTERN)
    repository_revision: str = Field(min_length=1)
    dirty_tree_sha256: str = Field(pattern=SHA256_PATTERN)
    started_at: datetime
    finished_at: datetime
    sandbox: Literal["READ_ONLY"] = "READ_ONLY"
    external_writes_permitted: Literal[False] = False
    exit_status: Literal["SUCCEEDED", "REFUSED", "FAILED", "USAGE_UNAVAILABLE"]

    @field_validator("model", "codex_version", "repository_revision")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return _nonblank(value) if value is not None else None

    @field_validator("started_at", "finished_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _ordered(self) -> "CodexRunProvenanceV1":
        if self.finished_at < self.started_at:
            raise ValueError("Codex run finished_at cannot precede started_at")
        return self


class CodexProposalEnvelopeV1(FactoryModel):
    schema_name: Literal["alphaquest.codex-proposal-envelope/v1"] = Field(
        default="alphaquest.codex-proposal-envelope/v1",
        alias="schema",
        serialization_alias="schema",
    )
    proposal_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_type: CodexTaskType
    task_sha256: str = Field(pattern=SHA256_PATTERN)
    context_packet_sha256: str = Field(pattern=SHA256_PATTERN)
    inputs_sha256: str = Field(pattern=SHA256_PATTERN)
    input_artifact_hashes: dict[str, str]
    proposal_schema: str = Field(min_length=1)
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    produced_at: datetime
    provenance: CodexRunProvenanceV1

    @field_validator("produced_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> "CodexProposalEnvelopeV1":
        if self.provenance.task_id != self.task_id:
            raise ValueError("proposal provenance task_id does not match envelope")
        if self.provenance.exit_status != "SUCCEEDED":
            raise ValueError("only a successful Codex run may produce a proposal envelope")
        if self.payload_sha256 != object_sha256(self.payload):
            raise ValueError("payload_sha256 does not match proposal payload")
        return self


class ImportedProposalV1(FactoryModel):
    schema_name: Literal["alphaquest.imported-proposal/v1"] = Field(
        default="alphaquest.imported-proposal/v1",
        alias="schema",
        serialization_alias="schema",
    )
    proposal_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_sha256: str = Field(pattern=SHA256_PATTERN)
    context_packet_sha256: str = Field(pattern=SHA256_PATTERN)
    proposal_schema: str
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    validated_payload: dict[str, Any]
    validated_at: datetime
    status: Literal["VALIDATED_NOT_APPLIED"] = "VALIDATED_NOT_APPLIED"
    durable_writes_performed: Literal[False] = False

    @field_validator("validated_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)


PROPOSAL_MODELS: dict[str, type[BaseModel]] = {
    "alphaquest.source-evidence-bundle/v1": SourceEvidenceBundleV1,
    "alphaquest.hypothesis-proposal/v1": HypothesisProposalV1,
    "alphaquest.mechanics-intent/v1": MechanicsIntentV1,
    "alphaquest.engineering-handoff-proposal/v1": EngineeringHandoffProposalV1,
    "alphaquest.failure-diagnosis/v1": FailureDiagnosisV1,
    "alphaquest.next-experiment-proposal/v1": NextExperimentProposalV1,
    "alphaquest.next-action-ranking-proposal/v1": NextActionRankingProposalV1,
    "alphaquest.candidate-due-diligence-summary/v1": CandidateDueDiligenceSummaryV1,
}


def _current_artifact_hashes(
    original: ContextPacketV1,
    current_artifacts: Mapping[str, ContextInput],
) -> dict[str, str]:
    if set(current_artifacts) != set(original.artifact_hashes):
        raise StaleProposalError("current context artifact names differ from the task packet")
    hashes: dict[str, str] = {}
    for name, value in sorted(current_artifacts.items()):
        snapshot = _snapshot_context_artifact(
            name,
            value,
            allowed_roots=None,
            maximum_file_bytes=5_000_000,
        )
        hashes[name] = snapshot.content_sha256
    return hashes


def validate_and_import_proposal(
    envelope: CodexProposalEnvelopeV1,
    *,
    expected_task: CodexTaskV1,
    original_context: ContextPacketV1,
    current_artifacts: Mapping[str, ContextInput],
    validated_at: datetime | None = None,
) -> ImportedProposalV1:
    """Validate an untrusted proposal without writing campaigns or evidence."""

    # ``frozen=True`` prevents field replacement but Python containers are not
    # recursively immutable.  Reparse canonical bytes so cross-field hash
    # validators run again even if a caller retained and mutated a nested
    # mapping or list after construction.
    try:
        envelope = CodexProposalEnvelopeV1.model_validate_json(
            canonical_json_bytes(envelope.model_dump(mode="json", by_alias=True))
        )
        expected_task = CodexTaskV1.model_validate_json(
            canonical_json_bytes(expected_task.model_dump(mode="json", by_alias=True))
        )
        original_context = ContextPacketV1.model_validate_json(
            canonical_json_bytes(original_context.model_dump(mode="json", by_alias=True))
        )
    except ValidationError as exc:
        raise StaleProposalError(f"factory task or context integrity check failed: {exc}") from exc

    if expected_task.task_id != original_context.task_id:
        raise StaleProposalError("task and context identifiers differ")
    if expected_task.context_packet_sha256 != original_context.packet_sha256:
        raise StaleProposalError("task no longer identifies the supplied context packet")
    if expected_task.inputs_sha256 != original_context.inputs_sha256:
        raise StaleProposalError("task input hash no longer identifies the supplied context")
    observed_hashes = _current_artifact_hashes(original_context, current_artifacts)
    if observed_hashes != original_context.artifact_hashes:
        raise StaleProposalError("one or more context inputs changed after the Codex task was created")
    comparisons = {
        "task_id": (envelope.task_id, expected_task.task_id),
        "task_type": (envelope.task_type, expected_task.task_type),
        "task_sha256": (envelope.task_sha256, expected_task.task_sha256),
        "context_packet_sha256": (
            envelope.context_packet_sha256,
            expected_task.context_packet_sha256,
        ),
        "inputs_sha256": (envelope.inputs_sha256, expected_task.inputs_sha256),
        "input_artifact_hashes": (
            envelope.input_artifact_hashes,
            expected_task.artifact_hashes,
        ),
        "proposal_schema": (envelope.proposal_schema, expected_task.expected_output_schema),
    }
    for label, (actual, expected) in comparisons.items():
        if actual != expected:
            raise StaleProposalError(f"proposal {label} does not match its expected task")
    model = PROPOSAL_MODELS.get(envelope.proposal_schema)
    if model is None:
        raise InvalidProposalError(f"unsupported proposal schema: {envelope.proposal_schema}")
    try:
        parsed = model.model_validate_json(canonical_json_bytes(envelope.payload))
    except ValidationError as exc:
        raise InvalidProposalError(
            f"proposal failed {envelope.proposal_schema}: {exc}"
        ) from exc
    validated_payload = parsed.model_dump(mode="json", by_alias=True)
    if object_sha256(validated_payload) != envelope.payload_sha256:
        raise InvalidProposalError("normalized proposal payload differs from the signed payload")
    return ImportedProposalV1(
        proposal_id=envelope.proposal_id,
        task_id=envelope.task_id,
        task_sha256=envelope.task_sha256,
        context_packet_sha256=envelope.context_packet_sha256,
        proposal_schema=envelope.proposal_schema,
        payload_sha256=envelope.payload_sha256,
        validated_payload=validated_payload,
        validated_at=validated_at or datetime.now(UTC),
    )


class InformationAccessEventV1(FactoryModel):
    schema_name: Literal["alphaquest.information-access-event/v1"] = Field(
        default="alphaquest.information-access-event/v1",
        alias="schema",
        serialization_alias="schema",
    )
    access_id: str = Field(pattern=IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=IDENTIFIER_PATTERN)
    edge_family_id: str = Field(pattern=IDENTIFIER_PATTERN)
    campaign_id: str = Field(pattern=IDENTIFIER_PATTERN)
    variant_id: str | None = Field(default=None, pattern=VARIANT_PATTERN)
    accessed_at: datetime
    category: InformationCategory
    granularity: InformationGranularity
    data_window_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    locked_holdout: bool
    purpose: str = Field(min_length=10)
    actor: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    previous_event_sha256: str = Field(pattern=SHA256_PATTERN)
    event_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("accessed_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("purpose", "actor")
    @classmethod
    def _text(cls, value: str) -> str:
        return _nonblank(value)

    @model_validator(mode="after")
    def _integrity(self) -> "InformationAccessEventV1":
        if self.locked_holdout and self.data_window_id is None:
            raise ValueError("locked-holdout access requires data_window_id")
        if self.category == InformationCategory.LOCKED_HOLDOUT_RESULT and not self.locked_holdout:
            raise ValueError("locked-holdout result access must be marked locked_holdout")
        if self.event_sha256 != _information_event_sha256(self):
            raise ValueError("information-access event_sha256 does not match event content")
        return self


def _information_event_sha256(event: InformationAccessEventV1 | Mapping[str, Any]) -> str:
    payload = (
        event.model_dump(mode="json", by_alias=True)
        if isinstance(event, InformationAccessEventV1)
        else dict(event)
    )
    payload.pop("event_sha256", None)
    return object_sha256(payload)


class InformationAccessLedgerV1(FactoryModel):
    schema_name: Literal["alphaquest.information-access-ledger/v1"] = Field(
        default="alphaquest.information-access-ledger/v1",
        alias="schema",
        serialization_alias="schema",
    )
    events: list[InformationAccessEventV1]

    @model_validator(mode="after")
    def _chain(self) -> "InformationAccessLedgerV1":
        previous = "0" * 64
        identifiers: set[str] = set()
        for event in self.events:
            if event.access_id in identifiers:
                raise ValueError("information access identifiers must be unique")
            if event.previous_event_sha256 != previous:
                raise ValueError("information-access ledger hash chain is invalid")
            identifiers.add(event.access_id)
            previous = event.event_sha256
        return self


def make_information_access_event(
    *,
    ledger: InformationAccessLedgerV1,
    access_id: str,
    task_id: str,
    edge_family_id: str,
    campaign_id: str,
    variant_id: str | None,
    category: InformationCategory,
    granularity: InformationGranularity,
    data_window_id: str | None,
    locked_holdout: bool,
    purpose: str,
    actor: str,
    artifact_sha256: str,
    accessed_at: datetime | None = None,
) -> InformationAccessEventV1:
    previous = ledger.events[-1].event_sha256 if ledger.events else "0" * 64
    payload = {
        "schema": "alphaquest.information-access-event/v1",
        "access_id": access_id,
        "task_id": task_id,
        "edge_family_id": edge_family_id,
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "accessed_at": accessed_at or datetime.now(UTC),
        "category": category,
        "granularity": granularity,
        "data_window_id": data_window_id,
        "locked_holdout": locked_holdout,
        "purpose": purpose,
        "actor": actor,
        "artifact_sha256": artifact_sha256,
        "previous_event_sha256": previous,
    }
    payload["event_sha256"] = _information_event_sha256(payload)
    return InformationAccessEventV1.model_validate(payload)


def append_information_access(
    ledger: InformationAccessLedgerV1,
    event: InformationAccessEventV1,
) -> InformationAccessLedgerV1:
    expected = ledger.events[-1].event_sha256 if ledger.events else "0" * 64
    if event.previous_event_sha256 != expected:
        raise ValueError("information access event does not extend the current ledger head")
    return InformationAccessLedgerV1(events=[*ledger.events, event])


def consumed_locked_holdouts(
    ledger: InformationAccessLedgerV1,
    *,
    edge_family_id: str,
) -> set[str]:
    """Any research-facing access consumes a locked window for later design."""

    return {
        event.data_window_id
        for event in ledger.events
        if event.edge_family_id == edge_family_id
        and event.locked_holdout
        and event.data_window_id is not None
    }


class ResearchBudgetV1(FactoryModel):
    schema_name: Literal["alphaquest.research-budget/v1"] = Field(
        default="alphaquest.research-budget/v1",
        alias="schema",
        serialization_alias="schema",
    )
    edge_family_id: str = Field(pattern=IDENTIFIER_PATTERN)
    max_hypotheses: int = Field(ge=1)
    max_pnl_trials: int = Field(ge=1)
    max_variants: int = Field(ge=1, le=5)
    max_rescue_attempts: int = Field(ge=0, le=1)
    max_codex_runs: int = Field(ge=1)
    locked_holdout_window_ids: list[str] = Field(min_length=1)

    @field_validator("locked_holdout_window_ids")
    @classmethod
    def _windows(cls, values: list[str]) -> list[str]:
        normalized = _nonblank_items(values, label="locked_holdout_window_ids")
        for value in normalized:
            if not value[0].isalnum() or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for character in value):
                raise ValueError("locked holdout identifiers must be stable identifiers")
        return normalized


class BudgetUsageV1(FactoryModel):
    schema_name: Literal["alphaquest.research-budget-usage/v1"] = Field(
        default="alphaquest.research-budget-usage/v1",
        alias="schema",
        serialization_alias="schema",
    )
    edge_family_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hypotheses: int = Field(ge=0)
    pnl_trials: int = Field(ge=0)
    variants: int = Field(ge=0)
    rescue_attempts: int = Field(ge=0)
    codex_runs: int = Field(ge=0)


class BudgetDecisionV1(FactoryModel):
    schema_name: Literal["alphaquest.research-budget-decision/v1"] = Field(
        default="alphaquest.research-budget-decision/v1",
        alias="schema",
        serialization_alias="schema",
    )
    action: NextAction
    allowed: bool
    blockers: list[str]
    fresh_locked_holdout_window_ids: list[str]

    @field_validator("blockers", "fresh_locked_holdout_window_ids")
    @classmethod
    def _lists(cls, values: list[str], info: Any) -> list[str]:
        return _nonblank_items(values, label=info.field_name)


def enforce_budget(
    budget: ResearchBudgetV1,
    usage: BudgetUsageV1,
    ledger: InformationAccessLedgerV1,
    *,
    action: NextAction,
) -> BudgetDecisionV1:
    if usage.edge_family_id != budget.edge_family_id:
        raise ValueError("budget usage belongs to a different edge family")
    consumed = consumed_locked_holdouts(ledger, edge_family_id=budget.edge_family_id)
    fresh = [window for window in budget.locked_holdout_window_ids if window not in consumed]
    blockers: list[str] = []
    if usage.codex_runs >= budget.max_codex_runs and action in {
        NextAction.PROPOSE_SUCCESSOR,
        NextAction.START_NEW_RESEARCH_GENERATION,
    }:
        blockers.append("Codex run budget is exhausted")
    if action == NextAction.PROPOSE_SUCCESSOR:
        if usage.pnl_trials >= budget.max_pnl_trials:
            blockers.append("PnL-bearing trial budget is exhausted")
        if usage.variants >= budget.max_variants:
            blockers.append("variant budget is exhausted")
    if action == NextAction.START_NEW_RESEARCH_GENERATION:
        if usage.hypotheses >= budget.max_hypotheses:
            blockers.append("hypothesis budget is exhausted")
        if not fresh:
            blockers.append("no fresh locked confirmation window remains")
    return BudgetDecisionV1(
        action=action,
        allowed=not blockers,
        blockers=blockers,
        fresh_locked_holdout_window_ids=fresh,
    )


class NextActionEligibilityV1(FactoryModel):
    schema_name: Literal["alphaquest.next-action-eligibility/v1"] = Field(
        default="alphaquest.next-action-eligibility/v1",
        alias="schema",
        serialization_alias="schema",
    )
    diagnosis_sha256: str = Field(pattern=SHA256_PATTERN)
    verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    eligible_actions: list[NextAction] = Field(min_length=1)
    blocked_actions: dict[str, str]
    fresh_locked_holdout_window_ids: list[str]

    @model_validator(mode="after")
    def _distinct(self) -> "NextActionEligibilityV1":
        if len(set(self.eligible_actions)) != len(self.eligible_actions):
            raise ValueError("eligible next actions must be distinct")
        return self


_POST_OOS_STAGES = {
    StageKind.WFA_OOS,
    StageKind.LOCKED_HOLDOUT,
    StageKind.STRESS,
    StageKind.FINAL_ACCEPTANCE,
    StageKind.FORWARD,
}


def determine_next_action_eligibility(
    diagnosis: FailureDiagnosisV1,
    *,
    diagnosis_sha256: str,
    budget: ResearchBudgetV1,
    usage: BudgetUsageV1,
    ledger: InformationAccessLedgerV1,
    pnl_generated: bool,
) -> NextActionEligibilityV1:
    """Apply verdict, information-set, and budget policy before Codex ranking."""

    eligible: list[NextAction] = []
    blocked: dict[str, str] = {}
    consumed = consumed_locked_holdouts(ledger, edge_family_id=budget.edge_family_id)
    fresh = [window for window in budget.locked_holdout_window_ids if window not in consumed]

    if diagnosis.verdict == "PASS":
        eligible.append(NextAction.BEGIN_CANDIDATE_REVIEW)
        for action in (NextAction.PROPOSE_SUCCESSOR, NextAction.REPAIR_SAME_VARIANT):
            blocked[action.value] = "PASS freezes mechanics; proceed to independent candidate review"
    elif diagnosis.verdict == "NEEDS MANUAL REVIEW":
        eligible.append(NextAction.OBTAIN_MANUAL_REVIEW)
        if not pnl_generated and any(
            item in diagnosis.classifications
            for item in {
                FailureClass.DATA_QUALITY,
                FailureClass.MECHANICS_DEFECT,
                FailureClass.INSUFFICIENT_EVIDENCE,
            }
        ):
            eligible.append(NextAction.REPAIR_SAME_VARIANT)
        blocked[NextAction.PROPOSE_SUCCESSOR.value] = (
            "NEEDS MANUAL REVIEW permits evidence repair or review, never a new variant"
        )
    else:
        eligible.append(NextAction.ABANDON_EDGE)
        if FailureClass.ACCOUNT_UNSUITABLE in diagnosis.classifications:
            blocked[NextAction.ASSESS_OTHER_DESTINATION.value] = (
                "destination assessment requires scientific-validity PASS and belongs to the separate candidate path"
            )
        post_oos = diagnosis.stage_kind in _POST_OOS_STAGES
        holdout_consumed = bool(consumed)
        if post_oos or holdout_consumed:
            blocked[NextAction.PROPOSE_SUCCESSOR.value] = (
                "post-OOS or locked-holdout evidence cannot tune a successor in the same research generation"
            )
            generation = enforce_budget(
                budget,
                usage,
                ledger,
                action=NextAction.START_NEW_RESEARCH_GENERATION,
            )
            if generation.allowed:
                eligible.append(NextAction.START_NEW_RESEARCH_GENERATION)
            else:
                blocked[NextAction.START_NEW_RESEARCH_GENERATION.value] = "; ".join(generation.blockers)
                eligible.append(NextAction.STOP_NO_FRESH_HOLDOUT)
        else:
            successor = enforce_budget(
                budget,
                usage,
                ledger,
                action=NextAction.PROPOSE_SUCCESSOR,
            )
            if successor.allowed:
                eligible.append(NextAction.PROPOSE_SUCCESSOR)
            else:
                blocked[NextAction.PROPOSE_SUCCESSOR.value] = "; ".join(successor.blockers)

    return NextActionEligibilityV1(
        diagnosis_sha256=diagnosis_sha256,
        verdict=diagnosis.verdict,
        eligible_actions=eligible,
        blocked_actions=blocked,
        fresh_locked_holdout_window_ids=fresh,
    )


__all__ = [
    "BudgetDecisionV1",
    "BudgetExceededError",
    "BudgetUsageV1",
    "CandidateDueDiligenceSummaryV1",
    "CodexProposalEnvelopeV1",
    "CodexRunProvenanceV1",
    "CodexTaskType",
    "CodexTaskV1",
    "ContextArtifactV1",
    "ContextPacketV1",
    "CriterionOutcomeV1",
    "EngineeringHandoffProposalV1",
    "FactoryEvent",
    "FactoryState",
    "FailureClass",
    "FailureDiagnosisV1",
    "HypothesisProposalV1",
    "ImportedProposalV1",
    "InformationAccessEventV1",
    "InformationAccessLedgerV1",
    "InformationCategory",
    "InformationGranularity",
    "InformationGrantV1",
    "InvalidFactoryTransitionError",
    "InvalidProposalError",
    "MechanicsIntentV1",
    "NextAction",
    "NextActionEligibilityV1",
    "NextActionRankingProposalV1",
    "NextExperimentProposalV1",
    "RankedNextActionV1",
    "ParameterIntentV1",
    "ResearchBudgetV1",
    "ResearchFactoryError",
    "ResultSummaryV1",
    "SourceClaimV1",
    "SourceEvidenceBundleV1",
    "StageKind",
    "StaleProposalError",
    "append_information_access",
    "build_codex_task",
    "build_context_packet",
    "canonical_json_bytes",
    "classify_result_failure",
    "consumed_locked_holdouts",
    "determine_next_action_eligibility",
    "enforce_budget",
    "make_information_access_event",
    "object_sha256",
    "transition_factory_state",
    "validate_and_import_proposal",
]
