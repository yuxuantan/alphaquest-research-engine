from __future__ import annotations

from pathlib import Path

import csv
from datetime import timedelta
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace
import pandas as pd
import pytest
import yaml

from alphaquest.research.campaign_stages import (
    DEFAULT_STAGE_ORDER,
    canonicalize_campaign_config,
)
from alphaquest.research.experiment_registry import AttemptStatusTransition, ExperimentRegistry
from alphaquest.studio.finalization import FinalizationResult
from alphaquest.studio.jobs import JobCancellationRequested, OperationalState, SQLiteJobQueue
from alphaquest.studio.process_ownership import process_group_members, process_registry_root
from alphaquest.studio.worker import (
    MECHANICS_VALIDATION_RUN,
    StudioWorker,
    _campaign_config_paths,
    _persist_campaign_progress,
    _run_declared_campaign_variant,
    _run_declared_bar_mechanics_validation,
    run_forever,
    run_once,
)


def test_campaign_stage_progress_maps_into_reserved_runner_range():
    updates = []

    class Context:
        def report_progress(self, **kwargs):
            updates.append(kwargs)

    _persist_campaign_progress(
        Context(),
        {
            "phase": "walk_forward_analysis",
            "message": "Walk Forward Analysis (stage 3 of 8): walk-forward windows",
            "percent": 50.0,
            "completed": 4,
            "total": 8,
            "unit": "walk-forward windows",
            "stage_index": 3,
            "stage_total": 8,
        },
    )

    assert updates == [
        {
            "phase": "walk_forward_analysis",
            "message": "Walk Forward Analysis (stage 3 of 8): walk-forward windows",
            "percent": 36.5625,
            "completed": 4,
            "total": 8,
            "unit": "walk-forward windows",
        }
    ]


