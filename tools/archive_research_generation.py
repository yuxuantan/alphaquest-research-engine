from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Iterable


LEDGER_HEADER = (
    "timestamp,campaign_id,variant_id,instrument,timeframe,edge,variant_mechanic,"
    "parameter_space,data_scope,config_path,report_path,stage,result,decision,"
    "failure_reason,rescue_attempt\n"
)


def _children(root: Path, *, keep: Iterable[str] = ()) -> list[Path]:
    retained = set(keep)
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.name not in retained)


def _file_count(path: Path) -> int:
    if path.is_file():
        return 1
    return sum(1 for child in path.rglob("*") if child.is_file())


def build_operations(project_root: Path, reset_id: str) -> tuple[Path, list[tuple[Path, Path]]]:
    archive_root = project_root / "research" / "archived_generations" / reset_id
    operations: list[tuple[Path, Path]] = []

    groups = (
        (project_root / "research" / "campaigns" / "active", archive_root / "campaigns" / "active", ()),
        (
            project_root / "research" / "campaigns" / "archive",
            archive_root / "campaigns" / "archive",
            ("README.md",),
        ),
        (project_root / "research" / "evidence" / "runs", archive_root / "evidence" / "runs", ()),
        (project_root / "research" / "drafts", archive_root / "drafts", ("README.md",)),
        (project_root / "research_artifacts", archive_root / "research_artifacts", ("README.md",)),
        (project_root / "catalogs", archive_root / "catalogs", ("README.md", ".DS_Store")),
        (project_root / "views", archive_root / "views", ("README.md",)),
    )
    for source_root, destination_root, keep in groups:
        for source in _children(source_root, keep=keep):
            operations.append((source, destination_root / source.name))

    ledger = project_root / "research_ledger.csv"
    if ledger.is_file():
        operations.append((ledger, archive_root / "research_ledger.csv"))
    return archive_root, operations


def archive_generation(*, project_root: Path, reset_id: str, apply: bool) -> dict[str, object]:
    archive_root, operations = build_operations(project_root, reset_id)
    collisions = [str(destination) for _source, destination in operations if destination.exists()]
    if collisions:
        raise RuntimeError(f"archive destination collision(s): {collisions[:10]}")

    entries = [
        {
            "source": str(source.relative_to(project_root)),
            "destination": str(destination.relative_to(project_root)),
            "kind": "directory" if source.is_dir() else "file",
            "file_count": _file_count(source),
        }
        for source, destination in operations
    ]
    manifest: dict[str, object] = {
        "schema": "alphaquest.research-generation-archive/v1",
        "reset_id": reset_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": (
            "User-authorized clean-slate reset: every prior campaign, variant, run, draft, ledger row, "
            "and generated research artifact was unverified by manual mechanics review."
        ),
        "policy": (
            "Prior material is recoverable for audit but excluded from configured campaign, evidence, "
            "draft, ledger, catalog, view, and research-artifact surfaces. No historical verdict is trusted."
        ),
        "archive_root": str(archive_root.relative_to(project_root)),
        "operation_count": len(entries),
        "file_count": sum(int(entry["file_count"]) for entry in entries),
        "applied": apply,
        "entries": entries,
    }
    if not apply:
        return manifest

    archive_root.mkdir(parents=True, exist_ok=False)
    for source, destination in operations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    (project_root / "research_ledger.csv").write_text(LEDGER_HEADER, encoding="utf-8")
    manifest_path = project_root / "research_artifacts" / "governance" / f"research_reset_{reset_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest["manifest_path"] = str(manifest_path.relative_to(project_root))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Recoverably archive one unverified research generation.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--reset-id", default="clean_slate_20260720")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the moves. Without this flag, print a dry-run manifest only.",
    )
    args = parser.parse_args()
    payload = archive_generation(
        project_root=Path(args.project_root).resolve(),
        reset_id=str(args.reset_id),
        apply=bool(args.apply),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
