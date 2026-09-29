from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphaquest.research.literature.contracts import ActorProvenanceV1, SourceIdentityRevisionV1
from alphaquest.research.literature.store import LiteratureStore
from alphaquest.studio.api import FactoryRunNextRequest
from alphaquest.studio.factory_service import ResearchFactoryService
from alphaquest.studio.research_factory import SelectedSourceV1
from tests.test_studio_factory_service import FakeRunner, _draft
from tests.test_studio_factory_review_handoff import _fulltext_capture, _source_proposal


def _selection(root: Path, *, permission: str = "ALLOWED_EXTERNAL_PROCESSOR", **capture_kwargs) -> dict:
    capture = _fulltext_capture(root, **capture_kwargs)
    fields = {
        "capture_id", "source_version_id", "source_version_revision_sha256",
        "retrieval_locator", "status", "captured_at", "access_basis",
        "local_retention_permission", "redistribution_permission", "external_model_processing_permission",
        "media_type", "content_sha256", "content_bytes", "extracted_representation_sha256",
        "extracted_bytes", "extractor_id", "extractor_version", "extractor_config_sha256", "failure_reason",
    }
    payload = {k: v for k, v in capture.model_dump().items() if k in fields}
    payload.update(capture_id="capture.selected", external_model_processing_permission=permission)
    capture = LiteratureStore(root).append_capture(
        payload, actor=ActorProvenanceV1(actor_class="HUMAN_OWNER_RESEARCHER", actor_id="test-owner"),
        idempotency_key="capture.selected",
    )
    return {
        "capture_id": capture.capture_id, "capture_revision_sha256": capture.record_sha256,
        "proposed_year": 2025, "locator": capture.retrieval_locator,
    }


