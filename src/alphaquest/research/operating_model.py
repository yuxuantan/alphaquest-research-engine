"""Canonical P1 research operating-model policy and integrity checks.

This module validates policy definitions only.  It does not implement the
future backlog, execution, deployment, or live orchestration described by
policy-only transitions in the specification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    "HISTORICAL_CANDIDATE_CANNOT_IMPLY_LIVE_AUTHORIZATION",
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
    "DISCRETIONARY_ABANDONMENT_AND_REVISIT_REQUIRE_HUMAN",
    "SAME_CONTRACT_DATA_APPEND_CANNOT_REBIND_FROZEN_RESEARCH",
    "CODEX_CANNOT_OVERRIDE_DETERMINISTIC_GATE_FAILURE",
    "HUMAN_CANNOT_OVERRIDE_MISSING_OBJECTIVE_EVIDENCE",
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
    if identity.get("methodology_identity_is_separate") is not True:
        raise OperatingModelError("operating-model and methodology identities must remain separate")

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
    _require_deployment_authority(transitions)
    _require_no_historical_candidate_shortcut(transitions)
    _require_account_scientific_separation(
        objects,
        transitions,
        _mapping(document.get("account_suitability_policy"), "account_suitability_policy"),
    )
    _require_campaign_termination_authority(
        transitions,
        _mapping(document.get("campaign_termination_policy"), "campaign_termination_policy"),
    )

    codex_policy = _mapping(document.get("codex_policy"), "codex_policy")
    permissions = _indexed(codex_policy.get("autonomous_permissions"), "codex_policy.autonomous_permissions")
    if "IMPLEMENT_APPROVED_MECHANICS" not in permissions:
        raise OperatingModelError("Codex policy must classify bounded implementation authority")
    prohibitions = _indexed(codex_policy.get("prohibitions"), "codex_policy.prohibitions")
    if not REQUIRED_PROHIBITIONS.issubset(prohibitions):
        missing = sorted(REQUIRED_PROHIBITIONS - set(prohibitions))
        raise OperatingModelError("Codex prohibitions are missing: " + ", ".join(missing))

    deterministic = _mapping(document.get("deterministic_authority"), "deterministic_authority")
    decisions = set(_string_sequence(deterministic.get("decisions"), "deterministic_authority.decisions"))
    required_deterministic_decisions = {
        "PREDECLARED_NUMERICAL_STAGE_GATES",
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
    if not {"PASS", "FAIL", "NEEDS_MANUAL_REVIEW"}.issubset(scientific):
        raise OperatingModelError("scientific state must retain PASS, FAIL, and NEEDS_MANUAL_REVIEW")
    if not {"PASS", "FAIL", "NEEDS_MANUAL_REVIEW"}.issubset(account):
        raise OperatingModelError("account suitability must be an exact-profile decision axis")
    if "PASS" in deployment or "FAIL" in deployment:
        raise OperatingModelError("deployment state must not collapse into scientific PASS/FAIL")


def _require_acyclic_object_dependencies(
    objects: Mapping[str, Mapping[str, Any]],
) -> None:
    graph = {
        object_id: [
            dependency
            for dependency in _string_sequence(
                item.get("downstream"),
                f"research_objects.{object_id}.downstream",
            )
            if dependency in objects
        ]
        for object_id, item in objects.items()
    }
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


def _require_no_historical_candidate_shortcut(
    transitions: Mapping[str, Mapping[str, Any]],
) -> None:
    forbidden_targets = {"SHADOW", "SMALL_LIVE", "LIVE", "MONITORING"}
    for transition_id, transition in transitions.items():
        if (
            transition.get("from_stage") == "HISTORICAL_CANDIDATE_REVIEW"
            and transition.get("to_stage") in forbidden_targets
        ):
            raise OperatingModelError(
                f"transition {transition_id} shortcuts historical candidate status to live authorization"
            )


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

    append = _mapping(transitions.get("APPEND_FORWARD_OBSERVATION"), "APPEND_FORWARD_OBSERVATION")
    if append.get("initiator") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("AlphaQuest must initiate canonical forward evidence capture")
    if append.get("source_actor") != "EXTERNAL_SYSTEM":
        raise OperatingModelError("forward capture must identify the external source actor")
    if append.get("human_approval_required") is not False or append.get("alphaquest_automatic") is not True:
        raise OperatingModelError("valid forward evidence capture must be automatic without human approval")

    if policy.get("canonical_evidence_owner") != "ALPHAQUEST_DETERMINISTIC_ENGINE":
        raise OperatingModelError("forward evidence policy must assign AlphaQuest custody")
    if policy.get("event_source_actor") != "EXTERNAL_SYSTEM":
        raise OperatingModelError("forward evidence policy must separate external source from custody")
    if policy.get("automatic_append_after_validation") is not True:
        raise OperatingModelError("validated forward observations must append automatically")
    if policy.get("invalid_missing_or_ambiguous_evidence") != "fail_closed_without_append":
        raise OperatingModelError("invalid or ambiguous forward evidence must fail closed")
    required = set(policy.get("required_capture_validation") or [])
    if not {
        "source_identity",
        "strict_post_start_chronology",
        "event_hash",
        "previous_event_hash",
        "attachment_hashes",
        "reconciliation_fields",
    }.issubset(required):
        raise OperatingModelError("forward evidence custody validation is incomplete")


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

    append_policy = _mapping(
        data.get("same_contract_append_policy"),
        "change_governance.data.same_contract_append_policy",
    )
    governed = set(append_policy.get("governed_research_decisions") or [])
    if not {
        "rebind_frozen_campaign_to_expanded_dataset",
        "change_locked_historical_or_holdout_boundary",
        "create_data_refresh_attempt",
    }.issubset(governed):
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
