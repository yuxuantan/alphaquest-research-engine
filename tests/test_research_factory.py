from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

import pytest
from pydantic import ValidationError

from alphaquest.studio.research_factory import (
    BudgetUsageV1,
    CandidateDueDiligenceSummaryV1,
    CodexProposalEnvelopeV1,
    CodexRunProvenanceV1,
    CodexTaskType,
    CriterionOutcomeV1,
    EngineeringHandoffProposalV1,
    FactoryEvent,
    FactoryState,
    FailureClass,
    InformationAccessLedgerV1,
    InformationCategory,
    InformationGranularity,
    InformationGrantV1,
    InvalidFactoryTransitionError,
    InvalidProposalError,
    MechanicsIntentV1,
    NextAction,
    ParameterIntentV1,
    ResearchBudgetV1,
    ResultSummaryV1,
    SourceClaimV1,
    SourceEvidenceBundleV1,
    StageKind,
    StaleProposalError,
    append_information_access,
    build_codex_task,
    build_context_packet,
    classify_result_failure,
    consumed_locked_holdouts,
    determine_next_action_eligibility,
    make_information_access_event,
    object_sha256,
    transition_factory_state,
    validate_and_import_proposal,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


def _hypothesis_payload() -> dict:
    return {
        "schema": "alphaquest.hypothesis-proposal/v1",
        "hypothesis_id": "prior_liquidity_response",
        "edge_family_id": "liquidity_compensation",
        "instrument": "ES",
        "market_behavior": "Prior-session liquidity stress predicts a next-session futures response.",
        "causal_mechanism": "Inventory-constrained liquidity providers require compensation after absorbing demand.",
        "counterparty": "Urgent liquidity demanders crossing the spread under constrained capacity.",
        "information_availability_timeline": [
            "The prior session closes before its liquidity state is finalized.",
            "The frozen state becomes available before the next session entry decision.",
        ],
        "expected_holding_horizon": "Next regular trading session",
        "null_hypothesis": "The completed liquidity state has no predictive effect after realistic costs.",
        "falsifying_observations": ["Stitched unseen windows show non-positive net expectancy."],
        "confounders": ["The state may proxy for volatility rather than constrained intermediation."],
        "persistence_rationale": "Balance-sheet constraints and urgent demand should recur across independent sessions.",
        "expected_regimes": ["Elevated but orderly realized volatility"],
        "transaction_cost_sensitivity": "The effect must remain positive after declared commissions and slippage.",
        "capacity_assumptions": "One contract is small relative to normal ES displayed and traded liquidity.",
        "required_data_fields": ["timestamp", "close", "volume"],
        "source_bundle_sha256s": [HASH_A],
        "source_claim_ids": ["claim_1"],
        "research_objectives_sha256": HASH_B,
        "unresolved_questions": [],
        "status": "PROPOSAL",
        "confirmed": False,
    }


def _criterion(
    metric: str,
    *,
    passed: bool = False,
    stage: str = "core_grid",
    near: bool = False,
) -> CriterionOutcomeV1:
    return CriterionOutcomeV1(
        criterion_id=metric.replace("/", "_"),
        metric=metric,
        stage=stage,
        passed=passed,
        actual=0.5,
        threshold=1.0,
        comparator=">=",
        evidence_ref=f"result.json#{metric}",
        near_threshold=near,
    )


def _summary(
    verdict: str,
    *,
    stage_kind: StageKind = StageKind.DEVELOPMENT,
    criteria: list[CriterionOutcomeV1] | None = None,
    pnl_generated: bool = True,
    data_issues: list[str] | None = None,
    mechanics_issues: list[str] | None = None,
) -> ResultSummaryV1:
    return ResultSummaryV1(
        campaign_id="demo",
        variant_id="v01",
        result_bundle_sha256=HASH_A,
        verdict=verdict,
        failed_stage=None if verdict == "PASS" else "core_grid",
        stage_kind=stage_kind,
        criteria=criteria or [],
        data_quality_issues=data_issues or [],
        mechanics_issues=mechanics_issues or [],
        operational_issues=[],
        pnl_generated=pnl_generated,
    )


def _budget(*, holdouts: list[str] | None = None) -> ResearchBudgetV1:
    return ResearchBudgetV1(
        edge_family_id="liquidity_compensation",
        max_hypotheses=3,
        max_pnl_trials=4,
        max_variants=5,
        max_rescue_attempts=1,
        max_codex_runs=20,
        locked_holdout_window_ids=holdouts or ["holdout_a", "holdout_b"],
    )


def _usage(**overrides) -> BudgetUsageV1:
    values = {
        "edge_family_id": "liquidity_compensation",
        "hypotheses": 1,
        "pnl_trials": 1,
        "variants": 1,
        "rescue_attempts": 0,
        "codex_runs": 2,
    }
    values.update(overrides)
    return BudgetUsageV1(**values)


def _empty_ledger() -> InformationAccessLedgerV1:
    return InformationAccessLedgerV1(events=[])


def _diagnosis(verdict: str, *, stage_kind: StageKind = StageKind.DEVELOPMENT, pnl=False):
    if verdict == "PASS":
        summary = _summary("PASS", criteria=[], pnl_generated=pnl)
    elif verdict == "FAIL":
        summary = _summary(
            "FAIL",
            stage_kind=stage_kind,
            criteria=[_criterion("profit_factor")],
            pnl_generated=True,
        )
    else:
        summary = _summary(
            "NEEDS MANUAL REVIEW",
            criteria=[],
            pnl_generated=pnl,
            mechanics_issues=["mechanics_validation.json#entry_timing"],
        )
    return classify_result_failure(summary, diagnosis_id=f"diagnosis_{verdict.lower().replace(' ', '_')}")


def test_strict_versioned_research_contracts_reject_extra_or_unreviewed_authority():
    source = SourceEvidenceBundleV1(
        bundle_id="source_1",
        title="Liquidity provision and futures returns",
        authors=["A Researcher"],
        year=2024,
        locator="https://example.test/paper",
        publication_type="PEER_REVIEWED",
        venue="Journal of Market Microstructure",
        retrieved_at=NOW,
        content_sha256=None,
        verification_status="PARTIAL",
        retraction_status="UNKNOWN",
        claims=[
            SourceClaimV1(
                claim_id="claim_1",
                statement="Liquidity constraints are followed by measurable compensation in prices.",
                source_location="Section 4",
                support="DIRECT",
                evidence_sha256=HASH_B,
            )
        ],
        conflicting_evidence=[],
        inference_notes=[],
        created_by="codex-local",
    )
    assert source.model_dump(by_alias=True)["schema"] == "alphaquest.source-evidence-bundle/v1"
    assert source.confirmed is False

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourceEvidenceBundleV1.model_validate({**source.model_dump(), "approved": True})
    with pytest.raises(ValidationError, match="Input should be False"):
        SourceEvidenceBundleV1.model_validate({**source.model_dump(), "confirmed": True})


def test_mechanics_intent_enforces_certification_and_parameter_budgets():
    parameters = [
        ParameterIntentV1(
            parameter_id="lookback",
            methodology_category="entry",
            reviewed_default=10,
            candidate_values=[5, 10],
            tunable=True,
            rationale="Measures the predeclared liquidity-state horizon.",
        ),
        ParameterIntentV1(
            parameter_id="threshold",
            methodology_category="entry",
            reviewed_default=2.0,
            candidate_values=[1.5, 2.0],
            tunable=True,
            rationale="Defines the predeclared state extremity threshold.",
        ),
        ParameterIntentV1(
            parameter_id="stop_points",
            methodology_category="sl",
            reviewed_default=3.0,
            candidate_values=[2.0, 3.0],
            tunable=True,
            rationale="Bounds adverse movement after the causal state is invalidated.",
        ),
    ]
    intent = MechanicsIntentV1(
        mechanics_id="mechanics_1",
        hypothesis_id="prior_liquidity_response",
        hypothesis_sha256=HASH_A,
        variant_id="v01",
        execution_lane="CERTIFIED_RECIPE",
        certified_strategy_id="prior_state_response",
        unsupported_reason=None,
        signal_availability="Prior state is finalized before the entry decision.",
        entry_state_machine=["Observe the completed state.", "Enter at the next eligible bar open."],
        entry_timing="Next eligible bar open after signal availability.",
        invalidation_condition="The predeclared state threshold is no longer satisfied.",
        stop_semantics="Place a tick-rounded protective stop immediately after entry.",
        target_and_exit_semantics="Exit at the certified target or forced session flatten.",
        session_boundaries="Use configured exchange sessions and flatten before the cutoff.",
        reentry_policy="Permit no more than one entry per completed state per session.",
        position_limits="Use one contract and never pyramid or hold overnight.",
        required_data_fields=["timestamp", "close", "volume"],
        parameters=parameters,
        rationale="This is the smallest certified expression of the frozen causal hypothesis.",
    )
    assert intent.confirmed is False

    too_narrow = intent.model_dump()
    too_narrow["parameters"] = [parameters[0].model_dump()]
    with pytest.raises(ValidationError, match="8 to 120 combinations"):
        MechanicsIntentV1.model_validate(too_narrow)

    uncertified = intent.model_dump()
    uncertified["certified_strategy_id"] = None
    with pytest.raises(ValidationError, match="requires certified_strategy_id"):
        MechanicsIntentV1.model_validate(uncertified)


def test_handoff_and_candidate_contracts_preserve_manual_review_boundaries():
    handoff = EngineeringHandoffProposalV1(
        handoff_id="handoff_1",
        campaign_id="demo",
        hypothesis_sha256=HASH_A,
        reviewed_hypothesis_artifact_sha256=HASH_B,
        mechanics_intent_sha256=HASH_C,
        reviewed_mechanics_artifact_sha256=HASH_D,
        proposed_variant_id="v01",
        reason_unsupported="The event sequence cannot be represented by an existing certified strategy.",
        causal_timeline=["Observe an event using only records available before the decision."],
        required_data_granularity="Event-level records",
        fill_and_ambiguity_rules=["Resolve simultaneous stop and target pessimistically."],
        required_module_contract=["Use the generic event replay runner."],
        required_tests=["Verify entry timing and no-lookahead behavior."],
        proposed_mechanic="Implement one stateful event mechanic through the certified factory contract.",
    )
    assert handoff.status == "NEEDS MANUAL REVIEW"
    assert handoff.confirmed is False

    candidate = CandidateDueDiligenceSummaryV1(
        summary_id="summary_1",
        campaign_id="demo",
        variant_id="v01",
        result_bundle_sha256=HASH_A,
        mechanics_approval_sha256=HASH_B,
        robustness_evidence=["Stitched OOS result meets the frozen acceptance criteria."],
        limitations=["Historical results cannot establish future profitability."],
        unresolved_risks=["Forward regime drift remains unobserved."],
        forward_requirements=["Complete the immutable forward-incubation plan."],
        recommendation="ELIGIBLE_FOR_HUMAN_REVIEW",
    )
    assert candidate.automatic_deployment_permitted is False
    assert candidate.human_approval_required is True


def test_factory_state_machine_is_explicit_and_fail_closed():
    state = FactoryState.READY_FOR_RESEARCH
    for event, expected in (
        (FactoryEvent.PREPARE_CODEX_TASK, FactoryState.CODEX_TASK_PREPARED),
        (FactoryEvent.QUEUE_CODEX, FactoryState.WAITING_FOR_CODEX),
        (FactoryEvent.START_CODEX, FactoryState.CODEX_RUNNING),
        (FactoryEvent.ACCEPT_CODEX_OUTPUT, FactoryState.PROPOSAL_READY),
        (FactoryEvent.ROUTE_MECHANICS_REVIEW, FactoryState.WAITING_FOR_MECHANICS_APPROVAL),
        (FactoryEvent.APPROVE_MECHANICS, FactoryState.READY_FOR_TESTING),
        (FactoryEvent.START_TESTING, FactoryState.TESTING),
        (FactoryEvent.RECORD_RESULT, FactoryState.RESULT_READY_FOR_DIAGNOSIS),
    ):
        state = transition_factory_state(state, event)
        assert state == expected

    assert transition_factory_state(
        FactoryState.CODEX_RUNNING,
        FactoryEvent.CODEX_UNAVAILABLE,
    ) == FactoryState.WAITING_FOR_CODEX
    assert transition_factory_state(
        FactoryState.WAITING_FOR_MECHANICS_APPROVAL,
        FactoryEvent.REJECT_MECHANICS,
    ) == FactoryState.NEEDS_MANUAL_REVIEW
    with pytest.raises(InvalidFactoryTransitionError, match="not legal"):
        transition_factory_state(FactoryState.READY_FOR_RESEARCH, FactoryEvent.START_TESTING)
    with pytest.raises(InvalidFactoryTransitionError, match="not legal"):
        transition_factory_state(FactoryState.TERMINAL_PASS, FactoryEvent.PREPARE_SUCCESSOR)


def test_context_packet_is_detached_hash_bound_and_blocks_holdout_from_design(tmp_path):
    source = {"edge": "liquidity compensation", "trials": ["failed_one"]}
    source_before = json.loads(json.dumps(source))
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({"max_variants": 5}), encoding="utf-8")
    grants = [
        InformationGrantV1(
            artifact_name="inventory",
            category=InformationCategory.RESEARCH_INVENTORY,
            granularity=InformationGranularity.METADATA,
            allowed_use="Compare the proposed economic edge with prior research.",
        ),
        InformationGrantV1(
            artifact_name="policy",
            category=InformationCategory.CAMPAIGN_POLICY,
            granularity=InformationGranularity.METADATA,
            allowed_use="Constrain the proposal to current research policy.",
        ),
    ]
    packet = build_context_packet(
        task_id="task_1",
        task_type=CodexTaskType.HYPOTHESIS_PROPOSAL,
        objective="Propose one falsifiable hypothesis from verified evidence.",
        artifacts={"inventory": source, "policy": policy_path},
        allowed_information=grants,
        forbidden_information=["Locked holdout results", "Live deployment credentials"],
        built_at=NOW,
        allowed_roots=[tmp_path],
    )
    source["trials"].append("mutated_after_snapshot")
    assert packet.artifacts[0].content == source_before
    assert packet.inputs_sha256 != packet.packet_sha256
    assert set(packet.artifact_hashes) == {"inventory", "policy"}
    assert str(tmp_path) not in json.dumps(packet.model_dump(mode="json"))

    holdout_grant = InformationGrantV1(
        artifact_name="holdout",
        category=InformationCategory.LOCKED_HOLDOUT_RESULT,
        granularity=InformationGranularity.AGGREGATE,
        allowed_use="Diagnose the already terminal frozen candidate result.",
        data_window_id="holdout_a",
        locked_holdout=True,
    )
    with pytest.raises(ValueError, match="locked-holdout information cannot enter"):
        build_context_packet(
            task_id="task_2",
            task_type=CodexTaskType.NEXT_EXPERIMENT,
            objective="Choose the next bounded experiment without tuning a holdout.",
            artifacts={"holdout": {"profit_factor": 0.8}},
            allowed_information=[holdout_grant],
            forbidden_information=["Trade-level holdout results"],
            built_at=NOW,
        )


