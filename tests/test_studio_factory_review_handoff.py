from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphaquest.studio.api import register_api_routes
from alphaquest.studio.codex_runtime import (
    CodexAuthenticationMode,
    CodexAvailabilityStatus,
    CodexAvailabilityV1,
    CodexOutputMetadataV1,
    CodexRunProvenanceV1,
    CodexRunResultV1,
    CodexRunStatus,
    CodexSandboxMode,
    _model_sha256,
)
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.factory_reviews import (
    EngineeringHandoffIntentHumanAcceptanceV1,
    HYPOTHESIS_REVIEW_FIELDS,
    HypothesisHumanAcceptanceV1,
    MECHANICS_REVIEW_FIELDS,
    SOURCE_METADATA_FIELDS,
    SourceEvidenceHumanVerificationV1,
)
from alphaquest.studio.factory_service import ResearchFactoryService


HASH_A = "a" * 64
HASH_B = "b" * 64


def _draft(project_root: Path) -> Path:
    return DraftStore(project_root).save(
        "structured_factory",
        {
            "schema": "alphaquest.campaign-draft/v1",
            "campaign_id": "structured_factory",
            "title": "Test a source-supported intraday futures behavior",
            "instrument": "ES",
            "timeframe": "1m",
            "research_objectives": {
                "schema": "alphaquest.research-objectives/v1",
                "development_goal": "Determine whether this futures edge survives the complete frozen protocol.",
                "development_deadline": "2027-08-25",
                "evaluation_horizon_months": 24,
                "minimum_annualized_return_fraction": 0.2,
                "minimum_mar": 0.4,
                "maximum_drawdown_fraction": 0.1,
                "minimum_complete_wfa_windows": 3,
                "minimum_wfa_oos_trades": 50,
                "minimum_acceptance_oos_trades": 30,
                "monte_carlo_min_runs": 8000,
                "monte_carlo_horizon_months": 6,
                "minimum_net_profit_probability": 0.7,
                "maximum_account_breach_probability": 0.1,
                "forward_incubation_min_calendar_days": 90,
                "forward_incubation_min_trades": 30,
                "maximum_variants": 5,
                "abandonment_rules": ["Stop when a frozen scientific gate fails."],
                "retirement_rules": ["Retire after governed live degradation."],
                "confirmed": True,
            },
            "variant_protocol": "sequential_failure_informed",
            "sequential_variant_history": [],
            "frozen": False,
        },
        wizard_step=1,
    )


def _source_proposal() -> dict[str, object]:
    return {
        "schema": "alphaquest.source-evidence-bundle/v1",
        "bundle_id": "exchange_source_1",
        "title": "Exchange study of a persistent intraday futures behavior",
        "authors": ["Exchange Research Team"],
        "year": 2025,
        "locator": "https://example.invalid/source.pdf",
        "publication_type": "EXCHANGE_RESEARCH",
        "venue": "Example Exchange",
        "retrieved_at": "2026-08-25T00:00:00Z",
        "content_sha256": None,
        "verification_status": "PARTIAL",
        "retraction_status": "UNKNOWN",
        "claims": [
            {
                "claim_id": "direct_1",
                "statement": "The source reports a persistent response after a fully observed liquidity condition.",
                "source_location": "page 7, figure 2",
                "support": "DIRECT",
                "evidence_sha256": None,
            },
            {
                "claim_id": "inference_1",
                "statement": "The reported response may extend to the selected market under similar participation.",
                "source_location": "human inference from pages 7 to 9",
                "support": "INFERENCE",
                "evidence_sha256": None,
            },
        ],
        "conflicting_evidence": ["The source reports weaker effects in its highest-volatility subsample."],
        "inference_notes": ["Futures-market transfer remains a falsifiable inference."],
        "created_by": "codex_subscription",
        "confirmed": False,
    }


