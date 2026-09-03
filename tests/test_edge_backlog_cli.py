from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphaquest.cli import main


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _observation() -> dict:
    return {
        "observation_id": "obs.cli",
        "statement": "Completed auction pressure persisted beyond the observed opening interval.",
        "evidence_refs": [
            {
                "source_id": "source.cli",
                "source_kind": "EXCHANGE_RESEARCH",
                "locator": "https://example.test/exchange-note",
                "claim_locator": "section-2",
                "evidence_time": "2026-09-01T09:30:00-04:00",
                "integrity": "LOCATOR_ONLY",
                "content_sha256": None,
            }
        ],
        "known_conflicts": [],
    }


def _entry(observation_sha256: str) -> dict:
    return {
        "entry_id": "edge.cli",
        "title": "Auction pressure continuation",
        "instruments": ["ES"],
        "market_behavior": "Opening auction pressure persists after the observed interval",
        "causal_mechanism": "Delayed inventory hedging",
        "counterparty_transfer_rationale": "Late hedgers transfer returns to patient liquidity providers",
        "information_inputs": ["completed auction pressure"],
        "information_availability": "Available only after the observed opening interval completes",
        "expected_effect": "Short-horizon continuation",
        "holding_horizon": "Intraday minutes",
        "market_context": "Regular trading hours",
        "observation_refs": [
            {
                "observation_id": "obs.cli",
                "observation_revision_sha256": observation_sha256,
                "role": "MOTIVATING",
            }
        ],
        "open_questions": [],
    }


def test_cli_end_to_end_capture_search_review_and_validate(tmp_path: Path, capsys) -> None:
    observation_input = _write(tmp_path / "observation.json", _observation())
    assert (
        main(
            [
                "edge-backlog",
                "capture-observation",
                "--project-root",
                str(tmp_path),
                "--input",
                str(observation_input),
                "--actor-id",
                "codex-cli",
                "--task-id",
                "task.cli.capture",
            ]
        )
        == 0
    )
    observation = json.loads(capsys.readouterr().out)
    assert observation["actor"]["actor_class"] == "CODEX"

    entry_input = _write(tmp_path / "entry.json", _entry(observation["record_sha256"]))
    assert (
        main(
            [
                "edge-backlog",
                "create",
                "--project-root",
                str(tmp_path),
                "--input",
                str(entry_input),
                "--actor-id",
                "codex-cli",
            ]
        )
        == 0
    )
    entry = json.loads(capsys.readouterr().out)
    assert entry["actor"]["actor_class"] == "CODEX"

    assert (
        main(
            [
                "edge-backlog",
                "search",
                "--project-root",
                str(tmp_path),
                "--query",
                "inventory hedging",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)[0]["entry_id"] == "edge.cli"

    assert main(["edge-backlog", "duplicate-candidates", "edge.cli", "--project-root", str(tmp_path)]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert snapshot["candidates"] == []

    assert (
        main(
            [
                "edge-backlog",
                "review",
                "edge.cli",
                "--project-root",
                str(tmp_path),
                "--disposition",
                "REVIEWED_CONTINUE",
                "--duplicate-resolution",
                "DISTINCT_EDGE",
                "--candidate-snapshot-sha256",
                snapshot["snapshot_sha256"],
                "--reason-code",
                "OTHER",
                "--rationale",
                "The owner reviewed the empty deterministic candidate snapshot.",
                "--reviewer-id",
                "owner",
                "--decision-id",
                "decision.cli.review",
            ]
        )
        == 0
    )
    decision = json.loads(capsys.readouterr().out)
    assert decision["actor"]["actor_class"] == "HUMAN_OWNER_RESEARCHER"

    assert main(["edge-backlog", "show", "edge.cli", "--project-root", str(tmp_path), "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["state"] == "REVIEWED_CONTINUE"
    assert shown["entry"]["record_sha256"] == entry["record_sha256"]

    assert main(["edge-backlog", "validate", "--project-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_cli_suspension_requires_explicit_human_resume(tmp_path: Path, capsys) -> None:
    observation_input = _write(tmp_path / "observation.json", _observation())
    main(
        [
            "edge-backlog",
            "capture-observation",
            "--project-root",
            str(tmp_path),
            "--input",
            str(observation_input),
            "--actor-id",
            "codex-cli",
        ]
    )
    observation = json.loads(capsys.readouterr().out)
    entry_input = _write(tmp_path / "entry.json", _entry(observation["record_sha256"]))
    main(
        [
            "edge-backlog",
            "create",
            "--project-root",
            str(tmp_path),
            "--input",
            str(entry_input),
            "--actor-id",
            "codex-cli",
        ]
    )
    capsys.readouterr()
    main(["edge-backlog", "duplicate-candidates", "edge.cli", "--project-root", str(tmp_path)])
    snapshot = json.loads(capsys.readouterr().out)

    assert (
        main(
            [
                "edge-backlog",
                "review",
                "edge.cli",
                "--project-root",
                str(tmp_path),
                "--disposition",
                "SUSPENDED",
                "--duplicate-resolution",
                "UNRESOLVED",
                "--candidate-snapshot-sha256",
                snapshot["snapshot_sha256"],
                "--reason-code",
                "DATA_UNAVAILABLE",
                "--rationale",
                "The required timing evidence is not currently available.",
                "--revisit-condition",
                "A timestamped source becomes available.",
                "--reviewer-id",
                "owner",
                "--decision-id",
                "decision.cli.suspend",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "edge-backlog",
                "revise",
                "edge.cli",
                "--project-root",
                str(tmp_path),
                "--input",
                str(entry_input),
                "--actor-id",
                "codex-cli",
            ]
        )
        == 2
    )
    assert "resume is required" in capsys.readouterr().err

    assert (
        main(
            [
                "edge-backlog",
                "resume",
                "edge.cli",
                "--project-root",
                str(tmp_path),
                "--reason-code",
                "NEW_INFORMATION",
                "--rationale",
                "The owner verified newly available timestamped evidence.",
                "--reviewer-id",
                "owner",
                "--decision-id",
                "decision.cli.resume",
            ]
        )
        == 0
    )
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["disposition"] == "RESUMED"

    assert (
        main(
            [
                "edge-backlog",
                "revise",
                "edge.cli",
                "--project-root",
                str(tmp_path),
                "--input",
                str(entry_input),
                "--actor-id",
                "codex-cli",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["revision"] == 2


def test_cli_has_no_actor_escalation_delete_or_admission_command(capsys) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "edge-backlog",
                "capture-observation",
                "--input",
                "ignored.json",
                "--actor-id",
                "codex",
                "--actor-type",
                "HUMAN_OWNER_RESEARCHER",
            ]
        )
    assert "unrecognized arguments: --actor-type" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc:
        main(["edge-backlog", "delete"])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "invalid choice" in error
    assert "admit" not in error
