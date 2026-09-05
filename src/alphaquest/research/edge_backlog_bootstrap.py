"""Deterministic, derived-only historical Edge Backlog index."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Mapping

from pydantic import Field, model_validator
import yaml

from alphaquest.research.edge_backlog import (
    HISTORY_INDEX_SCHEMA,
    HistoricalEdgeIndexRecordV1,
    Sha256,
    StrictBacklogModel,
    backlog_file_lock,
    canonical_json_bytes,
    load_historical_edge_index_records,
    record_sha256,
)
from alphaquest.research.storage import StorageLayout, campaign_definition_paths, display_path, load_storage_layout


_COMMITTED_LAYOUT_FIELDS = frozenset(
    {
        "schema",
        "active_campaign_root",
        "archive_campaign_roots",
        "evidence_roots",
        "research_artifact_root",
        "catalog_root",
        "views_root",
        "run_store_root",
        "draft_root",
        "dataset_root",
        "handoff_root",
        "studio_runtime_root",
        "edge_backlog_root",
        "edge_backlog_history_index",
        "migration_manifest",
        "legacy_prefixes",
    }
)
_COMMITTED_LAYOUT_PATH_FIELDS = (
    "active_campaign_root",
    "research_artifact_root",
    "catalog_root",
    "views_root",
    "run_store_root",
    "draft_root",
    "dataset_root",
    "handoff_root",
    "studio_runtime_root",
    "edge_backlog_root",
    "edge_backlog_history_index",
    "migration_manifest",
)


@dataclass(frozen=True)
class HistoricalSourceFileState:
    path: str
    source_kind: str
    mode: str
    data: bytes


@dataclass(frozen=True)
class HistoricalRepositoryState:
    commit: str
    layout: StorageLayout
    layout_file: HistoricalSourceFileState
    sources: tuple[HistoricalSourceFileState, ...]
    source_object_ids: tuple[tuple[str, str], ...]
    records: tuple[HistoricalEdgeIndexRecordV1, ...]


@dataclass(frozen=True)
class RepositoryFileAnchor:
    """The unique immutable Git introduction of one canonical file."""

    introduction_commit: str
    preceding_commit: str


class HistoricalEdgeIndexPriorV1(StrictBacklogModel):
    """Exact validator for the only released pre-remediation derived row format."""

    schema_name: Literal[HISTORY_INDEX_SCHEMA] = Field(
        default=HISTORY_INDEX_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    record_id: str = Field(pattern=r"^history\.[a-f0-9]{24}$")
    source_kind: Literal[
        "CAMPAIGN_DEFINITION",
        "RESEARCH_LEDGER_ROW",
        "EXPERIMENT_REGISTRY_EVENT",
        "RESEARCH_RESET_MANIFEST",
    ]
    source_path: str = Field(min_length=1)
    source_sha256: Sha256
    source_row_number: int | None = Field(default=None, ge=1)
    archive_generation: str = Field(min_length=1)
    evidence_eligibility: Literal["CURRENT_SCOPE", "HISTORICAL_INELIGIBLE"]
    campaign_id: str | None = None
    variant_id: str | None = None
    attempt_id: str | None = None
    instrument: str | None = None
    timeframe: str | None = None
    raw_title: str | None = None
    raw_edge: str | None = None
    raw_hypothesis: str | None = None
    raw_edge_family: str | None = None
    raw_counterparty_transfer_rationale: str | None = None
    raw_information_availability: str | None = None
    raw_expected_effect: str | None = None
    raw_config_path: str | None = None
    raw_report_path: str | None = None
    legacy_fingerprint: dict[str, Any] | str | None = None
    raw_outcome: str | None = None
    raw_scientific_verdict: str | None = None
    raw_disposition: str | None = None
    raw_failure_reason: str | None = None
    extraction_completeness: Literal["COMPLETE", "PARTIAL", "INSUFFICIENT"]
    semantic_resolution: Literal["LEGACY_CANDIDATE", "NEEDS_MANUAL_REVIEW"]
    record_sha256: Sha256

    @model_validator(mode="after")
    def validate_provenance_and_hash(self) -> "HistoricalEdgeIndexPriorV1":
        path = Path(self.source_path)
        if path.is_absolute() or ".." in path.parts or not self.source_path.strip():
            raise ValueError("prior historical source_path must be project-relative")
        row_kinds = {"RESEARCH_LEDGER_ROW", "EXPERIMENT_REGISTRY_EVENT"}
        if (self.source_kind in row_kinds) != (self.source_row_number is not None):
            raise ValueError("prior historical source_row_number does not match source_kind")
        expected_eligibility = (
            "CURRENT_SCOPE" if self.archive_generation == "CURRENT" else "HISTORICAL_INELIGIBLE"
        )
        if self.evidence_eligibility != expected_eligibility:
            raise ValueError("prior evidence_eligibility does not match archive provenance")
        expected_resolution = (
            "LEGACY_CANDIDATE" if self.extraction_completeness == "COMPLETE" else "NEEDS_MANUAL_REVIEW"
        )
        if self.semantic_resolution != expected_resolution:
            raise ValueError("prior semantic_resolution does not match extraction completeness")
        identity = {
            "source_kind": self.source_kind,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_row_number": self.source_row_number,
        }
        expected_id = "history." + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()[:24]
        if self.record_id != expected_id:
            raise ValueError("prior historical record_id does not match source provenance")
        if self.record_sha256 != record_sha256(self.model_dump(mode="json", by_alias=True)):
            raise ValueError("prior historical index record_sha256 mismatch")
        return self


def historical_source_inventory(
    project_root: str | Path,
    *,
    layout: StorageLayout | None = None,
) -> dict[Path, str]:
    """Return the complete approved source-file set used by bootstrap and verification."""

    root = Path(project_root).resolve()
    layout = layout or load_storage_layout(root)
    inventory: dict[Path, str] = {}
    definitions = set(campaign_definition_paths(project_root=root, layout=layout, include_ledger=True))
    archived_root = root / "research" / "archived_generations"
    if archived_root.is_dir():
        definitions.update(path.resolve() for path in archived_root.glob("*/campaigns/*/*/campaign.yaml"))
    for path in definitions:
        _add_source(inventory, path, "CAMPAIGN_DEFINITION")
    ledger_paths = {
        root / "research_ledger.csv",
        root / "Start here" / "research_ledger.csv",
    }
    if archived_root.is_dir():
        ledger_paths.update(archived_root.glob("*/research_ledger.csv"))
    for path in sorted(ledger_paths):
        if path.is_file():
            _add_source(inventory, path, "RESEARCH_LEDGER_ROW")
    experiment_path = layout.research_artifact_root / "governance" / "experiment_registry.jsonl"
    if experiment_path.is_file():
        _add_source(inventory, experiment_path, "EXPERIMENT_REGISTRY_EVENT")
    for path in sorted((layout.research_artifact_root / "governance").glob("research_reset*.json")):
        if path.is_file():
            _add_source(inventory, path, "RESEARCH_RESET_MANIFEST")
    return inventory


def extract_historical_source_records(
    project_root: str | Path,
    path: str | Path,
    source_kind: str,
    *,
    layout: StorageLayout | None = None,
    source_bytes: bytes | None = None,
) -> list[HistoricalEdgeIndexRecordV1]:
    """Run the sole source-specific historical projection parser."""

    root = Path(project_root).resolve()
    source = _historical_source_path(root, path, commit_bound=source_bytes is not None)
    layout = layout or load_storage_layout(root)
    if source_kind == "CAMPAIGN_DEFINITION":
        records = [_campaign_record(root, source, layout, source_bytes)]
    elif source_kind == "RESEARCH_LEDGER_ROW":
        records = _ledger_records(root, source, layout, source_bytes)
    elif source_kind == "EXPERIMENT_REGISTRY_EVENT":
        records = _experiment_records(root, source, layout, source_bytes)
    elif source_kind == "RESEARCH_RESET_MANIFEST":
        records = [_reset_record(root, source, layout, source_bytes)]
    else:
        raise ValueError(f"unsupported historical source_kind: {source_kind!r}")
    if not records:
        raise ValueError(
            "approved historical source produced an invalid zero-row projection: "
            f"{_historical_source_relative(root, source)}"
        )
    return records


def validate_historical_record_provenance(
    record: HistoricalEdgeIndexRecordV1,
    *,
    project_root: str | Path,
    layout: StorageLayout | None = None,
) -> None:
    """Verify one embedded row against its exact approved source projection."""

    validate_historical_records_provenance(
        [record],
        project_root=project_root,
        layout=layout,
    )


def validate_historical_records_provenance(
    records: list[HistoricalEdgeIndexRecordV1],
    *,
    project_root: str | Path,
    layout: StorageLayout | None = None,
) -> None:
    """Verify supplied strict rows against their exact approved source projections."""

    root = Path(project_root).resolve()
    layout = layout or load_storage_layout(root)
    inventory = historical_source_inventory(root, layout=layout)
    grouped: dict[str, list[HistoricalEdgeIndexRecordV1]] = {}
    for record in records:
        grouped.setdefault(record.source_path, []).append(record)
    for source_path, claimed in grouped.items():
        source = (root / source_path).resolve()
        if not _is_relative_to(source, root):
            raise ValueError(f"historical source escapes project root: {source_path}")
        expected_kind = inventory.get(source)
        if expected_kind is None:
            raise ValueError(f"historical source is absent or outside approved roots: {source_path}")
        if any(item.source_kind != expected_kind for item in claimed):
            raise ValueError(f"historical source_kind does not match approved source: {source_path}")
        expected = extract_historical_source_records(
            root,
            source,
            expected_kind,
            layout=layout,
        )
        expected_by_id = {item.record_id: item for item in expected}
        for item in claimed:
            resolved = expected_by_id.get(item.record_id)
            if resolved is None or resolved.model_dump(mode="json", by_alias=True) != item.model_dump(
                mode="json", by_alias=True
            ):
                raise ValueError(
                    f"historical row does not equal the source-specific projection: {source_path}"
                )


def validate_historical_index_records(
    records: list[HistoricalEdgeIndexRecordV1],
    *,
    project_root: str | Path,
    layout: StorageLayout | None = None,
) -> None:
    """Require exact equality with the complete current approved-source projection."""

    root = Path(project_root).resolve()
    layout = layout or load_storage_layout(root)
    expected = _historical_records_for_working_tree(root, layout)
    actual_payloads = [item.model_dump(mode="json", by_alias=True) for item in records]
    expected_payloads = [item.model_dump(mode="json", by_alias=True) for item in expected]
    if actual_payloads != expected_payloads:
        raise ValueError(
            "historical edge index does not equal the complete approved-source projection"
        )


def historical_records_for_repository_commit(
    project_root: str | Path,
    commit: str | None = None,
) -> tuple[str, list[HistoricalEdgeIndexRecordV1]]:
    """Rebuild the complete matcher universe from one immutable Git source tree."""

    state = historical_repository_state(project_root, commit)
    return state.commit, list(state.records)


def historical_repository_state(
    project_root: str | Path,
    commit: str | None = None,
) -> HistoricalRepositoryState:
    """Reconstruct one universe exclusively from lexical Git paths and blobs."""

    root = Path(project_root).resolve()
    repository_root = Path(_git(root, "rev-parse", "--show-toplevel", text=True).strip())
    if repository_root != root:
        raise ValueError("historical source Git root does not equal the configured project root")
    requested = commit or "HEAD"
    resolved = _git(root, "rev-parse", f"{requested}^{{commit}}", text=True).strip()
    if commit is not None and resolved != commit:
        raise ValueError("historical source commit must be a full immutable Git object ID")
    entries = _repository_tree_entries(root, resolved)
    layout_file = _required_repository_file(
        root,
        entries,
        "config/storage_layout.yaml",
        label="committed storage layout",
    )
    layout = _strict_committed_storage_layout(root, layout_file.data)
    _validate_git_discovery_nodes(entries, root, layout, label="committed")
    sources: list[HistoricalSourceFileState] = []
    source_object_ids: list[tuple[str, str]] = []
    records: list[HistoricalEdgeIndexRecordV1] = []
    for relative, (mode, object_type, object_id) in sorted(entries.items()):
        source_kind = _historical_source_kind_for_relative(relative, root, layout)
        if source_kind is None:
            continue
        if mode != "100644" or object_type != "blob":
            raise ValueError(
                f"approved committed historical source must be one 100644 blob: {relative}"
            )
        data = _git(root, "cat-file", "blob", object_id)
        source = HistoricalSourceFileState(relative, source_kind, mode, data)
        sources.append(source)
        source_object_ids.append((relative, object_id))
        records.extend(
            extract_historical_source_records(
                root,
                relative,
                source_kind,
                layout=layout,
                source_bytes=data,
            )
        )
    records.sort(key=_historical_record_sort_key)
    return HistoricalRepositoryState(
        commit=resolved,
        layout=layout,
        layout_file=layout_file,
        sources=tuple(sources),
        source_object_ids=tuple(source_object_ids),
        records=tuple(records),
    )


def historical_records_for_current_review(
    project_root: str | Path,
) -> tuple[str, list[HistoricalEdgeIndexRecordV1]]:
    """Require HEAD, index, and worktree to encode one exact historical source state."""

    root = Path(project_root).resolve()
    committed = historical_repository_state(root)
    index_entries = _repository_index_entries(root)
    index_layout = _required_index_file(
        root,
        index_entries,
        "config/storage_layout.yaml",
        label="indexed storage layout",
    )
    working_layout_file = _required_working_file(
        root,
        "config/storage_layout.yaml",
        "STORAGE_LAYOUT",
        label="working-tree storage layout",
    )
    if index_layout != committed.layout_file or working_layout_file != committed.layout_file:
        raise ValueError("storage layout differs across HEAD, Git index, and working tree")
    layout = _strict_committed_storage_layout(root, working_layout_file.data)
    _validate_index_discovery_nodes(index_entries, root, layout)
    _validate_working_discovery_nodes(root, layout)
    candidate_paths = set(_working_tree_historical_source_paths(root, layout))
    candidate_paths.update(source.path for source in committed.sources)
    candidate_paths.update(
        relative
        for relative in index_entries
        if _historical_source_kind_for_relative(relative, root, layout) is not None
    )
    indexed = _historical_sources_from_index(index_entries, root, layout, candidate_paths)
    working = _historical_sources_from_working_tree(root, layout, candidate_paths)
    committed_object_ids = dict(committed.source_object_ids)
    expected_indexed = tuple(
        (source.path, source.source_kind, source.mode, committed_object_ids[source.path])
        for source in committed.sources
    )
    if indexed != expected_indexed or working != committed.sources:
        raise ValueError("approved historical sources differ across HEAD, Git index, and working tree")
    return committed.commit, list(committed.records)


def repository_head(project_root: str | Path) -> str | None:
    """Return exact HEAD for a repository rooted at project_root, or None outside Git."""

    root = Path(project_root).resolve()
    try:
        top_level = _git_optional(root, "rev-parse", "--show-toplevel", text=True)
    except OSError as exc:
        raise ValueError(f"could not inspect repository HEAD: {exc}") from exc
    if top_level is None:
        return None
    repository_root = Path(str(top_level).strip())
    if repository_root != root:
        raise ValueError("Git root does not equal the configured project root")
    return str(_git(root, "rev-parse", "HEAD^{commit}", text=True)).strip()


def repository_commit_is_ancestor(
    project_root: str | Path,
    ancestor: str,
    descendant: str,
) -> bool:
    """Use the commit graph, never commit timestamps, to establish ordering."""

    root = Path(project_root).resolve()
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise ValueError(f"could not compare repository commits: {result.stderr.strip()}")


def repository_file_anchor(
    project_root: str | Path,
    relative_path: str,
    expected_bytes: bytes,
) -> RepositoryFileAnchor | None:
    """Resolve a unique, unchanged first Git anchor for exact canonical bytes.

    None means the canonical file has never been committed and is provisional.
    Once introduced, every reachable descendant must retain the exact same blob.
    """

    root = Path(project_root).resolve()
    head = repository_head(root)
    if head is None:
        return None
    _validate_repository_relative_path(relative_path)
    expected_object_id = _git_with_input(root, expected_bytes, "hash-object", "--stdin").decode(
        "ascii"
    ).strip()
    commits = str(_git(root, "rev-list", "--topo-order", "HEAD", text=True)).splitlines()
    entries: dict[str, tuple[str, str, str] | None] = {
        commit: _repository_path_entry(root, commit, relative_path) for commit in commits
    }
    matching = {
        commit
        for commit, entry in entries.items()
        if entry == ("100644", "blob", expected_object_id)
    }
    if not matching:
        if any(entry is not None for entry in entries.values()):
            raise ValueError("committed canonical decision was rewritten or removed")
        return None
    if entries[head] != ("100644", "blob", expected_object_id):
        raise ValueError("committed canonical decision blob no longer matches its first Git anchor")

    parents = {
        commit: tuple(
            str(_git(root, "show", "-s", "--format=%P", commit, text=True)).strip().split()
        )
        for commit in commits
    }
    introductions = [
        commit
        for commit in matching
        if not any(parent in matching for parent in parents[commit])
    ]
    if len(introductions) != 1:
        raise ValueError("canonical decision has an ambiguous Git introduction history")
    introduction = introductions[0]
    introduction_parents = parents[introduction]
    if len(introduction_parents) != 1:
        raise ValueError("canonical decision introduction must have exactly one Git parent")
    if any(entries[parent] is not None for parent in introduction_parents):
        raise ValueError("canonical decision path existed before its exact Git anchor")

    for commit, entry in entries.items():
        if repository_commit_is_ancestor(root, introduction, commit) and entry != (
            "100644",
            "blob",
            expected_object_id,
        ):
            raise ValueError("committed canonical decision was changed or removed after introduction")
    return RepositoryFileAnchor(
        introduction_commit=introduction,
        preceding_commit=introduction_parents[0],
    )


def repository_path_inventory(
    project_root: str | Path,
    prefix: str,
) -> tuple[set[str], set[str]]:
    """Return current and ever-reachable lexical paths below one repository prefix."""

    root = Path(project_root).resolve()
    head = repository_head(root)
    if head is None:
        return set(), set()
    normalized = prefix.rstrip("/")
    _validate_repository_relative_path(normalized)
    path_prefix = normalized + "/"
    current = {
        path
        for path in _repository_tree_entries(root, head)
        if path.startswith(path_prefix)
    }
    history = _git(
        root,
        "log",
        "--format=",
        "--name-only",
        "-z",
        "HEAD",
        "--",
        normalized,
    )
    ever: set[str] = set()
    for raw_path in history.split(b"\0"):
        if not raw_path:
            continue
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("repository history contains a non-UTF-8 path") from exc
        _validate_repository_relative_path(path)
        if path.startswith(path_prefix):
            ever.add(path)
    return current, ever


def historical_source_layout_for_repository_commit(
    project_root: str | Path,
    commit: str,
) -> StorageLayout:
    """Load the strict storage layout from one already-resolved repository commit."""

    return historical_repository_state(project_root, commit).layout


def historical_source_state_for_working_tree(
    project_root: str | Path,
) -> tuple[StorageLayout, list[HistoricalEdgeIndexRecordV1]]:
    """Return the strict current layout and its complete approved-source projection."""

    root = Path(project_root).resolve()
    state = _required_working_file(
        root,
        "config/storage_layout.yaml",
        "STORAGE_LAYOUT",
        label="working-tree storage layout",
    )
    try:
        layout = _strict_committed_storage_layout(root, state.data)
    except ValueError as exc:
        raise ValueError(f"working-tree storage layout is invalid: {exc}") from exc
    return layout, _historical_records_for_working_tree(root, layout)


def historical_source_layout_semantics(layout: StorageLayout) -> dict[str, Any]:
    """Return only layout values capable of changing historical source discovery."""

    root = layout.project_root

    def relative(path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("historical source layout path escapes the project root") from exc

    return {
        "active_campaign_root": relative(layout.active_campaign_root),
        "archive_campaign_roots": [relative(path) for path in layout.archive_campaign_roots],
        "evidence_roots": [relative(path) for path in layout.evidence_roots],
        "research_artifact_root": relative(layout.research_artifact_root),
        "migration_manifest": relative(layout.migration_manifest),
        "legacy_prefixes": [list(item) for item in layout.legacy_prefixes],
    }


def _repository_tree_entries(
    root: Path,
    commit: str,
) -> dict[str, tuple[str, str, str]]:
    entries: dict[str, tuple[str, str, str]] = {}
    tree = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
    for raw in tree.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        try:
            relative = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("repository tree contains a non-UTF-8 path") from exc
        _validate_repository_relative_path(relative)
        if relative in entries:
            raise ValueError(f"repository tree repeats path: {relative}")
        entries[relative] = (mode, object_type, object_id)
    return entries


def _repository_path_entry(
    root: Path,
    commit: str,
    relative: str,
) -> tuple[str, str, str] | None:
    data = _git(root, "ls-tree", "-z", commit, "--", relative)
    rows = [row for row in data.split(b"\0") if row]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError(f"repository commit repeats canonical path: {relative}")
    metadata, raw_path = rows[0].split(b"\t", 1)
    try:
        actual_path = raw_path.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("repository commit contains a non-UTF-8 path") from exc
    if actual_path != relative:
        raise ValueError(f"repository tree returned a non-exact canonical path: {actual_path}")
    mode, object_type, object_id = metadata.decode("ascii").split()
    return mode, object_type, object_id


def _repository_index_entries(root: Path) -> dict[str, tuple[tuple[str, str, int], ...]]:
    grouped: dict[str, list[tuple[str, str, int]]] = {}
    data = _git(root, "ls-files", "--stage", "-z")
    for raw in data.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, object_id, raw_stage = metadata.decode("ascii").split()
        try:
            relative = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Git index contains a non-UTF-8 path") from exc
        _validate_repository_relative_path(relative)
        grouped.setdefault(relative, []).append((mode, object_id, int(raw_stage)))
    return {
        relative: tuple(sorted(entries, key=lambda item: item[2]))
        for relative, entries in grouped.items()
    }


def _historical_discovery_prefixes(root: Path, layout: StorageLayout) -> tuple[str, ...]:
    paths = [
        layout.active_campaign_root,
        *layout.archive_campaign_roots,
        *(root / PurePosixPath(old.rstrip("/")) for old, _new in layout.legacy_prefixes),
        root / "research/archived_generations",
        root / "Start here",
        layout.research_artifact_root / "governance",
    ]
    values: set[str] = set()
    for path in paths:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("historical discovery root escapes the project root") from exc
        _validate_repository_relative_path(relative)
        values.add(relative)
    return tuple(sorted(values))


def _validate_git_discovery_nodes(
    entries: Mapping[str, tuple[str, str, str]],
    root: Path,
    layout: StorageLayout,
    *,
    label: str,
) -> None:
    prefixes = _historical_discovery_prefixes(root, layout)
    for relative, (mode, object_type, _object_id) in entries.items():
        is_root_or_ancestor = any(
            relative == prefix or prefix.startswith(relative + "/") for prefix in prefixes
        )
        is_within_root = any(relative.startswith(prefix + "/") for prefix in prefixes)
        if is_root_or_ancestor:
            raise ValueError(
                f"{label} historical discovery root must be a Git tree, not an entry: {relative}"
            )
        if is_within_root and (mode in {"120000", "160000"} or object_type != "blob"):
            raise ValueError(
                f"{label} historical discovery storage contains a symlink or gitlink: {relative}"
            )


def _validate_index_discovery_nodes(
    entries: Mapping[str, tuple[tuple[str, str, int], ...]],
    root: Path,
    layout: StorageLayout,
) -> None:
    flattened: dict[str, tuple[str, str, str]] = {}
    for relative, staged in entries.items():
        if len(staged) != 1 or staged[0][2] != 0:
            prefixes = _historical_discovery_prefixes(root, layout)
            if any(
                relative == prefix
                or relative.startswith(prefix + "/")
                or prefix.startswith(relative + "/")
                for prefix in prefixes
            ):
                raise ValueError(
                    f"indexed historical discovery storage has unresolved stages: {relative}"
                )
            continue
        mode, object_id, _stage = staged[0]
        object_type = "commit" if mode == "160000" else "blob"
        flattened[relative] = (mode, object_type, object_id)
    _validate_git_discovery_nodes(flattened, root, layout, label="indexed")


def _validate_working_discovery_nodes(root: Path, layout: StorageLayout) -> None:
    for relative in _historical_discovery_prefixes(root, layout):
        path = root / PurePosixPath(relative)
        current = root
        for part in PurePosixPath(relative).parts:
            current /= part
            if not os.path.lexists(current):
                break
            metadata = current.lstat()
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(
                    f"working historical discovery root is not a plain directory: {relative}"
                )
        if not path.is_dir():
            continue
        for directory, directory_names, file_names in os.walk(path, followlinks=False):
            directory_path = Path(directory)
            for name in [*directory_names, *file_names]:
                candidate = directory_path / name
                if candidate.is_symlink():
                    source = candidate.relative_to(root).as_posix()
                    raise ValueError(
                        f"working historical discovery storage contains a symlink: {source}"
                    )


def _required_repository_file(
    root: Path,
    entries: Mapping[str, tuple[str, str, str]],
    relative: str,
    *,
    label: str,
) -> HistoricalSourceFileState:
    entry = entries.get(relative)
    if entry is None:
        raise ValueError(f"{label} is missing: {relative}")
    mode, object_type, object_id = entry
    if mode != "100644" or object_type != "blob":
        raise ValueError(f"{label} must be one 100644 blob: {relative}")
    return HistoricalSourceFileState(
        path=relative,
        source_kind="STORAGE_LAYOUT",
        mode=mode,
        data=_git(root, "cat-file", "blob", object_id),
    )


def _required_index_file(
    root: Path,
    entries: Mapping[str, tuple[tuple[str, str, int], ...]],
    relative: str,
    *,
    label: str,
) -> HistoricalSourceFileState:
    staged = entries.get(relative, ())
    if len(staged) != 1 or staged[0][2] != 0:
        raise ValueError(f"{label} is missing or has unresolved index stages: {relative}")
    mode, object_id, _stage = staged[0]
    object_type = _git(root, "cat-file", "-t", object_id, text=True).strip()
    if mode != "100644" or object_type != "blob":
        raise ValueError(f"{label} must be one stage-zero 100644 blob: {relative}")
    return HistoricalSourceFileState(
        path=relative,
        source_kind="STORAGE_LAYOUT",
        mode=mode,
        data=_git(root, "cat-file", "blob", object_id),
    )


def _required_working_file(
    root: Path,
    relative: str,
    source_kind: str,
    *,
    label: str,
) -> HistoricalSourceFileState:
    _validate_repository_relative_path(relative)
    path = root / PurePosixPath(relative)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} cannot be read: {relative}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o111:
        raise ValueError(f"{label} must be one non-executable regular file: {relative}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} cannot be read: {relative}: {exc}") from exc
    return HistoricalSourceFileState(relative, source_kind, "100644", data)


def _historical_sources_from_index(
    entries: Mapping[str, tuple[tuple[str, str, int], ...]],
    root: Path,
    layout: StorageLayout,
    candidate_paths: set[str],
) -> tuple[tuple[str, str, str, str], ...]:
    sources: list[tuple[str, str, str, str]] = []
    for relative in sorted(candidate_paths):
        source_kind = _historical_source_kind_for_relative(relative, root, layout)
        if source_kind is None:
            continue
        staged = entries.get(relative, ())
        if not staged:
            continue
        if len(staged) != 1 or staged[0][2] != 0:
            raise ValueError(f"approved historical source has unresolved index stages: {relative}")
        mode, object_id, _stage = staged[0]
        if mode != "100644":
            raise ValueError(
                f"approved indexed historical source must be one 100644 blob: {relative}"
            )
        sources.append((relative, source_kind, mode, object_id))
    return tuple(sources)


def _historical_sources_from_working_tree(
    root: Path,
    layout: StorageLayout,
    candidate_paths: set[str],
) -> tuple[HistoricalSourceFileState, ...]:
    sources: list[HistoricalSourceFileState] = []
    for relative in sorted(candidate_paths):
        source_kind = _historical_source_kind_for_relative(relative, root, layout)
        if source_kind is None:
            continue
        path = root / PurePosixPath(relative)
        if not os.path.lexists(path):
            continue
        source = _required_working_file(
            root,
            relative,
            source_kind,
            label="approved working-tree historical source",
        )
        extract_historical_source_records(
            root,
            relative,
            source_kind,
            layout=layout,
            source_bytes=source.data,
        )
        sources.append(source)
    return tuple(sources)


def _working_tree_historical_source_paths(root: Path, layout: StorageLayout) -> tuple[str, ...]:
    candidates: set[str] = set()

    def add(path: Path) -> None:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("approved historical source escapes the project root") from exc
        _validate_repository_relative_path(relative)
        candidates.add(relative)

    campaign_roots = [layout.active_campaign_root, *layout.archive_campaign_roots]
    campaign_roots.extend(root / PurePosixPath(old.rstrip("/")) for old, _new in layout.legacy_prefixes)
    for campaign_root in campaign_roots:
        for path in campaign_root.glob("*/campaign.yaml"):
            add(path)
    archived_root = root / "research" / "archived_generations"
    for path in archived_root.glob("*/campaigns/*/*/campaign.yaml"):
        add(path)
    for path in (
        root / "research_ledger.csv",
        root / "Start here" / "research_ledger.csv",
    ):
        if os.path.lexists(path):
            add(path)
    for path in archived_root.glob("*/research_ledger.csv"):
        add(path)
    governance = layout.research_artifact_root / "governance"
    experiment = governance / "experiment_registry.jsonl"
    if os.path.lexists(experiment):
        add(experiment)
    for path in governance.glob("research_reset*.json"):
        add(path)
    for path in historical_source_inventory(root, layout=layout):
        add(path)
    return tuple(sorted(candidates))


def _validate_repository_relative_path(value: str) -> None:
    if not value or value.startswith("/") or "\\" in value or "\x00" in value:
        raise ValueError(f"repository path is not canonical: {value!r}")
    path = PurePosixPath(value)
    if path.as_posix() != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"repository path is not canonical: {value!r}")


def _historical_source_path(root: Path, value: str | Path, *, commit_bound: bool) -> Path:
    path = Path(value)
    if commit_bound:
        if path.is_absolute():
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError as exc:
                raise ValueError("commit-bound historical source path escapes the project root") from exc
        else:
            relative = path.as_posix()
        _validate_repository_relative_path(relative)
        return root / PurePosixPath(relative)
    resolved = path.resolve()
    if not _is_relative_to(resolved, root):
        raise ValueError("historical source path escapes the project root")
    return resolved


def _historical_source_relative(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("historical source path escapes the project root") from exc
    _validate_repository_relative_path(relative)
    return relative


def _historical_record_sort_key(
    item: HistoricalEdgeIndexRecordV1,
) -> tuple[str, int, str, str]:
    return (
        item.source_path,
        item.source_row_number or 0,
        item.source_kind,
        item.record_id,
    )


def _historical_records_for_working_tree(
    root: Path,
    layout: StorageLayout,
    *,
    inventory: dict[Path, str] | None = None,
) -> list[HistoricalEdgeIndexRecordV1]:
    approved = inventory if inventory is not None else historical_source_inventory(root, layout=layout)
    records: list[HistoricalEdgeIndexRecordV1] = []
    for path, source_kind in sorted(approved.items(), key=lambda item: item[0].as_posix()):
        records.extend(
            extract_historical_source_records(
                root,
                path,
                source_kind,
                layout=layout,
            )
        )
    records.sort(key=_historical_record_sort_key)
    return records


def _storage_layout_for_repository_commit(root: Path, commit: str) -> StorageLayout:
    relative = "config/storage_layout.yaml"
    entry = _git(root, "ls-tree", "-z", commit, "--", relative)
    rows = [row for row in entry.split(b"\0") if row]
    if len(rows) != 1:
        raise ValueError("historical source commit is missing the committed storage layout file")
    metadata, raw_path = rows[0].split(b"\t", 1)
    mode, object_type, object_id = metadata.decode("ascii").split()
    if raw_path.decode("utf-8") != relative or mode != "100644" or object_type != "blob":
        raise ValueError("committed storage layout must be one canonical regular Git blob")
    data = _git(root, "cat-file", "blob", object_id)
    return _strict_committed_storage_layout(root, data)


def _strict_committed_storage_layout(root: Path, data: bytes) -> StorageLayout:
    if not data or not data.endswith(b"\n") or data.endswith(b"\n\n"):
        raise ValueError("committed storage layout must have exactly one final LF")
    if b"\r" in data or b"\t" in data or data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("committed storage layout is not canonically encoded")
    try:
        text = data.decode("utf-8")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        _validate_unique_yaml_mappings(node)
        document = yaml.safe_load(text)
    except (UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        raise ValueError(f"committed storage layout is malformed: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("committed storage layout must be a mapping")
    keys = set(document)
    if keys != _COMMITTED_LAYOUT_FIELDS:
        missing = sorted(_COMMITTED_LAYOUT_FIELDS - keys)
        extra = sorted(keys - _COMMITTED_LAYOUT_FIELDS)
        raise ValueError(
            f"committed storage layout fields are not canonical; missing={missing}, extra={extra}"
        )
    if document["schema"] != "alphaquest.storage-layout/v1":
        raise ValueError(f"unsupported committed storage layout schema: {document['schema']!r}")

    paths = {
        field: _canonical_layout_path(document[field], field=field)
        for field in _COMMITTED_LAYOUT_PATH_FIELDS
    }
    arrays: dict[str, tuple[str, ...]] = {}
    for field in ("archive_campaign_roots", "evidence_roots"):
        values = document[field]
        if not isinstance(values, list) or not values:
            raise ValueError(f"committed storage layout {field} must be a nonempty path list")
        normalized = tuple(
            _canonical_layout_path(value, field=f"{field}[{position}]")
            for position, value in enumerate(values)
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"committed storage layout {field} contains duplicate paths")
        arrays[field] = normalized

    prefixes = document["legacy_prefixes"]
    if not isinstance(prefixes, dict) or not prefixes:
        raise ValueError("committed storage layout legacy_prefixes must be a nonempty mapping")
    normalized_prefixes: list[tuple[str, str]] = []
    for old, new in prefixes.items():
        normalized_prefixes.append(
            (
                _canonical_layout_path(old, field="legacy_prefixes key", trailing_slash=True),
                _canonical_layout_path(new, field=f"legacy_prefixes[{old!r}]", trailing_slash=True),
            )
        )

    active = paths["active_campaign_root"]
    if any(_layout_paths_overlap(active, archive) for archive in arrays["archive_campaign_roots"]):
        raise ValueError("committed active and archive campaign roots must not overlap")
    for position, archive in enumerate(arrays["archive_campaign_roots"]):
        if any(
            _layout_paths_overlap(archive, other)
            for other in arrays["archive_campaign_roots"][position + 1 :]
        ):
            raise ValueError("committed archive campaign roots must not overlap")

    def absolute(value: str) -> Path:
        return root / PurePosixPath(value)

    return StorageLayout(
        project_root=root,
        active_campaign_root=absolute(active),
        archive_campaign_roots=tuple(absolute(value) for value in arrays["archive_campaign_roots"]),
        evidence_roots=tuple(absolute(value) for value in arrays["evidence_roots"]),
        research_artifact_root=absolute(paths["research_artifact_root"]),
        catalog_root=absolute(paths["catalog_root"]),
        views_root=absolute(paths["views_root"]),
        run_store_root=absolute(paths["run_store_root"]),
        draft_root=absolute(paths["draft_root"]),
        dataset_root=absolute(paths["dataset_root"]),
        handoff_root=absolute(paths["handoff_root"]),
        studio_runtime_root=absolute(paths["studio_runtime_root"]),
        edge_backlog_root=absolute(paths["edge_backlog_root"]),
        edge_backlog_history_index=absolute(paths["edge_backlog_history_index"]),
        migration_manifest=absolute(paths["migration_manifest"]),
        legacy_prefixes=tuple(
            sorted(normalized_prefixes, key=lambda item: len(item[0]), reverse=True)
        ),
    )


def _validate_unique_yaml_mappings(node: yaml.Node | None) -> None:
    if node is None:
        raise ValueError("empty YAML document")
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key, value in node.value:
            if not isinstance(key, yaml.ScalarNode):
                raise ValueError("mapping keys must be plain scalar values")
            if key.value in seen:
                raise ValueError(f"duplicate mapping key {key.value!r}")
            seen.add(key.value)
            _validate_unique_yaml_mappings(value)
    elif isinstance(node, yaml.SequenceNode):
        for value in node.value:
            _validate_unique_yaml_mappings(value)


def _canonical_layout_path(
    value: Any,
    *,
    field: str,
    trailing_slash: bool = False,
) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"committed storage layout {field} must be a nonblank canonical path")
    if "\\" in value or "\x00" in value or value.startswith("/"):
        raise ValueError(f"committed storage layout {field} must be a project-relative POSIX path")
    if trailing_slash != value.endswith("/"):
        requirement = "end with /" if trailing_slash else "not end with /"
        raise ValueError(f"committed storage layout {field} must {requirement}")
    raw = value[:-1] if trailing_slash else value
    path = PurePosixPath(raw)
    if raw in {"", "."} or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"committed storage layout {field} is not canonical")
    if path.as_posix() != raw:
        raise ValueError(f"committed storage layout {field} is not canonical")
    return value


def _layout_paths_overlap(first: str, second: str) -> bool:
    first_path = PurePosixPath(first)
    second_path = PurePosixPath(second)
    return first_path == second_path or first_path in second_path.parents or second_path in first_path.parents


def build_historical_edge_index(
    project_root: str | Path = ".",
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a byte-stable index without writing any canonical research object."""

    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    output = _validated_output_path(root, layout, output_path)

    source_inventory = historical_source_inventory(root, layout=layout)
    source_paths = set(source_inventory)
    if output.resolve() in {path.resolve() for path in source_paths}:
        raise ValueError("derived history index target cannot replace a bootstrap source file")
    records = _historical_records_for_working_tree(root, layout, inventory=source_inventory)
    data = b"".join(canonical_json_bytes(item) + b"\n" for item in records)
    lock_path = layout.studio_runtime_root / "edge-backlog.lock"
    with backlog_file_lock(lock_path, exclusive=True):
        _assert_replaceable_derived_index(output)
        _atomic_replace(output, data)
    counts: dict[str, int] = {}
    for record in records:
        counts[record.source_kind] = counts.get(record.source_kind, 0) + 1
    return {
        "schema": "alphaquest.edge-backlog-history-index-build/v1",
        "status": "PASS",
        "output_path": display_path(output, root),
        "output_sha256": hashlib.sha256(data).hexdigest(),
        "records": len(records),
        "source_counts": dict(sorted(counts.items())),
        "source_generation_counts": {
            generation: sum(item.source_generation == generation for item in records)
            for generation in ("CURRENT", "CONFIGURED_ARCHIVE", "CLEAN_SLATE_ARCHIVE")
        },
        "historical_ineligible": sum(item.source_generation != "CURRENT" for item in records),
        "not_current_p1_evidence": sum(item.p1_evidence_eligibility == "NOT_CURRENT_P1_EVIDENCE" for item in records),
        "duplicate_recall_only": sum(item.derived_index_use == "DUPLICATE_RECALL_ONLY" for item in records),
        "needs_manual_review": sum(item.semantic_resolution == "NEEDS_MANUAL_REVIEW" for item in records),
    }


