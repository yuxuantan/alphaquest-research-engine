from __future__ import annotations

from pathlib import Path

import csv
from datetime import timedelta
import hashlib
import json
import sqlite3
import yaml

from alphaquest.research.campaign_stages import DEFAULT_STAGE_ORDER
from alphaquest.studio.finalization import FinalizationResult
from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
from alphaquest.studio.worker import (
    MECHANICS_VALIDATION_RUN,
    StudioWorker,
    _campaign_config_paths,
    run_forever,
    run_once,
)


def _workspace(tmp_path: Path) -> tuple[Path, dict]:
    campaign = tmp_path / "research/campaigns/active/demo"
    variants = [f"v{index:02d}" for index in range(1, 6)]
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "governance_contract_version": 2,
                "variants": variants,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    base = {
        "campaign_id": "demo",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "symbol": "ES",
        "dataset_id": "bars",
        "timeframe": "1m",
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "data_subset": {"start_date": "2025-01-01", "end_date": "2025-01-07"},
                "evidence_dir": str(tmp_path / "validation-evidence"),
            }
        },
        "campaign_tests": {
            "stage_order": list(DEFAULT_STAGE_ORDER),
            **{stage: {"enabled": True} for stage in DEFAULT_STAGE_ORDER},
        },
    }
    for variant in variants:
        path = campaign / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({**base, "variant_id": variant}, sort_keys=False), encoding="utf-8")
    return campaign, base


def _gate(_cfg, config_path):
    declared = ((_cfg.get("research_metadata") or {}).get("validation_gate") or {})
    return {
        "required": declared.get("required"),
        "status": "APPROVED_FOR_TESTING",
        "config_path": str(config_path),
        "config_hash": "config-locked",
        "input_data_hash": "data-locked",
        "lane": declared.get("lane"),
        "evidence_dir": declared.get("evidence_dir"),
        "approval_path": None,
        "errors": [],
    }


class _FakeFinalizer:
    def __init__(self, root: Path, verdicts: list[str] | None = None) -> None:
        self.root = root
        self.events = []
        self.verdicts = list(verdicts or ["FAIL"])

    def record_recovery_phase(self, job_id, phase, *, details=None, terminal=False):
        self.events.append((phase, terminal, details or {}))
        path = self.root / "runtime/recovery" / f"{job_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    def finalize(self, *, job_id, config_path, summary):
        self.events.append(("finalize", False, {"summary": summary}))
        verdict = self.verdicts.pop(0)
        run_dir = Path(summary["output_dir"])
        return FinalizationResult(
            job_id=job_id,
            run_dir=run_dir,
            reporting_dir=run_dir / "reporting_v2",
            result_bundle_path=run_dir / "reporting_v2/result_bundle_v2.json",
            finalization_manifest_path=run_dir / "reporting_v2/finalization_manifest.json",
            recovery_journal_path=self.root / "runtime/recovery" / f"{job_id}.json",
            research_verdict=verdict,
            ledger_appended=True,
            registry_counts={"runs": 1},
            artifact_hashes={"summary": "abc"},
        )


def _submit(
    queue: SQLiteJobQueue,
    config: Path,
    *,
    variant: str = "v01",
    job_type: str = "campaign_variant_run",
):
    return queue.submit(
        job_type=job_type,
        campaign_id="demo",
        payload={
            "campaign_id": "demo",
            "variant_id": variant,
            "config_path": str(config),
            "output_dir": str(config.parents[5] / "evidence/runs/demo" / variant / "ES/run1"),
        },
        idempotency_key=f"demo:{variant}:original:{job_type}",
        hash_locks={"config_hash": "config-locked", "input_data_hash": "data-locked"},
    )


