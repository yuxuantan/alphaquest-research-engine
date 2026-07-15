from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

import pandas as pd
import yaml

from alphaquest.research.storage import display_path, load_storage_layout


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEAVY_GENERATED_PATTERNS = {
    "validation_cleaned_frames": "**/validation/cleaned_data.csv",
    "validation_feature_frames": "**/validation/features_data.csv",
    "validation_tick_windows": "**/validation_runs/*/tick_windows.parquet",
    "monkey_iteration_results": "**/monkey_results.csv",
    "wfa_monkey_iteration_results": "**/wfa_oos_monkey_results.csv",
    "incubation_monkey_iteration_results": "**/incubation_monkey_results.csv",
    "monte_carlo_path_events": "**/wfa_oos_monte_carlo_path_events.csv",
    "monte_carlo_path_trades": "**/wfa_oos_monte_carlo_path_trades.csv",
    "generated_html_reports": "**/*.html",
    "core_grid_iteration_trades": "**/core_grid_iteration_trades.csv",
    "core_grid_iteration_daily": "**/core_grid_iteration_daily.csv",
}
JUNK_DIR_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
JUNK_FILE_NAMES = {".DS_Store"}
JUNK_FILE_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak"}
TOP_LEVEL_RUN_ID_KEYS = {"test_run_id", "campaign_test_run_id", "run_name", "run_id"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune reproducible bulk artifacts and exact superseded error runs.")
    parser.add_argument("--root")
    parser.add_argument(
        "--audit-prefix",
        default=f"research_artifacts/cleanup/repository_cleanup_{datetime.now().date().isoformat().replace('-', '')}",
    )
    parser.add_argument("--apply", action="store_true", help="Delete candidates. Without this flag the command is dry-run.")
    args = parser.parse_args()

    layout = load_storage_layout(PROJECT_ROOT)
    generated_root = PROJECT_ROOT / (
        args.root or display_path(layout.evidence_roots[0], PROJECT_ROOT)
    )
    payload_groups = find_heavy_generated_payloads(generated_root)
    redundant_runs = find_redundant_runs(generated_root)
    junk_paths = find_junk_paths(PROJECT_ROOT)
    report = build_report(payload_groups, redundant_runs, junk_paths, applied=False)

    audit_prefix = PROJECT_ROOT / args.audit_prefix
    audit_prefix.parent.mkdir(parents=True, exist_ok=True)
    if args.apply:
        report["status"] = "APPROVED_PENDING_APPLY"
        _write_audit(audit_prefix, report)

    if args.apply:
        removed_run_paths = {str(item["remove_path"].relative_to(PROJECT_ROOT)) for item in redundant_runs}
        for paths in payload_groups.values():
            for path in paths:
                path.unlink(missing_ok=True)
        for item in redundant_runs:
            shutil.rmtree(item["remove_path"])
        for path in sorted(junk_paths, key=lambda item: len(item.parts), reverse=True):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        _remove_stale_source_result_pointers(removed_run_paths)
        _remove_stale_runs_index_rows(removed_run_paths)
        report["status"] = "APPLIED"
        report["applied_at"] = datetime.now(timezone.utc).isoformat()

    _write_audit(audit_prefix, report)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"{mode}: files={report['deleted_file_count']} runs={report['removed_run_count']} "
        f"reclaim_gib={report['reclaim_bytes'] / 1024**3:.2f}"
    )
    return 0


def find_heavy_generated_payloads(root: Path) -> dict[str, list[Path]]:
    return {
        label: sorted(path for path in root.glob(pattern) if path.is_file() and _payload_is_reproducible(path))
        for label, pattern in HEAVY_GENERATED_PATTERNS.items()
    }


def find_redundant_runs(root: Path) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for run_dir in root.glob("*/*/*/*"):
        config_path = run_dir / "effective_config.yaml"
        if not run_dir.is_dir() or not config_path.is_file():
            continue
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        identity = _config_identity(config)
        summary = _read_json(run_dir / "campaign_test_summary.json")
        stages = summary.get("stages") if isinstance(summary.get("stages"), list) else []
        groups[(*run_dir.parts[-4:-1], identity)].append(
            {
                "path": run_dir,
                "summary": summary,
                "stages": stages,
                "has_error": any(stage.get("status") == "error" for stage in stages if isinstance(stage, dict)),
            }
        )

    redundant = []
    for group in groups.values():
        if len(group) < 2:
            continue
        valid = [item for item in group if item["summary"] and not item["has_error"]]
        errors = [item for item in group if item["has_error"]]
        if not valid or not errors:
            continue
        keep = max(valid, key=_run_preference)
        for item in errors:
            summary = item["summary"]
            redundant.append(
                {
                    "remove_path": item["path"],
                    "keep_path": keep["path"],
                    "size_bytes": _tree_size(item["path"]),
                    "config_identity": _config_identity(
                        yaml.safe_load((item["path"] / "effective_config.yaml").read_text(encoding="utf-8")) or {}
                    ),
                    "source_config_hash": summary.get("source_config_hash"),
                    "effective_config_hash": summary.get("config_hash"),
                    "updated_at": summary.get("updated_at"),
                    "error": _first_stage_error(item["stages"]),
                    "reason": "same effective config as completed replacement; superseded run ended in error",
                }
            )
    return sorted(redundant, key=lambda item: str(item["remove_path"]))


