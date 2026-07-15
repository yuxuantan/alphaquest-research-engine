"""Read-only, fail-closed lineage inspection for generated research runs."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import yaml


STRICT_VERDICTS = {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}
AUTHORITATIVE_NAMES = (
    "campaign_test_summary.json",
    "variant_test_summary.json",
    "run_manifest.json",
    "data_manifest.json",
    "source_config.yaml",
    "effective_config.yaml",
    "methodology_audit.md",
    "run_uid.txt",
)


def inspect_run_lineage(run_dir: str | Path, *, project_root: str | Path = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    directory = _resolve(root, run_dir)
    summary = _read_json(directory / "campaign_test_summary.json") or _read_json(directory / "variant_test_summary.json")
    manifest = _read_json(directory / "run_manifest.json")
    data_manifest = _read_json(directory / "data_manifest.json")
    source_snapshot = directory / "source_config.yaml"
    effective_snapshot = directory / "effective_config.yaml"
    source_cfg = _read_yaml(source_snapshot)
    effective_cfg = _read_yaml(effective_snapshot)
    cfg = effective_cfg or source_cfg

    errors: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []
    source_declared = str(
        manifest.get("config_source")
        or summary.get("source_config_path")
        or manifest.get("source_config")
        or ""
    )
    source_authored = _resolve(root, source_declared) if source_declared else None

    hashes = {
        "source_config": _hash_reconciliation(
            declared=manifest.get("source_config_hash") or summary.get("source_config_hash"),
            snapshot=source_snapshot,
            authored=source_authored,
        ),
        "effective_config": _hash_reconciliation(
            declared=manifest.get("config_hash") or summary.get("config_hash"),
            snapshot=effective_snapshot,
        ),
        "input_data": _input_hash_reconciliation(directory, manifest, summary),
    }
    for label, item in hashes.items():
        if item["mismatch"]:
            errors.append(f"{label} hash mismatch")
        elif not item["declared"]:
            missing.append(f"{label} hash is not declared")
    if not hashes["input_data"].get("reconciled"):
        missing.append("input-data hash lacks two matching durable declarations")
    if not source_snapshot.is_file():
        missing.append("source_config.yaml snapshot")
    if not effective_snapshot.is_file():
        missing.append("effective_config.yaml snapshot")
    if source_authored is not None and not source_authored.is_file():
        warnings.append("authored source config path no longer resolves; retained snapshot is the only source evidence")
    elif hashes["source_config"].get("authored_matches") is False:
        warnings.append("current authored source config has drifted from the retained source snapshot")

    data_cfg = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    raw_sources = _raw_sources(root, data_cfg, data_manifest)
    if not raw_sources:
        missing.append("declared raw source")
    for item in raw_sources:
        if not item["exists"]:
            errors.append(f"declared source missing: {item['path']}")

    source_type = data_cfg.get("source") or manifest.get("data_source") or summary.get("data_source")
    vendor = data_cfg.get("vendor") or data_manifest.get("vendor")
    if not source_type:
        missing.append("explicit source type")
    if not vendor:
        missing.append("explicit data vendor")

    date_range = _date_range(cfg, summary, data_manifest)
    if not date_range["start"] or not date_range["end"]:
        missing.append("exact start/end date range")
    timezone = data_cfg.get("timezone") or data_cfg.get("exchange_timezone")
    if not timezone:
        missing.append("timezone")
    elif str(timezone) != "America/New_York":
        warnings.append(f"market timezone is {timezone}, not America/New_York")
    session = _session_contract(data_cfg, cfg)
    for field in ("session", "forced_flatten"):
        if not session.get(field):
            missing.append(f"explicit {field} semantics")

    contract = {
        "symbols": _contract_symbols(cfg, data_cfg, data_manifest),
        "continuous_contract": data_cfg.get("continuous_contract"),
        "roll_calendar": data_cfg.get("roll_calendar") or data_manifest.get("roll_calendar"),
        "roll_boundary_policy": data_cfg.get("roll_boundary_policy"),
    }
    if not contract["symbols"]:
        missing.append("contract symbols")
    if not contract["continuous_contract"] and not contract["roll_calendar"]:
        missing.append("continuous-contract or roll policy")

    core = cfg.get("core") if isinstance(cfg.get("core"), dict) else {}
    costs = {name: core.get(name) for name in ("commission_per_contract", "slippage_ticks", "tick_size", "point_value", "tick_value")}
    for field in ("commission_per_contract", "slippage_ticks", "tick_size"):
        if costs.get(field) is None:
            missing.append(f"cost/execution field {field}")
    if costs.get("point_value") is None and costs.get("tick_value") is None:
        missing.append("point_value or tick_value")

    event_source = data_cfg.get("execution_data") if isinstance(data_cfg.get("execution_data"), dict) else {}
    event_replay = _event_replay_contract(event_source, data_manifest, manifest)
    if event_replay["enabled"]:
        for field in ("detail_source", "event_ordering", "source_ordinal"):
            if not event_replay.get(field):
                missing.append(f"event replay {field}")

    transformations = _transformations(data_cfg, data_manifest)
    if _is_derived_source(data_cfg) and not transformations:
        missing.append("derived-cache parent and transformation")

    data_quality = _data_quality_coverage(directory, data_cfg, data_manifest)
    for field in ("timestamp_validation", "duplicate_check", "out_of_order_check", "session_gap_report"):
        if not data_quality.get(field):
            missing.append(f"data quality {field.replace('_', ' ')}")

    validation = _validation_coverage(directory, manifest, summary, cfg, root)
    if not validation["exported"]:
        missing.append("validation evidence export")
    if validation["lane"] == "event_replay" and not validation["event_transitions"]:
        errors.append("event-replay run lacks canonical event-transition validation")
    if validation["lane"] == "bar" and not validation["bar_windows"]:
        missing.append("bar validation windows")
    if validation["manual_status"] != "approved_for_testing":
        missing.append("hash-bound manual approved_for_testing decision")

    stages = _stage_coverage(summary)
    if not stages:
        missing.append("stage execution sequence")
    terminal = _strict_verdict(summary)
    if terminal not in STRICT_VERDICTS:
        missing.append("strict terminal verdict")
        terminal = "NEEDS MANUAL REVIEW"

    verdict = "FAIL" if errors else ("NEEDS MANUAL REVIEW" if missing else "PASS")
    authoritative = [str(path.relative_to(root)) for name in AUTHORITATIVE_NAMES if (path := directory / name).is_file()]
    for value in (validation.get("approval_path"), validation.get("evidence_dir")):
        if not value:
            continue
        path = _resolve(root, value)
        if path.is_file():
            authoritative.append(_display(root, path))
        elif path.is_dir():
            authoritative.extend(
                _display(root, item)
                for item in sorted(path.iterdir())
                if item.is_file() and item.name in {"metadata.json", "validation_checks.parquet", "event_transitions.parquet", "bar_windows.parquet"}
            )
    return {
        "run_dir": _display(root, directory),
        "run_uid": manifest.get("run_uid") or summary.get("run_uid") or _read_text(directory / "run_uid.txt"),
        "campaign_id": manifest.get("campaign_id") or summary.get("campaign_id"),
        "variant_id": manifest.get("variant_id") or summary.get("variant_id"),
        "test_run_id": manifest.get("test_run_id") or summary.get("test_run_id") or summary.get("run_id"),
        "lineage_verdict": verdict,
        "recorded_verdict": terminal,
        "errors": errors,
        "missing_evidence": sorted(set(missing)),
        "warnings": warnings,
        "hashes": hashes,
        "source_config": {"declared": source_declared or None, "snapshot": _display(root, source_snapshot) if source_snapshot.is_file() else None},
        "effective_config": _display(root, effective_snapshot) if effective_snapshot.is_file() else None,
        "data": {
            "dataset_id": cfg.get("dataset_id") or data_cfg.get("dataset_id") or manifest.get("dataset_id"),
            "source_type": source_type,
            "vendor": vendor,
            "raw_sources": raw_sources,
            "date_range": date_range,
            "timezone": timezone,
            "session": session,
            "contract": contract,
            "costs": costs,
            "transformations": transformations,
            "quality_coverage": data_quality,
            "data_manifest": _display(root, directory / "data_manifest.json") if data_manifest else None,
        },
        "event_replay": event_replay,
        "validation": validation,
        "stages": stages,
        "authoritative_artifacts": authoritative,
        "snapshot_caveat": "Generated config snapshots prove recorded provenance, not that the run was rerun.",
    }


def lineage_coverage(run_dirs: Iterable[str | Path], *, project_root: str | Path = ".") -> dict[str, Any]:
    rows = [inspect_run_lineage(path, project_root=project_root) for path in run_dirs]
    verdicts = Counter(row["lineage_verdict"] for row in rows)
    missing = Counter(item for row in rows for item in row["missing_evidence"])
    errors = Counter(item for row in rows for item in row["errors"])
    validation = Counter(row["validation"]["coverage_state"] for row in rows)
    return {
        "run_count": len(rows),
        "lineage_verdicts": dict(sorted(verdicts.items())),
        "validation_coverage": dict(sorted(validation.items())),
        "missing_evidence": dict(missing.most_common()),
        "errors": dict(errors.most_common()),
        "runs": rows,
    }


def _hash_reconciliation(*, declared: Any, snapshot: Path, authored: Path | None = None) -> dict[str, Any]:
    declared_text = str(declared or "").strip()
    snapshot_hash = _file_sha256(snapshot)
    authored_hash = _file_sha256(authored) if authored else ""
    mismatch = bool(declared_text and snapshot_hash and declared_text != snapshot_hash)
    authored_matches = None if not authored_hash or not declared_text else authored_hash == declared_text
    return {
        "declared": declared_text or None,
        "snapshot_sha256": snapshot_hash or None,
        "snapshot_matches": None if not declared_text or not snapshot_hash else declared_text == snapshot_hash,
        "authored_sha256": authored_hash or None,
        "authored_matches": authored_matches,
        "mismatch": mismatch,
    }


def _input_hash_reconciliation(directory: Path, manifest: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    manifest_hash = str(manifest.get("input_data_hash") or "").strip()
    summary_hash = str(summary.get("input_data_hash") or "").strip()
    declared = manifest_hash or summary_hash
    sidecar = _read_text(directory / "input_data_hash.txt")
    durable_values = [value for value in (manifest_hash, summary_hash, sidecar) if value]
    mismatch = len(set(durable_values)) > 1
    return {
        "declared": declared or None,
        "manifest": manifest_hash or None,
        "summary": summary_hash or None,
        "sidecar": sidecar or None,
        "snapshot_sha256": None,
        "snapshot_matches": None if not declared or not sidecar else declared == sidecar,
        "authored_sha256": None,
        "authored_matches": None,
        "mismatch": mismatch,
        "reconciled": len(durable_values) >= 2 and not mismatch,
    }


def _raw_sources(root: Path, data_cfg: dict[str, Any], data_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    values = []
    for key in ("raw_csv", "raw_parquet", "raw_dir", "archive"):
        if data_cfg.get(key):
            values.append((key, data_cfg[key]))
        if data_manifest.get(key):
            values.append((f"manifest_{key}", data_manifest[key]))
    execution = data_cfg.get("execution_data") if isinstance(data_cfg.get("execution_data"), dict) else {}
    for key in ("raw_dir", "archive", "contract_manifest", "quality_manifest"):
        if execution.get(key):
            values.append((f"execution_{key}", execution[key]))
    rows = []
    seen = set()
    for role, value in values:
        path = _resolve(root, str(value))
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"role": role, "path": _display(root, path), "exists": path.exists()})
    return rows


def _date_range(cfg: dict[str, Any], summary: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    subsets = []
    for section in ("core_grid", "wfa", "campaign_tests"):
        value = cfg.get(section)
        if isinstance(value, dict):
            subsets.append(value.get("data_subset") or value.get("subset") or value)
    start = data.get("start_date") or manifest.get("start_date")
    end = data.get("end_date") or manifest.get("end_date")
    for subset in subsets:
        if isinstance(subset, dict):
            start = start or subset.get("start_date")
            end = end or subset.get("end_date")
    metrics = summary.get("core_metrics") if isinstance(summary.get("core_metrics"), dict) else {}
    start = start or metrics.get("first_session")
    end = end or metrics.get("last_session")
    return {"start": start, "end": end}


def _session_contract(data: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
    apex = cfg.get("apex_rules") if isinstance(cfg.get("apex_rules"), dict) else {}
    session = data.get("session") or data.get("session_labels") or data.get("rth_start")
    if not session and data.get("session_start") and data.get("session_end"):
        session = f"{data['session_start']}-{data['session_end']}"
    return {
        "session": session,
        "rth_start": data.get("rth_start") or data.get("session_start"),
        "rth_end": data.get("rth_end") or data.get("session_end"),
        "forced_flatten": strategy.get("flatten_time") or apex.get("force_flatten_time") or (cfg.get("core") or {}).get("flatten_time"),
    }


def _contract_symbols(cfg: dict[str, Any], data: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    values = [cfg.get("symbol"), data.get("symbol"), manifest.get("contract"), manifest.get("contracts")]
    out = []
    for value in values:
        if isinstance(value, list):
            out.extend(str(item) for item in value if item)
        elif value:
            out.append(str(value))
    return sorted(set(out))


def _event_replay_contract(execution: dict[str, Any], data_manifest: dict[str, Any], run_manifest: dict[str, Any]) -> dict[str, Any]:
    lane = str(run_manifest.get("engine_lane") or "")
    explicit_source = execution.get("source") or data_manifest.get("detail_source")
    enabled = lane == "canonical_event_replay" or bool(explicit_source)
    source = explicit_source or (run_manifest.get("data_source") if enabled else None)
    semantics = execution.get("price_path_semantics") or data_manifest.get("price_path_semantics")
    return {
        "enabled": enabled,
        "detail_source": source,
        "event_ordering": execution.get("event_ordering") or semantics,
        "source_ordinal": execution.get("preserve_source_ordinal") or ("source_ordinal" if semantics and "ordinal" in str(semantics) else None),
    }


def _transformations(data: dict[str, Any], manifest: dict[str, Any]) -> list[Any]:
    values = []
    for key in ("transformations", "transformation", "derived_from", "construction_policy"):
        if data.get(key):
            values.append({key: data[key]})
        if manifest.get(key):
            values.append({key: manifest[key]})
    return values


def _data_quality_coverage(directory: Path, data: dict[str, Any], manifest: dict[str, Any]) -> dict[str, bool]:
    quality_files = [
        directory / "validation/data_quality_report.csv",
        directory / "data_quality_report.csv",
    ]
    declared = manifest.get("data_quality_report") or data.get("validation_report")
    report_exists = any(path.is_file() for path in quality_files) or bool(declared)
    checks = manifest.get("quality_checks") if isinstance(manifest.get("quality_checks"), dict) else {}
    return {
        "timestamp_validation": report_exists or bool(checks.get("timestamps_timezone_aware")),
        "duplicate_check": report_exists or bool(checks.get("duplicates_checked")),
        "out_of_order_check": report_exists or bool(checks.get("out_of_order_checked")),
        "session_gap_report": bool(manifest.get("session_gap_report") or checks.get("session_gaps_reported")),
    }


def _is_derived_source(data: dict[str, Any]) -> bool:
    source = str(data.get("source") or "").lower()
    return "cache" in source or bool(data.get("feature_cache"))


def _validation_coverage(
    directory: Path,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    cfg: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    validation_dirs = sorted(path for path in (directory / "validation_runs").glob("*") if path.is_dir())
    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), dict) else {}
    gate = research.get("validation_gate") if isinstance(research.get("validation_gate"), dict) else {}
    declared_evidence = _resolve(root, gate["evidence_dir"]) if gate.get("evidence_dir") else None
    if declared_evidence and declared_evidence.is_dir() and declared_evidence not in validation_dirs:
        validation_dirs.insert(0, declared_evidence)
    metadata = _read_json(validation_dirs[0] / "metadata.json") if validation_dirs else {}
    lane = str(metadata.get("validation_lane") or "")
    if not lane:
        lane = "event_replay" if manifest.get("engine_lane") == "canonical_event_replay" else "bar"
    declared_approval = _resolve(root, gate["approval_path"]) if gate.get("approval_path") else None
    approval = _read_json(declared_approval) if declared_approval else _read_json(directory / "validation_approval.json")
    if not approval:
        for path in validation_dirs:
            approval = _read_json(path / "approval.json")
            if approval:
                break
    exported = bool(validation_dirs or (directory / "validation").is_dir())
    checks = any((path / "validation_checks.parquet").is_file() for path in validation_dirs) or (directory / "validation/validation_checks.csv").is_file()
    bars = any((path / "bar_windows.parquet").is_file() for path in validation_dirs)
    events = any((path / "event_transitions.parquet").is_file() for path in validation_dirs)
    manual = str(approval.get("status") or "").lower() or "missing"
    if not exported:
        state = "missing"
    elif not checks:
        state = "exported_without_automated_checks"
    elif manual != "approved_for_testing":
        state = "automated_only_manual_missing"
    else:
        state = "approved"
    return {
        "exported": exported,
        "lane": lane,
        "automated_checks": checks,
        "bar_windows": bars,
        "event_transitions": events,
        "manual_status": manual,
        "coverage_state": state,
        "skip_validation_recorded": summary.get("skip_validation"),
        "evidence_dir": _display(root, declared_evidence) if declared_evidence else None,
        "approval_path": _display(root, declared_approval) if declared_approval else None,
    }


def _stage_coverage(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, stage in enumerate(summary.get("stages") or []):
        if not isinstance(stage, dict):
            continue
        rows.append({
            "index": index,
            "stage": stage.get("stage") or stage.get("name"),
            "status": stage.get("status"),
            "passed": stage.get("passed"),
            "reason": stage.get("reason") or stage.get("skip_reason") or stage.get("error"),
        })
    return rows


def _strict_verdict(summary: dict[str, Any]) -> str:
    value = str(summary.get("decision") or summary.get("status") or "").upper().replace("_", " ")
    if value in STRICT_VERDICTS:
        return value
    if summary.get("passed") is True:
        return "PASS"
    if summary.get("passed") is False or summary.get("halted") is True:
        return "FAIL"
    return "NEEDS MANUAL REVIEW"


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())


def _file_sha256(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None