def test_worker_resolves_all_five_configs_from_the_current_follow_up_attempt(tmp_path):
    campaign, _base = _workspace(tmp_path)
    attempt_id = "replication_20260715"
    paths = []
    hashes = {}
    for variant in (f"v{index:02d}" for index in range(1, 6)):
        source = campaign / "variants" / variant / "config.yaml"
        cfg = yaml.safe_load(source.read_text(encoding="utf-8"))
        cfg.update(
            {
                "attempt_id": attempt_id,
                "attempt_kind": "replication",
                "parent_attempt_id": "original",
                "test_run_id": f"attempt_{attempt_id}",
            }
        )
        path = campaign / "follow_up_attempts" / attempt_id / variant / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        paths.append(path.resolve())
        hashes[variant] = hashlib.sha256(path.read_bytes()).hexdigest()
    (campaign / "follow_up_attempts" / attempt_id / "attempt_manifest.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.follow-up-attempt/v1",
                "attempt_id": attempt_id,
                "config_sha256": hashes,
            }
        ),
        encoding="utf-8",
    )

    selected = paths[2]
    selected_cfg = yaml.safe_load(selected.read_text(encoding="utf-8"))

    assert _campaign_config_paths(selected, selected_cfg, project_root=tmp_path) == paths


def test_worker_preflights_then_reserves_immediately_before_existing_runner(tmp_path):
    campaign, _base = _workspace(tmp_path)
    caller_directory = Path.cwd()
    config = campaign / "variants/v01/config.yaml"
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config)
    order = []
    finalizer = _FakeFinalizer(tmp_path)

    def validate_attempt(_cfg, _path, *, out_dir):
        order.append(("attempt_contract", Path(out_dir)))
        return {"attempt_id": "original"}

    def staged_runner(_path, **kwargs):
        assert Path.cwd() == tmp_path.resolve()
        order.append(("runner", kwargs))
        assert queue.get(job.job_id).attempt_reserved is True
        return {
            "campaign_id": "demo",
            "variant_id": "v01",
            "test_run_id": "run1",
            "output_dir": str(kwargs["out_dir"]),
            "research_verdict": "FAIL",
            "stages": [],
        }

    worker = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        staged_runner=staged_runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{"status": "APPROVED_FOR_TESTING"} for _ in paths],
        attempt_validator=validate_attempt,
        finalizer=finalizer,
    )

    completed = worker.run_once()

    assert completed.state == OperationalState.SUCCEEDED
    assert Path.cwd() == caller_directory
    assert completed.attempt_reserved is True
    assert completed.research_verdict == "FAIL"
    assert order[0][0] == "attempt_contract"
    assert order[1][0] == "runner"
    assert order[1][1] == {
        "skip_validation": False,
        "continue_on_failure": False,
        "out_dir": order[0][1],
        "include_acceptance": True,
        "fast_runtime_defaults": False,
    }
    assert [event[0] for event in finalizer.events] == [
        "READY_TO_RESERVE",
        "ATTEMPT_RESERVED",
        "finalize",
    ]


def test_preflight_failure_is_manual_review_without_attempt_or_evidence(tmp_path):
    campaign, _base = _workspace(tmp_path)
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, campaign / "variants/v01/config.yaml")
    runner_called = False

    def runner(*_args, **_kwargs):
        nonlocal runner_called
        runner_called = True
        raise AssertionError("runner must not be called")

    result = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        staged_runner=runner,
        preflight_runner=lambda **_kwargs: {"passed": False, "failures": ["missing campaign governance"]},
        gate_inspector=_gate,
        finalizer=_FakeFinalizer(tmp_path),
    )

    assert result.job_id == job.job_id
    assert result.state == OperationalState.SUCCEEDED
    assert result.attempt_reserved is False
    assert result.research_verdict == "NEEDS MANUAL REVIEW"
    assert result.result["candidate_artifacts_suppressed"] is True
    assert result.result["failures"] == ["missing campaign governance"]
    assert runner_called is False


def test_missing_mandatory_stage_on_later_variant_blocks_before_attempt(tmp_path):
    campaign, _base = _workspace(tmp_path)
    later = campaign / "variants/v05/config.yaml"
    later_config = yaml.safe_load(later.read_text(encoding="utf-8"))
    later_config["campaign_tests"].pop(DEFAULT_STAGE_ORDER[-1])
    later.write_text(yaml.safe_dump(later_config, sort_keys=False), encoding="utf-8")
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, campaign / "variants/v01/config.yaml")

    completed = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{} for _ in paths],
        finalizer=_FakeFinalizer(tmp_path),
    )

    assert completed.job_id == job.job_id
    assert completed.attempt_reserved is False
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert "v05" in completed.result["reason"]
    assert "missing" in completed.result["reason"]