def _proposal_fixture(current_artifacts: dict):
    grant = InformationGrantV1(
        artifact_name="source",
        category=InformationCategory.SOURCE,
        granularity=InformationGranularity.METADATA,
        allowed_use="Create one falsifiable and source-bound hypothesis proposal.",
    )
    context = build_context_packet(
        task_id="task_hypothesis",
        task_type=CodexTaskType.HYPOTHESIS_PROPOSAL,
        objective="Produce one strict hypothesis proposal without changing repository state.",
        artifacts=current_artifacts,
        allowed_information=[grant],
        forbidden_information=["Market result tables"],
        built_at=NOW,
    )
    task = build_codex_task(
        context,
        expected_output_schema="alphaquest.hypothesis-proposal/v1",
        created_at=NOW,
    )
    payload = _hypothesis_payload()
    provenance = CodexRunProvenanceV1(
        run_id="run_1",
        task_id=task.task_id,
        model="subscription-codex",
        codex_version="codex-cli 0.148.0-alpha.9",
        authentication_mode="CHATGPT_SUBSCRIPTION",
        runtime_request_sha256=HASH_A,
        prompt_sha256=HASH_B,
        output_schema_sha256=HASH_C,
        repository_revision="abc123",
        dirty_tree_sha256=HASH_C,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=5),
        exit_status="SUCCEEDED",
    )
    envelope = CodexProposalEnvelopeV1(
        proposal_id="proposal_1",
        task_id=task.task_id,
        task_type=task.task_type,
        task_sha256=task.task_sha256,
        context_packet_sha256=context.packet_sha256,
        inputs_sha256=context.inputs_sha256,
        input_artifact_hashes=context.artifact_hashes,
        proposal_schema=task.expected_output_schema,
        payload=payload,
        payload_sha256=object_sha256(payload),
        produced_at=NOW + timedelta(seconds=5),
        provenance=provenance,
    )
    return context, task, envelope


