"""Transactional Studio reporting and run-finalization services.

The staged runner remains authoritative for scientific execution.  This module
adds a small, atomic reporting transaction around the artifacts it produced:

* build and validate ``ResultBundleV2`` in a same-filesystem staging directory;
* hash the evidence used by the report;
* atomically publish the complete reporting directory;
* append one idempotent terminal ledger event; and
* refresh rebuildable indexes only after durable reporting exists.

The recovery journal is deliberately outside immutable evidence.  A worker
crash never causes this module (or the queue) to replay a research attempt.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping, Sequence

import pandas as pd
import yaml

from alphaquest.research.campaign_stages import DEFAULT_STAGE_ORDER, update_source_results_index
from alphaquest.research.registry import build_registry, export_registry_csvs, generate_views
from alphaquest.research.storage import display_path, load_storage_layout
from alphaquest.studio.results import (
    RESULT_BUNDLE_FILENAME,
    MetricValueV2,
    ResultBundleBuilder,
    ResultBundleV2,
    StageCriterionV2,
    load_result_bundle,
)


FINALIZATION_SCHEMA = "alphaquest.studio-finalization/v1"
RECOVERY_JOURNAL_SCHEMA = "alphaquest.studio-recovery-journal/v1"
REPORTING_DIRECTORY = "reporting_v2"
FINALIZATION_MANIFEST = "finalization_manifest.json"
METHODOLOGY_AUDIT = "methodology_audit.md"
INCOMPLETE_ATTEMPT_MARKER = "studio_incomplete_attempt.json"

LEDGER_FIELDS = (
    "timestamp",
    "campaign_id",
    "variant_id",
    "instrument",
    "timeframe",
    "edge",
    "variant_mechanic",
    "parameter_space",
    "data_scope",
    "config_path",
    "report_path",
    "stage",
    "result",
    "decision",
    "failure_reason",
    "rescue_attempt",
)

_CANDIDATE_PACKAGE_FILES = (
    "candidate_strategy_report.md",
    "manual_due_diligence_checklist.md",
    "final_config.yaml",
    "final_trade_log.csv",
    "validation_trade_log.csv",
    "final_equity_curve.csv",
    "WFA_trade_log.csv",
    "MonteCarlo_summary.json",
    "candidate_review.json",
    f"{REPORTING_DIRECTORY}/candidate_review.json",
)

RegistryRefresher = Callable[[Path], Mapping[str, Any]]
SourceIndexRefresher = Callable[[Path, dict[str, Any], dict[str, Any]], Path | None]


class FinalizationError(RuntimeError):
    """A reserved attempt could not be finalized safely."""


@dataclass(frozen=True)
class FinalizationResult:
    """Durable pointers returned to the queue after finalization."""

    job_id: str
    run_dir: Path
    reporting_dir: Path
    result_bundle_path: Path
    finalization_manifest_path: Path
    recovery_journal_path: Path
    research_verdict: str
    ledger_appended: bool
    registry_counts: dict[str, Any]
    artifact_hashes: dict[str, str]
    idempotent_reuse: bool = False

    def as_job_result(self, *, project_root: str | Path) -> dict[str, Any]:
        root = Path(project_root).resolve()
        return {
            "research_verdict": self.research_verdict,
            "run_dir": display_path(self.run_dir, root),
            "reporting_dir": display_path(self.reporting_dir, root),
            "result_bundle_path": display_path(self.result_bundle_path, root),
            "finalization_manifest_path": display_path(self.finalization_manifest_path, root),
            "recovery_journal_path": display_path(self.recovery_journal_path, root),
            "ledger_appended": self.ledger_appended,
            "registry_counts": self.registry_counts,
            "artifact_hashes": self.artifact_hashes,
            "idempotent_reuse": self.idempotent_reuse,
        }


def inspect_finalized_result(
    result_bundle_path: str | Path,
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Verify that a ResultBundleV2 belongs to a complete immutable transaction.

    Candidate review and result presentation must never trust a bundle in
    isolation: the adjacent finalization manifest binds the bundle to its
    source evidence, live frozen config, ledger/index publication, and hashes.
    """

    errors: list[str] = []
    bundle_path = Path(result_bundle_path).resolve()
    reporting_dir = bundle_path.parent
    run_dir = reporting_dir.parent
    manifest_path = reporting_dir / FINALIZATION_MANIFEST
    bundle: ResultBundleV2 | None = None
    manifest: dict[str, Any] | None = None
    try:
        bundle = load_result_bundle(bundle_path)
    except (OSError, ValueError) as exc:
        errors.append(f"ResultBundleV2 is invalid: {exc}")
    try:
        manifest = _read_json_mapping(manifest_path)
    except (OSError, ValueError) as exc:
        errors.append(f"finalization manifest is missing or invalid: {exc}")

    if manifest is not None:
        if manifest.get("schema") != FINALIZATION_SCHEMA:
            errors.append("finalization manifest schema is not AlphaQuest Studio v1")
        if manifest.get("automatic_replay_permitted") is not False:
            errors.append("finalization manifest must forbid automatic replay")
        if manifest.get("transaction_complete") is not True:
            errors.append("finalization transaction is incomplete")
        if manifest.get("ledger_recorded") is not True:
            errors.append("terminal ledger publication is incomplete")
        if manifest.get("registry_published") is not True or not isinstance(
            manifest.get("registry_counts"), Mapping
        ):
            errors.append("registry publication is incomplete")
        if manifest.get("terminal_recovery_phase") != "FINALIZED":
            errors.append("finalization lacks terminal recovery-journal binding")
        journal_value = manifest.get("recovery_journal")
        journal_hash = str(manifest.get("terminal_recovery_journal_sha256") or "")
        if not journal_value or len(journal_hash) != 64:
            errors.append("terminal recovery-journal path or hash is missing")
        else:
            journal_path = Path(str(journal_value))
            if not journal_path.is_absolute():
                journal_path = _result_project_root(run_dir, manifest=manifest) / journal_path
            try:
                _validate_terminal_recovery_journal(
                    journal_path,
                    job_id=str(manifest.get("job_id") or ""),
                )
                if _file_sha256(journal_path) != journal_hash:
                    errors.append("terminal recovery-journal hash drifted")
            except (OSError, ValueError, FinalizationError) as exc:
                errors.append(f"terminal recovery-journal binding is invalid: {exc}")
        if str(manifest.get("result_bundle") or "") != RESULT_BUNDLE_FILENAME:
            errors.append("finalization manifest does not identify ResultBundleV2")
        if (run_dir / INCOMPLETE_ATTEMPT_MARKER).is_file():
            errors.append("the reserved attempt is marked incomplete")
        if bundle is not None:
            expected_identity = {
                "campaign_id": bundle.campaign_id,
                "variant_id": bundle.variant_id,
                "run_id": bundle.run_id,
                "research_verdict": bundle.verdict,
            }
            mismatches = [
                key
                for key, expected in expected_identity.items()
                if str(manifest.get(key) or "") != str(expected)
            ]
            if mismatches:
                errors.append("finalization identity/verdict mismatch: " + ", ".join(mismatches))
            if bundle.verdict == "PASS" and list(manifest.get("evidence_issues") or []):
                errors.append("PASS finalization records unresolved evidence issues")
        _verify_manifest_hashes(
            manifest.get("reporting_artifact_sha256"),
            base=reporting_dir,
            label="reporting",
            errors=errors,
        )
        _verify_manifest_hashes(
            manifest.get("evidence_artifact_sha256"),
            base=run_dir,
            label="source evidence",
            errors=errors,
        )
        if config_path is not None:
            source = str(manifest.get("source_config") or "").strip()
            configured = Path(config_path).resolve()
            if not source:
                errors.append("finalization manifest does not record source_config")
            else:
                source_path = Path(source)
                if source_path.is_absolute():
                    matches_source = source_path.resolve() == configured
                else:
                    matches_source = configured.as_posix().endswith("/" + source_path.as_posix().lstrip("./"))
                if not matches_source:
                    errors.append("candidate config does not match finalized source_config")

    return {
        "valid": not errors,
        "errors": errors,
        "bundle": bundle,
        "manifest": manifest,
        "manifest_path": manifest_path,
    }


def _result_project_root(run_dir: Path, *, manifest: Mapping[str, Any] | None = None) -> Path:
    recorded_run = str((manifest or {}).get("run_dir") or "").strip()
    if recorded_run and not Path(recorded_run).is_absolute():
        for parent in (run_dir, *run_dir.parents):
            if (parent / recorded_run).resolve() == run_dir.resolve():
                return parent
    for parent in (run_dir, *run_dir.parents):
        if (parent / "config" / "storage_layout.yaml").is_file():
            return parent
    return Path.cwd().resolve()