def test_current_approval_hash_drift_blocks_before_attempt(tmp_path):
    campaign, _base = _workspace(tmp_path)
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, campaign / "variants/v01/config.yaml")

    result = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        gate_inspector=lambda cfg, path: {
            **_gate(cfg, path),
            "config_hash": "changed-after-approval",
        },
        finalizer=_FakeFinalizer(tmp_path),
    )

    assert result is None
    blocked = queue.get(job.job_id)
    assert blocked.state == OperationalState.BLOCKED
    assert blocked.attempt_reserved is False
    assert blocked.research_verdict is None
    assert "hash drift" in blocked.blocked_reason


def test_bounded_worker_drain_runs_later_variant_after_scientific_failure(tmp_path):
    campaign, _base = _workspace(tmp_path)
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    first = _submit(queue, campaign / "variants/v01/config.yaml", variant="v01")
    second = _submit(queue, campaign / "variants/v02/config.yaml", variant="v02")
    finalizer = _FakeFinalizer(tmp_path, verdicts=["FAIL", "PASS"])

    def runner(path, **kwargs):
        variant = Path(path).parent.name
        return {
            "campaign_id": "demo",
            "variant_id": variant,
            "test_run_id": "run1",
            "output_dir": str(kwargs["out_dir"]),
            "research_verdict": "FAIL" if variant == "v01" else "PASS",
            "stages": [],
        }

    handled = run_forever(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        max_jobs=2,
        recover_stale_after=None,
        staged_runner=runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{} for _ in paths],
        attempt_validator=lambda *_args, **_kwargs: {},
        finalizer=finalizer,
    )

    assert handled == 2
    assert queue.get(first.job_id).research_verdict == "FAIL"
    assert queue.get(second.job_id).research_verdict == "PASS"
    assert queue.get(second.job_id).state == OperationalState.SUCCEEDED


def test_mechanics_validation_job_generates_review_evidence_without_reserving_attempt(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config, job_type=MECHANICS_VALIDATION_RUN)
    finalizer = _FakeFinalizer(tmp_path)
    calls = []

    def mechanics_runner(path, root):
        calls.append((path, root))
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        evidence = Path(cfg["research_metadata"]["validation_gate"]["evidence_dir"])
        evidence.mkdir(parents=True)
        (evidence / "metadata.json").write_text("{}\n", encoding="utf-8")
        return {"service": "fake-declared-bar-service", "exit_code": 0}

    completed = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        mechanics_runner=mechanics_runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        finalizer=finalizer,
    )

    assert completed.job_id == job.job_id
    assert completed.state == OperationalState.SUCCEEDED
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert completed.attempt_reserved is False
    assert completed.result["mechanics_validation_status"] == "READY_FOR_REVIEW"
    assert completed.result["candidate_artifacts_suppressed"] is True
    assert calls == [(config.resolve(), tmp_path.resolve())]
    assert [event[0] for event in finalizer.events] == [
        "MECHANICS_VALIDATION_STARTED",
        "MECHANICS_VALIDATION_READY_FOR_REVIEW",
    ]


def test_unsupported_event_mechanics_lane_is_nmr_and_never_calls_bar_runner(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg["research_metadata"]["validation_gate"]["lane"] = "event_replay"
    config.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config, job_type=MECHANICS_VALIDATION_RUN)
    runner_called = False

    def bar_runner(*_args):
        nonlocal runner_called
        runner_called = True
        raise AssertionError("unsupported event lane must never call generic bar validation")

    completed = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        mechanics_runner=bar_runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        finalizer=_FakeFinalizer(tmp_path),
    )

    assert completed.job_id == job.job_id
    assert completed.state == OperationalState.SUCCEEDED
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert completed.attempt_reserved is False
    assert completed.result["unsupported_lane"] is True
    assert completed.result["validation_lane"] == "event_replay"
    assert runner_called is False


