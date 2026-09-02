"""Canonical P1 research operating-model policy and integrity checks.

This module validates policy definitions only.  It does not implement the
future backlog, execution, deployment, or live orchestration described by
policy-only transitions in the specification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPERATING_MODEL_PATH = PROJECT_ROOT / "config" / "research_operating_model.yaml"
OPERATING_MODEL_SCHEMA = "alphaquest.research-operating-model/v1"

REQUIRED_ACTORS = {
    "CODEX",
    "ALPHAQUEST_DETERMINISTIC_ENGINE",
    "HUMAN_OWNER_RESEARCHER",
    "EXTERNAL_SYSTEM",
}
REQUIRED_OBJECTS = {
    "OBSERVATION",
    "HYPOTHESIS",
    "EDGE_FAMILY",
    "CAMPAIGN",
    "STRATEGY_VARIANT",
    "ATTEMPT",
    "RUN",
    "MECHANICS_APPROVAL",
    "HISTORICAL_VALIDATION_RESULT",
    "CANDIDATE_STRATEGY",
    "FORWARD_INCUBATION_PLAN",
    "FORWARD_OBSERVATION",
    "PORTFOLIO_CANDIDATE",
    "ACCOUNT_SUITABILITY_ASSESSMENT",
    "DEPLOYMENT_PACKAGE",
    "LIVE_STRATEGY_INSTANCE",
}
REQUIRED_STATE_AXES = {
    "RESEARCH_LIFECYCLE_STAGE",
    "LIFECYCLE_DISPOSITION",
    "SCIENTIFIC_STATE",
    "IMPLEMENTATION_STATE",
    "FORWARD_STATE",
    "PORTFOLIO_STATE",
    "ACCOUNT_SUITABILITY_STATE",
    "DEPLOYMENT_STATE",
    "OPERATIONAL_STATE",
    "EVIDENCE_CURRENTNESS",
    "EDGE_FAMILY_DISPOSITION",
}
REQUIRED_INVARIANTS = {
    "CODEX_CANNOT_AUTHORIZE_LIVE_DEPLOYMENT",
    "ACCOUNT_SUITABILITY_CANNOT_CREATE_SCIENTIFIC_VALIDITY",
    "ACCOUNT_SUITABILITY_CANNOT_CREATE_CANDIDATE_STATUS",
    "RESEARCH_OBJECT_DEPENDENCIES_ARE_ACYCLIC",
    "RESEARCH_OBJECT_MUTABILITY_IS_CANONICAL_AND_SEPARATE_FROM_CURRENTNESS",
    "CANONICAL_TRANSITION_GRAPH_FAILS_CLOSED",
    "CANONICAL_TRANSITION_EFFECT_CONTRACTS_FAIL_CLOSED",
    "PROTECTED_DEPLOYMENT_INGRESS_FAILS_CLOSED",
    "HISTORICAL_CANDIDATE_CANNOT_IMPLY_LIVE_AUTHORIZATION",
    "HISTORICAL_VERDICT_RECORDING_DOES_NOT_CREATE_CANDIDATE_STATUS",
    "HISTORICAL_FAIL_CANNOT_ENTER_CANDIDATE_REVIEW",
    "NEEDS_MANUAL_REVIEW_REQUIRES_GOVERNED_RESOLUTION",
    "FORWARD_INCUBATION_CANNOT_BE_HISTORICALLY_BACKFILLED",
    "FORWARD_EVIDENCE_IS_ALPHAQUEST_CUSTODIED",
    "FAILED_RESEARCH_CANNOT_BE_DELETED_OR_RELABELED_PASS",
    "METHODOLOGY_CHANGE_REQUIRES_DISTINGUISHABLE_IDENTITY",
    "MATERIAL_DATA_CHANGE_REQUIRES_DISTINGUISHABLE_LINEAGE",
    "SEMANTIC_IMPLEMENTATION_CHANGE_INVALIDATES_DEPENDENCIES",
    "UNCERTAIN_IMPLEMENTATION_EQUIVALENCE_FAILS_CLOSED",
    "PROVEN_NONSEMANTIC_CHANGE_MAY_REUSE_EVIDENCE",
    "RED_TEAM_IS_SEPARATE_FROM_IMPLEMENTATION_OWNERSHIP",
    "SINGLE_HUMAN_INDEPENDENCE_IS_TASK_BASED",
    "DETERMINISTIC_CAMPAIGN_STOP_REQUIRES_NO_HUMAN",
    "VARIANT_FAILURE_DOES_NOT_EXHAUST_CAMPAIGN_WITH_REMAINING_BUDGET",
    "CAMPAIGN_EXHAUSTION_REQUIRES_CAMPAIGN_LEVEL_RULE",
    "DISCRETIONARY_ABANDONMENT_AND_REVISIT_REQUIRE_HUMAN",
    "SAME_CONTRACT_DATA_APPEND_CANNOT_REBIND_FROZEN_RESEARCH",
    "CODEX_CANNOT_OVERRIDE_DETERMINISTIC_GATE_FAILURE",
    "HUMAN_CANNOT_OVERRIDE_MISSING_OBJECTIVE_EVIDENCE",
    "OPERATING_MODEL_IDENTITY_IS_ENGINE_AND_METHODOLOGY_INDEPENDENT",
}
REQUIRED_PROHIBITIONS = {
    "WEAKEN_GATE_AFTER_RESULTS",
    "MODIFY_OOS_AFTER_ACCESS",
    "DELETE_FAILED_RESEARCH",
    "HIDE_PARAMETER_SEARCH",
    "REWRITE_HISTORICAL_EVIDENCE",
    "RETROACTIVELY_CHANGE_METHODOLOGY_IDENTITY",
    "SELF_APPROVE_MECHANICS",
    "SELF_APPROVE_RED_TEAM",
    "RECERTIFY_WITHOUT_PROCESS",
    "AUTHORIZE_OR_PROMOTE_LIVE",
    "CHANGE_RISK_TO_RESCUE_STRATEGY",
    "CHANGE_ACCOUNT_RULES_TO_CREATE_SUITABILITY",
    "CONVERT_MISSING_EVIDENCE_TO_PASS",
    "SILENTLY_APPROXIMATE_UNSUPPORTED_MECHANICS_OR_DATA",
    "RETRY_UNTIL_PASS",
    "USE_LIVE_RESULTS_TO_REWRITE_RESEARCH",
}
REQUIRED_DATA_CHANGES = {
    "ADD_ROWS_SAME_CERTIFIED_DATASET",
    "ADD_NEW_INSTRUMENT",
    "CHANGE_VENDOR_OR_SOURCE",
    "CHANGE_ROLL_METHODOLOGY",
    "FIX_TIMESTAMPS",
    "CHANGE_AGGRESSOR_CLASSIFICATION",
    "CHANGE_NORMALIZATION",
    "ADD_NEW_FIELDS",
    "REPAIR_CORRUPT_DATA",
    "CHANGE_SESSION_DEFINITIONS",
}
REQUIRED_IMPLEMENTATION_CHANGES = {
    "COMMENT_OR_DOCS_ONLY",
    "REFACTOR_PROVEN_BEHAVIOR_IDENTICAL",
    "BUG_FIX_BEHAVIOR_UNCHANGED",
    "BUG_FIX_BEHAVIOR_CHANGED",
    "PERFORMANCE_ONLY_OPTIMIZATION",
    "MECHANICS_CHANGE",
    "DEPENDENCY_SEMANTIC_CHANGE",
}
SEMANTIC_IMPLEMENTATION_CHANGES = {
    "BUG_FIX_BEHAVIOR_CHANGED",
    "MECHANICS_CHANGE",
    "DEPENDENCY_SEMANTIC_CHANGE",
}
PROVEN_NONSEMANTIC_IMPLEMENTATION_CHANGES = {
    "REFACTOR_PROVEN_BEHAVIOR_IDENTICAL",
    "BUG_FIX_BEHAVIOR_UNCHANGED",
    "PERFORMANCE_ONLY_OPTIMIZATION",
}
IMPLEMENTATION_STATUSES = {"EXISTING", "EXISTING_PARTIAL", "POLICY_ONLY"}
PARTIAL_CONFORMANCE_FIELDS = {
    "current_runtime_behavior",
    "target_policy_behavior",
    "known_gap",
    "migration_required",
}
CODEX_TRANSITION_MODES = {
    "ALLOWED_AFTER_HUMAN_SCOPE_APPROVAL",
    "ALLOWED_PROPOSAL_ONLY",
    "ALLOWED_TO_ANALYZE_ONLY",
    "ALLOWED_TO_INTERPRET_ONLY",
    "ALLOWED_TO_PREPARE_NOT_APPROVE",
    "ALLOWED_TO_REQUEST_AND_SUMMARIZE_ONLY",
    "ALLOWED_TO_REQUEST_AUTHORED_RUN_ONLY",
    "ALLOWED_TO_SUMMARIZE_ONLY",
    "PROHIBITED",
    "PROHIBITED_TO_APPROVE",
    "PROHIBITED_TO_DECIDE",
    "PROHIBITED_TO_OVERRIDE",
    "PROHIBITED_TO_OVERRIDE_OR_RESTART",
    "PROHIBITED_TO_START",
    "PROPOSAL_ONLY",
}
CRITICAL_HUMAN_TRANSITION_AUTHORITY = {
    "APPROVE_MECHANICAL_INTERPRETATION": "PROHIBITED",
    "OPEN_LOCKED_ACCEPTANCE_OOS": "PROHIBITED",
    "APPROVE_HISTORICAL_CANDIDATE": "PROHIBITED_TO_APPROVE",
    "ACCEPT_FORWARD_REVIEW": "PROHIBITED_TO_APPROVE",
    "RECORD_PORTFOLIO_DISPOSITION": "PROPOSAL_ONLY",
    "AUTHORIZE_DEPLOYMENT": "PROHIBITED",
    "PROMOTE_SHADOW_TO_SMALL_LIVE": "PROHIBITED",
    "PROMOTE_SMALL_LIVE_TO_LIVE": "PROHIBITED",
}
REQUIRED_AUTONOMOUS_PERMISSIONS = {
    "READ_AND_SEARCH_LITERATURE": "ADVISORY",
    "PROPOSE_HYPOTHESIS": "PROPOSAL",
    "CRITIQUE_HYPOTHESIS": "ADVISORY",
    "ESTIMATE_IMPLEMENTATION_FEASIBILITY": "ADVISORY",
    "PREPARE_CAMPAIGN_DRAFT": "PROPOSAL",
    "IMPLEMENT_APPROVED_MECHANICS": "AUTHORIZED_IMPLEMENTATION",
    "RUN_AUTHORED_HISTORICAL_ATTEMPT": "AUTHORIZED_EXECUTION_REQUEST",
    "RUN_PREDECLARED_ROBUSTNESS": "AUTHORIZED_EXECUTION_REQUEST",
    "SUMMARIZE_EVIDENCE": "ADVISORY",
    "IDENTIFY_AND_DIAGNOSE_BUGS": "ADVISORY",
    "RED_TEAM_CANDIDATE": "ADVISORY",
    "PREPARE_FORWARD_OR_DEPLOYMENT_REVIEW_PACKAGE": "PROPOSAL",
    "ANALYZE_LIVE_DIAGNOSTICS": "ADVISORY",
}
REQUIRED_MACHINE_PROHIBITIONS = {
    "NO_SELF_APPROVAL": (
        "APPROVAL",
        {
            "APPROVE_MECHANICAL_INTERPRETATION",
            "APPROVE_HISTORICAL_CANDIDATE",
            "ACCEPT_FORWARD_REVIEW",
            "RECORD_PORTFOLIO_DISPOSITION",
        },
    ),
    "NO_LOCKED_OOS_OPEN": ("TRANSITION_INITIATION", {"OPEN_LOCKED_ACCEPTANCE_OOS"}),
    "NO_RESEARCH_VERDICT": (
        "DECISION",
        {"RECORD_HISTORICAL_SCREENING_FAILURE", "RECORD_HISTORICAL_VERDICT"},
    ),
    "NO_DEPLOYMENT_AUTHORITY": (
        "APPROVAL",
        {
            "AUTHORIZE_DEPLOYMENT",
            "PROMOTE_SHADOW_TO_SMALL_LIVE",
            "PROMOTE_SMALL_LIVE_TO_LIVE",
        },
    ),
    "NO_GATE_OVERRIDE": ("OVERRIDE", {"DETERMINISTIC_GATES", "CAMPAIGN_STOP"}),
    "NO_EVIDENCE_REWRITE": ("MUTATION", {"IMMUTABLE_RESEARCH_EVIDENCE"}),
    "NO_OOS_REDEFINITION": ("MUTATION", {"CONSUMED_OOS_OR_HOLDOUT"}),
    "NO_RETRY_UNTIL_PASS": ("EXECUTION", {"UNBUDGETED_RESCUE", "ATTEMPT_ID_REUSE"}),
    "NO_UNGOVERNED_RECERTIFICATION": (
        "CERTIFICATION",
        {"RECERTIFY_WITHOUT_GOVERNED_PROCESS"},
    ),
}
REQUIRED_DEPLOYMENT_AXIS_STATES = {
    "SCIENTIFIC_STATE": "PASS",
    "FORWARD_STATE": "ACCEPTED",
    "PORTFOLIO_STATE": "ACCEPTED",
    "ACCOUNT_SUITABILITY_STATE": "PASS",
    "IMPLEMENTATION_STATE": "CERTIFIED_CURRENT",
    "EVIDENCE_CURRENTNESS": "CURRENT",
}


@dataclass(frozen=True)
class TransitionContract:
    """Constitutional identity, edge, side-axis scope, and exact state effects."""

    initiator: str
    from_stage: str
    to_stage: str
    applicable_stages: frozenset[str] | None = None
    effects: tuple[tuple[str, str], ...] = ()


LIVE_OPERATIONAL_STAGES = frozenset({"SHADOW", "SMALL_LIVE", "LIVE"})
OPERATIONAL_SIDE_AXIS_TRANSITIONS = frozenset(
    {"APPEND_LIVE_MONITORING", "SAFETY_PAUSE", "RETIRE_LIVE_INSTANCE"}
)
CAMPAIGN_RESEARCH_STAGES = frozenset(
    {
        "APPROVED_FOR_IMPLEMENTATION",
        "IMPLEMENTATION",
        "MECHANICS_CAUSAL_REVIEW",
        "HISTORICAL_SCREENING",
        "FULL_HISTORICAL_VALIDATION",
    }
)
ACCOUNT_ASSESSMENT_STAGES = frozenset(
    {
        "HISTORICAL_CANDIDATE_REVIEW",
        "FORWARD_INCUBATION",
        "FORWARD_REVIEW",
        "PORTFOLIO_REVIEW",
        "ACCOUNT_SUITABILITY_REVIEW",
        "DEPLOYMENT_REVIEW",
    }
)
CANONICAL_TRANSITION_CONTRACT = {
    "RECORD_RESEARCH_LEAD": TransitionContract("CODEX", "DISCOVERY", "DISCOVERY"),
    "PROPOSE_HYPOTHESIS_FOR_REVIEW": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE", "DISCOVERY", "HYPOTHESIS_REVIEW"
    ),
    "ADMIT_HYPOTHESIS_FOR_IMPLEMENTATION": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "HYPOTHESIS_REVIEW", "APPROVED_FOR_IMPLEMENTATION"
    ),
    "START_IMPLEMENTATION": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "APPROVED_FOR_IMPLEMENTATION", "IMPLEMENTATION"
    ),
    "SUBMIT_MECHANICS_FOR_REVIEW": TransitionContract(
        "CODEX", "IMPLEMENTATION", "MECHANICS_CAUSAL_REVIEW"
    ),
    "APPROVE_MECHANICAL_INTERPRETATION": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "MECHANICS_CAUSAL_REVIEW", "HISTORICAL_SCREENING"
    ),
    "RUN_HISTORICAL_SCREENING": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE", "HISTORICAL_SCREENING", "FULL_HISTORICAL_VALIDATION"
    ),
    "RECORD_HISTORICAL_SCREENING_FAILURE": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE",
        "HISTORICAL_SCREENING",
        "HISTORICAL_SCREENING",
        effects=(
            ("scientific_state_effect", "FAIL"),
            ("lifecycle_effect", "terminate_bound_attempt_or_variant_path_only"),
            ("campaign_effect", "no_automatic_exhaustion"),
            ("candidate_effect", "prohibited"),
        ),
    ),
    "OPEN_LOCKED_ACCEPTANCE_OOS": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "FULL_HISTORICAL_VALIDATION", "FULL_HISTORICAL_VALIDATION"
    ),
    "RECORD_HISTORICAL_VERDICT": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE",
        "FULL_HISTORICAL_VALIDATION",
        "FULL_HISTORICAL_VALIDATION",
        effects=(
            ("lifecycle_effect", "scientific_state_only_no_candidate_status"),
            ("failure_lifecycle_effect", "terminate_bound_attempt_or_variant_path_only"),
            ("campaign_effect", "no_automatic_exhaustion"),
            ("candidate_effect", "prohibited_unless_scientific_PASS"),
        ),
    ),
    "ENTER_HISTORICAL_CANDIDATE_REVIEW": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE",
        "FULL_HISTORICAL_VALIDATION",
        "HISTORICAL_CANDIDATE_REVIEW",
    ),
    "APPROVE_HISTORICAL_CANDIDATE": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "HISTORICAL_CANDIDATE_REVIEW",
        "HISTORICAL_CANDIDATE_REVIEW",
        effects=(
            ("candidate_disposition_effect", "APPROVED_CURRENT"),
            ("lifecycle_disposition_effect", "ACTIVE"),
        ),
    ),
    "REJECT_HISTORICAL_CANDIDATE": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "HISTORICAL_CANDIDATE_REVIEW",
        "HISTORICAL_CANDIDATE_REVIEW",
        effects=(
            ("candidate_disposition_effect", "REJECTED"),
            ("lifecycle_disposition_effect", "ACTIVE"),
        ),
    ),
    "BLOCK_HISTORICAL_CANDIDATE_FOR_MANUAL_REVIEW": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "HISTORICAL_CANDIDATE_REVIEW",
        "HISTORICAL_CANDIDATE_REVIEW",
        effects=(
            ("candidate_disposition_effect", "NEEDS_MANUAL_REVIEW"),
            ("lifecycle_disposition_effect", "BLOCKED"),
        ),
    ),
    "START_FORWARD_INCUBATION": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "HISTORICAL_CANDIDATE_REVIEW", "FORWARD_INCUBATION"
    ),
    "APPEND_FORWARD_OBSERVATION": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE", "FORWARD_INCUBATION", "FORWARD_INCUBATION"
    ),
    "MARK_FORWARD_ELIGIBLE_FOR_REVIEW": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE", "FORWARD_INCUBATION", "FORWARD_REVIEW"
    ),
    "ACCEPT_FORWARD_REVIEW": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "FORWARD_REVIEW",
        "PORTFOLIO_REVIEW",
        effects=(("forward_state_effect", "ACCEPTED"),),
    ),
    "REJECT_FORWARD_REVIEW": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "FORWARD_REVIEW",
        "FORWARD_REVIEW",
        effects=(("forward_state_effect", "FAILED"),),
    ),
    "BLOCK_FORWARD_FOR_MANUAL_REVIEW": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "FORWARD_REVIEW",
        "FORWARD_REVIEW",
        effects=(
            ("forward_state_effect", "NEEDS_MANUAL_REVIEW"),
            ("lifecycle_disposition_effect", "BLOCKED"),
        ),
    ),
    "CREATE_PORTFOLIO_REVIEW": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE", "PORTFOLIO_REVIEW", "PORTFOLIO_REVIEW"
    ),
    "RECORD_PORTFOLIO_DISPOSITION": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "PORTFOLIO_REVIEW",
        "ACCOUNT_SUITABILITY_REVIEW",
        effects=(("portfolio_state_effect", "ACCEPTED"),),
    ),
    "REJECT_PORTFOLIO_DISPOSITION": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "PORTFOLIO_REVIEW",
        "PORTFOLIO_REVIEW",
        effects=(("portfolio_state_effect", "REJECTED"),),
    ),
    "BLOCK_PORTFOLIO_FOR_MANUAL_REVIEW": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "PORTFOLIO_REVIEW",
        "PORTFOLIO_REVIEW",
        effects=(
            ("portfolio_state_effect", "NEEDS_MANUAL_REVIEW"),
            ("lifecycle_disposition_effect", "BLOCKED"),
        ),
    ),
    "ASSESS_ACCOUNT_SUITABILITY": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE",
        "ACCOUNT_SUITABILITY_REVIEW",
        "ACCOUNT_SUITABILITY_REVIEW",
        ACCOUNT_ASSESSMENT_STAGES,
    ),
    "ENTER_DEPLOYMENT_REVIEW": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE", "ACCOUNT_SUITABILITY_REVIEW", "DEPLOYMENT_REVIEW"
    ),
    "AUTHORIZE_DEPLOYMENT": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "DEPLOYMENT_REVIEW", "SHADOW"
    ),
    "PROMOTE_SHADOW_TO_SMALL_LIVE": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "SHADOW", "SMALL_LIVE"
    ),
    "PROMOTE_SMALL_LIVE_TO_LIVE": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "SMALL_LIVE", "LIVE"
    ),
    "APPEND_LIVE_MONITORING": TransitionContract(
        "EXTERNAL_SYSTEM",
        "LIVE",
        "LIVE",
        LIVE_OPERATIONAL_STAGES,
        effects=(
            ("operational_state_effect", "HEALTHY_or_ALERT"),
            ("scientific_state_effect", "none"),
        ),
    ),
    "SAFETY_PAUSE": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE",
        "LIVE",
        "LIVE",
        LIVE_OPERATIONAL_STAGES,
        effects=(
            ("operational_state_effect", "PAUSED"),
            ("scientific_state_effect", "none"),
        ),
    ),
    "RETIRE_LIVE_INSTANCE": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "LIVE",
        "LIVE",
        LIVE_OPERATIONAL_STAGES,
        effects=(
            ("operational_state_effect", "STOPPED"),
            ("lifecycle_disposition_effect", "RETIRED"),
            ("scientific_state_effect", "none"),
        ),
    ),
    "STOP_CAMPAIGN_ON_PREDECLARED_RULE": TransitionContract(
        "ALPHAQUEST_DETERMINISTIC_ENGINE",
        "HISTORICAL_SCREENING",
        "HISTORICAL_SCREENING",
        CAMPAIGN_RESEARCH_STAGES,
        effects=(("lifecycle_effect", "set_disposition_EXHAUSTED_and_block_new_attempts"),),
    ),
    "DISCRETIONARILY_ABANDON_CAMPAIGN": TransitionContract(
        "HUMAN_OWNER_RESEARCHER",
        "FULL_HISTORICAL_VALIDATION",
        "FULL_HISTORICAL_VALIDATION",
        CAMPAIGN_RESEARCH_STAGES,
        effects=(("lifecycle_effect", "set_disposition_ABANDONED_and_block_new_attempts"),),
    ),
    "ABANDON_EDGE_FAMILY": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "DISCOVERY", "DISCOVERY"
    ),
    "REVISIT_FAILED_EDGE": TransitionContract(
        "HUMAN_OWNER_RESEARCHER", "DISCOVERY", "HYPOTHESIS_REVIEW"
    ),
}
CANONICAL_TRANSITION_EFFECT_FIELDS = frozenset(
    field
    for contract in CANONICAL_TRANSITION_CONTRACT.values()
    for field, _value in contract.effects
)
EXPECTED_TRANSITION_INITIATORS = {
    transition_id: contract.initiator
    for transition_id, contract in CANONICAL_TRANSITION_CONTRACT.items()
}
CANONICAL_OBJECT_MUTABILITY = {
    "OBSERVATION": "append_only_until_promoted_then_frozen",
    "HYPOTHESIS": "proposal_mutable_accepted_artifact_immutable",
    "EDGE_FAMILY": "append_only_lineage_and_disposition",
    "CAMPAIGN": "append_only_variants_attempts_and_disposition",
    "STRATEGY_VARIANT": "frozen_after_publication",
    "ATTEMPT": "pending_until_execution_then_immutable",
    "RUN": "immutable_after_completion",
    "MECHANICS_APPROVAL": "immutable_and_hash_bound",
    "HISTORICAL_VALIDATION_RESULT": "immutable",
    "CANDIDATE_STRATEGY": "immutable_review_with_currentness_recomputed",
    "FORWARD_INCUBATION_PLAN": "immutable_plan_append_only_events",
    "FORWARD_OBSERVATION": "append_only",
    "PORTFOLIO_CANDIDATE": "immutable_binding_to_current_candidate_and_forward_evidence",
    "ACCOUNT_SUITABILITY_ASSESSMENT": "immutable",
    "DEPLOYMENT_PACKAGE": "immutable_decision_new_package_for_change",
    "LIVE_STRATEGY_INSTANCE": "append_only_operations_new_package_for_semantic_or_risk_change",
}
PROTECTED_DEPLOYMENT_INGRESS = {
    "SHADOW": "AUTHORIZE_DEPLOYMENT",
    "SMALL_LIVE": "PROMOTE_SHADOW_TO_SMALL_LIVE",
    "LIVE": "PROMOTE_SMALL_LIVE_TO_LIVE",
}


class OperatingModelError(ValueError):
    """Raised when the canonical operating-model specification is inconsistent."""


def load_operating_model(
    path: str | Path = DEFAULT_OPERATING_MODEL_PATH,
) -> dict[str, Any]:
    """Load and validate the canonical P1 policy."""

    policy_path = Path(path)
    if not policy_path.is_file():
        raise FileNotFoundError(f"research operating model not found: {policy_path}")
    try:
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise OperatingModelError(f"research operating model is not valid YAML: {exc}") from exc
    policy = _mapping(raw, "operating model")
    validate_operating_model(policy)
    return policy


def operating_model_sha256(
    path: str | Path = DEFAULT_OPERATING_MODEL_PATH,
) -> str:
    """Return the byte identity paired with ``policy_version`` by consumers."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_operating_model(policy: Mapping[str, Any]) -> None:
    """Fail closed on contradictory authority, identity, or lifecycle policy."""

    document = _mapping(policy, "operating model")
    if document.get("schema") != OPERATING_MODEL_SCHEMA:
        raise OperatingModelError(f"schema must be {OPERATING_MODEL_SCHEMA}")
    if not str(document.get("policy_version") or "").strip():
        raise OperatingModelError("policy_version is required")
    if document.get("optimization_target") != "unseen_live_survival_probability":
        raise OperatingModelError("operating model must optimize unseen live survival probability")

    identity = _mapping(document.get("identity"), "identity")
    if identity.get("semantic_change_requires_new_policy_version") is not True:
        raise OperatingModelError("semantic policy changes must require a new policy version")
    if identity.get("historical_records_keep_original_policy_identity") is not True:
        raise OperatingModelError("historical records must retain their original policy identity")
    if identity.get("retroactive_rebinding_prohibited") is not True:
        raise OperatingModelError("retroactive policy rebinding must be prohibited")
    if identity.get("identity_fields") != ["schema", "policy_version", "policy_sha256"]:
        raise OperatingModelError(
            "operating-model identity must be schema, policy version, and policy content hash"
        )
    if identity.get("engine_identity_is_separate") is not True:
        raise OperatingModelError("operating-model and engine identities must remain separate")
    if identity.get("methodology_identity_is_separate") is not True:
        raise OperatingModelError("operating-model and methodology identities must remain separate")
    introduced = _mapping(identity.get("introduced_against"), "identity.introduced_against")
    for field in ("p0_engine_tag", "engine_contract", "methodology"):
        if not str(introduced.get(field) or "").strip():
            raise OperatingModelError(f"introduced-against provenance requires {field}")
    if identity.get("introduction_metadata_is_non_normative") is not True:
        raise OperatingModelError("introduced-against metadata must be non-normative provenance")
    if identity.get("current_engine_or_methodology_version_is_not_a_validation_prerequisite") is not True:
        raise OperatingModelError(
            "current engine or methodology versions cannot be operating-model validation prerequisites"
        )

    actors = _mapping(document.get("actors"), "actors")
    if set(actors) != REQUIRED_ACTORS:
        raise OperatingModelError("actors must define exactly: " + ", ".join(sorted(REQUIRED_ACTORS)))
    codex_actor = _mapping(actors["CODEX"], "actors.CODEX")
    if any(
        codex_actor.get(field) is not False
        for field in (
            "may_approve_own_work",
            "may_override_deterministic_gate",
            "may_authorize_deployment",
        )
    ):
        raise OperatingModelError("Codex cannot self-approve, override gates, or authorize deployment")
    human_actor = _mapping(actors["HUMAN_OWNER_RESEARCHER"], "actors.HUMAN_OWNER_RESEARCHER")
    if human_actor.get("may_override_missing_objective_evidence") is not False:
        raise OperatingModelError("human approval cannot override missing objective evidence")
    if human_actor.get("may_override_deterministic_gate_failure") is not False:
        raise OperatingModelError("human approval cannot override deterministic gate failure")

    objects = _indexed(document.get("research_objects"), "research_objects")
    if set(objects) != REQUIRED_OBJECTS:
        raise OperatingModelError(
            "research object model must define exactly: " + ", ".join(sorted(REQUIRED_OBJECTS))
        )
    for object_id, item in objects.items():
        owner = str(item.get("owner") or "")
        if owner not in actors:
            raise OperatingModelError(f"research object {object_id} has unknown owner {owner!r}")
        for field in (
            "represents",
            "created_when",
            "mutability",
            "evidence",
            "invalidated_by",
            "downstream",
        ):
            if field not in item:
                raise OperatingModelError(f"research object {object_id} is missing {field}")
    _require_object_mutability_contract(objects)
    _require_acyclic_object_dependencies(objects)

    axes = _mapping(document.get("state_axes"), "state_axes")
    if set(axes) != REQUIRED_STATE_AXES:
        raise OperatingModelError("state axes must define exactly: " + ", ".join(sorted(REQUIRED_STATE_AXES)))
    for axis_name, raw_axis in axes.items():
        axis = _mapping(raw_axis, f"state_axes.{axis_name}")
        values = _string_sequence(axis.get("values"), f"state_axes.{axis_name}.values")
        if len(values) != len(set(values)):
            raise OperatingModelError(f"state axis {axis_name} contains duplicate values")
    lifecycle_stages = set(axes["RESEARCH_LIFECYCLE_STAGE"]["values"])
    _require_state_axis_separation(axes)

    transitions = _indexed(document.get("transitions"), "transitions")
    for transition_id, transition in transitions.items():
        _validate_transition(transition_id, transition, actors, lifecycle_stages)
    _require_canonical_transition_contract(transitions)
    _require_transition_authority(transitions)
    _require_lifecycle_connectivity(transitions, lifecycle_stages)
    _require_review_disposition_paths(transitions)
    _require_scientific_failure_paths(transitions)
    _require_deployment_authority(transitions)
    _require_protected_deployment_ingress(transitions)
    _require_exact_deployment_prerequisites(transitions, axes)
    _require_no_historical_candidate_shortcut(transitions)
    _require_historical_verdict_boundary(
        transitions,
        _mapping(document.get("historical_verdict_policy"), "historical_verdict_policy"),
    )
    _require_account_scientific_separation(
        objects,
        transitions,
        _mapping(document.get("account_suitability_policy"), "account_suitability_policy"),
    )
    _require_campaign_termination_authority(
        transitions,
        _mapping(document.get("campaign_termination_policy"), "campaign_termination_policy"),
    )
    _validate_attempt_and_search_governance(
        _mapping(document.get("attempt_and_search_governance"), "attempt_and_search_governance")
    )
    _validate_revisit_policy(_mapping(document.get("revisit_policy"), "revisit_policy"))

    codex_policy = _mapping(document.get("codex_policy"), "codex_policy")
    permissions = _indexed(codex_policy.get("autonomous_permissions"), "codex_policy.autonomous_permissions")
    _validate_codex_permissions(permissions)
    _validate_machine_prohibitions(
        _indexed(codex_policy.get("machine_prohibitions"), "codex_policy.machine_prohibitions")
    )
    prohibitions = _indexed(codex_policy.get("prohibitions"), "codex_policy.prohibitions")
    if not REQUIRED_PROHIBITIONS.issubset(prohibitions):
        missing = sorted(REQUIRED_PROHIBITIONS - set(prohibitions))
        raise OperatingModelError("Codex prohibitions are missing: " + ", ".join(missing))

    deterministic = _mapping(document.get("deterministic_authority"), "deterministic_authority")
    decisions = set(_string_sequence(deterministic.get("decisions"), "deterministic_authority.decisions"))
    required_deterministic_decisions = {
        "PREDECLARED_NUMERICAL_STAGE_GATES",
        "IMMUTABLE_SCIENTIFIC_VERDICT_RECORDING",
        "HISTORICAL_CANDIDATE_ELIGIBILITY",
        "CANONICAL_FORWARD_EVENT_CAPTURE_AFTER_SOURCE_VALIDATION",
        "PREDECLARED_CAMPAIGN_STOP_AND_ATTEMPT_BLOCKING",
        "SAME_CONTRACT_DATA_APPEND_IDENTITY_AND_VALIDATION",
    }
    if not required_deterministic_decisions.issubset(decisions):
        raise OperatingModelError("AlphaQuest deterministic authority is incomplete")
    override = _mapping(deterministic.get("override_policy"), "deterministic_authority.override_policy")
    if override.get("codex_may_override") is not False:
        raise OperatingModelError("Codex cannot override deterministic authority")
    if override.get("human_may_override_missing_or_failed_objective_evidence") is not False:
        raise OperatingModelError("human judgment cannot override missing or failed objective evidence")

    separations = _indexed(document.get("separation_of_duties"), "separation_of_duties")
    red_team = _mapping(separations.get("EVALUATION_VS_RED_TEAM"), "EVALUATION_VS_RED_TEAM")
    if red_team.get("producer_role") == red_team.get("reviewer_or_consumer_role"):
        raise OperatingModelError("red-team ownership must differ from evaluation ownership")
    if red_team.get("required_separate_task") is not True:
        raise OperatingModelError("red-team evaluation must use a separate task")
    _require_single_human_independence(
        actors,
        separations,
        _mapping(document.get("independence_policy"), "independence_policy"),
    )
    _validate_runtime_conformance(
        transitions,
        _mapping(document.get("runtime_conformance"), "runtime_conformance"),
    )

    failed = _mapping(document.get("failed_research_policy"), "failed_research_policy")
    if failed.get("deletable") is not False or failed.get("reclassifiable_to_pass") is not False:
        raise OperatingModelError("failed research cannot be deleted or reclassified to PASS")
    if failed.get("original_verdict_remains_authoritative_for_original_run") is not True:
        raise OperatingModelError("the original run verdict must remain authoritative")

    forward = _mapping(document.get("forward_evidence_policy"), "forward_evidence_policy")
    prohibited_sources = set(
        _string_sequence(forward.get("prohibited_sources"), "forward_evidence_policy.prohibited_sources")
    )
    if "historical_backfill" not in prohibited_sources:
        raise OperatingModelError("historical backfill must be prohibited for forward evidence")
    if forward.get("strict_timestamp_order") is not True:
        raise OperatingModelError("forward evidence must have strict timestamp ordering")
    if forward.get("automatic_scientific_pass") is not False:
        raise OperatingModelError("forward incubation cannot automatically create scientific PASS")
    if forward.get("automatic_deployment_authorization") is not False:
        raise OperatingModelError("forward incubation cannot authorize deployment")
    _require_forward_evidence_custody(objects, transitions, forward)

    changes = _mapping(document.get("change_governance"), "change_governance")
    _validate_methodology_change_governance(changes)
    _validate_data_change_governance(changes)
    _validate_implementation_change_governance(changes)

    cascades = _indexed(document.get("invalidation_cascades"), "invalidation_cascades")
    for required in (
        "STRATEGY_SOURCE_CHANGE",
        "METHODOLOGY_CHANGE",
        "MATERIAL_DATA_CHANGE",
        "CONFIG_OR_PARAMETER_CHANGE",
        "PROVEN_NON_SEMANTIC_IMPLEMENTATION_CHANGE",
    ):
        if required not in cascades:
            raise OperatingModelError(f"invalidation cascade {required} is required")

    invariants = _indexed(document.get("invariants"), "invariants")
    if not REQUIRED_INVARIANTS.issubset(invariants):
        missing = sorted(REQUIRED_INVARIANTS - set(invariants))
        raise OperatingModelError("required invariants are missing: " + ", ".join(missing))


