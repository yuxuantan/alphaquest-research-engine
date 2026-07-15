import json

import pytest

from alphaquest.research.artifact_store import ArtifactStore


def test_artifact_store_writes_structured_campaign_json(tmp_path):
    store = ArtifactStore(tmp_path / "research_artifacts")

    path = store.write_json("campaigns", "audit.json", {"status": "PASS"}, campaign_id="es_demo")

    assert path == tmp_path / "research_artifacts" / "campaigns" / "es_demo" / "audit.json"
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "PASS"


def test_artifact_store_rejects_unclassified_or_unsafe_paths(tmp_path):
    store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError):
        store.write_text("misc", "audit.md", "x")
    with pytest.raises(ValueError):
        store.write_text("cleanup", "../audit.md", "x")
