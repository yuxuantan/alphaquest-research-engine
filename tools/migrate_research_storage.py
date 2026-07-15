from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from alphaquest.research.storage import load_storage_layout, resolve_recorded_path


SCHEMA = "alphaquest.storage-migration/v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan, apply, and verify the research storage migration.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--manifest")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    layout = load_storage_layout(root)
    manifest_path = Path(args.manifest) if args.manifest else layout.migration_manifest
    if manifest_path is None:
        raise SystemExit("storage_layout.yaml must configure migration_manifest")
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path

    if not manifest_path.is_file():
        manifest = plan_migration(root, manifest_path)
        _write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.apply:
        manifest = apply_migration(root, manifest_path, manifest)
    if args.verify or args.apply:
        manifest = verify_migration(root, manifest_path, manifest)
    print(
        f"{manifest_path.relative_to(root)}: status={manifest['status']} "
        f"moves={len(manifest['moves'])} paths={manifest['resolution_snapshot']['path_count']} "
        f"uids={manifest['resolution_snapshot']['uid_count']}"
    )
    return 0 if manifest["status"] == "APPLIED_VERIFIED" or not (args.apply or args.verify) else 1


def plan_migration(root: Path, manifest_path: Path) -> dict[str, Any]:
    layout = load_storage_layout(root)
    moves = [
        _move_record(root, root / "campaigns", layout.archive_campaign_roots[0], "authored_archive"),
        _move_record(root, root / "backtest-campaigns", layout.evidence_roots[0], "run_evidence"),
    ]
    snapshot = _resolution_snapshot(root)
    return {
        "schema": SCHEMA,
        "status": "PLANNED",
        "created_at": _now(),
        "manifest_path": _display(root, manifest_path),
        "legacy_prefixes": dict(layout.legacy_prefixes),
        "moves": moves,
        "resolution_snapshot": snapshot,
        "verification": None,
    }


def apply_migration(root: Path, manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    _validate_manifest(manifest)
    if manifest["status"] == "APPLIED_VERIFIED":
        return manifest
    if manifest["status"] not in {"PLANNED", "APPLY_FAILED"}:
        raise RuntimeError(f"manifest is not applyable: {manifest['status']}")
    manifest["status"] = "APPLYING"
    _write_json(manifest_path, manifest)
    try:
        for move in manifest["moves"]:
            source = root / move["source"]
            destination = root / move["destination"]
            if not source.exists() and destination.exists():
                continue
            if not source.exists():
                raise RuntimeError(f"migration source is missing: {source}")
            if destination.exists():
                raise RuntimeError(f"migration destination already exists: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
        layout = load_storage_layout(root)
        layout.active_campaign_root.mkdir(parents=True, exist_ok=True)
        manifest["status"] = "APPLIED_PENDING_VERIFICATION"
        manifest["applied_at"] = _now()
    except Exception as exc:
        manifest["status"] = "APPLY_FAILED"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(manifest_path, manifest)
        raise
    _write_json(manifest_path, manifest)
    return manifest


def verify_migration(root: Path, manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    _validate_manifest(manifest)
    failures: list[str] = []
    verified_files = 0
    verified_bytes = 0
    for move in manifest["moves"]:
        source = root / move["source"]
        destination = root / move["destination"]
        if source.exists():
            failures.append(f"legacy source still exists: {move['source']}")
        if not destination.exists():
            failures.append(f"destination missing: {move['destination']}")
            continue
        current = _tree_stats(destination)
        for key in ("file_count", "total_bytes", "tree_sha256"):
            if current[key] != move[key]:
                failures.append(f"{move['destination']} {key} mismatch")
        verified_files += current["file_count"]
        verified_bytes += current["total_bytes"]

    paths = manifest["resolution_snapshot"]["paths"]
    layout = load_storage_layout(root)
    resolvable_paths = 0
    for item in paths:
        resolved = resolve_recorded_path(item["recorded_path"], project_root=root, layout=layout)
        if item["existed_before"]:
            if resolved.exists():
                resolvable_paths += 1
            else:
                failures.append(f"previously resolvable path is missing: {item['recorded_path']}")

    expected_uids = set(manifest["resolution_snapshot"]["run_uids"])
    actual_uids = {
        path.read_text(encoding="utf-8").strip()
        for evidence_root in layout.evidence_roots
        if evidence_root.exists()
        for path in evidence_root.glob("*/*/*/*/run_uid.txt")
    }
    missing_uids = sorted(expected_uids - actual_uids)
    if missing_uids:
        failures.append(f"missing historical run UIDs: {len(missing_uids)}")

    manifest["verification"] = {
        "verified_at": _now(),
        "verified_files": verified_files,
        "verified_bytes": verified_bytes,
        "previously_resolvable_paths": sum(item["existed_before"] for item in paths),
        "resolved_after_migration": resolvable_paths,
        "preexisting_missing_paths": sum(not item["existed_before"] for item in paths),
        "expected_run_uids": len(expected_uids),
        "resolved_run_uids": len(expected_uids & actual_uids),
        "failures": failures,
    }
    manifest["status"] = "APPLIED_VERIFIED" if not failures else "VERIFICATION_FAILED"
    _write_json(manifest_path, manifest)
    if failures:
        raise RuntimeError("storage migration verification failed: " + "; ".join(failures[:10]))
    return manifest


def _move_record(root: Path, source: Path, destination: Path, kind: str) -> dict[str, Any]:
    if not source.exists():
        raise FileNotFoundError(source)
    stats = _tree_stats(source)
    return {
        "kind": kind,
        "source": _display(root, source),
        "destination": _display(root, destination),
        **stats,
    }


def _tree_stats(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file() and not item.is_symlink())
    total = 0
    for file_path in files:
        relative = file_path.relative_to(path).as_posix()
        content_hash = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                content_hash.update(chunk)
        size = file_path.stat().st_size
        total += size
        digest.update(f"{relative}\0{size}\0{content_hash.hexdigest()}\n".encode())
    return {"file_count": len(files), "total_bytes": total, "tree_sha256": digest.hexdigest()}


def _resolution_snapshot(root: Path) -> dict[str, Any]:
    database = root / "catalogs/research_registry.sqlite"
    paths: set[str] = set()
    uids: set[str] = set()
    if database.is_file():
        with sqlite3.connect(database) as connection:
            for table, columns in (
                ("runs", ("run_uid", "output_dir", "summary_path", "source_config_path")),
                ("artifacts", ("path",)),
                ("campaigns", ("definition_path",)),
                ("variants", ("definition_path",)),
                ("attempts", ("definition_path",)),
            ):
                for row in connection.execute(f"SELECT {', '.join(columns)} FROM {table}"):
                    for column, value in zip(columns, row):
                        if column == "run_uid" and value:
                            uids.add(str(value))
                        elif value:
                            paths.add(str(value))
    ledger = root / "research_ledger.csv"
    if ledger.is_file():
        with ledger.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for column in ("config_path", "report_path"):
                    if row.get(column):
                        paths.add(row[column])
    entries = []
    for recorded in sorted(paths):
        resolved = resolve_recorded_path(recorded, project_root=root)
        entries.append(
            {
                "recorded_path": recorded,
                "resolved_before": _display(root, resolved),
                "existed_before": resolved.exists(),
            }
        )
    return {
        "source_database": "catalogs/research_registry.sqlite",
        "path_count": len(entries),
        "uid_count": len(uids),
        "paths": entries,
        "run_uids": sorted(uids),
    }


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"unsupported migration manifest schema: {manifest.get('schema')!r}")
    if not manifest.get("moves"):
        raise ValueError("migration manifest contains no moves")


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
