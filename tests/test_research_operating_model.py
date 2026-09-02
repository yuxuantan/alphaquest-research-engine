from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from alphaquest.research.operating_model import (
    DEFAULT_OPERATING_MODEL_PATH,
    OPERATING_MODEL_SCHEMA,
    OperatingModelError,
    load_operating_model,
    operating_model_sha256,
    validate_operating_model,
)


def _policy() -> dict:
    return deepcopy(load_operating_model())


def _item(items: list[dict], item_id: str) -> dict:
    return next(item for item in items if item["id"] == item_id)


def test_canonical_operating_model_is_runnable_and_separate_from_methodology() -> None:
    policy = load_operating_model()

    assert policy["schema"] == OPERATING_MODEL_SCHEMA
    assert policy["policy_version"] == "2026-09-02.2"
    assert policy["identity"]["identity_fields"] == [
        "schema",
        "policy_version",
        "policy_sha256",
    ]
    assert policy["identity"]["introduced_against"] == {
        "p0_engine_tag": "engine-v0.1.0-p0",
        "engine_contract": "2026.08.14.1",
        "methodology": "2026-08-14.2",
    }
    assert policy["identity"]["introduction_metadata_is_non_normative"] is True
    assert len(operating_model_sha256()) == 64
    assert Path(DEFAULT_OPERATING_MODEL_PATH).is_file()


def test_operating_model_validation_does_not_pin_current_engine_or_methodology() -> None:
    policy = _policy()
    policy["identity"]["introduced_against"].update(
        {
            "p0_engine_tag": "future-qualified-tag",
            "engine_contract": "future-engine-contract",
            "methodology": "future-methodology",
        }
    )

    validate_operating_model(policy)


def test_codex_cannot_authorize_or_promote_live_deployment() -> None:
    policy = _policy()
    authorization = _item(policy["transitions"], "AUTHORIZE_DEPLOYMENT")
    authorization["codex"] = "ALLOWED"

    with pytest.raises(OperatingModelError, match="Codex authority mode|cannot approve"):
        validate_operating_model(policy)


def test_account_suitability_cannot_create_scientific_validity() -> None:
    policy = _policy()
    assessment = _item(policy["transitions"], "ASSESS_ACCOUNT_SUITABILITY")
    assessment["evidence_required"].remove("scientific_pass")
    assessment["deterministic_checks"].remove("scientific_pass_first")

    with pytest.raises(OperatingModelError, match="require scientific PASS first"):
        validate_operating_model(policy)


def test_candidate_and_account_suitability_dependencies_must_be_acyclic() -> None:
    policy = _policy()
    account = _item(policy["research_objects"], "ACCOUNT_SUITABILITY_ASSESSMENT")
    account["downstream"].append("CANDIDATE_STRATEGY")

    with pytest.raises(OperatingModelError, match="dependencies must be acyclic"):
        validate_operating_model(policy)


def test_candidate_approval_cannot_depend_on_account_suitability() -> None:
    policy = _policy()
    approval = _item(policy["transitions"], "APPROVE_HISTORICAL_CANDIDATE")
    approval["evidence_required"].append("account_suitability_pass")

    with pytest.raises(OperatingModelError, match="candidate approval cannot depend"):
        validate_operating_model(policy)


def test_historical_candidate_cannot_directly_imply_live_authorization() -> None:
    policy = _policy()
    shortcut = deepcopy(_item(policy["transitions"], "START_FORWARD_INCUBATION"))
    shortcut.update(
        {
            "id": "ILLEGAL_HISTORICAL_PASS_TO_LIVE",
            "from_stage": "HISTORICAL_CANDIDATE_REVIEW",
            "to_stage": "LIVE",
        }
    )
    policy["transitions"].append(shortcut)

    with pytest.raises(OperatingModelError, match="canonical transition set mismatch"):
        validate_operating_model(policy)


def test_unknown_codex_deployment_ingress_transition_is_rejected() -> None:
    policy = _policy()
    transition = deepcopy(_item(policy["transitions"], "RECORD_RESEARCH_LEAD"))
    transition.update(
        {
            "id": "CODEX_DEPLOYMENT_REVIEW_TO_SHADOW",
            "from_stage": "DEPLOYMENT_REVIEW",
            "to_stage": "SHADOW",
        }
    )
    policy["transitions"].append(transition)

    with pytest.raises(OperatingModelError, match="canonical transition set mismatch"):
        validate_operating_model(policy)


