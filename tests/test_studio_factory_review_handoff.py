from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

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
from alphaquest.research.literature.contracts import (
    ActorProvenanceV1,
    SourceCaptureRevisionV1,
    SourceIdentityRevisionV1,
    SourceVersionIdentityRevisionV1,
)
from alphaquest.research.literature.store import LiteratureStore
from alphaquest.studio.factory_reviews import (
    EngineeringHandoffIntentHumanAcceptanceV1,
    HYPOTHESIS_REVIEW_FIELDS,
    HypothesisHumanAcceptanceV1,
    MECHANICS_REVIEW_FIELDS,
    SOURCE_METADATA_FIELDS,
    ReviewedSourceEvidenceArtifactV2,
    SourceEvidenceHumanVerificationV1,
    SourceEvidenceHumanVerificationV2,
    build_reviewed_source_evidence_v2,
)
from alphaquest.studio.factory_service import ResearchFactoryService, _identity_token
from alphaquest.studio.research_factory import CodexTaskType, SourceEvidenceBundleV1


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


def _fulltext_capture(
    project_root: Path,
    *,
    suffix: str = "source",
    source_category: str = "EXCHANGE",
    version_kind: str = "ORIGINAL",
    capture_status: str = "FULL_TEXT_CAPTURED",
    start_first: bool = False,
    locator: str | None = None,
    work_locators: list[str] | None = None,
    version_strong_identifiers: dict[str, str] | None = None,
    retained_bytes: bytes | None = None,
    extracted_representation_bytes: bytes | None = None,
):
    store = LiteratureStore(project_root)
    actor = ActorProvenanceV1(
        actor_class="HUMAN_OWNER_RESEARCHER",
        actor_id="source-review-fixture",
    )
    proposal = _source_proposal()
    source_locator = locator or str(proposal["locator"])
    work = store.append_work(
        {
            "work_id": f"work.{suffix}",
            "source_category": source_category,
            "title": proposal["title"],
            "authors": proposal["authors"],
            "strong_identifiers": {},
            "locators": work_locators or [source_locator],
            "identity_status": "VERIFIED_STRONG",
            "change_reason": "Test fixture identity",
        },
        actor=actor,
        idempotency_key=f"work.{suffix}",
    )
    version = store.append_source_version(
        {
            "source_version_id": f"version.{suffix}",
            "work_id": work.work_id,
            "work_revision_sha256": work.record_sha256,
            "version_kind": version_kind,
            "version_label": "2025 exchange publication",
            "strong_identifiers": version_strong_identifiers or {},
            "public_availability": {
                "original_value": "2025",
                "parsed_value": None,
                "precision": "YEAR",
                "verification": "VERIFIED",
                "timezone_basis": None,
                "provenance_record_ids": [],
            },
            "identity_status": "VERIFIED_STRONG",
            "change_reason": "Test fixture version",
        },
        actor=actor,
        idempotency_key=f"version.{suffix}",
    )
    content = (
        retained_bytes
        if retained_bytes is not None
        else b"Complete retained source document used by the source-review fixture."
    )
    extracted = (
        extracted_representation_bytes
        if extracted_representation_bytes is not None
        else content
    )
    content_sha = store.put_artifact(content, kind="artifacts")
    extracted_sha = store.put_artifact(extracted, kind="extracted")
    capture_payload = {
            "capture_id": f"capture.{suffix}",
            "source_version_id": version.source_version_id,
            "source_version_revision_sha256": version.record_sha256,
            "retrieval_locator": source_locator,
            "status": capture_status,
            "captured_at": datetime.now(UTC),
            "access_basis": "OWNER_PROVIDED",
            "local_retention_permission": "ALLOWED",
            "redistribution_permission": "RESTRICTED",
            "external_model_processing_permission": "LOCAL_ONLY",
            "media_type": "application/pdf",
            "content_sha256": content_sha,
            "content_bytes": len(content),
            "extracted_representation_sha256": extracted_sha,
            "extracted_bytes": len(extracted),
            "extractor_id": "fixture-extractor",
            "extractor_version": "1",
            "extractor_config_sha256": hashlib.sha256(b"fixture-extractor-v1").hexdigest(),
            "failure_reason": None,
        }
    if start_first:
        store.append_capture(
            {
                "capture_id": capture_payload["capture_id"],
                "source_version_id": capture_payload["source_version_id"],
                "source_version_revision_sha256": capture_payload["source_version_revision_sha256"],
                "retrieval_locator": capture_payload["retrieval_locator"],
                "status": "STARTED",
                "captured_at": capture_payload["captured_at"],
                "access_basis": capture_payload["access_basis"],
                "local_retention_permission": capture_payload["local_retention_permission"],
                "redistribution_permission": capture_payload["redistribution_permission"],
                "external_model_processing_permission": capture_payload["external_model_processing_permission"],
                "media_type": None,
                "content_sha256": None,
                "content_bytes": None,
                "extracted_representation_sha256": None,
                "extracted_bytes": None,
                "extractor_id": None,
                "extractor_version": None,
                "extractor_config_sha256": None,
                "failure_reason": None,
            },
            actor=actor,
            idempotency_key=f"capture.{suffix}.start",
        )
        capture_payload = {
            key: value for key, value in capture_payload.items()
            if key == "capture_id" or key in {
                "status", "media_type", "content_sha256", "content_bytes",
                "extracted_representation_sha256", "extracted_bytes", "extractor_id",
                "extractor_version", "extractor_config_sha256", "failure_reason",
            }
        }
    return store.append_capture(
        capture_payload,
        actor=actor,
        idempotency_key=f"capture.{suffix}.finish" if start_first else f"capture.{suffix}",
    )


