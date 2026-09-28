from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Barrier
from typing import Any, Mapping

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from alphaquest.studio.api import register_api_routes
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.factory_reviews import (
    EngineeringHandoffIntentHumanAcceptanceV1,
    HYPOTHESIS_REVIEW_FIELDS,
    HypothesisHumanAcceptanceV1,
    MECHANICS_REVIEW_FIELDS,
    ReviewedEngineeringHandoffIntentArtifactV1,
    ReviewedHypothesisArtifactV1,
    ReviewedSourceEvidenceArtifactV1,
    ReviewedSourceEvidenceArtifactV2,
    SOURCE_METADATA_FIELDS,
    SourceEvidenceHumanVerificationV1,
    build_reviewed_source_evidence,
)
from alphaquest.studio.factory_service import ResearchFactoryService
from alphaquest.studio.research_factory import CodexTaskType, object_sha256
from alphaquest.studio.research_factory import SourceEvidenceBundleV1
from tests.test_studio_factory_review_handoff import (
    FakeRunner,
    HASH_A,
    HASH_B,
    _draft,
    _hypothesis_proposal,
    _fulltext_capture,
    _mechanics_proposal,
    _source_proposal,
)


REVIEWED_AT = datetime(2026, 9, 28, 1, 2, 3, tzinfo=UTC)
_NO_DELIVERY = object()


@dataclass(frozen=True)
class ReviewCase:
    kind: str
    service: ResearchFactoryService
    task_id: str
    method_name: str
    argument_name: str
    review: Any
    artifact_model: type
    storage_kind: str
    capture_revision_sha256: str | None = None