def test_unknown_human_discovery_to_live_transition_is_rejected() -> None:
    policy = _policy()
    transition = deepcopy(_item(policy["transitions"], "ABANDON_EDGE_FAMILY"))
    transition.update(
        {
            "id": "HUMAN_DISCOVERY_TO_LIVE",
            "from_stage": "DISCOVERY",
            "to_stage": "LIVE",
        }
    )
    policy["transitions"].append(transition)

    with pytest.raises(OperatingModelError, match="canonical transition set mismatch"):
        validate_operating_model(policy)


def test_unknown_codex_scientific_verdict_transition_is_rejected() -> None:
    policy = _policy()
    transition = deepcopy(_item(policy["transitions"], "RECORD_RESEARCH_LEAD"))
    transition.update(
        {
            "id": "CODEX_RECORD_SCIENTIFIC_VERDICT",
            "from_stage": "FULL_HISTORICAL_VALIDATION",
            "to_stage": "FULL_HISTORICAL_VALIDATION",
            "scientific_state_effect": "PASS",
        }
    )
    policy["transitions"].append(transition)

    with pytest.raises(OperatingModelError, match="canonical transition set mismatch"):
        validate_operating_model(policy)


def test_missing_canonical_transition_is_rejected() -> None:
    policy = _policy()
    policy["transitions"] = [
        transition
        for transition in policy["transitions"]
        if transition["id"] != "RECORD_RESEARCH_LEAD"
    ]

    with pytest.raises(OperatingModelError, match="canonical transition set mismatch"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    "transition_id",
    [
        "RECORD_RESEARCH_LEAD",
        "STOP_CAMPAIGN_ON_PREDECLARED_RULE",
        "ABANDON_EDGE_FAMILY",
        "REVISIT_FAILED_EDGE",
        "APPEND_FORWARD_OBSERVATION",
    ],
)
def test_second_audit_transition_rewires_are_rejected(transition_id: str) -> None:
    policy = _policy()
    _item(policy["transitions"], transition_id)["to_stage"] = "LIVE"

    with pytest.raises(OperatingModelError, match=f"canonical transition {transition_id} must be"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    "transition_id",
    [
        "ASSESS_ACCOUNT_SUITABILITY",
        "APPEND_LIVE_MONITORING",
        "SAFETY_PAUSE",
        "RETIRE_LIVE_INSTANCE",
        "STOP_CAMPAIGN_ON_PREDECLARED_RULE",
        "DISCRETIONARILY_ABANDON_CAMPAIGN",
    ],
)
def test_canonical_applicable_stage_scopes_are_exact(transition_id: str) -> None:
    policy = _policy()
    _item(policy["transitions"], transition_id)["applicable_stages"].pop()

    with pytest.raises(OperatingModelError, match="applicable_stages must remain exact"):
        validate_operating_model(policy)


