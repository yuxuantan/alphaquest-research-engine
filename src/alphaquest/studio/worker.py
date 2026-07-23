"""Single-process durable worker for AlphaQuest Research Studio.

V1 accepts full ``campaign_variant_run`` jobs and pre-PnL
``mechanics_validation_run`` jobs.  The worker deliberately uses the existing
staged and declared mechanics runners; it does not implement a second simulator
or a weaker methodology.  Hash locks, current mechanics approval, full
preflight, campaign-wide approval, and the one-run-per-attempt contract are
checked before a performance job crosses the queue's irreversible reservation
marker.  Mechanics validation never crosses that marker.
"""

from __future__ import annotations

import copy
from collections import deque
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Mapping, Protocol

import yaml

from alphaquest.research.campaign_stages import (
    DEFAULT_STAGE_ORDER,
    _require_attempt_contract,
    run_campaign_stage_tests,
)
from alphaquest.research.preflight import run_preflight
from alphaquest.research.storage import resolve_campaign_context
from alphaquest.run_core import STRUCTURED_PROGRESS_PREFIX, _apply_mechanics_validation_contract
from alphaquest.studio.approvals import require_all_variant_mechanics_approved
from alphaquest.studio.finalization import FinalizationResult, RunFinalizer
from alphaquest.studio.jobs import (
    JobCancellationRequested,
    JobExecutionContext,
    JobRecordV1,
    SQLiteJobQueue,
)
from alphaquest.utils.config import variant_root
from alphaquest.validation.promotion_gate import inspect_validation_gate


CAMPAIGN_VARIANT_RUN = "campaign_variant_run"
MECHANICS_VALIDATION_RUN = "mechanics_validation_run"

_PROJECT_CWD_LOCK = threading.RLock()

StagedRunner = Callable[..., dict[str, Any]]
PreflightRunner = Callable[..., dict[str, Any]]
GateInspector = Callable[[dict[str, Any], Path], dict[str, Any]]
CampaignApprovalChecker = Callable[[list[Path]], list[dict[str, Any]]]
AttemptValidator = Callable[..., dict[str, Any]]
MechanicsRunner = Callable[[Path, Path], Mapping[str, Any]]
MechanicsProgressCallback = Callable[[Mapping[str, Any]], None]


class StopSignal(Protocol):
    def is_set(self) -> bool: ...