class FakeRunner:
    def __init__(self, proposal: dict[str, object]) -> None:
        self.proposal = proposal
        self.run_count = 0

    def probe(self) -> CodexAvailabilityV1:
        return CodexAvailabilityV1(
            status=CodexAvailabilityStatus.AVAILABLE,
            executable_available=True,
            authenticated=True,
            authentication_mode=CodexAuthenticationMode.CHATGPT,
            version="codex-cli test",
            checked_at=datetime.now(UTC),
            detail="subscription authenticated",
        )

    def run(self, task, *, task_id, cancellation_requested=None, heartbeat=None):
        self.run_count += 1
        if heartbeat:
            heartbeat()
        now = datetime.now(UTC)
        encoded = json.dumps(self.proposal, sort_keys=True).encode("utf-8")
        provenance = CodexRunProvenanceV1(
            run_id=f"run-{task_id}",
            task_id=task_id,
            task_sha256=_model_sha256(task),
            prompt_sha256=hashlib.sha256(task.prompt.encode("utf-8")).hexdigest(),
            output_schema_sha256=hashlib.sha256(
                json.dumps(task.output_schema, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            input_hashes=task.input_hashes,
            workspace_root=task.workspace_root,
            sandbox=CodexSandboxMode.READ_ONLY,
            requested_model=None,
            codex_version="codex-cli test",
            command_argv=["codex", "exec", "--sandbox", "read-only"],
            thread_id=None,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            exit_code=0,
        )
        output = CodexOutputMetadataV1(
            output_sha256=hashlib.sha256(encoded).hexdigest(),
            output_bytes=len(encoded),
            stdout_sha256=hashlib.sha256(b"").hexdigest(),
            stdout_bytes=0,
            stderr_sha256=hashlib.sha256(b"").hexdigest(),
            stderr_bytes=0,
            schema_validated=True,
        )
        return CodexRunResultV1(
            status=CodexRunStatus.SUCCEEDED,
            proposal=self.proposal,
            provenance=provenance,
            output_metadata=output,
        )


def _hypothesis_proposal(bindings: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "alphaquest.hypothesis-proposal/v1",
        "hypothesis_id": "structured_liquidity_response",
        "edge_family_id": bindings["edge_family_id"],
        "instrument": bindings["instrument"],
        "market_behavior": "A completed intraday liquidity condition predicts a later, separately timed futures response.",
        "causal_mechanism": "Inventory-constrained intermediaries demand compensation after absorbing urgent order flow.",
        "counterparty": "Urgent liquidity demanders trading against constrained intermediaries.",
        "information_availability_timeline": [
            "The source state is calculated only after all contributing events are observed.",
            "Any entry decision occurs after the completed state becomes available.",
        ],
        "expected_holding_horizon": "Same regular trading session",
        "null_hypothesis": "The completed condition has no positive unseen expectancy after realistic costs.",
        "falsifying_observations": ["Stitched unseen windows show non-positive net expectancy."],
        "confounders": ["The state may proxy for volatility rather than intermediary inventory."],
        "persistence_rationale": "Liquidity demand and constrained intermediation are recurring market functions.",
        "expected_regimes": ["Liquid regular sessions with two-sided participation."],
        "transaction_cost_sensitivity": "The edge must remain positive after commissions and pessimistic slippage.",
        "capacity_assumptions": "One-contract tests do not establish institutional capacity.",
        "required_data_fields": ["timestamp", "price", "size", "side"],
        "source_bundle_sha256s": bindings["source_bundle_sha256s"],
        "source_claim_ids": bindings["source_claim_ids"],
        "research_objectives_sha256": bindings["research_objectives_sha256"],
        "unresolved_questions": ["Whether the response survives unseen regimes remains unknown."],
        "status": "PROPOSAL",
        "confirmed": False,
    }


def _mechanics_proposal(binding: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "alphaquest.mechanics-intent/v1",
        "mechanics_id": "structured_handoff_v01",
        "hypothesis_id": binding["hypothesis_id"],
        "hypothesis_sha256": binding["hypothesis_sha256"],
        "variant_id": "v01",
        "execution_lane": "ENGINEERING_HANDOFF",
        "certified_strategy_id": None,
        "unsupported_reason": "No current certified event package expresses the required ordered liquidity state.",
        "signal_availability": "Every state transition uses only events observed before the decision timestamp.",
        "entry_state_machine": ["Observe the complete state, then wait for a separately timed confirmation event."],
        "entry_timing": "Enter only after the confirmation event is fully available.",
        "invalidation_condition": "Invalidate when the reviewed state no longer holds before confirmation.",
        "stop_semantics": "Place a pessimistically ordered structural stop immediately after entry.",
        "target_and_exit_semantics": "Use a frozen causal exit and force flatten before the configured cutoff.",
        "session_boundaries": "Use configured exchange sessions in America/New_York and never hold overnight.",
        "reentry_policy": "Require a new independently completed state before re-entry.",
        "position_limits": "Hold at most one bounded position and never pyramid.",
        "required_data_fields": ["timestamp", "price", "size", "side", "session_id"],
        "parameters": [],
        "rationale": "The smallest causal expression requires an event order not present in a certified package.",
        "status": "PROPOSAL",
        "confirmed": False,
    }


def test_structured_reviews_preserve_full_proposals_and_drive_exact_next_context(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "alphaquest.studio.factory_service._certified_catalog",
        lambda _root: [],
    )
    draft_path = _draft(tmp_path)
    initial_draft = draft_path.read_bytes()
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))

    source_task = service.enqueue_next(
        campaign_id="structured_factory",
        request_id="structured-source-task",
    )
    service.run_worker_once(worker_id="source-worker")
    source_review = SourceEvidenceHumanVerificationV1(
        review_id="source_human_review_1",
        reviewer="Researcher One",
        reviewed_at=datetime.now(UTC),
        verified_metadata_fields=list(SOURCE_METADATA_FIELDS),
        content_sha256=HASH_A,
        retraction_status="NOT_RETRACTED",
        verification_method="Opened the captured PDF and checked its publisher metadata and retraction index.",
        claim_reviews=[
            {
                "claim_id": "direct_1",
                "proposed_support": "DIRECT",
                "decision": "ACCEPT",
                "evidence_sha256": HASH_B,
                "verification_method": "Compared the claim to the captured page and figure.",
                "notes": "The figure directly supports the narrower descriptive statement.",
            },
            {
                "claim_id": "inference_1",
                "proposed_support": "INFERENCE",
                "decision": "REJECT",
                "evidence_sha256": None,
                "verification_method": "Checked the source population against the proposed transfer.",
                "notes": "The source does not directly establish transfer to this market.",
            },
        ],
        notes="Accepted one directly evidenced claim and retained the rejected inference in the artifact.",
    )
    reviewed_source = service.record_reviewed_source_evidence(
        str(source_task["task_id"]),
        verification=source_review,
    )
    assert reviewed_source["source_evidence"]["claims"] == _source_proposal()["claims"]
    assert reviewed_source["source_evidence"]["verification_status"] == "PARTIAL"
    assert reviewed_source["human_verification"]["source_identity_status"] == "VERIFIED"
    assert draft_path.read_bytes() == initial_draft

    hypothesis_plan = service._discover_plan("structured_factory")
    assert hypothesis_plan["task_type"] == "HYPOTHESIS_PROPOSAL"
    assert hypothesis_plan["artifacts"]["reviewed_source_evidence"] == [reviewed_source]
    bindings = hypothesis_plan["artifacts"]["research_bindings"]
    assert bindings["reviewed_source_artifact_sha256s"] == [reviewed_source["artifact_sha256"]]
    assert bindings["source_claim_ids"] == ["exchange_source_1.direct_1"]

    service.runner = FakeRunner(_hypothesis_proposal(bindings))
    hypothesis_task = service.enqueue_next(
        campaign_id="structured_factory",
        request_id="structured-hypothesis-task",
    )
    service.run_worker_once(worker_id="hypothesis-worker")
    before_hypothesis_review = draft_path.read_bytes()
    reviewed_hypothesis = service.record_reviewed_hypothesis(
        str(hypothesis_task["task_id"]),
        acceptance=HypothesisHumanAcceptanceV1(
            review_id="hypothesis_human_review_1",
            reviewer="Researcher One",
            reviewed_at=datetime.now(UTC),
            reviewed_fields=list(HYPOTHESIS_REVIEW_FIELDS),
            objective_alignment="PASS",
            source_claim_alignment="PASS",
            falsifiability="PASS",
            information_timeline_no_lookahead="PASS",
            execution_cost_awareness="PASS",
            notes="Reviewed every structured field against the accepted claim and research objectives.",
        ),
    )
    assert reviewed_hypothesis["hypothesis"] == _hypothesis_proposal(bindings)
    assert reviewed_hypothesis["reviewed_source_artifact_sha256s"] == [
        reviewed_source["artifact_sha256"]
    ]
    assert draft_path.read_bytes() == before_hypothesis_review

    document = DraftStore(tmp_path).load("structured_factory")
    draft = dict(document["draft"])
    draft.update(
        {
            "duplicate_review": {"conclusion": "distinct"},
            "dataset": {"dataset_id": "es_events", "quality_verdict": "PASS"},
            "execution": {"session_start": "09:30:00", "forced_flatten": "15:55:00"},
        }
    )
    DraftStore(tmp_path).save("structured_factory", draft, wizard_step=4)
    mechanics_plan = service._discover_plan("structured_factory")
    assert mechanics_plan["task_type"] == "MECHANICS_INTENT"
    assert mechanics_plan["artifacts"]["reviewed_hypothesis"] == reviewed_hypothesis
    binding = mechanics_plan["artifacts"]["hypothesis_binding"]
    assert binding["reviewed_hypothesis_artifact_sha256"] == reviewed_hypothesis["artifact_sha256"]

    service.runner = FakeRunner(_mechanics_proposal(binding))
    mechanics_task = service.enqueue_next(
        campaign_id="structured_factory",
        request_id="structured-mechanics-task",
    )
    service.run_worker_once(worker_id="mechanics-worker")
    reviewed_mechanics = service.record_reviewed_engineering_handoff_intent(
        str(mechanics_task["task_id"]),
        acceptance=EngineeringHandoffIntentHumanAcceptanceV1(
            review_id="engineering_intent_human_review_1",
            reviewer="Researcher One",
            reviewed_at=datetime.now(UTC),
            reviewed_fields=list(MECHANICS_REVIEW_FIELDS),
            hypothesis_alignment="PASS",
            unsupported_scope_confirmed="PASS",
            causal_timeline_reviewed="PASS",
            notes="Confirmed that the reviewed intent is unsupported and should stop at an engineering handoff.",
        ),
    )
    assert reviewed_mechanics["mechanics_intent"] == _mechanics_proposal(binding)
    handoff_plan = service._discover_plan("structured_factory")
    assert handoff_plan["task_type"] == "ENGINEERING_HANDOFF"
    handoff_binding = handoff_plan["artifacts"]["engineering_handoff_binding"]
    assert handoff_binding["mechanics_intent_sha256"] == reviewed_mechanics["mechanics_intent_sha256"]
    assert handoff_binding["reviewed_mechanics_artifact_sha256"] == reviewed_mechanics["artifact_sha256"]
    assert "certified_catalog" not in handoff_plan["artifacts"]
    service.runner = FakeRunner(
        {
            "schema": "alphaquest.engineering-handoff-proposal/v1",
            "handoff_id": "structured_engineering_handoff_v01",
            "campaign_id": handoff_binding["campaign_id"],
            "hypothesis_sha256": handoff_binding["hypothesis_sha256"],
            "reviewed_hypothesis_artifact_sha256": handoff_binding[
                "reviewed_hypothesis_artifact_sha256"
            ],
            "mechanics_intent_sha256": handoff_binding["mechanics_intent_sha256"],
            "reviewed_mechanics_artifact_sha256": handoff_binding[
                "reviewed_mechanics_artifact_sha256"
            ],
            "proposed_variant_id": "v01",
            "reason_unsupported": "The reviewed ordered event state is not available in a certified package.",
            "causal_timeline": ["Observe every required event before evaluating the later confirmation."],
            "required_data_granularity": "Event-level records",
            "fill_and_ambiguity_rules": ["Resolve simultaneous stop and target pessimistically."],
            "required_module_contract": ["Use the generic canonical event replay runner."],
            "required_tests": ["Verify session logic, entry timing, no lookahead, and forced flatten."],
            "proposed_mechanic": "Implement the reviewed state machine as one repository-owned event strategy module.",
            "status": "NEEDS MANUAL REVIEW",
            "confirmed": False,
        }
    )
    handoff_task = service.enqueue_next(
        campaign_id="structured_factory",
        request_id="structured-engineering-handoff-task",
    )
    handoff_result = service.run_worker_once(worker_id="handoff-worker")
    assert handoff_result is not None
    assert handoff_result["proposal_validation"]["status"] == "VALIDATED_NOT_APPLIED"
    assert handoff_result["applied"] is False
    assert handoff_result["approved"] is False