def test_transition_without_side_axis_scope_cannot_add_applicable_stages() -> None:
    policy = _policy()
    _item(policy["transitions"], "RECORD_RESEARCH_LEAD")["applicable_stages"] = ["DISCOVERY"]

    with pytest.raises(OperatingModelError, match="cannot declare applicable_stages"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    ("transition_id", "effect_field", "effect_value"),
    [
        ("APPEND_FORWARD_OBSERVATION", "scientific_state_effect", "PASS"),
        (
            "APPEND_FORWARD_OBSERVATION",
            "candidate_disposition_effect",
            "APPROVED_CURRENT",
        ),
        (
            "APPEND_FORWARD_OBSERVATION",
            "deployment_state_effect",
            "APPROVED_FOR_MANUAL_DEPLOYMENT",
        ),
        (
            "ENTER_HISTORICAL_CANDIDATE_REVIEW",
            "candidate_disposition_effect",
            "APPROVED_CURRENT",
        ),
        ("MARK_FORWARD_ELIGIBLE_FOR_REVIEW", "forward_state_effect", "ACCEPTED"),
        ("CREATE_PORTFOLIO_REVIEW", "portfolio_state_effect", "ACCEPTED"),
        (
            "ENTER_DEPLOYMENT_REVIEW",
            "deployment_state_effect",
            "APPROVED_FOR_MANUAL_DEPLOYMENT",
        ),
        (
            "ASSESS_ACCOUNT_SUITABILITY",
            "candidate_disposition_effect",
            "APPROVED_CURRENT",
        ),
        ("ASSESS_ACCOUNT_SUITABILITY", "scientific_state_effect", "PASS"),
        (
            "RECORD_RESEARCH_LEAD",
            "deployment_state_effect",
            "APPROVED_FOR_MANUAL_DEPLOYMENT",
        ),
    ],
)
def test_latest_audit_cross_axis_effect_mutations_are_rejected(
    transition_id: str,
    effect_field: str,
    effect_value: str,
) -> None:
    policy = _policy()
    _item(policy["transitions"], transition_id)[effect_field] = effect_value

    with pytest.raises(OperatingModelError, match="effect"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    ("transition_id", "effect_field", "wrong_value"),
    [
        ("ACCEPT_FORWARD_REVIEW", "forward_state_effect", "FAILED"),
        ("REJECT_FORWARD_REVIEW", "forward_state_effect", "ACCEPTED"),
        ("RECORD_PORTFOLIO_DISPOSITION", "portfolio_state_effect", "REJECTED"),
        ("REJECT_PORTFOLIO_DISPOSITION", "portfolio_state_effect", "ACCEPTED"),
        (
            "APPROVE_HISTORICAL_CANDIDATE",
            "candidate_disposition_effect",
            "REJECTED",
        ),
        (
            "REJECT_HISTORICAL_CANDIDATE",
            "candidate_disposition_effect",
            "APPROVED_CURRENT",
        ),
        ("SAFETY_PAUSE", "operational_state_effect", "HEALTHY"),
        ("RETIRE_LIVE_INSTANCE", "operational_state_effect", "HEALTHY"),
    ],
)
def test_canonical_effect_values_cannot_be_substituted(
    transition_id: str,
    effect_field: str,
    wrong_value: str,
) -> None:
    policy = _policy()
    _item(policy["transitions"], transition_id)[effect_field] = wrong_value

    with pytest.raises(OperatingModelError, match="effect contract must remain exact"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    ("transition_id", "required_effect_field"),
    [
        ("ACCEPT_FORWARD_REVIEW", "forward_state_effect"),
        ("RECORD_PORTFOLIO_DISPOSITION", "portfolio_state_effect"),
        ("APPROVE_HISTORICAL_CANDIDATE", "candidate_disposition_effect"),
        ("SAFETY_PAUSE", "operational_state_effect"),
    ],
)
def test_required_canonical_effect_cannot_be_removed(
    transition_id: str,
    required_effect_field: str,
) -> None:
    policy = _policy()
    del _item(policy["transitions"], transition_id)[required_effect_field]

    with pytest.raises(OperatingModelError, match="effect contract must remain exact"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    ("transition_id", "effect_field", "effect_value"),
    [
        ("REJECT_HISTORICAL_CANDIDATE", "portfolio_state_effect", "ACCEPTED"),
        (
            "REJECT_PORTFOLIO_DISPOSITION",
            "deployment_state_effect",
            "APPROVED_FOR_MANUAL_DEPLOYMENT",
        ),
        ("DISCRETIONARILY_ABANDON_CAMPAIGN", "scientific_state_effect", "PASS"),
        ("SAFETY_PAUSE", "candidate_disposition_effect", "APPROVED_CURRENT"),
        ("RECORD_RESEARCH_LEAD", "forward_state_effect", "ACCEPTED"),
        ("ASSESS_ACCOUNT_SUITABILITY", "portfolio_state_effect", "ACCEPTED"),
        ("AUTHORIZE_DEPLOYMENT", "scientific_state_effect", "PASS"),
    ],
)
def test_novel_cross_axis_effect_attacks_are_rejected(
    transition_id: str,
    effect_field: str,
    effect_value: str,
) -> None:
    policy = _policy()
    _item(policy["transitions"], transition_id)[effect_field] = effect_value

    with pytest.raises(OperatingModelError, match="effect"):
        validate_operating_model(policy)