def test_worker_failure_after_reservation_publishes_incomplete_nmr_without_replay(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config)
    output = Path(job.payload["output_dir"])

    def crashing_runner(_path, **kwargs):
        run_dir = Path(kwargs["out_dir"])
        run_dir.mkdir(parents=True)
        (run_dir / "candidate_strategy_report.md").write_text("unsafe candidate\n", encoding="utf-8")
        (run_dir / "partial_stage.txt").write_text("preserve me\n", encoding="utf-8")
        raise RuntimeError("injected runner crash")

    worker = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        staged_runner=crashing_runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{} for _ in paths],
        attempt_validator=lambda *_args, **_kwargs: {},
    )

    failed = worker.run_once()

    assert failed.state == OperationalState.FAILED_OPERATIONAL
    assert failed.attempt_reserved is True
    assert failed.research_verdict == "NEEDS MANUAL REVIEW"
    assert "injected runner crash" in failed.error
    marker = json.loads((output / "studio_incomplete_attempt.json").read_text(encoding="utf-8"))
    assert marker["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert marker["automatic_replay_permitted"] is False
    assert "explicit replication" in marker["next_action"]
    assert not (output / "candidate_strategy_report.md").exists()
    assert (output / "partial_stage.txt").read_text(encoding="utf-8") == "preserve me\n"
    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle))[-1]["stage"] == "incomplete_studio_attempt"
    assert worker.run_once() is None


def test_worker_cancellation_after_reservation_publishes_incomplete_nmr(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config)
    output = Path(job.payload["output_dir"])

    def cancelled_runner(_path, **kwargs):
        run_dir = Path(kwargs["out_dir"])
        run_dir.mkdir(parents=True)
        (run_dir / "candidate_strategy_report.md").write_text("unsafe candidate\n", encoding="utf-8")
        queue.request_cancel(job.job_id)
        return {
            "campaign_id": "demo",
            "variant_id": "v01",
            "test_run_id": "run1",
            "output_dir": str(run_dir),
            "research_verdict": "PASS",
            "stages": [],
        }

    cancelled = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        staged_runner=cancelled_runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{} for _ in paths],
        attempt_validator=lambda *_args, **_kwargs: {},
    ).run_once()

    assert cancelled.state == OperationalState.CANCELLED
    assert cancelled.attempt_reserved is True
    assert cancelled.research_verdict == "NEEDS MANUAL REVIEW"
    marker = json.loads((output / "studio_incomplete_attempt.json").read_text(encoding="utf-8"))
    assert marker["operational_state"] == "CANCELLED"
    assert marker["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert not (output / "candidate_strategy_report.md").exists()


def test_worker_startup_marks_crashed_reserved_attempt_incomplete_without_replay(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    database = tmp_path / "runtime/jobs.sqlite3"
    queue = SQLiteJobQueue(database)
    job = _submit(queue, config)
    claimed = queue.claim_next(
        worker_id="dead-worker",
        observed_hashes={"config_hash": "config-locked", "input_data_hash": "data-locked"},
    )
    assert claimed is not None
    queue.mark_attempt_reserved(job.job_id, worker_id="dead-worker")
    output = Path(job.payload["output_dir"])
    output.mkdir(parents=True)
    (output / "candidate_strategy_report.md").write_text("unsafe candidate\n", encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE studio_jobs SET heartbeat_at = ?, updated_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00", job.job_id),
        )

    handled = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="replacement-worker",
    ).run_forever(
        poll_interval=0,
        max_jobs=1,
        recover_stale_after=timedelta(seconds=1),
    )

    recovered = queue.get(job.job_id)
    assert handled == 0
    assert recovered.state == OperationalState.FAILED_OPERATIONAL
    assert recovered.research_verdict == "NEEDS MANUAL REVIEW"
    assert "automatic replay is forbidden" in recovered.error
    marker = json.loads((output / "studio_incomplete_attempt.json").read_text(encoding="utf-8"))
    assert marker["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert marker["automatic_replay_permitted"] is False
    assert not (output / "candidate_strategy_report.md").exists()