def test_proposal_import_is_pure_strict_and_stale_safe():
    artifacts = {"source": {"title": "Verified source", "content_sha256": HASH_A}}
    context, task, envelope = _proposal_fixture(artifacts)
    imported = validate_and_import_proposal(
        envelope,
        expected_task=task,
        original_context=context,
        current_artifacts=artifacts,
        validated_at=NOW + timedelta(seconds=6),
    )
    assert imported.status == "VALIDATED_NOT_APPLIED"
    assert imported.durable_writes_performed is False
    assert imported.validated_payload["schema"] == "alphaquest.hypothesis-proposal/v1"

    changed = {"source": {"title": "Changed source", "content_sha256": HASH_A}}
    with pytest.raises(StaleProposalError, match="context inputs changed"):
        validate_and_import_proposal(
            envelope,
            expected_task=task,
            original_context=context,
            current_artifacts=changed,
        )

    bad_payload = dict(envelope.payload)
    bad_payload["unexpected_authority"] = "APPROVED"
    bad_envelope = envelope.model_copy(
        update={"payload": bad_payload, "payload_sha256": object_sha256(bad_payload)}
    )
    with pytest.raises(InvalidProposalError, match="Extra inputs are not permitted"):
        validate_and_import_proposal(
            bad_envelope,
            expected_task=task,
            original_context=context,
            current_artifacts=artifacts,
        )

    wrong_task = envelope.model_copy(update={"task_sha256": HASH_A})
    with pytest.raises(StaleProposalError, match="task_sha256"):
        validate_and_import_proposal(
            wrong_task,
            expected_task=task,
            original_context=context,
            current_artifacts=artifacts,
        )

    nested_mutation = task.model_copy(deep=True)
    nested_mutation.artifact_hashes["source"] = HASH_B
    with pytest.raises(StaleProposalError, match="integrity check failed"):
        validate_and_import_proposal(
            envelope,
            expected_task=nested_mutation,
            original_context=context,
            current_artifacts=artifacts,
        )