def test_recording_historical_verdict_does_not_enter_candidate_review() -> None:
    policy = _policy()
    record = _item(policy["transitions"], "RECORD_HISTORICAL_VERDICT")
    record["to_stage"] = "HISTORICAL_CANDIDATE_REVIEW"

    with pytest.raises(OperatingModelError, match="canonical transition RECORD_HISTORICAL_VERDICT"):
        validate_operating_model(policy)


def test_historical_fail_cannot_enter_candidate_review() -> None:
    policy = _policy()
    enter = _item(policy["transitions"], "ENTER_HISTORICAL_CANDIDATE_REVIEW")
    enter["eligible_scientific_states"].append("FAIL")

    with pytest.raises(OperatingModelError, match="only scientific PASS"):
        validate_operating_model(policy)


def test_needs_manual_review_cannot_enter_without_governed_resolution() -> None:
    policy = _policy()
    policy["historical_verdict_policy"]["needs_manual_review_resolution"] = (
        "human_click_without_new_evidence"
    )

    with pytest.raises(OperatingModelError, match="requires governed resolution"):
        validate_operating_model(policy)


def test_forward_incubation_cannot_use_historical_backfill() -> None:
    policy = _policy()
    policy["forward_evidence_policy"]["prohibited_sources"].remove("historical_backfill")

    with pytest.raises(OperatingModelError, match="historical backfill must be prohibited"):
        validate_operating_model(policy)


def test_forward_observation_is_alphaquest_custodied_external_source_evidence() -> None:
    policy = _policy()
    observation = _item(policy["research_objects"], "FORWARD_OBSERVATION")
    observation["owner"] = "EXTERNAL_SYSTEM"

    with pytest.raises(OperatingModelError, match="AlphaQuest must own canonical"):
        validate_operating_model(policy)

    policy = _policy()
    policy["forward_evidence_policy"]["invalid_missing_or_ambiguous_evidence"] = (
        "append_with_warning"
    )
    with pytest.raises(OperatingModelError, match="must fail closed"):
        validate_operating_model(policy)


def test_failed_research_cannot_be_deleted_or_reclassified_to_pass() -> None:
    policy = _policy()
    policy["failed_research_policy"]["reclassifiable_to_pass"] = True

    with pytest.raises(OperatingModelError, match="cannot be deleted or reclassified"):
        validate_operating_model(policy)


def test_semantic_methodology_change_requires_distinguishable_identity() -> None:
    policy = _policy()
    policy["change_governance"]["methodology"]["version_rule"] = (
        "Reuse the current version after a semantic change."
    )

    with pytest.raises(OperatingModelError, match="distinct version and hash"):
        validate_operating_model(policy)


def test_material_data_change_requires_distinguishable_lineage() -> None:
    policy = _policy()
    timestamps = _item(
        policy["change_governance"]["data"]["categories"],
        "FIX_TIMESTAMPS",
    )
    timestamps["preserves_dataset_identity"] = True

    with pytest.raises(OperatingModelError, match="cannot preserve identity"):
        validate_operating_model(policy)


def test_same_contract_data_append_is_automatic_but_cannot_rebind_frozen_research() -> None:
    policy = _policy()
    append = _item(
        policy["change_governance"]["data"]["categories"],
        "ADD_ROWS_SAME_CERTIFIED_DATASET",
    )
    append["human_review"] = "required_for_ingestion"

    with pytest.raises(OperatingModelError, match="cannot require human approval"):
        validate_operating_model(policy)

    policy = _policy()
    append = _item(
        policy["change_governance"]["data"]["categories"],
        "ADD_ROWS_SAME_CERTIFIED_DATASET",
    )
    append["locked_window_effect"] = "expand_boundaries_automatically"
    with pytest.raises(OperatingModelError, match="cannot leak into frozen"):
        validate_operating_model(policy)


def test_semantic_implementation_change_invalidates_certification_and_approval() -> None:
    policy = _policy()
    mechanics = _item(
        policy["change_governance"]["implementation"]["categories"],
        "MECHANICS_CHANGE",
    )
    mechanics["certification"] = "remains_current"
    mechanics["mechanics_approval"] = "remains_current"

    with pytest.raises(OperatingModelError, match="must stale certification"):
        validate_operating_model(policy)


