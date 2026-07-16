from __future__ import annotations

from datetime import timedelta

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
