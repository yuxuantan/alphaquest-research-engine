from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphaquest.studio import workflow as workflow_module
from alphaquest.studio.api import register_api_routes
from alphaquest.studio.workflow import StudioWorkflowService, _step_gates


def _certification() -> SimpleNamespace:
    return SimpleNamespace(
        strategy_id="certified_test_strategy",
        implementation_version="1",
        implementation_sha256="a" * 64,
        studio={"visible": True},
    )


def test_certified_event_replay_satisfies_mechanics_gate_without_ui_only_state() -> None:
    gates = _step_gates(
        {
            "authoring_lane": "certified_event_replay",
            "event_strategy": "certified_test_strategy",
        },
        {},
    )

    assert gates[4] is True


def test_event_strategy_api_marks_mechanics_step_complete(tmp_path, monkeypatch) -> None:
    service = StudioWorkflowService(tmp_path)
    service.create_draft(
        campaign_id="event_gate_regression",
        title="Certified event gate regression",
        instrument="ES",
    )
    document = service.store.load("event_gate_regression")
    draft = dict(document["draft"])
    draft["dataset"] = {"event_source": {"schema": "alphaquest.event-source/v1"}}
    service.store.save("event_gate_regression", draft, wizard_step=5)
    monkeypatch.setattr(
        workflow_module,
        "get_strategy_certification",
        lambda strategy_id, project_root, require_current: _certification(),
    )
    app = FastAPI()
    register_api_routes(app, tmp_path)

    response = TestClient(app).put(
        "/api/drafts/event_gate_regression/mechanics/event-strategy",
        json={"strategy_id": "certified_test_strategy", "confirmed": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["draft"]["authoring_lane"] == "certified_event_replay"
    assert payload["draft"]["event_strategy"] == "certified_test_strategy"
    assert payload["steps"][4]["complete"] is True