class StudioWorker:
    """Execute queued Studio work with one local worker identity."""

    def __init__(
        self,
        queue: SQLiteJobQueue,
        *,
        project_root: str | Path = ".",
        worker_id: str | None = None,
        staged_runner: StagedRunner = run_campaign_stage_tests,
        preflight_runner: PreflightRunner = run_preflight,
        gate_inspector: GateInspector = inspect_validation_gate,
        campaign_approval_checker: CampaignApprovalChecker = require_all_variant_mechanics_approved,
        attempt_validator: AttemptValidator = _require_attempt_contract,
        mechanics_runner: MechanicsRunner | None = None,
        finalizer: RunFinalizer | None = None,
    ) -> None:
        self.queue = queue
        self.project_root = Path(project_root).resolve()
        self.worker_id = worker_id or _default_worker_id()
        self.staged_runner = staged_runner
        self.preflight_runner = preflight_runner
        self.gate_inspector = gate_inspector
        self.campaign_approval_checker = campaign_approval_checker
        self.attempt_validator = attempt_validator
        self.mechanics_runner = mechanics_runner or _run_declared_bar_mechanics_validation
        self._mechanics_runner_reports_progress = mechanics_runner is None
        self.finalizer = finalizer or RunFinalizer(self.project_root)

    def run_once(self) -> JobRecordV1 | None:
        """Claim and execute one job; terminal jobs are never replayed."""

        return self.queue.run_once(
            worker_id=self.worker_id,
            executor=self._execute,
            observed_hashes=self._observed_hashes,
        )

    def run_forever(
        self,
        *,
        poll_interval: float = 0.5,
        stop_signal: StopSignal | Callable[[], bool] | None = None,
        max_jobs: int | None = None,
        recover_stale_after: timedelta | None = timedelta(minutes=5),
    ) -> int:
        """Poll until stopped, returning the number of terminal jobs handled.

        Stale active jobs are marked terminal on startup.  They are never put
        back on the queue, including jobs that died before attempt reservation.
        """

        if poll_interval < 0:
            raise ValueError("poll_interval must be non-negative")
        if max_jobs is not None and max_jobs < 1:
            raise ValueError("max_jobs must be positive")
        if recover_stale_after is not None:
            self._recover_orphaned_jobs(stale_after=recover_stale_after)
        handled = 0
        while not _stop_requested(stop_signal):
            record = self.run_once()
            if record is not None:
                handled += 1
                if max_jobs is not None and handled >= max_jobs:
                    return handled
                continue
            if recover_stale_after is not None:
                # A worker that starts before a crashed predecessor reaches the
                # stale threshold will eventually terminalize it.  Live staged
                # runs keep their heartbeat current via `_heartbeat_pump`.
                self._recover_orphaned_jobs(stale_after=recover_stale_after)
            if max_jobs is not None:
                # A bounded drain is also useful for launcher health checks and
                # deterministic tests; it exits when no job is immediately due.
                return handled
            if poll_interval:
                time.sleep(poll_interval)
        return handled

    def _observed_hashes(self, job: JobRecordV1) -> Mapping[str, str]:
        # Queue claiming happens before `_execute`, so bind hash observation to
        # the same explicit project root as execution.  This keeps any legacy
        # relative-path readers deterministic even when Studio was launched
        # from a different working directory.
        with _project_working_directory(self.project_root):
            return self._observed_hashes_from_project_root(job)

    def _observed_hashes_from_project_root(self, job: JobRecordV1) -> Mapping[str, str]:
        if job.job_type not in {CAMPAIGN_VARIANT_RUN, MECHANICS_VALIDATION_RUN}:
            raise ValueError(f"unsupported Studio job type: {job.job_type}")
        config_path, cfg = self._load_job_config(job)
        gate = self.gate_inspector(cfg, config_path)
        if job.job_type == CAMPAIGN_VARIANT_RUN and gate.get("status") != "APPROVED_FOR_TESTING":
            errors = "; ".join(str(item) for item in gate.get("errors") or [])
            raise ValueError(f"current mechanics approval is unresolved: {errors or gate.get('status')}")
        config_hash = str(gate.get("config_hash") or "")
        data_hash = str(gate.get("input_data_hash") or "")
        if not config_hash or not data_hash:
            raise ValueError("mechanics approval does not provide current config and input-data hashes")
        values = {
            "config_hash": config_hash,
            "config": config_hash,
            "source_config_hash": config_hash,
            "input_data_hash": data_hash,
            "data_hash": data_hash,
            "data": data_hash,
        }
        approval_path = gate.get("approval_path")
        if approval_path and Path(str(approval_path)).is_file():
            approval_hash = _file_sha256(Path(str(approval_path)))
            values["approval_hash"] = approval_hash
            values["approval_sha256"] = approval_hash
        return values

    def _execute(self, context: JobExecutionContext, job: JobRecordV1) -> dict[str, Any]:
        # The authoritative staged stack still resolves a few recorded source
        # paths relative to the process working directory. Studio's worker is
        # a separate single-worker process in V1, so bind the complete job to
        # its explicit workspace and restore the caller's directory afterward.
        with _project_working_directory(self.project_root):
            return self._execute_from_project_root(context, job)

    def _execute_from_project_root(
        self,
        context: JobExecutionContext,
        job: JobRecordV1,
    ) -> dict[str, Any]:
        if job.job_type == MECHANICS_VALIDATION_RUN:
            return self._execute_mechanics_validation(context, job)
        if job.job_type != CAMPAIGN_VARIANT_RUN:
            raise ValueError(f"unsupported Studio job type: {job.job_type}")
        config_path, cfg = self._load_job_config(job)
        context.raise_if_cancelled()

        missing_locks = sorted({"config_hash", "input_data_hash"} - set(job.hash_locks))
        if missing_locks:
            return _manual_review_without_attempt(
                f"Studio run is missing mandatory hash locks: {', '.join(missing_locks)}"
            )

        gate = self.gate_inspector(cfg, config_path)
        drift = _gate_drift(job.hash_locks, gate)
        if drift:
            return _manual_review_without_attempt(
                "hash or mechanics-approval drift was detected immediately before preflight: " + drift
            )

        approval_paths = _campaign_config_paths(config_path, cfg, project_root=self.project_root)
        preflight = self.preflight_runner(
            config_paths=approval_paths,
            run_tests=False,
            project_root=self.project_root,
        )
        if not bool(preflight.get("passed")):
            return {
                **_manual_review_without_attempt("full staged-submission preflight failed"),
                "preflight": _strict_json_mapping(preflight),
                "failures": [str(item) for item in preflight.get("failures") or []],
            }

        methodology_issues: list[str] = []
        for campaign_config_path in approval_paths:
            campaign_config = yaml.safe_load(campaign_config_path.read_text(encoding="utf-8")) or {}
            issue = _mandatory_methodology_issue(campaign_config)
            if issue:
                methodology_issues.append(f"{campaign_config_path.parent.name}: {issue}")
        if methodology_issues:
            return {
                **_manual_review_without_attempt(
                    "full mandatory methodology is not frozen for every variant: "
                    + "; ".join(methodology_issues)
                ),
                "preflight": _strict_json_mapping(preflight),
            }

        try:
            approval_reports = self.campaign_approval_checker(approval_paths)
        except Exception as exc:
            return {
                **_manual_review_without_attempt(
                    f"the current sequential variant requires mechanics approval: {exc}"
                ),
                "preflight": _strict_json_mapping(preflight),
            }

        output_dir = self._output_dir(job, cfg, config_path)
        # This repeats the runner's immutable-attempt guard before reservation.
        # The runner repeats it after reservation to catch the remaining race.
        self.attempt_validator(cfg, config_path, out_dir=output_dir)
        context.heartbeat()
        self.finalizer.record_recovery_phase(
            job.job_id,
            "READY_TO_RESERVE",
            details={
                "config_path": str(config_path),
                "output_dir": str(output_dir),
                "preflight_passed": True,
                "approved_variant_count": len(approval_reports),
            },
        )
        context.raise_if_cancelled()
        context.reserve_attempt()
        self.finalizer.record_recovery_phase(
            job.job_id,
            "ATTEMPT_RESERVED",
            details={"output_dir": str(output_dir)},
        )
        context.raise_if_cancelled()

        try:
            with _heartbeat_pump(context):
                summary = self.staged_runner(
                    config_path,
                    skip_validation=False,
                    continue_on_failure=False,
                    out_dir=output_dir,
                    include_acceptance=True,
                    fast_runtime_defaults=False,
                )
                context.raise_if_cancelled()
                finalized = self.finalizer.finalize(
                    job_id=job.job_id,
                    config_path=config_path,
                    summary=summary,
                )
            context.raise_if_cancelled()
        except BaseException as exc:
            self._abort_reserved_job(
                job,
                config_path=config_path,
                output_dir=output_dir,
                reason=f"{type(exc).__name__}: {exc}",
                cancelled=isinstance(exc, JobCancellationRequested),
            )
            raise
        return {
            **finalized.as_job_result(project_root=self.project_root),
            "preflight": _strict_json_mapping(preflight),
            "approval_count": len(approval_reports),
        }

    def _recover_orphaned_jobs(self, *, stale_after: timedelta) -> list[JobRecordV1]:
        recovered = self.queue.recover_orphaned_jobs(stale_after=stale_after)
        for job in recovered:
            if not job.attempt_reserved or job.job_type != CAMPAIGN_VARIANT_RUN:
                continue
            try:
                config_path, cfg = self._load_job_config(job)
                output_dir = self._output_dir(job, cfg, config_path)
            except Exception:
                continue
            self._abort_reserved_job(
                job,
                config_path=config_path,
                output_dir=output_dir,
                reason=job.error or "worker heartbeat expired after attempt reservation",
                cancelled=job.state.value == "CANCELLED",
            )
        return recovered

    def _abort_reserved_job(
        self,
        job: JobRecordV1,
        *,
        config_path: Path,
        output_dir: Path,
        reason: str,
        cancelled: bool,
    ) -> None:
        try:
            self.finalizer.abort_reserved_attempt(
                job_id=job.job_id,
                config_path=config_path,
                run_dir=output_dir,
                reason=reason,
                operational_state="CANCELLED" if cancelled else "FAILED_OPERATIONAL",
            )
        except Exception as exc:
            # The queue still persists the operational failure.  The recovery
            # journal records this hook failure when the concrete finalizer is
            # available, and no attempt is ever replayed automatically.
            try:
                self.finalizer.record_recovery_phase(
                    job.job_id,
                    "ATTEMPT_ABORT_HOOK_FAILED",
                    details={"error": f"{type(exc).__name__}: {exc}"},
                    terminal=True,
                )
            except Exception:
                pass

    def _execute_mechanics_validation(
        self,
        context: JobExecutionContext,
        job: JobRecordV1,
    ) -> dict[str, Any]:
        """Generate deterministic pre-PnL mechanics evidence without an attempt."""

        context.report_progress(
            phase="validating_specification",
            message="Validating frozen strategy specification",
            percent=1.0,
        )
        config_path, cfg = self._load_job_config(job)
        context.raise_if_cancelled()
        missing_locks = sorted({"config_hash", "input_data_hash"} - set(job.hash_locks))
        if missing_locks:
            return _manual_review_without_attempt(
                f"mechanics-validation job is missing hash locks: {', '.join(missing_locks)}"
            )
        gate = self.gate_inspector(cfg, config_path)
        drift = _mechanics_gate_drift(job.hash_locks, gate)
        if drift:
            return _manual_review_without_attempt(
                "mechanics-validation hash drift was detected before evidence generation: " + drift
            )
        if gate.get("required") is not True:
            return _manual_review_without_attempt(
                "mechanics validation is not declared as required by the frozen strategy specification"
            )
        lane = str(gate.get("lane") or "").strip().lower()
        if lane not in {"bar", "event_replay"}:
            return {
                **_manual_review_without_attempt(
                    "Studio mechanics validation supports only certified bar and event_replay lanes"
                ),
                "validation_lane": lane or None,
                "unsupported_lane": True,
            }
        try:
            # Validate the declared short slice and generated-validation
            # provenance contract without mutating the authored configuration.
            _apply_mechanics_validation_contract(copy.deepcopy(cfg))
        except Exception as exc:
            return _manual_review_without_attempt(f"mechanics-validation contract is invalid: {exc}")

        context.report_progress(
            phase="preflight",
            message="Running mechanics-validation preflight",
            percent=4.0,
        )
        campaign_paths = _campaign_config_paths(config_path, cfg, project_root=self.project_root)
        preflight = self.preflight_runner(
            config_paths=campaign_paths,
            run_tests=False,
            project_root=self.project_root,
        )
        if not bool(preflight.get("passed")):
            return {
                **_manual_review_without_attempt("mechanics-validation preflight failed"),
                "preflight": _strict_json_mapping(preflight),
                "failures": [str(item) for item in preflight.get("failures") or []],
            }

        self.finalizer.record_recovery_phase(
            job.job_id,
            "MECHANICS_VALIDATION_STARTED",
            details={
                "config_path": str(config_path),
                "validation_lane": lane,
                "attempt_reserved": False,
            },
        )
        context.report_progress(
            phase="starting_runner",
            message="Starting deterministic mechanics replay",
            percent=8.0,
        )

        def persist_runner_progress(payload: Mapping[str, Any]) -> None:
            context.raise_if_cancelled()
            context.report_progress(
                phase=str(payload.get("phase") or "mechanics_replay"),
                message=str(payload.get("message") or "Running mechanics replay"),
                percent=float(payload.get("percent") or 8.0),
                completed=_optional_int(payload.get("completed")),
                total=_optional_int(payload.get("total")),
                unit=str(payload.get("unit") or "").strip() or None,
            )

        with _heartbeat_pump(context):
            if self._mechanics_runner_reports_progress:
                runner_value = _run_declared_bar_mechanics_validation(
                    config_path,
                    self.project_root,
                    progress_callback=persist_runner_progress,
                )
            else:
                runner_value = self.mechanics_runner(config_path, self.project_root)
            runner_result = _strict_json_mapping(runner_value)
        context.raise_if_cancelled()
        context.report_progress(
            phase="finalizing_review_evidence",
            message="Finalizing mechanics-review evidence",
            percent=98.0,
        )
        refreshed_gate = self.gate_inspector(cfg, config_path)
        evidence_dir_value = refreshed_gate.get("evidence_dir") or gate.get("evidence_dir")
        evidence_dir = Path(str(evidence_dir_value)) if evidence_dir_value else None
        if evidence_dir is not None and not evidence_dir.is_absolute():
            evidence_dir = (self.project_root / evidence_dir).resolve()
        if evidence_dir is None or not evidence_dir.is_dir():
            raise RuntimeError(
                "declared mechanics-validation runner completed without its evidence directory"
            )
        self.finalizer.record_recovery_phase(
            job.job_id,
            "MECHANICS_VALIDATION_READY_FOR_REVIEW",
            details={
                "evidence_dir": str(evidence_dir),
                "attempt_reserved": False,
            },
            terminal=True,
        )
        context.report_progress(
            phase="ready_for_review",
            message="Ready for mechanics review",
            percent=100.0,
        )
        return {
            "research_verdict": "NEEDS MANUAL REVIEW",
            "attempt_reserved": False,
            "candidate_artifacts_suppressed": True,
            "mechanics_validation_status": "READY_FOR_REVIEW",
            "validation_lane": lane,
            "config_path": str(config_path),
            "evidence_dir": str(evidence_dir),
            "config_hash": str(refreshed_gate.get("config_hash") or gate.get("config_hash") or ""),
            "input_data_hash": str(
                refreshed_gate.get("input_data_hash") or gate.get("input_data_hash") or ""
            ),
            "preflight": _strict_json_mapping(preflight),
            "runner": runner_result,
            "next_action": "Review the sampled mechanics evidence and record approval or rejection.",
        }

    def _load_job_config(self, job: JobRecordV1) -> tuple[Path, dict[str, Any]]:
        raw = job.payload.get("config_path")
        if not raw:
            raise ValueError("campaign_variant_run payload requires config_path")
        path = Path(str(raw))
        path = path.resolve() if path.is_absolute() else (self.project_root / path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Studio campaign config does not exist: {path}")
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"could not read Studio campaign config {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Studio campaign config must be a mapping: {path}")
        campaign_id = str(value.get("campaign_id") or "")
        variant_id = str(value.get("variant_id") or "")
        if job.campaign_id and campaign_id != job.campaign_id:
            raise ValueError(
                f"job campaign_id {job.campaign_id!r} does not match config campaign_id {campaign_id!r}"
            )
        if job.payload.get("variant_id") and variant_id != str(job.payload["variant_id"]):
            raise ValueError(
                f"job variant_id {job.payload['variant_id']!r} does not match config variant_id {variant_id!r}"
            )
        if job.payload.get("attempt_id") and str(value.get("attempt_id") or "") != str(
            job.payload["attempt_id"]
        ):
            raise ValueError(
                f"job attempt_id {job.payload['attempt_id']!r} does not match config attempt_id "
                f"{value.get('attempt_id')!r}"
            )
        return path, value

    def _output_dir(self, job: JobRecordV1, cfg: dict[str, Any], config_path: Path) -> Path:
        declared = job.payload.get("output_dir")
        if declared:
            path = Path(str(declared))
            return path.resolve() if path.is_absolute() else (self.project_root / path).resolve()
        derived = variant_root(cfg, config_path=config_path)
        return derived.resolve() if derived.is_absolute() else (self.project_root / derived).resolve()