def _source_review(
    *, content_sha256: str = HASH_A,
    review_id: str = "source_review_original",
    notes: str | None = None,
):
    return SourceEvidenceHumanVerificationV1(
        review_id=review_id,
        reviewer="Researcher One",
        reviewed_at=REVIEWED_AT,
        verified_metadata_fields=list(SOURCE_METADATA_FIELDS),
        content_sha256=content_sha256,
        retraction_status="NOT_RETRACTED",
        verification_method="Opened the captured source and checked its publisher metadata.",
        claim_reviews=[
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
        notes=notes or "Accepted the directly evidenced claim and retained the rejected inference.",
    )


def _hypothesis_review(
    *, review_id: str = "hypothesis_review_original", notes: str | None = None
):
    return HypothesisHumanAcceptanceV1(
        review_id=review_id,
        reviewer="Researcher One",
        reviewed_at=REVIEWED_AT,
        reviewed_fields=list(HYPOTHESIS_REVIEW_FIELDS),
        objective_alignment="PASS",
        source_claim_alignment="PASS",
        falsifiability="PASS",
        information_timeline_no_lookahead="PASS",
        execution_cost_awareness="PASS",
        notes=notes or "Reviewed every field against the accepted claim and objectives.",
    )


def _engineering_review(
    *, review_id: str = "engineering_review_original", notes: str | None = None
):
    return EngineeringHandoffIntentHumanAcceptanceV1(
        review_id=review_id,
        reviewer="Researcher One",
        reviewed_at=REVIEWED_AT,
        reviewed_fields=list(MECHANICS_REVIEW_FIELDS),
        hypothesis_alignment="PASS",
        unsupported_scope_confirmed="PASS",
        causal_timeline_reviewed="PASS",
        notes=notes or "Confirmed the unsupported intent should stop at an engineering handoff.",
    )


def _prepare_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> ReviewCase:
    monkeypatch.setattr("alphaquest.studio.factory_service._certified_catalog", lambda _root: [])
    _draft(tmp_path)
    service = ResearchFactoryService(tmp_path, runner=FakeRunner(_source_proposal()))
    capture = _fulltext_capture(tmp_path)
    source_task = service.enqueue_next(
        campaign_id="structured_factory", request_id=f"{kind}-source-task"
    )
    service.run_worker_once(worker_id=f"{kind}-source-worker")
    if kind == "source":
        return ReviewCase(
            kind,
            service,
            str(source_task["task_id"]),
            "record_reviewed_source_evidence",
            "verification",
            _source_review(content_sha256=capture.content_sha256),
            ReviewedSourceEvidenceArtifactV2,
            "source",
            capture.record_sha256,
        )

    service.record_reviewed_source_evidence(
        str(source_task["task_id"]),
        verification=_source_review(
            content_sha256=capture.content_sha256,
            review_id="source_prerequisite",
        ),
        capture_revision_sha256=capture.record_sha256,
    )
    hypothesis_plan = service._discover_plan("structured_factory")
    bindings = hypothesis_plan["artifacts"]["research_bindings"]
    service.runner = FakeRunner(_hypothesis_proposal(bindings))
    hypothesis_task = service.enqueue_next(
        campaign_id="structured_factory", request_id=f"{kind}-hypothesis-task"
    )
    service.run_worker_once(worker_id=f"{kind}-hypothesis-worker")
    if kind == "hypothesis":
        return ReviewCase(
            kind,
            service,
            str(hypothesis_task["task_id"]),
            "record_reviewed_hypothesis",
            "acceptance",
            _hypothesis_review(),
            ReviewedHypothesisArtifactV1,
            "hypothesis",
        )

    service.record_reviewed_hypothesis(
        str(hypothesis_task["task_id"]),
        acceptance=_hypothesis_review(review_id="hypothesis_prerequisite"),
    )
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
    binding = mechanics_plan["artifacts"]["hypothesis_binding"]
    service.runner = FakeRunner(_mechanics_proposal(binding))
    mechanics_task = service.enqueue_next(
        campaign_id="structured_factory", request_id="engineering-mechanics-task"
    )
    service.run_worker_once(worker_id="engineering-mechanics-worker")
    return ReviewCase(
        kind,
        service,
        str(mechanics_task["task_id"]),
        "record_reviewed_engineering_handoff_intent",
        "acceptance",
        _engineering_review(),
        ReviewedEngineeringHandoffIntentArtifactV1,
        "engineering-intent",
    )


def _delivery(case: ReviewCase, *, operation_id: str | None = None) -> dict[str, str]:
    validation = json.loads(
        (case.service.proposal_root / case.task_id / "validation.json").read_text(encoding="utf-8")
    )
    return {
        "operation_id": operation_id or f"{case.kind}_review_delivery_0001",
        "proposal_id": validation["proposal_id"],
        "payload_sha256": validation["payload_sha256"],
        "validation_sha256": validation["validation_sha256"],
    }


def _record(
    case: ReviewCase,
    *,
    service: ResearchFactoryService | None = None,
    review: Any | None = None,
    delivery: Mapping[str, Any] | object = _NO_DELIVERY,
) -> dict[str, Any]:
    target = service or case.service
    method = getattr(target, case.method_name)
    kwargs = {case.argument_name: review or case.review}
    if case.kind == "source":
        kwargs["capture_revision_sha256"] = case.capture_revision_sha256
    if delivery is not _NO_DELIVERY:
        kwargs["delivery"] = delivery
    return method(case.task_id, **kwargs)


def _replayed_review(case: ReviewCase) -> Any:
    return case.review.model_copy(
        update={
            "review_id": f"{case.kind}_review_generated_on_retry",
            "reviewed_at": REVIEWED_AT + timedelta(minutes=5),
        }
    )


def _fail_final_write_once(monkeypatch: pytest.MonkeyPatch):
    original = ResearchFactoryService._write_review_once
    calls = 0

    def fail_once(path: Path, payload: Mapping[str, Any]) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected final review write failure")
        original(path, payload)

    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(fail_once))
    return original


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_pending_delivery_rejects_a_competing_operation_after_final_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    delivery = _delivery(case)
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=delivery)
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))

    reopened = ResearchFactoryService(tmp_path)
    competing = {**delivery, "operation_id": f"{kind}_review_delivery_competing"}
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, service=reopened, review=_replayed_review(case), delivery=competing)


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_exact_replay_completes_pending_delivery_with_original_server_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    delivery = _delivery(case)
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=delivery)
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))

    artifact_path = (
        case.service.review_root / "structured_factory" / case.storage_kind / f"{case.task_id}.json"
    )
    assert not artifact_path.exists()
    reopened = ResearchFactoryService(tmp_path)
    artifact = _record(
        case, service=reopened, review=_replayed_review(case), delivery=delivery
    )
    validated = case.artifact_model.model_validate_json(json.dumps(artifact))
    review = getattr(validated, "human_verification", None) or validated.human_acceptance
    assert review.review_id == case.review.review_id
    assert review.reviewed_at == case.review.reviewed_at
    assert "delivery" not in artifact
    assert "operation_id" not in artifact
    assert artifact["campaign_mutations_performed"] is False
    assert artifact["mechanics_approval_granted"] is False
    assert artifact["testing_authorized"] is False
    assert json.loads(artifact_path.read_text(encoding="utf-8")) == artifact
    assert reopened.get_task(case.task_id)["review_delivery"]["status"] == "COMMITTED"


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_pending_delivery_rejects_changed_decision_binding_and_legacy_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    delivery = _delivery(case)
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=delivery)
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))
    reopened = ResearchFactoryService(tmp_path)

    changed_review = case.review.model_copy(update={"notes": "A different substantive decision."})
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, service=reopened, review=changed_review, delivery=delivery)
    for key in ("proposal_id", "payload_sha256", "validation_sha256"):
        changed_delivery = {**delivery, key: ("c" * 64 if key != "proposal_id" else "proposal_other")}
        with pytest.raises((RuntimeError, ValueError)):
            _record(case, service=reopened, delivery=changed_delivery)
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, service=reopened)

    artifact = _record(case, service=reopened, review=_replayed_review(case), delivery=delivery)
    assert case.artifact_model.model_validate_json(json.dumps(artifact))


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_delivery_rejects_wrong_proposal_identity_before_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    wrong = {**_delivery(case), "proposal_id": "proposal_from_another_task"}
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, delivery=wrong)
    assert not (case.service.review_root / "delivery" / f"{case.task_id}.json").exists()
    assert case.artifact_model.model_validate_json(
        json.dumps(_record(case, delivery=_delivery(case)))
    )


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_pending_delivery_revalidates_current_inputs_before_exact_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    delivery = _delivery(case)
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=delivery)
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))

    store = DraftStore(tmp_path)
    document = store.load("structured_factory")
    original_draft = dict(document["draft"])
    changed = dict(original_draft)
    changed["title"] = "A stale title introduced after delivery admission"
    store.save("structured_factory", changed, wizard_step=4 if kind == "engineering" else 1)
    reopened = ResearchFactoryService(tmp_path)
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, service=reopened, review=_replayed_review(case), delivery=delivery)
    assert reopened.get_task(case.task_id)["review_delivery"]["status"] == "ADMITTED"

    store.save("structured_factory", original_draft, wizard_step=4 if kind == "engineering" else 1)
    artifact = _record(case, service=reopened, review=_replayed_review(case), delivery=delivery)
    validated = case.artifact_model.model_validate_json(json.dumps(artifact))
    review = getattr(validated, "human_verification", None) or validated.human_acceptance
    assert review.review_id == case.review.review_id