def test_path_backed_context_is_rehashed_when_proposal_is_imported(tmp_path):
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps({"claim": "original"}), encoding="utf-8")
    artifacts = {"source": source_path}
    context, task, envelope = _proposal_fixture(artifacts)
    source_path.write_text(json.dumps({"claim": "changed"}), encoding="utf-8")

    with pytest.raises(StaleProposalError, match="context inputs changed"):
        validate_and_import_proposal(
            envelope,
            expected_task=task,
            original_context=context,
            current_artifacts=artifacts,
        )


def test_failure_classification_uses_all_failed_criteria_and_preserves_verdict():
    summary = _summary(
        "FAIL",
        criteria=[
            _criterion("net_after_cost_profit_factor"),
            _criterion("trades_per_year"),
            _criterion("parameter_neighbour_stability"),
            _criterion("max_drawdown"),
            _criterion("monthly_consistency", passed=True, near=True),
        ],
    )
    diagnosis = classify_result_failure(summary, diagnosis_id="diagnosis_1")
    assert diagnosis.verdict == "FAIL"
    assert set(diagnosis.classifications) == {
        FailureClass.COST_SENSITIVE,
        FailureClass.TRADE_DENSITY,
        FailureClass.PARAMETER_INSTABILITY,
        FailureClass.TAIL_RISK,
    }
    assert len(diagnosis.failed_criteria) == 4
    assert [item.metric for item in diagnosis.near_failed_criteria] == ["monthly_consistency"]

    manual = classify_result_failure(
        _summary(
            "NEEDS MANUAL REVIEW",
            criteria=[],
            pnl_generated=False,
            data_issues=["dataset_manifest.json#quality"],
            mechanics_issues=["mechanics_validation.json#entry_timing"],
        ),
        diagnosis_id="diagnosis_2",
    )
    assert manual.classifications == [FailureClass.DATA_QUALITY, FailureClass.MECHANICS_DEFECT]

    passed = classify_result_failure(_summary("PASS"), diagnosis_id="diagnosis_3")
    assert passed.classifications == []
    assert passed.failed_criteria == []