def test_uncertain_implementation_equivalence_fails_closed() -> None:
    policy = _policy()
    policy["change_governance"]["implementation"]["equivalence_policy"][
        "default_when_missing_failed_or_uncertain"
    ] = "reuse_existing_evidence"

    with pytest.raises(OperatingModelError, match="uncertain implementation equivalence"):
        validate_operating_model(policy)


def test_proven_nonsemantic_change_does_not_permanently_require_full_rerun() -> None:
    policy = _policy()
    refactor = _item(
        policy["change_governance"]["implementation"]["categories"],
        "REFACTOR_PROVEN_BEHAVIOR_IDENTICAL",
    )
    refactor["full_scientific_rerun_unconditionally_required"] = True

    with pytest.raises(OperatingModelError, match="cannot always require a full scientific rerun"):
        validate_operating_model(policy)


def test_red_team_evaluation_is_separate_from_implementation_ownership() -> None:
    policy = _policy()
    separation = _item(policy["separation_of_duties"], "EVALUATION_VS_RED_TEAM")
    separation["reviewer_or_consumer_role"] = separation["producer_role"]

    with pytest.raises(OperatingModelError, match="red-team ownership must differ"):
        validate_operating_model(policy)


def test_independence_remains_satisfiable_by_one_human_owner() -> None:
    policy = _policy()
    policy["independence_policy"]["distinct_human_identities_required"] = True

    with pytest.raises(OperatingModelError, match="cannot require a second human"):
        validate_operating_model(policy)


def test_deterministic_campaign_stop_needs_no_human_approval() -> None:
    policy = _policy()
    stop = _item(policy["transitions"], "STOP_CAMPAIGN_ON_PREDECLARED_RULE")
    stop["human_approval_required"] = True
    stop["alphaquest_automatic"] = False

    with pytest.raises(OperatingModelError, match="automatic without human approval"):
        validate_operating_model(policy)


def test_variant_stage_failure_does_not_automatically_exhaust_campaign() -> None:
    policy = _policy()
    variant_failure = policy["campaign_termination_policy"]["variant_failure"]
    assert "core_grid" in variant_failure["limited_stage_failures"]
    assert "authorized_variant_budget_remains" in variant_failure["successor_may_remain_when"]
    variant_failure["automatically_exhausts_campaign"] = True

    with pytest.raises(OperatingModelError, match="variant failure cannot automatically exhaust"):
        validate_operating_model(policy)


def test_campaign_exhaustion_requires_campaign_level_condition() -> None:
    policy = _policy()
    stop = policy["campaign_termination_policy"]["deterministic_stop"]
    stop["criteria"].append("deterministic_stage_gate_failure")

    with pytest.raises(OperatingModelError, match="incomplete or unexpected"):
        validate_operating_model(policy)


def test_discretionary_abandonment_and_revisit_remain_human_gated() -> None:
    policy = _policy()
    revisit = _item(policy["transitions"], "REVISIT_FAILED_EDGE")
    revisit["human_approval_required"] = False

    with pytest.raises(OperatingModelError, match="REVISIT_FAILED_EDGE must remain human-gated"):
        validate_operating_model(policy)


def test_deterministic_gate_failure_cannot_be_overridden_by_codex() -> None:
    policy = _policy()
    policy["deterministic_authority"]["override_policy"]["codex_may_override"] = True

    with pytest.raises(OperatingModelError, match="Codex cannot override"):
        validate_operating_model(policy)


def test_human_approval_cannot_override_missing_objective_evidence() -> None:
    policy = _policy()
    policy["deterministic_authority"]["override_policy"][
        "human_may_override_missing_or_failed_objective_evidence"
    ] = True

    with pytest.raises(OperatingModelError, match="human judgment cannot override"):
        validate_operating_model(policy)


