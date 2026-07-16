from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


DEFINITION_INDEX_SCHEMA = "alphaquest.definition-index/v1"


def definition_manifests(
    campaign_root: str | Path = "campaigns",
    *,
    project_root: str | Path = ".",
    output_root: str | Path = "catalogs/definitions",
) -> dict[Path, dict[str, Any]]:
    root = Path(project_root).resolve()
    source_root = _resolve(root, campaign_root)
    index_root = _resolve(root, output_root)
    documents: dict[Path, dict[str, Any]] = {}
    if not source_root.exists():
        return documents
    for campaign_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        campaign = _read_yaml(campaign_dir / "campaign.yaml")
        campaign_id = str(campaign.get("campaign_id") or campaign_dir.name)
        original_configs = sorted((campaign_dir / "variants").glob("*/config.yaml"))
        variants = [_config_reference(root, path, index) for index, path in enumerate(original_configs, start=1)]
        rescue_root = campaign_dir / "rescue_attempts"
        follow_up_root = campaign_dir / "follow_up_attempts"
        rescue_configs = set(rescue_root.rglob("config.yaml")) if rescue_root.exists() else set()
        follow_up_configs = set(follow_up_root.rglob("config.yaml")) if follow_up_root.exists() else set()
        supplemental_configs = sorted(
            set(campaign_dir.rglob("config.yaml"))
            - set(original_configs)
            - rescue_configs
            - follow_up_configs
        )
        supplemental = []
        for index, path in enumerate(supplemental_configs, start=1):
            reference = _config_reference(root, path, index)
            reference["short_id"] = f"s{index:03d}"
            reference["definition_state"] = path.relative_to(campaign_dir).parts[0]
            supplemental.append(reference)
        attempts: dict[str, list[Path]] = defaultdict(list)
        attempt_roots: dict[str, Path] = {}
        if rescue_root.exists():
            for config_path in sorted(rescue_root.rglob("config.yaml")):
                relative = config_path.relative_to(rescue_root)
                attempt_id = relative.parts[0] if relative.parts else "rescue"
                attempts[attempt_id].append(config_path)
                attempt_roots[attempt_id] = rescue_root / attempt_id
        if follow_up_root.exists():
            for config_path in sorted(follow_up_root.glob("*/*/config.yaml")):
                relative = config_path.relative_to(follow_up_root)
                attempt_id = relative.parts[0]
                attempts[attempt_id].append(config_path)
                attempt_roots[attempt_id] = follow_up_root / attempt_id
        attempt_records = []
        for attempt_index, (attempt_id, config_paths) in enumerate(sorted(attempts.items()), start=1):
            references = [_config_reference(root, path, index) for index, path in enumerate(config_paths, start=1)]
            first = references[0] if references else {}
            source_root = attempt_roots[attempt_id]
            follow_up_manifest = _read_json(source_root / "attempt_manifest.json")
            attempt_records.append({
                "attempt_id": attempt_id,
                "short_id": f"a{attempt_index:03d}",
                "attempt_kind": first.get("attempt_kind") or follow_up_manifest.get("attempt_kind") or "rescue",
                "parent_attempt": first.get("parent_attempt_id") or follow_up_manifest.get("parent_attempt_id") or "original",
                "authorization_status": (
                    "governed_studio_follow_up"
                    if follow_up_manifest.get("schema") == "alphaquest.follow-up-attempt/v1"
                    else "imported_from_legacy_authored_tree"
                ),
                "source_config_root": _display(root, source_root),
                "variants": references,
            })
        documents[index_root / f"{campaign_id}.yaml"] = {
            "schema": DEFINITION_INDEX_SCHEMA,
            "generated": True,
            "campaign_id": campaign_id,
            "purpose": "Canonical flat index over executable authored definitions.",
            "variants": variants,
            "attempts": attempt_records,
            "supplemental_definitions": supplemental,
        }
    return documents


def write_definition_manifests(
    campaign_root: str | Path = "campaigns",
    *,
    project_root: str | Path = ".",
    output_root: str | Path = "catalogs/definitions",
    apply: bool = False,
) -> dict[str, int]:
    documents = definition_manifests(campaign_root, project_root=project_root, output_root=output_root)
    root = Path(project_root).resolve()
    created = 0
    updated = 0
    unchanged = 0
    for path, document in documents.items():
        content = yaml.safe_dump(document, sort_keys=False, default_flow_style=False, width=120)
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        if old == content:
            unchanged += 1
            continue
        if old is None:
            created += 1
        else:
            existing = _read_yaml(path)
            if existing.get("generated") is not True or existing.get("schema") != DEFINITION_INDEX_SCHEMA:
                raise RuntimeError(f"refusing to replace non-generated definition manifest: {path}")
            updated += 1
        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    removed = _remove_legacy_indexes(_resolve(root, campaign_root)) if apply else 0
    return {
        "documents": len(documents),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "removed_legacy_indexes": removed,
    }


def _remove_legacy_indexes(campaign_root: Path) -> int:
    removed = 0
    for path in [
        *campaign_root.glob("*/definition_index.yaml"),
        *campaign_root.glob("*/variant_index.yaml"),
        *campaign_root.glob("*/attempts/*.yaml"),
    ]:
        document = _read_yaml(path)
        if document.get("generated") is True and document.get("schema") == DEFINITION_INDEX_SCHEMA:
            path.unlink()
            removed += 1
    for directory in campaign_root.glob("*/attempts"):
        try:
            directory.rmdir()
        except OSError:
            pass
    return removed


def _config_reference(root: Path, path: Path, index: int) -> dict[str, Any]:
    config = _read_yaml(path)
    return {
        "short_id": f"v{index:03d}",
        "variant_id": str(config.get("variant_id") or path.parent.name),
        "test_run_id": config.get("test_run_id") or config.get("campaign_test_run_id") or config.get("run_id"),
        "symbol": config.get("symbol") or (config.get("data") or {}).get("symbol"),
        "timeframe": config.get("timeframe") or (config.get("data") or {}).get("source_timeframe"),
        "dataset_id": config.get("dataset_id") or (config.get("data") or {}).get("dataset_id"),
        "attempt_id": config.get("attempt_id"),
        "attempt_kind": config.get("attempt_kind"),
        "attempt_provenance": config.get("attempt_provenance"),
        "parent_attempt_id": config.get("parent_attempt_id"),
        "config_path": _display(root, path),
        "config_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


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


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())