def _verify_manifest_hashes(
    raw_hashes: Any,
    *,
    base: Path,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(raw_hashes, Mapping) or not raw_hashes:
        errors.append(f"{label} artifact hashes are missing")
        return
    root = base.resolve()
    for relative, expected in sorted(raw_hashes.items()):
        path = (root / str(relative)).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"{label} artifact path escapes its immutable root: {relative}")
            continue
        if not path.is_file():
            errors.append(f"hashed {label} artifact is missing: {relative}")
        elif _file_sha256(path) != str(expected):
            errors.append(f"hashed {label} artifact drifted: {relative}")


class RunFinalizer:
    """Build and atomically publish Studio reporting for one staged run."""

    def __init__(
        self,
        project_root: str | Path = ".",
        *,
        registry_refresher: RegistryRefresher | None = None,
        source_index_refresher: SourceIndexRefresher | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = load_storage_layout(self.project_root)
        self.registry_refresher = registry_refresher or _refresh_registry
        self.source_index_refresher = source_index_refresher or _refresh_source_index

    def recovery_journal_path(self, job_id: str) -> Path:
        return self.layout.studio_runtime_root / "recovery" / f"{_safe_identifier(job_id)}.json"

    def record_recovery_phase(
        self,
        job_id: str,
        phase: str,
        *,
        details: Mapping[str, Any] | None = None,
        terminal: bool = False,
    ) -> Path:
        """Persist an idempotent, append-by-phase recovery journal."""

        path = self.recovery_journal_path(job_id)
        existing = _read_json_mapping(path) if path.is_file() else {}
        created_at = existing.get("created_at") or _now_iso()
        events = existing.get("events") if isinstance(existing.get("events"), list) else []
        normalized_details = _json_safe_mapping(details or {})
        event = {"phase": str(phase), "recorded_at": _now_iso(), "details": normalized_details}
        if not events or events[-1].get("phase") != event["phase"] or events[-1].get("details") != normalized_details:
            events.append(event)
        payload = {
            "schema": RECOVERY_JOURNAL_SCHEMA,
            "job_id": job_id,
            "created_at": created_at,
            "updated_at": event["recorded_at"],
            "phase": str(phase),
            "terminal": bool(terminal),
            "automatic_replay_permitted": False,
            "events": events,
        }
        _atomic_write_json(path, payload)
        return path

    def abort_reserved_attempt(
        self,
        *,
        job_id: str,
        config_path: str | Path,
        run_dir: str | Path,
        reason: str,
        operational_state: str = "FAILED_OPERATIONAL",
        publish_ledger: bool = True,
    ) -> Path:
        """Durably fail closed after the irreversible attempt reservation.

        This hook never replays a runner.  It preserves whatever staged
        evidence exists, removes candidate conveniences, and publishes a
        separate append-only NMR event plus a source-index override when those
        rebuildable surfaces are available.
        """

        cfg_path = _resolve_path(config_path, self.project_root)
        cfg = _read_yaml_mapping(cfg_path)
        output = _resolve_path(run_dir, self.project_root)
        output.mkdir(parents=True, exist_ok=True)
        marker_path = output / INCOMPLETE_ATTEMPT_MARKER
        message = str(reason).strip() or "reserved Studio attempt ended before complete finalization"
        summary = _incomplete_attempt_summary(
            output,
            cfg_path=cfg_path,
            cfg=cfg,
            job_id=job_id,
            reason=message,
        )
        marker = {
            "schema": "alphaquest.studio-incomplete-attempt/v1",
            "job_id": job_id,
            "campaign_id": summary.get("campaign_id"),
            "variant_id": summary.get("variant_id"),
            "run_id": summary.get("test_run_id"),
            "attempt_id": summary.get("attempt_id"),
            "attempt_reserved": True,
            "operational_state": operational_state,
            "research_verdict": "NEEDS MANUAL REVIEW",
            "reason": message,
            "next_action": (
                "Inspect the preserved partial evidence, then create an explicit replication, "
                "data refresh, methodology rerun, pre-PnL mechanics correction, or authorized rescue."
            ),
            "automatic_replay_permitted": False,
            "source_config": display_path(cfg_path, self.project_root),
            "run_dir": display_path(output, self.project_root),
            "recorded_at": _now_iso(),
            "publication_errors": [],
        }
        _atomic_write_json(marker_path, marker)
        _suppress_candidate_package(output)

        publication_errors: list[str] = []
        ledger_appended = False
        source_index: Path | None = None
        registry_counts: dict[str, Any] = {}
        authoritative = _authoritative_summary(
            summary,
            verdict="NEEDS MANUAL REVIEW",
            finalization_state="INCOMPLETE",
            incomplete_marker_path=marker_path,
        )
        if publish_ledger:
            try:
                ledger_appended = _append_incomplete_ledger_event(
                    self.project_root / "research_ledger.csv",
                    cfg_path=cfg_path,
                    cfg=cfg,
                    summary=authoritative,
                    marker_path=marker_path,
                    reason=message,
                    project_root=self.project_root,
                )
            except Exception as exc:  # marker publication must survive auxiliary failures
                publication_errors.append(f"ledger: {type(exc).__name__}: {exc}")
        else:
            publication_errors.append(
                "ledger: incomplete event was not appended because terminal-row rollback failed"
            )
        try:
            source_index = self.source_index_refresher(cfg_path, cfg, authoritative)
        except Exception as exc:
            publication_errors.append(f"source results index: {type(exc).__name__}: {exc}")
        try:
            registry_counts = dict(self.registry_refresher(self.project_root))
        except Exception as exc:
            publication_errors.append(f"registry refresh: {type(exc).__name__}: {exc}")

        marker.update(
            {
                "ledger_appended": ledger_appended,
                "source_results_index": (
                    display_path(source_index, self.project_root) if source_index is not None else None
                ),
                "registry_counts": registry_counts,
                "publication_errors": publication_errors,
            }
        )
        _atomic_write_json(marker_path, marker)
        self.record_recovery_phase(
            job_id,
            "ATTEMPT_INCOMPLETE",
            details={
                "research_verdict": "NEEDS MANUAL REVIEW",
                "reason": message,
                "marker": display_path(marker_path, self.project_root),
                "publication_errors": publication_errors,
            },
            terminal=True,
        )
        return marker_path

    def finalize(
        self,
        *,
        job_id: str,
        config_path: str | Path,
        summary: Mapping[str, Any],
    ) -> FinalizationResult:
        """Finalize one completed staged run without replaying any execution."""

        cfg_path = _resolve_path(config_path, self.project_root)
        cfg = _read_yaml_mapping(cfg_path)
        run_summary = _json_safe_mapping(summary)
        run_dir = _resolve_run_dir(run_summary, self.project_root)
        reporting_dir = run_dir / REPORTING_DIRECTORY
        manifest_path = reporting_dir / FINALIZATION_MANIFEST
        journal_path = self.recovery_journal_path(job_id)

        if (run_dir / INCOMPLETE_ATTEMPT_MARKER).is_file():
            _suppress_candidate_package(run_dir)
            raise FinalizationError(
                "reserved attempt is already marked incomplete; automatic finalization or replay is forbidden"
            )

        if reporting_dir.exists():
            return self._reuse_completed(
                job_id=job_id,
                cfg_path=cfg_path,
                cfg=cfg,
                summary=run_summary,
                run_dir=run_dir,
                reporting_dir=reporting_dir,
                manifest_path=manifest_path,
                journal_path=journal_path,
            )

        journal_path = self.record_recovery_phase(
            job_id,
            "RUNNER_COMPLETED",
            details={"run_dir": display_path(run_dir, self.project_root)},
        )

        if not run_dir.is_dir():
            self.record_recovery_phase(
                job_id,
                "FINALIZATION_FAILED",
                details={"error": f"staged run directory does not exist: {run_dir}"},
                terminal=True,
            )
            raise FinalizationError(f"staged run directory does not exist: {run_dir}")

        staging = run_dir / f".{REPORTING_DIRECTORY}.{_safe_identifier(job_id)}.tmp"
        if staging.exists():
            # A stale staging directory is partial evidence from an interrupted
            # finalization, never a completed result.  It is safe to replace
            # because the queue does not replay the staged research attempt.
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        try:
            evidence_issues, evidence_hashes = _validate_and_hash_runner_evidence(run_dir, run_summary)
            stage_criteria = _stage_criteria(run_summary)
            original_verdict = _strict_verdict(run_summary.get("research_verdict"))
            verdict = _final_verdict(original_verdict, evidence_issues, run_summary)
            trades, trade_path, trade_issue = _load_reporting_trades(run_dir, original_verdict)
            if trade_issue:
                evidence_issues.append(trade_issue)
                if original_verdict == "PASS":
                    verdict = "NEEDS MANUAL REVIEW"
                stage_criteria.append(_reporting_criterion(trade_issue))
            evaluation = _reporting_evaluation_contract(run_dir, trade_path)

            optional_frames, supplemental_issues = _supplemental_frames(run_dir)
            if original_verdict == "PASS" and supplemental_issues:
                evidence_issues.extend(supplemental_issues)
                verdict = "NEEDS MANUAL REVIEW"
                stage_criteria.extend(_reporting_criterion(issue) for issue in supplemental_issues)
            generated_at = _journal_created_at(journal_path)
            try:
                bundle = ResultBundleBuilder().build_and_write(
                    trades,
                    staging,
                    campaign_id=str(run_summary.get("campaign_id") or cfg.get("campaign_id") or ""),
                    variant_id=str(run_summary.get("variant_id") or cfg.get("variant_id") or ""),
                    run_id=str(
                        run_summary.get("test_run_id")
                        or run_summary.get("run_uid")
                        or cfg.get("test_run_id")
                        or job_id
                    ),
                    verdict=verdict,  # type: ignore[arg-type]
                    stage_criteria=stage_criteria,
                    initial_balance=float((cfg.get("core") or {}).get("initial_balance") or 0.0),
                    parameter_neighbors=optional_frames["parameter_neighbors"],
                    wfa_stitched_oos=optional_frames["wfa_stitched_oos"],
                    monte_carlo_summary=optional_frames["monte_carlo_summary"],
                    generated_at=generated_at,
                    exchange_timezone=_config_exchange_timezone(cfg),
                    evaluation_start=evaluation["start"],
                    evaluation_end=evaluation["end"],
                    trading_dates=evaluation["trading_dates"],
                )
            except Exception as exc:
                # Reporting ambiguity must not preserve a PASS.  Publish a
                # strict, inspectable NMR bundle when the malformed trade
                # artifact itself cannot be summarized.
                evidence_issues.append(f"ResultBundleV2 construction failed: {type(exc).__name__}: {exc}")
                verdict = "NEEDS MANUAL REVIEW"
                shutil.rmtree(staging)
                staging.mkdir(parents=True)
                bundle = ResultBundleBuilder().build_and_write(
                    _empty_trade_frame(),
                    staging,
                    campaign_id=str(run_summary.get("campaign_id") or cfg.get("campaign_id") or "unknown"),
                    variant_id=str(run_summary.get("variant_id") or cfg.get("variant_id") or "unknown"),
                    run_id=str(run_summary.get("test_run_id") or run_summary.get("run_uid") or job_id),
                    verdict="NEEDS MANUAL REVIEW",
                    stage_criteria=[*stage_criteria, _reporting_criterion(evidence_issues[-1])],
                    initial_balance=float((cfg.get("core") or {}).get("initial_balance") or 0.0),
                    parameter_neighbors=_empty_frame(("reason",)),
                    wfa_stitched_oos=_empty_trade_frame(),
                    monte_carlo_summary=_empty_frame(("reason",)),
                    generated_at=generated_at,
                    exchange_timezone=_config_exchange_timezone(cfg),
                    evaluation_start=evaluation["start"],
                    evaluation_end=evaluation["end"],
                    trading_dates=evaluation["trading_dates"],
                )

            _validate_reporting_directory(staging, bundle)
            generated_hashes = _hash_files(staging, exclude={FINALIZATION_MANIFEST})
            audit = _methodology_audit(
                run_summary,
                bundle,
                evidence_issues=evidence_issues,
                trade_path=trade_path,
            )
            (staging / METHODOLOGY_AUDIT).write_text(audit, encoding="utf-8")
            generated_hashes[METHODOLOGY_AUDIT] = _file_sha256(staging / METHODOLOGY_AUDIT)
            manifest = {
                "schema": FINALIZATION_SCHEMA,
                "job_id": job_id,
                "campaign_id": bundle.campaign_id,
                "variant_id": bundle.variant_id,
                "run_id": bundle.run_id,
                "research_verdict": bundle.verdict,
                "finalized_at": _now_iso(),
                "automatic_replay_permitted": False,
                "source_config": display_path(cfg_path, self.project_root),
                "run_dir": display_path(run_dir, self.project_root),
                "result_bundle": RESULT_BUNDLE_FILENAME,
                "recovery_journal": display_path(journal_path, self.project_root),
                "evidence_issues": evidence_issues,
                "evidence_artifact_sha256": evidence_hashes,
                "reporting_artifact_sha256": generated_hashes,
                "registry_published": False,
                "terminal_recovery_phase": None,
                "terminal_recovery_journal_sha256": None,
                "transaction_complete": False,
            }
            _atomic_write_json(staging / FINALIZATION_MANIFEST, manifest)
            _validate_finalization_manifest(staging / FINALIZATION_MANIFEST, job_id=job_id)
            self.record_recovery_phase(
                job_id,
                "REPORTING_VALIDATED",
                details={
                    "research_verdict": bundle.verdict,
                    "evidence_artifact_count": len(evidence_hashes),
                    "reporting_artifact_count": len(generated_hashes) + 1,
                },
            )
            os.replace(staging, reporting_dir)
            _fsync_directory(run_dir)
        except Exception as exc:
            self.abort_reserved_attempt(
                job_id=job_id,
                config_path=cfg_path,
                run_dir=run_dir,
                reason=f"finalization failed: {type(exc).__name__}: {exc}",
            )
            self.record_recovery_phase(
                job_id,
                "FINALIZATION_FAILED",
                details={"error": f"{type(exc).__name__}: {exc}"},
                terminal=True,
            )
            raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)

        bundle = load_result_bundle(reporting_dir / RESULT_BUNDLE_FILENAME)
        if bundle.verdict != "PASS":
            _suppress_candidate_package(run_dir)
        authoritative_summary = _authoritative_summary(
            run_summary,
            verdict=bundle.verdict,
            finalization_state="COMPLETE",
            result_bundle_path=reporting_dir / RESULT_BUNDLE_FILENAME,
        )
        ledger_path = self.project_root / "research_ledger.csv"
        ledger_checkpoint = _capture_file_checkpoint(ledger_path)
        try:
            ledger_appended = _append_terminal_ledger_event(
                ledger_path,
                cfg_path=cfg_path,
                cfg=cfg,
                summary=authoritative_summary,
                bundle=bundle,
                report_path=reporting_dir / RESULT_BUNDLE_FILENAME,
                project_root=self.project_root,
            )
            source_index = self.source_index_refresher(cfg_path, cfg, authoritative_summary)
            manifest = _read_json_mapping(reporting_dir / FINALIZATION_MANIFEST)
            manifest["ledger_appended"] = ledger_appended
            manifest["ledger_recorded"] = True
            manifest["source_results_index"] = (
                display_path(source_index, self.project_root) if source_index is not None else None
            )
            manifest["registry_published"] = False
            manifest["transaction_complete"] = False
            _atomic_write_json(reporting_dir / FINALIZATION_MANIFEST, manifest)
            registry_counts = dict(self.registry_refresher(self.project_root))
            manifest["registry_counts"] = registry_counts
            manifest["registry_published"] = True
            _atomic_write_json(reporting_dir / FINALIZATION_MANIFEST, manifest)
            self.record_recovery_phase(
                job_id,
                "FINALIZED",
                details={
                    "research_verdict": bundle.verdict,
                    "reporting_dir": display_path(reporting_dir, self.project_root),
                    "ledger_appended": ledger_appended,
                },
                terminal=True,
            )
            terminal_journal = _validate_terminal_recovery_journal(journal_path, job_id=job_id)
            manifest["terminal_recovery_phase"] = terminal_journal["phase"]
            manifest["terminal_recovery_journal_sha256"] = _file_sha256(journal_path)
            manifest["transaction_completed_at"] = _now_iso()
            manifest["transaction_complete"] = True
            _atomic_write_json(reporting_dir / FINALIZATION_MANIFEST, manifest)
            # Rebuild once more after the complete manifest and terminal journal
            # binding are visible, so registry inspection publishes the final
            # ResultBundle verdict rather than the provisional fail-closed NMR.
            registry_counts = dict(self.registry_refresher(self.project_root))
            _validate_finalization_manifest(
                reporting_dir / FINALIZATION_MANIFEST,
                job_id=job_id,
                journal_path=journal_path,
            )
        except Exception as exc:
            # Reporting exists but the finalization transaction is incomplete.
            # Suppress candidate convenience artifacts until an explicit human
            # recovery call completes ledger/index publication.
            _suppress_candidate_package(run_dir)
            incomplete = _read_json_mapping(reporting_dir / FINALIZATION_MANIFEST)
            incomplete["transaction_complete"] = False
            incomplete["transaction_error"] = f"{type(exc).__name__}: {exc}"
            _atomic_write_json(reporting_dir / FINALIZATION_MANIFEST, incomplete)
            rollback_error: Exception | None = None
            try:
                _restore_file_checkpoint(ledger_path, ledger_checkpoint)
            except Exception as rollback_exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_error = rollback_exc
            self.abort_reserved_attempt(
                job_id=job_id,
                config_path=cfg_path,
                run_dir=run_dir,
                reason=(
                    f"post-publication finalization failed: {type(exc).__name__}: {exc}"
                    + (
                        f"; terminal ledger rollback failed: {type(rollback_error).__name__}: "
                        f"{rollback_error}"
                        if rollback_error is not None
                        else ""
                    )
                ),
                publish_ledger=rollback_error is None,
            )
            self.record_recovery_phase(
                job_id,
                "FINALIZATION_FAILED",
                details={
                    "error": f"post-publication finalization failed: {type(exc).__name__}: {exc}",
                    "reporting_dir": display_path(reporting_dir, self.project_root),
                },
                terminal=True,
            )
            raise FinalizationError(f"post-publication finalization failed: {exc}") from exc

        manifest = _read_json_mapping(reporting_dir / FINALIZATION_MANIFEST)
        artifact_hashes = {
            **dict(manifest.get("evidence_artifact_sha256") or {}),
            **{
                f"{REPORTING_DIRECTORY}/{key}": value
                for key, value in dict(manifest.get("reporting_artifact_sha256") or {}).items()
            },
        }
        return FinalizationResult(
            job_id=job_id,
            run_dir=run_dir,
            reporting_dir=reporting_dir,
            result_bundle_path=reporting_dir / RESULT_BUNDLE_FILENAME,
            finalization_manifest_path=reporting_dir / FINALIZATION_MANIFEST,
            recovery_journal_path=journal_path,
            research_verdict=bundle.verdict,
            ledger_appended=ledger_appended,
            registry_counts=registry_counts,
            artifact_hashes=artifact_hashes,
        )

    def _reuse_completed(
        self,
        *,
        job_id: str,
        cfg_path: Path,
        cfg: dict[str, Any],
        summary: dict[str, Any],
        run_dir: Path,
        reporting_dir: Path,
        manifest_path: Path,
        journal_path: Path,
    ) -> FinalizationResult:
        manifest = _validate_finalization_manifest(
            manifest_path,
            job_id=job_id,
            journal_path=journal_path,
        )
        bundle_path = reporting_dir / RESULT_BUNDLE_FILENAME
        bundle = load_result_bundle(bundle_path)
        _validate_reporting_hashes(reporting_dir, manifest)
        authoritative_summary = _authoritative_summary(
            summary,
            verdict=bundle.verdict,
            finalization_state="COMPLETE",
            result_bundle_path=bundle_path,
        )
        if bundle.verdict != "PASS":
            _suppress_candidate_package(run_dir)
        ledger_appended = False
        if not bool(manifest.get("transaction_complete")):
            ledger_path = self.project_root / "research_ledger.csv"
            ledger_checkpoint = _capture_file_checkpoint(ledger_path)
            try:
                ledger_appended = _append_terminal_ledger_event(
                    ledger_path,
                    cfg_path=cfg_path,
                    cfg=cfg,
                    summary=authoritative_summary,
                    bundle=bundle,
                    report_path=bundle_path,
                    project_root=self.project_root,
                )
                source_index = self.source_index_refresher(cfg_path, cfg, authoritative_summary)
                manifest["ledger_appended"] = ledger_appended
                manifest["ledger_recorded"] = True
                manifest["source_results_index"] = (
                    display_path(source_index, self.project_root) if source_index is not None else None
                )
                manifest["registry_published"] = False
                manifest["transaction_complete"] = False
                _atomic_write_json(manifest_path, manifest)
                registry_counts = dict(self.registry_refresher(self.project_root))
                manifest["registry_counts"] = registry_counts
                manifest["registry_published"] = True
                _atomic_write_json(manifest_path, manifest)
                self.record_recovery_phase(
                    job_id,
                    "FINALIZED",
                    details={
                        "research_verdict": bundle.verdict,
                        "reporting_dir": display_path(reporting_dir, self.project_root),
                        "idempotent_reuse": True,
                    },
                    terminal=True,
                )
                terminal_journal = _validate_terminal_recovery_journal(journal_path, job_id=job_id)
                manifest["terminal_recovery_phase"] = terminal_journal["phase"]
                manifest["terminal_recovery_journal_sha256"] = _file_sha256(journal_path)
                manifest["transaction_completed_at"] = _now_iso()
                manifest["transaction_complete"] = True
                _atomic_write_json(manifest_path, manifest)
                registry_counts = dict(self.registry_refresher(self.project_root))
                _validate_finalization_manifest(
                    manifest_path,
                    job_id=job_id,
                    journal_path=journal_path,
                )
            except Exception as exc:
                manifest["transaction_complete"] = False
                manifest["transaction_error"] = f"{type(exc).__name__}: {exc}"
                _atomic_write_json(manifest_path, manifest)
                rollback_error: Exception | None = None
                try:
                    _restore_file_checkpoint(ledger_path, ledger_checkpoint)
                except Exception as rollback_exc:  # pragma: no cover - catastrophic filesystem failure
                    rollback_error = rollback_exc
                self.abort_reserved_attempt(
                    job_id=job_id,
                    config_path=cfg_path,
                    run_dir=run_dir,
                    reason=(
                        f"explicit finalization recovery failed: {type(exc).__name__}: {exc}"
                        + (
                            f"; terminal ledger rollback failed: {type(rollback_error).__name__}: "
                            f"{rollback_error}"
                            if rollback_error is not None
                            else ""
                        )
                    ),
                    publish_ledger=rollback_error is None,
                )
                self.record_recovery_phase(
                    job_id,
                    "FINALIZATION_FAILED",
                    details={"error": f"explicit recovery failed: {type(exc).__name__}: {exc}"},
                    terminal=True,
                )
                raise FinalizationError(f"explicit finalization recovery failed: {exc}") from exc
        hashes = {
            **dict(manifest.get("evidence_artifact_sha256") or {}),
            **{
                f"{REPORTING_DIRECTORY}/{key}": value
                for key, value in dict(manifest.get("reporting_artifact_sha256") or {}).items()
            },
        }
        return FinalizationResult(
            job_id=job_id,
            run_dir=run_dir,
            reporting_dir=reporting_dir,
            result_bundle_path=bundle_path,
            finalization_manifest_path=manifest_path,
            recovery_journal_path=journal_path,
            research_verdict=bundle.verdict,
            ledger_appended=ledger_appended,
            registry_counts=dict(manifest.get("registry_counts") or {}),
            artifact_hashes=hashes,
            idempotent_reuse=True,
        )