def test_information_access_ledger_is_hash_chained_and_consumes_locked_holdouts():
    ledger = _empty_ledger()
    first = make_information_access_event(
        ledger=ledger,
        access_id="access_1",
        task_id="diagnose_1",
        edge_family_id="liquidity_compensation",
        campaign_id="demo",
        variant_id="v01",
        category=InformationCategory.LOCKED_HOLDOUT_RESULT,
        granularity=InformationGranularity.AGGREGATE,
        data_window_id="holdout_a",
        locked_holdout=True,
        purpose="Diagnose the terminal result without changing its historical evidence.",
        actor="codex-local",
        artifact_sha256=HASH_A,
        accessed_at=NOW,
    )
    ledger = append_information_access(ledger, first)
    second = make_information_access_event(
        ledger=ledger,
        access_id="access_2",
        task_id="candidate_1",
        edge_family_id="liquidity_compensation",
        campaign_id="demo",
        variant_id="v01",
        category=InformationCategory.DEVELOPMENT_RESULT,
        granularity=InformationGranularity.METADATA,
        data_window_id=None,
        locked_holdout=False,
        purpose="Prepare a read-only candidate review evidence index.",
        actor="codex-local",
        artifact_sha256=HASH_B,
        accessed_at=NOW + timedelta(seconds=1),
    )
    ledger = append_information_access(ledger, second)
    assert consumed_locked_holdouts(
        ledger,
        edge_family_id="liquidity_compensation",
    ) == {"holdout_a"}

    tampered = ledger.model_dump(mode="json", by_alias=True)
    tampered["events"][0]["artifact_sha256"] = HASH_C
    with pytest.raises(ValidationError, match="event_sha256"):
        InformationAccessLedgerV1.model_validate_json(json.dumps(tampered))

    stale_branch = make_information_access_event(
        ledger=_empty_ledger(),
        access_id="stale_access",
        task_id="stale_task",
        edge_family_id="liquidity_compensation",
        campaign_id="demo",
        variant_id="v01",
        category=InformationCategory.DEVELOPMENT_RESULT,
        granularity=InformationGranularity.METADATA,
        data_window_id=None,
        locked_holdout=False,
        purpose="Attempt to append from a stale empty-ledger head.",
        actor="codex-local",
        artifact_sha256=HASH_C,
        accessed_at=NOW,
    )
    with pytest.raises(ValueError, match="does not extend"):
        append_information_access(ledger, stale_branch)


