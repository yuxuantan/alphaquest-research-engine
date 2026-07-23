from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest
from pydantic import ValidationError

from alphaquest.studio.jobs import (
    IdempotencyConflictError,
    JobRecordV1,
    JobCancellationRequested,
    OperationalState,
    SQLiteJobQueue,
)


def test_job_record_public_contract_rejects_type_coercion(tmp_path):
    record = SQLiteJobQueue(tmp_path / "jobs.sqlite").submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="strict-public-record",
        hash_locks={},
    )
    document = record.model_dump(mode="python", by_alias=True)
    document["attempt_reserved"] = 1

    with pytest.raises(ValidationError, match="bool_type"):
        JobRecordV1.model_validate(document)


def test_job_submission_is_idempotent_and_conflicts_fail_closed(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "runtime" / "jobs.sqlite")

    first = queue.submit(
        job_type="campaign_run",
        payload={"campaign_id": "demo"},
        idempotency_key="demo-run-1",
        hash_locks={"config": "abc"},
        campaign_id="demo",
    )
    repeated = queue.submit(
        job_type="campaign_run",
        payload={"campaign_id": "demo"},
        idempotency_key="demo-run-1",
        hash_locks={"config": "abc"},
        campaign_id="demo",
    )

    assert repeated.job_id == first.job_id
    assert repeated.state == OperationalState.QUEUED
    with pytest.raises(IdempotencyConflictError):
        queue.submit(
            job_type="campaign_run",
            payload={"campaign_id": "different"},
            idempotency_key="demo-run-1",
            hash_locks={"config": "abc"},
        )


def test_hash_drift_blocks_before_attempt_reservation(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="hash-locked",
        hash_locks={"config": "expected", "data": "data-hash"},
    )

    claimed = queue.claim_next(
        worker_id="worker-1",
        observed_hashes={"config": "changed", "data": "data-hash"},
    )
    blocked = queue.get(job.job_id)

    assert claimed is None
    assert blocked.state == OperationalState.BLOCKED
    assert blocked.attempt_reserved is False
    assert blocked.research_verdict is None
    assert "hash drift" in blocked.blocked_reason


def test_single_worker_and_queued_cancellation_are_safe(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    first = queue.submit(
        job_type="import",
        payload={},
        idempotency_key="first",
        hash_locks={},
    )
    second = queue.submit(
        job_type="import",
        payload={},
        idempotency_key="second",
        hash_locks={},
    )

    active = queue.claim_next(worker_id="worker-1", observed_hashes={})
    assert active.job_id == first.job_id
    assert queue.claim_next(worker_id="worker-2", observed_hashes={}) is None

    cancelled = queue.request_cancel(second.job_id)
    assert cancelled.state == OperationalState.CANCELLED
    assert cancelled.attempt_reserved is False
    assert cancelled.research_verdict is None


def test_equal_timestamp_bulk_jobs_claim_in_declared_insertion_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "alphaquest.studio.jobs._now_iso",
        lambda: "2026-07-15T12:00:00+00:00",
    )
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    for variant in ("v01", "v02", "v03", "v04", "v05"):
        queue.submit(
            job_type="campaign_variant_run",
            campaign_id="demo",
            payload={"variant_id": variant},
            idempotency_key=f"demo:{variant}",
            hash_locks={},
        )

    claimed = []
    for _ in range(5):
        job = queue.claim_next(worker_id="worker-1", observed_hashes={})
        assert job is not None
        claimed.append(job.payload["variant_id"])
        queue.complete(job.job_id, worker_id="worker-1", result={})

    assert claimed == ["v01", "v02", "v03", "v04", "v05"]


def test_worker_failure_after_reservation_needs_manual_review_and_never_replays(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    submitted = queue.submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="crash-after-reserve",
        hash_locks={"config": "locked"},
    )

    def executor(context, _job):
        context.reserve_attempt()
        raise RuntimeError("simulated worker crash")

    failed = queue.run_once(
        worker_id="worker-1",
        executor=executor,
        observed_hashes={"config": "locked"},
    )

    assert failed.job_id == submitted.job_id
    assert failed.state == OperationalState.FAILED_OPERATIONAL
    assert failed.attempt_reserved is True
    assert failed.research_verdict == "NEEDS MANUAL REVIEW"
    assert "simulated worker crash" in failed.error
    assert queue.run_once(worker_id="worker-1", executor=executor, observed_hashes={"config": "locked"}) is None


