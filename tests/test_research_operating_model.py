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
    assert policy["policy_version"] == "2026-09-01.2"
    assert policy["identity"]["current_engine_contract"] == "2026.08.14.1"
    assert policy["identity"]["current_methodology_version"] == "2026-08-14.2"
    assert policy["identity"]["methodology_changed_by_p1"] is False
    assert len(operating_model_sha256()) == 64
    assert Path(DEFAULT_OPERATING_MODEL_PATH).is_file()


def test_codex_cannot_authorize_or_promote_live_deployment() -> None:
    policy = _policy()
    authorization = _item(policy["transitions"], "AUTHORIZE_DEPLOYMENT")
    authorization["codex"] = "ALLOWED"

    with pytest.raises(OperatingModelError, match="Codex must be prohibited"):
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

    with pytest.raises(OperatingModelError, match="shortcuts historical candidate"):
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

    assert transitions["PROMOTE_SHADOW_TO_SMALL_LIVE"]["implementation_status"] == "policy_only"
    assert transitions["PROMOTE_SMALL_LIVE_TO_LIVE"]["implementation_status"] == "policy_only"
    assert transitions["SAFETY_PAUSE"]["implementation_status"] == "policy_only"
    assert _item(
        policy["invariants"],
        "POLICY_DEFINITIONS_DO_NOT_CLAIM_RUNTIME_ENFORCEMENT",
    )