def test_owned_campaign_subprocess_cancellation_kills_real_descendants(tmp_path):
    marker = tmp_path / "owned-process.json"
    script = f"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path({str(marker)!r}).write_text(
    json.dumps({{"leader_pid": os.getpid(), "child_pid": child.pid, "pgid": os.getpgrp()}}),
    encoding="utf-8",
)
time.sleep(60)
"""
    started = time.monotonic()

    with pytest.raises(JobCancellationRequested, match="Studio user requested"):
        _run_declared_campaign_variant(
            tmp_path / "config.yaml",
            tmp_path,
            output_dir=tmp_path / "evidence",
            job_id="owned-cancellation-test",
            authoritative_parallel_workers=3,
            cancellation_requested=marker.is_file,
            _command_override=[sys.executable, "-c", script],
        )

    assert time.monotonic() - started < 5.0
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert process_group_members(int(payload["pgid"])) == []
    assert list(process_registry_root(tmp_path).glob("*.json")) == []
    for pid in (payload["leader_pid"], payload["child_pid"]):
        output = subprocess.run(
            ["ps", "-p", str(pid), "-o", "state="],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert not output or output.startswith("Z")


def test_declared_mechanics_runner_streams_structured_progress(monkeypatch, tmp_path):
    class FakeProcess:
        stdout = iter(
            [
                'ALPHAQUEST_PROGRESS {"phase":"event_replay","message":"Replaying market sessions",'
                '"percent":50.0,"completed":5,"total":10,"unit":"sessions"}\n',
                "/tmp/generated/core\n",
            ]
        )
        stderr = iter(())

        @staticmethod
        def wait(timeout=None):
            return 0

    monkeypatch.setattr("alphaquest.studio.worker.subprocess.Popen", lambda *_args, **_kwargs: FakeProcess())
    updates = []

    result = _run_declared_bar_mechanics_validation(
        tmp_path / "config.yaml",
        tmp_path,
        progress_callback=updates.append,
    )

    assert updates == [
        {
            "phase": "event_replay",
            "message": "Replaying market sessions",
            "percent": 50.0,
            "completed": 5,
            "total": 10,
            "unit": "sessions",
        }
    ]
    assert result["source_run_dir"] == "/tmp/generated/core"


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
                "economic_edge_fingerprint": {
                    "market_behavior": "intraday continuation",
                    "causal_mechanism": "persistent order flow",
                    "signal_inputs": ["completed bars"],
                    "market_context": "regular trading hours",
                    "holding_period": "intraday",
                },
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
        "research_objectives": {
            "schema": "alphaquest.research-objectives/v1",
            "development_goal": "Determine whether the candidate has robust unseen performance.",
            "development_deadline": "2027-12-31",
            "evaluation_horizon_months": 24,
            "minimum_annualized_return_fraction": 0.2,
            "minimum_mar": 0.4,
            "maximum_drawdown_fraction": 0.1,
            "minimum_complete_wfa_windows": 3,
            "minimum_wfa_oos_trades": 50,
            "minimum_acceptance_oos_trades": 30,
            "monte_carlo_min_runs": 8000,
            "monte_carlo_horizon_months": 6,
            "minimum_net_profit_probability": 0.7,
            "maximum_account_breach_probability": 0.1,
            "forward_incubation_min_calendar_days": 90,
            "forward_incubation_min_trades": 30,
            "maximum_variants": 5,
            "abandonment_rules": ["Stop after the frozen variant budget is exhausted."],
            "retirement_rules": ["Retire after a predeclared live-risk threshold is breached."],
            "confirmed": True,
        },
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
        "core_grid": {"parameters": {}},
    }
    base = canonicalize_campaign_config(base)
    for variant in variants:
        path = campaign / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({**base, "variant_id": variant}, sort_keys=False), encoding="utf-8")
    return campaign, base


def _gate(_cfg, config_path):
    declared = (_cfg.get("research_metadata") or {}).get("validation_gate") or {}
    return {
        "required": declared.get("required"),
        "status": "APPROVED_FOR_TESTING",
        "config_path": str(config_path),
        "config_hash": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
        "input_data_hash": "d" * 64,
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
        bundle_path = run_dir / "reporting_v2/result_bundle_v2.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(json.dumps({"verdict": verdict}) + "\n", encoding="utf-8")
        return FinalizationResult(
            job_id=job_id,
            run_dir=run_dir,
            reporting_dir=run_dir / "reporting_v2",
            result_bundle_path=bundle_path,
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
        hash_locks={
            "config_hash": hashlib.sha256(config.read_bytes()).hexdigest(),
            "input_data_hash": "d" * 64,
        },
    )


def test_worker_preflight_isolated_to_selected_variant_in_follow_up_attempt(tmp_path):
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

    assert _campaign_config_paths(selected, selected_cfg, project_root=tmp_path) == [selected]


def test_worker_reservation_binds_original_and_legacy_parent_lineage(tmp_path):
    campaign, _base = _workspace(tmp_path)
    original_path = campaign / "variants/v01/config.yaml"
    original_cfg = yaml.safe_load(original_path.read_text(encoding="utf-8"))
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    worker = StudioWorker(queue, project_root=tmp_path, worker_id="worker-1")

    original = worker._build_experiment_reservation(
        original_cfg,
        config_path=original_path,
        gate=_gate(original_cfg, original_path),
    )
    assert original.parent_attempt_id is None
    assert original.parent_recorded_in_registry is None
    assert original.parent_evidence_sha256 is None

    child_cfg = {
        **original_cfg,
        "attempt_id": "replication_20260814",
        "attempt_kind": "replication",
        "parent_attempt_id": "original",
    }
    attempt_root = campaign / "follow_up_attempts/replication_20260814"
    child_path = attempt_root / "v01/config.yaml"
    child_path.parent.mkdir(parents=True)
    child_path.write_text(yaml.safe_dump(child_cfg, sort_keys=False), encoding="utf-8")
    (attempt_root / "attempt_manifest.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.follow-up-attempt/v1",
                "attempt_id": "replication_20260814",
                "config_sha256": {
                    "v01": hashlib.sha256(child_path.read_bytes()).hexdigest(),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    child = worker._build_experiment_reservation(
        child_cfg,
        config_path=child_path,
        gate=_gate(child_cfg, child_path),
    )
    assert child.parent_attempt_id == "original"
    assert child.parent_recorded_in_registry is False
    assert child.parent_evidence_sha256 is not None
    assert len(child.parent_evidence_sha256) == 64

    worker.experiment_registry.reserve(original)
    registered_parent_child = worker._build_experiment_reservation(
        child_cfg,
        config_path=child_path,
        gate=_gate(child_cfg, child_path),
    )
    assert registered_parent_child.parent_recorded_in_registry is True
    assert registered_parent_child.parent_evidence_sha256 is None


def test_worker_preflights_then_reserves_immediately_before_existing_runner(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("alphaquest.studio.worker.os.cpu_count", lambda: 8)
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
    assert completed.result["experiment_registry"]["economic_edge_trial_count"] == 1
    assert order[0][0] == "attempt_contract"
    assert order[1][0] == "runner"
    assert order[1][1] == {
        "skip_validation": False,
        "continue_on_failure": False,
        "out_dir": order[0][1],
        "include_acceptance": True,
        "fast_runtime_defaults": False,
        "authoritative_parallel_workers": 3,
        "authoritative_core_grid_workers": 6,
    }
    assert [event[0] for event in finalizer.events] == [
        "READY_TO_RESERVE",
        "ATTEMPT_RESERVED",
        "finalize",
    ]
    registry = ExperimentRegistry(
        tmp_path / "research_artifacts/governance/experiment_registry.jsonl"
    )
    registered = registry.attempts()[0]
    assert registered["current_status"] == "COMPLETED"
    assert registered["resolution"]["research_verdict"] == "FAIL"
    assert registered["resolution"]["result_sha256"] == hashlib.sha256(
        (order[0][1] / "reporting_v2/result_bundle_v2.json").read_bytes()
    ).hexdigest()


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


def test_worker_rejects_legacy_config_without_frozen_objectives_before_registry_or_pnl(
    tmp_path,
):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg.pop("research_objectives", None)
    cfg.pop("research_objectives_sha256", None)
    config.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config)
    runner_called = False

    def runner(*_args, **_kwargs):
        nonlocal runner_called
        runner_called = True
        raise AssertionError("legacy objective-less config must not enter PnL")

    completed = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        staged_runner=runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{} for _ in paths],
        attempt_validator=lambda *_args, **_kwargs: {},
        finalizer=_FakeFinalizer(tmp_path),
    ).run_once()

    assert completed.job_id == job.job_id
    assert completed.state == OperationalState.SUCCEEDED
    assert completed.attempt_reserved is False
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert "cannot be retrofitted after PnL" in completed.result["reason"]
    assert runner_called is False
    assert not (
        tmp_path / "research_artifacts/governance/experiment_registry.jsonl"
    ).exists()


def test_missing_mandatory_stage_on_sibling_does_not_block_selected_variant(tmp_path):
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
    assert completed.attempt_reserved is True
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert "v05" not in str(completed.result)


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


def test_worker_observes_hashes_from_explicit_project_root(tmp_path, monkeypatch):
    campaign, _base = _workspace(tmp_path)
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(
        queue,
        campaign / "variants/v01/config.yaml",
        job_type=MECHANICS_VALIDATION_RUN,
    )
    observed_working_directories = []

    def gate(cfg, path):
        observed_working_directories.append(Path.cwd())
        return _gate(cfg, path)

    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    worker = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        gate_inspector=gate,
        finalizer=_FakeFinalizer(tmp_path),
    )

    assert worker._observed_hashes(job)["input_data_hash"] == "d" * 64
    assert observed_working_directories == [tmp_path.resolve()]
    assert Path.cwd() == outside


def test_worker_observes_complete_campaign_identity_locks(tmp_path):
    campaign, _base = _workspace(tmp_path)
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, campaign / "variants/v01/config.yaml")
    approval_path = tmp_path / "approval.json"
    approval_path.write_text('{"status":"approved_for_testing"}\n', encoding="utf-8")

    def gate(cfg, path):
        return {
            **_gate(cfg, path),
            "approval_path": str(approval_path),
            "strategy_implementation_sha256": "a" * 64,
            "strategy_certification_manifest_sha256": "b" * 64,
        }

    worker = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        gate_inspector=gate,
        finalizer=_FakeFinalizer(tmp_path),
    )

    observed = worker._observed_hashes(job)
    assert observed["mechanics_approval_sha256"] == hashlib.sha256(
        approval_path.read_bytes()
    ).hexdigest()
    assert observed["strategy_implementation_sha256"] == "a" * 64
    assert observed["strategy_certification_manifest_sha256"] == "b" * 64


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
    preflight_paths = []

    def mechanics_runner(path, root):
        calls.append((path, root))
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        evidence = Path(cfg["research_metadata"]["validation_gate"]["evidence_dir"])
        evidence.mkdir(parents=True)
        (evidence / "metadata.json").write_text("{}\n", encoding="utf-8")
        return {"service": "fake-declared-bar-service", "exit_code": 0}

    def preflight_runner(**kwargs):
        preflight_paths.extend(kwargs["config_paths"])
        return {"passed": True, "failures": []}

    completed = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        mechanics_runner=mechanics_runner,
        preflight_runner=preflight_runner,
        gate_inspector=_gate,
        finalizer=finalizer,
    )

    assert completed.job_id == job.job_id
    assert completed.state == OperationalState.SUCCEEDED
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert completed.attempt_reserved is False
    assert completed.result["mechanics_validation_status"] == "READY_FOR_REVIEW"
    assert completed.result["candidate_artifacts_suppressed"] is True
    assert completed.progress.phase == "ready_for_review"
    assert completed.progress.message == "Ready for mechanics review"
    assert completed.progress.percent == 100.0
    assert calls == [(config.resolve(), tmp_path.resolve())]
    assert preflight_paths == [config.resolve()]
    assert [event[0] for event in finalizer.events] == [
        "MECHANICS_VALIDATION_STARTED",
        "MECHANICS_VALIDATION_READY_FOR_REVIEW",
    ]


def test_certified_event_mechanics_lane_runs_generic_validation_service(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg["research_metadata"]["validation_gate"]["lane"] = "event_replay"
    cfg["engine_lane"] = "canonical_event_replay"
    config.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config, job_type=MECHANICS_VALIDATION_RUN)
    runner_called = False

    def event_runner(*_args):
        nonlocal runner_called
        runner_called = True
        (tmp_path / "validation-evidence").mkdir(parents=True)
        return {"service": "test-certified-event-runner"}

    completed = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        mechanics_runner=event_runner,
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        finalizer=_FakeFinalizer(tmp_path),
    )

    assert completed.job_id == job.job_id
    assert completed.state == OperationalState.SUCCEEDED
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert completed.attempt_reserved is False
    assert completed.result["validation_lane"] == "event_replay"
    assert completed.result["mechanics_validation_status"] == "READY_FOR_REVIEW"
    assert runner_called is True


def test_mechanics_validation_job_blocks_review_when_automated_checks_error(
    tmp_path,
):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(
        queue,
        config,
        job_type=MECHANICS_VALIDATION_RUN,
    )
    finalizer = _FakeFinalizer(tmp_path)

    def mechanics_runner(_path, _root):
        evidence = tmp_path / "validation-evidence"
        evidence.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "check_id": "identity.trade_count.1",
                    "check_name": (
                        "mechanics_review_trade_sample_present"
                    ),
                    "category": "identity",
                    "status": "ERROR",
                    "severity": "ERROR",
                    "description": "Too few completed trades.",
                    "trade_id": None,
                    "expected": "at least 5 completed trades",
                    "actual": "0",
                    "details": None,
                }
            ]
        ).to_parquet(
            evidence / "validation_checks.parquet",
            index=False,
        )
        return {"service": "test-certified-event-runner"}

    completed = run_once(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        mechanics_runner=mechanics_runner,
        preflight_runner=lambda **_kwargs: {
            "passed": True,
            "failures": [],
        },
        gate_inspector=_gate,
        finalizer=finalizer,
    )

    assert completed.job_id == job.job_id
    assert completed.state == OperationalState.SUCCEEDED
    assert completed.research_verdict == "NEEDS MANUAL REVIEW"
    assert (
        completed.result["mechanics_validation_status"]
        == "EVIDENCE_BLOCKED"
    )
    assert completed.result["blocking_checks"] == [
        "mechanics_review_trade_sample_present"
    ]
    assert completed.progress.phase == "evidence_blocked"
    assert [event[0] for event in finalizer.events] == [
        "MECHANICS_VALIDATION_STARTED",
        "MECHANICS_VALIDATION_EVIDENCE_BLOCKED",
    ]


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
    registered = ExperimentRegistry(
        tmp_path / "research_artifacts/governance/experiment_registry.jsonl"
    ).attempts()[0]
    assert registered["current_status"] == "FAILED"
    assert registered["resolution"]["research_verdict"] == "NEEDS MANUAL REVIEW"
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
    registered = ExperimentRegistry(
        tmp_path / "research_artifacts/governance/experiment_registry.jsonl"
    ).attempts()[0]
    assert registered["current_status"] == "CANCELLED"
    assert registered["resolution"]["research_verdict"] == "NEEDS MANUAL REVIEW"


def test_queue_reservation_failure_after_registry_reservation_is_durably_closed(
    tmp_path,
    monkeypatch,
):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    queue = SQLiteJobQueue(tmp_path / "runtime/jobs.sqlite3")
    job = _submit(queue, config)
    output = Path(job.payload["output_dir"])

    def fail_queue_reservation(*_args, **_kwargs):
        raise RuntimeError("injected queue reservation failure")

    monkeypatch.setattr(queue, "mark_attempt_reserved", fail_queue_reservation)
    failed = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="worker-1",
        staged_runner=lambda *_args, **_kwargs: pytest.fail("runner must not start"),
        preflight_runner=lambda **_kwargs: {"passed": True, "failures": []},
        gate_inspector=_gate,
        campaign_approval_checker=lambda paths: [{} for _ in paths],
        attempt_validator=lambda *_args, **_kwargs: {},
    ).run_once()

    assert failed.state == OperationalState.FAILED_OPERATIONAL
    assert failed.attempt_reserved is False
    marker = json.loads((output / "studio_incomplete_attempt.json").read_text(encoding="utf-8"))
    assert marker["research_verdict"] == "NEEDS MANUAL REVIEW"
    registered = ExperimentRegistry(
        tmp_path / "research_artifacts/governance/experiment_registry.jsonl"
    ).attempts()[0]
    assert registered["current_status"] == "FAILED"
    assert registered["resolution"]["research_verdict"] == "NEEDS MANUAL REVIEW"


def test_stale_recovery_preserves_hash_valid_finalized_result_as_completed(
    tmp_path,
    monkeypatch,
):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    database = tmp_path / "runtime/jobs.sqlite3"
    queue = SQLiteJobQueue(database)
    job = _submit(queue, config)
    claimed = queue.claim_next(
        worker_id="dead-worker",
        observed_hashes={
            "config_hash": hashlib.sha256(config.read_bytes()).hexdigest(),
            "input_data_hash": "d" * 64,
        },
    )
    assert claimed is not None
    queue.mark_attempt_reserved(job.job_id, worker_id="dead-worker")

    worker = StudioWorker(queue, project_root=tmp_path, worker_id="replacement-worker")
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    reservation = worker._build_experiment_reservation(
        cfg,
        config_path=config,
        gate=_gate(cfg, config),
    )
    worker.experiment_registry.reserve(reservation)
    worker.experiment_registry.transition(
        AttemptStatusTransition(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="original",
            from_status="RESERVED",
            to_status="RUNNING",
            recorded_at="2026-08-14T08:01:00+00:00",
            reason="Runner accepted ownership before the worker crashed.",
        )
    )
    output = Path(job.payload["output_dir"])
    result_path = output / "reporting_v2/result_bundle_v2.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text('{"verdict":"FAIL"}\n', encoding="utf-8")
    monkeypatch.setattr(
        "alphaquest.studio.worker.inspect_finalized_result",
        lambda *_args, **_kwargs: {
            "valid": True,
            "bundle": SimpleNamespace(verdict="FAIL"),
        },
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE studio_jobs SET heartbeat_at = ?, updated_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00", job.job_id),
        )

    worker.run_forever(
        poll_interval=0,
        max_jobs=1,
        recover_stale_after=timedelta(seconds=1),
    )

    registered = worker.experiment_registry.attempts()[0]
    assert registered["current_status"] == "COMPLETED"
    assert registered["resolution"]["research_verdict"] == "FAIL"
    assert registered["resolution"]["result_sha256"] == hashlib.sha256(
        result_path.read_bytes()
    ).hexdigest()
    assert not (output / "studio_incomplete_attempt.json").exists()


def test_worker_startup_marks_crashed_reserved_attempt_incomplete_without_replay(tmp_path):
    campaign, _base = _workspace(tmp_path)
    config = campaign / "variants/v01/config.yaml"
    database = tmp_path / "runtime/jobs.sqlite3"
    queue = SQLiteJobQueue(database)
    job = _submit(queue, config)
    claimed = queue.claim_next(
        worker_id="dead-worker",
        observed_hashes={
            "config_hash": hashlib.sha256(config.read_bytes()).hexdigest(),
            "input_data_hash": "d" * 64,
        },
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
