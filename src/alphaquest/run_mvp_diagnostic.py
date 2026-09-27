"""Build a fail-closed index for one completed diagnostic pre-acceptance run.

This module is deliberately report-only.  It neither launches research stages nor
creates or approves any research-governance decision.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from alphaquest.authoring.models import CERTIFIED_RECIPE_BINDINGS, DatasetManifestV1
from alphaquest.research.campaign_stages import (
    ACCEPTANCE_STAGE,
    PRE_ACCEPTANCE_STAGE_ORDER,
    apply_authoritative_parallel_defaults,
    canonicalize_campaign_config,
)
from alphaquest.research.preflight import run_preflight
from alphaquest.research.schemas import (
    validate_campaign_config_contract,
    validate_run_summary_contract,
    validate_stage_result_contract,
)
from alphaquest.research.storage import (
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.utils.config import strategy_mechanic, validate_campaign_run_root
from alphaquest.utils.hashing import file_sha256


SCHEMA = "alphaquest.mvp-diagnostic-index/v1"
DIAGNOSTIC_REASON = f"mandatory {ACCEPTANCE_STAGE} was omitted"
_IDENTITY_FIELDS = (
    "run_uid",
    "campaign_id",
    "variant_id",
    "test_run_id",
    "attempt_id",
    "attempt_kind",
    "attempt_provenance",
    "parent_attempt_id",
    "symbol",
    "dataset_id",
)
_REQUIRED_IDENTITY_FIELDS = tuple(field for field in _IDENTITY_FIELDS if field != "parent_attempt_id")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label} at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required {label}: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid {label} at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a YAML mapping: {path}")
    return value


def _artifact(path: Path, *, project_root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required artifact is not a file: {path}")
    try:
        display = path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        display = str(path.resolve())
    return {"path": display, "sha256": file_sha256(path), "bytes": path.stat().st_size}


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, found {actual!r}")


def _compiled_object_sha256(value: Any) -> str:
    """Match CampaignCompiler's canonical object hash for published documents."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_reference(value: Any, project_root: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required {label} path")
    return resolve_recorded_path(value, project_root=project_root).resolve()