def find_junk_paths(root: Path) -> list[Path]:
    paths = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        if current_path == root / ".git":
            dirs[:] = []
            continue
        for directory in list(dirs):
            if directory in JUNK_DIR_NAMES:
                paths.append(current_path / directory)
                dirs.remove(directory)
        for filename in files:
            path = current_path / filename
            if filename in JUNK_FILE_NAMES or path.suffix.lower() in JUNK_FILE_SUFFIXES:
                paths.append(path)
    return sorted(set(paths))


def build_report(
    payload_groups: dict[str, list[Path]],
    redundant_runs: list[dict[str, Any]],
    junk_paths: list[Path],
    *,
    applied: bool,
) -> dict[str, Any]:
    payload_summary = {}
    inventory: list[dict[str, Any]] = []
    candidate_files: set[Path] = set()
    for label, paths in payload_groups.items():
        size = sum(path.stat().st_size for path in paths)
        payload_summary[label] = {"file_count": len(paths), "bytes": size}
        candidate_files.update(paths)
        inventory.extend(
            {
                "path": path,
                "artifact_class": f"reproducible_bulk_output:{label}",
                "size_bytes": path.stat().st_size,
                "references": _payload_references(path),
                "reproducible": True,
                "retention_decision": "delete",
                "reason": "bulk iteration or visualization payload is reconstructable from retained compact evidence",
            }
            for path in paths
        )
    for item in redundant_runs:
        candidate_files.update(path for path in item["remove_path"].rglob("*") if path.is_file())
        inventory.append(
            {
                "path": item["remove_path"],
                "artifact_class": "superseded_duplicate:error_run",
                "size_bytes": item["size_bytes"],
                "references": [item["keep_path"]],
                "reproducible": True,
                "retention_decision": "delete",
                "reason": item["reason"],
            }
        )
    for path in junk_paths:
        if path.is_dir():
            candidate_files.update(item for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            candidate_files.add(path)
        inventory.append(
            {
                "path": path,
                "artifact_class": "cache_or_junk",
                "size_bytes": _tree_size(path),
                "references": [],
                "reproducible": True,
                "retention_decision": "delete",
                "reason": "interpreter, test, lint, editor, or operating-system cache/junk",
            }
        )
    reclaim_bytes = sum(path.stat().st_size for path in candidate_files if path.exists())
    junk_bytes = sum(
        path.stat().st_size
        for junk_path in junk_paths
        for path in ([junk_path] if junk_path.is_file() else junk_path.rglob("*"))
        if path.is_file()
    )
    return {
        "status": "APPLIED" if applied else "DRY_RUN",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "remove only reproducible bulk payloads and error runs replaced by the same effective config",
        "payload_classes": payload_summary,
        "removed_runs": redundant_runs,
        "junk_path_count": len(junk_paths),
        "junk_bytes": junk_bytes,
        "deleted_file_count": len(candidate_files),
        "removed_run_count": len(redundant_runs),
        "reclaim_bytes": reclaim_bytes,
        "inventory": sorted(inventory, key=lambda item: str(item["path"])),
        "retained": [
            "authored campaigns and strategy modules",
            "research ledgers and methodology audits",
            "effective/source configs and run manifests",
            "campaign, variant, stage, core-grid, monkey, WFA, and Monte Carlo summaries",
            "fixed-config trade logs and equity CSVs",
            "WFA stitched OOS trade logs",
            "compact validation trades, conditions, bar windows, exit audits, and checks",
        ],
    }


def _write_audit(prefix: Path, report: dict[str, Any]) -> None:
    prefix.with_suffix(".json").write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")
    prefix.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")


def _config_identity(config: dict[str, Any]) -> str:
    normalized = {key: value for key, value in config.items() if key not in TOP_LEVEL_RUN_ID_KEYS | {"research_policy"}}
    payload = json.dumps(normalized, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _run_preference(item: dict[str, Any]) -> tuple[int, str, str]:
    summary = item["summary"]
    stages = item["stages"]
    return len(stages), str(summary.get("updated_at") or ""), str(item["path"])


def _first_stage_error(stages: list[dict[str, Any]]) -> str | None:
    for stage in stages:
        if isinstance(stage, dict) and stage.get("status") == "error":
            return str(stage.get("error") or stage.get("message") or stage.get("stage") or "error")
    return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _payload_is_reproducible(path: Path) -> bool:
    if path.suffix.lower() == ".html":
        return (path.parent / f"{path.stem}.csv").is_file()
    run_root = _run_root(path)
    if run_root is None:
        return False
    if not (run_root / "campaign_test_summary.json").is_file():
        return False
    if not ((run_root / "effective_config.yaml").is_file() and (run_root / "source_config.yaml").is_file()):
        return False
    if "validation_runs" in path.parts and path.name == "tick_windows.parquet":
        validation_dir = path.parent
        compact = (
            validation_dir / "trades.parquet",
            validation_dir / "condition_snapshots.parquet",
            validation_dir / "exit_audits.parquet",
            validation_dir / "validation_checks.parquet",
        )
        if not all(item.is_file() for item in compact):
            return False
        return bool(_existing_raw_sources(run_root / "effective_config.yaml"))
    return True


def _payload_references(path: Path) -> list[Path]:
    if path.suffix.lower() == ".html":
        csv_path = path.parent / f"{path.stem}.csv"
        return [csv_path] if csv_path.is_file() else []
    run_root = _run_root(path)
    if run_root is None:
        return []
    candidates = [
        run_root / "campaign_test_summary.json",
        run_root / "run_manifest.json",
        run_root / "source_config.yaml",
        run_root / "effective_config.yaml",
        run_root / "input_data_hash.txt",
        path.parent / "trades.parquet",
        path.parent / "condition_snapshots.parquet",
        path.parent / "event_transitions.parquet",
        path.parent / "exit_audits.parquet",
        path.parent / "validation_checks.parquet",
        *_existing_raw_sources(run_root / "effective_config.yaml"),
    ]
    return [item for item in candidates if item.exists()]


def _run_root(path: Path) -> Path | None:
    for parent in path.parents:
        if (parent / "campaign_test_summary.json").is_file():
            return parent
    return None


def _existing_raw_sources(config_path: Path) -> list[Path]:
    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    execution = data.get("execution_data") if isinstance(data.get("execution_data"), dict) else {}
    values = []
    for container in (data, execution):
        for key in ("raw_csv", "raw_parquet", "raw_dir", "archive", "roll_calendar", "contract_manifest", "quality_manifest"):
            if container.get(key):
                values.append(Path(str(container[key])))
    return sorted({path for path in values if path.exists()})


def _remove_stale_source_result_pointers(removed_run_paths: set[str]) -> None:
    layout = load_storage_layout(PROJECT_ROOT)
    for index_path in (
        path
        for campaign_root in layout.campaign_roots
        for path in campaign_root.rglob("results_index.yaml")
    ):
        try:
            data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        runs = data.get("runs") if isinstance(data.get("runs"), list) else []
        retained = [item for item in runs if str(item.get("run_dir")) not in removed_run_paths]
        if retained == runs:
            continue
        data["runs"] = retained
        index_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _remove_stale_runs_index_rows(removed_run_paths: set[str]) -> None:
    by_parent: dict[Path, set[str]] = defaultdict(set)
    for run_path in removed_run_paths:
        path = Path(run_path)
        by_parent[PROJECT_ROOT / path.parent].add(path.name)
    for parent, run_ids in by_parent.items():
        index_path = parent / "runs_index.csv"
        if not index_path.is_file():
            continue
        rows = pd.read_csv(index_path)
        if "test_run_id" not in rows.columns:
            continue
        retained = rows[~rows["test_run_id"].astype(str).isin(run_ids)]
        retained.to_csv(index_path, index=False)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value.relative_to(PROJECT_ROOT) if value.is_relative_to(PROJECT_ROOT) else value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Repository Cleanup Audit",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Reclaimed: `{report['reclaim_bytes'] / 1024**3:.2f} GiB`",
        f"Generated files removed: `{report['deleted_file_count']}`",
        f"Superseded error runs removed: `{report['removed_run_count']}`",
        "",
        "## Removed Payload Classes",
        "",
    ]
    for label, item in report["payload_classes"].items():
        lines.append(f"- `{label}`: {item['file_count']} files, {item['bytes'] / 1024**2:.1f} MiB")
    lines.extend(["", "## Removed Runs", ""])
    for item in report["removed_runs"]:
        lines.append(f"- `{_json_safe(item['remove_path'])}` -> kept `{_json_safe(item['keep_path'])}`")
    lines.extend(["", "## Retained Evidence", ""])
    lines.extend(f"- {item}" for item in report["retained"])
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
