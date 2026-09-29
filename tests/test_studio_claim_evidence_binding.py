"""New claim bindings and historical delivery compatibility, without model calls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from alphaquest.studio.factory_reviews import (
    SourceEvidenceHumanVerificationV2, build_reviewed_source_evidence_v2,
)
from alphaquest.studio.factory_service import ResearchFactoryService
from alphaquest.studio.research_factory import SourceEvidenceBundleV1
from tests.test_studio_factory_review_handoff import (
    FakeRunner, _draft, _fulltext_capture, _source_proposal, _source_review_payload,
)


def prepared(root: Path, evidence: str = "extraction"):
    _draft(root)
    capture = _fulltext_capture(root, retained_bytes=b"Retained document bytes", extracted_representation_bytes=b"Extracted source text")
    source = _source_proposal()
    source["claims"][0]["evidence_sha256"] = {
        "extraction": capture.extracted_representation_sha256,
        "document": capture.content_sha256,
        "missing": None,
        "unrelated": "f" * 64,
    }[evidence]
    service = ResearchFactoryService(root, runner=FakeRunner(source))
    task = service.enqueue_next(campaign_id="structured_factory", request_id="claim-binding")
    service.run_worker_once(worker_id="fixture-only")
    return service, capture, task["task_id"], source


@pytest.mark.parametrize("evidence", ["extraction", "document", "missing"])
def test_accepted_hash_is_derived_from_exact_retained_artifact(tmp_path, evidence):
    service, capture, task_id, _ = prepared(tmp_path, evidence)
    ready = service.source_review_readiness(task_id)["options"][0]
    bound = ready["claim_evidence"][0]
    expected = capture.content_sha256 if evidence == "document" else capture.extracted_representation_sha256
    assert bound["status"] == "BOUND"
    assert bound["evidence_sha256"] == expected
    assert bound["basis"] == ("SELECTED_EXTRACTION_FALLBACK" if evidence == "missing" else "PROPOSAL_MATCH")
    review = _source_review_payload(capture)
    review["claim_reviews"][0].pop("evidence_sha256")
    result = service.record_reviewed_source_evidence(
        task_id, verification=review, capture_revision_sha256=capture.record_sha256,
    )
    assert result["human_verification"]["claim_reviews"][0]["evidence_sha256"] == expected
    assert result["human_verification"]["claim_reviews"][1]["evidence_sha256"] is None
    assert result["campaign_mutations_performed"] is False


@pytest.mark.parametrize("supplied", ["f" * 64, "document"])
def test_new_write_rejects_wrong_claim_hash_before_delivery(tmp_path, supplied):
    service, capture, task_id, _ = prepared(tmp_path)
    review = _source_review_payload(capture)
    review["claim_reviews"][0]["evidence_sha256"] = capture.content_sha256 if supplied == "document" else supplied
    with pytest.raises(ValueError, match="claim evidence hash does not match"):
        service.record_reviewed_source_evidence(task_id, verification=review, capture_revision_sha256=capture.record_sha256)
    assert not service._review_delivery_path(task_id).exists()
    assert service.get_task(task_id)["structured_review"] is None


def test_unrelated_proposed_evidence_can_be_rejected_but_not_accepted(tmp_path):
    service, capture, task_id, _ = prepared(tmp_path, "unrelated")
    ready = service.source_review_readiness(task_id)
    assert ready["status"] == "READY"
    assert ready["options"][0]["claim_evidence"][0]["status"] == "UNBOUND"
    review = _source_review_payload(capture)
    with pytest.raises(ValueError, match="not bound to the selected capture"):
        service.record_reviewed_source_evidence(task_id, verification=review, capture_revision_sha256=capture.record_sha256)
    review["claim_reviews"][0]["decision"] = "REJECT"
    review["claim_reviews"][1]["decision"] = "ACCEPT"
    # Human acceptance of the inference is explicit; its null proposal hash
    # binds the selected extraction. The unrelated claim remains rejected.
    result = service.record_reviewed_source_evidence(task_id, verification=review, capture_revision_sha256=capture.record_sha256)
    assert result["human_verification"]["claim_reviews"][0]["evidence_sha256"] is None
    assert result["human_verification"]["claim_reviews"][1]["evidence_sha256"] == capture.extracted_representation_sha256


def test_omitted_automatically_bound_hash_can_be_replayed_exactly(tmp_path):
    service, capture, task_id, _ = prepared(tmp_path)
    validation = service.get_task(task_id)["proposal_validation"]
    delivery = {"operation_id": "auto-hash", "proposal_id": validation["proposal_id"],
                "payload_sha256": validation["payload_sha256"], "validation_sha256": validation["validation_sha256"]}
    review = _source_review_payload(capture)
    review["claim_reviews"][0].pop("evidence_sha256")
    first = service.record_reviewed_source_evidence(task_id, verification=review, capture_revision_sha256=capture.record_sha256, delivery=delivery)
    assert service.record_reviewed_source_evidence(task_id, verification=review, capture_revision_sha256=capture.record_sha256, delivery=delivery) == first


@pytest.mark.parametrize("admitted_only", [False, True])
def test_pre_upgrade_v2_exact_replay_preserves_original_hash_and_decision(tmp_path, admitted_only):
    service, capture, task_id, source = prepared(tmp_path, "missing")
    validation = service.get_task(task_id)["proposal_validation"]
    review = _source_review_payload(capture)
    review["claim_reviews"][0]["evidence_sha256"] = "b" * 64
    review["capture_binding"] = service.source_review_readiness(task_id)["options"][0]["binding"]
    artifact = build_reviewed_source_evidence_v2(
        campaign_id="structured_factory", task_id=task_id,
        proposal_id=validation["proposal_id"], proposal_payload_sha256=validation["payload_sha256"],
        proposal_validation_sha256=validation["validation_sha256"],
        source_evidence=SourceEvidenceBundleV1.model_validate_json(json.dumps(source)),
        human_verification=SourceEvidenceHumanVerificationV2.model_validate(review),
    )
    delivery = {"operation_id": "historical-v2", "proposal_id": validation["proposal_id"],
                "payload_sha256": validation["payload_sha256"], "validation_sha256": validation["validation_sha256"]}
    path = service._review_artifact_path("structured_factory", "source", task_id)
    with service._controller_lock():
        original = service._commit_review_artifact(path, artifact, delivery)
    if admitted_only:
        path.unlink()  # Simulate interrupted historical delivery in the fixture only.
    replay = service.record_reviewed_source_evidence(
        task_id, verification=review, capture_revision_sha256=capture.record_sha256, delivery=delivery,
    )
    assert replay == original
    assert replay["human_verification"]["claim_reviews"][0]["evidence_sha256"] == "b" * 64
    changed = deepcopy(review)
    changed["claim_reviews"][0]["notes"] = "Changed human decision rationale"
    with pytest.raises(RuntimeError, match="different review decision"):
        service.record_reviewed_source_evidence(
            task_id, verification=changed, capture_revision_sha256=capture.record_sha256, delivery=delivery,
        )
    assert service.get_task(task_id)["structured_review"] is not None
