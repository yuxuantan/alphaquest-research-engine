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
    Sha256,
    StrictBacklogModel,
    canonical_json_bytes,
    record_sha256,
)
from alphaquest.research.storage import campaign_definition_paths, display_path, load_storage_layout


HISTORY_INDEX_SCHEMA = "alphaquest.edge-backlog-history-index-record/v1"


class HistoricalEdgeIndexRecordV1(StrictBacklogModel):
    """One provenance-preserving projection from an existing historical source."""

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
    def validate_hash(self) -> "HistoricalEdgeIndexRecordV1":
        if self.record_sha256 != record_sha256(self.model_dump(mode="json", by_alias=True)):
            raise ValueError("historical index record_sha256 mismatch")
        return self


def build_historical_edge_index(
    project_root: str | Path = ".",
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a byte-stable index without writing any canonical research object."""

    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    output = Path(output_path) if output_path is not None else layout.edge_backlog_history_index
    output = output if output.is_absolute() else root / output

    records: list[HistoricalEdgeIndexRecordV1] = []
    definitions = set(campaign_definition_paths(project_root=root, include_ledger=True))
    archived_root = root / "research" / "archived_generations"
    if archived_root.is_dir():
        definitions.update(path.resolve() for path in archived_root.glob("*/campaigns/*/*/campaign.yaml"))
    for path in sorted(definitions):
        record = _campaign_record(root, path)
        if record is not None:
            records.append(record)

    for path in sorted(root.glob("**/research_ledger.csv")):
        if not path.is_file() or _is_generated_or_git(path, root, layout.catalog_root):
            continue
        records.extend(_ledger_records(root, path))

    experiment_path = layout.research_artifact_root / "governance" / "experiment_registry.jsonl"
    if experiment_path.is_file():
        records.extend(_experiment_records(root, experiment_path))

    for path in sorted((layout.research_artifact_root / "governance").glob("research_reset*.json")):
        record = _reset_record(root, path)
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
        "historical_ineligible": sum(item.evidence_eligibility == "HISTORICAL_INELIGIBLE" for item in records),
        "needs_manual_review": sum(item.semantic_resolution == "NEEDS_MANUAL_REVIEW" for item in records),
    }


def validate_historical_edge_index(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"historical edge index not found: {source}")
    records = []
    previous_key: tuple[str, int, str, str] | None = None
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank historical index line at {line_number}")
        record = HistoricalEdgeIndexRecordV1.model_validate_json(line)
        key = (
            record.source_path,
            record.source_row_number or 0,
            record.source_kind,
            record.record_id,
        )
        if previous_key is not None and key < previous_key:
            raise ValueError("historical edge index is not deterministically sorted")
        records.append(record)
        previous_key = key
    return {
        "schema": "alphaquest.edge-backlog-history-index-validation/v1",
        "status": "PASS",
        "records": len(records),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


def _campaign_record(root: Path, path: Path) -> HistoricalEdgeIndexRecordV1 | None:
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
        **_generation(path, root),
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


def _ledger_records(root: Path, path: Path) -> list[HistoricalEdgeIndexRecordV1]:
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
                    **_generation(path, root),
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


def _experiment_records(root: Path, path: Path) -> list[HistoricalEdgeIndexRecordV1]:
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
            **_generation(path, root),
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


def _reset_record(root: Path, path: Path) -> HistoricalEdgeIndexRecordV1 | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = {
        "source_kind": "RESEARCH_RESET_MANIFEST",
        "source_path": display_path(path, root),
        "source_sha256": _file_sha256(path),
        "source_row_number": None,
        **_generation(path, root),
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
        "semantic_resolution": "LEGACY_CANDIDATE" if completeness == "COMPLETE" else "NEEDS_MANUAL_REVIEW",
    }
    payload["record_sha256"] = record_sha256(payload)
    return HistoricalEdgeIndexRecordV1.model_validate(payload)


def _generation(path: Path, root: Path) -> dict[str, str]:
    try:
        relative = path.resolve().relative_to(root)
    except ValueError:
        relative = path
    parts = relative.parts
    try:
        index = parts.index("archived_generations")
    except ValueError:
        return {"archive_generation": "CURRENT", "evidence_eligibility": "CURRENT_SCOPE"}
    generation = parts[index + 1] if index + 1 < len(parts) else "UNKNOWN_ARCHIVE"
    return {
        "archive_generation": generation,
        "evidence_eligibility": "HISTORICAL_INELIGIBLE",
    }


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


def _is_generated_or_git(path: Path, root: Path, catalog_root: Path) -> bool:
    resolved = path.resolve()
    try:
        resolved.relative_to((root / ".git").resolve())
        return True
    except ValueError:
        pass
    try:
        resolved.relative_to(catalog_root.resolve())
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