def _inventory_run(run_dir: Path, project_root: Path) -> list[dict[str, Any]]:
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"run directory contains no artifacts: {run_dir}")
    return [_artifact(path, project_root=project_root) for path in files]


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_run_location(
    run_dir: Path,
    *,
    project_root: Path,
    effective_config: dict[str, Any],
    effective_path: Path,
) -> None:
    layout = load_storage_layout(project_root)
    if not any(_is_relative_to(run_dir, evidence_root.resolve()) for evidence_root in layout.evidence_roots):
        raise ValueError("run directory must be below a configured evidence root")
    validate_campaign_run_root(run_dir, effective_config, config_path=effective_path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _config_identity(config: dict[str, Any]) -> dict[str, Any]:
    data = config.get("data") if isinstance(config.get("data"), dict) else {}
    return {
        "campaign_id": config.get("campaign_id"),
        "variant_id": config.get("variant_id"),
        "test_run_id": config.get("test_run_id"),
        "attempt_id": config.get("attempt_id"),
        "attempt_kind": config.get("attempt_kind"),
        "attempt_provenance": config.get("attempt_provenance"),
        "parent_attempt_id": config.get("parent_attempt_id"),
        "symbol": config.get("symbol") or data.get("symbol"),
        "dataset_id": config.get("dataset_id") or data.get("dataset_id"),
        "timeframe": config.get("timeframe") or data.get("timeframe") or data.get("source_timeframe"),
    }


def _bind_identities(
    source_config: dict[str, Any],
    effective_config: dict[str, Any],
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    source_identity = _config_identity(source_config)
    effective_identity = _config_identity(effective_config)
    for field in _REQUIRED_IDENTITY_FIELDS:
        _require_nonempty_string(summary.get(field), f"summary.{field}")
        _require_equal(manifest.get(field), summary.get(field), f"manifest {field}")
    _require_nonempty_string(summary.get("timeframe"), "summary.timeframe")
    _require_equal(manifest.get("timeframe"), summary.get("timeframe"), "manifest timeframe")
    for field in (*_REQUIRED_IDENTITY_FIELDS[1:], "parent_attempt_id", "timeframe"):
        _require_equal(source_identity.get(field), summary.get(field), f"source config {field}")
        _require_equal(effective_identity.get(field), summary.get(field), f"effective config {field}")
    _require_equal(manifest.get("parent_attempt_id"), summary.get("parent_attempt_id"), "manifest parent_attempt_id")
    _require_equal(summary.get("attempt_provenance"), "authored", "attempt provenance")
    if summary.get("attempt_kind") == "original":
        _require_equal(summary.get("parent_attempt_id"), None, "original attempt parent")
    elif not isinstance(summary.get("parent_attempt_id"), str) or not summary["parent_attempt_id"].strip():
        raise ValueError("non-original attempt requires a non-empty parent_attempt_id")


def _expected_effective_config(
    source_config: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Any]:
    expected = canonicalize_campaign_config(source_config, include_acceptance=False)
    workers = summary.get("authoritative_parallel_workers")
    core_workers = summary.get("authoritative_core_grid_workers")
    if workers is None and core_workers is not None:
        raise ValueError("authoritative_core_grid_workers requires authoritative_parallel_workers")
    if workers is not None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError("authoritative_parallel_workers must be a positive integer or null")
        if core_workers is not None and (
            isinstance(core_workers, bool) or not isinstance(core_workers, int) or core_workers < 1
        ):
            raise ValueError("authoritative_core_grid_workers must be a positive integer or null")
        expected = apply_authoritative_parallel_defaults(
            expected,
            workers=workers,
            core_grid_workers=core_workers,
        )
    return expected


def _authoring_binding(
    source_path: Path,
    source_config: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    context = resolve_campaign_context(source_path, project_root=project_root)
    if context is None or context.lifecycle != "active":
        raise ValueError("source config must belong to a published active campaign")
    manifest_path = context.campaign_root / "authoring_manifest.json"
    authoring = _read_json(manifest_path, "authoring manifest")
    _require_equal(authoring.get("schema"), "alphaquest.authoring-manifest/v1", "authoring manifest schema")
    _require_equal(authoring.get("campaign_id"), source_config.get("campaign_id"), "authoring campaign")
    _require_equal(authoring.get("authoring_lane"), "certified_recipe", "authoring lane")
    recipe = _require_nonempty_string(authoring.get("certified_recipe"), "authoring certified_recipe")
    if recipe not in CERTIFIED_RECIPE_BINDINGS:
        raise ValueError(f"unsupported certified recipe: {recipe}")
    expected_entry, expected_setup = CERTIFIED_RECIPE_BINDINGS[recipe]
    entry = ((source_config.get("strategy") or {}).get("entry") or {})
    _require_equal(entry.get("module"), expected_entry, "certified recipe entry module")
    if expected_setup is not None:
        _require_equal((entry.get("params") or {}).get("setup_mode"), expected_setup, "certified recipe setup mode")
    _require_equal(authoring.get("dataset_id"), _config_identity(source_config)["dataset_id"], "authoring dataset")
    compiled = authoring.get("compiled_document_sha256")
    if not isinstance(compiled, dict):
        raise ValueError("authoring manifest lacks compiled document hashes")
    config_relative = source_path.relative_to(context.campaign_root).as_posix()
    _require_equal(
        compiled.get(config_relative),
        _compiled_object_sha256(source_config),
        "published source config hash",
    )
    documents: list[dict[str, Any]] = []
    for relative, expected_hash in sorted(compiled.items()):
        document_path = context.campaign_root / str(relative)
        artifact = _artifact(document_path, project_root=project_root)
        document = _read_yaml(document_path, f"published document {relative}")
        compiled_object_sha256 = _compiled_object_sha256(document)
        _require_equal(
            compiled_object_sha256,
            expected_hash,
            f"published document {relative} hash",
        )
        documents.append(
            {
                "path": artifact["path"],
                "file_sha256": artifact["sha256"],
                "bytes": artifact["bytes"],
                "compiled_object_sha256": compiled_object_sha256,
            }
        )
    return {
        "manifest": _artifact(manifest_path, project_root=project_root),
        "authoring_lane": "certified_recipe",
        "certified_recipe": recipe,
        "documents": documents,
    }


def _preflight_binding(
    receipt_path: Path,
    source_path: Path,
    embedded: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    receipt = _read_json(receipt_path, "pre-run preflight receipt")
    _require_equal(receipt, embedded, "separate pre-run preflight receipt")
    if receipt.get("passed") is not True or receipt.get("failures"):
        raise ValueError("pre-run configuration/data preflight must pass without failures")
    _require_equal(receipt.get("tests_ran"), False, "pre-run preflight tests_ran")
    current = run_preflight(config_paths=[source_path], run_tests=False, project_root=project_root)
    if current.get("passed") is not True or current.get("failures"):
        raise ValueError("current authored config/data preflight failed")
    _require_equal(current.get("tests_ran"), False, "current config validation tests_ran")
    return {
        "recorded_receipt": _artifact(receipt_path, project_root=project_root),
        "recorded": receipt,
        "current_config_validation": current,
        "repository_engineering_tests_verified": False,
    }


def _mechanics_bindings(
    source_config: dict[str, Any],
    summary: dict[str, Any],
    manifest: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    summary_gate = summary.get("mechanics_validation_gate")
    manifest_gate = manifest.get("mechanics_validation_gate")
    if not isinstance(summary_gate, dict) or not isinstance(manifest_gate, dict):
        raise ValueError("run does not record a mechanics validation gate")
    _require_equal(manifest_gate, summary_gate, "manifest mechanics gate")
    _require_equal(summary_gate.get("status"), "APPROVED_FOR_TESTING", "mechanics gate status")
    _require_equal(summary_gate.get("approval_status"), "approved_for_testing", "mechanics approval status")
    if summary_gate.get("errors"):
        raise ValueError("mechanics gate records errors")

    research = source_config.get("research_metadata")
    gate = research.get("validation_gate") if isinstance(research, dict) else None
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise ValueError("source config lacks a required mechanics validation gate")
    evidence_dir = _resolve_reference(gate.get("evidence_dir"), project_root, "mechanics evidence_dir")
    approval_path = _resolve_reference(gate.get("approval_path"), project_root, "mechanics approval_path")
    _require_equal(
        _resolve_reference(summary_gate.get("evidence_dir"), project_root, "recorded mechanics evidence_dir"),
        evidence_dir,
        "mechanics evidence path",
    )
    _require_equal(
        _resolve_reference(summary_gate.get("approval_path"), project_root, "recorded mechanics approval_path"),
        approval_path,
        "mechanics approval path",
    )
    if not evidence_dir.is_dir():
        raise ValueError(f"mechanics evidence directory is missing: {evidence_dir}")
    evidence_files = sorted(path for path in evidence_dir.iterdir() if path.is_file())
    if not evidence_files:
        raise ValueError(f"mechanics evidence directory contains no files: {evidence_dir}")
    approval = _read_json(approval_path, "mechanics approval")
    _require_equal(approval.get("status"), "approved_for_testing", "mechanics approval document status")
    _require_equal(approval.get("config_hash"), summary.get("source_config_hash"), "mechanics approval config hash")
    _require_equal(approval.get("input_data_hash"), summary_gate.get("input_data_hash"), "mechanics approval input hash")
    for approval_field, gate_field in (
        ("status", "approval_status"),
        ("reviewer", "reviewer"),
        ("reviewed_at", "reviewed_at"),
        ("lane", "lane"),
        ("validation_schema_version", "validation_schema_version"),
        ("strategy_implementation_version", "strategy_implementation_version"),
        ("strategy_implementation_sha256", "strategy_implementation_sha256"),
        ("strategy_certification_manifest_sha256", "strategy_certification_manifest_sha256"),
    ):
        if approval_field in approval or summary_gate.get(gate_field) is not None:
            _require_equal(
                approval.get(approval_field),
                summary_gate.get(gate_field),
                f"mechanics approval {approval_field}",
            )
    _require_nonempty_string(approval.get("reviewer"), "mechanics approval reviewer")
    _require_nonempty_string(approval.get("reviewed_at"), "mechanics approval reviewed_at")
    for approval_field, gate_field in (
        ("fixed_random_sample_size", "manual_review_random_sample_size"),
        ("fixed_random_seed", "manual_review_seed"),
        ("parameter_mode", "parameter_mode"),
    ):
        if gate.get(gate_field) is not None:
            _require_equal(
                approval.get(approval_field), gate.get(gate_field), f"mechanics approval {approval_field}"
            )
    return {
        "recorded_gate": deepcopy(summary_gate),
        "gate_currently_revalidated": False,
        "human_authority_verified": False,
        "evidence_inventory_only": True,
        "approval_record": {
            key: approval.get(key)
            for key in (
                "schema",
                "status",
                "reviewer",
                "reviewed_at",
                "notes",
                "config_hash",
                "input_data_hash",
                "lane",
                "validation_schema_version",
                "fixed_random_sample_size",
                "fixed_random_seed",
                "parameter_mode",
            )
        },
        "approval": _artifact(approval_path, project_root=project_root),
        "evidence": [_artifact(path, project_root=project_root) for path in evidence_files],
    }


def _dataset_binding(
    source_config: dict[str, Any], summary: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    data = source_config.get("data")
    if not isinstance(data, dict):
        raise ValueError("source config data section is missing")
    dataset_id = str(data.get("dataset_id") or "")
    _require_equal(dataset_id, summary.get("dataset_id"), "dataset identity")
    layout = load_storage_layout(project_root)
    manifest_path = layout.dataset_root / dataset_id / "dataset_manifest.json"
    dataset_manifest = _read_json(manifest_path, "dataset manifest")
    try:
        DatasetManifestV1.model_validate(dataset_manifest)
    except ValueError as exc:
        raise ValueError(f"dataset manifest contract failed: {exc}") from exc
    _require_equal(dataset_manifest.get("dataset_id"), dataset_id, "dataset manifest identity")
    _require_equal(dataset_manifest.get("quality_verdict"), "PASS", "dataset quality verdict")
    source = str(data.get("source") or "").strip().lower()
    if source not in {"csv", "parquet"}:
        raise ValueError(
            "MVP diagnostic indexing supports one local CSV or Parquet bar dataset; "
            f"unsupported source {source!r} requires a separate binding design"
        )
    _require_equal(str(dataset_manifest.get("source") or "").strip().lower(), source, "dataset source")
    canonical_path = _resolve_reference(dataset_manifest.get("path"), project_root, "canonical dataset")
    configured_path = _resolve_reference(
        data.get("raw_csv" if source == "csv" else "raw_parquet"),
        project_root,
        f"configured {source} dataset",
    )
    _require_equal(configured_path, canonical_path, "configured canonical dataset path")
    canonical = _artifact(canonical_path, project_root=project_root)
    _require_equal(canonical["sha256"], dataset_manifest.get("canonical_sha256"), "dataset manifest canonical hash")
    _require_equal(canonical["sha256"], data.get("canonical_sha256"), "source config canonical hash")
    gate = summary["mechanics_validation_gate"]
    _require_equal(canonical["sha256"], gate.get("input_data_hash"), "mechanics input data hash")
    return {
        "dataset_id": dataset_id,
        "manifest": _artifact(manifest_path, project_root=project_root),
        "manifest_document": dataset_manifest,
        "canonical_file": canonical,
    }


def _stage_bindings(
    run_dir: Path, summary: dict[str, Any], manifest: dict[str, Any], project_root: Path
) -> list[dict[str, Any]]:
    stages = summary.get("stages")
    if not isinstance(stages, list) or not all(isinstance(item, dict) for item in stages):
        raise ValueError("campaign summary stages must be a list of objects")
    names = [item.get("stage") for item in stages]
    _require_equal(names, PRE_ACCEPTANCE_STAGE_ORDER, "pre-acceptance stage order")
    _require_equal(manifest.get("stage_order"), PRE_ACCEPTANCE_STAGE_ORDER, "manifest stage order")
    bindings: list[dict[str, Any]] = []
    for item in stages:
        stage = str(item["stage"])
        validate_stage_result_contract(item, context=f"campaign summary stage {stage}")
        status = str(item.get("status"))
        if (status == "passed") != (item.get("passed") is True):
            raise ValueError(f"{stage} status and passed flag are inconsistent")
        if status == "error" and not str(item.get("error") or "").strip():
            raise ValueError(f"{stage} error status requires a non-empty error")
        if status == "skipped" and not str(item.get("skip_reason") or "").strip():
            raise ValueError(f"{stage} skipped status requires a non-empty skip_reason")
        result_path = run_dir / stage / "stage_result.json"
        if result_path.is_file():
            result = _read_json(result_path, f"{stage} stage result")
            validate_stage_result_contract(result, context=f"{stage}/stage_result.json")
            _require_equal(result, item, f"{stage} stage result")
            artifacts_value = result.get("artifacts")
            if status in {"passed", "failed"} and (
                not isinstance(artifacts_value, list) or not artifacts_value
            ):
                raise ValueError(f"{stage} completed result requires a non-empty artifacts list")
            artifact_bindings: list[dict[str, Any]] = []
            if artifacts_value is not None:
                if not isinstance(artifacts_value, list):
                    raise ValueError(f"{stage}.artifacts must be a list when present")
                for index, value in enumerate(artifacts_value):
                    artifact_path = _resolve_reference(
                        value, project_root, f"{stage}.artifacts[{index}]"
                    )
                    if not _is_relative_to(artifact_path, (run_dir / stage).resolve()):
                        raise ValueError(f"{stage} artifact is outside its stage directory: {value}")
                    artifact_bindings.append(_artifact(artifact_path, project_root=project_root))
            if status in {"passed", "failed"}:
                recorded = {item["path"] for item in artifact_bindings}
                actual = {
                    _artifact(path, project_root=project_root)["path"]
                    for path in (run_dir / stage).rglob("*")
                    if path.is_file() and path.name != "stage_result.json"
                }
                _require_equal(recorded, actual, f"{stage} referenced artifact inventory")
            bindings.append(
                {
                    "summary": deepcopy(item),
                    "stage_result": deepcopy(result),
                    "artifact": _artifact(result_path, project_root=project_root),
                    "referenced_artifacts": artifact_bindings,
                    "missing_stage_result_reason": None,
                }
            )
            continue
        if item.get("status") != "skipped" or not str(item.get("skip_reason") or "").strip():
            raise ValueError(f"missing stage_result.json for non-skipped stage: {stage}")
        bindings.append(
            {
                "summary": deepcopy(item),
                "stage_result": None,
                "artifact": None,
                "referenced_artifacts": [],
                "missing_stage_result_reason": str(item["skip_reason"]),
            }
        )
    return bindings


def build_diagnostic_index(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    preflight_receipt: str | Path,
    mode: str,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run = Path(run_dir)
    run = run.resolve() if run.is_absolute() else (root / run).resolve()
    if mode not in {"synthetic", "unverified"}:
        raise ValueError("mode must be 'synthetic' or 'unverified'; positive real-origin classification is unsupported")
    if not run.is_dir():
        raise ValueError(f"run directory does not exist: {run}")

    summary_path = run / "campaign_test_summary.json"
    variant_summary_path = run / "variant_test_summary.json"
    manifest_path = run / "run_manifest.json"
    summary = _read_json(summary_path, "campaign summary")
    variant_summary = _read_json(variant_summary_path, "variant summary")
    manifest = _read_json(manifest_path, "run manifest")
    _require_equal(variant_summary, summary, "variant summary")
    validate_run_summary_contract(summary, context="campaign_test_summary.json")

    for key in ("diagnostic_only", "skip_validation", "fast_runtime_defaults", "passed", "halted"):
        if not isinstance(summary.get(key), bool):
            raise ValueError(f"summary.{key} must be boolean")
    _require_equal(summary.get("diagnostic_only"), True, "diagnostic_only")
    _require_equal(summary.get("skip_validation"), False, "skip_validation")
    _require_equal(summary.get("fast_runtime_defaults"), False, "fast_runtime_defaults")
    _require_equal(summary.get("diagnostic_reasons"), [DIAGNOSTIC_REASON], "diagnostic reasons")
    _require_equal(summary.get("research_verdict"), "NEEDS MANUAL REVIEW", "research verdict")
    _require_equal(summary.get("generic_objective_verdict"), "NEEDS MANUAL REVIEW", "generic objective verdict")
    _require_equal(summary.get("scientific_validity_verdict"), "NEEDS MANUAL REVIEW", "scientific validity verdict")
    _require_equal(summary.get("passed"), False, "run passed flag")
    preflight = summary.get("submission_preflight")
    if not isinstance(preflight, dict) or preflight.get("passed") is not True or preflight.get("failures"):
        raise ValueError("submission preflight must be successful and record no failures")
    _require_equal(manifest.get("submission_preflight"), preflight, "manifest submission preflight")
    for key in (
        "diagnostic_only",
        "diagnostic_reasons",
        "research_verdict",
        "generic_objective_verdict",
        "scientific_validity_verdict",
        "authoritative_parallel_workers",
        "authoritative_core_grid_workers",
    ):
        _require_equal(manifest.get(key), summary.get(key), f"manifest {key}")
    if not isinstance(manifest.get("diagnostic_only"), bool):
        raise ValueError("manifest.diagnostic_only must be boolean")

    effective_path = run / "effective_config.yaml"
    snapshot_path = run / "source_config.yaml"
    effective_config = _read_yaml(effective_path, "effective config")
    source_config = _read_yaml(snapshot_path, "source config snapshot")
    validate_campaign_config_contract(source_config, context="source_config.yaml")
    validate_campaign_config_contract(effective_config, context="effective_config.yaml")
    _require_equal(file_sha256(effective_path), summary.get("config_hash"), "effective config hash")
    _require_equal(file_sha256(snapshot_path), summary.get("source_config_hash"), "source config snapshot hash")
    for key, expected in (
        ("config_path", effective_path),
        ("effective_config_path", effective_path),
        ("source_config_snapshot_path", snapshot_path),
    ):
        _require_equal(_resolve_reference(summary.get(key), root, key), expected.resolve(), key)
    _require_equal(
        _resolve_reference(manifest.get("effective_config"), root, "manifest effective_config"),
        effective_path.resolve(),
        "manifest effective config path",
    )
    _require_equal(
        _resolve_reference(manifest.get("source_config_snapshot"), root, "manifest source_config_snapshot"),
        snapshot_path.resolve(),
        "manifest source config snapshot path",
    )
    _require_equal(manifest.get("config_hash"), summary.get("config_hash"), "manifest effective config hash")
    _require_equal(manifest.get("source_config_hash"), summary.get("source_config_hash"), "manifest source config hash")
    source_path = _resolve_reference(summary.get("source_config_path"), root, "authored source config")
    _require_equal(file_sha256(source_path), summary.get("source_config_hash"), "authored source config hash")
    _require_equal(
        _resolve_reference(manifest.get("config_source"), root, "manifest config_source"),
        source_path,
        "manifest source config path",
    )
    _bind_identities(source_config, effective_config, summary, manifest)
    _require_equal(
        effective_config,
        _expected_effective_config(source_config, summary),
        "effective config canonicalization",
    )
    _require_run_location(
        run,
        project_root=root,
        effective_config=effective_config,
        effective_path=effective_path,
    )
    _require_equal(_resolve_reference(summary.get("output_dir"), root, "summary output_dir"), run, "summary output_dir")
    run_uid_path = run / "run_uid.txt"
    _artifact(run_uid_path, project_root=root)
    run_uid = _require_nonempty_string(run_uid_path.read_text(encoding="utf-8").strip(), "run_uid.txt")
    _require_equal(run_uid, summary.get("run_uid"), "run UID marker")

    authoring = _authoring_binding(source_path, source_config, root)
    mechanics = _mechanics_bindings(source_config, summary, manifest, root)
    dataset = _dataset_binding(source_config, summary, root)
    stages = _stage_bindings(run, summary, manifest, root)
    receipt = Path(preflight_receipt)
    receipt = receipt.resolve() if receipt.is_absolute() else (root / receipt).resolve()
    preflight_binding = _preflight_binding(receipt, source_path, preflight, root)

    labels = (
        [
            "Synthetic fixture source; not independently verified.",
            "Duplicate and implementation-admission decisions are scripted fixture context.",
            "Mechanics approval is simulated and has no owner authority.",
            "Operational PASS means only that the harness produced bound diagnostic evidence.",
        ]
        if mode == "synthetic"
        else [
            "User-supplied diagnostic evidence of unverified data origin.",
            "No real-data provenance classification is made by this index.",
            "Recorded mechanics approval is reported, not independently re-audited by this index.",
        ]
    )
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "overall_verdict": "NEEDS MANUAL REVIEW",
        "passed": False,
        "labels": labels,
        "assurance": {
            "source_review_verified": False,
            "implementation_admission_verified": False,
            "data_origin_verified": False,
            "mechanics_gate_currently_revalidated": False,
            "human_mechanics_authority_verified": False,
            "repository_engineering_tests_verified": False,
            "canonical_result_bundle_finalized": False,
            "scientific_pass_or_fail_claimed": False,
            "candidate_promoted": False,
            "trading_ready": False,
            "p3_qualified": False,
        },
        "run_identity": {field: summary.get(field) for field in _IDENTITY_FIELDS},
        "run_controls": {
            "diagnostic_only": True,
            "diagnostic_reasons": [DIAGNOSTIC_REASON],
            "skip_validation": False,
            "fast_runtime_defaults": False,
            "submission_preflight": deepcopy(preflight),
        },
        "preflight": preflight_binding,
        "source_config": {
            "authored": _artifact(source_path, project_root=root),
            "snapshot": _artifact(snapshot_path, project_root=root),
            "effective": _artifact(effective_path, project_root=root),
        },
        "execution_contract": {
            "mechanic": strategy_mechanic(effective_config),
            "strategy": deepcopy(effective_config["strategy"]),
            "core_grid_parameters": deepcopy((effective_config.get("core_grid") or {}).get("parameters") or {}),
            "wfa_parameters": deepcopy((effective_config.get("wfa") or {}).get("parameters") or {}),
        },
        "authoring": authoring,
        "dataset": dataset,
        "mechanics": mechanics,
        "stages": stages,
        "stage_outcomes_retained": True,
        "run_manifest": _artifact(manifest_path, project_root=root),
        "campaign_summary": _artifact(summary_path, project_root=root),
        "variant_summary": _artifact(variant_summary_path, project_root=root),
        "run_artifacts": _inventory_run(run, root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--preflight-receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", required=True, choices=("synthetic", "unverified"))
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    run = Path(args.run_dir)
    run = run.resolve() if run.is_absolute() else (root / run).resolve()
    output = Path(args.output)
    output = output.resolve() if output.is_absolute() else (root / output).resolve()
    try:
        output.relative_to(run)
    except ValueError:
        pass
    else:
        raise ValueError("diagnostic index output must be outside the run directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = build_diagnostic_index(
        project_root=root,
        run_dir=run,
        preflight_receipt=args.preflight_receipt,
        mode=args.mode,
    )
    with output.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(output)
    print("NEEDS MANUAL REVIEW")


if __name__ == "__main__":
    main()