def _api_payload(case: ReviewCase) -> dict[str, Any]:
    review = case.review.model_dump(mode="json")
    for server_owned in ("review_id", "reviewed_at", "decision", "source_identity_status"):
        review.pop(server_owned, None)
    if case.kind == "source":
        review.pop("content_sha256", None)
        review.pop("capture_binding", None)
        review["capture_revision_sha256"] = case.capture_revision_sha256
    return {**review, "delivery": _delivery(case)}


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_reviewed_api_requires_delivery_and_lost_response_replays_original_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    suffix = {
        "source": "reviewed-source-evidence",
        "hypothesis": "reviewed-hypothesis",
        "engineering": "reviewed-engineering-intent",
    }[kind]
    url = f"/api/factory/tasks/{case.task_id}/{suffix}"
    payload = _api_payload(case)
    app = FastAPI()
    register_api_routes(app, tmp_path)
    client = TestClient(app)

    missing = dict(payload)
    missing.pop("delivery")
    assert client.post(url, json=missing).status_code == 422
    first = client.post(url, json=payload)
    assert first.status_code == 200, first.text
    artifact_path = (
        case.service.review_root / "structured_factory" / case.storage_kind / f"{case.task_id}.json"
    )
    original_bytes = artifact_path.read_bytes()
    replay = client.post(url, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert artifact_path.read_bytes() == original_bytes
    artifact = replay.json()["reviewed_artifact"]
    assert case.artifact_model.model_validate_json(json.dumps(artifact))
    assert "delivery" not in artifact
    assert "operation_id" not in artifact


def test_concurrent_exact_deliveries_converge_on_one_server_generated_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, "source")
    delivery = _delivery(case)
    barrier = Barrier(2)

    def submit(index: int) -> dict[str, Any]:
        service = ResearchFactoryService(tmp_path)
        review = case.review.model_copy(
            update={
                "review_id": f"concurrent_source_review_{index}",
                "reviewed_at": REVIEWED_AT + timedelta(seconds=index),
            }
        )
        barrier.wait(timeout=5)
        return _record(case, service=service, review=review, delivery=delivery)

    with ThreadPoolExecutor(max_workers=2) as executor:
        artifacts = list(executor.map(submit, (1, 2)))
    assert artifacts[0] == artifacts[1]
    assert artifacts[0]["human_verification"]["review_id"] in {
        "concurrent_source_review_1",
        "concurrent_source_review_2",
    }
    reopened = ResearchFactoryService(tmp_path)
    assert reopened.get_task(case.task_id)["review_delivery"]["status"] == "COMMITTED"
    assert len(reopened._reviewed_source_artifacts("structured_factory")) == 1


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_concurrent_conflicting_operations_admit_exactly_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    barrier = Barrier(2)

    def submit(index: int):
        service = ResearchFactoryService(tmp_path)
        delivery = _delivery(case, operation_id=f"{kind}_competing_operation_{index}")
        review = case.review.model_copy(
            update={
                "review_id": f"{kind}_concurrent_review_{index}",
                "reviewed_at": REVIEWED_AT + timedelta(seconds=index),
            }
        )
        barrier.wait(timeout=5)
        try:
            return "accepted", delivery, _record(
                case, service=service, review=review, delivery=delivery
            )
        except (RuntimeError, ValueError) as exc:
            return "rejected", delivery, str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(submit, (1, 2)))
    accepted = [item for item in outcomes if item[0] == "accepted"]
    rejected = [item for item in outcomes if item[0] == "rejected"]
    assert len(accepted) == 1
    assert len(rejected) == 1
    detail = ResearchFactoryService(tmp_path).get_task(case.task_id)
    assert detail["review_delivery"]["status"] == "COMMITTED"
    assert detail["review_delivery"]["operation_id"] == accepted[0][1]["operation_id"]
    assert case.artifact_model.model_validate_json(json.dumps(accepted[0][2]))