def _validate_and_hash_runner_evidence(
    run_dir: Path,
    summary: Mapping[str, Any],
) -> tuple[list[str], dict[str, str]]:
    issues: list[str] = []
    required = [
        "campaign_test_summary.json",
        "variant_test_summary.json",
        "run_manifest.json",
        "effective_config.yaml",
        "source_config.yaml",
    ]
    paths: list[Path] = []
    for relative in required:
        path = run_dir / relative
        if not path.is_file():
            issues.append(f"required staged artifact is missing: {relative}")
        else:
            paths.append(path)

    stages = summary.get("stages") if isinstance(summary.get("stages"), list) else []
    for stage in stages:
        if not isinstance(stage, Mapping):
            issues.append("stage summary contains a non-mapping record")
            continue
        name = str(stage.get("stage") or "")
        status = str(stage.get("status") or "")
        if not name:
            issues.append("stage summary is missing its stage name")
            continue
        stage_result = run_dir / name / "stage_result.json"
        if status != "skipped":
            if not stage_result.is_file():
                issues.append(f"stage result is missing for {name}")
            else:
                paths.append(stage_result)

    # Hash every source artifact that can feed ResultBundleV2, not only the
    # top-level summaries.  Missing inputs are evaluated separately because a
    # scientific FAIL may legitimately stop before later robustness stages.
    reporting_inputs = (
        "acceptance_oos_test/trade_log.csv",
        "simulated_incubation_core/trade_log.csv",
        "walk_forward_analysis/wfa_oos_trade_log.csv",
        "limited_core_grid_test/fixed_config_core_trade_log.csv",
        "limited_core_grid_test/core_grid_results.csv",
        "limited_core_grid_test/core_grid_summary.json",
        "limited_core_grid_test/validation/tradingview_comparison.csv",
        "walk_forward_analysis/wfa_results.csv",
        "walk_forward_analysis/validation/tradingview_comparison.csv",
        "simulated_incubation_core/incubation_oos_summary.json",
        "simulated_incubation_core/validation/tradingview_comparison.csv",
        "acceptance_oos_test/acceptance_oos_summary.json",
        "acceptance_oos_test/validation/tradingview_comparison.csv",
        "wfa_oos_monte_carlo/wfa_oos_monte_carlo_summary.json",
    )
    paths.extend(path for relative in reporting_inputs if (path := run_dir / relative).is_file())

    for path in paths:
        if path.suffix == ".json":
            try:
                _read_strict_json(path)
            except ValueError as exc:
                issues.append(str(exc))

    return issues, {
        str(path.relative_to(run_dir)): _file_sha256(path)
        for path in sorted(set(paths))
        if path.is_file()
    }


