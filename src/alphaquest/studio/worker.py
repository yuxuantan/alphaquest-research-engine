"""Single-process durable worker for AlphaQuest Research Studio.

The worker accepts full ``campaign_variant_run`` jobs, pre-PnL
``mechanics_validation_run`` jobs, declared strategy-certification jobs, and
post-result account-assessment jobs.  It deliberately uses the existing
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
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import queue as thread_queue
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
from alphaquest.research.experiment_registry import (
    RESERVED as EXPERIMENT_RESERVED,
    RUNNING as EXPERIMENT_RUNNING,
    STRICT_RESEARCH_VERDICTS,
    AttemptReservation,
    AttemptPrePerformanceRetry,
    AttemptResolution,
    AttemptStatusTransition,
    ExperimentRegistry,
    ExperimentRegistryError,
    ExperimentTransitionError,
    reservation_from_campaign_config,
)
from alphaquest.research.preflight import run_preflight
from alphaquest.research.storage import display_path, load_storage_layout, resolve_campaign_context
from alphaquest.run_core import STRUCTURED_PROGRESS_PREFIX, _apply_mechanics_validation_contract
from alphaquest.studio.approvals import require_all_variant_mechanics_approved
from alphaquest.studio.finalization import (
    REPORTING_DIRECTORY,
    FinalizationResult,
    RunFinalizer,
    inspect_finalized_result,
)
from alphaquest.studio.results import RESULT_BUNDLE_FILENAME
from alphaquest.studio.jobs import (
    JobCancellationRequested,
    JobExecutionContext,
    JobRecordV1,
    SQLiteJobQueue,
)
from alphaquest.studio.process_ownership import (
    process_group_members,
    process_registry_root,
    refresh_process_group_record,
    register_process_group,
    terminate_process_group,
    terminate_registered_process_groups,
    unregister_process_group,
)
from alphaquest.utils.config import variant_root
from alphaquest.validation.checks import load_validation_checks_report
from alphaquest.validation.promotion_gate import inspect_validation_gate


CAMPAIGN_VARIANT_RUN = "campaign_variant_run"
MECHANICS_VALIDATION_RUN = "mechanics_validation_run"
STRATEGY_CERTIFICATION_RUN = "strategy_certification_run"
ACCOUNT_ASSESSMENT_RUN = "account_assessment_run"

_PROJECT_CWD_LOCK = threading.RLock()

StagedRunner = Callable[..., dict[str, Any]]
PreflightRunner = Callable[..., dict[str, Any]]
GateInspector = Callable[[dict[str, Any], Path], dict[str, Any]]
CampaignApprovalChecker = Callable[[list[Path]], list[dict[str, Any]]]
AttemptValidator = Callable[..., dict[str, Any]]
MechanicsRunner = Callable[[Path, Path], Mapping[str, Any]]
MechanicsProgressCallback = Callable[[Mapping[str, Any]], None]


def _persist_campaign_progress(
    context: JobExecutionContext,
    update: Mapping[str, Any],
) -> None:
    """Map one real staged-runner counter into the full job's progress range."""

    stage_index = max(int(update.get("stage_index") or 1), 1)
    stage_total = max(int(update.get("stage_total") or len(DEFAULT_STAGE_ORDER)), 1)
    stage_percent = max(0.0, min(float(update.get("percent") or 0.0), 100.0))
    completed_stage_fraction = (stage_index - 1) + (stage_percent / 100.0)
    overall_percent = 10.0 + (85.0 * completed_stage_fraction / stage_total)
    completed = update.get("completed")
    total = update.get("total")
    worker_counts = {
        key: value
        for key, value in {
            "active_workers": _optional_int(update.get("active_workers")),
            "expected_workers": _optional_int(update.get("expected_workers")),
        }.items()
        if value is not None
    }
    context.report_progress(
        phase=str(update.get("phase") or "campaign_stages"),
        message=str(update.get("message") or f"Running campaign stage {stage_index} of {stage_total}"),
        percent=min(overall_percent, 95.0),
        completed=int(completed) if completed is not None else None,
        total=int(total) if total is not None else None,
        unit=str(update["unit"]) if update.get("unit") else None,
        **worker_counts,
    )


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
        experiment_registry: ExperimentRegistry | None = None,
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
        self._staged_runner_reports_progress = staged_runner is run_campaign_stage_tests
        self.finalizer = finalizer or RunFinalizer(self.project_root)
        layout = load_storage_layout(self.project_root)
        self.experiment_registry = experiment_registry or ExperimentRegistry(
            layout.research_artifact_root / "governance" / "experiment_registry.jsonl"
        )

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
        # Any registry record present before this worker starts belongs to a
        # predecessor that can no longer supervise its descendants.
        orphan_outcomes = terminate_registered_process_groups(self.project_root)
        failures = [item for item in orphan_outcomes if not item["terminated"]]
        if failures:
            raise RuntimeError(
                "failed to terminate orphaned Studio job process groups: "
                + "; ".join(str(item["error"]) for item in failures)
            )
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
        if job.job_type == STRATEGY_CERTIFICATION_RUN:
            from alphaquest.strategy_certification import (
                compute_implementation_sha256,
                get_strategy_certification,
            )

            strategy_id = str(job.payload.get("strategy_id") or "").strip()
            certification = get_strategy_certification(
                strategy_id,
                self.project_root,
                require_current=False,
            )
            return {
                "implementation_hash": compute_implementation_sha256(
                    self.project_root,
                    certification.source_files,
                ),
                "certification_manifest_hash": _file_sha256(
                    certification.manifest_path
                ),
            }
        if job.job_type == ACCOUNT_ASSESSMENT_RUN:
            return self._observed_account_assessment_hashes(job)
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
            values["mechanics_approval_sha256"] = approval_hash
        strategy_implementation_sha256 = str(
            gate.get("strategy_implementation_sha256") or ""
        )
        if strategy_implementation_sha256:
            values["strategy_implementation_sha256"] = (
                strategy_implementation_sha256
            )
        strategy_certification_manifest_sha256 = str(
            gate.get("strategy_certification_manifest_sha256") or ""
        )
        if strategy_certification_manifest_sha256:
            values["strategy_certification_manifest_sha256"] = (
                strategy_certification_manifest_sha256
            )
        if job.job_type == CAMPAIGN_VARIANT_RUN and job.payload.get(
            "pre_performance_retry"
        ) is not None:
            output_dir = self._output_dir(job, cfg, config_path)
            retry_contract = _validate_preperformance_retry(
                job,
                project_root=self.project_root,
                output_dir=output_dir,
                gate=gate,
            )
            assert retry_contract is not None
            values["pre_performance_proof_sha256"] = str(
                retry_contract["proof_sha256"]
            )
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
        if job.job_type == STRATEGY_CERTIFICATION_RUN:
            return self._execute_strategy_certification(context, job)
        if job.job_type == ACCOUNT_ASSESSMENT_RUN:
            return self._execute_account_assessment(context, job)
        if job.job_type == MECHANICS_VALIDATION_RUN:
            return self._execute_mechanics_validation(context, job)
        if job.job_type != CAMPAIGN_VARIANT_RUN:
            raise ValueError(f"unsupported Studio job type: {job.job_type}")
        context.report_progress(
            phase="validating_submission",
            message="Validating campaign, approval, and locked inputs",
            percent=1.0,
        )
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
        context.report_progress(
            phase="preflight",
            message="Running full staged-submission preflight",
            percent=4.0,
        )
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
                    "full mandatory methodology is not frozen for every variant: " + "; ".join(methodology_issues)
                ),
                "preflight": _strict_json_mapping(preflight),
            }

        try:
            context.report_progress(
                phase="mechanics_approval",
                message="Checking current mechanics approvals",
                percent=7.0,
            )
            approval_reports = self.campaign_approval_checker(approval_paths)
        except Exception as exc:
            return {
                **_manual_review_without_attempt(f"the current sequential variant requires mechanics approval: {exc}"),
                "preflight": _strict_json_mapping(preflight),
            }

        output_dir = self._output_dir(job, cfg, config_path)
        retry_contract = _validate_preperformance_retry(
            job,
            project_root=self.project_root,
            output_dir=output_dir,
            gate=gate,
        )
        # This repeats the runner's immutable-attempt guard before reservation.
        # The runner repeats it after reservation to catch the remaining race.
        self.attempt_validator(cfg, config_path, out_dir=output_dir)
        try:
            experiment_reservation = self._build_experiment_reservation(
                cfg,
                config_path=config_path,
                gate=gate,
            )
        except ExperimentRegistryError as exc:
            return {
                **_manual_review_without_attempt(
                    "the PnL experiment cannot be pre-registered: " + str(exc)
                ),
                "preflight": _strict_json_mapping(preflight),
            }
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
        context.report_progress(
            phase="reserving_attempt",
            message="Reserving immutable campaign attempt",
            percent=9.0,
        )
        registry_reserved = False
        try:
            # This is the first durable PnL-trial marker and is deliberately
            # adjacent to the queue's irreversible attempt reservation.  A
            # crash between the two still consumes a trial and is recovered
            # as an incomplete experiment; it is never silently replayed.
            experiment_event = self.experiment_registry.reserve(experiment_reservation)
            registry_reserved = True
            context.reserve_attempt()
            if retry_contract is not None:
                experiment_event = self.experiment_registry.retry_pre_performance(
                    AttemptPrePerformanceRetry(
                        campaign_id=experiment_reservation.campaign_id,
                        variant_id=experiment_reservation.variant_id,
                        attempt_id=experiment_reservation.attempt_id,
                        prior_resolution_sha256=str(
                            retry_contract["prior_resolution_sha256"]
                        ),
                        pre_performance_proof_sha256=str(
                            retry_contract["proof_sha256"]
                        ),
                        failed_job_id=str(retry_contract["failed_job_id"]),
                        retry_job_id=job.job_id,
                        recorded_at=_now_iso(),
                        reason=(
                            "User explicitly continued the same reserved methodology after "
                            "hash-bound evidence proved that no PnL-bearing stage began."
                        ),
                    )
                )
            self.finalizer.record_recovery_phase(
                job.job_id,
                "ATTEMPT_RESERVED",
                details={
                    "output_dir": str(output_dir),
                    "experiment_record_sha256": experiment_event["record_sha256"],
                    "pre_performance_retry": retry_contract is not None,
                },
            )
            if retry_contract is None:
                self.experiment_registry.transition(
                    AttemptStatusTransition(
                        campaign_id=experiment_reservation.campaign_id,
                        variant_id=experiment_reservation.variant_id,
                        attempt_id=experiment_reservation.attempt_id,
                        from_status=EXPERIMENT_RESERVED,
                        to_status=EXPERIMENT_RUNNING,
                        recorded_at=_now_iso(),
                        reason="Studio queue reserved the immutable attempt and accepted runner ownership.",
                    )
                )
            context.raise_if_cancelled()
            with _heartbeat_pump(context):
                runner_kwargs = {
                    "skip_validation": False,
                    "continue_on_failure": False,
                    "out_dir": output_dir,
                    "include_acceptance": True,
                    "fast_runtime_defaults": False,
                    "authoritative_parallel_workers": min(3, os.cpu_count() or 1),
                    "authoritative_core_grid_workers": min(6, os.cpu_count() or 1),
                }
                if self._staged_runner_reports_progress:
                    summary = _run_declared_campaign_variant(
                        config_path,
                        self.project_root,
                        output_dir=output_dir,
                        job_id=job.job_id,
                        authoritative_parallel_workers=int(runner_kwargs["authoritative_parallel_workers"]),
                        authoritative_core_grid_workers=int(
                            runner_kwargs["authoritative_core_grid_workers"]
                        ),
                        progress_callback=lambda update: _persist_campaign_progress(
                            context,
                            update,
                        ),
                        cancellation_requested=context.cancellation_requested,
                    )
                else:
                    summary = self.staged_runner(config_path, **runner_kwargs)
                context.raise_if_cancelled()
                context.report_progress(
                    phase="finalizing_evidence",
                    message="Finalizing governed result bundle and research ledger",
                    percent=97.0,
                )
                finalized = self.finalizer.finalize(
                    job_id=job.job_id,
                    config_path=config_path,
                    summary=summary,
                )
                result_sha256 = self._resolve_completed_experiment(
                    cfg,
                    finalized=finalized,
                    reason="The governed finalizer published a terminal ResultBundleV2.",
                )
        except BaseException as exc:
            if registry_reserved and not self._resolve_valid_finalized_experiment(
                cfg,
                config_path=config_path,
                output_dir=output_dir,
                reason="A complete hash-valid finalized result survived worker interruption.",
            ):
                self._abort_reserved_job(
                    job,
                    config_path=config_path,
                    output_dir=output_dir,
                    reason=f"{type(exc).__name__}: {exc}",
                    cancelled=isinstance(exc, JobCancellationRequested),
                    resolve_experiment=True,
                )
            raise
        context.report_progress(
            phase="completed",
            message="Campaign variant run completed",
            percent=100.0,
        )
        return {
            **finalized.as_job_result(project_root=self.project_root),
            "preflight": _strict_json_mapping(preflight),
            "approval_count": len(approval_reports),
            "experiment_registry": {
                "path": display_path(self.experiment_registry.path, self.project_root),
                "status": "COMPLETED",
                "result_sha256": result_sha256,
                "economic_edge_trial_count": self.experiment_registry.trial_count(
                    experiment_reservation.economic_edge_fingerprint_sha256
                ),
            },
        }

    def _build_experiment_reservation(
        self,
        cfg: Mapping[str, Any],
        *,
        config_path: Path,
        gate: Mapping[str, Any],
    ) -> AttemptReservation:
        context = resolve_campaign_context(config_path, project_root=self.project_root)
        if context is None or not context.campaign_yaml.is_file():
            raise ExperimentRegistryError(
                "the config is not inside a governed campaign with campaign.yaml"
            )
        try:
            campaign = yaml.safe_load(context.campaign_yaml.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ExperimentRegistryError(
                f"could not read campaign economic-edge identity: {exc}"
            ) from exc
        if not isinstance(campaign, Mapping):
            raise ExperimentRegistryError("campaign.yaml must contain a mapping")
        if str(campaign.get("campaign_id") or context.campaign_id) != str(
            cfg.get("campaign_id") or ""
        ):
            raise ExperimentRegistryError("campaign.yaml identity does not match the run config")
        fingerprint = campaign.get("economic_edge_fingerprint")
        if not isinstance(fingerprint, Mapping) or not fingerprint:
            raise ExperimentRegistryError(
                "campaign.yaml must freeze a non-empty economic_edge_fingerprint before PnL"
            )

        attempt_kind = str(cfg.get("attempt_kind") or "")
        parent_attempt_id = str(cfg.get("parent_attempt_id") or "").strip() or None
        if attempt_kind == "original" and parent_attempt_id is not None:
            raise ExperimentRegistryError("an original attempt cannot declare a parent attempt")
        if attempt_kind != "original" and parent_attempt_id is None:
            raise ExperimentRegistryError("a non-original attempt must declare its immutable parent")

        parent_recorded: bool | None = None
        parent_evidence_sha256: str | None = None
        if parent_attempt_id is not None:
            parent_recorded = any(
                str(item.get("campaign_id") or "") == str(cfg.get("campaign_id") or "")
                and str(item.get("attempt_id") or "") == parent_attempt_id
                for item in self.experiment_registry.attempts()
            )
            if not parent_recorded:
                parent_evidence_sha256 = _legacy_parent_evidence_sha256(
                    context.campaign_root,
                    variant_id=str(cfg.get("variant_id") or ""),
                    parent_attempt_id=parent_attempt_id,
                )

        return reservation_from_campaign_config(
            cfg,
            config_sha256=str(gate.get("config_hash") or ""),
            data_sha256=str(gate.get("input_data_hash") or ""),
            economic_edge_fingerprint=fingerprint,
            reserved_at=_now_iso(),
            parent_recorded_in_registry=parent_recorded,
            parent_evidence_sha256=parent_evidence_sha256,
        )

    def _resolve_completed_experiment(
        self,
        cfg: Mapping[str, Any],
        *,
        finalized: FinalizationResult,
        reason: str,
    ) -> str:
        verdict = str(finalized.research_verdict or "").upper()
        if verdict not in STRICT_RESEARCH_VERDICTS:
            raise ExperimentRegistryError(
                "finalized experiment does not carry a strict PASS, FAIL, or NEEDS MANUAL REVIEW verdict"
            )
        result_path = Path(finalized.result_bundle_path).resolve()
        if not result_path.is_file():
            raise ExperimentRegistryError(
                f"finalized ResultBundleV2 is missing and cannot be hash-bound: {result_path}"
            )
        try:
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperimentRegistryError(f"finalized ResultBundleV2 is invalid JSON: {exc}") from exc
        bundle_verdict = (
            str(result_payload.get("verdict") or "").upper()
            if isinstance(result_payload, Mapping)
            else ""
        )
        if bundle_verdict != verdict:
            raise ExperimentRegistryError(
                "finalizer verdict does not match the finalized ResultBundleV2 verdict"
            )
        result_sha256 = _file_sha256(result_path)
        current = self.experiment_registry.current_status(
            str(cfg.get("campaign_id") or ""),
            str(cfg.get("variant_id") or ""),
            str(cfg.get("attempt_id") or ""),
        )
        if current != EXPERIMENT_RUNNING:
            raise ExperimentTransitionError(
                f"completed ResultBundleV2 belongs to an experiment in {current}, not RUNNING"
            )
        self.experiment_registry.resolve(
            AttemptResolution(
                campaign_id=str(cfg.get("campaign_id") or ""),
                variant_id=str(cfg.get("variant_id") or ""),
                attempt_id=str(cfg.get("attempt_id") or ""),
                from_status=EXPERIMENT_RUNNING,
                terminal_status="COMPLETED",
                recorded_at=_now_iso(),
                reason=reason,
                research_verdict=verdict,
                result_sha256=result_sha256,
            )
        )
        return result_sha256

    def _resolve_valid_finalized_experiment(
        self,
        cfg: Mapping[str, Any],
        *,
        config_path: Path,
        output_dir: Path,
        reason: str,
    ) -> bool:
        """Recover a terminal registry state without replaying finalized PnL."""

        result_path = output_dir / REPORTING_DIRECTORY / RESULT_BUNDLE_FILENAME
        if not result_path.is_file():
            return False
        try:
            inspection = inspect_finalized_result(result_path, config_path=config_path)
        except Exception:
            return False
        bundle = inspection.get("bundle")
        if inspection.get("valid") is not True or bundle is None:
            return False
        verdict = str(getattr(bundle, "verdict", "") or "").upper()
        if verdict not in STRICT_RESEARCH_VERDICTS:
            return False
        try:
            current = self.experiment_registry.current_status(
                str(cfg.get("campaign_id") or ""),
                str(cfg.get("variant_id") or ""),
                str(cfg.get("attempt_id") or ""),
            )
            if current == "COMPLETED":
                return True
            if current == EXPERIMENT_RESERVED:
                self.experiment_registry.transition(
                    AttemptStatusTransition(
                        campaign_id=str(cfg.get("campaign_id") or ""),
                        variant_id=str(cfg.get("variant_id") or ""),
                        attempt_id=str(cfg.get("attempt_id") or ""),
                        from_status=EXPERIMENT_RESERVED,
                        to_status=EXPERIMENT_RUNNING,
                        recorded_at=_now_iso(),
                        reason="Recovery verified that the governed runner produced a complete finalized result.",
                    )
                )
            elif current != EXPERIMENT_RUNNING:
                return False
            self.experiment_registry.resolve(
                AttemptResolution(
                    campaign_id=str(cfg.get("campaign_id") or ""),
                    variant_id=str(cfg.get("variant_id") or ""),
                    attempt_id=str(cfg.get("attempt_id") or ""),
                    from_status=EXPERIMENT_RUNNING,
                    terminal_status="COMPLETED",
                    recorded_at=_now_iso(),
                    reason=reason,
                    research_verdict=verdict,
                    result_sha256=_file_sha256(result_path),
                )
            )
            return True
        except ExperimentRegistryError:
            return False

    def _recover_orphaned_jobs(self, *, stale_after: timedelta) -> list[JobRecordV1]:
        recovered = self.queue.recover_orphaned_jobs(stale_after=stale_after)
        for job in recovered:
            if job.job_type != CAMPAIGN_VARIANT_RUN:
                continue
            try:
                config_path, cfg = self._load_job_config(job)
                output_dir = self._output_dir(job, cfg, config_path)
            except Exception:
                continue
            if self._resolve_valid_finalized_experiment(
                cfg,
                config_path=config_path,
                output_dir=output_dir,
                reason="Stale-job recovery verified a complete hash-valid finalized ResultBundleV2.",
            ):
                continue
            try:
                registry_status = self.experiment_registry.current_status(
                    str(cfg.get("campaign_id") or ""),
                    str(cfg.get("variant_id") or ""),
                    str(cfg.get("attempt_id") or ""),
                )
            except ExperimentRegistryError:
                registry_status = None
            if not job.attempt_reserved and registry_status not in {
                EXPERIMENT_RESERVED,
                EXPERIMENT_RUNNING,
            }:
                continue
            self._abort_reserved_job(
                job,
                config_path=config_path,
                output_dir=output_dir,
                reason=job.error or "worker heartbeat expired after attempt reservation",
                cancelled=job.state.value == "CANCELLED",
                resolve_experiment=registry_status in {
                    EXPERIMENT_RESERVED,
                    EXPERIMENT_RUNNING,
                },
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
        resolve_experiment: bool = False,
    ) -> None:
        marker_path: Path | None = None
        try:
            marker_path = self.finalizer.abort_reserved_attempt(
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
            return

        # The registry terminal event is intentionally written only after the
        # durable incomplete marker.  If marker publication failed, the active
        # registry state remains visible for manual recovery instead of falsely
        # claiming the interrupted attempt was safely closed.
        if not resolve_experiment or marker_path is None or not marker_path.is_file():
            return
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            current = self.experiment_registry.current_status(
                str(cfg.get("campaign_id") or ""),
                str(cfg.get("variant_id") or ""),
                str(cfg.get("attempt_id") or ""),
            )
            if current not in {EXPERIMENT_RESERVED, EXPERIMENT_RUNNING}:
                return
            self.experiment_registry.resolve(
                AttemptResolution(
                    campaign_id=str(cfg.get("campaign_id") or ""),
                    variant_id=str(cfg.get("variant_id") or ""),
                    attempt_id=str(cfg.get("attempt_id") or ""),
                    from_status=current,
                    terminal_status="CANCELLED" if cancelled else "FAILED",
                    recorded_at=_now_iso(),
                    reason=reason,
                    research_verdict="NEEDS MANUAL REVIEW",
                    result_sha256=None,
                )
            )
        except Exception as exc:
            try:
                self.finalizer.record_recovery_phase(
                    job.job_id,
                    "EXPERIMENT_REGISTRY_RESOLUTION_FAILED",
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
        # Mechanics approval belongs to one immutable variant definition.  A
        # previously concluded sibling may legitimately carry an older
        # certification identity, so campaign-wide preflight would prevent a
        # later variant from ever producing its own review evidence.  The
        # selected config still receives the full config, campaign-governance,
        # data, and certification checks performed by ``run_preflight``.
        preflight = self.preflight_runner(
            config_paths=[config_path],
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
            raise RuntimeError("declared mechanics-validation runner completed without its evidence directory")
        validation_checks = load_validation_checks_report(evidence_dir)
        blocking_checks = validation_checks[
            validation_checks["status"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .isin({"error", "fail", "failed", "unresolved"})
        ]
        if not blocking_checks.empty:
            blocker_names = [
                str(value)
                for value in blocking_checks["check_name"].dropna().unique()
            ]
            self.finalizer.record_recovery_phase(
                job.job_id,
                "MECHANICS_VALIDATION_EVIDENCE_BLOCKED",
                details={
                    "evidence_dir": str(evidence_dir),
                    "attempt_reserved": False,
                    "blocking_checks": blocker_names,
                },
                terminal=True,
            )
            context.report_progress(
                phase="evidence_blocked",
                message=(
                    "Mechanics evidence is incomplete; resolve automated "
                    "validation errors before review"
                ),
                percent=100.0,
            )
            return {
                "research_verdict": "NEEDS MANUAL REVIEW",
                "attempt_reserved": False,
                "candidate_artifacts_suppressed": True,
                "mechanics_validation_status": "EVIDENCE_BLOCKED",
                "validation_lane": lane,
                "config_path": str(config_path),
                "evidence_dir": str(evidence_dir),
                "config_hash": str(
                    refreshed_gate.get("config_hash")
                    or gate.get("config_hash")
                    or ""
                ),
                "input_data_hash": str(
                    refreshed_gate.get("input_data_hash")
                    or gate.get("input_data_hash")
                    or ""
                ),
                "preflight": _strict_json_mapping(preflight),
                "runner": runner_result,
                "blocking_checks": blocker_names,
                "next_action": (
                    "Inspect the failed automated mechanics checks. Do not "
                    "record mechanics approval for this evidence."
                ),
            }
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
            "input_data_hash": str(refreshed_gate.get("input_data_hash") or gate.get("input_data_hash") or ""),
            "preflight": _strict_json_mapping(preflight),
            "runner": runner_result,
            "next_action": "Review the sampled mechanics evidence and record approval or rejection.",
        }

    def _observed_account_assessment_hashes(
        self,
        job: JobRecordV1,
    ) -> Mapping[str, str]:
        inputs = self._account_assessment_inputs(job)
        return {
            "result_bundle_hash": _file_sha256(inputs["bundle_path"]),
            "config_hash": str(inputs["gate"].get("config_hash") or ""),
            "input_data_hash": str(inputs["gate"].get("input_data_hash") or ""),
            "account_profile_hash": inputs["profile"].sha256,
        }

    def _account_assessment_inputs(self, job: JobRecordV1) -> dict[str, Any]:
        from alphaquest.accounts.catalog import resolve_account_profile
        from alphaquest.studio.results import load_result_bundle

        bundle_path = _resolved_job_path(
            self.project_root,
            job.payload.get("result_bundle_path"),
            label="result bundle",
        )
        config_path = _resolved_job_path(
            self.project_root,
            job.payload.get("config_path"),
            label="source config",
        )
        evidence_roots = tuple(
            item.resolve()
            for item in load_storage_layout(self.project_root).evidence_roots
        )
        if not any(bundle_path.is_relative_to(item) for item in evidence_roots):
            raise ValueError("account assessment result bundle is outside governed evidence roots")
        context = resolve_campaign_context(config_path, project_root=self.project_root)
        if context is None:
            raise ValueError("account assessment config is outside a governed campaign")
        inspection = inspect_finalized_result(bundle_path, config_path=config_path)
        if inspection.get("valid") is not True:
            raise ValueError(
                "account assessment requires a complete hash-valid ResultBundleV2: "
                + "; ".join(str(item) for item in inspection.get("errors") or [])
            )
        bundle = load_result_bundle(bundle_path)
        campaign_id = str(job.payload.get("campaign_id") or "")
        variant_id = str(job.payload.get("variant_id") or "")
        if bundle.campaign_id != campaign_id or bundle.variant_id != variant_id:
            raise ValueError("account assessment selection does not match ResultBundleV2 identity")
        if bundle.scientific_validity_verdict != "PASS":
            raise ValueError(
                "account assessment requires scientific-validity PASS; generic objective PASS is not required"
            )
        if context.campaign_id != campaign_id or config_path.parent.name != variant_id:
            raise ValueError("account assessment source config identity does not match the selection")
        profile = resolve_account_profile(
            str(job.payload.get("profile_id") or ""),
            version=str(job.payload.get("profile_version") or "") or None,
            project_root=self.project_root,
        )
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        data = cfg.get("data") if isinstance(cfg.get("data"), Mapping) else {}
        input_data_hash = str(
            data.get("canonical_sha256")
            or data.get("source_sha256")
            or ""
        ).strip()
        if not input_data_hash:
            raise ValueError("account assessment source config has no frozen input-data hash")
        gate = {
            "config_hash": _file_sha256(config_path),
            "input_data_hash": input_data_hash,
        }
        return {
            "bundle_path": bundle_path,
            "config_path": config_path,
            "bundle": bundle,
            "config": cfg,
            "gate": gate,
            "profile": profile,
        }

    def _execute_strategy_certification(
        self,
        context: JobExecutionContext,
        job: JobRecordV1,
    ) -> dict[str, Any]:
        from alphaquest.strategy_certification import certify_strategy

        strategy_id = str(job.payload.get("strategy_id") or "").strip()
        context.report_progress(
            phase="certification_tests",
            message="Running every test declared by the strategy certification manifest",
            percent=5.0,
        )
        context.raise_if_cancelled()
        with _heartbeat_pump(context):
            certification = certify_strategy(strategy_id, self.project_root)
        context.raise_if_cancelled()
        context.report_progress(
            phase="certification_complete",
            message="Strategy implementation is certified",
            percent=100.0,
        )
        return {
            "certification_verdict": "PASS",
            "strategy_id": strategy_id,
            "implementation_version": certification.implementation_version,
            "implementation_sha256": certification.implementation_sha256,
            "manifest_sha256": certification.manifest_sha256,
            "required_test_count": len(certification.required_tests),
            "next_action": (
                "Create an immutable pre-PnL mechanics-correction attempt with "
                "certification refresh, then generate and review fresh mechanics evidence."
            ),
        }

    def _execute_account_assessment(
        self,
        context: JobExecutionContext,
        job: JobRecordV1,
    ) -> dict[str, Any]:
        from alphaquest.accounts.assessment import run_governed_account_assessment
        from alphaquest.accounts.models import AccountAssessmentCostsV1
        from alphaquest.studio.results import (
            RESULT_BUNDLE_V3_FILENAME,
            build_result_bundle_v3,
        )

        inputs = self._account_assessment_inputs(job)
        context.report_progress(
            phase="preparing_account_evidence",
            message="Verifying and normalizing the exact finalized trade evidence",
            percent=5.0,
        )
        trades = _account_assessment_trades(
            inputs["bundle"],
            inputs["bundle_path"],
            inputs["config"],
        )
        raw_costs = job.payload.get("costs")
        costs = (
            AccountAssessmentCostsV1.model_validate(raw_costs, strict=False)
            if isinstance(raw_costs, Mapping)
            else None
        )
        profile = inputs["profile"]
        context.raise_if_cancelled()
        context.report_progress(
            phase="account_monte_carlo",
            message=(
                f"Replaying {profile.profile.evaluation_policy.monte_carlo_runs} "
                "governed account paths"
            ),
            percent=15.0,
            total=profile.profile.evaluation_policy.monte_carlo_runs,
            unit="paths",
        )
        with _heartbeat_pump(context):
            manifest = run_governed_account_assessment(
                trades,
                profile,
                load_storage_layout(self.project_root).research_artifact_root,
                campaign_id=str(job.payload["campaign_id"]),
                variant_id=str(job.payload["variant_id"]),
                attempt_id=inputs["bundle"].run_id,
                source_attempt_id=str(job.payload["attempt_id"]),
                config_sha256=str(inputs["gate"]["config_hash"]),
                data_sha256=str(inputs["gate"]["input_data_hash"]),
                strategy_implementation_sha256=_strategy_implementation_hash(
                    inputs["config"]
                ),
                costs=costs,
                manual_attestations=job.payload.get("manual_attestations") or [],
                runs=profile.profile.evaluation_policy.monte_carlo_runs,
                seed=11,
            )
        context.raise_if_cancelled()
        context.report_progress(
            phase="publishing_account_assessment",
            message="Binding the destination verdict to ResultBundleV3",
            percent=95.0,
        )
        manifests = _matching_account_assessment_manifests(
            load_storage_layout(self.project_root).research_artifact_root,
            campaign_id=inputs["bundle"].campaign_id,
            variant_id=inputs["bundle"].variant_id,
            result_run_id=inputs["bundle"].run_id,
        )
        output_path = inputs["bundle_path"].parent / RESULT_BUNDLE_V3_FILENAME
        bundle_v3 = build_result_bundle_v3(
            inputs["bundle_path"],
            manifests,
            output_path,
        )
        context.report_progress(
            phase="account_assessment_complete",
            message="Account-specific suitability assessment complete",
            percent=100.0,
        )
        return {
            "research_verdict": manifest["verdict"],
            "assessment_id": manifest["assessment_id"],
            "campaign_id": manifest["campaign_id"],
            "variant_id": manifest["variant_id"],
            "attempt_id": job.payload["attempt_id"],
            "result_run_id": manifest["attempt_id"],
            "profile_id": manifest["profile_id"],
            "profile_version": manifest["profile_version"],
            "profile_sha256": manifest["profile_sha256"],
            "assessment_path": manifest["assessment_path"],
            "result_bundle_v3": str(output_path),
            "account_evaluation_count": len(bundle_v3.account_evaluations),
            "next_action": "Inspect the account-specific deterministic and Monte Carlo gates in Results.",
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
            raise ValueError(f"job campaign_id {job.campaign_id!r} does not match config campaign_id {campaign_id!r}")
        if job.payload.get("variant_id") and variant_id != str(job.payload["variant_id"]):
            raise ValueError(
                f"job variant_id {job.payload['variant_id']!r} does not match config variant_id {variant_id!r}"
            )
        if job.payload.get("attempt_id") and str(value.get("attempt_id") or "") != str(job.payload["attempt_id"]):
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


def _legacy_parent_evidence_sha256(
    campaign_root: Path,
    *,
    variant_id: str,
    parent_attempt_id: str,
) -> str:
    """Bind an unregistered parent to verified immutable authoring evidence."""

    if not variant_id:
        raise ExperimentRegistryError("parent lineage requires a variant_id")
    files: list[tuple[str, Path]] = []
    if parent_attempt_id == "original":
        config_path = campaign_root / "variants" / variant_id / "config.yaml"
        files.append(("parent_config", config_path))
    else:
        attempt_root = campaign_root / "follow_up_attempts" / parent_attempt_id
        manifest_path = attempt_root / "attempt_manifest.json"
        config_path = attempt_root / variant_id / "config.yaml"
        files.extend(
            (
                ("parent_attempt_manifest", manifest_path),
                ("parent_config", config_path),
            )
        )

    missing = [str(path) for _role, path in files if not path.is_file()]
    if missing:
        raise ExperimentRegistryError(
            "legacy parent evidence is missing and cannot be hash-bound: " + ", ".join(missing)
        )

    if parent_attempt_id != "original":
        manifest_path = files[0][1]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperimentRegistryError(f"legacy parent manifest is invalid: {exc}") from exc
        declared = manifest.get("config_sha256") if isinstance(manifest, Mapping) else None
        if not isinstance(declared, Mapping):
            raise ExperimentRegistryError("legacy parent manifest lacks config_sha256 bindings")
        actual = _file_sha256(files[1][1])
        if str(declared.get(variant_id) or "") != actual:
            raise ExperimentRegistryError(
                "legacy parent config does not match its immutable attempt-manifest hash"
            )

    payload = {
        "campaign_id": campaign_root.name,
        "variant_id": variant_id,
        "parent_attempt_id": parent_attempt_id,
        "files": [
            {
                "role": role,
                "path": str(path.relative_to(campaign_root)),
                "sha256": _file_sha256(path),
            }
            for role, path in files
        ],
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _campaign_config_paths(
    config_path: Path,
    cfg: Mapping[str, Any],
    *,
    project_root: Path,
) -> list[Path]:
    """Resolve only the job variant's governed config.

    Campaign order proves sequencing between independent variants. It does not
    make sibling implementations execution dependencies of the selected job.
    """
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

        paths = list(FollowUpAttemptService(project_root).config_paths(context.campaign_id, attempt_id))
        if config_path.resolve() not in paths:
            raise ValueError("job config path is not the governed definition for its follow-up attempt")
        return [config_path.resolve()]
    by_variant: dict[str, list[Path]] = {
        variant_id: []
        for variant_id in (
            str(item if isinstance(item, str) else (item or {}).get("variant_id") or (item or {}).get("id") or "")
            for item in variants
        )
    }
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
        variant_id = str(
            item if isinstance(item, str) else (item or {}).get("variant_id") or (item or {}).get("id") or ""
        )
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
    return [config_path.resolve()]


def _mandatory_methodology_issue(cfg: Mapping[str, Any]) -> str | None:
    objectives = cfg.get("research_objectives")
    objectives_sha256 = str(cfg.get("research_objectives_sha256") or "")
    if not isinstance(objectives, Mapping) or not objectives_sha256:
        return (
            "confirmed frozen research_objectives and research_objectives_sha256 are required before PnL; "
            "objectives cannot be retrofitted after PnL, so create a new governed pre-PnL protocol"
        )
    actual_objectives_sha256 = hashlib.sha256(
        json.dumps(
            objectives,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if objectives_sha256 != actual_objectives_sha256:
        return (
            "research_objectives_sha256 does not match the frozen objective contract; "
            "objectives cannot be changed after PnL"
        )
    if objectives.get("confirmed") is not True:
        return "research objectives must be explicitly confirmed before PnL"
    tests = cfg.get("campaign_tests")
    if not isinstance(tests, Mapping):
        return "campaign_tests is missing; the full staged methodology cannot be proven"
    order = tests.get("stage_order")
    if list(order or []) != list(DEFAULT_STAGE_ORDER):
        return "campaign_tests.stage_order must contain the full mandatory methodology in order: " + ", ".join(
            DEFAULT_STAGE_ORDER
        )
    missing = [stage for stage in DEFAULT_STAGE_ORDER if not isinstance(tests.get(stage), Mapping)]
    if missing:
        return "mandatory stage configurations are missing: " + ", ".join(missing)
    disabled = [stage for stage in DEFAULT_STAGE_ORDER if tests[stage].get("enabled") is not True]
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
    approval_path = Path(str(gate.get("approval_path") or ""))
    optional = {
        "mechanics_approval_sha256": (
            _file_sha256(approval_path) if approval_path.is_file() else ""
        ),
        "strategy_implementation_sha256": str(
            gate.get("strategy_implementation_sha256") or ""
        ),
        "strategy_certification_manifest_sha256": str(
            gate.get("strategy_certification_manifest_sha256") or ""
        ),
    }
    expected.update({key: value for key, value in optional.items() if key in hash_locks})
    mismatches = [
        f"{key}: queued={hash_locks.get(key, '<missing>')}, current={value or '<missing>'}"
        for key, value in expected.items()
        if hash_locks.get(key) != value
    ]
    return "; ".join(mismatches) if mismatches else None


def _validate_preperformance_retry(
    job: JobRecordV1,
    *,
    project_root: Path,
    output_dir: Path,
    gate: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw = job.payload.get("pre_performance_retry")
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or raw.get("schema") != (
        "alphaquest.pre-performance-campaign-retry/v1"
    ):
        raise ValueError("campaign retry payload has an unsupported proof contract")
    if int(raw.get("retry_index") or 0) != 1:
        raise ValueError("campaign retry payload exceeds the single permitted retry")
    failed_job_id = str(raw.get("failed_job_id") or "")
    if not failed_job_id or str(job.payload.get("retry_of_job_id") or "") != failed_job_id:
        raise ValueError("campaign retry payload does not bind its failed job")
    recovery_path = Path(str(raw.get("recovery_path") or ""))
    recovery_path = (
        recovery_path.resolve()
        if recovery_path.is_absolute()
        else (project_root / recovery_path).resolve()
    )
    runtime_root = load_storage_layout(project_root).studio_runtime_root.resolve()
    expected_root = runtime_root / "failed-campaign-runs" / failed_job_id
    if not recovery_path.is_relative_to(expected_root) or not recovery_path.is_file():
        raise ValueError("campaign retry proof is outside its governed recovery root")
    proof_sha256 = _file_sha256(recovery_path)
    if proof_sha256 != str(raw.get("proof_sha256") or "") or proof_sha256 != str(
        job.hash_locks.get("pre_performance_proof_sha256") or ""
    ):
        raise ValueError("campaign retry proof hash has drifted")
    try:
        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"campaign retry proof could not be read: {exc}") from exc
    if not isinstance(recovery, Mapping):
        raise ValueError("campaign retry proof must be a mapping")
    expected = {
        "schema": "alphaquest.pre-performance-campaign-retry/v1",
        "campaign_id": str(job.payload.get("campaign_id") or ""),
        "variant_id": str(job.payload.get("variant_id") or ""),
        "attempt_id": str(job.payload.get("attempt_id") or ""),
        "retry_index": 1,
        "failed_job_id": failed_job_id,
        "config_hash": str(gate.get("config_hash") or ""),
        "input_data_hash": str(gate.get("input_data_hash") or ""),
        "strategy_implementation_sha256": str(
            gate.get("strategy_implementation_sha256") or ""
        ),
        "strategy_certification_manifest_sha256": str(
            gate.get("strategy_certification_manifest_sha256") or ""
        ),
        "prior_resolution_sha256": str(raw.get("prior_resolution_sha256") or ""),
    }
    mismatches = [
        key for key, value in expected.items() if recovery.get(key) != value
    ]
    if mismatches:
        raise ValueError(
            "campaign retry proof identity mismatch: " + ", ".join(sorted(mismatches))
        )
    approval_path = Path(str(recovery.get("approval_path") or ""))
    if not approval_path.is_file() or _file_sha256(approval_path) != str(
        recovery.get("approval_sha256") or ""
    ):
        raise ValueError("campaign retry mechanics approval hash has drifted")
    archive = Path(str(recovery.get("archived_run_root") or "")).resolve()
    if not archive.is_relative_to(expected_root) or not archive.is_dir():
        raise ValueError("campaign retry archived run is missing or outside recovery root")
    if output_dir.exists():
        raise ValueError("campaign retry output path is not fresh")
    files = recovery.get("source_file_sha256")
    if not isinstance(files, Mapping) or any(
        not (archive / str(relative)).is_file()
        or _file_sha256(archive / str(relative)) != str(expected_hash)
        for relative, expected_hash in files.items()
    ):
        raise ValueError("campaign retry archived evidence hash mismatch")
    return dict(raw)


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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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


def _resolved_job_path(project_root: Path, value: Any, *, label: str) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"account assessment payload requires {label}")
    path = Path(raw)
    path = path.resolve() if path.is_absolute() else (project_root / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"account assessment {label} is missing: {path}")
    return path


def _account_assessment_trades(bundle: Any, bundle_path: Path, cfg: Mapping[str, Any]):
    """Load only hash-bound reporting artifacts and expose account simulator columns."""

    import pandas as pd

    report_root = bundle_path.parent.resolve()

    def load_status(status: Any, *, label: str):
        if not status.available or not status.path or not status.sha256:
            raise ValueError(f"account assessment requires available {label} evidence")
        path = (report_root / str(status.path)).resolve()
        if not path.is_relative_to(report_root) or not path.is_file():
            raise ValueError(f"account assessment {label} evidence is outside the finalized report")
        if _file_sha256(path) != status.sha256:
            raise ValueError(f"account assessment {label} evidence hash is stale")
        return pd.read_csv(path)

    frame = load_status(bundle.analysis_artifacts.trade_list, label="trade-list")
    if "session_date" not in frame:
        timestamp = next(
            (
                name
                for name in ("exit_timestamp", "exit_time", "entry_timestamp", "entry_time")
                if name in frame
            ),
            None,
        )
        if timestamp is not None:
            frame["session_date"] = pd.to_datetime(
                frame[timestamp], utc=True, errors="coerce"
            ).dt.date
    if "contracts" not in frame and "quantity" in frame:
        frame["contracts"] = frame["quantity"]
    if "forced_flatten_compliant" not in frame and "position_flat_before_deadline" in frame:
        frame["forced_flatten_compliant"] = frame["position_flat_before_deadline"]

    if "mae_currency" not in frame:
        if "mae_usd" in frame:
            frame["mae_currency"] = pd.to_numeric(frame["mae_usd"], errors="coerce").abs()
        else:
            excursion_column = next(
                (
                    name
                    for name in ("mae_points", "max_adverse_excursion", "mae")
                    if name in frame
                ),
                None,
            )
            excursion_source = excursion_column or ""
            if excursion_column is None and bundle.analysis_artifacts.mfe_mae.available:
                excursions = load_status(bundle.analysis_artifacts.mfe_mae, label="MAE/MFE")
                if "trade_id" in frame and "trade_id" in excursions and "mae" in excursions:
                    keep = [name for name in ("trade_id", "mae", "mae_source") if name in excursions]
                    frame = frame.merge(excursions[keep], on="trade_id", how="left", suffixes=("", "_audit"))
                    excursion_column = "mae"
                    sources = (
                        [str(item) for item in frame["mae_source"].dropna().unique()]
                        if "mae_source" in frame
                        else []
                    )
                    excursion_source = " ".join(sources)
            if excursion_column is not None:
                excursion = pd.to_numeric(frame[excursion_column], errors="coerce").abs()
                if any(token in excursion_source.casefold() for token in ("usd", "currency")):
                    frame["mae_currency"] = excursion
                else:
                    point_value = _account_point_value(cfg)
                    if point_value is not None and "contracts" in frame:
                        frame["max_adverse_excursion"] = excursion
                        frame["point_value"] = point_value
    return frame


def _account_point_value(cfg: Mapping[str, Any]) -> float | None:
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), Mapping) else {}
    for component in ("event", "entry"):
        binding = strategy.get(component) if isinstance(strategy.get(component), Mapping) else {}
        params = binding.get("params") if isinstance(binding.get("params"), Mapping) else {}
        value = params.get("point_value")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) > 0:
            return float(value)
    core = cfg.get("core") if isinstance(cfg.get("core"), Mapping) else {}
    value = core.get("point_value")
    return float(value) if isinstance(value, (int, float)) and float(value) > 0 else None


def _strategy_implementation_hash(cfg: Mapping[str, Any]) -> str | None:
    certification = cfg.get("strategy_certification")
    if not isinstance(certification, Mapping):
        return None
    value = str(certification.get("implementation_sha256") or "").strip()
    return value or None


def _matching_account_assessment_manifests(
    research_artifact_root: Path,
    *,
    campaign_id: str,
    variant_id: str,
    result_run_id: str,
) -> list[Path]:
    root = research_artifact_root.resolve() / "account_evaluations"
    latest: dict[tuple[str, str], tuple[str, Path]] = {}
    for path in sorted(root.rglob("evaluation_manifest.json")) if root.is_dir() else []:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(value, Mapping)
            and str(value.get("campaign_id") or "") == campaign_id
            and str(value.get("variant_id") or "") == variant_id
            and str(value.get("attempt_id") or "") == result_run_id
        ):
            key = (str(value.get("profile_id") or ""), str(value.get("profile_version") or ""))
            created_at = str(value.get("created_at") or "")
            previous = latest.get(key)
            if previous is None or (created_at, str(path)) > (previous[0], str(previous[1])):
                latest[key] = (created_at, path)
    return [latest[key][1] for key in sorted(latest)]


def _run_declared_campaign_variant(
    config_path: Path,
    project_root: Path,
    *,
    output_dir: Path,
    job_id: str,
    authoritative_parallel_workers: int,
    authoritative_core_grid_workers: int = 6,
    progress_callback: Callable[[Mapping[str, Any]], None] | None = None,
    cancellation_requested: Callable[[], bool] | None = None,
    _command_override: list[str] | None = None,
) -> dict[str, Any]:
    """Run one campaign in a dedicated, durably registered process group."""

    result_dir = process_registry_root(project_root).parent / "job-results"
    result_path = result_dir / f"{job_id}.json"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path.unlink(missing_ok=True)
    default_command = [
        sys.executable,
        "-m",
        "alphaquest.run_campaign_stages",
        "--config",
        str(config_path),
        "--out",
        str(output_dir),
        "--authoritative-parallel-workers",
        str(max(1, int(authoritative_parallel_workers))),
        "--authoritative-core-grid-workers",
        str(max(1, int(authoritative_core_grid_workers))),
        "--structured-progress",
        "--result-json",
        str(result_path),
    ]
    command = list(_command_override) if _command_override is not None else default_command
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module; governed config is the only input
        command,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    process_group_id = os.getpgid(process.pid)
    registry_path = register_process_group(
        project_root,
        job_id=job_id,
        leader_pid=process.pid,
        process_group_id=process_group_id,
        owner_pid=os.getpid(),
        command=command,
    )
    output_events: thread_queue.Queue[tuple[str, str | None]] = thread_queue.Queue()
    stdout_tail: deque[str] = deque(maxlen=30)
    stderr_tail: deque[str] = deque(maxlen=50)

    def drain(stream, label: str) -> None:
        if stream is not None:
            for raw_line in stream:
                output_events.put((label, raw_line.rstrip()))
        output_events.put((label, None))

    stdout_thread = threading.Thread(
        target=drain,
        args=(process.stdout, "stdout"),
        name=f"alphaquest-campaign-stdout-{job_id}",
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=drain,
        args=(process.stderr, "stderr"),
        name=f"alphaquest-campaign-stderr-{job_id}",
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    finished_streams: set[str] = set()
    last_registry_refresh = 0.0
    leader_exited_at: float | None = None
    try:
        while process.poll() is None or len(finished_streams) < 2:
            if cancellation_requested is not None and cancellation_requested():
                raise JobCancellationRequested("Studio user requested cancellation")
            if process.poll() is not None:
                leader_exited_at = leader_exited_at or time.monotonic()
                if time.monotonic() - leader_exited_at >= 1.0 and len(finished_streams) < 2:
                    remaining = process_group_members(process_group_id)
                    if remaining:
                        terminate_process_group(process_group_id)
                    break
            try:
                label, line = output_events.get(timeout=0.2)
            except thread_queue.Empty:
                label, line = "", ""
            if line is None:
                finished_streams.add(label)
            elif line:
                if label == "stderr":
                    stderr_tail.append(line)
                elif STRUCTURED_PROGRESS_PREFIX in line:
                    structured = line.split(STRUCTURED_PROGRESS_PREFIX, 1)[1]
                    try:
                        payload = json.loads(structured)
                    except json.JSONDecodeError as exc:
                        stderr_tail.append(f"invalid structured progress event: {exc}")
                    else:
                        if progress_callback is not None and isinstance(payload, dict):
                            progress_callback(payload)
                else:
                    stdout_tail.append(line)
            now = time.monotonic()
            if now - last_registry_refresh >= 1.0:
                refresh_process_group_record(registry_path)
                last_registry_refresh = now

        return_code = process.wait()
        stdout_thread.join(timeout=2.0)
        stderr_thread.join(timeout=2.0)
        remaining = process_group_members(process_group_id)
        if remaining:
            terminate_process_group(process_group_id)
            raise RuntimeError(
                "campaign runner exited while owned descendants remained: " + ", ".join(str(pid) for pid in remaining)
            )
        if return_code != 0:
            detail = "\n".join(list(stderr_tail or stdout_tail)[-30:])
            raise RuntimeError(f"declared campaign runner exited {return_code}: {detail}")
        if not result_path.is_file():
            detail = "\n".join(list(stderr_tail or stdout_tail)[-30:])
            raise RuntimeError(
                "declared campaign runner completed without a result payload" + (f": {detail}" if detail else "")
            )
        try:
            summary = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"declared campaign result payload is invalid: {exc}") from exc
        if not isinstance(summary, dict):
            raise RuntimeError("declared campaign result payload must be a mapping")
        return summary
    except BaseException:
        terminate_process_group(process_group_id)
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass
        stdout_thread.join(timeout=2.0)
        stderr_thread.join(timeout=2.0)
        raise
    finally:
        if not process_group_members(process_group_id):
            unregister_process_group(registry_path)
        result_path.unlink(missing_ok=True)


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
        raise RuntimeError(f"declared mechanics-validation runner exited {return_code}: {detail}")
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