def test_cooperative_cancellation_after_reservation_preserves_manual_review_verdict(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    queue.submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="cancel-after-reserve",
        hash_locks={},
    )

    def executor(context, _job):
        context.reserve_attempt()
        queue.request_cancel(context.job_id)
        context.raise_if_cancelled()

    cancelled = queue.run_once(worker_id="worker-1", executor=executor, observed_hashes={})

    assert cancelled.state == OperationalState.CANCELLED
    assert cancelled.attempt_reserved is True
    assert cancelled.research_verdict == "NEEDS MANUAL REVIEW"


def test_reservation_refuses_a_preexisting_cancel_request(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="cancel-before-reserve",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})
    queue.request_cancel(job.job_id)

    with pytest.raises(JobCancellationRequested):
        queue.mark_attempt_reserved(job.job_id, worker_id="worker-1")


def test_stale_worker_recovery_is_terminal_not_a_requeue(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="orphan",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})

    recovered = queue.recover_orphaned_jobs(stale_after=timedelta(microseconds=1))

    assert [item.job_id for item in recovered] == [job.job_id]
    assert recovered[0].state == OperationalState.FAILED_OPERATIONAL
    assert recovered[0].attempt_reserved is False
    assert queue.claim_next(worker_id="worker-2", observed_hashes={}) is None


def test_stale_cancel_request_finishes_cancelled_without_replay(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="campaign_run",
        payload={},
        idempotency_key="orphan-cancel",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})
    queue.request_cancel(job.job_id)

    recovered = queue.recover_orphaned_jobs(stale_after=timedelta(microseconds=1))

    assert recovered[0].state == OperationalState.CANCELLED
    assert recovered[0].research_verdict is None
    assert "cancellation_reason" in recovered[0].result


def test_job_progress_is_durable_monotonic_and_separate_from_heartbeat(tmp_path):
    database = tmp_path / "jobs.sqlite"
    queue = SQLiteJobQueue(database)
    job = queue.submit(
        job_type="mechanics_validation_run",
        payload={},
        idempotency_key="progress",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})

    updated = queue.update_progress(
        job.job_id,
        worker_id="worker-1",
        phase="event_replay",
        message="Replaying market sessions",
        percent=50.0,
        completed=5,
        total=10,
        unit="sessions",
    )

    assert updated.progress.phase == "event_replay"
    assert updated.progress.completed == 5
    assert updated.progress.total == 10
    assert updated.progress.percent == 50.0
    assert updated.heartbeat_at == updated.progress.updated_at
    reloaded = SQLiteJobQueue(database).get(job.job_id)
    assert reloaded.progress == updated.progress
    with pytest.raises(ValueError, match="cannot move backwards"):
        queue.update_progress(
            job.job_id,
            worker_id="worker-1",
            phase="event_replay",
            message="Replaying market sessions",
            percent=49.0,
        )


def test_version_one_job_database_migrates_without_losing_jobs(tmp_path):
    database = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE studio_jobs (
                job_id TEXT PRIMARY KEY, schema_name TEXT NOT NULL, job_type TEXT NOT NULL,
                campaign_id TEXT, idempotency_key TEXT NOT NULL UNIQUE,
                submission_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL, hash_locks_json TEXT NOT NULL,
                state TEXT NOT NULL, worker_id TEXT, attempt_reserved INTEGER NOT NULL DEFAULT 0,
                research_verdict TEXT, result_json TEXT, blocked_reason TEXT, error TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT,
                heartbeat_at TEXT, cancellation_requested_at TEXT, finished_at TEXT
            )
            """
        )
        connection.execute("PRAGMA user_version = 1")

    SQLiteJobQueue(database)

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(studio_jobs)")}
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert "progress_json" in columns
    assert version == 2
