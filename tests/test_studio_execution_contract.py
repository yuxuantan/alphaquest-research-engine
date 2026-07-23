from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from alphaquest.authoring.models import ExecutionSettingsV1
from alphaquest.studio.web import create_app


def _execution(
    *,
    session_end: str = "16:00:00",
    tick_value: float = 12.5,
) -> dict[str, object]:
    return {
        "session_start": "09:30:00",
        "session_end": session_end,
        "latest_entry_time": "15:45:00",
        "flatten_time": "15:55:00",
        "latest_flat_time": "15:56:00",
        "overnight_allowed": False,
        "initial_balance": 150_000.0,
        "tick_size": 0.25,
        "point_value": 50.0,
        "tick_value": tick_value,
        "commission_per_contract": 2.5,
        "slippage_ticks": 1.0,
        "contracts": 1,
        "prop_profile": "configured_local_profile",
    }


def test_execution_settings_require_entry_and_flattening_inside_declared_session() -> None:
    with pytest.raises(ValidationError, match="session/entry/flatten times are not in causal order"):
        ExecutionSettingsV1.model_validate(_execution(session_end="10:00:00"))


def test_execution_api_rejects_entry_after_declared_session_close(tmp_path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index.html").write_text("<!doctype html><title>Studio</title>", encoding="utf-8")
    client = TestClient(create_app(project_root=tmp_path, assets_dir=assets))

    response = client.put(
        "/api/drafts/missing_draft/execution",
        json={"roll_policy_confirmed": True, "execution": _execution(session_end="10:00:00")},
    )

    assert response.status_code == 422
    assert "session/entry/flatten times are not in causal order" in response.text


def test_execution_settings_require_consistent_futures_tick_value() -> None:
    with pytest.raises(ValidationError, match="tick_value must equal tick_size multiplied by point_value"):
        ExecutionSettingsV1.model_validate(_execution(tick_value=1.0))


def test_execution_api_rejects_internally_inconsistent_tick_value(tmp_path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index.html").write_text("<!doctype html><title>Studio</title>", encoding="utf-8")
    client = TestClient(create_app(project_root=tmp_path, assets_dir=assets))

    response = client.put(
        "/api/drafts/missing_draft/execution",
        json={"roll_policy_confirmed": True, "execution": _execution(tick_value=1.0)},
    )

    assert response.status_code == 422
    assert "tick_value must equal tick_size multiplied by point_value" in response.text