def test_pending_source_delivery_rejects_a_changed_nested_claim_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, "source")
    delivery = _delivery(case)
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=delivery)
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))

    changed_claims = [
        case.review.claim_reviews[0].model_copy(
            update={"notes": "Changed nested human evidence interpretation."}
        ),
        *case.review.claim_reviews[1:],
    ]
    changed = case.review.model_copy(update={"claim_reviews": changed_claims})
    reopened = ResearchFactoryService(tmp_path)
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, service=reopened, review=changed, delivery=delivery)
    artifact = _record(case, service=reopened, review=_replayed_review(case), delivery=delivery)
    assert artifact["human_verification"]["claim_reviews"][0]["notes"] == (
        case.review.claim_reviews[0].notes
    )


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
def test_admitted_delivery_is_visible_but_grants_no_review_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=_delivery(case))
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))

    reopened = ResearchFactoryService(tmp_path)
    detail = reopened.get_task(case.task_id)
    assert detail["review_delivery"]["status"] == "ADMITTED"
    assert detail["structured_review"] is None
    artifact_path = (
        reopened.review_root / "structured_factory" / case.storage_kind / f"{case.task_id}.json"
    )
    assert not artifact_path.exists()
    readers = {
        "source": reopened._reviewed_source_artifacts,
        "hypothesis": reopened._reviewed_hypothesis_artifacts,
        "engineering": reopened._reviewed_engineering_intent_artifacts,
    }
    assert all(item.task_id != case.task_id for item in readers[kind]("structured_factory"))


def test_tampered_delivery_sidecar_reports_integrity_error_without_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, "source")
    original = _fail_final_write_once(monkeypatch)
    with pytest.raises(RuntimeError, match="injected final review write failure"):
        _record(case, delivery=_delivery(case))
    monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))

    intent_path = case.service.review_root / "delivery" / f"{case.task_id}.json"
    tampered = json.loads(intent_path.read_text(encoding="utf-8"))
    tampered["delivery"]["operation_id"] = "tampered_operation"
    intent_path.write_text(json.dumps(tampered), encoding="utf-8")
    detail = ResearchFactoryService(tmp_path).get_task(case.task_id)
    assert detail["review_delivery"] == {"status": "INTEGRITY_ERROR"}
    assert detail["structured_review"] is None