def _require_state_axis_separation(axes: Mapping[str, Any]) -> None:
    scientific = set(axes["SCIENTIFIC_STATE"]["values"])
    account = set(axes["ACCOUNT_SUITABILITY_STATE"]["values"])
    deployment = set(axes["DEPLOYMENT_STATE"]["values"])
    lifecycle = set(axes["RESEARCH_LIFECYCLE_STAGE"]["values"])
    forward = set(axes["FORWARD_STATE"]["values"])
    if not {"PASS", "FAIL", "NEEDS_MANUAL_REVIEW"}.issubset(scientific):
        raise OperatingModelError("scientific state must retain PASS, FAIL, and NEEDS_MANUAL_REVIEW")
    if not {"PASS", "FAIL", "NEEDS_MANUAL_REVIEW"}.issubset(account):
        raise OperatingModelError("account suitability must be an exact-profile decision axis")
    if "PASS" in deployment or "FAIL" in deployment:
        raise OperatingModelError("deployment state must not collapse into scientific PASS/FAIL")
    if "MONITORING" in lifecycle:
        raise OperatingModelError("monitoring must be represented only by OPERATIONAL_STATE")
    if "ACCEPTED" not in forward:
        raise OperatingModelError("forward state must represent accepted human review explicitly")


def _require_object_mutability_contract(
    objects: Mapping[str, Mapping[str, Any]],
) -> None:
    if set(objects) != set(CANONICAL_OBJECT_MUTABILITY):
        raise OperatingModelError("canonical research-object mutability set is incomplete")
    for object_id, expected_mutability in CANONICAL_OBJECT_MUTABILITY.items():
        actual_mutability = objects[object_id].get("mutability")
        if actual_mutability != expected_mutability:
            raise OperatingModelError(
                f"research object {object_id} mutability must remain "
                f"{expected_mutability!r}; immutable history and currentness are separate"
            )