def _final_verdict(original: str, issues: Sequence[str], summary: Mapping[str, Any]) -> str:
    if issues:
        return "NEEDS MANUAL REVIEW"
    if bool(summary.get("diagnostic_only")):
        return "NEEDS MANUAL REVIEW"
    stages = summary.get("stages") if isinstance(summary.get("stages"), list) else []
    names = [str(item.get("stage") or "") for item in stages if isinstance(item, Mapping)]
    statuses = [str(item.get("status") or "") for item in stages if isinstance(item, Mapping)]
    if original == "PASS" and (names != list(DEFAULT_STAGE_ORDER) or statuses != ["passed"] * len(DEFAULT_STAGE_ORDER)):
        return "NEEDS MANUAL REVIEW"
    return original


def _stage_criteria(summary: Mapping[str, Any]) -> list[StageCriterionV2]:
    output: list[StageCriterionV2] = []
    stages = summary.get("stages") if isinstance(summary.get("stages"), list) else []
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        name = str(stage.get("stage") or "unknown_stage")
        status = str(stage.get("status") or "unknown")
        items = stage.get("criteria") if isinstance(stage.get("criteria"), list) else []
        if not items:
            result = "PASS" if status == "passed" else ("FAIL" if status == "failed" else "NEEDS MANUAL REVIEW")
            reason = str(stage.get("error") or stage.get("skip_reason") or f"stage status is {status}")
            output.append(
                StageCriterionV2(
                    stage=name,
                    metric="stage_status",
                    operator="==",
                    threshold=MetricValueV2(value="passed"),
                    actual=MetricValueV2(value=status),
                    result=result,  # type: ignore[arg-type]
                    reason=reason,
                    evidence_path=f"{name}/stage_result.json" if status != "skipped" else None,
                )
            )
            continue
        for item in items:
            if not isinstance(item, Mapping):
                continue
            expected = item.get("expected") if isinstance(item.get("expected"), Mapping) else {}
            operator, threshold = _criterion_operator_threshold(expected)
            actual, actual_reason = _metric_value(item.get("actual"), missing_reason="criterion actual value is undefined")
            passed = bool(item.get("passed"))
            if status == "failed":
                result = "PASS" if passed else "FAIL"
            elif status == "passed":
                result = "PASS" if passed else "NEEDS MANUAL REVIEW"
            else:
                result = "NEEDS MANUAL REVIEW"
            reason = (
                f"actual {_display_scalar(item.get('actual'))} {'met' if passed else 'did not meet'} "
                f"required {operator} {_display_scalar(threshold)}"
            )
            if actual_reason:
                reason = actual_reason
            output.append(
                StageCriterionV2(
                    stage=name,
                    metric=str(item.get("metric") or "unnamed_criterion"),
                    operator=operator,  # type: ignore[arg-type]
                    threshold=_metric_value(threshold, missing_reason="criterion threshold is undefined")[0],
                    actual=actual,
                    result=result,  # type: ignore[arg-type]
                    reason=reason,
                    evidence_path=f"{name}/stage_result.json",
                )
            )
    return output