def test_policy_only_states_do_not_claim_future_live_orchestration_exists() -> None:
    policy = load_operating_model()
    transitions = {item["id"]: item for item in policy["transitions"]}

    assert transitions["PROMOTE_SHADOW_TO_SMALL_LIVE"]["implementation_status"] == "POLICY_ONLY"
    assert transitions["PROMOTE_SMALL_LIVE_TO_LIVE"]["implementation_status"] == "POLICY_ONLY"
    assert transitions["SAFETY_PAUSE"]["implementation_status"] == "POLICY_ONLY"
    assert _item(
        policy["invariants"],
        "POLICY_DEFINITIONS_DO_NOT_CLAIM_RUNTIME_ENFORCEMENT",
    )


@pytest.mark.parametrize(
    ("transition_id", "unsafe_mode"),
    [
        ("APPROVE_MECHANICAL_INTERPRETATION", "PROPOSAL_ONLY"),
        ("OPEN_LOCKED_ACCEPTANCE_OOS", "PROPOSAL_ONLY"),
        ("APPROVE_HISTORICAL_CANDIDATE", "PROPOSAL_ONLY"),
        ("ACCEPT_FORWARD_REVIEW", "PROPOSAL_ONLY"),
        ("RECORD_PORTFOLIO_DISPOSITION", "ALLOWED_AFTER_HUMAN_SCOPE_APPROVAL"),
        ("AUTHORIZE_DEPLOYMENT", "PROPOSAL_ONLY"),
        ("PROMOTE_SHADOW_TO_SMALL_LIVE", "PROPOSAL_ONLY"),
        ("PROMOTE_SMALL_LIVE_TO_LIVE", "PROPOSAL_ONLY"),
    ],
)
def test_critical_codex_authority_mutations_are_rejected(
    transition_id: str,
    unsafe_mode: str,
) -> None:
    policy = _policy()
    _item(policy["transitions"], transition_id)["codex"] = unsafe_mode

    with pytest.raises(OperatingModelError, match="Codex cannot|Codex must"):
        validate_operating_model(policy)


def test_autonomous_permission_cannot_grant_mechanics_approval() -> None:
    policy = _policy()
    permission = _item(policy["codex_policy"]["autonomous_permissions"], "IMPLEMENT_APPROVED_MECHANICS")
    permission["grants_approval"] = True

    with pytest.raises(OperatingModelError, match="cannot grant approval"):
        validate_operating_model(policy)


def test_human_transition_cannot_become_alphaquest_automatic() -> None:
    policy = _policy()
    approval = _item(policy["transitions"], "APPROVE_HISTORICAL_CANDIDATE")
    approval["alphaquest_automatic"] = True

    with pytest.raises(OperatingModelError, match="human transition.*cannot be AlphaQuest-automatic"):
        validate_operating_model(policy)


def test_deterministic_verdict_cannot_become_discretionary_codex_authority() -> None:
    policy = _policy()
    verdict = _item(policy["transitions"], "RECORD_HISTORICAL_VERDICT")
    verdict["initiator"] = "CODEX"
    verdict["alphaquest_automatic"] = False

    with pytest.raises(OperatingModelError, match="must remain owned by ALPHAQUEST"):
        validate_operating_model(policy)


def test_machine_semantic_prohibition_cannot_be_reversed_by_prose() -> None:
    policy = _policy()
    prose = _item(policy["codex_policy"]["prohibitions"], "SELF_APPROVE_MECHANICS")
    prose["enforceable_rule"] = "Codex may approve mechanics."

    validate_operating_model(policy)


def test_machine_semantic_prohibition_effect_is_enforced() -> None:
    policy = _policy()
    prohibition = _item(policy["codex_policy"]["machine_prohibitions"], "NO_SELF_APPROVAL")
    prohibition["effect"] = "ALLOWED"

    with pytest.raises(OperatingModelError, match="must prohibit"):
        validate_operating_model(policy)


def test_ungoverned_recertification_prohibition_is_required() -> None:
    policy = _policy()
    policy["codex_policy"]["machine_prohibitions"] = [
        item
        for item in policy["codex_policy"]["machine_prohibitions"]
        if item["id"] != "NO_UNGOVERNED_RECERTIFICATION"
    ]

    with pytest.raises(OperatingModelError, match="prohibitions are incomplete"):
        validate_operating_model(policy)