def run_once(
    queue: SQLiteJobQueue | str | Path,
    *,
    project_root: str | Path = ".",
    worker_id: str | None = None,
    **worker_kwargs: Any,
) -> JobRecordV1 | None:
    """Public convenience API for one durable worker iteration."""

    resolved_queue = queue if isinstance(queue, SQLiteJobQueue) else SQLiteJobQueue(queue)
    return StudioWorker(
        resolved_queue,
        project_root=project_root,
        worker_id=worker_id,
        **worker_kwargs,
    ).run_once()


def run_forever(
    queue: SQLiteJobQueue | str | Path,
    *,
    project_root: str | Path = ".",
    worker_id: str | None = None,
    poll_interval: float = 0.5,
    stop_signal: StopSignal | Callable[[], bool] | None = None,
    max_jobs: int | None = None,
    recover_stale_after: timedelta | None = timedelta(minutes=5),
    **worker_kwargs: Any,
) -> int:
    """Public convenience API for the long-lived local worker."""

    resolved_queue = queue if isinstance(queue, SQLiteJobQueue) else SQLiteJobQueue(queue)
    return StudioWorker(
        resolved_queue,
        project_root=project_root,
        worker_id=worker_id,
        **worker_kwargs,
    ).run_forever(
        poll_interval=poll_interval,
        stop_signal=stop_signal,
        max_jobs=max_jobs,
        recover_stale_after=recover_stale_after,
    )