def test_next_action_policy_separates_pass_manual_fail_and_holdout_research_generations():
    budget = _budget()
    usage = _usage()
    ledger = _empty_ledger()

    passed = determine_next_action_eligibility(
        _diagnosis("PASS"),
        diagnosis_sha256=HASH_A,
        budget=budget,
        usage=usage,
        ledger=ledger,
        pnl_generated=True,
    )
    assert passed.eligible_actions == [NextAction.BEGIN_CANDIDATE_REVIEW]
    assert NextAction.PROPOSE_SUCCESSOR.value in passed.blocked_actions

    manual = determine_next_action_eligibility(
        _diagnosis("NEEDS MANUAL REVIEW", pnl=False),
        diagnosis_sha256=HASH_A,
        budget=budget,
        usage=usage,
        ledger=ledger,
        pnl_generated=False,
    )
    assert set(manual.eligible_actions) == {
        NextAction.OBTAIN_MANUAL_REVIEW,
        NextAction.REPAIR_SAME_VARIANT,
    }
    assert NextAction.PROPOSE_SUCCESSOR.value in manual.blocked_actions

    failed_development = determine_next_action_eligibility(
        _diagnosis("FAIL"),
        diagnosis_sha256=HASH_A,
        budget=budget,
        usage=usage,
        ledger=ledger,
        pnl_generated=True,
    )
    assert NextAction.PROPOSE_SUCCESSOR in failed_development.eligible_actions

    account_failure = classify_result_failure(
        _summary(
            "FAIL",
            criteria=[_criterion("destination_account_fit")],
            pnl_generated=True,
        ),
        diagnosis_id="diagnosis_account_failure",
    )
    account_failure_actions = determine_next_action_eligibility(
        account_failure,
        diagnosis_sha256=HASH_A,
        budget=budget,
        usage=usage,
        ledger=ledger,
        pnl_generated=True,
    )
    assert FailureClass.ACCOUNT_UNSUITABLE in account_failure.classifications
    assert NextAction.ASSESS_OTHER_DESTINATION not in account_failure_actions.eligible_actions
    assert "scientific-validity PASS" in account_failure_actions.blocked_actions[
        NextAction.ASSESS_OTHER_DESTINATION.value
    ]

    access = make_information_access_event(
        ledger=ledger,
        access_id="access_holdout_a",
        task_id="diagnose_holdout",
        edge_family_id="liquidity_compensation",
        campaign_id="demo",
        variant_id="v01",
        category=InformationCategory.LOCKED_HOLDOUT_RESULT,
        granularity=InformationGranularity.AGGREGATE,
        data_window_id="holdout_a",
        locked_holdout=True,
        purpose="Diagnose the terminal locked-holdout result for disposition only.",
        actor="codex-local",
        artifact_sha256=HASH_A,
        accessed_at=NOW,
    )
    ledger = append_information_access(ledger, access)
    failed_holdout = determine_next_action_eligibility(
        _diagnosis("FAIL", stage_kind=StageKind.LOCKED_HOLDOUT),
        diagnosis_sha256=HASH_A,
        budget=budget,
        usage=usage,
        ledger=ledger,
        pnl_generated=True,
    )
    assert NextAction.PROPOSE_SUCCESSOR not in failed_holdout.eligible_actions
    assert NextAction.START_NEW_RESEARCH_GENERATION in failed_holdout.eligible_actions
    assert failed_holdout.fresh_locked_holdout_window_ids == ["holdout_b"]

    access_b = make_information_access_event(
        ledger=ledger,
        access_id="access_holdout_b",
        task_id="diagnose_holdout_b",
        edge_family_id="liquidity_compensation",
        campaign_id="demo",
        variant_id="v02",
        category=InformationCategory.LOCKED_HOLDOUT_RESULT,
        granularity=InformationGranularity.AGGREGATE,
        data_window_id="holdout_b",
        locked_holdout=True,
        purpose="Record that the final fresh confirmation window has been exposed.",
        actor="codex-local",
        artifact_sha256=HASH_B,
        accessed_at=NOW + timedelta(seconds=1),
    )
    exhausted_ledger = append_information_access(ledger, access_b)
    exhausted = determine_next_action_eligibility(
        _diagnosis("FAIL", stage_kind=StageKind.FINAL_ACCEPTANCE),
        diagnosis_sha256=HASH_A,
        budget=budget,
        usage=usage,
        ledger=exhausted_ledger,
        pnl_generated=True,
    )
    assert NextAction.STOP_NO_FRESH_HOLDOUT in exhausted.eligible_actions
    assert NextAction.START_NEW_RESEARCH_GENERATION not in exhausted.eligible_actions


def test_trial_and_variant_budgets_block_adaptive_successors():
    eligibility = determine_next_action_eligibility(
        _diagnosis("FAIL"),
        diagnosis_sha256=HASH_A,
        budget=_budget(),
        usage=_usage(pnl_trials=4, variants=5),
        ledger=_empty_ledger(),
        pnl_generated=True,
    )
    assert NextAction.PROPOSE_SUCCESSOR not in eligibility.eligible_actions
    reason = eligibility.blocked_actions[NextAction.PROPOSE_SUCCESSOR.value]
    assert "trial budget is exhausted" in reason
    assert "variant budget is exhausted" in reason
