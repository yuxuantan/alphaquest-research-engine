"""Read-only Studio workspace discovery plus rebuildable index refresh."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import yaml

from alphaquest.authoring.compiler import AUTHORING_MANIFEST_SCHEMA, STRATEGY_SPEC_SCHEMA
from alphaquest.research.registry import build_registry, export_registry_csvs, generate_views
from alphaquest.research.storage import campaign_definition_paths, display_path, load_storage_layout, resolve_campaign_context


def list_published_campaigns(project_root: str | Path = ".") -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    registry_states = _registry_campaign_states(root)
    rows: list[dict[str, Any]] = []
    for definition in campaign_definition_paths(project_root=root, include_ledger=False):
        try:
            value = yaml.safe_load(definition.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            value = {}
        if not isinstance(value, dict):
            value = {}
        context = resolve_campaign_context(definition, project_root=root)
        variants = value.get("variants") if isinstance(value.get("variants"), list) else []
        studio_status = _studio_publication_status(definition.parent, value, variants)
        campaign_id = str(value.get("campaign_id") or definition.parent.name)
        authored_lifecycle = context.lifecycle if context else "unknown"
        registry_state = registry_states.get(campaign_id)
        rows.append(
            {
                "campaign_id": campaign_id,
                "title": value.get("title") or definition.parent.name,
                "instrument": value.get("instrument") or value.get("symbol"),
                "timeframe": value.get("timeframe"),
                "lifecycle": registry_state or authored_lifecycle,
                "authored_lifecycle": authored_lifecycle,
                "variant_count": len(variants),
                **studio_status,
                "path": display_path(definition, root),
            }
        )
    return sorted(rows, key=lambda row: (row["lifecycle"] != "active", row["campaign_id"]))


def _registry_campaign_states(root: Path) -> dict[str, str]:
    database = load_storage_layout(root).catalog_root / "research_registry.sqlite"
    if not database.is_file():
        return {}
    try:
        with sqlite3.connect(database) as connection:
            return {
                str(campaign_id): str(lifecycle)
                for campaign_id, lifecycle in connection.execute(
                    "SELECT campaign_id, lifecycle_state FROM campaigns"
                )
            }
    except sqlite3.Error:
        return {}


def _studio_publication_status(
    campaign_root: Path,
    campaign: dict[str, Any],
    variants: list[Any],
) -> dict[str, Any]:
    """Classify novice-safe publications without mutating legacy source trees.

    A campaign is Studio-managed only when its frozen specification, manifest,
    one to five sequential configs, and all compiled document hashes still agree. Everything else
    remains executable through expert interfaces but is blocked in Studio.
    """

    blocked = {
        "studio_managed": False,
        "workflow_status": "BLOCKED · DEVELOPER-MANAGED",
        "workflow_blocker": (
            "Missing, incomplete, or hash-drifted Studio authoring contract; "
            "use the expert workflow or complete an engineering review."
        ),
    }
    manifest_path = campaign_root / "authoring_manifest.json"
    spec_path = campaign_root / "strategy_spec.yaml"
    if not manifest_path.is_file() or not spec_path.is_file():
        return blocked
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        if not isinstance(manifest, dict) or not isinstance(spec, dict):
            return blocked
        campaign_id = str(campaign.get("campaign_id") or campaign_root.name)
        variant_ids = [
            str(item if isinstance(item, str) else (item or {}).get("variant_id") or (item or {}).get("id") or "")
            for item in variants
        ]
        if (
            not 1 <= len(variant_ids) <= 5
            or any(not item for item in variant_ids)
            or len(set(variant_ids)) != len(variant_ids)
            or manifest.get("schema") != AUTHORING_MANIFEST_SCHEMA
            or manifest.get("campaign_id") != campaign_id
            or manifest.get("variant_count") != len(variant_ids)
            or spec.get("schema") != STRATEGY_SPEC_SCHEMA
            or spec.get("campaign_id") != campaign_id
            or spec.get("frozen") is not True
        ):
            return blocked
        expected_paths = {
            "campaign.yaml",
            "strategy_spec.yaml",
            *(f"variants/{variant_id}/config.yaml" for variant_id in variant_ids),
        }
        hashes = manifest.get("compiled_document_sha256")
        if not isinstance(hashes, dict) or set(hashes) != expected_paths:
            return blocked
        for relative in expected_paths:
            path = campaign_root / relative
            if not path.is_file():
                return blocked
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if hashes.get(relative) != _object_sha256(document):
                return blocked
    except (OSError, json.JSONDecodeError, yaml.YAMLError, TypeError, ValueError):
        return blocked
    return {
        "studio_managed": True,
        "workflow_status": "STUDIO-MANAGED · READY",
        "workflow_blocker": "",
    }


def _object_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def list_dataset_manifests(project_root: str | Path = ".") -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    dataset_root = Path(getattr(layout, "dataset_root", root / "research" / "datasets"))
    rows: list[dict[str, Any]] = []
    for path in sorted(dataset_root.glob("*/dataset_manifest.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            rows.append({**value, "manifest_path": display_path(path, root)})
    return rows


def list_review_queue(project_root: str | Path = ".") -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    database = load_storage_layout(root).catalog_root / "research_registry.sqlite"
    if not database.is_file():
        return []
    query = (
        "SELECT campaign_id, variant_id, run_uid, test_run_id, verdict, failed_stage, updated_at "
        "FROM runs WHERE archived = 0 AND verdict IN ('PASS', 'NEEDS MANUAL REVIEW', 'NEEDS_MANUAL_REVIEW') "
        "ORDER BY updated_at DESC LIMIT 200"
    )
    try:
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query)]
    except sqlite3.Error:
        return []


def refresh_generated_indexes_if_stale(
    project_root: str | Path = ".",
    *,
    force: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    database = layout.catalog_root / "research_registry.sqlite"
    definitions = campaign_definition_paths(project_root=root, layout=layout, include_ledger=True)
    index_inputs = list(definitions)
    for campaign_root in layout.campaign_roots:
        if campaign_root.is_dir():
            index_inputs.extend(campaign_root.glob("*/results_index.yaml"))
            index_inputs.extend(campaign_root.glob("*/**/config.yaml"))
            index_inputs.extend(campaign_root.glob("*/**/attempt_manifest.json"))
    definition_catalog = layout.catalog_root / "definitions"
    if definition_catalog.is_dir():
        index_inputs.extend(definition_catalog.glob("*.yaml"))
    for evidence_root in layout.evidence_roots:
        if not evidence_root.is_dir():
            continue
        for pattern in (
            "**/campaign_test_summary.json",
            "**/reporting_v2/result_bundle_v2.json",
            "**/reporting_v2/candidate_review.json",
        ):
            index_inputs.extend(evidence_root.glob(pattern))
    latest_source = max((path.stat().st_mtime for path in index_inputs if path.is_file()), default=0.0)
    database_mtime = database.stat().st_mtime if database.is_file() else 0.0
    if not force and database_mtime >= latest_source and database.is_file():
        return {
            "refreshed": False,
            "database": display_path(database, root),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    campaign_roots = [display_path(path, root) for path in layout.campaign_roots]
    evidence_roots = [display_path(path, root) for path in layout.evidence_roots]
    database_path = display_path(database, root)
    artifact_root = display_path(layout.research_artifact_root, root)
    export_root = display_path(layout.catalog_root / "exports", root)
    views_root = display_path(layout.views_root, root)
    counts = build_registry(
        project_root=root,
        database_path=database_path,
        campaign_roots=campaign_roots,
        run_roots=evidence_roots,
        research_artifact_root=artifact_root,
    )
    counts.update(
        {
            f"export_{key}": value
            for key, value in export_registry_csvs(
                project_root=root,
                database_path=database_path,
                output_root=export_root,
            ).items()
        }
    )
    counts.update(
        {
            f"view_{key}": value
            for key, value in generate_views(
                project_root=root,
                database_path=database_path,
                output_root=views_root,
            ).items()
        }
    )
    return {
        "refreshed": True,
        "database": display_path(database, root),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
    }


__all__ = [
    "list_dataset_manifests",
    "list_published_campaigns",
    "list_review_queue",
    "refresh_generated_indexes_if_stale",
]
