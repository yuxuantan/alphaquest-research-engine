"""Deterministic, derived-only historical Edge Backlog index."""

from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
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
    source = Path(path).resolve()
    layout = layout or load_storage_layout(root)
    if source_kind == "CAMPAIGN_DEFINITION":
        record = _campaign_record(root, source, layout, source_bytes)
        return [] if record is None else [record]
    if source_kind == "RESEARCH_LEDGER_ROW":
        return _ledger_records(root, source, layout, source_bytes)
    if source_kind == "EXPERIMENT_REGISTRY_EVENT":
        return _experiment_records(root, source, layout, source_bytes)
    if source_kind == "RESEARCH_RESET_MANIFEST":
        record = _reset_record(root, source, layout, source_bytes)
        return [] if record is None else [record]
    raise ValueError(f"unsupported historical source_kind: {source_kind!r}")


def validate_historical_record_provenance(
    record: HistoricalEdgeIndexRecordV1,
    *,
    project_root: str | Path,
    layout: StorageLayout | None = None,
) -> None:
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
    """Verify strict rows against existing files in approved historical roots."""

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


def historical_records_for_repository_commit(
    project_root: str | Path,
    commit: str | None = None,
) -> tuple[str, list[HistoricalEdgeIndexRecordV1]]:
    """Rebuild the complete matcher universe from one immutable Git source tree."""

    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    requested = commit or "HEAD"
    resolved = _git(root, "rev-parse", f"{requested}^{{commit}}", text=True).strip()
    if commit is not None and resolved != commit:
        raise ValueError("historical source commit must be a full immutable Git object ID")
    tree = _git(root, "ls-tree", "-r", "-z", "--full-tree", resolved)
    blobs: list[tuple[str, str, str]] = []
    for raw in tree.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        _mode, object_type, object_id = metadata.decode("ascii").split()
        if object_type != "blob":
            continue
        relative = raw_path.decode("utf-8")
        source_kind = _historical_source_kind_for_relative(relative, root, layout)
        if source_kind is not None:
            blobs.append((relative, object_id, source_kind))
    records: list[HistoricalEdgeIndexRecordV1] = []
    for relative, object_id, source_kind in sorted(blobs):
        data = _git(root, "cat-file", "blob", object_id)
        records.extend(
            extract_historical_source_records(
                root,
                root / relative,
                source_kind,
                layout=layout,
                source_bytes=data,
            )
        )
    records.sort(key=lambda item: (item.source_path, item.source_row_number or 0, item.source_kind, item.record_id))
    return resolved, records


def repository_commit_recorded_at(project_root: str | Path, commit: str) -> datetime:
    root = Path(project_root).resolve()
    value = _git(root, "show", "-s", "--format=%cI", commit, text=True).strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("historical source commit has an invalid immutable timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("historical source commit timestamp must be timezone-aware")
    return parsed


def build_historical_edge_index(
    project_root: str | Path = ".",
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a byte-stable index without writing any canonical research object."""

    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    output = _validated_output_path(root, layout, output_path)

    records: list[HistoricalEdgeIndexRecordV1] = []
    source_inventory = historical_source_inventory(root, layout=layout)
    source_paths = set(source_inventory)
    if output.resolve() in {path.resolve() for path in source_paths}:
        raise ValueError("derived history index target cannot replace a bootstrap source file")
    for path, source_kind in sorted(source_inventory.items(), key=lambda item: item[0].as_posix()):
        records.extend(extract_historical_source_records(root, path, source_kind, layout=layout))

    records.sort(
        key=lambda item: (
            item.source_path,
            item.source_row_number or 0,
            item.source_kind,
            item.record_id,
        )
    )
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
    validate_historical_records_provenance(records, project_root=root)
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
) -> HistoricalEdgeIndexRecordV1 | None:
    try:
        data = path.read_bytes() if source_bytes is None else source_bytes
        payload = yaml.safe_load(data.decode("utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(payload, dict):
        return None
    result = payload.get("result_summary") if isinstance(payload.get("result_summary"), dict) else {}
    fingerprint = payload.get("economic_edge_fingerprint")
    raw = {
        "source_kind": "CAMPAIGN_DEFINITION",
        "source_path": display_path(path, root),
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
                    "source_path": display_path(path, root),
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
            continue
        raw = {
            "source_kind": "EXPERIMENT_REGISTRY_EVENT",
            "source_path": display_path(path, root),
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
) -> HistoricalEdgeIndexRecordV1 | None:
    try:
        data = path.read_bytes() if source_bytes is None else source_bytes
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    raw = {
        "source_kind": "RESEARCH_RESET_MANIFEST",
        "source_path": display_path(path, root),
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
        "raw_outcome": _optional(payload.get("status") if isinstance(payload, dict) else None),
        "raw_scientific_verdict": None,
        "raw_disposition": _optional(payload.get("status") if isinstance(payload, dict) else None),
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
        if _is_relative_to(path.resolve(), archive_root.resolve()):
            return {
                "source_generation": "CONFIGURED_ARCHIVE",
                "archive_generation": display_path(archive_root, root),
                "p1_evidence_eligibility": "NOT_CURRENT_P1_EVIDENCE",
                "derived_index_use": "DUPLICATE_RECALL_ONLY",
            }
    try:
        relative = path.resolve().relative_to(root)
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
        if _is_valid_prior_history_index_v1(path):
            return
        raise ValueError(
            "existing derived history index target is not a valid derived index and will not be replaced"
        ) from exc


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
        inventory = historical_source_inventory(root, layout=layout)
    except (OSError, ValueError):
        return False
    seen_ids: set[str] = set()
    expected_cache: dict[Path, list[HistoricalEdgeIndexRecordV1]] = {}
    previous_key: tuple[str, int, str, str] | None = None
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
        source = (root / record.source_path).resolve()
        expected_kind = inventory.get(source)
        if expected_kind != record.source_kind:
            return False
        try:
            if source not in expected_cache:
                expected_cache[source] = extract_historical_source_records(
                    root,
                    source,
                    expected_kind,
                    layout=layout,
                )
            expected_rows = expected_cache[source]
        except (OSError, ValueError):
            return False
        expected = next(
            (
                item
                for item in expected_rows
                if item.source_row_number == record.source_row_number
                and item.source_path == record.source_path
                and item.source_sha256 == record.source_sha256
            ),
            None,
        )
        if expected is None or not _prior_projection_matches(record, expected):
            return False
        key = (
            record.source_path,
            record.source_row_number or 0,
            record.source_kind,
            record.record_id,
        )
        if previous_key is not None and key <= previous_key:
            return False
        seen_ids.add(record.record_id)
        previous_key = key
    return True


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
        return path.resolve().relative_to(root)
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
    "build_historical_edge_index",
    "validate_historical_edge_index",
]
