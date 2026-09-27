"""Build a fail-closed index for one completed diagnostic pre-acceptance run.

This module is deliberately report-only.  It neither launches research stages nor
creates or approves any research-governance decision.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from alphaquest.research.campaign_stages import (
    ACCEPTANCE_STAGE,
    PRE_ACCEPTANCE_STAGE_ORDER,
)
from alphaquest.research.storage import load_storage_layout, resolve_recorded_path
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
_SYNTHETIC_MARKERS = ("synthetic", "simulated", "fixture", "tutorial")


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


def _resolve_reference(value: Any, project_root: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required {label} path")
    return resolve_recorded_path(value, project_root=project_root).resolve()


def _inventory_run(run_dir: Path, project_root: Path) -> list[dict[str, Any]]:
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"run directory contains no artifacts: {run_dir}")
    return [_artifact(path, project_root=project_root) for path in files]


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
    return {
        "recorded_gate": deepcopy(summary_gate),
        "gate_currently_revalidated": False,
        "evidence_inventory_only": True,
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
    _require_equal(dataset_manifest.get("dataset_id"), dataset_id, "dataset manifest identity")
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
        result_path = run_dir / stage / "stage_result.json"
        if result_path.is_file():
            result = _read_json(result_path, f"{stage} stage result")
            _require_equal(result, item, f"{stage} stage result")
            bindings.append(
                {
                    "summary": deepcopy(item),
                    "stage_result": deepcopy(result),
                    "artifact": _artifact(result_path, project_root=project_root),
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
                "missing_stage_result_reason": str(item["skip_reason"]),
            }
        )
    return bindings


def build_diagnostic_index(
    *, project_root: str | Path, run_dir: str | Path, mode: str
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run = Path(run_dir)
    run = run.resolve() if run.is_absolute() else (root / run).resolve()
    if mode not in {"synthetic", "real"}:
        raise ValueError("mode must be 'synthetic' or 'real'")
    if not run.is_dir():
        raise ValueError(f"run directory does not exist: {run}")

    summary_path = run / "campaign_test_summary.json"
    variant_summary_path = run / "variant_test_summary.json"
    manifest_path = run / "run_manifest.json"
    summary = _read_json(summary_path, "campaign summary")
    variant_summary = _read_json(variant_summary_path, "variant summary")
    manifest = _read_json(manifest_path, "run manifest")
    _require_equal(variant_summary, summary, "variant summary")
    for field in _IDENTITY_FIELDS:
        _require_equal(manifest.get(field), summary.get(field), f"run identity {field}")

    _require_equal(summary.get("diagnostic_only"), True, "diagnostic_only")
    _require_equal(summary.get("skip_validation"), False, "skip_validation")
    _require_equal(summary.get("fast_runtime_defaults"), False, "fast_runtime_defaults")
    _require_equal(summary.get("diagnostic_reasons"), [DIAGNOSTIC_REASON], "diagnostic reasons")
    _require_equal(summary.get("research_verdict"), "NEEDS MANUAL REVIEW", "research verdict")
    _require_equal(summary.get("passed"), False, "run passed flag")
    preflight = summary.get("submission_preflight")
    if not isinstance(preflight, dict) or preflight.get("passed") is not True or preflight.get("failures"):
        raise ValueError("submission preflight must be successful and record no failures")
    _require_equal(manifest.get("submission_preflight"), preflight, "manifest submission preflight")
    for key in ("diagnostic_only", "diagnostic_reasons", "research_verdict"):
        _require_equal(manifest.get(key), summary.get(key), f"manifest {key}")

    effective_path = run / "effective_config.yaml"
    snapshot_path = run / "source_config.yaml"
    effective_config = _read_yaml(effective_path, "effective config")
    source_config = _read_yaml(snapshot_path, "source config snapshot")
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
    for field, source in (
        ("campaign_id", source_config.get("campaign_id")),
        ("variant_id", source_config.get("variant_id")),
        ("symbol", source_config.get("symbol") or (source_config.get("data") or {}).get("symbol")),
    ):
        _require_equal(source, summary.get(field), f"source config {field}")

    mechanics = _mechanics_bindings(source_config, summary, manifest, root)
    dataset = _dataset_binding(source_config, summary, root)
    stages = _stage_bindings(run, summary, manifest, root)

    marker_values = {
        "campaign_id": summary.get("campaign_id"),
        "dataset_id": summary.get("dataset_id"),
        "mechanics_reviewer": mechanics["recorded_gate"].get("reviewer"),
        "dataset_source": dataset["manifest_document"].get("source"),
    }
    detected_markers = sorted(
        {marker for value in marker_values.values() for marker in _SYNTHETIC_MARKERS if marker in str(value).lower()}
    )
    if mode == "real" and detected_markers:
        raise ValueError(f"real mode rejects evident synthetic fixture markers: {', '.join(detected_markers)}")

    labels = (
        [
            "Synthetic fixture source; not independently verified.",
            "Duplicate and implementation-admission decisions are scripted fixture context.",
            "Mechanics approval is simulated and has no owner authority.",
            "Operational PASS means only that the harness produced bound diagnostic evidence.",
        ]
        if mode == "synthetic"
        else [
            "Real-data diagnostic evidence; source review and implementation admission are not verified by this index.",
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
        "source_config": {
            "authored": _artifact(source_path, project_root=root),
            "snapshot": _artifact(snapshot_path, project_root=root),
            "effective": _artifact(effective_path, project_root=root),
        },
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
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", required=True, choices=("synthetic", "real"))
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
    document = build_diagnostic_index(project_root=root, run_dir=run, mode=args.mode)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(output)
    print("NEEDS MANUAL REVIEW")


if __name__ == "__main__":
    main()
