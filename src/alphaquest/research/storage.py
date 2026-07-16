from __future__ import annotations

import csv
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
    draft_root: Path
    dataset_root: Path
    handoff_root: Path
    studio_runtime_root: Path
    migration_manifest: Path | None
    legacy_prefixes: tuple[tuple[str, str], ...]

    @property
    def campaign_roots(self) -> tuple[Path, ...]:
        return (self.active_campaign_root, *self.archive_campaign_roots)


@dataclass(frozen=True)
class CampaignContext:
    """Storage-aware identity and source paths for one authored campaign."""

    campaign_id: str
    campaign_root: Path
    source_root: Path
    lifecycle: str

    @property
    def campaign_yaml(self) -> Path:
        return self.campaign_root / "campaign.yaml"

    @property
    def results_index(self) -> Path:
        return self.campaign_root / "results_index.yaml"


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
        draft_root=one("draft_root", "research/drafts"),
        dataset_root=one("dataset_root", "research/datasets"),
        handoff_root=one("handoff_root", "research/handoffs"),
        studio_runtime_root=one("studio_runtime_root", "run-store/studio-runtime"),
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


def resolve_campaign_context(
    value: str | Path,
    *,
    project_root: str | Path = ".",
    layout: StorageLayout | None = None,
) -> CampaignContext | None:
    """Resolve an authored config or definition to its campaign source root.

    Configured roots are authoritative.  The legacy ``campaigns/<id>`` source
    root remains readable so historical definitions and external fixtures do
    not lose their campaign identity after the storage-layout migration.
    Generated evidence roots are intentionally excluded.
    """

    layout = layout or load_storage_layout(project_root)
    raw_path = Path(value)
    if raw_path.is_absolute():
        path = raw_path.resolve()
    else:
        path = (layout.project_root / raw_path).resolve()

    roots: list[tuple[Path, str]] = [(layout.active_campaign_root, "active")]
    roots.extend((root, "archive") for root in layout.archive_campaign_roots)
    roots.extend((root, "legacy") for root in _legacy_campaign_roots(layout))

    seen: set[Path] = set()
    for source_root, lifecycle in sorted(
        roots,
        key=lambda item: len(item[0].resolve().parts),
        reverse=True,
    ):
        resolved_root = source_root.resolve()
        if resolved_root in seen:
            continue
        seen.add(resolved_root)
        try:
            relative = path.relative_to(resolved_root)
        except ValueError:
            continue
        if not relative.parts:
            return None
        campaign_id = relative.parts[0]
        if campaign_id in {"variants", "rescue_attempts"}:
            return None
        return CampaignContext(
            campaign_id=campaign_id,
            campaign_root=resolved_root / campaign_id,
            source_root=resolved_root,
            lifecycle=lifecycle,
        )

    evidence_roots = tuple(root.resolve() for root in layout.evidence_roots)
    legacy_evidence_roots = tuple(
        _absolute(layout.project_root, old.rstrip("/")).resolve()
        for old, _new in layout.legacy_prefixes
        if Path(old.rstrip("/")).name == "backtest-campaigns"
    )
    if not any(_is_relative_to(path, root) for root in (*evidence_roots, *legacy_evidence_roots)):
        start = path if path.is_dir() else path.parent
        for parent in (start, *start.parents):
            if (parent / "campaign.yaml").is_file():
                return CampaignContext(
                    campaign_id=parent.name,
                    campaign_root=parent,
                    source_root=parent.parent,
                    lifecycle="ledger",
                )
    return None


def campaign_definition_paths(
    *,
    project_root: str | Path = ".",
    layout: StorageLayout | None = None,
    include_ledger: bool = True,
) -> tuple[Path, ...]:
    """Return deduplicated campaign definitions from every governed source.

    The configured active and archive roots are always scanned.  Ledger
    references are also followed when possible so migrated or legacy campaign
    definitions remain part of duplicate-edge checks.
    """

    layout = layout or load_storage_layout(project_root)
    definitions: set[Path] = set()
    for source_root in (*layout.campaign_roots, *_legacy_campaign_roots(layout)):
        if source_root.is_dir():
            definitions.update(
                path.resolve()
                for path in source_root.glob("*/campaign.yaml")
                if path.is_file()
            )

    if include_ledger:
        for campaign_id, recorded_path in _ledger_campaign_references(layout.project_root):
            if recorded_path:
                resolved = resolve_recorded_path(
                    recorded_path,
                    project_root=layout.project_root,
                    layout=layout,
                )
                context = resolve_campaign_context(
                    resolved,
                    project_root=layout.project_root,
                    layout=layout,
                )
                if context is not None and context.campaign_yaml.is_file():
                    definitions.add(context.campaign_yaml.resolve())
                    continue
            if campaign_id:
                for source_root in layout.campaign_roots:
                    candidate = source_root / campaign_id / "campaign.yaml"
                    if candidate.is_file():
                        definitions.add(candidate.resolve())
                        break
    return tuple(sorted(definitions))


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


def _legacy_campaign_roots(layout: StorageLayout) -> tuple[Path, ...]:
    roots: list[Path] = []
    for old, _new in layout.legacy_prefixes:
        relative = Path(old.rstrip("/"))
        if relative.name == "campaigns":
            roots.append(_absolute(layout.project_root, relative))
    return tuple(roots)


def _ledger_campaign_references(project_root: Path) -> tuple[tuple[str, str], ...]:
    references: list[tuple[str, str]] = []
    candidates = (
        project_root / "research_ledger.csv",
        project_root / "Start here" / "research_ledger.csv",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    references.append(
                        (
                            str(row.get("campaign_id") or "").strip(),
                            str(row.get("config_path") or "").strip(),
                        )
                    )
        except (OSError, csv.Error):
            continue
    return tuple(references)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _absolute(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
