from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
import stat
import textwrap
import threading

import pytest
from pydantic import ValidationError

from alphaquest.studio.codex_runtime import (
    CodexAuthenticationMode,
    CodexAvailabilityStatus,
    CodexFailureKind,
    CodexIdempotencyConflictError,
    CodexRunStatus,
    CodexRunner,
    CodexSandboxMode,
    CodexTaskRequestV1,
    CodexTaskState,
    InvalidCodexTaskTransitionError,
    SQLiteCodexTaskQueue,
)


OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"action": {"type": "string", "minLength": 1}},
    "required": ["action"],
}


def _task(workspace: Path, **overrides) -> CodexTaskRequestV1:
    values = {
        "task_type": "hypothesis_proposal",
        "prompt": "Return the next governed proposal.",
        "output_schema": OUTPUT_SCHEMA,
        "workspace_root": str(workspace),
        "input_hashes": {"research_plan": "a" * 64},
    }
    values.update(overrides)
    return CodexTaskRequestV1(**values)


def _fake_codex(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-codex"
    executable.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            from pathlib import Path
            import sys
            import time

            args = sys.argv[1:]
            raw_args = list(args)
            fixture_root = Path(__file__).parent
            mode_path = fixture_root / "fake-codex-mode"
            mode = mode_path.read_text().strip() if mode_path.is_file() else "success"
            if args == ["--version"]:
                print("codex-cli 1.2.3")
                raise SystemExit(0)
            if args == ["login", "status"]:
                if mode == "logged-out":
                    print("Not logged in", file=sys.stderr)
                    raise SystemExit(1)
                if mode == "api-auth":
                    print("Logged in using API key")
                    raise SystemExit(0)
                print("Logged in using ChatGPT")
                raise SystemExit(0)
            if args and args[0] == "--search":
                args = args[1:]
            if not args or args[0] != "exec":
                raise SystemExit(2)

            prompt = sys.stdin.read()
            output_path = Path(args[args.index("--output-last-message") + 1])
            schema_path = Path(args[args.index("--output-schema") + 1])
            (fixture_root / "trace.json").write_text(json.dumps({
                "args": raw_args,
                "prompt": prompt,
                "schema": json.loads(schema_path.read_text()),
                "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
                "unrelated_secret_present": bool(os.environ.get("AWS_SECRET_ACCESS_KEY")),
            }))
            if mode in {"timeout", "cancel"}:
                time.sleep(5)
            if mode == "rate-limit":
                print("rate limit reached", file=sys.stderr)
                raise SystemExit(1)
            if mode == "auth-failure":
                print("authentication required", file=sys.stderr)
                raise SystemExit(1)
            if mode == "invalid-json":
                output_path.write_text("not-json")
            elif mode == "invalid-schema":
                output_path.write_text(json.dumps({"wrong": True}))
            else:
                output_path.write_text(json.dumps({"action": "REVIEW"}))
            print(json.dumps({"type": "thread.started", "thread_id": "thread-123"}))
            """
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _set_fake_mode(executable: Path, mode: str) -> None:
    executable.with_name("fake-codex-mode").write_text(mode, encoding="utf-8")


def test_task_contract_is_strict_read_only_and_rejects_unsafe_schemas(tmp_path):
    request = _task(tmp_path)

    assert request.sandbox == CodexSandboxMode.READ_ONLY
    document = request.model_dump(mode="python", by_alias=True)
    document["timeout_seconds"] = "10"
    with pytest.raises(ValidationError, match="float_type"):
        CodexTaskRequestV1.model_validate(document)

    writable = request.model_dump(mode="python", by_alias=True)
    writable["sandbox"] = "workspace-write"
    with pytest.raises(ValidationError, match="sandbox"):
        CodexTaskRequestV1.model_validate(writable)

    with pytest.raises(ValidationError, match="additionalProperties"):
        _task(
            tmp_path,
            output_schema={
                "type": "object",
                "properties": {"action": {"type": "string"}},
                "required": ["action"],
            },
        )
    with pytest.raises(ValidationError, match="external JSON Schema references"):
        _task(
            tmp_path,
            output_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"action": {"$ref": "https://example.invalid/schema.json"}},
                "required": ["action"],
            },
        )


def test_probe_requires_chatgpt_auth_and_returns_only_sanitized_status(tmp_path, monkeypatch):
    executable = _fake_codex(tmp_path)
    runner = CodexRunner(executable=str(executable))

    available = runner.probe()

    assert available.status == CodexAvailabilityStatus.AVAILABLE
    assert available.authentication_mode == CodexAuthenticationMode.CHATGPT
    assert available.version == "codex-cli 1.2.3"
    assert "token" not in available.model_dump_json().casefold()

    _set_fake_mode(executable, "api-auth")
    api_auth = runner.probe()
    assert api_auth.status == CodexAvailabilityStatus.WRONG_AUTH_MODE
    assert api_auth.authentication_mode == CodexAuthenticationMode.API_KEY

    _set_fake_mode(executable, "logged-out")
    logged_out = runner.probe()
    assert logged_out.status == CodexAvailabilityStatus.AUTH_REQUIRED
    assert logged_out.authenticated is False


def test_runner_uses_argv_stdin_schema_capture_and_strips_api_key(tmp_path, monkeypatch):
    executable = _fake_codex(tmp_path)
    trace_path = tmp_path / "trace.json"
    marker = tmp_path / "shell-injection-worked"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-reach-child")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-reach-child")
    prompt = f"Return a proposal; $(touch {marker})"
    runner = CodexRunner(executable=str(executable), poll_interval_seconds=0.01)

    result = runner.run(_task(tmp_path, prompt=prompt), task_id="task-1")

    assert result.status == CodexRunStatus.SUCCEEDED
    assert result.proposal == {"action": "REVIEW"}
    assert result.provenance.thread_id == "thread-123"
    assert result.provenance.sandbox == CodexSandboxMode.READ_ONLY
    assert result.output_metadata.schema_validated is True
    assert result.output_metadata.output_bytes > 0
    assert all("alphaquest-codex-" not in item for item in result.provenance.command_argv)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["prompt"] == prompt
    assert prompt not in trace["args"]
    assert trace["api_key_present"] is False
    assert trace["unrelated_secret_present"] is False
    assert trace["schema"] == OUTPUT_SCHEMA
    assert trace["args"][trace["args"].index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in trace["args"]
    assert "--ignore-rules" in trace["args"]
    assert "--skip-git-repo-check" in trace["args"]
    assert not marker.exists()


def test_runner_enables_native_web_search_only_when_predeclared(tmp_path, monkeypatch):
    executable = _fake_codex(tmp_path)
    trace_path = tmp_path / "trace.json"
    runner = CodexRunner(executable=str(executable), poll_interval_seconds=0.01)

    result = runner.run(_task(tmp_path, web_search=True), task_id="source-research")

    assert result.status == CodexRunStatus.SUCCEEDED
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["args"][0:2] == ["--search", "exec"]


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("invalid-json", CodexFailureKind.INVALID_OUTPUT),
        ("invalid-schema", CodexFailureKind.INVALID_OUTPUT),
        ("rate-limit", CodexFailureKind.RATE_LIMIT),
        ("auth-failure", CodexFailureKind.AUTH),
    ],
)
def test_runner_classifies_process_and_output_failures(tmp_path, monkeypatch, mode, expected):
    executable = _fake_codex(tmp_path)
    _set_fake_mode(executable, mode)
    runner = CodexRunner(executable=str(executable), poll_interval_seconds=0.01)

    result = runner.run(_task(tmp_path), task_id=f"task-{mode}")

    assert result.status == CodexRunStatus.FAILED
    assert result.proposal is None
    assert result.provenance.failure_kind == expected
    assert result.provenance.safe_error


def test_runner_classifies_timeout_and_cancellation(tmp_path, monkeypatch):
    executable = _fake_codex(tmp_path)
    runner = CodexRunner(executable=str(executable), poll_interval_seconds=0.01)

    _set_fake_mode(executable, "timeout")
    timed_out = runner.run(_task(tmp_path, timeout_seconds=0.08), task_id="timeout")
    assert timed_out.provenance.failure_kind == CodexFailureKind.TIMEOUT

    _set_fake_mode(executable, "cancel")
    cancellation = threading.Event()
    cancellation.set()
    cancelled = runner.run(
        _task(tmp_path),
        task_id="cancelled",
        cancellation_requested=cancellation.is_set,
    )
    assert cancelled.provenance.failure_kind == CodexFailureKind.CANCELLED


def test_codex_queue_submission_is_idempotent_and_separate(tmp_path):
    database = tmp_path / "codex.sqlite"
    queue = SQLiteCodexTaskQueue(database)
    request = _task(tmp_path)

    first = queue.submit(
        request,
        idempotency_key="research:one",
        max_runs=2,
        task_id="factory_task_one",
    )
    repeated = queue.submit(request, idempotency_key="research:one", max_runs=2)

    assert first.task_id == "factory_task_one"
    assert repeated.task_id == first.task_id
    assert repeated.state == CodexTaskState.WAITING_FOR_CODEX
    with pytest.raises(CodexIdempotencyConflictError):
        queue.submit(
            _task(tmp_path, prompt="A materially different request."),
            idempotency_key="research:one",
            max_runs=2,
        )
    with queue._connect() as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert "codex_tasks" in tables
    assert "studio_jobs" not in tables


def test_internal_task_scan_is_complete_while_public_listing_is_paginated(tmp_path):
    queue = SQLiteCodexTaskQueue(tmp_path / "codex.sqlite")
    request = _task(tmp_path)
    for index in range(3):
        queue.submit(request, idempotency_key=f"scan-{index}", task_id=f"scan_{index}")

    assert len(queue.list_tasks(limit=2)) == 2
    assert [item.task_id for item in queue.scan_tasks()] == ["scan_2", "scan_1", "scan_0"]



def test_queue_success_is_proposal_ready_with_append_only_run_provenance(tmp_path):
    executable = _fake_codex(tmp_path)
    queue = SQLiteCodexTaskQueue(tmp_path / "codex.sqlite")
    submitted = queue.submit(_task(tmp_path), idempotency_key="success")

    completed = queue.run_once(
        worker_id="codex-worker-1",
        runner=CodexRunner(executable=str(executable), poll_interval_seconds=0.01),
    )

    assert completed is not None
    assert completed.task_id == submitted.task_id
    assert completed.state == CodexTaskState.PROPOSAL_READY
    assert completed.proposal == {"action": "REVIEW"}
    assert completed.run_count == 1
    runs = queue.list_runs(submitted.task_id)
    assert len(runs) == 1
    assert runs[0].result.provenance.task_id == submitted.task_id
    assert queue.claim_next(worker_id="codex-worker-1") is None


def test_temporary_unavailability_pauses_and_requires_explicit_bounded_resume(tmp_path, monkeypatch):
    executable = _fake_codex(tmp_path)
    runner = CodexRunner(executable=str(executable), poll_interval_seconds=0.01)
    queue = SQLiteCodexTaskQueue(tmp_path / "codex.sqlite")
    submitted = queue.submit(_task(tmp_path), idempotency_key="bounded", max_runs=2)
    _set_fake_mode(executable, "rate-limit")

    paused = queue.run_once(worker_id="worker", runner=runner)

    assert paused is not None
    assert paused.state == CodexTaskState.PAUSED
    assert paused.failure_kind == CodexFailureKind.RATE_LIMIT
    assert queue.claim_next(worker_id="worker") is None

    resumed = queue.resume(submitted.task_id)
    assert resumed.state == CodexTaskState.WAITING_FOR_CODEX
    _set_fake_mode(executable, "success")
    completed = queue.run_once(worker_id="worker", runner=runner)
    assert completed is not None
    assert completed.state == CodexTaskState.PROPOSAL_READY
    assert completed.run_count == 2
    assert len(queue.list_runs(submitted.task_id)) == 2
    with pytest.raises(InvalidCodexTaskTransitionError):
        queue.resume(submitted.task_id)


def test_failed_task_never_replays_without_explicit_retry_and_budget(tmp_path, monkeypatch):
    executable = _fake_codex(tmp_path)
    runner = CodexRunner(executable=str(executable), poll_interval_seconds=0.01)
    queue = SQLiteCodexTaskQueue(tmp_path / "codex.sqlite")
    submitted = queue.submit(_task(tmp_path), idempotency_key="invalid", max_runs=1)
    _set_fake_mode(executable, "invalid-json")

    failed = queue.run_once(worker_id="worker", runner=runner)

    assert failed is not None
    assert failed.state == CodexTaskState.FAILED
    assert failed.run_count == 1
    assert queue.run_once(worker_id="worker", runner=runner) is None
    with pytest.raises(InvalidCodexTaskTransitionError, match="exhausted"):
        queue.retry_failed(submitted.task_id)


def test_queue_cancellation_and_orphan_recovery_are_terminal(tmp_path):
    queue = SQLiteCodexTaskQueue(tmp_path / "codex.sqlite")
    waiting = queue.submit(_task(tmp_path), idempotency_key="waiting")
    cancelled = queue.request_cancel(waiting.task_id)
    assert cancelled.state == CodexTaskState.CANCELLED

    active = queue.submit(_task(tmp_path), idempotency_key="active")
    queue.claim_next(worker_id="worker")
    recovered = queue.recover_orphaned_tasks(stale_after=timedelta(microseconds=1))
    assert [record.task_id for record in recovered] == [active.task_id]
    assert recovered[0].state == CodexTaskState.FAILED
    assert queue.claim_next(worker_id="other") is None
