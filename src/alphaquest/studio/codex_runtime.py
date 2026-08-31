"""Subscription-backed, fail-closed Codex runtime primitives for Research Studio.

This module is intentionally isolated from the Studio API, UI, and scientific
job worker.  Codex produces an untrusted proposal; AlphaQuest remains the
system of record and must validate/import that proposal in a later governed
step.  The runtime never passes a prompt through a shell and defaults to a
read-only Codex sandbox.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
from typing import Any, Literal
from uuid import uuid4

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema.validators import validator_for
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


CODEX_TASK_SCHEMA = "alphaquest.codex-runtime-task-request/v1"
CODEX_PROVENANCE_SCHEMA = "alphaquest.codex-runtime-run-provenance/v1"
CODEX_OUTPUT_METADATA_SCHEMA = "alphaquest.codex-output-metadata/v1"
CODEX_RUN_RESULT_SCHEMA = "alphaquest.codex-run-result/v1"
CODEX_AVAILABILITY_SCHEMA = "alphaquest.codex-availability/v1"
CODEX_TASK_RECORD_SCHEMA = "alphaquest.codex-task-record/v1"
CODEX_TASK_RUN_RECORD_SCHEMA = "alphaquest.codex-task-run-record/v1"
CODEX_QUEUE_SCHEMA_VERSION = 1

MAX_PROMPT_BYTES = 1_000_000
MAX_SCHEMA_BYTES = 500_000
MAX_FINAL_OUTPUT_BYTES = 2_000_000
MAX_PROCESS_CAPTURE_BYTES = 8_000_000
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class CodexSandboxMode(str, Enum):
    """The factory runtime is proposal-only and therefore always read-only."""

    READ_ONLY = "read-only"


class CodexFailureKind(str, Enum):
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    PROCESS_ERROR = "PROCESS_ERROR"


class CodexRunStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CodexAvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_INSTALLED = "NOT_INSTALLED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    WRONG_AUTH_MODE = "WRONG_AUTH_MODE"
    UNAVAILABLE = "UNAVAILABLE"


class CodexAuthenticationMode(str, Enum):
    CHATGPT = "CHATGPT"
    API_KEY = "API_KEY"
    UNKNOWN = "UNKNOWN"


class CodexTaskState(str, Enum):
    WAITING_FOR_CODEX = "WAITING_FOR_CODEX"
    RUNNING = "RUNNING"
    PROPOSAL_READY = "PROPOSAL_READY"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_TASK_STATES = {CodexTaskState.RUNNING, CodexTaskState.CANCEL_REQUESTED}
TERMINAL_TASK_STATES = {
    CodexTaskState.PROPOSAL_READY,
    CodexTaskState.FAILED,
    CodexTaskState.CANCELLED,
}
PAUSING_FAILURES = {
    CodexFailureKind.AUTH,
    CodexFailureKind.RATE_LIMIT,
    CodexFailureKind.UNAVAILABLE,
}


class CodexTaskRequestV1(BaseModel):
    """One bounded, schema-constrained request to the local Codex executable."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-runtime-task-request/v1"] = Field(
        default=CODEX_TASK_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    task_type: str
    prompt: str
    output_schema: dict[str, JsonValue]
    workspace_root: str
    input_hashes: dict[str, str] = Field(default_factory=dict)
    model: str | None = None
    web_search: bool = False
    sandbox: CodexSandboxMode = CodexSandboxMode.READ_ONLY
    timeout_seconds: float = Field(default=900.0, ge=0.05, le=7200.0)

    @field_validator("task_type", "workspace_root")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be non-empty")
        return value.strip()

    @field_validator("prompt")
    @classmethod
    def _bounded_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must be non-empty")
        if len(value.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise ValueError(f"prompt exceeds the {MAX_PROMPT_BYTES}-byte Codex task boundary")
        return value

    @field_validator("workspace_root")
    @classmethod
    def _absolute_workspace(cls, value: str) -> str:
        candidate = Path(value)
        if not candidate.is_absolute():
            raise ValueError("workspace_root must be absolute")
        return str(candidate)

    @field_validator("model")
    @classmethod
    def _optional_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("model cannot be blank")
        return normalized

    @field_validator("input_hashes")
    @classmethod
    def _valid_input_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, digest in value.items():
            clean_key = key.strip()
            if not clean_key:
                raise ValueError("input hash names must be non-empty")
            if not re.fullmatch(SHA256_PATTERN, digest):
                raise ValueError(f"input hash {clean_key!r} must be a lowercase SHA-256 digest")
            normalized[clean_key] = digest
        return normalized

    @field_validator("output_schema")
    @classmethod
    def _strict_output_schema(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _validate_output_schema(value)
        return value


class CodexRunProvenanceV1(BaseModel):
    """Secret-free, hash-bound record of one local Codex invocation."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-runtime-run-provenance/v1"] = Field(
        default=CODEX_PROVENANCE_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    run_id: str
    task_id: str
    task_sha256: str = Field(pattern=SHA256_PATTERN)
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    output_schema_sha256: str = Field(pattern=SHA256_PATTERN)
    input_hashes: dict[str, str]
    workspace_root: str
    sandbox: CodexSandboxMode
    requested_model: str | None = None
    codex_version: str | None = None
    command_argv: list[str]
    thread_id: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    exit_code: int | None = None
    failure_kind: CodexFailureKind | None = None
    safe_error: str | None = None

    @field_validator("run_id", "task_id")
    @classmethod
    def _required_ids(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run and task IDs must be non-empty")
        return value.strip()

    @field_validator("started_at", "finished_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provenance timestamps must be timezone-aware")
        return value

    @field_validator("command_argv")
    @classmethod
    def _safe_command(cls, value: list[str]) -> list[str]:
        if not value or any(not item for item in value):
            raise ValueError("command_argv must contain non-empty arguments")
        return value


class CodexOutputMetadataV1(BaseModel):
    """Bounded capture metadata; raw authentication/process streams are not stored."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-output-metadata/v1"] = Field(
        default=CODEX_OUTPUT_METADATA_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    output_bytes: int = Field(ge=0)
    stdout_sha256: str = Field(pattern=SHA256_PATTERN)
    stdout_bytes: int = Field(ge=0)
    stderr_sha256: str = Field(pattern=SHA256_PATTERN)
    stderr_bytes: int = Field(ge=0)
    schema_validated: bool


class CodexRunResultV1(BaseModel):
    """Result of a Codex run; a successful proposal is still untrusted input."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-run-result/v1"] = Field(
        default=CODEX_RUN_RESULT_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    status: CodexRunStatus
    proposal: dict[str, JsonValue] | None = None
    provenance: CodexRunProvenanceV1
    output_metadata: CodexOutputMetadataV1

    @model_validator(mode="after")
    def _consistent_result(self) -> "CodexRunResultV1":
        if self.status == CodexRunStatus.SUCCEEDED:
            if self.proposal is None or not self.output_metadata.schema_validated:
                raise ValueError("a successful Codex run requires a schema-validated proposal")
            if self.provenance.failure_kind is not None or self.provenance.safe_error is not None:
                raise ValueError("a successful Codex run cannot contain failure metadata")
        else:
            if self.proposal is not None:
                raise ValueError("a failed Codex run cannot expose a proposal")
            if self.provenance.failure_kind is None:
                raise ValueError("a failed Codex run requires a classified failure")
        return self


class CodexAvailabilityV1(BaseModel):
    """Sanitized local-runtime status.  It never includes credential material."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-availability/v1"] = Field(
        default=CODEX_AVAILABILITY_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    status: CodexAvailabilityStatus
    executable_available: bool
    authenticated: bool | None
    authentication_mode: CodexAuthenticationMode | None
    version: str | None
    checked_at: datetime
    detail: str

    @field_validator("checked_at")
    @classmethod
    def _checked_at_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("availability timestamp must be timezone-aware")
        return value


class CodexTaskRecordV1(BaseModel):
    """Strict public representation of one durable Codex task."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-task-record/v1"] = Field(
        default=CODEX_TASK_RECORD_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    task_id: str
    idempotency_key: str
    submission_sha256: str = Field(pattern=SHA256_PATTERN)
    request: CodexTaskRequestV1
    state: CodexTaskState
    worker_id: str | None = None
    run_count: int = Field(ge=0)
    max_runs: int = Field(ge=1, le=10)
    proposal: dict[str, JsonValue] | None = None
    last_run_result: CodexRunResultV1 | None = None
    failure_kind: CodexFailureKind | None = None
    error: str | None = None
    pause_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("task_id", "idempotency_key")
    @classmethod
    def _record_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task_id and idempotency_key must be non-empty")
        return value.strip()

    @field_validator(
        "created_at",
        "updated_at",
        "started_at",
        "heartbeat_at",
        "cancellation_requested_at",
        "finished_at",
    )
    @classmethod
    def _record_timestamps_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Codex task timestamps must be timezone-aware")
        return value


class CodexTaskRunRecordV1(BaseModel):
    """Append-only queue record for one invocation of a durable task."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_name: Literal["alphaquest.codex-task-run-record/v1"] = Field(
        default=CODEX_TASK_RUN_RECORD_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    task_id: str
    run_ordinal: int = Field(ge=1)
    result: CodexRunResultV1
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _run_timestamp_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Codex task-run timestamp must be timezone-aware")
        return value


class CodexIdempotencyConflictError(ValueError):
    """An idempotency key was reused for a materially different Codex task."""


class InvalidCodexTaskTransitionError(RuntimeError):
    """A caller attempted a fail-open or otherwise illegal queue transition."""


CancellationProbe = Callable[[], bool]
HeartbeatCallback = Callable[[], None]


class CodexRunner:
    """Invoke subscription-authenticated ``codex exec`` without using a shell."""

    def __init__(
        self,
        *,
        executable: str = "codex",
        require_chatgpt_login: bool = True,
        probe_timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.05,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        if not executable.strip():
            raise ValueError("Codex executable is required")
        if probe_timeout_seconds <= 0 or poll_interval_seconds <= 0 or heartbeat_interval_seconds <= 0:
            raise ValueError("Codex probe, poll, and heartbeat intervals must be positive")
        self.executable = executable.strip()
        self.require_chatgpt_login = bool(require_chatgpt_login)
        self.probe_timeout_seconds = float(probe_timeout_seconds)
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)

    def probe(self) -> CodexAvailabilityV1:
        """Check executable and login mode while returning only fixed safe messages."""

        checked_at = _now()
        resolved = _resolve_executable(self.executable)
        if resolved is None:
            return CodexAvailabilityV1(
                status=CodexAvailabilityStatus.NOT_INSTALLED,
                executable_available=False,
                authenticated=None,
                authentication_mode=None,
                version=None,
                checked_at=checked_at,
                detail="Codex executable was not found on the configured path.",
            )
        try:
            version_run = subprocess.run(  # noqa: S603 - fixed argv, shell is explicitly disabled
                [resolved, "--version"],
                capture_output=True,
                text=True,
                timeout=self.probe_timeout_seconds,
                check=False,
                shell=False,
                env=_subscription_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return CodexAvailabilityV1(
                status=CodexAvailabilityStatus.UNAVAILABLE,
                executable_available=True,
                authenticated=None,
                authentication_mode=None,
                version=None,
                checked_at=checked_at,
                detail="Codex executable did not respond to a local version check.",
            )
        version = _safe_version(version_run.stdout) if version_run.returncode == 0 else None
        if version_run.returncode != 0:
            return CodexAvailabilityV1(
                status=CodexAvailabilityStatus.UNAVAILABLE,
                executable_available=True,
                authenticated=None,
                authentication_mode=None,
                version=version,
                checked_at=checked_at,
                detail="Codex executable failed its local version check.",
            )
        try:
            login_run = subprocess.run(  # noqa: S603 - fixed argv, shell is explicitly disabled
                [resolved, "login", "status"],
                capture_output=True,
                text=True,
                timeout=self.probe_timeout_seconds,
                check=False,
                shell=False,
                env=_subscription_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return CodexAvailabilityV1(
                status=CodexAvailabilityStatus.UNAVAILABLE,
                executable_available=True,
                authenticated=None,
                authentication_mode=None,
                version=version,
                checked_at=checked_at,
                detail="Codex login status could not be checked locally.",
            )
        combined = f"{login_run.stdout}\n{login_run.stderr}".casefold()
        if login_run.returncode != 0 or any(
            marker in combined for marker in ("not logged in", "login required", "unauthenticated")
        ):
            return CodexAvailabilityV1(
                status=CodexAvailabilityStatus.AUTH_REQUIRED,
                executable_available=True,
                authenticated=False,
                authentication_mode=None,
                version=version,
                checked_at=checked_at,
                detail="Codex requires a local login.",
            )
        if "chatgpt" in combined:
            mode = CodexAuthenticationMode.CHATGPT
        elif "api key" in combined or "api-key" in combined:
            mode = CodexAuthenticationMode.API_KEY
        else:
            mode = CodexAuthenticationMode.UNKNOWN
        if self.require_chatgpt_login and mode != CodexAuthenticationMode.CHATGPT:
            return CodexAvailabilityV1(
                status=CodexAvailabilityStatus.WRONG_AUTH_MODE,
                executable_available=True,
                authenticated=True,
                authentication_mode=mode,
                version=version,
                checked_at=checked_at,
                detail="Codex is not confirmed to use ChatGPT subscription authentication.",
            )
        return CodexAvailabilityV1(
            status=CodexAvailabilityStatus.AVAILABLE,
            executable_available=True,
            authenticated=True,
            authentication_mode=mode,
            version=version,
            checked_at=checked_at,
            detail="Codex is available with approved local authentication.",
        )

    def run(
        self,
        task: CodexTaskRequestV1,
        *,
        task_id: str,
        cancellation_requested: CancellationProbe | None = None,
        heartbeat: HeartbeatCallback | None = None,
    ) -> CodexRunResultV1:
        """Run one task and return a classified result instead of leaking raw errors."""

        normalized_task_id = task_id.strip()
        if not normalized_task_id:
            raise ValueError("task_id is required")
        workspace = Path(task.workspace_root)
        if not workspace.is_dir():
            raise ValueError("Codex task workspace_root must identify an existing directory")
        availability = self.probe()
        if availability.status != CodexAvailabilityStatus.AVAILABLE:
            kind = (
                CodexFailureKind.AUTH
                if availability.status
                in {CodexAvailabilityStatus.AUTH_REQUIRED, CodexAvailabilityStatus.WRONG_AUTH_MODE}
                else CodexFailureKind.UNAVAILABLE
            )
            return _preflight_failure_result(
                task,
                task_id=normalized_task_id,
                executable=self.executable,
                codex_version=availability.version,
                failure_kind=kind,
                safe_error=availability.detail,
            )
        resolved = _resolve_executable(self.executable)
        if resolved is None:  # fail closed if PATH changed between probe and invocation
            return _preflight_failure_result(
                task,
                task_id=normalized_task_id,
                executable=self.executable,
                codex_version=availability.version,
                failure_kind=CodexFailureKind.UNAVAILABLE,
                safe_error="Codex executable became unavailable before invocation.",
            )

        task_sha = _model_sha256(task)
        prompt_sha = _sha256_bytes(task.prompt.encode("utf-8"))
        schema_json = _canonical_json(task.output_schema)
        schema_sha = _sha256_bytes(schema_json.encode("utf-8"))
        run_id = str(uuid4())
        started_at = _now()
        started_clock = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="alphaquest-codex-") as temporary_directory:
            temporary_root = Path(temporary_directory)
            schema_path = temporary_root / "output.schema.json"
            output_path = temporary_root / "proposal.json"
            prompt_path = temporary_root / "prompt.txt"
            schema_path.write_text(schema_json, encoding="utf-8")
            prompt_path.write_text(task.prompt, encoding="utf-8")
            argv = [resolved]
            if task.web_search:
                argv.append("--search")
            argv.extend(
                [
                "exec",
                "--sandbox",
                task.sandbox.value,
                "--cd",
                str(workspace),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--color",
                "never",
                "--json",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                ]
            )
            if task.model is not None:
                argv.extend(["--model", task.model])
            argv.append("-")
            stdout_bytes = b""
            stderr_bytes = b""
            exit_code: int | None = None
            failure_kind: CodexFailureKind | None = None
            safe_error: str | None = None
            proposal: dict[str, JsonValue] | None = None
            output_bytes = b""
            schema_validated = False

            try:
                with (
                    prompt_path.open("rb") as prompt_file,
                    tempfile.TemporaryFile() as stdout_file,
                    tempfile.TemporaryFile() as stderr_file,
                ):
                    process = subprocess.Popen(  # noqa: S603 - fixed argv, shell is explicitly disabled
                        argv,
                        cwd=workspace,
                        stdin=prompt_file,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        shell=False,
                        start_new_session=(os.name != "nt"),
                        env=_subscription_environment(),
                    )
                    deadline = started_clock + task.timeout_seconds
                    next_heartbeat = started_clock
                    while process.poll() is None:
                        current_clock = time.monotonic()
                        if heartbeat is not None and current_clock >= next_heartbeat:
                            heartbeat()
                            next_heartbeat = current_clock + self.heartbeat_interval_seconds
                        if cancellation_requested is not None and cancellation_requested():
                            failure_kind = CodexFailureKind.CANCELLED
                            safe_error = "Codex task was cancelled by the local controller."
                            _terminate_process(process)
                            break
                        if current_clock >= deadline:
                            failure_kind = CodexFailureKind.TIMEOUT
                            safe_error = f"Codex task exceeded its {task.timeout_seconds:g}-second timeout."
                            _terminate_process(process)
                            break
                        if stdout_file.tell() > MAX_PROCESS_CAPTURE_BYTES or stderr_file.tell() > MAX_PROCESS_CAPTURE_BYTES:
                            failure_kind = CodexFailureKind.INVALID_OUTPUT
                            safe_error = "Codex process output exceeded the bounded capture limit."
                            _terminate_process(process)
                            break
                        time.sleep(self.poll_interval_seconds)
                    if process.poll() is None:
                        _terminate_process(process)
                    exit_code = process.wait(timeout=2.0)
                    stdout_file.seek(0)
                    stderr_file.seek(0)
                    stdout_bytes = stdout_file.read(MAX_PROCESS_CAPTURE_BYTES + 1)
                    stderr_bytes = stderr_file.read(MAX_PROCESS_CAPTURE_BYTES + 1)
            except OSError:
                failure_kind = CodexFailureKind.UNAVAILABLE
                safe_error = "Codex process could not be started locally."
            except Exception as exc:  # subprocess boundary must become classified evidence
                failure_kind = CodexFailureKind.PROCESS_ERROR
                safe_error = _safe_error_detail(f"{type(exc).__name__}: {exc}")

            if failure_kind is None and (
                len(stdout_bytes) > MAX_PROCESS_CAPTURE_BYTES
                or len(stderr_bytes) > MAX_PROCESS_CAPTURE_BYTES
            ):
                failure_kind = CodexFailureKind.INVALID_OUTPUT
                safe_error = "Codex process output exceeded the bounded capture limit."
            if failure_kind is None and exit_code != 0:
                failure_kind = _classify_process_failure(stdout_bytes, stderr_bytes)
                safe_error = _process_failure_message(failure_kind, exit_code)
            if failure_kind is None:
                try:
                    if not output_path.is_file():
                        raise ValueError("Codex produced no final proposal file")
                    if output_path.stat().st_size > MAX_FINAL_OUTPUT_BYTES:
                        raise ValueError("Codex final proposal exceeded the bounded output limit")
                    output_bytes = output_path.read_bytes()
                    decoded = json.loads(output_bytes.decode("utf-8"))
                    if not isinstance(decoded, dict):
                        raise ValueError("Codex proposal must be a JSON object")
                    validator_for(task.output_schema)(task.output_schema).validate(decoded)
                    proposal = decoded
                    schema_validated = True
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    ValueError,
                    OSError,
                    jsonschema_exceptions.ValidationError,
                    jsonschema_exceptions.SchemaError,
                ) as exc:
                    failure_kind = CodexFailureKind.INVALID_OUTPUT
                    safe_error = _safe_error_detail(f"Codex proposal failed validation: {exc}")

            finished_at = _now()
            duration_ms = max(0, round((time.monotonic() - started_clock) * 1000))
            thread_id = _extract_thread_id(stdout_bytes)
            command_for_provenance = _stable_command_argv(argv, temporary_root=temporary_root)
            provenance = CodexRunProvenanceV1(
                run_id=run_id,
                task_id=normalized_task_id,
                task_sha256=task_sha,
                prompt_sha256=prompt_sha,
                output_schema_sha256=schema_sha,
                input_hashes=task.input_hashes,
                workspace_root=str(workspace),
                sandbox=task.sandbox,
                requested_model=task.model,
                codex_version=availability.version,
                command_argv=command_for_provenance,
                thread_id=thread_id,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                exit_code=exit_code,
                failure_kind=failure_kind,
                safe_error=safe_error,
            )
            metadata = CodexOutputMetadataV1(
                output_sha256=_sha256_bytes(output_bytes) if output_bytes else None,
                output_bytes=len(output_bytes),
                stdout_sha256=_sha256_bytes(stdout_bytes),
                stdout_bytes=len(stdout_bytes),
                stderr_sha256=_sha256_bytes(stderr_bytes),
                stderr_bytes=len(stderr_bytes),
                schema_validated=schema_validated,
            )
            return CodexRunResultV1(
                status=CodexRunStatus.SUCCEEDED if failure_kind is None else CodexRunStatus.FAILED,
                proposal=proposal if failure_kind is None else None,
                provenance=provenance,
                output_metadata=metadata,
            )


class SQLiteCodexTaskQueue:
    """A durable Codex-only queue with explicit, bounded retries."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def submit(
        self,
        request: CodexTaskRequestV1,
        *,
        idempotency_key: str,
        max_runs: int = 3,
        task_id: str | None = None,
    ) -> CodexTaskRecordV1:
        key = idempotency_key.strip()
        if not key:
            raise ValueError("idempotency_key is required")
        if max_runs < 1 or max_runs > 10:
            raise ValueError("max_runs must be between 1 and 10")
        request_json = _canonical_json(request.model_dump(mode="json", by_alias=True))
        submission_sha = _sha256_bytes(
            _canonical_json({"request": json.loads(request_json), "max_runs": max_runs}).encode("utf-8")
        )
        resolved_task_id = (task_id or str(uuid4())).strip()
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", resolved_task_id) is None:
            raise ValueError("task_id must be a stable identifier of at most 128 characters")
        now = _now_iso()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM codex_tasks WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                if existing["submission_sha256"] != submission_sha:
                    raise CodexIdempotencyConflictError(
                        f"idempotency key {key!r} already identifies a different Codex task"
                    )
                connection.commit()
                return _codex_task_record(existing)
            connection.execute(
                """
                INSERT INTO codex_tasks (
                    task_id, schema_name, idempotency_key, submission_sha256,
                    request_json, state, run_count, max_runs, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    resolved_task_id,
                    CODEX_TASK_RECORD_SCHEMA,
                    key,
                    submission_sha,
                    request_json,
                    CodexTaskState.WAITING_FOR_CODEX.value,
                    max_runs,
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get(resolved_task_id)

    def get(self, task_id: str) -> CodexTaskRecordV1:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM codex_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown Codex task: {task_id}")
        return _codex_task_record(row)

    def list_tasks(
        self,
        *,
        states: set[CodexTaskState | str] | None = None,
        limit: int = 100,
    ) -> list[CodexTaskRecordV1]:
        if limit < 1:
            raise ValueError("limit must be positive")
        parameters: list[Any] = []
        where = ""
        if states:
            values = sorted(CodexTaskState(item).value for item in states)
            where = f"WHERE state IN ({','.join('?' for _ in values)})"
            parameters.extend(values)
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM codex_tasks {where} ORDER BY created_at DESC, rowid DESC LIMIT ?",  # noqa: S608
                parameters,
            ).fetchall()
        return [_codex_task_record(row) for row in rows]

    def scan_tasks(
        self,
        *,
        states: set[CodexTaskState | str] | None = None,
    ) -> list[CodexTaskRecordV1]:
        """Return the complete durable task set for internal invariants.

        Public/API listings remain explicitly paginated through
        :meth:`list_tasks`.  Controller accounting, recovery, reconciliation,
        and ancestry checks must never inherit that presentation limit.
        """

        parameters: list[Any] = []
        where = ""
        if states:
            values = sorted(CodexTaskState(item).value for item in states)
            where = f"WHERE state IN ({','.join('?' for _ in values)})"
            parameters.extend(values)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM codex_tasks {where} ORDER BY created_at DESC, rowid DESC",  # noqa: S608
                parameters,
            ).fetchall()
        return [_codex_task_record(row) for row in rows]

    def list_runs(self, task_id: str) -> list[CodexTaskRunRecordV1]:
        self.get(task_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM codex_task_runs WHERE task_id = ? ORDER BY run_ordinal",
                (task_id,),
            ).fetchall()
        return [_codex_task_run_record(row) for row in rows]

    def claim_next(self, *, worker_id: str) -> CodexTaskRecordV1 | None:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id is required")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                "SELECT task_id FROM codex_tasks WHERE state IN (?, ?) LIMIT 1",
                (CodexTaskState.RUNNING.value, CodexTaskState.CANCEL_REQUESTED.value),
            ).fetchone()
            if active is not None:
                connection.commit()
                return None
            row = connection.execute(
                """
                SELECT * FROM codex_tasks
                WHERE state = ? AND run_count < max_runs
                ORDER BY created_at, rowid LIMIT 1
                """,
                (CodexTaskState.WAITING_FOR_CODEX.value,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            now = _now_iso()
            changed = connection.execute(
                """
                UPDATE codex_tasks
                SET state = ?, worker_id = ?, run_count = run_count + 1,
                    started_at = ?, heartbeat_at = ?, finished_at = NULL,
                    failure_kind = NULL, error = NULL, pause_reason = NULL, updated_at = ?
                WHERE task_id = ? AND state = ? AND run_count < max_runs
                """,
                (
                    CodexTaskState.RUNNING.value,
                    worker,
                    now,
                    now,
                    now,
                    row["task_id"],
                    CodexTaskState.WAITING_FOR_CODEX.value,
                ),
            ).rowcount
            connection.commit()
        return self.get(row["task_id"]) if changed else None

    def heartbeat(self, task_id: str, *, worker_id: str) -> CodexTaskRecordV1:
        now = _now_iso()
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE codex_tasks SET heartbeat_at = ?, updated_at = ?
                WHERE task_id = ? AND worker_id = ? AND state IN (?, ?)
                """,
                (
                    now,
                    now,
                    task_id,
                    worker_id,
                    CodexTaskState.RUNNING.value,
                    CodexTaskState.CANCEL_REQUESTED.value,
                ),
            ).rowcount
        if not changed:
            raise InvalidCodexTaskTransitionError("heartbeat requires ownership of an active Codex task")
        return self.get(task_id)

    def request_cancel(self, task_id: str) -> CodexTaskRecordV1:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM codex_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Codex task: {task_id}")
            record = _codex_task_record(row)
            now = _now_iso()
            if record.state in TERMINAL_TASK_STATES:
                connection.commit()
                return record
            if record.state in {CodexTaskState.WAITING_FOR_CODEX, CodexTaskState.PAUSED}:
                connection.execute(
                    """
                    UPDATE codex_tasks SET state = ?, cancellation_requested_at = ?,
                        finished_at = ?, updated_at = ? WHERE task_id = ?
                    """,
                    (CodexTaskState.CANCELLED.value, now, now, now, task_id),
                )
            elif record.state == CodexTaskState.RUNNING:
                connection.execute(
                    """
                    UPDATE codex_tasks SET state = ?, cancellation_requested_at = ?, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (CodexTaskState.CANCEL_REQUESTED.value, now, now, task_id),
                )
            connection.commit()
        return self.get(task_id)

    def pause(self, task_id: str, *, reason: str) -> CodexTaskRecordV1:
        message = reason.strip()
        if not message:
            raise ValueError("pause reason is required")
        now = _now_iso()
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE codex_tasks SET state = ?, pause_reason = ?, finished_at = ?, updated_at = ?
                WHERE task_id = ? AND state = ?
                """,
                (
                    CodexTaskState.PAUSED.value,
                    message,
                    now,
                    now,
                    task_id,
                    CodexTaskState.WAITING_FOR_CODEX.value,
                ),
            ).rowcount
        if not changed:
            raise InvalidCodexTaskTransitionError("only a waiting Codex task can be paused")
        return self.get(task_id)

    def resume(self, task_id: str) -> CodexTaskRecordV1:
        return self._explicit_requeue(task_id, required_state=CodexTaskState.PAUSED)

    def retry_failed(self, task_id: str) -> CodexTaskRecordV1:
        return self._explicit_requeue(task_id, required_state=CodexTaskState.FAILED)

    def complete_run(
        self,
        task_id: str,
        *,
        worker_id: str,
        result: CodexRunResultV1,
    ) -> CodexTaskRecordV1:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM codex_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Codex task: {task_id}")
            record = _codex_task_record(row)
            if record.worker_id != worker_id or record.state not in ACTIVE_TASK_STATES:
                raise InvalidCodexTaskTransitionError("only the owning worker can finish an active Codex task")
            if result.provenance.task_id != task_id:
                raise ValueError("Codex result task ID does not match the queue task")
            if result.provenance.task_sha256 != _model_sha256(record.request):
                raise ValueError("Codex result does not match the queued task hash")
            now = _now_iso()
            if record.state == CodexTaskState.CANCEL_REQUESTED:
                target_state = CodexTaskState.CANCELLED
                failure_kind = CodexFailureKind.CANCELLED
                error = "Codex task was cancelled by the local controller."
                pause_reason = None
                proposal = None
            elif result.status == CodexRunStatus.SUCCEEDED:
                target_state = CodexTaskState.PROPOSAL_READY
                failure_kind = None
                error = None
                pause_reason = None
                proposal = result.proposal
            else:
                assert result.provenance.failure_kind is not None
                failure_kind = result.provenance.failure_kind
                error = result.provenance.safe_error
                if failure_kind in PAUSING_FAILURES:
                    target_state = CodexTaskState.PAUSED
                    pause_reason = error or "Codex is temporarily unavailable."
                elif failure_kind == CodexFailureKind.CANCELLED:
                    target_state = CodexTaskState.CANCELLED
                    pause_reason = None
                else:
                    target_state = CodexTaskState.FAILED
                    pause_reason = None
                proposal = None
            result_json = _canonical_json(result.model_dump(mode="json", by_alias=True))
            connection.execute(
                """
                INSERT INTO codex_task_runs (
                    run_id, schema_name, task_id, run_ordinal, result_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.provenance.run_id,
                    CODEX_TASK_RUN_RECORD_SCHEMA,
                    task_id,
                    record.run_count,
                    result_json,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE codex_tasks
                SET state = ?, worker_id = NULL, proposal_json = ?, last_run_result_json = ?,
                    failure_kind = ?, error = ?, pause_reason = ?, heartbeat_at = ?,
                    finished_at = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    target_state.value,
                    _canonical_json(proposal) if proposal is not None else None,
                    result_json,
                    failure_kind.value if failure_kind is not None else None,
                    error,
                    pause_reason,
                    now,
                    now,
                    now,
                    task_id,
                ),
            )
            connection.commit()
        return self.get(task_id)

    def run_once(self, *, worker_id: str, runner: CodexRunner) -> CodexTaskRecordV1 | None:
        """Run one task.  Failures pause or terminate; none are automatically replayed."""

        task = self.claim_next(worker_id=worker_id)
        if task is None:
            return None
        try:
            result = runner.run(
                task.request,
                task_id=task.task_id,
                cancellation_requested=lambda: self.get(task.task_id).state
                == CodexTaskState.CANCEL_REQUESTED,
                heartbeat=lambda: self.heartbeat(task.task_id, worker_id=worker_id),
            )
        except Exception as exc:  # keep an unexpected adapter defect from orphaning the task
            result = _unexpected_failure_result(task.request, task_id=task.task_id, error=exc)
        return self.complete_run(task.task_id, worker_id=worker_id, result=result)

    def recover_orphaned_tasks(self, *, stale_after: timedelta) -> list[CodexTaskRecordV1]:
        """Terminate stale active tasks; recovery never silently requeues them."""

        if stale_after.total_seconds() <= 0:
            raise ValueError("stale_after must be positive")
        cutoff = (_now() - stale_after).isoformat()
        recovered: list[str] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT * FROM codex_tasks
                WHERE state IN (?, ?) AND COALESCE(heartbeat_at, started_at, updated_at) < ?
                """,
                (CodexTaskState.RUNNING.value, CodexTaskState.CANCEL_REQUESTED.value, cutoff),
            ).fetchall()
            now = _now_iso()
            for row in rows:
                cancellation = row["state"] == CodexTaskState.CANCEL_REQUESTED.value
                connection.execute(
                    """
                    UPDATE codex_tasks
                    SET state = ?, worker_id = NULL, failure_kind = ?, error = ?,
                        finished_at = ?, updated_at = ? WHERE task_id = ?
                    """,
                    (
                        CodexTaskState.CANCELLED.value if cancellation else CodexTaskState.FAILED.value,
                        CodexFailureKind.CANCELLED.value if cancellation else CodexFailureKind.PROCESS_ERROR.value,
                        (
                            "Codex cancellation was recovered after its worker heartbeat expired."
                            if cancellation
                            else "Codex worker heartbeat expired; automatic replay is forbidden."
                        ),
                        now,
                        now,
                        row["task_id"],
                    ),
                )
                recovered.append(row["task_id"])
            connection.commit()
        return [self.get(task_id) for task_id in recovered]

    def _explicit_requeue(
        self,
        task_id: str,
        *,
        required_state: CodexTaskState,
    ) -> CodexTaskRecordV1:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM codex_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Codex task: {task_id}")
            record = _codex_task_record(row)
            if record.state != required_state:
                raise InvalidCodexTaskTransitionError(
                    f"explicit requeue requires state {required_state.value}"
                )
            if record.run_count >= record.max_runs:
                raise InvalidCodexTaskTransitionError("Codex task exhausted its explicit run budget")
            now = _now_iso()
            connection.execute(
                """
                UPDATE codex_tasks
                SET state = ?, worker_id = NULL, proposal_json = NULL,
                    failure_kind = NULL, error = NULL, pause_reason = NULL,
                    started_at = NULL, heartbeat_at = NULL,
                    cancellation_requested_at = NULL, finished_at = NULL, updated_at = ?
                WHERE task_id = ?
                """,
                (CodexTaskState.WAITING_FOR_CODEX.value, now, task_id),
            )
            connection.commit()
        return self.get(task_id)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS codex_queue_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            current = connection.execute(
                "SELECT value FROM codex_queue_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if current is not None and int(current["value"]) != CODEX_QUEUE_SCHEMA_VERSION:
                raise RuntimeError(
                    f"Codex queue schema {current['value']} is unsupported; "
                    f"expected {CODEX_QUEUE_SCHEMA_VERSION}"
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO codex_queue_metadata (key, value) VALUES ('schema_version', ?)
                """,
                (str(CODEX_QUEUE_SCHEMA_VERSION),),
            )
            allowed_states = ",".join(repr(item.value) for item in CodexTaskState)
            allowed_failures = ",".join(repr(item.value) for item in CodexFailureKind)
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS codex_tasks (
                    task_id TEXT PRIMARY KEY,
                    schema_name TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    submission_sha256 TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ({allowed_states})),
                    worker_id TEXT,
                    run_count INTEGER NOT NULL DEFAULT 0 CHECK (run_count >= 0),
                    max_runs INTEGER NOT NULL CHECK (max_runs BETWEEN 1 AND 10),
                    proposal_json TEXT,
                    last_run_result_json TEXT,
                    failure_kind TEXT CHECK (failure_kind IS NULL OR failure_kind IN ({allowed_failures})),
                    error TEXT,
                    pause_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    heartbeat_at TEXT,
                    cancellation_requested_at TEXT,
                    finished_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS codex_task_runs (
                    run_id TEXT PRIMARY KEY,
                    schema_name TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    run_ordinal INTEGER NOT NULL CHECK (run_ordinal >= 1),
                    result_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE (task_id, run_ordinal),
                    FOREIGN KEY (task_id) REFERENCES codex_tasks(task_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS codex_tasks_state_order ON codex_tasks(state, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS codex_task_runs_task ON codex_task_runs(task_id, run_ordinal)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def _validate_output_schema(schema: Mapping[str, JsonValue]) -> None:
    encoded = _canonical_json(schema).encode("utf-8")
    if len(encoded) > MAX_SCHEMA_BYTES:
        raise ValueError(f"output schema exceeds the {MAX_SCHEMA_BYTES}-byte boundary")
    if schema.get("type") != "object":
        raise ValueError("Codex output schema root must have type 'object'")
    if schema.get("additionalProperties") is not False:
        raise ValueError("Codex output schema must set root additionalProperties to false")
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not properties:
        raise ValueError("Codex output schema must declare object properties")
    if not isinstance(required, list) or set(required) != set(properties):
        raise ValueError("Codex output schema must require every root property")
    for node in _walk_json(schema):
        if not isinstance(node, dict):
            continue
        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str) or not reference.startswith("#"):
                raise ValueError("external JSON Schema references are forbidden")
        if node.get("type") == "object":
            nested_properties = node.get("properties")
            nested_required = node.get("required")
            if node.get("additionalProperties") is not False:
                raise ValueError("every Codex output object must set additionalProperties to false")
            if not isinstance(nested_properties, dict):
                raise ValueError("every Codex output object must declare properties")
            if not isinstance(nested_required, list) or set(nested_required) != set(nested_properties):
                raise ValueError("every Codex output object must require all declared properties")
    try:
        validator_for(schema).check_schema(schema)
    except jsonschema_exceptions.SchemaError as exc:
        raise ValueError(f"invalid Codex output schema: {exc.message}") from exc


def _walk_json(value: JsonValue | Mapping[str, JsonValue]) -> list[JsonValue | Mapping[str, JsonValue]]:
    nodes: list[JsonValue | Mapping[str, JsonValue]] = [value]
    if isinstance(value, dict):
        for item in value.values():
            nodes.extend(_walk_json(item))
    elif isinstance(value, list):
        for item in value:
            nodes.extend(_walk_json(item))
    return nodes


def _resolve_executable(executable: str) -> str | None:
    if os.sep in executable or (os.altsep and os.altsep in executable):
        path = Path(executable)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(executable)


def _subscription_environment() -> dict[str, str]:
    """Expose only process essentials and local-login paths to the Codex child."""

    allowed = {
        "CODEX_HOME",
        "COLORTERM",
        "COMSPEC",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "NO_COLOR",
        "PATH",
        "PATHEXT",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "TMPDIR",
        "USER",
        "WINDIR",
        "XDG_CONFIG_HOME",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def _safe_version(value: str) -> str | None:
    for line in value.splitlines():
        normalized = line.strip()
        if normalized and len(normalized) <= 120 and re.fullmatch(r"[A-Za-z0-9_.+ -]+", normalized):
            return normalized
    return None


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            pass


def _classify_process_failure(stdout: bytes, stderr: bytes) -> CodexFailureKind:
    text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace").casefold()
    if any(
        marker in text
        for marker in (
            "not logged in",
            "login required",
            "authentication required",
            "unauthorized",
            "invalid authentication",
            "http 401",
        )
    ):
        return CodexFailureKind.AUTH
    if any(
        marker in text
        for marker in (
            "rate limit",
            "too many requests",
            "usage limit",
            "quota exceeded",
            "limit reached",
            "http 429",
        )
    ):
        return CodexFailureKind.RATE_LIMIT
    if any(
        marker in text
        for marker in (
            "service unavailable",
            "failed to connect",
            "connection refused",
            "could not resolve",
            "network is unreachable",
            "http 503",
        )
    ):
        return CodexFailureKind.UNAVAILABLE
    return CodexFailureKind.PROCESS_ERROR


def _process_failure_message(kind: CodexFailureKind, exit_code: int | None) -> str:
    suffix = f" (exit code {exit_code})" if exit_code is not None else ""
    messages = {
        CodexFailureKind.AUTH: "Codex authentication failed; local login is required.",
        CodexFailureKind.RATE_LIMIT: "Codex usage or rate limit was reached; explicit resume is required.",
        CodexFailureKind.UNAVAILABLE: "Codex service or network was unavailable.",
        CodexFailureKind.PROCESS_ERROR: "Codex process failed without a usable proposal.",
    }
    return messages.get(kind, "Codex execution failed.") + suffix


def _safe_error_detail(value: str) -> str:
    sanitized = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", value)
    sanitized = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", sanitized)
    sanitized = re.sub(
        r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        sanitized,
    )
    return sanitized.strip()[:1000] or "Codex execution failed."


def _extract_thread_id(stdout: bytes) -> str | None:
    for raw_line in stdout.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            value = event.get("thread_id")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _stable_command_argv(argv: list[str], *, temporary_root: Path) -> list[str]:
    """Replace ephemeral paths while preserving an auditable, secret-free command."""

    prefix = str(temporary_root)
    return [item.replace(prefix, "<runtime-temp>") for item in argv]


def _preflight_failure_result(
    task: CodexTaskRequestV1,
    *,
    task_id: str,
    executable: str,
    codex_version: str | None,
    failure_kind: CodexFailureKind,
    safe_error: str,
) -> CodexRunResultV1:
    now = _now()
    return CodexRunResultV1(
        status=CodexRunStatus.FAILED,
        proposal=None,
        provenance=CodexRunProvenanceV1(
            run_id=str(uuid4()),
            task_id=task_id,
            task_sha256=_model_sha256(task),
            prompt_sha256=_sha256_bytes(task.prompt.encode("utf-8")),
            output_schema_sha256=_sha256_bytes(_canonical_json(task.output_schema).encode("utf-8")),
            input_hashes=task.input_hashes,
            workspace_root=task.workspace_root,
            sandbox=task.sandbox,
            requested_model=task.model,
            codex_version=codex_version,
            command_argv=[executable, "exec", "--sandbox", task.sandbox.value, "-"],
            started_at=now,
            finished_at=now,
            duration_ms=0,
            exit_code=None,
            failure_kind=failure_kind,
            safe_error=safe_error,
        ),
        output_metadata=_empty_output_metadata(),
    )


def _unexpected_failure_result(
    task: CodexTaskRequestV1,
    *,
    task_id: str,
    error: Exception,
) -> CodexRunResultV1:
    return _preflight_failure_result(
        task,
        task_id=task_id,
        executable="codex",
        codex_version=None,
        failure_kind=CodexFailureKind.PROCESS_ERROR,
        safe_error=_safe_error_detail(f"{type(error).__name__}: {error}"),
    )


def _empty_output_metadata() -> CodexOutputMetadataV1:
    empty_sha = _sha256_bytes(b"")
    return CodexOutputMetadataV1(
        output_sha256=None,
        output_bytes=0,
        stdout_sha256=empty_sha,
        stdout_bytes=0,
        stderr_sha256=empty_sha,
        stderr_bytes=0,
        schema_validated=False,
    )


def _codex_task_record(row: sqlite3.Row) -> CodexTaskRecordV1:
    request = CodexTaskRequestV1.model_validate_json(row["request_json"])
    last_run_result = (
        CodexRunResultV1.model_validate_json(row["last_run_result_json"])
        if row["last_run_result_json"]
        else None
    )
    return CodexTaskRecordV1.model_validate(
        {
            "schema": row["schema_name"],
            "task_id": row["task_id"],
            "idempotency_key": row["idempotency_key"],
            "submission_sha256": row["submission_sha256"],
            "request": request,
            "state": CodexTaskState(row["state"]),
            "worker_id": row["worker_id"],
            "run_count": int(row["run_count"]),
            "max_runs": int(row["max_runs"]),
            "proposal": json.loads(row["proposal_json"]) if row["proposal_json"] else None,
            "last_run_result": last_run_result,
            "failure_kind": CodexFailureKind(row["failure_kind"]) if row["failure_kind"] else None,
            "error": row["error"],
            "pause_reason": row["pause_reason"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "updated_at": datetime.fromisoformat(row["updated_at"]),
            "started_at": datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            "heartbeat_at": datetime.fromisoformat(row["heartbeat_at"]) if row["heartbeat_at"] else None,
            "cancellation_requested_at": (
                datetime.fromisoformat(row["cancellation_requested_at"])
                if row["cancellation_requested_at"]
                else None
            ),
            "finished_at": datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        }
    )


def _codex_task_run_record(row: sqlite3.Row) -> CodexTaskRunRecordV1:
    result = CodexRunResultV1.model_validate_json(row["result_json"])
    return CodexTaskRunRecordV1.model_validate(
        {
            "schema": row["schema_name"],
            "task_id": row["task_id"],
            "run_ordinal": int(row["run_ordinal"]),
            "result": result,
            "recorded_at": datetime.fromisoformat(row["recorded_at"]),
        }
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _model_sha256(value: BaseModel) -> str:
    document = value.model_dump(mode="json", by_alias=True)
    return _sha256_bytes(_canonical_json(document).encode("utf-8"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now().isoformat()