def test_source_review_is_one_shot_and_requires_every_claim(tmp_path: Path) -> None:
    _draft(tmp_path)
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="one-shot-source-task")
    service.run_worker_once(worker_id="source-worker")
    base = {
        "review_id": "source_human_review_1",
        "reviewer": "Researcher One",
        "reviewed_at": datetime.now(UTC),
        "verified_metadata_fields": list(SOURCE_METADATA_FIELDS),
        "content_sha256": HASH_A,
        "retraction_status": "NOT_RETRACTED",
        "verification_method": "Opened and captured the source.",
        "claim_reviews": [
            {
                "claim_id": "direct_1",
                "proposed_support": "DIRECT",
                "decision": "ACCEPT",
                "evidence_sha256": HASH_B,
                "verification_method": "Checked the page.",
                "notes": "Direct support is present.",
            }
        ],
        "notes": "Human review notes.",
    }
    try:
        service.record_reviewed_source_evidence(str(task["task_id"]), verification=base)
    except ValueError as exc:
        assert "every proposed claim" in str(exc)
    else:
        raise AssertionError("an incomplete source-claim review was accepted")

    base["claim_reviews"].append(
        {
            "claim_id": "inference_1",
            "proposed_support": "INFERENCE",
            "decision": "REJECT",
            "evidence_sha256": None,
            "verification_method": "Checked transfer scope.",
            "notes": "Transfer remains unsupported.",
        }
    )
    service.record_reviewed_source_evidence(str(task["task_id"]), verification=base)
    try:
        service.record_reviewed_source_evidence(str(task["task_id"]), verification=base)
    except RuntimeError as exc:
        assert "immutable" in str(exc)
    else:
        raise AssertionError("a second human source review overwrote the first")
    artifact_path = (
        service.review_root
        / "structured_factory"
        / "source"
        / f"{task['task_id']}.json"
    )
    tampered = json.loads(artifact_path.read_text(encoding="utf-8"))
    tampered["human_verification"]["notes"] = "Tampered after acceptance."
    artifact_path.write_text(json.dumps(tampered), encoding="utf-8")
    blocked = service._discover_plan("structured_factory")
    assert blocked["eligible"] is False
    assert blocked["label"] == "Repair reviewed factory provenance"


