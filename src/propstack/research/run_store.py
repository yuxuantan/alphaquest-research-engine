from __future__ import annotations

import csv
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid
from typing import Any


RUN_UID_FILENAME = "run_uid.txt"
RUN_STORE_SCHEMA = "propstack.run-store/v1"


def ensure_run_uid(run_dir: str | Path) -> str:
    path = Path(run_dir) / RUN_UID_FILENAME
    if path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueError(f"invalid run UID in {path}: {value!r}") from exc
    value = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n", encoding="utf-8")
    return value


def read_run_uid(run_dir: str | Path) -> str | None:
    path = Path(run_dir) / RUN_UID_FILENAME
    if not path.is_file():
        return None
    value = path.read_text(encoding="utf-8").strip()
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def build_run_store_index(
    database_path: str | Path = "catalogs/research_registry.sqlite",
    *,
    project_root: str | Path = ".",
    output_root: str | Path = "run-store/generated",
    apply: bool = False,
) -> dict[str, int]:
    root = Path(project_root).resolve()
    database = _resolve(root, database_path)
    store = _resolve(root, output_root)
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        runs = connection.execute(
            """
            SELECT run_uid, campaign_id, variant_id, test_run_id, verdict,
                   updated_at, output_dir, summary_path, config_hash, input_data_hash
            FROM runs ORDER BY run_uid
            """
        ).fetchall()
    records = [_store_record(row) for row in runs]
    if apply:
        _reset_store(store)
        (store / ".generated_by_propstack").write_text(
            "Generated from catalogs/research_registry.sqlite. Do not edit.\n", encoding="utf-8"
        )
        for record in records:
            link = store / record["canonical_path"]
            link.parent.mkdir(parents=True, exist_ok=True)
            source = _resolve(root, record["output_dir"])
            if source.exists():
                link.symlink_to(os.path.relpath(source, link.parent), target_is_directory=True)
        _write_index(store / "index.csv", records)
        (store / "manifest.json").write_text(
            json.dumps(
                {
                    "schema": RUN_STORE_SCHEMA,
                    "storage_mode": "immutable_compatibility_links",
                    "source_registry": _display(root, database),
                    "run_count": len(records),
                    "note": "Legacy execution paths remain authoritative until a reviewed physical migration.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return {
        "runs": len(records),
        "resolvable_sources": sum(_resolve(root, record["output_dir"]).exists() for record in records),
    }


def backfill_run_uids(
    run_root: str | Path = "backtest-campaigns",
    *,
    project_root: str | Path = ".",
    apply: bool = False,
) -> dict[str, int]:
    root = Path(project_root).resolve()
    generated = _resolve(root, run_root)
    summary_paths = {
        *generated.glob("*/*/*/*/campaign_test_summary.json"),
        *generated.glob("*/*/*/*/variant_test_summary.json"),
    }
    run_dirs = sorted({path.parent for path in summary_paths})
    existing = 0
    created = 0
    invalid = 0
    for run_dir in run_dirs:
        uid_path = run_dir / RUN_UID_FILENAME
        if uid_path.is_file():
            if read_run_uid(run_dir):
                existing += 1
            else:
                invalid += 1
            continue
        created += 1
        if apply:
            ensure_run_uid(run_dir)
    return {"runs": len(run_dirs), "existing": existing, "created": created, "invalid": invalid}


def _store_record(row: sqlite3.Row) -> dict[str, Any]:
    updated_at = str(row["updated_at"] or "")
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        partition = f"runs/{parsed.year:04d}/{parsed.month:02d}/{row['run_uid']}"
    except ValueError:
        partition = f"runs/unknown/{row['run_uid']}"
    return {
        "run_uid": row["run_uid"],
        "canonical_path": partition,
        "campaign_id": row["campaign_id"],
        "variant_id": row["variant_id"],
        "test_run_id": row["test_run_id"],
        "verdict": row["verdict"],
        "updated_at": row["updated_at"],
        "output_dir": row["output_dir"],
        "summary_path": row["summary_path"],
        "config_hash": row["config_hash"],
        "input_data_hash": row["input_data_hash"],
    }


def _write_index(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = tuple(rows[0]) if rows else (
        "run_uid",
        "canonical_path",
        "campaign_id",
        "variant_id",
        "test_run_id",
        "verdict",
        "updated_at",
        "output_dir",
        "summary_path",
        "config_hash",
        "input_data_hash",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _reset_store(path: Path) -> None:
    if path.exists():
        marker = path / ".generated_by_propstack"
        if any(path.iterdir()) and not marker.is_file():
            raise RuntimeError(f"refusing to replace non-generated run store: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())
