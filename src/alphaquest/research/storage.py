from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any, Iterable

import yaml


STORAGE_LAYOUT_SCHEMA = "alphaquest.storage-layout/v1"
DEFAULT_LAYOUT_PATH = Path("config/storage_layout.yaml")


@dataclass(frozen=True)
class StorageLayout:
    project_root: Path
    active_campaign_root: Path
    archive_campaign_roots: tuple[Path, ...]
    evidence_roots: tuple[Path, ...]
    research_artifact_root: Path
    catalog_root: Path
    views_root: Path
    run_store_root: Path
    migration_manifest: Path | None
    legacy_prefixes: tuple[tuple[str, str], ...]

    @property
    def campaign_roots(self) -> tuple[Path, ...]:
        return (self.active_campaign_root, *self.archive_campaign_roots)


def load_storage_layout(
    project_root: str | Path = ".", layout_path: str | Path | None = None
) -> StorageLayout:
    root = Path(project_root).resolve()
    requested = Path(layout_path or os.environ.get("ALPHAQUEST_STORAGE_LAYOUT", DEFAULT_LAYOUT_PATH))
    path = requested if requested.is_absolute() else root / requested
    document: dict[str, Any] = {}
    if path.is_file():
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(value, dict):
            raise ValueError(f"storage layout must be a mapping: {path}")
        if value.get("schema") != STORAGE_LAYOUT_SCHEMA:
            raise ValueError(f"unsupported storage layout schema in {path}: {value.get('schema')!r}")
        document = value

    def one(key: str, default: str) -> Path:
        return _absolute(root, document.get(key) or default)

    def many(key: str, defaults: Iterable[str]) -> tuple[Path, ...]:
        values = document.get(key)
        if values is None:
            values = list(defaults)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError(f"{key} must be a list of paths in {path}")
        return tuple(_absolute(root, item) for item in values)

    prefixes = document.get("legacy_prefixes") or {
        "campaigns/": "research/campaigns/archive/",
        "backtest-campaigns/": "research/evidence/runs/",
    }
    if not isinstance(prefixes, dict):
        raise ValueError(f"legacy_prefixes must be a mapping in {path}")
    migration = document.get("migration_manifest")
    return StorageLayout(
        project_root=root,
        active_campaign_root=one("active_campaign_root", "research/campaigns/active"),
        archive_campaign_roots=many("archive_campaign_roots", ("research/campaigns/archive",)),
        evidence_roots=many("evidence_roots", ("research/evidence/runs",)),
        research_artifact_root=one("research_artifact_root", "research_artifacts"),
        catalog_root=one("catalog_root", "catalogs"),
        views_root=one("views_root", "views"),
        run_store_root=one("run_store_root", "run-store"),
        migration_manifest=_absolute(root, migration) if migration else None,
        legacy_prefixes=tuple(sorted(((str(k), str(v)) for k, v in prefixes.items()), key=lambda x: len(x[0]), reverse=True)),
    )


def resolve_recorded_path(
    value: str | Path, *, project_root: str | Path = ".", layout: StorageLayout | None = None
) -> Path:
    layout = layout or load_storage_layout(project_root)
    path = Path(value)
    if path.is_absolute():
        if path.exists():
            return path
        try:
            relative = path.relative_to(layout.project_root)
        except ValueError:
            return path
    else:
        relative = path
    direct = layout.project_root / relative
    if direct.exists():
        return direct
    text = relative.as_posix()
    for old, new in _manifest_prefixes(layout):
        normalized_old = old.rstrip("/") + "/"
        if text == old.rstrip("/"):
            return layout.project_root / new.rstrip("/")
        if text.startswith(normalized_old):
            return layout.project_root / new.rstrip("/") / text[len(normalized_old) :]
    return direct


def display_path(path: str | Path, project_root: str | Path = ".") -> str:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _manifest_prefixes(layout: StorageLayout) -> tuple[tuple[str, str], ...]:
    if layout.migration_manifest and layout.migration_manifest.is_file():
        return _cached_manifest_prefixes(
            str(layout.migration_manifest), layout.migration_manifest.stat().st_mtime_ns
        ) or layout.legacy_prefixes
    return layout.legacy_prefixes


@lru_cache(maxsize=8)
def _cached_manifest_prefixes(path: str, mtime_ns: int) -> tuple[tuple[str, str], ...]:
    del mtime_ns
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        prefixes = manifest.get("legacy_prefixes") or {}
        if isinstance(prefixes, dict):
            return tuple(
                sorted(
                    ((str(key), str(value)) for key, value in prefixes.items()),
                    key=lambda item: len(item[0]),
                    reverse=True,
                )
            )
    except (OSError, json.JSONDecodeError):
        pass
    return ()


def _absolute(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