def test_reviewed_source_api_requires_explicit_hashes_and_advances_factory(tmp_path: Path) -> None:
    draft_path = _draft(tmp_path)
    before = draft_path.read_bytes()
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="api-source-review")
    service.run_worker_once(worker_id="api-source-worker")
    app = FastAPI()
    register_api_routes(app, tmp_path)
    client = TestClient(app)
    payload = {
        "reviewer": "Researcher One",
        "notes": "Checked the captured primary source and retained the unsupported inference as rejected.",
        "verified_metadata_fields": list(SOURCE_METADATA_FIELDS),
        "content_sha256": HASH_A,
        "retraction_status": "NOT_RETRACTED",
        "verification_method": "Opened the captured source and checked publisher metadata.",
        "claim_reviews": [
            {
                "claim_id": "direct_1",
                "proposed_support": "DIRECT",
                "decision": "ACCEPT",
                "evidence_sha256": HASH_B,
                "verification_method": "Checked page 7 and figure 2.",
                "notes": "Direct support is present for the narrow claim.",
            },
            {
                "claim_id": "inference_1",
                "proposed_support": "INFERENCE",
                "decision": "REJECT",
                "evidence_sha256": None,
                "verification_method": "Checked source population and transfer scope.",
                "notes": "The proposed market transfer is not directly supported.",
            },
        ],
    }
    invalid = {**payload, "content_sha256": "not-a-hash"}
    assert client.post(
        f"/api/factory/tasks/{task['task_id']}/reviewed-source-evidence",
        json=invalid,
    ).status_code == 422
    response = client.post(
        f"/api/factory/tasks/{task['task_id']}/reviewed-source-evidence",
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["campaign_mutated"] is False
    assert body["mechanics_approved"] is False
    assert body["testing_authorized"] is False
    assert body["reviewed_artifact"]["source_evidence"]["verification_status"] == "PARTIAL"
    detail = client.get(f"/api/factory/tasks/{task['task_id']}").json()["task"]
    assert detail["structured_review"]["status"] == "ACCEPTED_FOR_HYPOTHESIS"
    assert draft_path.read_bytes() == before