def test_selected_source_uses_existing_factory_flow_with_no_approval(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    original = draft.read_bytes()
    selection = _selection(tmp_path)
    runner = FakeRunner(_source_proposal())
    service = ResearchFactoryService(tmp_path, runner=runner)
    queued = service.enqueue_next(campaign_id="factory_example", request_id="selected-source-001", selected_source=selection)
    assert queued["request"]["web_search"] is False
    assert service.enqueue_next(campaign_id="factory_example", request_id="selected-source-001", selected_source=selection)["task_id"] == queued["task_id"]
    context = json.loads((service.context_root / queued["task_id"] / "context_packet.json").read_text())
    assert any(g["granularity"] == "SOURCE_TEXT" for g in context["allowed_information"])
    assert "selected_source" in context["artifact_hashes"]
    completed = service.run_worker_once(worker_id="selected-source-test")
    assert completed["proposal_validation"]["status"] == "VALIDATED_NOT_APPLIED"
    assert runner.run_calls == 1
    assert completed["approved"] is False and completed["applied"] is False
    assert completed["structured_review"] is None
    assert draft.read_bytes() == original


@pytest.mark.parametrize("permission", ["UNKNOWN", "LOCAL_ONLY", "PROHIBITED"])
def test_permission_denial_precedes_context_and_runner(tmp_path: Path, permission: str) -> None:
    _draft(tmp_path)
    selection = _selection(tmp_path, permission=permission)
    runner = FakeRunner(_source_proposal())
    service = ResearchFactoryService(tmp_path, runner=runner)
    with pytest.raises(ValueError, match="ALLOWED_EXTERNAL_PROCESSOR"):
        service.enqueue_next(campaign_id="factory_example", request_id="selected-denied-001", selected_source=selection)
    assert runner.run_calls == 0
    assert not service.queue.list_tasks()
    assert not service.context_root.exists() or not list(service.context_root.iterdir())


@pytest.mark.parametrize("field,value", [("year", 2013), ("publication_type", "PEER_REVIEWED"), ("locator", "https://example.invalid/journal"), ("title", "Another paper"), ("authors", ["Another author"])])
def test_worker_cannot_substitute_selected_paper(tmp_path: Path, field: str, value: object) -> None:
    _draft(tmp_path)
    selection = _selection(tmp_path)
    proposal = _source_proposal()
    proposal[field] = value
    runner = FakeRunner(proposal)
    service = ResearchFactoryService(tmp_path, runner=runner)
    service.enqueue_next(campaign_id="factory_example", request_id="selected-wrong-output", selected_source=selection)
    completed = service.run_worker_once(worker_id="selected-wrong-test")
    assert completed["proposal_validation"]["status"] == "REJECTED_NOT_APPLIED"
    assert completed["approved"] is False and completed["applied"] is False


def test_changed_canonical_head_blocks_before_invocation(tmp_path: Path) -> None:
    _draft(tmp_path)
    selection = _selection(tmp_path)
    runner = FakeRunner(_source_proposal())
    service = ResearchFactoryService(tmp_path, runner=runner)
    service.enqueue_next(campaign_id="factory_example", request_id="selected-drift-001", selected_source=selection)
    store = LiteratureStore(tmp_path)
    work = store.latest(SourceIdentityRevisionV1, "work.source")
    store.append_work(
        {"work_id": "work.source", "title": "Corrected title", "change_reason": "Test currentness",
         "locators": work.locators, "strong_identifiers": work.strong_identifiers,
         "source_category": work.source_category, "authors": work.authors, "identity_status": work.identity_status},
        actor=ActorProvenanceV1(actor_class="HUMAN_OWNER_RESEARCHER", actor_id="test-owner"),
        idempotency_key="work.changed",
    )
    completed = service.run_worker_once(worker_id="selected-stale-test")
    assert runner.run_calls == 0
    assert completed["proposal_validation"]["status"] == "REJECTED_NOT_APPLIED"


def test_request_id_cannot_switch_source_selection(tmp_path: Path) -> None:
    _draft(tmp_path)
    selection = _selection(tmp_path)
    service = ResearchFactoryService(tmp_path, runner=FakeRunner())
    service.enqueue_next(campaign_id="factory_example", request_id="selected-idempotency", selected_source=selection)
    for other in (None, {**selection, "proposed_year": 2012}):
        with pytest.raises(ValueError, match="request_id"):
            service.enqueue_next(campaign_id="factory_example", request_id="selected-idempotency", selected_source=other)


def test_selected_source_has_no_arbitrary_path_or_prompt_fields() -> None:
    valid = {"capture_id": "capture.selected", "capture_revision_sha256": "a" * 64,
             "proposed_year": 2012, "locator": "https://example.invalid/paper"}
    assert FactoryRunNextRequest(campaign_id="example", request_id="selected-api-test", selected_source=valid).selected_source.proposed_year == 2012
    for extra in ("prompt", "path", "web_search", "external_model_processing_permission"):
        with pytest.raises(ValueError):
            SelectedSourceV1.model_validate({**valid, extra: "not allowed"})
    with pytest.raises(ValueError):
        SelectedSourceV1.model_validate({**valid, "proposed_year": True})


@pytest.mark.parametrize("capture_kwargs", [
    {"retained_bytes": b""}, {"extracted_representation_bytes": b""},
    {"extracted_representation_bytes": b"   "}, {"extracted_representation_bytes": b"\xff"},
    {"extracted_representation_bytes": b"x" * 250_001},
])
def test_invalid_document_input_never_reaches_worker(tmp_path: Path, capture_kwargs: dict) -> None:
    _draft(tmp_path)
    selection = _selection(tmp_path, **capture_kwargs)
    runner = FakeRunner(_source_proposal())
    service = ResearchFactoryService(tmp_path, runner=runner)
    with pytest.raises(ValueError):
        service.enqueue_next(campaign_id="factory_example", request_id="selected-invalid-bytes", selected_source=selection)
    assert runner.run_calls == 0
    assert not service.queue.list_tasks()


def test_cli_and_api_forward_only_structured_selection(tmp_path: Path, monkeypatch, capsys) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from alphaquest.cli import main
    from alphaquest.studio.api import register_api_routes
    selection = {"capture_id": "capture.selected", "capture_revision_sha256": "a" * 64,
                 "proposed_year": 2012, "locator": "https://example.invalid/paper"}
    received = []
    def enqueue(self, **kwargs):
        received.append(kwargs)
        return {"task_id": "test-only-task"}
    monkeypatch.setattr(ResearchFactoryService, "enqueue_next", enqueue)
    request_path = tmp_path / "selection.json"
    request_path.write_text(json.dumps(selection))
    assert main(["factory", "run-next", "--project-root", str(tmp_path), "--campaign-id", "example",
                 "--request-id", "selected-cli-test", "--selected-source", str(request_path), "--json"]) == 0
    assert received[-1]["selected_source"] == selection
    assert json.loads(capsys.readouterr().out)["queued_only"] is True
    app = FastAPI()
    register_api_routes(app, tmp_path)
    response = TestClient(app).post("/api/factory/run-next", json={"campaign_id": "example", "request_id": "selected-api-test", "selected_source": selection})
    assert response.status_code == 202
    assert received[-1]["selected_source"].model_dump() == selection
