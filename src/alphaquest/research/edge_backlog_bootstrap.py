"""Deterministic, derived-only historical Edge Backlog index."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
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
    definitions = set(campaign_definition_paths(project_root=root, include_ledger=True))
    archived_root = root / "research" / "archived_generations"
    if archived_root.is_dir():
        definitions.update(path.resolve() for path in archived_root.glob("*/campaigns/*/*/campaign.yaml"))
    ledger_paths = tuple(
        path for path in sorted(root.glob("**/research_ledger.csv")) if path.is_file() and not _is_git_path(path, root)
    )
    experiment_path = layout.research_artifact_root / "governance" / "experiment_registry.jsonl"
    experiment_paths = (experiment_path,) if experiment_path.is_file() else ()
    reset_paths = tuple(
        path for path in sorted((layout.research_artifact_root / "governance").glob("research_reset*.json"))
    )
    source_paths = {*definitions, *ledger_paths, *experiment_paths, *reset_paths}
    if output.resolve() in {path.resolve() for path in source_paths}:
        raise ValueError("derived history index target cannot replace a bootstrap source file")
    for path in sorted(definitions):
        record = _campaign_record(root, path, layout)
        if record is not None:
            records.append(record)

    for path in ledger_paths:
        records.extend(_ledger_records(root, path, layout))

    for path in experiment_paths:
        records.extend(_experiment_records(root, path, layout))

    for path in reset_paths:
        record = _reset_record(root, path, layout)
        if record is not None:
            records.append(record)

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


def validate_historical_edge_index(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    records = load_historical_edge_index_records(source)
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
) -> HistoricalEdgeIndexRecordV1 | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(payload, dict):
        return None
    result = payload.get("result_summary") if isinstance(payload.get("result_summary"), dict) else {}
    fingerprint = payload.get("economic_edge_fingerprint")
    raw = {
        "source_kind": "CAMPAIGN_DEFINITION",
        "source_path": display_path(path, root),
        "source_sha256": _file_sha256(path),
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


def _ledger_records(root: Path, path: Path, layout: StorageLayout) -> list[HistoricalEdgeIndexRecordV1]:
    output = []
    source_sha256 = _file_sha256(path)
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
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


def _experiment_records(root: Path, path: Path, layout: StorageLayout) -> list[HistoricalEdgeIndexRecordV1]:
    output = []
    source_sha256 = _file_sha256(path)
    for row_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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


def _reset_record(root: Path, path: Path, layout: StorageLayout) -> HistoricalEdgeIndexRecordV1 | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = {
        "source_kind": "RESEARCH_RESET_MANIFEST",
        "source_path": display_path(path, root),
        "source_sha256": _file_sha256(path),
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
    seen_ids: set[str] = set()
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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


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


def _is_git_path(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    try:
        resolved.relative_to((root / ".git").resolve())
        return True
    except ValueError:
        return False


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