def validate_historical_edge_index(
    path: str | Path,
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path)
    records = load_historical_edge_index_records(source)
    root = Path(project_root).resolve() if project_root is not None else _infer_project_root(source)
    validate_historical_index_records(records, project_root=root)
    return {
        "schema": "alphaquest.edge-backlog-history-index-validation/v1",
        "status": "PASS",
        "records": len(records),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


def _campaign_record(
    root: Path,
    path: Path,
    layout: StorageLayout,
    source_bytes: bytes | None = None,
) -> HistoricalEdgeIndexRecordV1:
    try:
        data = path.read_bytes() if source_bytes is None else source_bytes
        if not data.strip():
            raise ValueError("campaign definition is blank")
        payload = yaml.safe_load(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        raise ValueError(f"invalid historical campaign definition {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"historical campaign definition must be a mapping: {path}")
    result = payload.get("result_summary") if isinstance(payload.get("result_summary"), dict) else {}
    fingerprint = payload.get("economic_edge_fingerprint")
    raw = {
        "source_kind": "CAMPAIGN_DEFINITION",
        "source_path": _historical_source_relative(root, path),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_row_number": None,
        **_generation(path, root, layout),
        "campaign_id": _optional(payload.get("campaign_id") or path.parent.name),
        "variant_id": None,
        "attempt_id": None,
        "instrument": _optional(payload.get("instrument") or payload.get("symbol")),
        "timeframe": _optional(payload.get("timeframe")),
        "raw_title": _optional(payload.get("title")),
        "raw_edge": _optional(payload.get("edge") or payload.get("market_behavior")),
        "raw_hypothesis": _optional(payload.get("hypothesis")),
        "raw_edge_family": _optional(payload.get("edge_family")),
        "raw_counterparty_transfer_rationale": _optional(
            payload.get("counterparty_transfer_rationale") or payload.get("counterparty")
        ),
        "raw_information_availability": _optional(
            payload.get("information_availability") or payload.get("information_availability_timeline")
        ),
        "raw_expected_effect": _optional(payload.get("expected_effect")),
        "raw_config_path": None,
        "raw_report_path": None,
        "legacy_fingerprint": _json_safe(fingerprint) if fingerprint is not None else None,
        "raw_outcome": _optional(
            result.get("verdict") or payload.get("verdict") or payload.get("decision") or payload.get("status")
        ),
        "raw_scientific_verdict": _optional(result.get("verdict") or payload.get("verdict")),
        "raw_disposition": _optional(payload.get("decision") or payload.get("status")),
        "raw_failure_reason": _optional(result.get("failure_reason") or payload.get("failure_reason")),
    }
    return _seal_history(raw)


def _ledger_records(
    root: Path,
    path: Path,
    layout: StorageLayout,
    source_bytes: bytes | None = None,
) -> list[HistoricalEdgeIndexRecordV1]:
    output = []
    try:
        data = path.read_bytes() if source_bytes is None else source_bytes
        text = data.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"could not read historical ledger {path}: {exc}") from exc
    source_sha256 = hashlib.sha256(data).hexdigest()
    try:
        with io.StringIO(text, newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                raw = {
                    "source_kind": "RESEARCH_LEDGER_ROW",
                    "source_path": _historical_source_relative(root, path),
                    "source_sha256": source_sha256,
                    "source_row_number": row_number,
                    **_generation(path, root, layout),
                    "campaign_id": _optional(row.get("campaign_id") or row.get("strategy_id")),
                    "variant_id": _optional(row.get("variant_id")),
                    "attempt_id": _optional(row.get("attempt_id")),
                    "instrument": _optional(row.get("instrument") or row.get("symbol")),
                    "timeframe": _optional(row.get("timeframe")),
                    "raw_title": _optional(row.get("title")),
                    "raw_edge": _optional(row.get("edge")),
                    "raw_hypothesis": _optional(row.get("hypothesis")),
                    "raw_edge_family": _optional(row.get("edge_family")),
                    "raw_counterparty_transfer_rationale": _optional(row.get("counterparty_transfer_rationale")),
                    "raw_information_availability": _optional(row.get("information_availability")),
                    "raw_expected_effect": _optional(row.get("expected_effect")),
                    "raw_config_path": _optional(row.get("config_path")),
                    "raw_report_path": _optional(row.get("report_path")),
                    "legacy_fingerprint": _optional(row.get("economic_edge_fingerprint")),
                    "raw_outcome": _optional(row.get("verdict") or row.get("result") or row.get("status")),
                    "raw_scientific_verdict": _optional(row.get("verdict") or row.get("result")),
                    "raw_disposition": _optional(row.get("decision") or row.get("status")),
                    "raw_failure_reason": _optional(
                        row.get("failure_reason") or row.get("first_failed_stage") or row.get("notes")
                    ),
                }
                output.append(_seal_history(raw))
    except (OSError, csv.Error) as exc:
        raise ValueError(f"could not read historical ledger {path}: {exc}") from exc
    return output


def _experiment_records(
    root: Path,
    path: Path,
    layout: StorageLayout,
    source_bytes: bytes | None = None,
) -> list[HistoricalEdgeIndexRecordV1]:
    output = []
    try:
        data = path.read_bytes() if source_bytes is None else source_bytes
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"could not read experiment registry {path}: {exc}") from exc
    source_sha256 = hashlib.sha256(data).hexdigest()
    for row_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid experiment registry JSON at {path}:{row_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"experiment registry row must be an object at {path}:{row_number}")
        raw = {
            "source_kind": "EXPERIMENT_REGISTRY_EVENT",
            "source_path": _historical_source_relative(root, path),
            "source_sha256": source_sha256,
            "source_row_number": row_number,
            **_generation(path, root, layout),
            "campaign_id": _optional(row.get("campaign_id")),
            "variant_id": _optional(row.get("variant_id")),
            "attempt_id": _optional(row.get("attempt_id")),
            "instrument": None,
            "timeframe": None,
            "raw_title": None,
            "raw_edge": None,
            "raw_hypothesis": None,
            "raw_edge_family": None,
            "raw_counterparty_transfer_rationale": None,
            "raw_information_availability": None,
            "raw_expected_effect": None,
            "raw_config_path": None,
            "raw_report_path": None,
            "legacy_fingerprint": _optional(row.get("economic_edge_fingerprint_sha256")),
            "raw_outcome": _optional(row.get("verdict") or row.get("status") or row.get("to_status")),
            "raw_scientific_verdict": _optional(row.get("verdict")),
            "raw_disposition": _optional(row.get("status") or row.get("to_status")),
            "raw_failure_reason": _optional(row.get("failure_reason") or row.get("reason")),
        }
        output.append(_seal_history(raw))
    return output


def _reset_record(
    root: Path,
    path: Path,
    layout: StorageLayout,
    source_bytes: bytes | None = None,
) -> HistoricalEdgeIndexRecordV1:
    try:
        data = path.read_bytes() if source_bytes is None else source_bytes
        if not data.strip():
            raise ValueError("reset manifest is blank")
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid historical reset manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"historical reset manifest must be an object: {path}")
    raw = {
        "source_kind": "RESEARCH_RESET_MANIFEST",
        "source_path": _historical_source_relative(root, path),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_row_number": None,
        **_generation(path, root, layout),
        "campaign_id": None,
        "variant_id": None,
        "attempt_id": None,
        "instrument": None,
        "timeframe": None,
        "raw_title": "research reset manifest",
        "raw_edge": None,
        "raw_hypothesis": None,
        "raw_edge_family": None,
        "raw_counterparty_transfer_rationale": None,
        "raw_information_availability": None,
        "raw_expected_effect": None,
        "raw_config_path": None,
        "raw_report_path": None,
        "legacy_fingerprint": None,
        "raw_outcome": _optional(payload.get("status")),
        "raw_scientific_verdict": None,
        "raw_disposition": _optional(payload.get("status")),
        "raw_failure_reason": None,
    }
    return _seal_history(raw)


def _seal_history(raw: Mapping[str, Any]) -> HistoricalEdgeIndexRecordV1:
    semantic = {
        "instrument": raw.get("instrument"),
        "market_behavior": raw.get("raw_edge"),
        "causal_mechanism": raw.get("raw_hypothesis"),
        "counterparty": raw.get("raw_counterparty_transfer_rationale"),
        "information_availability": raw.get("raw_information_availability"),
        "expected_effect": raw.get("raw_expected_effect"),
        "holding_horizon": raw.get("timeframe"),
        "market_context": (
            raw.get("legacy_fingerprint", {}).get("market_context")
            if isinstance(raw.get("legacy_fingerprint"), dict)
            else None
        ),
        "information_inputs": (
            raw.get("legacy_fingerprint", {}).get("signal_inputs")
            if isinstance(raw.get("legacy_fingerprint"), dict)
            else None
        ),
    }
    populated = sum(_present(value) for value in semantic.values())
    completeness = "COMPLETE" if populated == len(semantic) else "PARTIAL" if populated >= 3 else "INSUFFICIENT"
    identity_material = {
        "source_kind": raw["source_kind"],
        "source_path": raw["source_path"],
        "source_sha256": raw["source_sha256"],
        "source_row_number": raw.get("source_row_number"),
    }
    record_id = "history." + hashlib.sha256(canonical_json_bytes(identity_material)).hexdigest()[:24]
    payload = {
        "schema": HISTORY_INDEX_SCHEMA,
        "record_id": record_id,
        **dict(raw),
        "extraction_completeness": completeness,
        "semantic_resolution": "NEEDS_MANUAL_REVIEW",
    }
    payload["record_sha256"] = record_sha256(payload)
    return HistoricalEdgeIndexRecordV1.model_validate(payload)


def _generation(path: Path, root: Path, layout: StorageLayout) -> dict[str, str]:
    for archive_root in layout.archive_campaign_roots:
        if _is_relative_to(path, archive_root):
            return {
                "source_generation": "CONFIGURED_ARCHIVE",
                "archive_generation": _historical_source_relative(root, archive_root),
                "p1_evidence_eligibility": "NOT_CURRENT_P1_EVIDENCE",
                "derived_index_use": "DUPLICATE_RECALL_ONLY",
            }
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    parts = relative.parts
    try:
        index = parts.index("archived_generations")
    except ValueError:
        return {
            "source_generation": "CURRENT",
            "archive_generation": "CURRENT",
            "p1_evidence_eligibility": "NOT_CURRENT_P1_EVIDENCE",
            "derived_index_use": "DUPLICATE_RECALL_ONLY",
        }
    generation = parts[index + 1] if index + 1 < len(parts) else "UNKNOWN_ARCHIVE"
    return {
        "source_generation": "CLEAN_SLATE_ARCHIVE",
        "archive_generation": generation,
        "p1_evidence_eligibility": "NOT_CURRENT_P1_EVIDENCE",
        "derived_index_use": "DUPLICATE_RECALL_ONLY",
    }


def _validated_output_path(
    root: Path,
    layout: StorageLayout,
    output_path: str | Path | None,
) -> Path:
    configured = layout.edge_backlog_history_index.resolve()
    requested = Path(output_path) if output_path is not None else configured
    requested = requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    if requested != configured:
        raise ValueError("derived history index output must equal the configured edge_backlog_history_index")
    catalog_root = layout.catalog_root.resolve()
    if requested == catalog_root or not _is_relative_to(requested, catalog_root):
        raise ValueError("derived history index must be a file beneath the configured catalog_root")
    protected_roots = (
        layout.edge_backlog_root,
        layout.active_campaign_root,
        *layout.archive_campaign_roots,
        *layout.evidence_roots,
        *(root / name for name in ("config", "docs", "src", "tests", "tools", "apps", "execution_system")),
    )
    if any(_is_relative_to(requested, protected.resolve()) for protected in protected_roots):
        raise ValueError("derived history index target overlaps protected canonical or research storage")
    protected_files = (
        root / "config/research_operating_model.yaml",
        root / "docs/research/research-operating-model.md",
        root / "src/alphaquest/research/operating_model.py",
    )
    if requested in {path.resolve() for path in protected_files}:
        raise ValueError("derived history index target overlaps canonical P1 policy storage")
    return requested


def _assert_replaceable_derived_index(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_file():
        raise ValueError("derived history index target is not a regular file")
    try:
        validate_historical_edge_index(path)
    except (OSError, ValueError) as exc:
        if _is_valid_prior_history_index_v1(path) or _is_valid_reachable_history_index(path):
            return
        raise ValueError(
            "existing derived history index target is not a valid derived index and will not be replaced"
        ) from exc


def _is_valid_reachable_history_index(path: Path) -> bool:
    """Permit replacement only for an exact projection of a reachable Git commit."""

    try:
        root = _infer_project_root(path)
        records = load_historical_edge_index_records(path)
        commits = str(_git(root, "rev-list", "HEAD", text=True)).splitlines()
    except (OSError, ValueError):
        return False
    actual = [item.model_dump(mode="json", by_alias=True) for item in records]
    for commit in commits:
        try:
            expected = historical_repository_state(root, commit).records
        except (OSError, ValueError):
            continue
        if actual == [item.model_dump(mode="json", by_alias=True) for item in expected]:
            return True
    return False


def _is_valid_prior_history_index_v1(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if not data or not data.endswith(b"\n"):
        return False
    try:
        root = _infer_project_root(path)
        layout = load_storage_layout(root)
        expected = _historical_records_for_working_tree(root, layout)
    except (OSError, ValueError):
        return False
    seen_ids: set[str] = set()
    previous_key: tuple[str, int, str, str] | None = None
    records: list[HistoricalEdgeIndexPriorV1] = []
    for raw_line in data.splitlines():
        if not raw_line:
            return False
        try:
            record = HistoricalEdgeIndexPriorV1.model_validate_json(raw_line)
        except ValueError:
            return False
        if raw_line != canonical_json_bytes(record):
            return False
        if record.record_id in seen_ids:
            return False
        key = (
            record.source_path,
            record.source_row_number or 0,
            record.source_kind,
            record.record_id,
        )
        if previous_key is not None and key <= previous_key:
            return False
        records.append(record)
        seen_ids.add(record.record_id)
        previous_key = key
    return len(records) == len(expected) and all(
        _prior_projection_matches(prior, current)
        for prior, current in zip(records, expected, strict=True)
    )


def _prior_projection_matches(
    prior: HistoricalEdgeIndexPriorV1,
    current: HistoricalEdgeIndexRecordV1,
) -> bool:
    shared_fields = (
        "record_id",
        "source_kind",
        "source_path",
        "source_sha256",
        "source_row_number",
        "archive_generation",
        "campaign_id",
        "variant_id",
        "attempt_id",
        "instrument",
        "timeframe",
        "raw_title",
        "raw_edge",
        "raw_hypothesis",
        "raw_edge_family",
        "raw_counterparty_transfer_rationale",
        "raw_information_availability",
        "raw_expected_effect",
        "raw_config_path",
        "raw_report_path",
        "legacy_fingerprint",
        "raw_outcome",
        "raw_scientific_verdict",
        "raw_disposition",
        "raw_failure_reason",
        "extraction_completeness",
    )
    return all(getattr(prior, field) == getattr(current, field) for field in shared_fields)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _add_source(inventory: dict[Path, str], path: Path, source_kind: str) -> None:
    resolved = path.resolve()
    previous = inventory.get(resolved)
    if previous is not None and previous != source_kind:
        raise ValueError(f"historical source has ambiguous kinds: {resolved}")
    inventory[resolved] = source_kind


def _historical_source_kind_for_relative(
    value: str,
    root: Path,
    layout: StorageLayout,
) -> str | None:
    relative = Path(value)
    if relative in {Path("research_ledger.csv"), Path("Start here/research_ledger.csv")} or (
        len(relative.parts) == 4
        and relative.parts[0:2] == ("research", "archived_generations")
        and relative.name == "research_ledger.csv"
    ):
        return "RESEARCH_LEDGER_ROW"
    governance = _relative_to_root(layout.research_artifact_root / "governance", root)
    if governance is not None and relative.parent == governance:
        if relative.name == "experiment_registry.jsonl":
            return "EXPERIMENT_REGISTRY_EVENT"
        if relative.name.startswith("research_reset") and relative.suffix == ".json":
            return "RESEARCH_RESET_MANIFEST"
    if relative.name != "campaign.yaml":
        return None
    campaign_roots = [layout.active_campaign_root, *layout.archive_campaign_roots]
    for configured_root in campaign_roots:
        configured = _relative_to_root(configured_root, root)
        if configured is not None and _is_direct_campaign_definition(relative, configured):
            return "CAMPAIGN_DEFINITION"
    for old_prefix, _new_prefix in layout.legacy_prefixes:
        legacy = Path(old_prefix.rstrip("/"))
        if _is_direct_campaign_definition(relative, legacy):
            return "CAMPAIGN_DEFINITION"
    parts = relative.parts
    if (
        len(parts) >= 7
        and parts[0:2] == ("research", "archived_generations")
        and parts[3] == "campaigns"
        and parts[-1] == "campaign.yaml"
        and len(parts[4:]) == 3
    ):
        return "CAMPAIGN_DEFINITION"
    return None


def _is_direct_campaign_definition(path: Path, source_root: Path) -> bool:
    try:
        remainder = path.relative_to(source_root)
    except ValueError:
        return False
    return len(remainder.parts) == 2 and remainder.parts[-1] == "campaign.yaml"


def _relative_to_root(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def _infer_project_root(index_path: Path) -> Path:
    source = index_path.resolve()
    for parent in source.parents:
        if (parent / "config/storage_layout.yaml").is_file():
            return parent
    if source.parent.name == "catalogs":
        return source.parent.parent
    raise ValueError("project_root is required to validate historical source provenance")


def _git(root: Path, *arguments: str, text: bool = False) -> bytes | str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise ValueError(f"could not resolve immutable historical source commit: {detail}") from exc
    return result.stdout


def _git_optional(root: Path, *arguments: str, text: bool = False) -> bytes | str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
    except OSError:
        raise
    if result.returncode == 0:
        return result.stdout
    return None


def _git_with_input(root: Path, data: bytes, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip() if isinstance(
            exc, subprocess.CalledProcessError
        ) else str(exc)
        raise ValueError(f"could not inspect immutable Git object: {detail}") from exc
    return result.stdout


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _present(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(str(value or "").strip())


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, allow_nan=False))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "HISTORY_INDEX_SCHEMA",
    "HistoricalEdgeIndexRecordV1",
    "HistoricalRepositoryState",
    "HistoricalSourceFileState",
    "RepositoryFileAnchor",
    "build_historical_edge_index",
    "historical_records_for_repository_commit",
    "historical_records_for_current_review",
    "historical_repository_state",
    "historical_source_layout_for_repository_commit",
    "historical_source_layout_semantics",
    "historical_source_state_for_working_tree",
    "historical_source_inventory",
    "repository_commit_is_ancestor",
    "repository_file_anchor",
    "repository_head",
    "repository_path_inventory",
    "validate_historical_edge_index",
    "validate_historical_index_records",
    "validate_historical_record_provenance",
    "validate_historical_records_provenance",
]