def test_valid_but_different_stored_artifact_reports_integrity_error_and_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, "source")
    delivery = _delivery(case)
    artifact = _record(case, delivery=delivery)
    artifact_path = (
        case.service.review_root / "structured_factory" / "source" / f"{case.task_id}.json"
    )
    different = json.loads(json.dumps(artifact))
    different["human_verification"]["notes"] = "A different but internally valid stored review."
    unsigned = {key: value for key, value in different.items() if key != "artifact_sha256"}
    different["artifact_sha256"] = object_sha256(unsigned)
    assert ReviewedSourceEvidenceArtifactV2.model_validate_json(json.dumps(different))
    artifact_path.write_text(json.dumps(different), encoding="utf-8")
    changed_bytes = artifact_path.read_bytes()

    reopened = ResearchFactoryService(tmp_path)
    detail = reopened.get_task(case.task_id)
    assert detail["review_delivery"] == {"status": "INTEGRITY_ERROR"}
    assert detail["structured_review"]["status"] == "ACCEPTED_FOR_HYPOTHESIS"
    with pytest.raises((RuntimeError, ValueError)):
        _record(case, service=reopened, review=_replayed_review(case), delivery=delivery)
    assert artifact_path.read_bytes() == changed_bytes


def test_reviewed_api_rejects_flat_or_extended_delivery_bodies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, "source")
    url = f"/api/factory/tasks/{case.task_id}/reviewed-source-evidence"
    payload = _api_payload(case)
    app = FastAPI()
    register_api_routes(app, tmp_path)
    client = TestClient(app)

    flat = dict(payload)
    delivery = flat.pop("delivery")
    flat.update(delivery)
    assert client.post(url, json=flat).status_code == 422
    extended = json.loads(json.dumps(payload))
    extended["delivery"]["unexpected"] = "not admitted"
    assert client.post(url, json=extended).status_code == 422


def test_legacy_v1_source_artifact_remains_byte_identical_and_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, "source")
    record, campaign_id, validation, imported = case.service._reviewable_proposal(
        case.task_id, expected_task_type=CodexTaskType.SOURCE_RESEARCH,
    )
    source = SourceEvidenceBundleV1.model_validate_json(
        json.dumps(imported.validated_payload, sort_keys=True)
    )
    artifact = build_reviewed_source_evidence(
        campaign_id=campaign_id,
        task_id=record.task_id,
        proposal_id=imported.proposal_id,
        proposal_payload_sha256=imported.payload_sha256,
        proposal_validation_sha256=validation["validation_sha256"],
        source_evidence=source,
        human_verification=case.review,
    )
    path = case.service._review_artifact_path(campaign_id, "source", case.task_id)
    case.service._write_review_once(path, artifact.model_dump(mode="json", by_alias=True))
    before = path.read_bytes()
    detail = ResearchFactoryService(tmp_path).get_task(case.task_id)
    assert detail["structured_review"]["artifact"]["schema"] == "alphaquest.reviewed-source-evidence/v1"
    assert path.read_bytes() == before
    assert ResearchFactoryService(tmp_path).get_task(case.task_id)["review_delivery"] is None


@pytest.mark.parametrize("kind", ["source", "hypothesis", "engineering"])
@pytest.mark.parametrize("state", ["admitted", "committed", "historical"])
@pytest.mark.parametrize("disposition", ["DISMISS", "ACKNOWLEDGE"])
def test_disposition_cannot_supersede_admitted_or_recorded_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, state: str, disposition: str
) -> None:
    case = _prepare_case(tmp_path, monkeypatch, kind)
    delivery = _delivery(case)
    if state == "admitted":
        original = _fail_final_write_once(monkeypatch)
        with pytest.raises(RuntimeError, match="injected final review write failure"):
            _record(case, delivery=delivery)
        monkeypatch.setattr(ResearchFactoryService, "_write_review_once", staticmethod(original))
    elif state == "committed":
        _record(case, delivery=delivery)
    else:
        _record(case)
    reopened = ResearchFactoryService(tmp_path)
    with pytest.raises(RuntimeError, match="review"):
        reopened.record_proposal_disposition(
            case.task_id, disposition=disposition, reviewer="Competing reviewer", notes="Close this task."
        )
    app = FastAPI()
    register_api_routes(app, tmp_path)
    response = TestClient(app).post(
        f"/api/factory/tasks/{case.task_id}/proposal-disposition",
        json={"disposition": disposition, "reviewer": "Competing reviewer", "notes": "Close this task."},
    )
    assert response.status_code == 409
    assert reopened.get_task(case.task_id)["proposal_disposition"] is None
    if state != "historical":
        result = _record(case, service=reopened, review=_replayed_review(case), delivery=delivery)
        saved = result.get("human_verification", result.get("human_acceptance"))
        assert saved["review_id"] == case.review.review_id
    assert reopened.get_task(case.task_id)["structured_review"] is not None
