"""Durable single-worker queue for local Research Studio operations.

Operational state is deliberately separate from a scientific verdict.  A job
can fail operationally without turning a strategy into a scientific FAIL, and
an interrupted job becomes ``NEEDS MANUAL REVIEW`` only after evidence has
actually been reserved.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from enum import Enum
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


JOB_SCHEMA = "alphaquest.studio-job/v1"
DATABASE_SCHEMA_VERSION = 1
STRICT_VERDICTS = {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}


class OperationalState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED_OPERATIONAL = "FAILED_OPERATIONAL"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_STATES = {OperationalState.RUNNING, OperationalState.CANCEL_REQUESTED}
TERMINAL_STATES = {
    OperationalState.BLOCKED,
    OperationalState.SUCCEEDED,
    OperationalState.FAILED_OPERATIONAL,
    OperationalState.CANCELLED,
}


class JobRecordV1(BaseModel):
    """Strict public representation of one queued operation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_name: Literal["alphaquest.studio-job/v1"] = Field(
        default=JOB_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    job_id: str
    job_type: str
    campaign_id: str | None = None
    idempotency_key: str
    payload: dict[str, Any]
    payload_sha256: str
    hash_locks: dict[str, str]
    state: OperationalState
    worker_id: str | None = None
    attempt_reserved: bool = False
    research_verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"] | None = None
    result: dict[str, Any] | None = None
    blocked_reason: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("job_id", "job_type", "idempotency_key")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be non-empty")
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
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("job timestamps must be timezone-aware")
        return value


class IdempotencyConflictError(ValueError):
    """The same key was reused for a materially different operation."""


class InvalidJobTransitionError(RuntimeError):
    """A caller attempted an unsafe operational-state transition."""


class JobCancellationRequested(RuntimeError):
    """Cooperative worker cancellation signal."""


HashObserver = Mapping[str, str] | Callable[[JobRecordV1], Mapping[str, str]]
JobExecutor = Callable[["JobExecutionContext", JobRecordV1], dict[str, Any] | None]


class SQLiteJobQueue:
    """SQLite-backed queue that permits at most one active local worker job."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def submit(
        self,
        *,
        job_type: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        hash_locks: Mapping[str, str],
        campaign_id: str | None = None,
    ) -> JobRecordV1:
        """Queue once; an identical repeated submission returns the original."""

        job_type_value = job_type.strip()
        key = idempotency_key.strip()
        if not job_type_value or not key:
            raise ValueError("job_type and idempotency_key are required")
        normalized_payload = _json_mapping(payload, label="payload")
        normalized_locks = _string_mapping(hash_locks, label="hash_locks")
        payload_json = _canonical_json(normalized_payload)
        locks_json = _canonical_json(normalized_locks)
        payload_sha = _sha256_text(payload_json)
        submission_sha = _sha256_text(
            _canonical_json(
                {
                    "job_type": job_type_value,
                    "campaign_id": campaign_id,
                    "payload": normalized_payload,
                    "hash_locks": normalized_locks,
                }
            )
        )
        now = _now_iso()
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM studio_jobs WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                if existing["submission_sha256"] != submission_sha:
                    raise IdempotencyConflictError(
                        f"idempotency key {key!r} already identifies a different operation"
                    )
                connection.commit()
                return _record(existing)
            connection.execute(
                """
                INSERT INTO studio_jobs (
                    job_id, schema_name, job_type, campaign_id, idempotency_key,
                    submission_sha256, payload_json, payload_sha256, hash_locks_json,
                    state, attempt_reserved, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    job_id,
                    JOB_SCHEMA,
                    job_type_value,
                    campaign_id,
                    key,
                    submission_sha,
                    payload_json,
                    payload_sha,
                    locks_json,
                    OperationalState.QUEUED.value,
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecordV1:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM studio_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown Studio job: {job_id}")
        return _record(row)

    def list_jobs(
        self,
        *,
        states: set[OperationalState | str] | None = None,
        limit: int = 100,
    ) -> list[JobRecordV1]:
        if limit < 1:
            raise ValueError("limit must be positive")
        params: list[Any] = []
        where = ""
        if states:
            values = sorted(OperationalState(item).value for item in states)
            where = f"WHERE state IN ({','.join('?' for _ in values)})"
            params.extend(values)
        params.append(int(limit))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM studio_jobs {where} ORDER BY created_at DESC, rowid DESC LIMIT ?",  # noqa: S608
                params,
            ).fetchall()
        return [_record(row) for row in rows]

    def claim_next(
        self,
        *,
        worker_id: str,
        observed_hashes: HashObserver | None,
    ) -> JobRecordV1 | None:
        """Claim the oldest safe job, blocking drifted jobs before reservation."""

        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id is required")
        while True:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                active = connection.execute(
                    "SELECT job_id FROM studio_jobs WHERE state IN (?, ?) LIMIT 1",
                    (OperationalState.RUNNING.value, OperationalState.CANCEL_REQUESTED.value),
                ).fetchone()
                if active is not None:
                    connection.commit()
                    return None
                row = connection.execute(
                    "SELECT * FROM studio_jobs WHERE state = ? ORDER BY created_at, rowid LIMIT 1",
                    (OperationalState.QUEUED.value,),
                ).fetchone()
                if row is None:
                    connection.commit()
                    return None
                pending = _record(row)
                mismatch = _hash_lock_mismatch(pending, observed_hashes)
                now = _now_iso()
                if mismatch:
                    connection.execute(
                        """
                        UPDATE studio_jobs
                        SET state = ?, blocked_reason = ?, updated_at = ?, finished_at = ?
                        WHERE job_id = ? AND state = ?
                        """,
                        (
                            OperationalState.BLOCKED.value,
                            mismatch,
                            now,
                            now,
                            pending.job_id,
                            OperationalState.QUEUED.value,
                        ),
                    )
                    connection.commit()
                    continue
                changed = connection.execute(
                    """
                    UPDATE studio_jobs
                    SET state = ?, worker_id = ?, started_at = ?, heartbeat_at = ?, updated_at = ?
                    WHERE job_id = ? AND state = ?
                    """,
                    (
                        OperationalState.RUNNING.value,
                        worker,
                        now,
                        now,
                        now,
                        pending.job_id,
                        OperationalState.QUEUED.value,
                    ),
                ).rowcount
                connection.commit()
                if changed:
                    return self.get(pending.job_id)

    def request_cancel(self, job_id: str) -> JobRecordV1:
        """Cancel queued work immediately or ask a running worker to stop safely."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM studio_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Studio job: {job_id}")
            record = _record(row)
            now = _now_iso()
            if record.state in TERMINAL_STATES:
                connection.commit()
                return record
            if record.state == OperationalState.QUEUED:
                connection.execute(
                    """
                    UPDATE studio_jobs
                    SET state = ?, cancellation_requested_at = ?, finished_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (OperationalState.CANCELLED.value, now, now, now, job_id),
                )
            elif record.state == OperationalState.RUNNING:
                connection.execute(
                    """
                    UPDATE studio_jobs
                    SET state = ?, cancellation_requested_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (OperationalState.CANCEL_REQUESTED.value, now, now, job_id),
                )
            connection.commit()
        return self.get(job_id)

    def cancellation_requested(self, job_id: str) -> bool:
        return self.get(job_id).state == OperationalState.CANCEL_REQUESTED

    def heartbeat(self, job_id: str, *, worker_id: str) -> JobRecordV1:
        now = _now_iso()
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE studio_jobs SET heartbeat_at = ?, updated_at = ?
                WHERE job_id = ? AND worker_id = ? AND state IN (?, ?)
                """,
                (
                    now,
                    now,
                    job_id,
                    worker_id,
                    OperationalState.RUNNING.value,
                    OperationalState.CANCEL_REQUESTED.value,
                ),
            ).rowcount
        if not changed:
            raise InvalidJobTransitionError("heartbeat requires ownership of an active job")
        return self.get(job_id)

    def mark_attempt_reserved(self, job_id: str, *, worker_id: str) -> JobRecordV1:
        """Record the irreversible evidence-reservation boundary exactly once."""

        now = _now_iso()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM studio_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Studio job: {job_id}")
            record = _record(row)
            if record.worker_id != worker_id or record.state != OperationalState.RUNNING:
                if record.state == OperationalState.CANCEL_REQUESTED:
                    raise JobCancellationRequested("cancellation was requested before evidence reservation")
                raise InvalidJobTransitionError("attempt reservation requires ownership of a running job")
            if not record.attempt_reserved:
                connection.execute(
                    "UPDATE studio_jobs SET attempt_reserved = 1, heartbeat_at = ?, updated_at = ? WHERE job_id = ?",
                    (now, now, job_id),
                )
            connection.commit()
        return self.get(job_id)

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        result: Mapping[str, Any] | None = None,
        research_verdict: str | None = None,
    ) -> JobRecordV1:
        normalized_result = _json_mapping(result or {}, label="result")
        verdict = _verdict_or_none(research_verdict)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM studio_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Studio job: {job_id}")
            record = _record(row)
            if record.worker_id != worker_id:
                raise InvalidJobTransitionError("only the owning worker can complete a job")
            if record.state == OperationalState.CANCEL_REQUESTED:
                connection.commit()
                return self._finish_cancelled(job_id, worker_id=worker_id, result=normalized_result)
            if record.state != OperationalState.RUNNING:
                raise InvalidJobTransitionError("completion requires a running job")
            now = _now_iso()
            connection.execute(
                """
                UPDATE studio_jobs
                SET state = ?, result_json = ?, research_verdict = ?, finished_at = ?,
                    heartbeat_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    OperationalState.SUCCEEDED.value,
                    _canonical_json(normalized_result),
                    verdict,
                    now,
                    now,
                    now,
                    job_id,
                ),
            )
            connection.commit()
        return self.get(job_id)

    def fail(self, job_id: str, *, worker_id: str, error: str) -> JobRecordV1:
        message = str(error).strip() or "unspecified operational failure"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM studio_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Studio job: {job_id}")
            record = _record(row)
            if record.worker_id != worker_id or record.state not in ACTIVE_STATES:
                raise InvalidJobTransitionError("only the owning worker can fail an active job")
            now = _now_iso()
            verdict = "NEEDS MANUAL REVIEW" if record.attempt_reserved else None
            connection.execute(
                """
                UPDATE studio_jobs
                SET state = ?, error = ?, research_verdict = ?, finished_at = ?,
                    heartbeat_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    OperationalState.FAILED_OPERATIONAL.value,
                    message,
                    verdict,
                    now,
                    now,
                    now,
                    job_id,
                ),
            )
            connection.commit()
        return self.get(job_id)

    def run_once(
        self,
        *,
        worker_id: str,
        executor: JobExecutor,
        observed_hashes: HashObserver | None,
    ) -> JobRecordV1 | None:
        """Claim and execute one job; failures are terminal and never replayed."""

        job = self.claim_next(worker_id=worker_id, observed_hashes=observed_hashes)
        if job is None:
            return None
        context = JobExecutionContext(queue=self, job_id=job.job_id, worker_id=worker_id)
        try:
            context.raise_if_cancelled()
            result = executor(context, job) or {}
            context.raise_if_cancelled()
            verdict = result.get("research_verdict") if isinstance(result, dict) else None
            return self.complete(
                job.job_id,
                worker_id=worker_id,
                result=result,
                research_verdict=verdict,
            )
        except JobCancellationRequested as exc:
            return self._finish_cancelled(
                job.job_id,
                worker_id=worker_id,
                result={"cancellation_reason": str(exc)},
            )
        except Exception as exc:  # worker boundary must persist failure before returning
            return self.fail(job.job_id, worker_id=worker_id, error=f"{type(exc).__name__}: {exc}")

    def recover_orphaned_jobs(self, *, stale_after: timedelta) -> list[JobRecordV1]:
        """Fail stale active jobs explicitly; never put them back on the queue."""

        if stale_after.total_seconds() <= 0:
            raise ValueError("stale_after must be positive")
        cutoff = (datetime.now(UTC) - stale_after).isoformat()
        recovered: list[str] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT * FROM studio_jobs
                WHERE state IN (?, ?) AND COALESCE(heartbeat_at, started_at, updated_at) < ?
                """,
                (OperationalState.RUNNING.value, OperationalState.CANCEL_REQUESTED.value, cutoff),
            ).fetchall()
            now = _now_iso()
            for row in rows:
                record = _record(row)
                verdict = "NEEDS MANUAL REVIEW" if record.attempt_reserved else None
                cancellation = record.state == OperationalState.CANCEL_REQUESTED
                target_state = OperationalState.CANCELLED if cancellation else OperationalState.FAILED_OPERATIONAL
                error = None if cancellation else "worker heartbeat expired; automatic replay is forbidden"
                result = (
                    _canonical_json({"cancellation_reason": "worker heartbeat expired after cancellation request"})
                    if cancellation
                    else None
                )
                connection.execute(
                    """
                    UPDATE studio_jobs
                    SET state = ?, error = ?, result_json = ?, research_verdict = ?, finished_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (
                        target_state.value,
                        error,
                        result,
                        verdict,
                        now,
                        now,
                        record.job_id,
                    ),
                )
                recovered.append(record.job_id)
            connection.commit()
        return [self.get(job_id) for job_id in recovered]

    def _finish_cancelled(
        self,
        job_id: str,
        *,
        worker_id: str,
        result: Mapping[str, Any] | None = None,
    ) -> JobRecordV1:
        normalized_result = _json_mapping(result or {}, label="result")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM studio_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown Studio job: {job_id}")
            record = _record(row)
            if record.worker_id != worker_id or record.state not in ACTIVE_STATES:
                raise InvalidJobTransitionError("only the owning worker can finish cancellation")
            now = _now_iso()
            verdict = "NEEDS MANUAL REVIEW" if record.attempt_reserved else None
            connection.execute(
                """
                UPDATE studio_jobs
                SET state = ?, result_json = ?, research_verdict = ?, finished_at = ?,
                    heartbeat_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    OperationalState.CANCELLED.value,
                    _canonical_json(normalized_result),
                    verdict,
                    now,
                    now,
                    now,
                    job_id,
                ),
            )
            connection.commit()
        return self.get(job_id)

    def _initialize(self) -> None:
        with self._connect() as connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current not in {0, DATABASE_SCHEMA_VERSION}:
                raise RuntimeError(
                    f"Studio job database schema {current} is unsupported; expected {DATABASE_SCHEMA_VERSION}"
                )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS studio_jobs (
                    job_id TEXT PRIMARY KEY,
                    schema_name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    campaign_id TEXT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    submission_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    hash_locks_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ({','.join(repr(item.value) for item in OperationalState)})),
                    worker_id TEXT,
                    attempt_reserved INTEGER NOT NULL DEFAULT 0 CHECK (attempt_reserved IN (0, 1)),
                    research_verdict TEXT CHECK (
                        research_verdict IS NULL OR research_verdict IN ('PASS', 'FAIL', 'NEEDS MANUAL REVIEW')
                    ),
                    result_json TEXT,
                    blocked_reason TEXT,
                    error TEXT,
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
                "CREATE INDEX IF NOT EXISTS studio_jobs_state_order ON studio_jobs(state, created_at)"
            )
            connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


class JobExecutionContext:
    """Narrow cooperative-control surface passed to a job executor."""

    def __init__(self, *, queue: SQLiteJobQueue, job_id: str, worker_id: str) -> None:
        self.queue = queue
        self.job_id = job_id
        self.worker_id = worker_id

    def reserve_attempt(self) -> JobRecordV1:
        self.raise_if_cancelled()
        return self.queue.mark_attempt_reserved(self.job_id, worker_id=self.worker_id)

    def heartbeat(self) -> JobRecordV1:
        return self.queue.heartbeat(self.job_id, worker_id=self.worker_id)

    def cancellation_requested(self) -> bool:
        return self.queue.cancellation_requested(self.job_id)

    def raise_if_cancelled(self) -> None:
        if self.cancellation_requested():
            raise JobCancellationRequested("Studio user requested cancellation")


def _hash_lock_mismatch(job: JobRecordV1, observed_hashes: HashObserver | None) -> str | None:
    if not job.hash_locks:
        return None
    if observed_hashes is None:
        return "hash verification is required before execution; attempt was not reserved"
    try:
        observed = observed_hashes(job) if callable(observed_hashes) else observed_hashes
        actual = _string_mapping(observed, label="observed_hashes")
    except Exception as exc:
        return f"hash verification failed before execution: {exc}"
    drift = [
        f"{name}: expected {expected}, observed {actual.get(name, '<missing>')}"
        for name, expected in job.hash_locks.items()
        if actual.get(name) != expected
    ]
    return "hash drift blocked execution without reserving an attempt: " + "; ".join(drift) if drift else None


def _record(row: sqlite3.Row) -> JobRecordV1:
    return JobRecordV1.model_validate(
        {
            "schema": row["schema_name"],
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "campaign_id": row["campaign_id"],
            "idempotency_key": row["idempotency_key"],
            "payload": json.loads(row["payload_json"]),
            "payload_sha256": row["payload_sha256"],
            "hash_locks": json.loads(row["hash_locks_json"]),
            "state": OperationalState(row["state"]),
            "worker_id": row["worker_id"],
            "attempt_reserved": bool(row["attempt_reserved"]),
            "research_verdict": row["research_verdict"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "blocked_reason": row["blocked_reason"],
            "error": row["error"],
            "created_at": _database_datetime(row["created_at"]),
            "updated_at": _database_datetime(row["updated_at"]),
            "started_at": _database_datetime(row["started_at"]),
            "heartbeat_at": _database_datetime(row["heartbeat_at"]),
            "cancellation_requested_at": _database_datetime(row["cancellation_requested_at"]),
            "finished_at": _database_datetime(row["finished_at"]),
        }
    )


def _database_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp persisted in Studio job database: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"naive timestamp persisted in Studio job database: {value!r}")
    return parsed


def _json_mapping(value: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    try:
        serialized = _canonical_json(dict(value))
        parsed = json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain finite JSON values: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a mapping")
    return parsed


def _string_mapping(value: Mapping[str, str], *, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    result: dict[str, str] = {}
    for raw_name, raw_hash in value.items():
        name, hash_value = str(raw_name).strip(), str(raw_hash).strip()
        if not name or not hash_value:
            raise ValueError(f"{label} keys and values must be non-empty")
        result[name] = hash_value
    return dict(sorted(result.items()))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _verdict_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    verdict = str(value).strip().upper()
    if verdict not in STRICT_VERDICTS:
        raise ValueError(f"research_verdict must be one of {sorted(STRICT_VERDICTS)}")
    return verdict


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