def _campaign_config_paths(
    config_path: Path,
    cfg: Mapping[str, Any],
    *,
    project_root: Path,
) -> list[Path]:
    context = resolve_campaign_context(config_path, project_root=project_root)
    if context is None or not context.campaign_yaml.is_file():
        raise ValueError("Studio run config is not inside a governed authored campaign")
    try:
        campaign = yaml.safe_load(context.campaign_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not read campaign definition {context.campaign_yaml}: {exc}") from exc
    variants = campaign.get("variants") if isinstance(campaign, dict) else None
    if not isinstance(variants, list) or not 1 <= len(variants) <= 5:
        raise ValueError("Studio campaigns require between one and five declared variants")
    attempt_id = str(cfg.get("attempt_id") or "")
    if not attempt_id:
        raise ValueError("Studio run config does not declare an authored attempt_id")
    try:
        relative_config = config_path.resolve().relative_to(context.campaign_root.resolve())
    except ValueError:
        relative_config = config_path
    if relative_config.parts and relative_config.parts[0] == "follow_up_attempts":
        from alphaquest.studio.followups import FollowUpAttemptService

        paths = list(
            FollowUpAttemptService(project_root).config_paths(context.campaign_id, attempt_id)
        )
        if config_path.resolve() not in paths:
            raise ValueError("job config path is not the governed definition for its follow-up attempt")
        return paths
    by_variant: dict[str, list[Path]] = {variant_id: [] for variant_id in (
        str(item if isinstance(item, str) else (item or {}).get("variant_id") or (item or {}).get("id") or "")
        for item in variants
    )}
    if "" in by_variant or len(by_variant) != len(variants):
        raise ValueError("campaign definition contains an invalid or duplicate variant ID")
    for candidate in context.campaign_root.rglob("config.yaml"):
        try:
            candidate_cfg = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(candidate_cfg, dict) or str(candidate_cfg.get("attempt_id") or "") != attempt_id:
            continue
        candidate_variant = str(candidate_cfg.get("variant_id") or candidate.parent.name)
        if candidate_variant in by_variant:
            by_variant[candidate_variant].append(candidate.resolve())
    paths: list[Path] = []
    for item in variants:
        variant_id = str(item if isinstance(item, str) else (item or {}).get("variant_id") or (item or {}).get("id") or "")
        if not variant_id:
            raise ValueError("campaign definition contains a variant without an ID")
        matches = by_variant[variant_id]
        if len(matches) != 1:
            raise ValueError(
                f"attempt {attempt_id!r} must contain exactly one config for {variant_id}; found {len(matches)}"
            )
        paths.append(matches[0])
    current = str(cfg.get("variant_id") or "")
    if current not in {path.parent.name for path in paths}:
        raise ValueError("job variant is not declared in campaign.yaml")
    if config_path.resolve() not in paths:
        raise ValueError("job config path is not the governed definition for its declared attempt identity")
    return paths


def _mandatory_methodology_issue(cfg: Mapping[str, Any]) -> str | None:
    tests = cfg.get("campaign_tests")
    if not isinstance(tests, Mapping):
        return "campaign_tests is missing; the full staged methodology cannot be proven"
    order = tests.get("stage_order")
    if list(order or []) != list(DEFAULT_STAGE_ORDER):
        return (
            "campaign_tests.stage_order must contain the full mandatory methodology in order: "
            + ", ".join(DEFAULT_STAGE_ORDER)
        )
    missing = [stage for stage in DEFAULT_STAGE_ORDER if not isinstance(tests.get(stage), Mapping)]
    if missing:
        return "mandatory stage configurations are missing: " + ", ".join(missing)
    disabled = [
        stage
        for stage in DEFAULT_STAGE_ORDER
        if tests[stage].get("enabled") is not True
    ]
    if disabled:
        return "mandatory stages are disabled: " + ", ".join(disabled)
    return None


def _gate_drift(hash_locks: Mapping[str, str], gate: Mapping[str, Any]) -> str | None:
    if gate.get("status") != "APPROVED_FOR_TESTING":
        return "mechanics approval is no longer APPROVED_FOR_TESTING"
    expected = {
        "config_hash": str(gate.get("config_hash") or ""),
        "input_data_hash": str(gate.get("input_data_hash") or ""),
    }
    mismatches = [
        f"{key}: queued={hash_locks.get(key, '<missing>')}, current={value or '<missing>'}"
        for key, value in expected.items()
        if hash_locks.get(key) != value
    ]
    return "; ".join(mismatches) if mismatches else None


def _mechanics_gate_drift(
    hash_locks: Mapping[str, str],
    gate: Mapping[str, Any],
) -> str | None:
    current = {
        "config_hash": str(gate.get("config_hash") or ""),
        "input_data_hash": str(gate.get("input_data_hash") or ""),
    }
    mismatches = [
        f"{key}: queued={hash_locks.get(key, '<missing>')}, current={value or '<missing>'}"
        for key, value in current.items()
        if hash_locks.get(key) != value
    ]
    return "; ".join(mismatches) if mismatches else None


def _manual_review_without_attempt(reason: str) -> dict[str, Any]:
    return {
        "research_verdict": "NEEDS MANUAL REVIEW",
        "attempt_reserved": False,
        "candidate_artifacts_suppressed": True,
        "reason": reason,
        "next_action": (
            "Resolve the blocker, then create an explicit replication, data refresh, methodology rerun, "
            "pre-PnL mechanics correction, or authorized rescue. This job will not replay."
        ),
    }


def _strict_json_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    import json

    return json.loads(json.dumps(value, sort_keys=True, default=str, allow_nan=False))


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _stop_requested(signal: StopSignal | Callable[[], bool] | None) -> bool:
    if signal is None:
        return False
    if callable(signal):
        return bool(signal())
    return bool(signal.is_set())


@contextmanager
def _project_working_directory(project_root: Path):
    """Bind legacy relative-path readers to one explicit Studio workspace."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Studio worker project root does not exist: {root}")
    with _PROJECT_CWD_LOCK:
        previous = Path.cwd()
        os.chdir(root)
        try:
            yield
        finally:
            os.chdir(previous)


@contextmanager
def _heartbeat_pump(context: JobExecutionContext, *, interval_seconds: float = 10.0):
    """Keep a long staged run distinguishable from a crashed local worker."""

    stopped = threading.Event()
    errors: list[Exception] = []

    def heartbeat() -> None:
        while not stopped.wait(interval_seconds):
            try:
                context.heartbeat()
            except Exception as exc:  # persisted by the queue at the worker boundary
                errors.append(exc)
                return

    thread = threading.Thread(
        target=heartbeat,
        name=f"alphaquest-heartbeat-{context.job_id}",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=max(1.0, interval_seconds + 1.0))
    if errors:
        raise RuntimeError(f"Studio worker heartbeat failed: {errors[0]}") from errors[0]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_declared_bar_mechanics_validation(
    config_path: Path,
    project_root: Path,
    *,
    progress_callback: MechanicsProgressCallback | None = None,
) -> Mapping[str, Any]:
    """Invoke the generic deterministic bar/event mechanics-validation service."""

    command = [
        sys.executable,
        "-m",
        "alphaquest.run_core",
        "--config",
        str(config_path),
        "--mechanics-validation",
        "--structured-progress",
    ]
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module; config is the governed job input
        command,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_tail: deque[str] = deque(maxlen=20)
    stderr_tail: deque[str] = deque(maxlen=20)

    def drain_stderr() -> None:
        if process.stderr is None:
            return
        for raw_line in process.stderr:
            line = raw_line.strip()
            if line:
                stderr_tail.append(line)

    stderr_thread = threading.Thread(
        target=drain_stderr,
        name="alphaquest-mechanics-stderr",
        daemon=True,
    )
    stderr_thread.start()
    try:
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith(STRUCTURED_PROGRESS_PREFIX):
                    try:
                        payload = json.loads(line[len(STRUCTURED_PROGRESS_PREFIX) :])
                    except json.JSONDecodeError as exc:
                        stderr_tail.append(f"invalid structured progress event: {exc}")
                        continue
                    if progress_callback is not None and isinstance(payload, dict):
                        progress_callback(payload)
                    continue
                stdout_tail.append(line)
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)
        stderr_thread.join(timeout=5.0)
        raise
    return_code = process.wait()
    stderr_thread.join(timeout=5.0)
    if return_code != 0:
        detail = "\n".join(list(stderr_tail or stdout_tail)[-20:])
        raise RuntimeError(
            f"declared mechanics-validation runner exited {return_code}: {detail}"
        )
    stdout_lines = list(stdout_tail)
    return {
        "service": "alphaquest.run_core --mechanics-validation",
        "exit_code": return_code,
        "source_run_dir": stdout_lines[-1] if stdout_lines else None,
        "stdout_tail": stdout_lines,
        "stderr_tail": list(stderr_tail),
    }


def _default_worker_id() -> str:
    return f"{socket.gethostname()}-{os_getpid()}"


def os_getpid() -> int:
    # Kept as a tiny seam for deterministic launcher tests.
    import os

    return os.getpid()


__all__ = [
    "CAMPAIGN_VARIANT_RUN",
    "MECHANICS_VALIDATION_RUN",
    "StudioWorker",
    "run_forever",
    "run_once",
]