def _criterion_operator_threshold(expected: Mapping[str, Any]) -> tuple[str, Any]:
    if "exclusive_min" in expected:
        return ">", expected["exclusive_min"]
    if "min" in expected:
        return ">=", expected["min"]
    if "max" in expected:
        return "<=", expected["max"]
    if "equals" in expected:
        return "==", expected["equals"]
    if "valid_parameter_combination_count" in expected:
        return "present", expected["valid_parameter_combination_count"]
    return "present", "criterion evidence"


def _metric_value(value: Any, *, missing_reason: str) -> tuple[MetricValueV2, str | None]:
    if value is None:
        return MetricValueV2(value=None, reason=missing_reason), missing_reason
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        reason = "criterion value is non-finite"
        return MetricValueV2(value=None, reason=reason), reason
    if isinstance(value, (str, int, float, bool)):
        return MetricValueV2(value=value), None
    return MetricValueV2(value=json.dumps(value, sort_keys=True, default=str)), None


def _reporting_criterion(issue: str) -> StageCriterionV2:
    return StageCriterionV2(
        stage="result_finalization",
        metric="required_reporting_evidence",
        operator="present",
        threshold=MetricValueV2(value="complete and valid"),
        actual=MetricValueV2(value=None, reason=issue),
        result="NEEDS MANUAL REVIEW",
        reason=issue,
    )


def _load_reporting_trades(run_dir: Path, verdict: str) -> tuple[pd.DataFrame, str | None, str | None]:
    candidates = (
        "acceptance_oos_test/trade_log.csv",
        "simulated_incubation_core/trade_log.csv",
        "walk_forward_analysis/wfa_oos_trade_log.csv",
        "limited_core_grid_test/fixed_config_core_trade_log.csv",
    )
    if verdict == "PASS" and not (run_dir / candidates[0]).is_file():
        return _empty_trade_frame(), None, "PASS lacks the mandatory acceptance OOS trade log"
    for relative in candidates:
        path = run_dir / relative
        if not path.is_file():
            continue
        try:
            trades = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            trades = _empty_trade_frame()
        except (OSError, ValueError) as exc:
            return _empty_trade_frame(), relative, f"trade log could not be read ({relative}): {exc}"
        if "net_pnl" not in trades.columns:
            return trades, relative, f"trade log lacks net_pnl ({relative})"
        return trades, relative, None
    return _empty_trade_frame(), None, "no staged trade log is available for ResultBundleV2"


def _reporting_evaluation_contract(run_dir: Path, trade_path: str | None) -> dict[str, Any]:
    output: dict[str, Any] = {"start": None, "end": None, "trading_dates": None}
    if trade_path is None:
        return output
    lane = trade_path.split("/", 1)[0]
    start: Any = None
    end: Any = None
    if lane == "acceptance_oos_test":
        summary = _optional_json_mapping(run_dir / lane / "acceptance_oos_summary.json")
        start, end = summary.get("test_start"), summary.get("test_end")
    elif lane == "simulated_incubation_core":
        summary = _optional_json_mapping(run_dir / lane / "incubation_oos_summary.json")
        start, end = summary.get("test_start"), summary.get("test_end")
    elif lane == "walk_forward_analysis":
        path = run_dir / lane / "wfa_results.csv"
        try:
            windows = pd.read_csv(path)
        except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError):
            windows = pd.DataFrame()
        if not windows.empty and {"test_start", "test_end"}.issubset(windows.columns):
            starts = pd.to_datetime(windows["test_start"], errors="coerce").dropna()
            ends = pd.to_datetime(windows["test_end"], errors="coerce").dropna()
            if len(starts) == len(windows) and len(ends) == len(windows):
                start, end = starts.min().date().isoformat(), ends.max().date().isoformat()
    elif lane == "limited_core_grid_test":
        summary = _optional_json_mapping(run_dir / lane / "core_grid_summary.json")
        subset = summary.get("resolved_data_subset") or summary.get("data_subset") or {}
        if isinstance(subset, Mapping):
            start = subset.get("start_date") or subset.get("start_timestamp")
            end = subset.get("end_date") or subset.get("end_timestamp")

    if start is None or end is None:
        return output
    try:
        start_date = pd.Timestamp(start).date()
        end_date = pd.Timestamp(end).date()
    except (TypeError, ValueError, OverflowError):
        return output
    if end_date < start_date:
        return output
    output["start"] = start_date
    output["end"] = end_date

    calendar_path = run_dir / lane / "validation" / "tradingview_comparison.csv"
    try:
        calendar = pd.read_csv(calendar_path)
    except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return output
    if "session_date" not in calendar.columns or calendar.empty:
        return output
    parsed = pd.to_datetime(calendar["session_date"], errors="coerce")
    if bool(parsed.isna().any()):
        return output
    dates = sorted(
        {
            value.date()
            for value in parsed
            if start_date <= value.date() <= end_date
        }
    )
    if dates:
        output["trading_dates"] = dates
    return output