def _source_review_payload(capture: SourceCaptureRevisionV1) -> dict[str, object]:
    return {
        "review_id": "human_source_review",
        "reviewer": "Researcher One",
        "reviewed_at": datetime.now(UTC),
        "verified_metadata_fields": list(SOURCE_METADATA_FIELDS),
        "content_sha256": capture.content_sha256,
        "retraction_status": "NOT_RETRACTED",
        "verification_method": "Opened the exact retained document and checked publisher metadata.",
        "claim_reviews": [
            {"claim_id": "direct_1", "proposed_support": "DIRECT", "decision": "ACCEPT", "evidence_sha256": capture.extracted_representation_sha256, "verification_method": "Checked the retained full text.", "notes": "Direct claim verified."},
            {"claim_id": "inference_1", "proposed_support": "INFERENCE", "decision": "REJECT", "evidence_sha256": None, "verification_method": "Checked transfer scope.", "notes": "Transfer remains unsupported."},
        ],
        "notes": "Human review retained all limitations.",
    }


def _append_version_relationship(
    project_root: Path,
    *,
    relationship_id: str,
    subject_id: str,
    predicate: str,
    object_id: str,
    status: str = "ACTIVE",
):
    return LiteratureStore(project_root).append_source_relationship(
        {
            "relationship_id": relationship_id,
            "subject_kind": "SOURCE_VERSION",
            "subject_id": subject_id,
            "predicate": predicate,
            "object_kind": "SOURCE_VERSION",
            "object_id": object_id,
            "status": status,
            "assertion_evidence_refs": [],
            "superseded_by_relationship_id": None,
            "change_reason": f"Source review fixture {predicate} {status}",
        },
        actor=ActorProvenanceV1(
            actor_class="HUMAN_OWNER_RESEARCHER", actor_id="source-review-fixture"
        ),
        idempotency_key=f"{relationship_id}.{status.lower()}",
    )


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
    capture = _fulltext_capture(tmp_path)

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
        content_sha256=capture.content_sha256,
        retraction_status="NOT_RETRACTED",
        verification_method="Opened the captured PDF and checked its publisher metadata and retraction index.",
        claim_reviews=[
            {
                "claim_id": "direct_1",
                "proposed_support": "DIRECT",
                "decision": "ACCEPT",
                "evidence_sha256": capture.extracted_representation_sha256,
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
        capture_revision_sha256=capture.record_sha256,
    )
    assert reviewed_source["source_evidence"]["claims"] == _source_proposal()["claims"]
    assert reviewed_source["source_evidence"]["verification_status"] == "PARTIAL"
    assert reviewed_source["human_verification"]["source_identity_status"] == "VERIFIED"
    detail = service.get_task(str(source_task["task_id"]))
    assert detail["structured_review"]["artifact"] == reviewed_source
    assert detail["structured_review"]["decision"] == "ACCEPT_FOR_HYPOTHESIS"
    assert detail["structured_review"]["proposal_payload_sha256"] == reviewed_source["proposal_payload_sha256"]
    summary = service.public_task(service.queue.get(str(source_task["task_id"])))
    assert "artifact" not in summary["structured_review"]
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
    assert service.get_task(str(hypothesis_task["task_id"]))["structured_review"]["artifact"] == reviewed_hypothesis
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
    receipt = service.get_task(str(mechanics_task["task_id"]))["structured_review"]
    assert receipt["artifact"] == reviewed_mechanics
    assert receipt["decision"] == "ACCEPT_FOR_ENGINEERING_HANDOFF"
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
    capture = _fulltext_capture(tmp_path)
    task = service.enqueue_next(campaign_id="structured_factory", request_id="one-shot-source-task")
    service.run_worker_once(worker_id="source-worker")
    base = {
        "review_id": "source_human_review_1",
        "reviewer": "Researcher One",
        "reviewed_at": datetime.now(UTC),
        "verified_metadata_fields": list(SOURCE_METADATA_FIELDS),
        "content_sha256": capture.content_sha256,
        "retraction_status": "NOT_RETRACTED",
        "verification_method": "Opened and captured the source.",
        "claim_reviews": [
            {
                "claim_id": "direct_1",
                "proposed_support": "DIRECT",
                "decision": "ACCEPT",
                "evidence_sha256": capture.extracted_representation_sha256,
                "verification_method": "Checked the page.",
                "notes": "Direct support is present.",
            }
        ],
        "notes": "Human review notes.",
    }
    try:
        service.record_reviewed_source_evidence(
            str(task["task_id"]), verification=base,
            capture_revision_sha256=capture.record_sha256,
        )
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
    service.record_reviewed_source_evidence(
        str(task["task_id"]), verification=base,
        capture_revision_sha256=capture.record_sha256,
    )
    try:
        service.record_reviewed_source_evidence(
            str(task["task_id"]), verification=base,
            capture_revision_sha256=capture.record_sha256,
        )
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
    capture = _fulltext_capture(tmp_path)
    task = service.enqueue_next(campaign_id="structured_factory", request_id="api-source-review")
    service.run_worker_once(worker_id="api-source-worker")
    app = FastAPI()
    register_api_routes(app, tmp_path)
    client = TestClient(app)
    payload = {
        "reviewer": "Researcher One",
        "notes": "Checked the captured primary source and retained the unsupported inference as rejected.",
        "verified_metadata_fields": list(SOURCE_METADATA_FIELDS),
        "capture_revision_sha256": capture.record_sha256,
        "retraction_status": "NOT_RETRACTED",
        "verification_method": "Opened the captured source and checked publisher metadata.",
        "claim_reviews": [
            {
                "claim_id": "direct_1",
                "proposed_support": "DIRECT",
                "decision": "ACCEPT",
                "evidence_sha256": capture.extracted_representation_sha256,
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
    validation = service.get_task(str(task["task_id"]))["proposal_validation"]
    payload["delivery"] = {
        "operation_id": "api-source-review-delivery",
        "proposal_id": validation["proposal_id"],
        "payload_sha256": validation["payload_sha256"],
        "validation_sha256": validation["validation_sha256"],
    }
    invalid = {**payload, "capture_revision_sha256": "not-a-hash"}
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
    assert detail["structured_review"]["artifact"] == body["reviewed_artifact"]
    assert detail["structured_review"]["notes"] == payload["notes"]
    reopened = ResearchFactoryService(tmp_path).get_task(str(task["task_id"]))
    assert reopened["structured_review"] == detail["structured_review"]
    assert draft_path.read_bytes() == before


def test_source_review_readiness_requires_current_matching_fulltext_and_real_bytes(tmp_path: Path) -> None:
    _draft(tmp_path)
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="capture-readiness")
    service.run_worker_once(worker_id="capture-readiness-worker")

    assert service.source_review_readiness(str(task["task_id"]))["status"] == "NOT_READY"
    with pytest.raises(ValueError, match="absent"):
        service.record_reviewed_source_evidence(
            str(task["task_id"]), verification={}, capture_revision_sha256=HASH_A,
        )

    abstract = _fulltext_capture(
        tmp_path, suffix="abstract", capture_status="GENUINE_ABSTRACT_CAPTURED"
    )
    working = _fulltext_capture(
        tmp_path, suffix="working", source_category="WORKING_PAPER",
        version_kind="WORKING_PAPER_REVISION",
    )
    case_sensitive_mismatch = _fulltext_capture(
        tmp_path, suffix="path-case", locator="https://example.invalid/Source.pdf"
    )
    fulltext = _fulltext_capture(tmp_path, suffix="eligible", start_first=True)
    readiness = service.source_review_readiness(str(task["task_id"]))
    by_id = {item["capture_id"]: item for item in readiness["options"]}
    assert by_id[abstract.capture_id]["issues"] == ["ABSTRACT_NOT_FULL_TEXT"]
    assert "PUBLICATION_CATEGORY_MISMATCH" in by_id[working.capture_id]["issues"]
    assert "LOCATOR_OR_STRONG_IDENTIFIER_MISMATCH" in by_id[
        case_sensitive_mismatch.capture_id
    ]["issues"]
    assert by_id[fulltext.capture_id]["readiness"] == "READY"

    start_revision = next(
        item for item in LiteratureStore(tmp_path).records()
        if isinstance(item, SourceCaptureRevisionV1)
        and item.capture_id == fulltext.capture_id and item.revision == 1
    )
    with pytest.raises(ValueError, match="absent"):
        service.record_reviewed_source_evidence(
            str(task["task_id"]), verification={},
            capture_revision_sha256=start_revision.record_sha256,
        )

    artifact_path = (
        tmp_path / "run-store" / "literature" / "extracted" / "sha256"
        / str(fulltext.extracted_representation_sha256)[:2]
        / str(fulltext.extracted_representation_sha256)
    )
    artifact_path.unlink()
    changed = service.source_review_readiness(str(task["task_id"]))
    assert "CAPTURE_ARTIFACT_UNAVAILABLE_OR_INVALID" in next(
        item for item in changed["options"] if item["capture_id"] == fulltext.capture_id
    )["issues"]


@pytest.mark.parametrize(
    ("raw", "extracted", "expected_issues"),
    [
        (b"", b"inspectable extraction", ["CAPTURE_RAW_CONTENT_EMPTY"]),
        (b"retained raw document", b"", ["CAPTURE_EXTRACTED_REPRESENTATION_EMPTY"]),
        (
            b"",
            b"",
            ["CAPTURE_EXTRACTED_REPRESENTATION_EMPTY", "CAPTURE_RAW_CONTENT_EMPTY"],
        ),
    ],
    ids=("empty-raw", "empty-extraction", "both-empty"),
)
def test_empty_capture_artifacts_block_readiness_write_and_downstream_v2_use(
    tmp_path: Path,
    raw: bytes,
    extracted: bytes,
    expected_issues: list[str],
) -> None:
    _draft(tmp_path)
    capture = _fulltext_capture(
        tmp_path,
        suffix="empty-artifact",
        retained_bytes=raw,
        extracted_representation_bytes=extracted,
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(
        campaign_id="structured_factory", request_id="empty-artifact-source"
    )
    service.run_worker_once(worker_id="empty-artifact-worker")
    task_id = str(task["task_id"])

    readiness = service.source_review_readiness(task_id)
    option = next(
        item for item in readiness["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert option["readiness"] == "NOT_READY"
    assert option["issues"] == expected_issues
    with pytest.raises(ValueError, match="CAPTURE_.*_EMPTY"):
        service.record_reviewed_source_evidence(
            task_id,
            verification=_source_review_payload(capture),
            capture_revision_sha256=capture.record_sha256,
        )
    review_path = service._review_artifact_path(
        "structured_factory", "source", task_id
    )
    assert not review_path.exists()

    # Represent a validly hashed receipt produced before this readiness rule.
    # Its immutable bytes remain readable as history but cannot supply current
    # downstream source authority.
    record, campaign_id, validation, imported = service._reviewable_proposal(
        task_id, expected_task_type=CodexTaskType.SOURCE_RESEARCH,
    )
    source = SourceEvidenceBundleV1.model_validate_json(
        json.dumps(imported.validated_payload, sort_keys=True)
    )
    verification = SourceEvidenceHumanVerificationV2.model_validate(
        {**_source_review_payload(capture), "capture_binding": option["binding"]}
    )
    artifact = build_reviewed_source_evidence_v2(
        campaign_id=campaign_id,
        task_id=record.task_id,
        proposal_id=imported.proposal_id,
        proposal_payload_sha256=imported.payload_sha256,
        proposal_validation_sha256=validation["validation_sha256"],
        source_evidence=source,
        human_verification=verification,
    )
    service._write_review_once(
        review_path, artifact.model_dump(mode="json", by_alias=True)
    )
    historical_bytes = review_path.read_bytes()
    assert ReviewedSourceEvidenceArtifactV2.model_validate_json(historical_bytes) == artifact
    assert service._discover_plan("structured_factory")["label"] == "Repair reviewed factory provenance"
    assert review_path.read_bytes() == historical_bytes


def test_nonempty_raw_and_extraction_remain_review_ready(tmp_path: Path) -> None:
    _draft(tmp_path)
    capture = _fulltext_capture(
        tmp_path,
        suffix="nonempty-artifacts",
        retained_bytes=b"%PDF retained raw document",
        extracted_representation_bytes=b"Inspectable extracted text",
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(
        campaign_id="structured_factory", request_id="nonempty-artifact-source"
    )
    service.run_worker_once(worker_id="nonempty-artifact-worker")
    task_id = str(task["task_id"])
    option = next(
        item for item in service.source_review_readiness(task_id)["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert option["readiness"] == "READY"
    artifact = service.record_reviewed_source_evidence(
        task_id,
        verification=_source_review_payload(capture),
        capture_revision_sha256=capture.record_sha256,
    )
    assert artifact["schema"] == "alphaquest.reviewed-source-evidence/v2"


def test_source_locator_matching_is_version_specific_with_two_versions_of_one_work(
    tmp_path: Path,
) -> None:
    _draft(tmp_path)
    proposal_locator = str(_source_proposal()["locator"])
    other_locator = "https://example.invalid/other-version.pdf"
    wrong_capture = _fulltext_capture(
        tmp_path,
        suffix="same-work-wrong",
        locator=other_locator,
        work_locators=[proposal_locator, other_locator],
        version_strong_identifiers={"url": other_locator},
    )
    store = LiteratureStore(tmp_path)
    work = store.latest(SourceIdentityRevisionV1, "work.same-work-wrong")
    store.append_source_version(
        {
            "source_version_id": "version.same-work-proposed",
            "work_id": work.work_id,
            "work_revision_sha256": work.record_sha256,
            "version_kind": "ORIGINAL",
            "version_label": "Exact proposed publication",
            "strong_identifiers": {"url": proposal_locator},
            "public_availability": {
                "original_value": "2025", "parsed_value": None,
                "precision": "YEAR", "verification": "VERIFIED",
                "timezone_basis": None, "provenance_record_ids": [],
            },
            "identity_status": "VERIFIED_STRONG",
            "change_reason": "Second exact version has no captured full text",
        },
        actor=ActorProvenanceV1(
            actor_class="HUMAN_OWNER_RESEARCHER", actor_id="source-review-fixture"
        ),
        idempotency_key="version.same-work-proposed",
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="same-work-versions")
    service.run_worker_once(worker_id="same-work-version-worker")

    option = next(
        item for item in service.source_review_readiness(str(task["task_id"]))["options"]
        if item["capture_id"] == wrong_capture.capture_id
    )
    assert option["readiness"] == "NOT_READY"
    assert "LOCATOR_OR_STRONG_IDENTIFIER_MISMATCH" in option["issues"]

    doi_proposal = _source_proposal()
    doi_proposal["locator"] = "https://doi.org/10.1234/proposed"
    contradictory = _fulltext_capture(
        tmp_path,
        suffix="contradictory-version-doi",
        locator="https://doi.org/10.1234/proposed",
        version_strong_identifiers={"doi": "10.1234/other"},
    )
    doi_service = ResearchFactoryService(tmp_path, runner=FakeRunner(doi_proposal))
    doi_task = doi_service.enqueue_next(
        campaign_id="structured_factory", request_id="contradictory-version-doi"
    )
    doi_service.run_worker_once(worker_id="contradictory-version-doi-worker")
    contradictory_option = next(
        item for item in doi_service.source_review_readiness(str(doi_task["task_id"]))["options"]
        if item["capture_id"] == contradictory.capture_id
    )
    assert contradictory_option["readiness"] == "NOT_READY"
    assert "LOCATOR_OR_STRONG_IDENTIFIER_MISMATCH" in contradictory_option["issues"]


def test_doi_identity_requires_a_whole_doi_or_genuine_resolver() -> None:
    assert _identity_token("10.1234/Source.(A)") == _identity_token(
        "https://DOI.org/10.1234/source.(a)"
    )
    assert _identity_token("doi: 10.1234/source") == "doi:10.1234/source"
    assert _identity_token("10.1234/source)") != _identity_token("10.1234/source")
    assert _identity_token(
        "https://unrelated.example/document?reference=10.1234/source"
    ) != _identity_token("10.1234/source")


@pytest.mark.parametrize(
    ("version_identifiers", "capture_locator"),
    [
        (
            {"url": "https://publisher.example/article/proposed", "doi": "10.1234/expected"},
            "https://doi.org/10.1234/wrong",
        ),
        (
            {"doi": "10.1234/wrong", "url": "https://publisher.example/article/proposed"},
            "https://doi.org/10.1234/expected",
        ),
        (
            {"url": "https://publisher.example/article/proposed", "doi_primary": "10.1234/expected", "doi_secondary": "10.1234/wrong"},
            "https://doi.org/10.1234/expected",
        ),
        (
            {"doi_secondary": "10.1234/wrong", "url": "https://publisher.example/article/proposed", "doi_primary": "10.1234/expected"},
            "https://doi.org/10.1234/expected",
        ),
    ],
    ids=("capture-doi-conflict", "version-doi-conflict", "internal-doi-conflict", "internal-doi-permutation"),
)
def test_doi_contradictions_block_readiness_and_review_write_independently_of_proposal_url(
    tmp_path: Path,
    version_identifiers: dict[str, str],
    capture_locator: str,
) -> None:
    _draft(tmp_path)
    proposal = _source_proposal()
    proposal["locator"] = "https://publisher.example/article/proposed"
    capture = _fulltext_capture(
        tmp_path,
        suffix="cross-family-doi-conflict",
        locator=capture_locator,
        version_strong_identifiers=version_identifiers,
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(proposal))
    task = service.enqueue_next(
        campaign_id="structured_factory", request_id="cross-family-doi-conflict"
    )
    service.run_worker_once(worker_id="cross-family-doi-conflict-worker")

    option = next(
        item for item in service.source_review_readiness(str(task["task_id"]))["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert option["readiness"] == "NOT_READY"
    assert "LOCATOR_OR_STRONG_IDENTIFIER_MISMATCH" in option["issues"]
    with pytest.raises(ValueError, match="LOCATOR_OR_STRONG_IDENTIFIER_MISMATCH"):
        service.record_reviewed_source_evidence(
            str(task["task_id"]),
            verification=_source_review_payload(capture),
            capture_revision_sha256=capture.record_sha256,
        )
    assert not service._review_artifact_path(
        "structured_factory", "source", str(task["task_id"])
    ).exists()


def test_publisher_url_with_consistent_version_and_capture_doi_is_review_ready(
    tmp_path: Path,
) -> None:
    _draft(tmp_path)
    publisher_url = "https://publisher.example/article/proposed"
    proposal = _source_proposal()
    proposal["locator"] = publisher_url
    capture = _fulltext_capture(
        tmp_path,
        suffix="consistent-cross-family-doi",
        locator="https://doi.org/10.1234/expected",
        version_strong_identifiers={"url": publisher_url, "doi": "10.1234/expected"},
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(proposal))
    task = service.enqueue_next(
        campaign_id="structured_factory", request_id="consistent-cross-family-doi"
    )
    service.run_worker_once(worker_id="consistent-cross-family-doi-worker")

    option = next(
        item for item in service.source_review_readiness(str(task["task_id"]))["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert option["readiness"] == "READY"
    artifact = service.record_reviewed_source_evidence(
        str(task["task_id"]),
        verification=_source_review_payload(capture),
        capture_revision_sha256=capture.record_sha256,
    )
    assert artifact["schema"] == "alphaquest.reviewed-source-evidence/v2"


@pytest.mark.parametrize(
    ("predicate", "expected_issue"),
    (("RETRACTS", "SOURCE_VERSION_RETRACTED"), ("CORRECTS", "SOURCE_VERSION_CORRECTED")),
)
def test_active_canonical_reliability_relationship_blocks_review_before_submission(
    tmp_path: Path, predicate: str, expected_issue: str,
) -> None:
    _draft(tmp_path)
    capture = _fulltext_capture(tmp_path, suffix=f"pre-{predicate.lower()}")
    notice = _fulltext_capture(tmp_path, suffix=f"notice-{predicate.lower()}")
    _append_version_relationship(
        tmp_path,
        relationship_id=f"relationship.pre-{predicate.lower()}",
        subject_id=notice.source_version_id,
        predicate=predicate,
        object_id=capture.source_version_id,
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id=f"pre-{predicate.lower()}")
    service.run_worker_once(worker_id=f"pre-{predicate.lower()}-worker")

    option = next(
        item for item in service.source_review_readiness(str(task["task_id"]))["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert option["readiness"] == "NOT_READY"
    assert expected_issue in option["issues"]
    with pytest.raises(ValueError, match=expected_issue):
        service.record_reviewed_source_evidence(
            str(task["task_id"]), verification=_source_review_payload(capture),
            capture_revision_sha256=capture.record_sha256,
        )


def test_retraction_of_resolved_equivalent_version_blocks_selected_capture(tmp_path: Path) -> None:
    _draft(tmp_path)
    capture = _fulltext_capture(tmp_path, suffix="resolved-selected")
    equivalent = _fulltext_capture(tmp_path, suffix="resolved-equivalent")
    notice = _fulltext_capture(tmp_path, suffix="resolved-notice")
    _append_version_relationship(
        tmp_path, relationship_id="relationship.resolved-equivalence",
        subject_id=equivalent.source_version_id, predicate="SAME_VERSION_AS",
        object_id=capture.source_version_id,
    )
    _append_version_relationship(
        tmp_path, relationship_id="relationship.resolved-retraction",
        subject_id=notice.source_version_id, predicate="RETRACTS",
        object_id=equivalent.source_version_id,
    )
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="resolved-retraction")
    service.run_worker_once(worker_id="resolved-retraction-worker")

    option = next(
        item for item in service.source_review_readiness(str(task["task_id"]))["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert "SOURCE_VERSION_RETRACTED" in option["issues"]


def test_relationship_currentness_stales_downstream_without_rewriting_receipt(
    tmp_path: Path,
) -> None:
    _draft(tmp_path)
    capture = _fulltext_capture(tmp_path, suffix="relationship-currentness")
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="relationship-currentness")
    service.run_worker_once(worker_id="relationship-currentness-worker")
    service.record_reviewed_source_evidence(
        str(task["task_id"]), verification=_source_review_payload(capture),
        capture_revision_sha256=capture.record_sha256,
    )
    path = service._review_artifact_path("structured_factory", "source", str(task["task_id"]))
    original = path.read_bytes()
    notice = _fulltext_capture(tmp_path, suffix="relationship-currentness-notice")
    relationship = _append_version_relationship(
        tmp_path, relationship_id="relationship.currentness-retraction",
        subject_id=notice.source_version_id, predicate="RETRACTS",
        object_id=capture.source_version_id,
    )
    assert service._discover_plan("structured_factory")["label"] == "Repair reviewed factory provenance"
    assert path.read_bytes() == original
    assert ReviewedSourceEvidenceArtifactV2.model_validate_json(original)

    _append_version_relationship(
        tmp_path, relationship_id=relationship.relationship_id,
        subject_id=relationship.subject_id, predicate=relationship.predicate,
        object_id=relationship.object_id, status="RETRACTED",
    )
    selected = next(
        item for item in service.source_review_readiness(str(task["task_id"]))["options"]
        if item["capture_id"] == capture.capture_id
    )
    assert selected["readiness"] == "READY"
    assert service._discover_plan("structured_factory")["label"] == "Repair reviewed factory provenance"
    assert path.read_bytes() == original


def test_equivalence_currentness_is_component_scoped_and_unrelated_relations_do_not_stale(
    tmp_path: Path,
) -> None:
    _draft(tmp_path)
    capture = _fulltext_capture(tmp_path, suffix="component-selected")
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="component-currentness")
    service.run_worker_once(worker_id="component-currentness-worker")
    service.record_reviewed_source_evidence(
        str(task["task_id"]), verification=_source_review_payload(capture),
        capture_revision_sha256=capture.record_sha256,
    )
    unrelated_a = _fulltext_capture(tmp_path, suffix="unrelated-a")
    unrelated_b = _fulltext_capture(tmp_path, suffix="unrelated-b")
    _append_version_relationship(
        tmp_path, relationship_id="relationship.unrelated-equivalence",
        subject_id=unrelated_a.source_version_id, predicate="SAME_VERSION_AS",
        object_id=unrelated_b.source_version_id,
    )
    assert service._discover_plan("structured_factory")["task_type"] == "HYPOTHESIS_PROPOSAL"

    equivalent = _fulltext_capture(tmp_path, suffix="component-equivalent")
    relationship = _append_version_relationship(
        tmp_path, relationship_id="relationship.component-equivalence",
        subject_id=equivalent.source_version_id, predicate="SAME_VERSION_AS",
        object_id=capture.source_version_id,
    )
    assert service._discover_plan("structured_factory")["label"] == "Repair reviewed factory provenance"
    _append_version_relationship(
        tmp_path, relationship_id=relationship.relationship_id,
        subject_id=relationship.subject_id, predicate=relationship.predicate,
        object_id=relationship.object_id, status="RETRACTED",
    )
    assert service._discover_plan("structured_factory")["label"] == "Repair reviewed factory provenance"


def test_source_review_rejects_fake_hash_and_stale_canonical_work(tmp_path: Path) -> None:
    _draft(tmp_path)
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    capture = _fulltext_capture(tmp_path, suffix="stale-check")
    task = service.enqueue_next(campaign_id="structured_factory", request_id="stale-capture-review")
    service.run_worker_once(worker_id="stale-capture-worker")
    review = {
        "review_id": "human_source_review",
        "reviewer": "Researcher One",
        "reviewed_at": datetime.now(UTC),
        "verified_metadata_fields": list(SOURCE_METADATA_FIELDS),
        "content_sha256": HASH_A,
        "retraction_status": "NOT_RETRACTED",
        "verification_method": "Opened the exact retained document and checked publisher metadata.",
        "claim_reviews": [
            {"claim_id": "direct_1", "proposed_support": "DIRECT", "decision": "ACCEPT", "evidence_sha256": capture.extracted_representation_sha256, "verification_method": "Checked the retained full text.", "notes": "Direct claim verified."},
            {"claim_id": "inference_1", "proposed_support": "INFERENCE", "decision": "REJECT", "evidence_sha256": None, "verification_method": "Checked transfer scope.", "notes": "Transfer remains unsupported."},
        ],
        "notes": "Human review retained all limitations.",
    }
    with pytest.raises(ValueError, match="supplied source hash"):
        service.record_reviewed_source_evidence(
            str(task["task_id"]), verification=review,
            capture_revision_sha256=capture.record_sha256,
        )

    store = LiteratureStore(tmp_path)
    work = next(
        item for item in store.records()
        if isinstance(item, SourceIdentityRevisionV1) and item.work_id == "work.stale-check"
    )
    store.append_work(
        {
            "work_id": work.work_id,
            "source_category": work.source_category,
            "title": work.title,
            "authors": list(work.authors),
            "strong_identifiers": dict(work.strong_identifiers),
            "locators": list(work.locators),
            "identity_status": work.identity_status,
            "change_reason": "Current head supersedes the capture's work revision.",
        },
        actor=ActorProvenanceV1(actor_class="HUMAN_OWNER_RESEARCHER", actor_id="source-review-fixture"),
        idempotency_key="work.stale-check.r2",
    )
    stale = service.source_review_readiness(str(task["task_id"]))
    assert "STALE_OR_MISSING_SOURCE_WORK" in next(
        item for item in stale["options"] if item["capture_id"] == capture.capture_id
    )["issues"]
