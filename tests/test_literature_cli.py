from __future__ import annotations

import json
from pathlib import Path

from alphaquest.cli import main
from tests.test_literature_stage1 import _project


def test_literature_cli_creates_inspects_and_validates_offline_records(tmp_path: Path, capsys) -> None:
    root = _project(tmp_path)
    source = root / "offline.txt"
    source.write_bytes(b"offline fixture")
    assert main(["literature", "put-artifact", "--project-root", str(root), "--input", str(source), "--kind", "artifacts"]) == 0
    artifact = json.loads(capsys.readouterr().out)
    assert len(artifact["sha256"]) == 64

    payload = root / "work.json"
    payload.write_text(
        json.dumps(
            {
                "work_id": "work.cli",
                "source_category": "EXCHANGE",
                "title": "Offline CLI fixture",
                "authors": ["Fixture Author"],
                "strong_identifiers": {},
                "locators": ["https://example.test/cli"],
                "identity_status": "PROVISIONAL",
                "change_reason": "CLI proof",
            }
        )
    )
    command = [
        "literature", "append", "work", "--project-root", str(root), "--input", str(payload),
        "--actor-id", "cli-engine", "--idempotency-key", "work.cli.r1",
    ]
    assert main(command) == 0
    work = json.loads(capsys.readouterr().out)
    assert work["record_id"] == "work.cli.r000001"

    assert main(["literature", "list", "--project-root", str(root), "--family", "source-works"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["record_id"] == work["record_id"]
    assert main(["literature", "show", work["record_id"], "--project-root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["record_sha256"] == work["record_sha256"]
    assert main(["literature", "validate", "--project-root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_openalex_cli_is_narrow_and_uses_frozen_protocol(monkeypatch, capsys):
    from alphaquest.research.literature import stage2_runner
    calls = []

    def run(root, sha):
        calls.append((root, sha))
        return {"complete": True, "searches": []}

    monkeypatch.setattr(stage2_runner, "run_openalex_pilot", run)
    assert main(["literature", "openalex-run", "--protocol-revision-sha", "a" * 64]) == 0
    assert calls == [(".", "a" * 64)]
    assert json.loads(capsys.readouterr().out)["complete"]
    import pytest
    for option in ["--url", "--host", "--provider-endpoint", "--arbitrary-query", "--file", "--shell"]:
        with pytest.raises(SystemExit):
            main(["literature", "openalex-run", "--protocol-revision-sha", "a" * 64, option, "forbidden"])
    assert len(calls) == 1