def _optional_json_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = _read_strict_json(path)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _supplemental_frames(run_dir: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    issues: list[str] = []
    parameter_path = run_dir / "limited_core_grid_test" / "core_grid_results.csv"
    parameter, parameter_issue = _read_required_reporting_csv(
        parameter_path,
        label="parameter-neighbor evidence",
        fallback_columns=("reason",),
    )
    if parameter_issue is None:
        parameter_issue = _parameter_neighbor_schema_issue(parameter)
    if parameter_issue:
        issues.append(parameter_issue)

    wfa_path = run_dir / "walk_forward_analysis" / "wfa_oos_trade_log.csv"
    wfa, wfa_issue = _read_required_reporting_csv(
        wfa_path,
        label="stitched walk-forward OOS trade evidence",
        fallback_columns=tuple(_empty_trade_frame().columns),
    )
    if wfa_issue is None:
        wfa_issue = _wfa_trade_schema_issue(wfa)
    if wfa_issue:
        issues.append(wfa_issue)

    monte_path = run_dir / "wfa_oos_monte_carlo" / "wfa_oos_monte_carlo_summary.json"
    monte = _empty_frame(("reason",))
    if not monte_path.is_file():
        issues.append("mandatory Monte Carlo drawdown/ruin evidence is missing")
    else:
        try:
            value = _read_strict_json(monte_path)
            monte = pd.json_normalize(value if isinstance(value, list) else [value])
            if monte.empty:
                issues.append("mandatory Monte Carlo drawdown/ruin evidence is empty")
            else:
                monte_issue = _monte_carlo_schema_issue(monte)
                if monte_issue:
                    issues.append(monte_issue)
        except (ValueError, TypeError) as exc:
            monte = _empty_frame(("reason",))
            issues.append(f"mandatory Monte Carlo drawdown/ruin evidence is invalid: {exc}")
    return (
        {
            "parameter_neighbors": parameter,
            "wfa_stitched_oos": wfa,
            "monte_carlo_summary": monte,
        },
        issues,
    )


def _read_required_reporting_csv(
    path: Path,
    *,
    label: str,
    fallback_columns: Sequence[str],
) -> tuple[pd.DataFrame, str | None]:
    if not path.is_file():
        return _empty_frame(fallback_columns), f"mandatory {label} is missing"
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return _empty_frame(fallback_columns), f"mandatory {label} has no schema or rows"
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return _empty_frame(fallback_columns), f"mandatory {label} is invalid: {exc}"
    if frame.empty:
        return frame, f"mandatory {label} is empty"
    return frame, None


def _parameter_neighbor_schema_issue(frame: pd.DataFrame) -> str | None:
    required = {"run_id", "total_trades", "net_profit", "profit_factor", "max_drawdown", "mar"}
    missing = sorted(required - set(frame.columns))
    if missing:
        return "mandatory parameter-neighbor evidence lacks required columns: " + ", ".join(missing)
    return _finite_numeric_schema_issue(
        frame,
        columns=sorted(required),
        label="mandatory parameter-neighbor evidence",
    )


def _wfa_trade_schema_issue(frame: pd.DataFrame) -> str | None:
    required = {
        "trade_id",
        "wfa_window_id",
        "wfa_test_start",
        "wfa_test_end",
        "entry_timestamp",
        "exit_timestamp",
        "net_pnl",
        "r_multiple",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        return "mandatory stitched walk-forward OOS evidence lacks required columns: " + ", ".join(missing)
    numeric_issue = _finite_numeric_schema_issue(
        frame,
        columns=["net_pnl", "r_multiple"],
        label="mandatory stitched walk-forward OOS evidence",
    )
    if numeric_issue:
        return numeric_issue
    for column in ("wfa_test_start", "wfa_test_end", "entry_timestamp", "exit_timestamp"):
        if bool(pd.to_datetime(frame[column], errors="coerce", utc=True).isna().any()):
            return f"mandatory stitched walk-forward OOS evidence has invalid {column} values"
    return None


def _monte_carlo_schema_issue(frame: pd.DataFrame) -> str | None:
    run_column = next((name for name in ("number_of_runs", "runs", "iterations") if name in frame.columns), None)
    drawdown_column = next(
        (name for name in ("p95_drawdown", "p95_max_drawdown", "drawdown_p95") if name in frame.columns),
        None,
    )
    ruin_column = next(
        (
            name
            for name in ("probability_account_breach", "ruin_probability", "probability_of_ruin")
            if name in frame.columns
        ),
        None,
    )
    missing = [
        label
        for value, label in (
            (run_column, "run count"),
            (drawdown_column, "p95 drawdown"),
            (ruin_column, "ruin probability"),
        )
        if value is None
    ]
    if missing:
        return "mandatory Monte Carlo evidence lacks required fields: " + ", ".join(missing)
    assert run_column is not None and drawdown_column is not None and ruin_column is not None
    issue = _finite_numeric_schema_issue(
        frame,
        columns=[run_column, drawdown_column, ruin_column],
        label="mandatory Monte Carlo evidence",
    )
    if issue:
        return issue
    runs = pd.to_numeric(frame[run_column])
    drawdown = pd.to_numeric(frame[drawdown_column])
    ruin = pd.to_numeric(frame[ruin_column])
    if bool(((runs <= 0) | (runs % 1 != 0)).any()):
        return "mandatory Monte Carlo evidence requires a positive integer run count"
    if bool((drawdown < 0).any()):
        return "mandatory Monte Carlo evidence requires non-negative p95 drawdown"
    if bool(((ruin < 0) | (ruin > 1)).any()):
        return "mandatory Monte Carlo evidence requires ruin probability between zero and one"
    return None


def _finite_numeric_schema_issue(
    frame: pd.DataFrame,
    *,
    columns: Sequence[str],
    label: str,
) -> str | None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if bool(values.isna().any()) or not bool(pd.Series(values).map(math.isfinite).all()):
            return f"{label} has missing or non-finite {column} values"
    return None


def _validate_reporting_directory(staging: Path, bundle: ResultBundleV2) -> None:
    required = {
        RESULT_BUNDLE_FILENAME,
        "yearly_breakdown.csv",
        "monthly_breakdown.csv",
        "entry_session_breakdown.csv",
        "side_breakdown.csv",
        "equity_curve.csv",
        "drawdown_curve.csv",
        "parameter_neighbors.csv",
        "wfa_stitched_oos.csv",
        "monte_carlo_summary.csv",
    }
    missing = sorted(relative for relative in required if not (staging / relative).is_file())
    if missing:
        raise FinalizationError("ResultBundleV2 staging is incomplete: " + ", ".join(missing))
    loaded = load_result_bundle(staging / RESULT_BUNDLE_FILENAME)
    if loaded != bundle:
        raise FinalizationError("ResultBundleV2 readback differs from the validated model")
    for path in sorted(staging.glob("*.json")):
        _read_strict_json(path)
    for filename in sorted(required - {RESULT_BUNDLE_FILENAME}):
        path = staging / filename
        try:
            pd.read_csv(path)
        except pd.errors.EmptyDataError as exc:
            raise FinalizationError(f"report CSV has no schema header: {filename}") from exc


def _methodology_audit(
    summary: Mapping[str, Any],
    bundle: ResultBundleV2,
    *,
    evidence_issues: Sequence[str],
    trade_path: str | None,
) -> str:
    lines = [
        "# Methodology audit",
        "",
        f"- Campaign: `{bundle.campaign_id}`",
        f"- Variant: `{bundle.variant_id}`",
        f"- Run: `{bundle.run_id}`",
        f"- ResultBundleV2 verdict: `{bundle.verdict}`",
        f"- Diagnostic-only run: `{bool(summary.get('diagnostic_only'))}`",
        f"- Reporting trade evidence: `{trade_path or 'unavailable'}`",
        "- PASS means candidate strategy only; it is not a trading approval.",
        "",
        "## Stage matrix",
        "",
        "| Stage | Status | First failed or unresolved criterion |",
        "|---|---|---|",
    ]
    for stage in summary.get("stages") or []:
        if not isinstance(stage, Mapping):
            continue
        failed = next(
            (
                f"{item.get('metric')}: actual={_display_scalar(item.get('actual'))}; "
                f"required={_display_scalar(item.get('expected'))}"
                for item in stage.get("criteria") or []
                if isinstance(item, Mapping) and not item.get("passed")
            ),
            str(stage.get("error") or stage.get("skip_reason") or ""),
        )
        lines.append(f"| {stage.get('stage')} | {stage.get('status')} | {failed} |")
    lines.extend(["", "## Evidence integrity", ""])
    if evidence_issues:
        lines.extend(f"- NEEDS MANUAL REVIEW: {issue}" for issue in evidence_issues)
    else:
        lines.append("- Required staged artifacts parsed successfully and were hash-recorded.")
    lines.extend(["", "## Final verdict", "", bundle.verdict, ""])
    return "\n".join(lines)


def _append_terminal_ledger_event(
    ledger_path: Path,
    *,
    cfg_path: Path,
    cfg: Mapping[str, Any],
    summary: Mapping[str, Any],
    bundle: ResultBundleV2,
    report_path: Path,
    project_root: Path,
) -> bool:
    report_value = display_path(report_path, project_root)
    existing_rows: list[dict[str, str]] = []
    if ledger_path.is_file():
        with ledger_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
                raise FinalizationError("research_ledger.csv header does not match the governed append contract")
            existing_rows = list(reader)
        for existing in existing_rows:
            if (
                existing.get("campaign_id") == bundle.campaign_id
                and existing.get("variant_id") == bundle.variant_id
                and existing.get("report_path") == report_value
                and str(existing.get("result") or "").upper() in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}
            ):
                return False
    else:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=LEDGER_FIELDS).writeheader()

    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), Mapping) else {}
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), Mapping) else {}
    row = {
        "timestamp": _now_iso(),
        "campaign_id": bundle.campaign_id,
        "variant_id": bundle.variant_id,
        "instrument": summary.get("symbol") or cfg.get("symbol") or "",
        "timeframe": summary.get("timeframe") or cfg.get("timeframe") or (cfg.get("data") or {}).get("timeframe") or "",
        "edge": research.get("edge_thesis") or research.get("hypothesis") or cfg.get("strategy_name") or "",
        "variant_mechanic": _mechanic_description(strategy),
        "parameter_space": json.dumps((cfg.get("core_grid") or {}).get("parameters") or {}, sort_keys=True),
        "data_scope": json.dumps((cfg.get("data") or {}).get("data_subset") or {}, sort_keys=True),
        "config_path": display_path(cfg_path, project_root),
        "report_path": report_value,
        "stage": "full_staged_methodology",
        "result": bundle.verdict,
        "decision": {
            "PASS": "CANDIDATE_REVIEW_REQUIRED",
            "FAIL": "REJECT",
            "NEEDS MANUAL REVIEW": "MANUAL_REVIEW_REQUIRED",
        }[bundle.verdict],
        "failure_reason": _first_unresolved_reason(bundle),
        "rescue_attempt": str(cfg.get("attempt_kind") or "none"),
    }
    with ledger_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())
    return True


