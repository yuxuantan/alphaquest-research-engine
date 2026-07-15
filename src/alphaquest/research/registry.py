from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable

import yaml

from alphaquest.research.catalog import catalog_rows
from alphaquest.research.run_store import read_run_uid
from alphaquest.maintenance.code_catalog import generate_code_views


SCHEMA_VERSION = "1"
VIEW_STATES = ("active", "review_queue", "candidate", "closed")
CRITICAL_ARTIFACTS = (
    "campaign_test_summary.json",
    "variant_test_summary.json",
    "run_manifest.json",
    "effective_config.yaml",
    "source_config.yaml",
    "config_hash.txt",
    "input_data_hash.txt",
    "methodology_audit.md",
    "run_uid.txt",
)


def build_registry(
    *,
    project_root: str | Path = ".",
    database_path: str | Path = "catalogs/research_registry.sqlite",
    campaign_root: str | Path = "campaigns",
    run_root: str | Path = "backtest-campaigns",
    research_artifact_root: str | Path = "research_artifacts",
) -> dict[str, int]:
    root = Path(project_root).resolve()
    db_path = _resolve(root, database_path)
    campaigns_path = _resolve(root, campaign_root)
    runs_path = _resolve(root, run_root)
    research_artifacts_path = _resolve(root, research_artifact_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = db_path.with_suffix(f"{db_path.suffix}.tmp")
    temporary_path.unlink(missing_ok=True)

    source_campaigns, source_variants, source_attempts = _source_records(root, campaigns_path)
    runs = _run_records(root, runs_path)
    campaign_records = _campaign_records(root, source_campaigns, source_variants, runs, runs_path)
    durable_artifacts = _durable_artifact_records(root, research_artifacts_path, campaign_records)

    connection = sqlite3.connect(temporary_path)
    try:
        _create_schema(connection)
        _insert_records(connection, campaign_records, source_variants, source_attempts, runs, durable_artifacts)
        connection.commit()
        result = {
            "campaigns": len(campaign_records),
            "variants": len(source_variants),
            "attempts": len(source_attempts),
            "runs": len(runs),
            "research_artifacts": len(durable_artifacts),
        }
    finally:
        connection.close()
    temporary_path.replace(db_path)
    return result


def generate_views(
    *,
    project_root: str | Path = ".",
    database_path: str | Path = "catalogs/research_registry.sqlite",
    output_root: str | Path = "views",
    recent_failure_limit: int = 100,
) -> dict[str, int]:
    root = Path(project_root).resolve()
    db_path = _resolve(root, database_path)
    views_path = _resolve(root, output_root)
    _reset_generated_directory(views_path)
    (views_path / ".generated_by_alphaquest").write_text(
        "Generated from catalogs/research_registry.sqlite. Do not edit.\n", encoding="utf-8"
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    artifact_counts: dict[str, int] = {}
    try:
        for state in VIEW_STATES:
            rows = connection.execute(
                """
                SELECT campaign_id, title, edge_family, lifecycle_state, authored_decision,
                       run_count, variant_count, latest_updated_at, definition_path
                FROM campaigns WHERE lifecycle_state = ? ORDER BY campaign_id
                """,
                (state,),
            ).fetchall()
            _write_campaign_view(root, views_path / state, rows, state, include_definition_links=state != "closed")
            counts[state] = len(rows)

        failures = connection.execute(
            """
            SELECT run_uid, campaign_id, variant_id, test_run_id, failed_stage,
                   updated_at, summary_path, output_dir
            FROM runs WHERE verdict = 'FAIL'
            ORDER BY COALESCE(updated_at, '') DESC, campaign_id, variant_id
            LIMIT ?
            """,
            (recent_failure_limit,),
        ).fetchall()
        _write_failure_view(root, views_path / "recent_failures", failures)
        counts["recent_failures"] = len(failures)
        review_runs = connection.execute(
            """
            SELECT run_uid, campaign_id, variant_id, test_run_id, failed_stage,
                   updated_at, summary_path, output_dir
            FROM runs WHERE verdict = 'NEEDS MANUAL REVIEW'
            ORDER BY COALESCE(updated_at, '') DESC, campaign_id, variant_id
            """
        ).fetchall()
        _write_rows(
            views_path / "review_queue" / "runs.csv",
            (
                "run_uid",
                "campaign_id",
                "variant_id",
                "test_run_id",
                "failed_stage",
                "updated_at",
                "summary_path",
                "output_dir",
            ),
            review_runs,
        )
        counts["review_runs"] = len(review_runs)
        _write_review_queue_readme(views_path / "review_queue", counts["review_queue"], review_runs)
        artifact_counts = _write_artifact_views(connection, views_path / "artifacts")
        _write_discovery_views(connection, views_path)
        built_at = _metadata_value(connection, "built_at")
    finally:
        connection.close()

    _write_views_readme(views_path, counts, artifact_counts, built_at)
    code_counts = generate_code_views(project_root=root, output_root=views_path / "code")
    counts.update({f"code_{key}": value for key, value in code_counts.items()})
    counts.update({f"artifacts_{key}": value for key, value in artifact_counts.items()})
    return counts


def export_registry_csvs(
    *,
    project_root: str | Path = ".",
    database_path: str | Path = "catalogs/research_registry.sqlite",
    output_root: str | Path = "catalogs/exports",
) -> dict[str, int]:
    root = Path(project_root).resolve()
    db_path = _resolve(root, database_path)
    output_path = _resolve(root, output_root)
    output_path.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    try:
        for table in (
            "campaigns",
            "variants",
            "attempts",
            "runs",
            "stages",
            "artifacts",
            "artifact_objects",
            "research_artifacts",
        ):
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            columns = [item[1] for item in connection.execute(f"PRAGMA table_info({table})")]
            with (output_path / f"{table}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(dict(row) for row in rows)
            counts[table] = len(rows)
    finally:
        connection.close()
    return counts


def registry_summary(database_path: str | Path) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        lifecycle = {
            row["lifecycle_state"]: row["count"]
            for row in connection.execute(
                "SELECT lifecycle_state, COUNT(*) AS count FROM campaigns GROUP BY lifecycle_state"
            )
        }
        verdicts = {
            row["verdict"]: row["count"]
            for row in connection.execute("SELECT verdict, COUNT(*) AS count FROM runs GROUP BY verdict")
        }
        return {
            "schema_version": _metadata_value(connection, "schema_version"),
            "built_at": _metadata_value(connection, "built_at"),
            "campaigns": connection.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
            "variants": connection.execute("SELECT COUNT(*) FROM variants").fetchone()[0],
            "attempts": connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
            "runs": connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "research_artifacts": connection.execute("SELECT COUNT(*) FROM research_artifacts").fetchone()[0],
            "artifact_objects": connection.execute("SELECT COUNT(*) FROM artifact_objects").fetchone()[0],
            "dedup_reclaimable_bytes": connection.execute(
                "SELECT COALESCE(SUM(reclaimable_bytes), 0) FROM artifact_objects"
            ).fetchone()[0],
            "campaign_lifecycle": lifecycle,
            "run_verdicts": verdicts,
        }
    finally:
        connection.close()


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE campaigns (
            campaign_id TEXT PRIMARY KEY,
            title TEXT,
            edge_family TEXT,
            definition_path TEXT,
            authored_status TEXT,
            authored_decision TEXT,
            lifecycle_state TEXT NOT NULL,
            lifecycle_reason TEXT NOT NULL,
            variant_count INTEGER NOT NULL,
            attempt_count INTEGER NOT NULL,
            run_count INTEGER NOT NULL,
            latest_updated_at TEXT
        );
        CREATE TABLE variants (
            campaign_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            definition_path TEXT NOT NULL,
            symbol TEXT,
            timeframe TEXT,
            dataset_id TEXT,
            config_hash TEXT NOT NULL,
            PRIMARY KEY (campaign_id, variant_id),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );
        CREATE TABLE attempts (
            campaign_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            attempt_kind TEXT NOT NULL,
            parent_variant_id TEXT,
            test_run_id TEXT,
            definition_path TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            PRIMARY KEY (campaign_id, attempt_id, variant_id, definition_path),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );
        CREATE TABLE runs (
            run_uid TEXT PRIMARY KEY,
            campaign_id TEXT,
            variant_id TEXT,
            test_run_id TEXT,
            symbol TEXT,
            dataset_id TEXT,
            timeframe TEXT,
            data_source TEXT,
            verdict TEXT NOT NULL,
            halted INTEGER,
            failed_stage TEXT,
            stage_count INTEGER NOT NULL,
            research_policy_version TEXT,
            research_policy_hash TEXT,
            engine_contract_version TEXT,
            config_hash TEXT,
            source_config_hash TEXT,
            input_data_hash TEXT,
            output_dir TEXT,
            summary_path TEXT NOT NULL,
            source_config_path TEXT,
            attempt_id TEXT,
            parent_run_uid TEXT,
            updated_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );
        CREATE TABLE stages (
            run_uid TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            stage_name TEXT,
            status TEXT,
            passed INTEGER,
            PRIMARY KEY (run_uid, stage_index),
            FOREIGN KEY (run_uid) REFERENCES runs(run_uid)
        );
        CREATE TABLE artifacts (
            run_uid TEXT NOT NULL,
            artifact_kind TEXT NOT NULL,
            path TEXT NOT NULL,
            size_bytes INTEGER,
            sha256 TEXT,
            PRIMARY KEY (run_uid, path),
            FOREIGN KEY (run_uid) REFERENCES runs(run_uid)
        );
        CREATE TABLE research_artifacts (
            path TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            category TEXT NOT NULL,
            campaign_id TEXT,
            suffix TEXT,
            size_bytes INTEGER NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );
        CREATE TABLE artifact_objects (
            sha256 TEXT PRIMARY KEY,
            size_bytes INTEGER NOT NULL,
            reference_count INTEGER NOT NULL,
            canonical_source_path TEXT NOT NULL,
            reclaimable_bytes INTEGER NOT NULL
        );
        CREATE INDEX runs_campaign_idx ON runs(campaign_id, variant_id, updated_at);
        CREATE INDEX runs_verdict_idx ON runs(verdict, updated_at);
        CREATE INDEX attempts_campaign_idx ON attempts(campaign_id, attempt_id);
        """
    )


def _insert_records(
    connection: sqlite3.Connection,
    campaigns: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    durable_artifacts: list[dict[str, Any]],
) -> None:
    connection.executemany(
        "INSERT INTO metadata(key, value) VALUES (?, ?)",
        (("schema_version", SCHEMA_VERSION), ("built_at", datetime.now(timezone.utc).isoformat())),
    )
    _insert_dicts(connection, "campaigns", campaigns)
    _insert_dicts(connection, "variants", variants)
    _insert_dicts(connection, "attempts", attempts)
    _insert_dicts(connection, "runs", [{key: value for key, value in row.items() if key not in {"stages", "artifacts"}} for row in runs])
    stage_rows = [stage for run in runs for stage in run["stages"]]
    artifact_rows = [artifact for run in runs for artifact in run["artifacts"]]
    _insert_dicts(connection, "stages", stage_rows)
    _insert_dicts(connection, "artifacts", artifact_rows)
    _insert_dicts(connection, "artifact_objects", _artifact_objects(artifact_rows))
    _insert_dicts(connection, "research_artifacts", durable_artifacts)


def _insert_dicts(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = tuple(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        ([row.get(column) for column in columns] for row in rows),
    )


def _source_records(
    root: Path, campaign_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    campaigns: list[dict[str, Any]] = []
    variants_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    if not campaign_root.exists():
        return campaigns, [], attempts
    for campaign_dir in sorted(path for path in campaign_root.iterdir() if path.is_dir()):
        campaign_yaml = campaign_dir / "campaign.yaml"
        metadata = _read_yaml(campaign_yaml)
        campaign_id = str(metadata.get("campaign_id") or campaign_dir.name)
        campaigns.append(
            {
                "campaign_id": campaign_id,
                "title": metadata.get("title"),
                "edge_family": metadata.get("edge_family"),
                "definition_path": _display(root, campaign_yaml) if campaign_yaml.is_file() else _display(root, campaign_dir),
                "authored_status": _scalar_text(metadata.get("status")),
                "authored_decision": _scalar_text(metadata.get("decision")),
            }
        )
        indexed = _indexed_source_records(root, campaign_dir, campaign_id)
        if indexed is not None:
            indexed_variants, indexed_attempts = indexed
            for record in indexed_variants:
                variants_by_key.setdefault((campaign_id, record["variant_id"]), record)
            attempts.extend(indexed_attempts)
            continue
        for config_path in sorted(campaign_dir.rglob("config.yaml")):
            config = _read_yaml(config_path)
            variant_id = str(config.get("variant_id") or config_path.parent.name)
            record = {
                "campaign_id": campaign_id,
                "variant_id": variant_id,
                "definition_path": _display(root, config_path),
                "symbol": _scalar_text(config.get("symbol")),
                "timeframe": _scalar_text(config.get("timeframe")),
                "dataset_id": _scalar_text(config.get("dataset_id")),
                "config_hash": _file_hash(config_path),
            }
            relative = config_path.relative_to(campaign_dir)
            if relative.parts[0] == "variants":
                variants_by_key.setdefault((campaign_id, variant_id), record)
                continue
            attempt_id = _attempt_id(relative)
            attempts.append(
                {
                    "campaign_id": campaign_id,
                    "attempt_id": attempt_id,
                    "variant_id": variant_id,
                    "attempt_kind": "rescue" if relative.parts[0] == "rescue_attempts" else "alternate",
                    "parent_variant_id": variant_id if (campaign_id, variant_id) in variants_by_key else None,
                    "test_run_id": _scalar_text(config.get("test_run_id") or config.get("run_id")),
                    "definition_path": _display(root, config_path),
                    "config_hash": record["config_hash"],
                }
            )
    return campaigns, sorted(variants_by_key.values(), key=_definition_key), sorted(attempts, key=_attempt_key)


def _indexed_source_records(
    root: Path, campaign_dir: Path, campaign_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    variant_index = _read_yaml(root / "catalogs" / "definitions" / f"{campaign_id}.yaml")
    if variant_index.get("generated") is not True:
        return None
    variants = []
    for reference in variant_index.get("variants") or []:
        if not isinstance(reference, dict) or not reference.get("config_path"):
            continue
        variants.append(
            {
                "campaign_id": campaign_id,
                "variant_id": str(reference.get("variant_id")),
                "definition_path": str(reference.get("config_path")),
                "symbol": _scalar_text(reference.get("symbol")),
                "timeframe": _scalar_text(reference.get("timeframe")),
                "dataset_id": _scalar_text(reference.get("dataset_id")),
                "config_hash": str(reference.get("config_sha256") or ""),
            }
        )
    attempts = []
    for reference in variant_index.get("supplemental_definitions") or []:
        if not isinstance(reference, dict) or not reference.get("config_path"):
            continue
        attempts.append(
            {
                "campaign_id": campaign_id,
                "attempt_id": str(reference.get("definition_state") or "supplemental"),
                "variant_id": str(reference.get("variant_id")),
                "attempt_kind": "alternate",
                "parent_variant_id": None,
                "test_run_id": _scalar_text(reference.get("test_run_id")),
                "definition_path": str(reference.get("config_path")),
                "config_hash": str(reference.get("config_sha256") or ""),
            }
        )
    for manifest in variant_index.get("attempts") or []:
        if not isinstance(manifest, dict):
            continue
        for reference in manifest.get("variants") or []:
            if not isinstance(reference, dict) or not reference.get("config_path"):
                continue
            attempts.append(
                {
                    "campaign_id": campaign_id,
                    "attempt_id": str(manifest.get("attempt_id") or manifest.get("short_id") or "rescue"),
                    "variant_id": str(reference.get("variant_id")),
                    "attempt_kind": str(manifest.get("attempt_kind") or "rescue"),
                    "parent_variant_id": str(reference.get("variant_id")),
                    "test_run_id": _scalar_text(reference.get("test_run_id")),
                    "definition_path": str(reference.get("config_path")),
                    "config_hash": str(reference.get("config_sha256") or ""),
                }
            )
    return variants, attempts


def _run_records(root: Path, run_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in catalog_rows(run_root):
        summary_path = _resolve(root, row["summary_path"])
        summary = _read_json(summary_path)
        campaign_id = _scalar_text(row.get("campaign_id"))
        variant_id = _scalar_text(row.get("variant_id"))
        if not campaign_id or not variant_id:
            continue
        display_summary = _display(root, summary_path)
        output_dir = _resolve(root, row.get("output_dir") or summary_path.parent)
        run_uid = read_run_uid(output_dir) or hashlib.sha256(display_summary.encode("utf-8")).hexdigest()[:24]
        verdict = _run_verdict(row)
        stages = []
        for index, stage in enumerate(summary.get("stages") or []):
            if not isinstance(stage, dict):
                continue
            stages.append(
                {
                    "run_uid": run_uid,
                    "stage_index": index,
                    "stage_name": _scalar_text(stage.get("stage") or stage.get("name")),
                    "status": _scalar_text(stage.get("status")),
                    "passed": _bool_int(stage.get("passed")),
                }
            )
        artifacts = _critical_artifacts(root, output_dir, summary_path, run_uid)
        records.append(
            {
                "run_uid": run_uid,
                "campaign_id": campaign_id,
                "variant_id": variant_id,
                "test_run_id": _scalar_text(row.get("test_run_id")),
                "symbol": _scalar_text(row.get("symbol")),
                "dataset_id": _scalar_text(row.get("dataset_id")),
                "timeframe": _scalar_text(row.get("timeframe")),
                "data_source": _scalar_text(row.get("data_source")),
                "verdict": verdict,
                "halted": _bool_int(row.get("halted")),
                "failed_stage": _scalar_text(row.get("failed_stage")),
                "stage_count": int(row.get("stage_count") or len(stages)),
                "research_policy_version": _scalar_text(row.get("research_policy_version")),
                "research_policy_hash": _scalar_text(row.get("research_policy_hash")),
                "engine_contract_version": _scalar_text(row.get("engine_contract_version")),
                "config_hash": _scalar_text(row.get("config_hash")),
                "source_config_hash": _scalar_text(row.get("source_config_hash")),
                "input_data_hash": _scalar_text(row.get("input_data_hash")),
                "output_dir": _display(root, output_dir),
                "summary_path": display_summary,
                "source_config_path": _scalar_text(row.get("source_config_path")),
                "attempt_id": _attempt_from_source_path(row.get("source_config_path")),
                "parent_run_uid": None,
                "updated_at": _scalar_text(row.get("updated_at")),
                "stages": stages,
                "artifacts": artifacts,
            }
        )
    _assign_parent_run_uids(records)
    return sorted(records, key=lambda item: (item["campaign_id"], item["variant_id"], item["run_uid"]))


def _assign_parent_run_uids(records: list[dict[str, Any]]) -> None:
    originals: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        if record.get("attempt_id") == "original":
            originals.setdefault((record["campaign_id"], record["variant_id"]), []).append(record)
    for record in records:
        if record.get("attempt_id") in {None, "original"}:
            continue
        candidates = originals.get((record["campaign_id"], record["variant_id"]), [])
        if candidates:
            parent = max(candidates, key=lambda item: (item.get("updated_at") or "", item["run_uid"]))
            record["parent_run_uid"] = parent["run_uid"]


def _campaign_records(
    root: Path,
    source_campaigns: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    run_root: Path,
) -> list[dict[str, Any]]:
    variants_by_campaign = _group_by(variants, "campaign_id")
    runs_by_campaign = _group_by(runs, "campaign_id")
    result = []
    for source in source_campaigns:
        campaign_id = source["campaign_id"]
        campaign_runs = runs_by_campaign.get(campaign_id, [])
        root_summary = _read_json(run_root / campaign_id / "campaign_test_summary.json")
        decision = _scalar_text(root_summary.get("decision") or source.get("authored_decision"))
        status = _scalar_text(root_summary.get("status") or source.get("authored_status"))
        lifecycle, reason = _campaign_lifecycle(decision, status, campaign_runs)
        result.append(
            {
                **source,
                "authored_status": status,
                "authored_decision": decision,
                "lifecycle_state": lifecycle,
                "lifecycle_reason": reason,
                "variant_count": len(variants_by_campaign.get(campaign_id, [])),
                "attempt_count": 0,
                "run_count": len(campaign_runs),
                "latest_updated_at": max((run.get("updated_at") or "" for run in campaign_runs), default="") or None,
            }
        )
    attempt_counts: dict[str, int] = {}
    campaign_root = _resolve(root, "campaigns")
    for path in campaign_root.glob("*/rescue_attempts/*") if campaign_root.exists() else []:
        attempt_counts[path.parent.parent.name] = attempt_counts.get(path.parent.parent.name, 0) + 1
    for record in result:
        record["attempt_count"] = attempt_counts.get(record["campaign_id"], 0)
    return result


def _campaign_lifecycle(decision: str | None, status: str | None, runs: list[dict[str, Any]]) -> tuple[str, str]:
    decision_upper = (decision or "").upper()
    status_lower = (status or "").lower()
    verdicts = {run["verdict"] for run in runs}
    if decision_upper == "PASS" or "PASS" in verdicts:
        return "candidate", "at least one terminal pass; still requires manual due diligence and incubation"
    if decision_upper == "FAIL" or status_lower in {"failed", "completed_failed", "closed"}:
        return "closed", "authored or generated campaign decision is terminal FAIL"
    if "NEEDS MANUAL REVIEW" in verdicts or "error" in status_lower or "incomplete" in status_lower:
        return "review_queue", "run evidence is incomplete, ambiguous, or errored"
    return "active", "no terminal campaign decision is recorded"


def _durable_artifact_records(
    root: Path, artifact_root: Path, campaigns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not artifact_root.exists():
        return []
    campaign_ids = sorted((row["campaign_id"] for row in campaigns), key=len, reverse=True)
    records = []
    for path in sorted(item for item in artifact_root.iterdir() if item.is_file()):
        campaign_id = next((value for value in campaign_ids if path.name.startswith(f"{value}_")), None)
        stat = path.stat()
        records.append(
            {
                "path": _display(root, path),
                "filename": path.name,
                "category": _artifact_category(path.name, campaign_id),
                "campaign_id": campaign_id,
                "suffix": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return records


def _artifact_category(filename: str, campaign_id: str | None) -> str:
    value = filename.lower()
    if "cleanup" in value:
        return "cleanup"
    if "density" in value:
        return "audits_density"
    if "qualif" in value or value.startswith("engine_"):
        return "qualification"
    if "gate" in value or "continuation" in value or "shortlist" in value:
        return "search_gates"
    if "catalog" in value or "ledger" in value:
        return "catalogs"
    if "audit" in value:
        return "audits_methodology"
    if campaign_id:
        return "campaigns"
    return "other"


def _run_verdict(row: dict[str, Any]) -> str:
    if row.get("passed") is True:
        return "PASS"
    if row.get("passed") is False or row.get("halted") is True or row.get("failed_stage"):
        return "FAIL"
    return "NEEDS MANUAL REVIEW"


def _critical_artifacts(root: Path, output_dir: Path, summary_path: Path, run_uid: str) -> list[dict[str, Any]]:
    paths = {summary_path}
    for name in CRITICAL_ARTIFACTS:
        candidate = output_dir / name
        if candidate.is_file():
            paths.add(candidate)
    artifacts = []
    for path in sorted(paths):
        artifacts.append(
            {
                "run_uid": run_uid,
                "artifact_kind": path.name,
                "path": _display(root, path),
                "size_bytes": path.stat().st_size if path.is_file() else None,
                "sha256": _declared_hash(output_dir, path.name) or _file_hash(path),
            }
        )
    return artifacts


def _artifact_objects(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        sha256 = artifact.get("sha256")
        if sha256:
            grouped.setdefault(str(sha256), []).append(artifact)
    objects = []
    for sha256, references in sorted(grouped.items()):
        size = int(references[0].get("size_bytes") or 0)
        objects.append(
            {
                "sha256": sha256,
                "size_bytes": size,
                "reference_count": len(references),
                "canonical_source_path": min(str(item["path"]) for item in references),
                "reclaimable_bytes": max(0, len(references) - 1) * size,
            }
        )
    return objects


def _declared_hash(output_dir: Path, name: str) -> str | None:
    hash_file = {"effective_config.yaml": "config_hash.txt", "source_config.yaml": "source_config_hash.txt"}.get(name)
    if not hash_file:
        return None
    path = output_dir / hash_file
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def _write_campaign_view(
    root: Path,
    path: Path,
    rows: Iterable[sqlite3.Row],
    state: str,
    *,
    include_definition_links: bool,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    columns = (
        "campaign_id",
        "title",
        "edge_family",
        "lifecycle_state",
        "authored_decision",
        "run_count",
        "variant_count",
        "latest_updated_at",
        "definition_path",
    )
    _write_rows(path / "campaigns.csv", columns, rows)
    if include_definition_links:
        links = path / "definitions"
        links.mkdir()
        for row in rows:
            definition = _resolve(root, row["definition_path"])
            target = definition.parent if definition.name == "campaign.yaml" else definition
            if target.exists():
                (links / row["campaign_id"]).symlink_to(os.path.relpath(target, links))
    if state == "closed":
        _write_closed_symbol_views(path, rows)
    lines = [
        f"# {state.replace('_', ' ').title()} Campaigns",
        "",
        f"Campaigns: `{len(rows)}`",
        "",
        "Generated from the institutional research registry. Do not edit this view.",
        "",
    ]
    if rows:
        lines.extend(_campaign_markdown_table(rows[:20], use_view_links=include_definition_links))
        if len(rows) > 20:
            lines.extend(["", "The complete set is in `campaigns.csv`."])
    else:
        lines.append("No campaigns currently have this lifecycle state.")
    lines.append("")
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_failure_view(root: Path, path: Path, rows: Iterable[sqlite3.Row]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    columns = (
        "run_uid",
        "campaign_id",
        "variant_id",
        "test_run_id",
        "failed_stage",
        "updated_at",
        "summary_path",
        "output_dir",
    )
    _write_rows(path / "runs.csv", columns, rows)
    lines = [
        "# Recent Failures",
        "",
        f"Runs shown: `{len(rows)}`",
        "",
        "Most recently updated failed runs. This is a review view, not a deletion queue.",
        "",
        *_run_markdown_table(rows[:20]),
        "",
        "The complete set is in `runs.csv`.",
        "",
    ]
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_artifact_views(connection: sqlite3.Connection, path: Path) -> dict[str, int]:
    path.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    categories = connection.execute(
        "SELECT category, COUNT(*) AS count FROM research_artifacts GROUP BY category ORDER BY category"
    ).fetchall()
    columns = ("path", "filename", "campaign_id", "suffix", "size_bytes", "updated_at")
    for category in categories:
        rows = connection.execute(
            "SELECT path, filename, campaign_id, suffix, size_bytes, updated_at "
            "FROM research_artifacts WHERE category = ? ORDER BY filename",
            (category["category"],),
        ).fetchall()
        _write_rows(path / f"{category['category']}.csv", columns, rows)
        counts[category["category"]] = int(category["count"])
    lines = [
        "# Artifact Views",
        "",
        "Categorized indexes over durable flat-path artifacts. Paths remain stable for provenance.",
        "",
        "| Category | Artifacts | Index |",
        "| --- | ---: | --- |",
    ]
    lines.extend(
        f"| {category.replace('_', ' ')} | {count} | [{category}.csv]({category}.csv) |"
        for category, count in sorted(counts.items())
    )
    lines.append("")
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return counts


def _write_views_readme(
    path: Path,
    counts: dict[str, int],
    artifact_counts: dict[str, int],
    built_at: str | None,
) -> None:
    lines = [
        "# Research Views",
        "",
        "Generated navigation over the registry. Source definitions and immutable run evidence remain elsewhere.",
        "",
        f"Registry built: `{built_at or 'unknown'}`",
        "",
        "## Research Queue",
        "",
        "| View | Campaigns | Runs |",
        "| --- | ---: | ---: |",
        f"| [Active](active/) | {counts.get('active', 0)} | - |",
        f"| [Manual review](review_queue/) | {counts.get('review_queue', 0)} | {counts.get('review_runs', 0)} |",
        f"| [Candidates](candidate/) | {counts.get('candidate', 0)} | - |",
        f"| [Closed](closed/) | {counts.get('closed', 0)} | - |",
        f"| [Recent failures](recent_failures/) | - | {counts.get('recent_failures', 0)} |",
        "",
        "## Discovery",
        "",
        "- [Campaigns by symbol](by_symbol/)",
        "- [Campaigns by edge family](by_edge_family/campaigns.csv)",
        "- [Durable artifacts](artifacts/)",
        "- [Code navigation](code/)",
        "",
        "## Artifact Counts",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name.replace('_', ' ')} | {count} |" for name, count in sorted(artifact_counts.items()))
    lines.append("")
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_review_queue_readme(path: Path, campaign_count: int, rows: Iterable[sqlite3.Row]) -> None:
    rows = list(rows)
    lines = [
        "# Manual Review Queue",
        "",
        f"Campaigns with review lifecycle: `{campaign_count}`",
        f"Runs requiring review: `{len(rows)}`",
        "",
        "A run in this queue is incomplete or lacks a terminal staged verdict. It is not a candidate strategy.",
        "",
    ]
    if rows:
        lines.extend(_run_markdown_table(rows[:20]))
        lines.extend(["", "The complete queue is in `runs.csv`."])
    else:
        lines.append("No runs currently require manual review.")
    lines.append("")
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _write_discovery_views(connection: sqlite3.Connection, views_path: Path) -> None:
    rows = connection.execute(
        """
        SELECT campaign_id, title, edge_family, lifecycle_state, authored_decision,
               run_count, variant_count, latest_updated_at, definition_path
        FROM campaigns ORDER BY campaign_id
        """
    ).fetchall()
    symbol_path = views_path / "by_symbol"
    symbol_path.mkdir()
    grouped: dict[str, list[sqlite3.Row]] = {"ES": [], "NQ": [], "OTHER": []}
    for row in rows:
        campaign_id = str(row["campaign_id"])
        symbol = "ES" if campaign_id.startswith("es_") else "NQ" if campaign_id.startswith("nq_") else "OTHER"
        grouped[symbol].append(row)
    columns = (
        "campaign_id",
        "title",
        "edge_family",
        "lifecycle_state",
        "authored_decision",
        "run_count",
        "variant_count",
        "latest_updated_at",
        "definition_path",
    )
    for symbol, symbol_rows in grouped.items():
        _write_rows(symbol_path / f"{symbol}.csv", columns, symbol_rows)
    (symbol_path / "README.md").write_text(
        "# Campaigns By Symbol\n\n"
        + "\n".join(f"- [{symbol}.csv]({symbol}.csv): {len(symbol_rows)}" for symbol, symbol_rows in grouped.items())
        + "\n",
        encoding="utf-8",
    )
    edge_path = views_path / "by_edge_family"
    edge_path.mkdir()
    _write_rows(edge_path / "campaigns.csv", columns, sorted(rows, key=lambda row: (row["edge_family"] or "", row["campaign_id"])))
    (edge_path / "README.md").write_text(
        "# Campaigns By Edge Family\n\nSee [campaigns.csv](campaigns.csv).\n", encoding="utf-8"
    )


def _write_closed_symbol_views(path: Path, rows: list[sqlite3.Row]) -> None:
    by_symbol = path / "by_symbol"
    by_symbol.mkdir()
    columns = (
        "campaign_id",
        "title",
        "edge_family",
        "authored_decision",
        "run_count",
        "latest_updated_at",
        "definition_path",
    )
    for symbol in ("ES", "NQ", "OTHER"):
        symbol_rows = [
            row
            for row in rows
            if (
                (symbol == "ES" and str(row["campaign_id"]).startswith("es_"))
                or (symbol == "NQ" and str(row["campaign_id"]).startswith("nq_"))
                or (symbol == "OTHER" and not str(row["campaign_id"]).startswith(("es_", "nq_")))
            )
        ]
        _write_rows(by_symbol / f"{symbol}.csv", columns, symbol_rows)


def _campaign_markdown_table(rows: Iterable[sqlite3.Row], *, use_view_links: bool) -> list[str]:
    lines = ["| Campaign | Edge family | Runs | Updated |", "| --- | --- | ---: | --- |"]
    for row in rows:
        campaign_id = str(row["campaign_id"])
        href = f"definitions/{campaign_id}" if use_view_links else f"../../campaigns/{campaign_id}/campaign.yaml"
        lines.append(
            f"| [{campaign_id}]({href}) | {row['edge_family'] or ''} | {row['run_count']} | "
            f"{row['latest_updated_at'] or ''} |"
        )
    return lines


def _run_markdown_table(rows: Iterable[sqlite3.Row]) -> list[str]:
    lines = ["| Campaign | Variant | Run | Failed stage | Updated |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        summary_path = str(row["summary_path"])
        lines.append(
            f"| {row['campaign_id']} | {row['variant_id']} | [{row['test_run_id']}](../../{summary_path}) | "
            f"{row['failed_stage'] or ''} | {row['updated_at'] or ''} |"
        )
    return lines


def _write_rows(path: Path, columns: Iterable[str], rows: Iterable[sqlite3.Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({column: row[column] for column in columns} for row in rows)


def _reset_generated_directory(path: Path) -> None:
    if path.exists():
        marker = path / ".generated_by_alphaquest"
        if any(path.iterdir()) and not marker.is_file():
            raise RuntimeError(f"refusing to replace non-generated view directory: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _metadata_value(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


def _attempt_id(relative: Path) -> str:
    if relative.parts[0] == "rescue_attempts" and len(relative.parts) > 1:
        return relative.parts[1]
    return relative.parent.as_posix().replace("/", "__")


def _attempt_from_source_path(value: Any) -> str | None:
    if not value:
        return None
    parts = Path(str(value)).parts
    try:
        index = parts.index("rescue_attempts")
    except ValueError:
        return "original"
    return parts[index + 1] if len(parts) > index + 1 else "rescue"


def _definition_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["campaign_id"], row["variant_id"], row["definition_path"]


def _attempt_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return row["campaign_id"], row["attempt_id"], row["variant_id"], row["definition_path"]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scalar_text(value: Any) -> str | None:
    return str(value) if isinstance(value, (str, int, float)) else None


def _bool_int(value: Any) -> int | None:
    return int(value) if isinstance(value, bool) else None


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())