def _require_acyclic_object_dependencies(
    objects: Mapping[str, Mapping[str, Any]],
) -> None:
    graph: dict[str, list[str]] = {}
    for object_id, item in objects.items():
        downstream = _string_sequence(
            item.get("downstream"),
            f"research_objects.{object_id}.downstream",
            allow_empty=True,
        )
        unknown = sorted(set(downstream) - set(objects))
        if unknown:
            raise OperatingModelError(
                f"research object {object_id} has unknown downstream references: "
                + ", ".join(unknown)
            )
        graph[object_id] = downstream
    active: list[str] = []
    visited: set[str] = set()

    def visit(object_id: str) -> None:
        if object_id in active:
            cycle = active[active.index(object_id) :] + [object_id]
            raise OperatingModelError(
                "research object dependencies must be acyclic: " + " -> ".join(cycle)
            )
        if object_id in visited:
            return
        active.append(object_id)
        for dependency in graph[object_id]:
            visit(dependency)
        active.pop()
        visited.add(object_id)

    for object_id in graph:
        visit(object_id)


def _validate_transition(
    transition_id: str,
    transition: Mapping[str, Any],
    actors: Mapping[str, Any],
    lifecycle_stages: set[str],
) -> None:
    required_fields = {
        "from_stage",
        "to_stage",
        "initiator",
        "evidence_required",
        "deterministic_checks",
        "codex",
        "human_approval_required",
        "alphaquest_automatic",
        "reversible",
        "invalidated_by",
        "implementation_status",
    }
    missing = sorted(required_fields - set(transition))
    if missing:
        raise OperatingModelError(f"transition {transition_id} is missing: {', '.join(missing)}")
    for field in ("from_stage", "to_stage"):
        if transition[field] not in lifecycle_stages:
            raise OperatingModelError(
                f"transition {transition_id} references unknown {field} {transition[field]!r}"
            )
    if transition["initiator"] not in actors:
        raise OperatingModelError(f"transition {transition_id} has an unknown initiator")
    if "source_actor" in transition and transition["source_actor"] not in actors:
        raise OperatingModelError(f"transition {transition_id} has an unknown source_actor")
    for field in ("human_approval_required", "alphaquest_automatic", "reversible"):
        if not isinstance(transition[field], bool):
            raise OperatingModelError(f"transition {transition_id}.{field} must be boolean")
    _string_sequence(transition["evidence_required"], f"transition {transition_id}.evidence_required")
    _string_sequence(transition["deterministic_checks"], f"transition {transition_id}.deterministic_checks")
    _string_sequence(
        transition["invalidated_by"],
        f"transition {transition_id}.invalidated_by",
        allow_empty=True,
    )
    if "applicable_stages" in transition:
        applicable = set(
            _string_sequence(
                transition["applicable_stages"],
                f"transition {transition_id}.applicable_stages",
            )
        )
        unknown = sorted(applicable - lifecycle_stages)
        if unknown:
            raise OperatingModelError(
                f"transition {transition_id} has unknown applicable stages: {', '.join(unknown)}"
            )
    codex_mode = transition.get("codex")
    if codex_mode not in CODEX_TRANSITION_MODES:
        raise OperatingModelError(f"transition {transition_id} has unknown Codex authority mode")
    implementation_status = transition.get("implementation_status")
    if implementation_status not in IMPLEMENTATION_STATUSES:
        raise OperatingModelError(
            f"transition {transition_id} has unknown implementation status {implementation_status!r}"
        )
    conformance = transition.get("runtime_conformance")
    if implementation_status == "EXISTING_PARTIAL":
        details = _mapping(conformance, f"transition {transition_id}.runtime_conformance")
        if set(details) != PARTIAL_CONFORMANCE_FIELDS:
            raise OperatingModelError(
                f"transition {transition_id} partial runtime conformance fields are incomplete or unexpected"
            )
        for field in PARTIAL_CONFORMANCE_FIELDS - {"migration_required"}:
            if not str(details.get(field) or "").strip():
                raise OperatingModelError(f"transition {transition_id} requires non-empty {field}")
        if details.get("migration_required") is not True:
            raise OperatingModelError(f"transition {transition_id} partial status requires migration")
        if transition.get("runtime_enforcement_claimed") is True:
            raise OperatingModelError(f"transition {transition_id} cannot claim full runtime enforcement")
    elif conformance is not None:
        raise OperatingModelError(
            f"transition {transition_id} may declare a runtime gap only as EXISTING_PARTIAL"
        )
    if implementation_status == "POLICY_ONLY":
        if transition.get("runtime_enforcement_claimed") is not False:
            raise OperatingModelError(
                f"transition {transition_id} POLICY_ONLY must disclaim runtime enforcement"
            )
    elif "runtime_enforcement_claimed" in transition:
        raise OperatingModelError(
            f"transition {transition_id} may use runtime_enforcement_claimed only as POLICY_ONLY"
        )