def _append_incomplete_ledger_event(
    ledger_path: Path,
    *,
    cfg_path: Path,
    cfg: Mapping[str, Any],
    summary: Mapping[str, Any],
    marker_path: Path,
    reason: str,
    project_root: Path,
) -> bool:
    report_value = display_path(marker_path, project_root)
    campaign_id = str(summary.get("campaign_id") or cfg.get("campaign_id") or "")
    variant_id = str(summary.get("variant_id") or cfg.get("variant_id") or "")
    if ledger_path.is_file():
        with ledger_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
                raise FinalizationError("research_ledger.csv header does not match the governed append contract")
            for existing in reader:
                if (
                    existing.get("campaign_id") == campaign_id
                    and existing.get("variant_id") == variant_id
                    and existing.get("report_path") == report_value
                    and existing.get("result") == "NEEDS MANUAL REVIEW"
                ):
                    return False
    else:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=LEDGER_FIELDS).writeheader()

    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), Mapping) else {}
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), Mapping) else {}
    row = {
        "timestamp": _now_iso(),
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "instrument": summary.get("symbol") or cfg.get("symbol") or "",
        "timeframe": summary.get("timeframe") or cfg.get("timeframe") or (cfg.get("data") or {}).get("timeframe") or "",
        "edge": research.get("edge_thesis") or research.get("hypothesis") or cfg.get("strategy_name") or "",
        "variant_mechanic": _mechanic_description(strategy),
        "parameter_space": json.dumps((cfg.get("core_grid") or {}).get("parameters") or {}, sort_keys=True),
        "data_scope": json.dumps((cfg.get("data") or {}).get("data_subset") or {}, sort_keys=True),
        "config_path": display_path(cfg_path, project_root),
        "report_path": report_value,
        "stage": "incomplete_studio_attempt",
        "result": "NEEDS MANUAL REVIEW",
        "decision": "MANUAL_REVIEW_REQUIRED",
        "failure_reason": reason,
        "rescue_attempt": str(cfg.get("attempt_kind") or "none"),
    }
    with ledger_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())
    return True


def _authoritative_summary(
    summary: Mapping[str, Any],
    *,
    verdict: str,
    finalization_state: str,
    result_bundle_path: Path | None = None,
    incomplete_marker_path: Path | None = None,
) -> dict[str, Any]:
    output = _json_safe_mapping(summary)
    output["research_verdict"] = verdict
    output["passed"] = verdict == "PASS"
    output["finalization_state"] = finalization_state
    output["result_bundle_path"] = str(result_bundle_path) if result_bundle_path is not None else None
    output["incomplete_attempt_marker_path"] = (
        str(incomplete_marker_path) if incomplete_marker_path is not None else None
    )
    output["updated_at"] = _now_iso()
    return output


def _incomplete_attempt_summary(
    run_dir: Path,
    *,
    cfg_path: Path,
    cfg: Mapping[str, Any],
    job_id: str,
    reason: str,
) -> dict[str, Any]:
    summary_path = run_dir / "campaign_test_summary.json"
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        try:
            summary = _read_json_mapping(summary_path)
        except ValueError:
            summary = {}
    summary = {
        **summary,
        "run_uid": summary.get("run_uid") or f"studio-incomplete-{_safe_identifier(job_id)}",
        "campaign_id": summary.get("campaign_id") or cfg.get("campaign_id"),
        "variant_id": summary.get("variant_id") or cfg.get("variant_id"),
        "test_run_id": summary.get("test_run_id") or cfg.get("test_run_id") or run_dir.name,
        "attempt_id": summary.get("attempt_id") or cfg.get("attempt_id"),
        "attempt_kind": summary.get("attempt_kind") or cfg.get("attempt_kind"),
        "attempt_provenance": summary.get("attempt_provenance") or cfg.get("attempt_provenance"),
        "parent_attempt_id": summary.get("parent_attempt_id") or cfg.get("parent_attempt_id"),
        "symbol": summary.get("symbol") or cfg.get("symbol") or (cfg.get("data") or {}).get("symbol"),
        "dataset_id": summary.get("dataset_id") or cfg.get("dataset_id") or (cfg.get("data") or {}).get("dataset_id"),
        "timeframe": summary.get("timeframe") or cfg.get("timeframe") or (cfg.get("data") or {}).get("timeframe"),
        "source_config_path": str(cfg_path),
        "output_dir": str(run_dir),
        "research_verdict": "NEEDS MANUAL REVIEW",
        "passed": False,
        "halted": True,
        "status": "incomplete",
        "incomplete_reason": reason,
        "stages": summary.get("stages") if isinstance(summary.get("stages"), list) else [],
        "updated_at": _now_iso(),
    }
    if not summary_path.is_file():
        _atomic_write_json(summary_path, summary)
    return summary