def test_unknown_implementation_status_is_rejected() -> None:
    policy = _policy()
    _item(policy["transitions"], "START_FORWARD_INCUBATION")["implementation_status"] = "mostly_done"

    with pytest.raises(OperatingModelError, match="unknown implementation status"):
        validate_operating_model(policy)


def test_partial_implementation_requires_structured_runtime_gap() -> None:
    policy = _policy()
    transition = _item(policy["transitions"], "APPROVE_HISTORICAL_CANDIDATE")
    del transition["runtime_conformance"]["known_gap"]

    with pytest.raises(OperatingModelError, match="partial runtime conformance fields"):
        validate_operating_model(policy)


def test_policy_only_transition_cannot_claim_runtime_enforcement() -> None:
    policy = _policy()
    transition = _item(policy["transitions"], "PROMOTE_SHADOW_TO_SMALL_LIVE")
    transition["runtime_enforcement_claimed"] = True

    with pytest.raises(OperatingModelError, match="must disclaim runtime enforcement"):
        validate_operating_model(policy)


def test_known_runtime_gap_requires_existing_partial_status() -> None:
    policy = _policy()
    transition = _item(policy["transitions"], "APPROVE_HISTORICAL_CANDIDATE")
    transition["implementation_status"] = "EXISTING"
    del transition["runtime_conformance"]

    with pytest.raises(OperatingModelError, match="known runtime gap must be EXISTING_PARTIAL"):
        validate_operating_model(policy)


def test_p1_cannot_embed_an_excess_numeric_variant_budget() -> None:
    policy = _policy()
    policy["attempt_and_search_governance"]["variant_budget"]["p1_numeric_limit"] = 50

    with pytest.raises(OperatingModelError, match="without a P1 number"):
        validate_operating_model(policy)


def test_post_oos_tuning_same_lineage_is_prohibited() -> None:
    policy = _policy()
    policy["attempt_and_search_governance"]["post_oos_tuning_same_lineage"] = "ALLOWED"

    with pytest.raises(OperatingModelError, match="post_oos_tuning_same_lineage"):
        validate_operating_model(policy)


def test_consumed_holdout_cannot_be_reopened() -> None:
    policy = _policy()
    policy["attempt_and_search_governance"]["consumed_holdout_reopen"] = "ALLOWED"

    with pytest.raises(OperatingModelError, match="consumed_holdout_reopen"):
        validate_operating_model(policy)


def test_unbounded_rescue_attempts_are_rejected() -> None:
    policy = _policy()
    policy["attempt_and_search_governance"]["rescue_budget"]["explicit_and_predeclared"] = False

    with pytest.raises(OperatingModelError, match="bounded predeclared budget"):
        validate_operating_model(policy)


def test_rescue_budget_exhaustion_must_prohibit_more_rescues() -> None:
    policy = _policy()
    policy["attempt_and_search_governance"]["rescue_budget"][
        "budget_exhaustion_effect"
    ] = "RESCUE_ALLOWED"

    with pytest.raises(OperatingModelError, match="bounded predeclared budget"):
        validate_operating_model(policy)


def test_minor_threshold_tweak_cannot_become_a_valid_revisit() -> None:
    policy = _policy()
    policy["revisit_policy"]["valid_triggers"].append("minor_threshold_tweak")

    with pytest.raises(OperatingModelError, match="material/invalid boundary"):
        validate_operating_model(policy)


def test_material_timestamp_repair_requires_human_review() -> None:
    policy = _policy()
    timestamps = _item(policy["change_governance"]["data"]["categories"], "FIX_TIMESTAMPS")
    timestamps["human_review"] = "not_required"

    with pytest.raises(OperatingModelError, match="timestamp repair requires governed human review"):
        validate_operating_model(policy)


def test_same_contract_append_cannot_automatically_rebind_frozen_research() -> None:
    policy = _policy()
    append = _item(
        policy["change_governance"]["data"]["categories"],
        "ADD_ROWS_SAME_CERTIFIED_DATASET",
    )
    append["campaign_rebind"] = "automatic"

    with pytest.raises(OperatingModelError, match="rebinding must remain governed"):
        validate_operating_model(policy)