def _require_canonical_transition_contract(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    actual_ids = set(transitions)
    canonical_ids = set(CANONICAL_TRANSITION_CONTRACT)
    if actual_ids != canonical_ids:
        missing = sorted(canonical_ids - actual_ids)
        unknown = sorted(actual_ids - canonical_ids)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise OperatingModelError(
            "canonical transition set mismatch: " + "; ".join(details)
        )

    for transition_id, contract in CANONICAL_TRANSITION_CONTRACT.items():
        transition = transitions[transition_id]
        actual_edge = (transition.get("from_stage"), transition.get("to_stage"))
        expected_edge = (contract.from_stage, contract.to_stage)
        if actual_edge != expected_edge:
            raise OperatingModelError(
                f"canonical transition {transition_id} must be "
                f"{contract.from_stage} -> {contract.to_stage}"
            )
        has_applicable_stages = "applicable_stages" in transition
        if contract.applicable_stages is None:
            if has_applicable_stages:
                raise OperatingModelError(
                    f"canonical transition {transition_id} cannot declare applicable_stages"
                )
        elif set(transition.get("applicable_stages") or []) != contract.applicable_stages:
            raise OperatingModelError(
                f"canonical transition {transition_id} applicable_stages must remain exact"
            )
        unknown_effect_fields = sorted(
            field
            for field in transition
            if field.endswith("_effect") and field not in CANONICAL_TRANSITION_EFFECT_FIELDS
        )
        if unknown_effect_fields:
            raise OperatingModelError(
                f"canonical transition {transition_id} declares unknown state-effect fields: "
                + ", ".join(unknown_effect_fields)
            )
        expected_effects = dict(contract.effects)
        actual_effects = {
            field: transition[field]
            for field in CANONICAL_TRANSITION_EFFECT_FIELDS
            if field in transition
        }
        if actual_effects != expected_effects:
            raise OperatingModelError(
                f"canonical transition {transition_id} effect contract must remain exact"
            )


def _require_transition_authority(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    for transition_id, transition in transitions.items():
        initiator = transition.get("initiator")
        expected_initiator = EXPECTED_TRANSITION_INITIATORS[transition_id]
        if initiator != expected_initiator:
            raise OperatingModelError(
                f"transition {transition_id} must remain owned by "
                f"{expected_initiator}"
            )
        automatic = transition.get("alphaquest_automatic")
        human_gate = transition.get("human_approval_required")
        if initiator == "HUMAN_OWNER_RESEARCHER" and automatic is not False:
            raise OperatingModelError(f"human transition {transition_id} cannot be AlphaQuest-automatic")
        if initiator in {"ALPHAQUEST_DETERMINISTIC_ENGINE", "EXTERNAL_SYSTEM"}:
            if automatic is not True or human_gate is not False:
                raise OperatingModelError(
                    f"deterministic transition {transition_id} must be automatic without human approval"
                )
        if initiator == "CODEX" and (automatic is not False or human_gate is not False):
            raise OperatingModelError(
                f"Codex proposal transition {transition_id} cannot approve or execute automatically"
            )

    for transition_id, codex_mode in CRITICAL_HUMAN_TRANSITION_AUTHORITY.items():
        transition = _mapping(transitions.get(transition_id), transition_id)
        if transition.get("initiator") != "HUMAN_OWNER_RESEARCHER":
            raise OperatingModelError(f"{transition_id} must be initiated by the human owner")
        if transition.get("human_approval_required") is not True:
            raise OperatingModelError(f"{transition_id} must require human approval")
        if transition.get("alphaquest_automatic") is not False:
            raise OperatingModelError(f"{transition_id} cannot be automatic")
        if transition.get("codex") != codex_mode:
            raise OperatingModelError(f"Codex cannot approve or initiate {transition_id}")

    deterministic_decisions = {
        "RUN_HISTORICAL_SCREENING",
        "RECORD_HISTORICAL_SCREENING_FAILURE",
        "RECORD_HISTORICAL_VERDICT",
        "ENTER_HISTORICAL_CANDIDATE_REVIEW",
        "APPEND_FORWARD_OBSERVATION",
        "MARK_FORWARD_ELIGIBLE_FOR_REVIEW",
        "CREATE_PORTFOLIO_REVIEW",
        "ASSESS_ACCOUNT_SUITABILITY",
        "ENTER_DEPLOYMENT_REVIEW",
        "SAFETY_PAUSE",
        "STOP_CAMPAIGN_ON_PREDECLARED_RULE",
    }
    for transition_id in deterministic_decisions:
        transition = _mapping(transitions.get(transition_id), transition_id)
        if transition.get("initiator") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
            raise OperatingModelError(f"deterministic transition {transition_id} must remain AlphaQuest-owned")
        if str(transition.get("codex") or "").startswith("ALLOWED_AFTER"):
            raise OperatingModelError(
                f"deterministic transition {transition_id} cannot become discretionary Codex authority"
            )


def _require_lifecycle_connectivity(
    transitions: Mapping[str, Mapping[str, Any]],
    lifecycle_stages: set[str],
) -> None:
    required_edges = {
        "PROPOSE_HYPOTHESIS_FOR_REVIEW": ("DISCOVERY", "HYPOTHESIS_REVIEW"),
        "ADMIT_HYPOTHESIS_FOR_IMPLEMENTATION": (
            "HYPOTHESIS_REVIEW",
            "APPROVED_FOR_IMPLEMENTATION",
        ),
        "START_IMPLEMENTATION": ("APPROVED_FOR_IMPLEMENTATION", "IMPLEMENTATION"),
        "SUBMIT_MECHANICS_FOR_REVIEW": ("IMPLEMENTATION", "MECHANICS_CAUSAL_REVIEW"),
        "APPROVE_MECHANICAL_INTERPRETATION": (
            "MECHANICS_CAUSAL_REVIEW",
            "HISTORICAL_SCREENING",
        ),
        "RUN_HISTORICAL_SCREENING": (
            "HISTORICAL_SCREENING",
            "FULL_HISTORICAL_VALIDATION",
        ),
        "ENTER_HISTORICAL_CANDIDATE_REVIEW": (
            "FULL_HISTORICAL_VALIDATION",
            "HISTORICAL_CANDIDATE_REVIEW",
        ),
        "START_FORWARD_INCUBATION": ("HISTORICAL_CANDIDATE_REVIEW", "FORWARD_INCUBATION"),
        "MARK_FORWARD_ELIGIBLE_FOR_REVIEW": ("FORWARD_INCUBATION", "FORWARD_REVIEW"),
        "ACCEPT_FORWARD_REVIEW": ("FORWARD_REVIEW", "PORTFOLIO_REVIEW"),
        "RECORD_PORTFOLIO_DISPOSITION": ("PORTFOLIO_REVIEW", "ACCOUNT_SUITABILITY_REVIEW"),
        "ENTER_DEPLOYMENT_REVIEW": ("ACCOUNT_SUITABILITY_REVIEW", "DEPLOYMENT_REVIEW"),
        "AUTHORIZE_DEPLOYMENT": ("DEPLOYMENT_REVIEW", "SHADOW"),
        "PROMOTE_SHADOW_TO_SMALL_LIVE": ("SHADOW", "SMALL_LIVE"),
        "PROMOTE_SMALL_LIVE_TO_LIVE": ("SMALL_LIVE", "LIVE"),
    }
    for transition_id, expected_edge in required_edges.items():
        transition = _mapping(transitions.get(transition_id), transition_id)
        actual_edge = (transition.get("from_stage"), transition.get("to_stage"))
        if actual_edge != expected_edge:
            raise OperatingModelError(
                f"lifecycle transition {transition_id} must be {expected_edge[0]} -> {expected_edge[1]}"
            )
    forward_start = _mapping(transitions.get("START_FORWARD_INCUBATION"), "START_FORWARD_INCUBATION")
    if "approved_candidate_review" not in set(forward_start.get("evidence_required") or []):
        raise OperatingModelError("forward incubation requires an approved candidate review")
    if "candidate_current" not in set(forward_start.get("deterministic_checks") or []):
        raise OperatingModelError("forward incubation requires a current accepted candidate")
    if "MONITORING" in lifecycle_stages:
        raise OperatingModelError("MONITORING cannot remain a research lifecycle stage")
    for transition_id in ("APPEND_LIVE_MONITORING", "SAFETY_PAUSE", "RETIRE_LIVE_INSTANCE"):
        transition = _mapping(transitions.get(transition_id), transition_id)
        if transition.get("from_stage") != "LIVE" or transition.get("to_stage") != "LIVE":
            raise OperatingModelError(f"{transition_id} must update operational state without lifecycle advance")
        if set(transition.get("applicable_stages") or []) != {"SHADOW", "SMALL_LIVE", "LIVE"}:
            raise OperatingModelError(f"{transition_id} must cover shadow, small-live, and live monitoring")
        if transition.get("scientific_state_effect") != "none":
            raise OperatingModelError(f"{transition_id} cannot create scientific validity")


def _require_review_disposition_paths(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    expected = {
        "APPROVE_HISTORICAL_CANDIDATE": (
            "HISTORICAL_CANDIDATE_REVIEW",
            "APPROVED_CURRENT",
            True,
        ),
        "REJECT_HISTORICAL_CANDIDATE": ("HISTORICAL_CANDIDATE_REVIEW", "REJECTED", False),
        "BLOCK_HISTORICAL_CANDIDATE_FOR_MANUAL_REVIEW": (
            "HISTORICAL_CANDIDATE_REVIEW",
            "NEEDS_MANUAL_REVIEW",
            False,
        ),
        "ACCEPT_FORWARD_REVIEW": ("PORTFOLIO_REVIEW", "ACCEPTED", True),
        "REJECT_FORWARD_REVIEW": ("FORWARD_REVIEW", "FAILED", False),
        "BLOCK_FORWARD_FOR_MANUAL_REVIEW": ("FORWARD_REVIEW", "NEEDS_MANUAL_REVIEW", False),
        "RECORD_PORTFOLIO_DISPOSITION": ("ACCOUNT_SUITABILITY_REVIEW", "ACCEPTED", True),
        "REJECT_PORTFOLIO_DISPOSITION": ("PORTFOLIO_REVIEW", "REJECTED", False),
        "BLOCK_PORTFOLIO_FOR_MANUAL_REVIEW": (
            "PORTFOLIO_REVIEW",
            "NEEDS_MANUAL_REVIEW",
            False,
        ),
    }
    effect_fields = {
        "APPROVE_HISTORICAL_CANDIDATE": "candidate_disposition_effect",
        "REJECT_HISTORICAL_CANDIDATE": "candidate_disposition_effect",
        "BLOCK_HISTORICAL_CANDIDATE_FOR_MANUAL_REVIEW": "candidate_disposition_effect",
        "ACCEPT_FORWARD_REVIEW": "forward_state_effect",
        "REJECT_FORWARD_REVIEW": "forward_state_effect",
        "BLOCK_FORWARD_FOR_MANUAL_REVIEW": "forward_state_effect",
        "RECORD_PORTFOLIO_DISPOSITION": "portfolio_state_effect",
        "REJECT_PORTFOLIO_DISPOSITION": "portfolio_state_effect",
        "BLOCK_PORTFOLIO_FOR_MANUAL_REVIEW": "portfolio_state_effect",
    }
    for transition_id, (expected_target, expected_effect, advances) in expected.items():
        transition = _mapping(transitions.get(transition_id), transition_id)
        if transition.get("to_stage") != expected_target:
            raise OperatingModelError(f"review disposition {transition_id} has an unsafe lifecycle target")
        field = effect_fields[transition_id]
        if transition.get(field) != expected_effect:
            raise OperatingModelError(f"review disposition {transition_id} has the wrong state effect")
        if advances:
            continue
        if transition.get("from_stage") != transition.get("to_stage"):
            raise OperatingModelError(f"rejected or blocked disposition {transition_id} cannot advance")
        if transition.get("advances_normal_path") is not False:
            raise OperatingModelError(f"rejected or blocked disposition {transition_id} must block advance")
        if expected_effect == "NEEDS_MANUAL_REVIEW" and transition.get(
            "lifecycle_disposition_effect"
        ) != "BLOCKED":
            raise OperatingModelError(f"manual-review disposition {transition_id} must remain blocked")


def _require_scientific_failure_paths(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    screening = _mapping(
        transitions.get("RECORD_HISTORICAL_SCREENING_FAILURE"),
        "RECORD_HISTORICAL_SCREENING_FAILURE",
    )
    if set(screening.get("failure_stages") or []) != {"limited_core_grid", "limited_monkey"}:
        raise OperatingModelError("screening failure path must cover limited core grid and monkey")
    if set(screening.get("evidence_required") or []) != {
        "immutable_failed_stage_result",
        "bound_attempt_identity",
        "complete_search_history",
    }:
        raise OperatingModelError("screening failure must preserve immutable evidence and search history")
    if screening.get("scientific_state_effect") != "FAIL":
        raise OperatingModelError("screening failure must record scientific FAIL")
    if screening.get("lifecycle_effect") != "terminate_bound_attempt_or_variant_path_only":
        raise OperatingModelError("screening failure must terminate only its bound path")
    if screening.get("campaign_effect") != "no_automatic_exhaustion":
        raise OperatingModelError("screening failure cannot automatically exhaust its campaign")
    if screening.get("candidate_effect") != "prohibited":
        raise OperatingModelError("screening failure cannot create candidate status")

    full = _mapping(transitions.get("RECORD_HISTORICAL_VERDICT"), "RECORD_HISTORICAL_VERDICT")
    if set(full.get("deterministic_failure_stages") or []) != {
        "walk_forward_analysis",
        "monte_carlo",
        "acceptance",
    }:
        raise OperatingModelError("full-validation failure path must cover WFA, Monte Carlo, and acceptance")
    if full.get("failure_lifecycle_effect") != "terminate_bound_attempt_or_variant_path_only":
        raise OperatingModelError("full-validation FAIL must terminate only its bound path")
    if full.get("campaign_effect") != "no_automatic_exhaustion":
        raise OperatingModelError("full-validation FAIL cannot automatically exhaust its campaign")
    if full.get("candidate_effect") != "prohibited_unless_scientific_PASS":
        raise OperatingModelError("full-validation failure cannot create candidate status")


def _require_deployment_authority(transitions: Mapping[str, Mapping[str, Any]]) -> None:
    for transition_id in (
        "AUTHORIZE_DEPLOYMENT",
        "PROMOTE_SHADOW_TO_SMALL_LIVE",
        "PROMOTE_SMALL_LIVE_TO_LIVE",
    ):
        transition = _mapping(transitions.get(transition_id), transition_id)
        if transition.get("initiator") != "HUMAN_OWNER_RESEARCHER":
            raise OperatingModelError(f"{transition_id} must be initiated by the human owner")
        if transition.get("human_approval_required") is not True:
            raise OperatingModelError(f"{transition_id} must require human approval")
        if transition.get("codex") != "PROHIBITED":
            raise OperatingModelError(f"Codex must be prohibited from {transition_id}")
        if transition.get("alphaquest_automatic") is not False:
            raise OperatingModelError(f"{transition_id} cannot be automatic")


def _require_protected_deployment_ingress(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    for transition_id, transition in transitions.items():
        destination = transition.get("to_stage")
        if destination not in PROTECTED_DEPLOYMENT_INGRESS:
            continue
        if transition_id in OPERATIONAL_SIDE_AXIS_TRANSITIONS:
            if (
                transition.get("from_stage") != "LIVE"
                or transition.get("to_stage") != "LIVE"
                or set(transition.get("applicable_stages") or []) != LIVE_OPERATIONAL_STAGES
            ):
                raise OperatingModelError(
                    f"operational side-axis transition {transition_id} cannot create live ingress"
                )
            continue
        authorized_transition = PROTECTED_DEPLOYMENT_INGRESS[destination]
        if transition_id != authorized_transition:
            raise OperatingModelError(
                f"only {authorized_transition} may enter protected stage {destination}"
            )
        if transition.get("initiator") != "HUMAN_OWNER_RESEARCHER":
            raise OperatingModelError(
                f"protected stage {destination} requires human-owned ingress"
            )


def _require_exact_deployment_prerequisites(
    transitions: Mapping[str, Mapping[str, Any]],
    axes: Mapping[str, Any],
) -> None:
    for transition_id in ("ENTER_DEPLOYMENT_REVIEW", "AUTHORIZE_DEPLOYMENT"):
        transition = _mapping(transitions.get(transition_id), transition_id)
        required_states = _mapping(
            transition.get("required_axis_states"),
            f"{transition_id}.required_axis_states",
        )
        if required_states != REQUIRED_DEPLOYMENT_AXIS_STATES:
            raise OperatingModelError(
                f"{transition_id} must require exact positive deployment axis states"
            )
        for axis_name, state in required_states.items():
            values = set(_mapping(axes.get(axis_name), axis_name).get("values") or [])
            if state not in values:
                raise OperatingModelError(
                    f"{transition_id} requires unknown {axis_name} value {state!r}"
                )
        if transition.get("required_candidate_status") != "APPROVED_CURRENT":
            raise OperatingModelError(f"{transition_id} must require an approved current candidate")
    authorization = _mapping(transitions.get("AUTHORIZE_DEPLOYMENT"), "AUTHORIZE_DEPLOYMENT")
    if set(authorization.get("required_deployment_controls") or []) != {
        "limits",
        "allocation",
        "kill_rules",
    }:
        raise OperatingModelError(
            "deployment authorization requires complete limits, allocation, and kill rules"
        )
    if "deployment_controls_complete_and_valid" not in set(
        authorization.get("deterministic_checks") or []
    ):
        raise OperatingModelError("deployment controls must be deterministically validated")


def _require_no_historical_candidate_shortcut(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    forbidden_targets = {"SHADOW", "SMALL_LIVE", "LIVE"}
    for transition_id, transition in transitions.items():
        if (
            transition.get("from_stage") == "HISTORICAL_CANDIDATE_REVIEW"
            and transition.get("to_stage") in forbidden_targets
        ):
            raise OperatingModelError(
                f"transition {transition_id} shortcuts historical candidate status to live authorization"
            )


def _require_historical_verdict_boundary(
    transitions: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> None:
    terminal_outcomes = {"PASS", "FAIL", "NEEDS_MANUAL_REVIEW"}
    record = _mapping(
        transitions.get("RECORD_HISTORICAL_VERDICT"),
        "RECORD_HISTORICAL_VERDICT",
    )
    if record.get("from_stage") != "FULL_HISTORICAL_VALIDATION" or record.get(
        "to_stage"
    ) != "FULL_HISTORICAL_VALIDATION":
        raise OperatingModelError(
            "historical verdict recording must remain in full historical validation"
        )
    if set(record.get("terminal_scientific_outcomes") or []) != terminal_outcomes:
        raise OperatingModelError("historical verdict recording must preserve all terminal outcomes")
    if record.get("lifecycle_effect") != "scientific_state_only_no_candidate_status":
        raise OperatingModelError("historical verdict recording cannot create candidate status")

    enter = _mapping(
        transitions.get("ENTER_HISTORICAL_CANDIDATE_REVIEW"),
        "ENTER_HISTORICAL_CANDIDATE_REVIEW",
    )
    if enter.get("from_stage") != "FULL_HISTORICAL_VALIDATION" or enter.get(
        "to_stage"
    ) != "HISTORICAL_CANDIDATE_REVIEW":
        raise OperatingModelError("candidate review entry must be a distinct lifecycle transition")
    if enter.get("initiator") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("candidate review eligibility must be decided by AlphaQuest")
    if enter.get("human_approval_required") is not False or enter.get(
        "alphaquest_automatic"
    ) is not True:
        raise OperatingModelError("eligible candidate review entry must be deterministic")
    if set(enter.get("eligible_scientific_states") or []) != {"PASS"}:
        raise OperatingModelError("only scientific PASS may enter historical candidate review")
    if set(enter.get("ineligible_scientific_states") or []) != {
        "FAIL",
        "NEEDS_MANUAL_REVIEW",
    }:
        raise OperatingModelError("FAIL and NEEDS_MANUAL_REVIEW must be ineligible for candidate review")
    required_evidence = {"immutable_historical_verdict", "scientific_pass", "predeclared_candidate_eligibility"}
    required_checks = {
        "verdict_is_scientific_pass",
        "no_unresolved_manual_review",
        "candidate_eligibility_prerequisites_pass",
    }
    if not required_evidence.issubset(set(enter.get("evidence_required") or [])):
        raise OperatingModelError("candidate review entry evidence is incomplete")
    if not required_checks.issubset(set(enter.get("deterministic_checks") or [])):
        raise OperatingModelError("candidate review entry checks are incomplete")
    for transition_id, transition in transitions.items():
        if (
            transition.get("to_stage") == "HISTORICAL_CANDIDATE_REVIEW"
            and transition.get("from_stage") != "HISTORICAL_CANDIDATE_REVIEW"
            and transition_id != "ENTER_HISTORICAL_CANDIDATE_REVIEW"
        ):
            raise OperatingModelError(
                f"transition {transition_id} bypasses governed candidate review entry"
            )

    if set(policy.get("terminal_scientific_outcomes") or []) != terminal_outcomes:
        raise OperatingModelError("historical verdict policy must preserve all terminal outcomes")
    if policy.get("recording_advances_lifecycle") is not False or policy.get(
        "recording_creates_candidate_status"
    ) is not False:
        raise OperatingModelError("recording a historical verdict cannot advance lifecycle")
    if policy.get("candidate_review_required_scientific_state") != "PASS":
        raise OperatingModelError("candidate review policy must require scientific PASS")
    if set(policy.get("candidate_review_prohibited_scientific_states") or []) != {
        "FAIL",
        "NEEDS_MANUAL_REVIEW",
    }:
        raise OperatingModelError("candidate review policy must prohibit FAIL and NEEDS_MANUAL_REVIEW")
    if policy.get("needs_manual_review_resolution") != (
        "governed_new_or_completed_evidence_with_distinct_identity_and_scientific_pass"
    ):
        raise OperatingModelError("NEEDS_MANUAL_REVIEW requires governed resolution")
    if policy.get("original_verdict_is_immutable") is not True:
        raise OperatingModelError("historical verdict resolution cannot rewrite the original verdict")


def _require_account_scientific_separation(
    objects: Mapping[str, Mapping[str, Any]],
    transitions: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> None:
    candidate = _mapping(objects.get("CANDIDATE_STRATEGY"), "CANDIDATE_STRATEGY")
    account = _mapping(
        objects.get("ACCOUNT_SUITABILITY_ASSESSMENT"),
        "ACCOUNT_SUITABILITY_ASSESSMENT",
    )
    candidate_creation = str(candidate.get("created_when") or "").casefold()
    if "account" in candidate_creation or "suitability" in candidate_creation:
        raise OperatingModelError("candidate creation cannot depend on account suitability")
    if "CANDIDATE_STRATEGY" in set(account.get("downstream") or []):
        raise OperatingModelError("account suitability cannot point downstream to Candidate Strategy")

    if policy.get("relationship_to_lifecycle") != "independent_side_axis":
        raise OperatingModelError("account suitability must be an independent side axis")
    if policy.get("may_be_computed_before_normal_gate") is not True:
        raise OperatingModelError("account suitability may be computed before its normal deployment gate")
    prerequisites = set(policy.get("prerequisites") or [])
    if not {
        "scientific_pass",
        "sufficient_appropriate_unseen_evidence",
        "exact_versioned_account_profile",
    }.issubset(prerequisites):
        raise OperatingModelError("account suitability prerequisites are incomplete")
    if policy.get("writes_only") != "ACCOUNT_SUITABILITY_STATE":
        raise OperatingModelError("account suitability may write only its own state axis")
    cannot_create = set(policy.get("cannot_create") or [])
    if not {"SCIENTIFIC_STATE", "CANDIDATE_STRATEGY", "DEPLOYMENT_STATE"}.issubset(
        cannot_create
    ):
        raise OperatingModelError("account suitability cannot manufacture candidate or scientific state")

    candidate_approval = _mapping(
        transitions.get("APPROVE_HISTORICAL_CANDIDATE"),
        "APPROVE_HISTORICAL_CANDIDATE",
    )
    candidate_evidence = " ".join(candidate_approval.get("evidence_required") or []).casefold()
    if "account" in candidate_evidence or "suitability" in candidate_evidence:
        raise OperatingModelError("historical candidate approval cannot depend on account suitability")

    assessment = _mapping(transitions.get("ASSESS_ACCOUNT_SUITABILITY"), "ASSESS_ACCOUNT_SUITABILITY")
    evidence = set(assessment.get("evidence_required") or [])
    checks = set(assessment.get("deterministic_checks") or [])
    if "scientific_pass" not in evidence or "scientific_pass_first" not in checks:
        raise OperatingModelError("account suitability must require scientific PASS first")
    if assessment.get("side_axis") != "ACCOUNT_SUITABILITY_STATE":
        raise OperatingModelError("account assessment must declare its side-axis effect")
    if assessment.get("from_stage") != assessment.get("to_stage"):
        raise OperatingModelError("account assessment cannot itself advance lifecycle stage")
    transition_cannot_create = set(assessment.get("cannot_create") or [])
    if not {"SCIENTIFIC_STATE", "CANDIDATE_STRATEGY", "DEPLOYMENT_STATE"}.issubset(
        transition_cannot_create
    ):
        raise OperatingModelError("account assessment transition can manufacture forbidden state")


def _require_campaign_termination_authority(
    transitions: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> None:
    stop = _mapping(
        transitions.get("STOP_CAMPAIGN_ON_PREDECLARED_RULE"),
        "STOP_CAMPAIGN_ON_PREDECLARED_RULE",
    )
    if stop.get("initiator") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("deterministic campaign stop must be initiated by AlphaQuest")
    if stop.get("human_approval_required") is not False or stop.get("alphaquest_automatic") is not True:
        raise OperatingModelError("deterministic campaign stop must be automatic without human approval")
    if stop.get("scope") != "campaign":
        raise OperatingModelError("deterministic campaign stop must have campaign scope")
    stop_evidence = set(stop.get("evidence_required") or [])
    stop_checks = set(stop.get("deterministic_checks") or [])
    if "predeclared_campaign_level_termination_rule" not in stop_evidence:
        raise OperatingModelError("campaign stop requires a campaign-level termination rule")
    if not {"termination_rule_scope_is_campaign", "campaign_level_condition_satisfied"}.issubset(
        stop_checks
    ):
        raise OperatingModelError("campaign stop must verify a campaign-level condition")
    stop_effect = str(stop.get("lifecycle_effect") or "")
    if "EXHAUSTED" not in stop_effect or "block_new_attempts" not in stop_effect:
        raise OperatingModelError(
            "deterministic campaign stop must set EXHAUSTED and block new attempts"
        )

    deterministic = _mapping(policy.get("deterministic_stop"), "deterministic_stop")
    if deterministic.get("authority") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("deterministic stop policy must assign AlphaQuest authority")
    if deterministic.get("requires_human_approval") is not False:
        raise OperatingModelError("deterministic stop policy cannot require human approval")
    if deterministic.get("rule_must_be_predeclared") is not True:
        raise OperatingModelError("deterministic campaign stop rules must be predeclared")
    if deterministic.get("scope") != "campaign_level_only":
        raise OperatingModelError("EXHAUSTED must be limited to campaign-level rules")
    criteria = set(deterministic.get("criteria") or [])
    required_criteria = {
        "governed_variant_budget_exhausted",
        "campaign_research_or_search_budget_exhausted",
        "campaign_fresh_holdout_budget_exhausted",
        "campaign_opportunity_frequency_structurally_infeasible_under_predeclared_requirement",
        "required_data_or_fidelity_structurally_unavailable_for_campaign",
        "execution_infeasibility_applies_to_campaign_hypothesis_or_mechanical_family",
        "explicit_predeclared_campaign_level_termination_contract_satisfied",
    }
    if criteria != required_criteria:
        raise OperatingModelError("campaign exhaustion criteria are incomplete or unexpected")
    forbidden_variant_stop_criteria = {
        "failed_predeclared_core_screening_gate",
        "deterministic_stage_gate_failure",
    }
    if criteria & forbidden_variant_stop_criteria:
        raise OperatingModelError("a single variant stage failure cannot exhaust a campaign")

    variant_failure = _mapping(policy.get("variant_failure"), "variant_failure")
    if variant_failure.get("automatically_exhausts_campaign") is not False:
        raise OperatingModelError("variant failure cannot automatically exhaust a campaign")
    if not {"core_grid", "monkey", "walk_forward_analysis", "monte_carlo", "acceptance"}.issubset(
        set(variant_failure.get("limited_stage_failures") or [])
    ):
        raise OperatingModelError("variant-local stage failure policy is incomplete")
    successor_conditions = set(variant_failure.get("successor_may_remain_when") or [])
    if not {
        "terminal_predecessor_FAIL_is_current",
        "authorized_variant_budget_remains",
        "no_campaign_level_stop_rule_is_satisfied",
        "successor_mechanics_are_materially_distinct_and_same_hypothesis",
    }.issubset(successor_conditions):
        raise OperatingModelError("governed successor-variant conditions are incomplete")
    if set(variant_failure.get("effects") or []) != {
        "preserve_terminal_failure_and_search_history",
        "stop_the_bound_attempt_or_variant_path",
        "do_not_create_candidate_status",
    }:
        raise OperatingModelError("variant failure effects must preserve history and terminate only its path")

    for transition_id in (
        "DISCRETIONARILY_ABANDON_CAMPAIGN",
        "ABANDON_EDGE_FAMILY",
        "REVISIT_FAILED_EDGE",
    ):
        transition = _mapping(transitions.get(transition_id), transition_id)
        if transition.get("initiator") != "HUMAN_OWNER_RESEARCHER":
            raise OperatingModelError(f"{transition_id} must be initiated by the human owner")
        if transition.get("human_approval_required") is not True:
            raise OperatingModelError(f"{transition_id} must remain human-gated")
        if transition.get("alphaquest_automatic") is not False:
            raise OperatingModelError(f"{transition_id} cannot be automatic")

    discretionary = _mapping(
        policy.get("discretionary_abandonment"),
        "discretionary_abandonment",
    )
    if discretionary.get("requires_human_approval") is not True:
        raise OperatingModelError("discretionary campaign abandonment must remain human-gated")


def _validate_attempt_and_search_governance(policy: Mapping[str, Any]) -> None:
    variant = _mapping(policy.get("variant_budget"), "attempt_and_search_governance.variant_budget")
    if variant != {
        "source": "GOVERNED_METHODOLOGY_OR_FROZEN_CAMPAIGN_PROTOCOL",
        "explicit_identity_required": True,
        "bounded": True,
        "p1_numeric_limit": None,
        "renaming_resets_budget": False,
    }:
        raise OperatingModelError(
            "variant budget must be bounded by an identified external governed source without a P1 number"
        )
    rescue = _mapping(policy.get("rescue_budget"), "attempt_and_search_governance.rescue_budget")
    required_rescue = {
        "source": "GOVERNED_METHODOLOGY_OR_FROZEN_CAMPAIGN_PROTOCOL",
        "explicit_and_predeclared": True,
        "frozen_before_relevant_results": True,
        "missing_budget_effect": "RESCUE_PROHIBITED",
        "budget_exhaustion_effect": "RESCUE_PROHIBITED",
        "each_rescue_new_attempt_identity": True,
        "history_immutable": True,
        "renaming_resets_budget": False,
        "post_oos_reopen_or_redefinition": "PROHIBITED",
        "hypothesis_change_same_lineage": "PROHIBITED",
    }
    if rescue != required_rescue:
        raise OperatingModelError("authorized rescue requires an immutable bounded predeclared budget")
    required_rules = {
        "post_oos_tuning_same_lineage": "PROHIBITED",
        "consumed_holdout_reopen": "PROHIBITED",
        "every_execution_new_attempt_identity": True,
        "retry_until_pass": "STRUCTURALLY_PROHIBITED",
    }
    for field, expected in required_rules.items():
        if policy.get(field) != expected:
            raise OperatingModelError(f"attempt/search anti-overfit rule {field} must be {expected}")
    joined = " ".join(str(item) for item in policy.get("new_variant_when") or []).casefold()
    if "governed external variant budget" not in joined:
        raise OperatingModelError("successor variants require an identified governed external budget")
    if any(token in joined for token in ("maximum five", "50 variants", "maximum 50")):
        raise OperatingModelError("P1 cannot independently own a numeric variant limit")
    anti_reset = str(policy.get("anti_reset_rule") or "").casefold()
    if not all(token in anti_reset for token in ("renaming", "budgets", "consumed holdouts")):
        raise OperatingModelError("renaming cannot reset budgets, history, or consumed holdouts")


def _validate_revisit_policy(policy: Mapping[str, Any]) -> None:
    valid = {
        "materially_new_dataset",
        "substantially_longer_sample",
        "different_instrument_with_justified_transfer_mechanism",
        "documented_market_structure_or_regime_change",
        "newly_available_execution_data",
        "corrected_engine_bug",
        "new_independent_academic_or_exchange_evidence",
        "materially_different_causal_mechanism",
    }
    invalid = {
        "backtest_was_close",
        "minor_threshold_tweak",
        "campaign_or_edge_relabel",
        "try_more_parameters",
        "reopen_failed_oos",
        "rerun_until_pass",
    }
    actual_valid = set(policy.get("valid_triggers") or [])
    actual_invalid = set(policy.get("invalid_triggers") or [])
    if actual_valid != valid or actual_invalid != invalid or actual_valid & actual_invalid:
        raise OperatingModelError("revisit triggers must preserve the exact material/invalid boundary")
    if policy.get("requires_human_approval") is not True:
        raise OperatingModelError("revisit requires human approval")
    if policy.get("requires_new_lineage_identity") is not True:
        raise OperatingModelError("revisit requires a new lineage identity")


def _validate_codex_permissions(permissions: Mapping[str, Mapping[str, Any]]) -> None:
    if set(permissions) != set(REQUIRED_AUTONOMOUS_PERMISSIONS):
        raise OperatingModelError("Codex autonomous permissions are incomplete or unexpected")
    for permission_id, expected_type in REQUIRED_AUTONOMOUS_PERMISSIONS.items():
        permission = _mapping(permissions.get(permission_id), permission_id)
        if permission.get("capability_type") != expected_type:
            raise OperatingModelError(f"Codex permission {permission_id} has unsafe capability type")
        if permission.get("grants_approval") is not False:
            raise OperatingModelError(f"Codex autonomous permission {permission_id} cannot grant approval")
        if permission.get("grants_override") is not False:
            raise OperatingModelError(f"Codex autonomous permission {permission_id} cannot grant override")


def _validate_machine_prohibitions(prohibitions: Mapping[str, Mapping[str, Any]]) -> None:
    if set(prohibitions) != set(REQUIRED_MACHINE_PROHIBITIONS):
        raise OperatingModelError("machine-semantic Codex prohibitions are incomplete or unexpected")
    for prohibition_id, (capability, actions) in REQUIRED_MACHINE_PROHIBITIONS.items():
        prohibition = _mapping(prohibitions.get(prohibition_id), prohibition_id)
        if prohibition.get("actor") != "CODEX":
            raise OperatingModelError(f"machine prohibition {prohibition_id} must bind CODEX")
        if prohibition.get("capability") != capability:
            raise OperatingModelError(f"machine prohibition {prohibition_id} has wrong capability")
        if set(prohibition.get("actions") or []) != actions:
            raise OperatingModelError(f"machine prohibition {prohibition_id} has wrong actions")
        if prohibition.get("effect") != "PROHIBITED":
            raise OperatingModelError(f"machine prohibition {prohibition_id} must prohibit its effect")


def _validate_runtime_conformance(
    transitions: Mapping[str, Mapping[str, Any]],
    conformance: Mapping[str, Any],
) -> None:
    if conformance.get("automation_contract") != "canonical_policy_only":
        raise OperatingModelError("future automation must consume the canonical policy only")
    if conformance.get("legacy_paths_may_satisfy_canonical_automation") is not False:
        raise OperatingModelError("legacy runtime paths cannot satisfy canonical automation")
    gaps = _indexed(conformance.get("known_gaps"), "runtime_conformance.known_gaps")
    expected = {
        "CANDIDATE_REVIEW_DISTINCT_HUMAN_IDENTITY": "APPROVE_HISTORICAL_CANDIDATE",
        "DESTINATION_SPECIFIC_CANDIDATE_CREATION": "APPROVE_HISTORICAL_CANDIDATE",
    }
    if {gap_id: gap.get("transition_id") for gap_id, gap in gaps.items()} != expected:
        raise OperatingModelError("candidate runtime conformance gaps are incomplete or unexpected")
    for gap_id, gap in gaps.items():
        if gap.get("automation_may_use_legacy_behavior") is not False:
            raise OperatingModelError(f"runtime gap {gap_id} cannot be used by canonical automation")
        if gap.get("migration_required") is not True:
            raise OperatingModelError(f"runtime gap {gap_id} requires migration")
        if not str(gap.get("current_runtime_behavior") or "").strip() or not str(
            gap.get("canonical_policy_behavior") or ""
        ).strip():
            raise OperatingModelError(f"runtime gap {gap_id} requires current and canonical behavior")
        transition = _mapping(transitions.get(gap["transition_id"]), gap["transition_id"])
        if transition.get("implementation_status") != "EXISTING_PARTIAL":
            raise OperatingModelError(
                f"transition {gap['transition_id']} with a known runtime gap must be EXISTING_PARTIAL"
            )


def _require_single_human_independence(
    actors: Mapping[str, Mapping[str, Any]],
    separations: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> None:
    human = _mapping(actors.get("HUMAN_OWNER_RESEARCHER"), "HUMAN_OWNER_RESEARCHER")
    if human.get("single_human_repository_supported") is not True:
        raise OperatingModelError("the authority model must remain satisfiable by one human owner")
    if policy.get("repository_model") != "single_human_owner":
        raise OperatingModelError("independence policy must declare the single-human repository model")
    if policy.get("distinct_human_identities_required") is not False:
        raise OperatingModelError("independence cannot require a second human identity")
    if policy.get("minimum_human_identities_required") != 1:
        raise OperatingModelError("single-human independence must require exactly one human identity")
    basis = set(policy.get("separation_basis") or [])
    if not {"task_context", "provenance", "implementation_ownership", "red_team_task"}.issubset(
        basis
    ):
        raise OperatingModelError("single-human independence needs task, provenance, and ownership separation")
    if policy.get("codex_may_approve_own_work") is not False:
        raise OperatingModelError("task-based independence cannot grant Codex approval authority")
    if policy.get("deterministic_results_overridable") is not False:
        raise OperatingModelError("task-based independence cannot override deterministic results")

    implementation_red_team = _mapping(
        separations.get("IMPLEMENTATION_VS_RED_TEAM"),
        "IMPLEMENTATION_VS_RED_TEAM",
    )
    if implementation_red_team.get("required_separate_task") is not True:
        raise OperatingModelError("implementation and red team must remain separate tasks")
    if implementation_red_team.get("producer_role") == implementation_red_team.get(
        "reviewer_or_consumer_role"
    ):
        raise OperatingModelError("implementation and red-team task ownership must differ")


def _require_forward_evidence_custody(
    objects: Mapping[str, Mapping[str, Any]],
    transitions: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> None:
    observation = _mapping(objects.get("FORWARD_OBSERVATION"), "FORWARD_OBSERVATION")
    if observation.get("owner") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("AlphaQuest must own canonical Forward Observation evidence")
    if observation.get("source_actor") != "EXTERNAL_SYSTEM":
        raise OperatingModelError("external systems must be forward event sources, not custodians")
    if set(observation.get("evidence") or []) != {
        "source_identity",
        "event_hash",
        "previous_event_hash",
        "occurred_at",
        "attachment_hashes",
        "trade_and_rule_reconciliation",
    }:
        raise OperatingModelError("Forward Observation object evidence and hash chain are incomplete")
    if set(observation.get("invalidated_by") or []) != {
        "historical_backfill",
        "non_increasing_time",
        "broken_hash_chain",
        "attachment_hash_drift",
    }:
        raise OperatingModelError("Forward Observation invalidation rules are incomplete")

    append = _mapping(transitions.get("APPEND_FORWARD_OBSERVATION"), "APPEND_FORWARD_OBSERVATION")
    if append.get("initiator") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("AlphaQuest must initiate canonical forward evidence capture")
    if append.get("source_actor") != "EXTERNAL_SYSTEM":
        raise OperatingModelError("forward capture must identify the external source actor")
    if append.get("human_approval_required") is not False or append.get("alphaquest_automatic") is not True:
        raise OperatingModelError("valid forward evidence capture must be automatic without human approval")
    if set(append.get("evidence_required") or []) != {
        "source_identity",
        "post_start_timestamp",
        "event_hash",
        "previous_event_hash",
        "attachment_hashes",
        "trade_reconciliation",
    }:
        raise OperatingModelError("forward append evidence identity and hash chain are incomplete")
    if set(append.get("deterministic_checks") or []) != {
        "source_identity_valid",
        "strict_post_start_chronology",
        "event_hash_valid",
        "previous_event_hash_chain_valid",
        "attachment_hashes_valid",
        "rule_fields_complete",
        "no_historical_backfill",
        "no_reconstructed_pre_start_event",
        "no_reused_historical_oos",
    }:
        raise OperatingModelError("forward append checks must validate chronology, hashes, and source exclusions")

    if policy.get("canonical_evidence_owner") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("forward evidence policy must assign AlphaQuest custody")
    if policy.get("event_source_actor") != "EXTERNAL_SYSTEM":
        raise OperatingModelError("forward evidence policy must separate external source from custody")
    if policy.get("automatic_append_after_validation") is not True:
        raise OperatingModelError("validated forward observations must append automatically")
    if policy.get("invalid_missing_or_ambiguous_evidence") != "fail_closed_without_append":
        raise OperatingModelError("invalid or ambiguous forward evidence must fail closed")
    required = set(policy.get("required_capture_validation") or [])
    if required != {
        "source_identity",
        "strict_post_start_chronology",
        "event_hash",
        "previous_event_hash",
        "attachment_hashes",
        "reconciliation_fields",
    }:
        raise OperatingModelError("forward evidence custody validation is incomplete")
    if set(policy.get("prohibited_sources") or []) != {
        "historical_backfill",
        "reconstructed_pre_start_observation",
        "reused_historical_oos",
    }:
        raise OperatingModelError("forward evidence prohibited sources are incomplete")


def _validate_methodology_change_governance(changes: Mapping[str, Any]) -> None:
    methodology = _mapping(changes.get("methodology"), "change_governance.methodology")
    version_rule = str(methodology.get("version_rule") or "").casefold()
    if "increments methodology version" not in version_rule or "changes policy hash" not in version_rule:
        raise OperatingModelError("semantic methodology changes require distinct version and hash identity")
    if methodology.get("retroactive_rewrite") != "prohibited":
        raise OperatingModelError("methodology governance must prohibit retroactive rewriting")
    regression = set(methodology.get("required_regression") or [])
    if not {"methodology_regression", "causal_execution_regression", "full_validate"}.issubset(regression):
        raise OperatingModelError("methodology change regression coverage is incomplete")


def _validate_data_change_governance(changes: Mapping[str, Any]) -> None:
    data = _mapping(changes.get("data"), "change_governance.data")
    categories = _indexed(data.get("categories"), "change_governance.data.categories")
    if set(categories) != REQUIRED_DATA_CHANGES:
        raise OperatingModelError("data change categories are incomplete or unexpected")
    for category_id, category in categories.items():
        for field in (
            "materiality",
            "preserves_dataset_identity",
            "new_version_or_hash",
            "invalidates_old_results",
            "rerun",
            "human_review",
            "recertification",
        ):
            if field not in category:
                raise OperatingModelError(f"data change {category_id} is missing {field}")
        if category.get("materiality") == "material":
            if category.get("preserves_dataset_identity") is not False:
                raise OperatingModelError(f"material data change {category_id} cannot preserve identity")
            if category.get("new_version_or_hash") is not True:
                raise OperatingModelError(f"material data change {category_id} needs new lineage")
            if category.get("invalidates_old_results") is not False:
                raise OperatingModelError(
                    f"material data change {category_id} must preserve old results as old-data history"
                )

    append = categories["ADD_ROWS_SAME_CERTIFIED_DATASET"]
    if append.get("ingestion") != "automatic_after_unchanged_contract_validation":
        raise OperatingModelError("same-contract data append ingestion must be automatic")
    if append.get("human_review") != "not_required_for_ingestion_or_content_versioning":
        raise OperatingModelError("routine same-contract append cannot require human approval")
    if append.get("new_version_or_hash") is not True or append.get("preserves_dataset_identity") is not False:
        raise OperatingModelError("same-contract append must create a distinct content identity")
    if append.get("campaign_rebind") != "human_or_governed_research_decision":
        raise OperatingModelError("frozen campaign data rebinding must remain governed")
    if "cannot_change_or_leak" not in str(append.get("locked_window_effect") or ""):
        raise OperatingModelError("same-contract append cannot leak into frozen OOS or holdout windows")

    timestamps = categories["FIX_TIMESTAMPS"]
    if timestamps.get("human_review") != "required":
        raise OperatingModelError("material timestamp repair requires governed human review")
    if timestamps.get("rerun") != "required_for_current_claims":
        raise OperatingModelError("material timestamp repair requires rerun for current claims")
    if timestamps.get("recertification") != "required_if_signal_availability_or_entry_timing_changes":
        raise OperatingModelError(
            "material timestamp repair requires recertification when causal timing can change"
        )

    append_policy = _mapping(
        data.get("same_contract_append_policy"),
        "change_governance.data.same_contract_append_policy",
    )
    automatic = set(append_policy.get("automatic_actions") or [])
    if automatic != {
        "capture_rows",
        "create_new_content_and_data_identity",
        "validate_unchanged_contract",
        "preserve_prior_dataset_and_evidence_identity",
    }:
        raise OperatingModelError("same-contract append automatic actions are incomplete or unsafe")
    governed = set(append_policy.get("governed_research_decisions") or [])
    if governed != {
        "rebind_frozen_campaign_to_expanded_dataset",
        "change_locked_historical_or_holdout_boundary",
        "create_data_refresh_attempt",
        "claim_new_research_evidence_from_expanded_sample",
    }:
        raise OperatingModelError("same-contract append must preserve governed research boundaries")
    if "cannot silently enter" not in str(append_policy.get("frozen_boundary_rule") or ""):
        raise OperatingModelError("same-contract append needs an explicit no-leakage boundary rule")


def _validate_implementation_change_governance(changes: Mapping[str, Any]) -> None:
    implementation = _mapping(changes.get("implementation"), "change_governance.implementation")
    equivalence = _mapping(
        implementation.get("equivalence_policy"),
        "change_governance.implementation.equivalence_policy",
    )
    if equivalence.get("approved_deterministic_standard_required") is not True:
        raise OperatingModelError("non-semantic reuse requires an approved deterministic equivalence standard")
    if equivalence.get("current_capability") != "not_claimed_by_P1":
        raise OperatingModelError("P1 cannot claim implementation-equivalence machinery exists")
    if equivalence.get("default_when_missing_failed_or_uncertain") != "semantic_or_uncertain_path":
        raise OperatingModelError("uncertain implementation equivalence must fail closed")
    if "blocked" not in str(equivalence.get("deployment_rule") or "").casefold():
        raise OperatingModelError("deployment must remain blocked until new certification is current")
    categories = _indexed(
        implementation.get("categories"), "change_governance.implementation.categories"
    )
    if set(categories) != REQUIRED_IMPLEMENTATION_CHANGES:
        raise OperatingModelError("implementation change categories are incomplete or unexpected")
    for category_id, category in categories.items():
        for field in (
            "new_implementation_hash",
            "certification",
            "mechanics_approval",
            "historical_results",
            "rerun",
            "forward_incubation",
            "deployment",
            "equivalence_class",
            "requires_approved_equivalence_standard",
            "full_scientific_rerun_unconditionally_required",
        ):
            if field not in category:
                raise OperatingModelError(f"implementation change {category_id} is missing {field}")
    for category_id in SEMANTIC_IMPLEMENTATION_CHANGES:
        category = categories[category_id]
        if category.get("equivalence_class") != "semantic":
            raise OperatingModelError(f"semantic implementation change {category_id} is misclassified")
        if category.get("new_implementation_hash") is not True:
            raise OperatingModelError(f"semantic implementation change {category_id} needs a new hash")
        if "stale" not in str(category.get("certification") or ""):
            raise OperatingModelError(f"semantic implementation change {category_id} must stale certification")
        if "stale" not in str(category.get("mechanics_approval") or "") and "new_approval" not in str(
            category.get("mechanics_approval") or ""
        ):
            raise OperatingModelError(
                f"semantic implementation change {category_id} must stale mechanics approval"
            )
        if str(category.get("rerun") or "") == "no":
            raise OperatingModelError(f"semantic implementation change {category_id} requires new evidence")
        if category.get("full_scientific_rerun_unconditionally_required") is not True:
            raise OperatingModelError(f"semantic implementation change {category_id} must fail closed")

    for category_id in PROVEN_NONSEMANTIC_IMPLEMENTATION_CHANGES:
        category = categories[category_id]
        if category.get("equivalence_class") != "proven_non_semantic":
            raise OperatingModelError(f"proven non-semantic change {category_id} is misclassified")
        if category.get("new_implementation_hash") is not True:
            raise OperatingModelError(f"proven non-semantic change {category_id} needs a new byte identity")
        if category.get("requires_approved_equivalence_standard") is not True:
            raise OperatingModelError(
                f"proven non-semantic change {category_id} requires an approved equivalence standard"
            )
        if category.get("full_scientific_rerun_unconditionally_required") is not False:
            raise OperatingModelError(
                f"proven non-semantic change {category_id} cannot always require a full scientific rerun"
            )
        if "may_remain_admissible" not in str(category.get("historical_results") or ""):
            raise OperatingModelError(
                f"proven non-semantic change {category_id} must permit explicit equivalence lineage"
            )
        if "may_continue_without_restart" not in str(category.get("forward_incubation") or ""):
            raise OperatingModelError(
                f"proven non-semantic change {category_id} must permit forward continuity"
            )
        if "blocked_until" not in str(category.get("deployment") or ""):
            raise OperatingModelError(
                f"proven non-semantic change {category_id} must block deployment until certified"
            )


def _indexed(value: object, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise OperatingModelError(f"{label} must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(value, start=1):
        item = _mapping(raw, f"{label}[{index}]")
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            raise OperatingModelError(f"{label}[{index}] requires id")
        if item_id in result:
            raise OperatingModelError(f"{label} contains duplicate id {item_id}")
        result[item_id] = item
    return result


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OperatingModelError(f"{label} must be a mapping")
    return dict(value)


def _string_sequence(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OperatingModelError(f"{label} must be a list")
    normalized = [str(item).strip() for item in value]
    if not allow_empty and not normalized:
        raise OperatingModelError(f"{label} must not be empty")
    if any(not item for item in normalized):
        raise OperatingModelError(f"{label} contains a blank item")
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the canonical AlphaQuest P1 operating model")
    parser.add_argument("--policy", default=str(DEFAULT_OPERATING_MODEL_PATH))
    args = parser.parse_args(argv)
    policy = load_operating_model(args.policy)
    print(
        json.dumps(
            {
                "schema": policy["schema"],
                "policy_version": policy["policy_version"],
                "policy_sha256": operating_model_sha256(args.policy),
                "status": "PASS",
                "objects": len(policy["research_objects"]),
                "transitions": len(policy["transitions"]),
                "invariants": len(policy["invariants"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