def _config_exchange_timezone(cfg: Mapping[str, Any]) -> str:
    data = cfg.get("data") if isinstance(cfg.get("data"), Mapping) else {}
    return str(data.get("exchange_timezone") or data.get("timezone") or "America/New_York")


def _refresh_source_index(config_path: Path, cfg: dict[str, Any], summary: dict[str, Any]) -> Path | None:
    # Always rewrite the matching entry.  The staged runner may already have
    # published a provisional PASS before ResultBundleV2 validation downgraded
    # it; returning the existing path would leave that stale verdict in place.
    return update_source_results_index(config_path, cfg, summary)


def _refresh_registry(project_root: Path) -> Mapping[str, Any]:
    layout = load_storage_layout(project_root)
    database = layout.catalog_root / "research_registry.sqlite"
    counts: dict[str, Any] = dict(
        build_registry(
            project_root=project_root,
            database_path=database,
            campaign_roots=layout.campaign_roots,
            run_roots=layout.evidence_roots,
            research_artifact_root=layout.research_artifact_root,
        )
    )
    counts.update(
        {
            f"export_{key}": value
            for key, value in export_registry_csvs(
                project_root=project_root,
                database_path=database,
                output_root=layout.catalog_root / "exports",
            ).items()
        }
    )
    counts.update(
        {
            f"view_{key}": value
            for key, value in generate_views(
                project_root=project_root,
                database_path=database,
                output_root=layout.views_root,
            ).items()
        }
    )
    return counts


def _validate_finalization_manifest(
    path: Path,
    *,
    job_id: str,
    journal_path: Path | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise FinalizationError(f"finalization manifest is missing: {path}")
    value = _read_strict_json(path)
    if not isinstance(value, dict) or value.get("schema") != FINALIZATION_SCHEMA:
        raise FinalizationError(f"unsupported finalization manifest: {path}")
    if value.get("job_id") != job_id:
        raise FinalizationError(
            f"reporting directory belongs to job {value.get('job_id')!r}, not {job_id!r}"
        )
    if value.get("transaction_complete") is True:
        if value.get("registry_published") is not True:
            raise FinalizationError("complete finalization manifest lacks durable registry publication")
        if value.get("terminal_recovery_phase") != "FINALIZED":
            raise FinalizationError("complete finalization manifest lacks terminal FINALIZED journal binding")
        expected_journal_hash = str(value.get("terminal_recovery_journal_sha256") or "")
        if len(expected_journal_hash) != 64:
            raise FinalizationError("complete finalization manifest lacks terminal recovery-journal hash")
        if journal_path is None:
            raise FinalizationError("complete finalization manifest requires recovery-journal inspection")
        _validate_terminal_recovery_journal(journal_path, job_id=job_id)
        if _file_sha256(journal_path) != expected_journal_hash:
            raise FinalizationError("terminal recovery-journal hash does not match finalization manifest")
    return value


def _validate_terminal_recovery_journal(path: Path, *, job_id: str) -> dict[str, Any]:
    if not path.is_file():
        raise FinalizationError(f"recovery journal is missing: {path}")
    value = _read_json_mapping(path)
    if value.get("schema") != RECOVERY_JOURNAL_SCHEMA or value.get("job_id") != job_id:
        raise FinalizationError("recovery journal identity does not match finalization transaction")
    if value.get("phase") != "FINALIZED" or value.get("terminal") is not True:
        raise FinalizationError("recovery journal is not durably bound to terminal FINALIZED phase")
    if value.get("automatic_replay_permitted") is not False:
        raise FinalizationError("terminal recovery journal must forbid automatic replay")
    return value


def _validate_reporting_hashes(reporting_dir: Path, manifest: Mapping[str, Any]) -> None:
    hashes = manifest.get("reporting_artifact_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise FinalizationError("finalization manifest does not contain reporting artifact hashes")
    mismatches = []
    for relative, expected in hashes.items():
        path = reporting_dir / str(relative)
        actual = _file_sha256(path) if path.is_file() else "<missing>"
        if actual != expected:
            mismatches.append(f"{relative}: expected {expected}, observed {actual}")
    if mismatches:
        raise FinalizationError("published reporting hash mismatch: " + "; ".join(mismatches))


def _suppress_candidate_package(run_dir: Path) -> None:
    for filename in _CANDIDATE_PACKAGE_FILES:
        path = run_dir / filename
        if path.is_file():
            path.unlink()


def _first_unresolved_reason(bundle: ResultBundleV2) -> str:
    if bundle.verdict == "PASS":
        return ""
    item = next((criterion for criterion in bundle.stage_criteria if criterion.result != "PASS"), None)
    return item.reason if item is not None else bundle.verdict_message


def _mechanic_description(strategy: Mapping[str, Any]) -> str:
    def module(section: str) -> str:
        value = strategy.get(section)
        return str(value.get("module") or "") if isinstance(value, Mapping) else ""

    return f"entry={module('entry')}; stop={module('sl')}; target={module('tp')}"


def _read_csv_or_empty(path: Path, *, columns: Sequence[str]) -> pd.DataFrame:
    if not path.is_file():
        return _empty_frame(columns)
    try:
        return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return _empty_frame(columns)


def _empty_trade_frame() -> pd.DataFrame:
    return _empty_frame(
        (
            "trade_id",
            "direction",
            "entry_timestamp",
            "exit_timestamp",
            "net_pnl",
            "r_multiple",
            "commission",
            "slippage_cost",
        )
    )


def _empty_frame(columns: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _hash_files(root: Path, *, exclude: set[str]) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and str(path.relative_to(root)) not in exclude
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value}")

    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"strict JSON validation failed for {path}: {exc}") from exc


def _read_json_mapping(path: Path) -> dict[str, Any]:
    value = _read_strict_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be a mapping: {path}")
    return value


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FinalizationError(f"could not read staged source config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FinalizationError(f"staged source config must be a mapping: {path}")
    return value


def _resolve_path(value: str | Path, project_root: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _resolve_run_dir(summary: Mapping[str, Any], project_root: Path) -> Path:
    value = summary.get("output_dir")
    if not value:
        raise FinalizationError("staged summary does not declare output_dir")
    return _resolve_path(str(value), project_root)


def _strict_verdict(value: Any) -> str:
    verdict = str(value or "NEEDS MANUAL REVIEW").strip().upper().replace("NEEDS_MANUAL_REVIEW", "NEEDS MANUAL REVIEW")
    if verdict not in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}:
        return "NEEDS MANUAL REVIEW"
    return verdict


def _journal_created_at(path: Path) -> datetime:
    value = _read_json_mapping(path).get("created_at")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(UTC)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _display_scalar(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _replace_nonfinite_json_values(value)
    try:
        serialized = json.dumps(normalized, sort_keys=True, default=str, allow_nan=False)
        result = json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise FinalizationError(f"value is not strict JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise FinalizationError("value must be a mapping")
    return result


def _replace_nonfinite_json_values(value: Any) -> Any:
    """Turn undefined numeric sentinels into JSON null before reporting."""

    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _replace_nonfinite_json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_replace_nonfinite_json_values(item) for item in value]
    return value


def _capture_file_checkpoint(path: Path) -> tuple[bool, bytes]:
    """Capture a small mutable governance file before an uncommitted append.

    Studio v1 has exactly one local worker, so restoring this checkpoint cannot
    race another authorized ledger writer.  The checkpoint prevents a failed
    multi-artifact finalization from leaving both a scientific terminal row and
    the authoritative incomplete-attempt row for the same reserved attempt.
    """

    return (True, path.read_bytes()) if path.is_file() else (False, b"")


def _restore_file_checkpoint(path: Path, checkpoint: tuple[bool, bytes]) -> None:
    existed, payload = checkpoint
    current = path.read_bytes() if path.is_file() else None
    expected = payload if existed else None
    if current == expected:
        return
    if not existed:
        path.unlink(missing_ok=True)
        _fsync_directory(path.parent)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".rollback.tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_identifier(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in "-_" else "_" for character in value)
    return normalized or "unknown"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "FINALIZATION_MANIFEST",
    "FINALIZATION_SCHEMA",
    "FinalizationError",
    "FinalizationResult",
    "REPORTING_DIRECTORY",
    "RECOVERY_JOURNAL_SCHEMA",
    "RunFinalizer",
]