def test_same_contract_append_cannot_automatically_claim_research_evidence() -> None:
    policy = _policy()
    append_policy = policy["change_governance"]["data"]["same_contract_append_policy"]
    append_policy["automatic_actions"].append("claim_new_research_evidence_from_expanded_sample")

    with pytest.raises(OperatingModelError, match="automatic actions are incomplete or unsafe"):
        validate_operating_model(policy)


def test_forward_observation_requires_previous_event_hash() -> None:
    policy = _policy()
    append = _item(policy["transitions"], "APPEND_FORWARD_OBSERVATION")
    append["evidence_required"].remove("previous_event_hash")

    with pytest.raises(OperatingModelError, match="hash chain are incomplete"):
        validate_operating_model(policy)


def test_forward_observation_requires_hash_chain_validation() -> None:
    policy = _policy()
    append = _item(policy["transitions"], "APPEND_FORWARD_OBSERVATION")
    append["deterministic_checks"].remove("previous_event_hash_chain_valid")

    with pytest.raises(OperatingModelError, match="chronology, hashes, and source exclusions"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    "object_id",
    [
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
    ],
)
def test_canonical_object_mutability_is_fail_closed(object_id: str) -> None:
    policy = _policy()
    _item(policy["research_objects"], object_id)["mutability"] = "freely_mutable"

    with pytest.raises(OperatingModelError, match=f"research object {object_id} mutability must remain"):
        validate_operating_model(policy)


def test_unknown_downstream_object_reference_is_rejected() -> None:
    policy = _policy()
    candidate = _item(policy["research_objects"], "CANDIDATE_STRATEGY")
    candidate["downstream"].append("NEW_OBSERVATION_ONLY")

    with pytest.raises(OperatingModelError, match="unknown downstream references"):
        validate_operating_model(policy)


@pytest.mark.parametrize(
    ("axis", "unsafe_state"),
    [
        ("ACCOUNT_SUITABILITY_STATE", "FAIL"),
        ("PORTFOLIO_STATE", "REJECTED"),
        ("FORWARD_STATE", "ELIGIBLE_FOR_REVIEW"),
    ],
)
def test_deployment_review_requires_exact_positive_axis_states(
    axis: str,
    unsafe_state: str,
) -> None:
    policy = _policy()
    transition = _item(policy["transitions"], "ENTER_DEPLOYMENT_REVIEW")
    transition["required_axis_states"][axis] = unsafe_state

    with pytest.raises(OperatingModelError, match="exact positive deployment axis states"):
        validate_operating_model(policy)


def test_deployment_authorization_requires_complete_controls() -> None:
    policy = _policy()
    transition = _item(policy["transitions"], "AUTHORIZE_DEPLOYMENT")
    transition["required_deployment_controls"].remove("kill_rules")

    with pytest.raises(OperatingModelError, match="complete limits, allocation, and kill rules"):
        validate_operating_model(policy)


def test_discovery_path_must_reach_hypothesis_review() -> None:
    policy = _policy()
    proposal = _item(policy["transitions"], "PROPOSE_HYPOTHESIS_FOR_REVIEW")
    proposal["to_stage"] = "DISCOVERY"

    with pytest.raises(OperatingModelError, match="must be DISCOVERY -> HYPOTHESIS_REVIEW"):
        validate_operating_model(policy)


def test_monitoring_must_remain_an_operational_side_axis() -> None:
    policy = _policy()
    policy["state_axes"]["RESEARCH_LIFECYCLE_STAGE"]["values"].append("MONITORING")

    with pytest.raises(OperatingModelError, match="monitoring must be represented only"):
        validate_operating_model(policy)


def test_screening_failure_terminates_only_bound_path() -> None:
    policy = _policy()
    failure = _item(policy["transitions"], "RECORD_HISTORICAL_SCREENING_FAILURE")
    failure["campaign_effect"] = "EXHAUSTED"

    with pytest.raises(OperatingModelError, match="effect contract must remain exact"):
        validate_operating_model(policy)


def test_rejected_forward_review_cannot_advance() -> None:
    policy = _policy()
    rejection = _item(policy["transitions"], "REJECT_FORWARD_REVIEW")
    rejection["to_stage"] = "PORTFOLIO_REVIEW"

    with pytest.raises(OperatingModelError, match="canonical transition REJECT_FORWARD_REVIEW"):
        validate_operating_model(policy)
