"""Append-only canonical P3 literature store and offline artifact verifier."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Iterator, Mapping, TypeVar

from pydantic import BaseModel, ValidationError

from alphaquest.research.edge_backlog_io import (
    exclusive_write_repository_file,
    read_repository_file,
    read_repository_file_optional,
    repository_directory_fd,
    repository_file_lock,
)
from alphaquest.research.literature.contracts import (
    CANONICAL_RECORD_TYPES,
    SCHEMA_TYPES,
    ActorProvenanceV1,
    CanonicalRecordV1,
    ClaimExtractionRevisionV1,
    CodexTaskAttemptRevisionV1,
    DossierFreezeV1,
    EdgeDossierRevisionV1,
    EvidenceRelationRevisionV1,
    LiteratureConflictError,
    LiteratureIntegrityError,
    P2EmissionOperationRevisionV1,
    P2EmissionReceiptV1,
    ResearchProtocolRevisionV1,
    RevisionRecordV1,
    SearchRunRevisionV1,
    SourceCaptureRevisionV1,
    SourceIdentityRevisionV1,
    SourceRelationshipRevisionV1,
    SourceVersionIdentityRevisionV1,
    canonical_json_bytes,
    intent_sha256,
    methodology_sha256,
    record_sha256,
    _TRUSTED_CANONICAL_WRITER_CONTEXT,
)
from alphaquest.research.storage import StorageLayout, load_storage_layout
from alphaquest.research.literature.security import (
    assert_no_pnl_control_fields,
    assert_no_pnl_repository_reference,
)


T = TypeVar("T", bound=CanonicalRecordV1)
LITERATURE_RELATIVE = "research/literature"
LITERATURE_RUNTIME_RELATIVE = "run-store/literature"
_LOCK_RELATIVE = f"{LITERATURE_RUNTIME_RELATIVE}/literature.lock"
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_MANAGED_FIELDS = {
    "schema",
    "schema_name",
    "append_sequence",
    "previous_store_record_sha256",
    "recorded_at",
    "actor",
    "idempotency_key",
    "intent_sha256",
    "record_sha256",
}
_REVISION_MANAGED_FIELDS = {"record_id", "revision", "previous_revision_sha256"}
_SEARCH_IMMUTABLE_FIELDS = {
    "search_run_id",
    "protocol_id",
    "protocol_revision_sha256",
    "execution_lineage_id",
    "lane",
    "query",
    "query_kind",
    "parent_search_run_id",
    "adaptive_depth",
    "provider_id",
    "provider_attempt_ordinal",
}
_SEARCH_TERMINAL_FIELDS = {
    "status",
    "inspected_results",
    "capture_attempt_records",
    "bytes_retrieved",
    "elapsed_seconds",
    "provider_trace_completeness",
    "failure_reason",
    "saturation_claimed",
}
_CAPTURE_IMMUTABLE_FIELDS = {
    "capture_id",
    "source_version_id",
    "source_version_revision_sha256",
    "retrieval_locator",
    "captured_at",
    "access_basis",
    "local_retention_permission",
    "redistribution_permission",
    "external_model_processing_permission",
}
_CAPTURE_TERMINAL_FIELDS = {
    "status",
    "media_type",
    "content_sha256",
    "content_bytes",
    "extracted_representation_sha256",
    "extracted_bytes",
    "extractor_id",
    "extractor_version",
    "extractor_config_sha256",
    "failure_reason",
}
_P3_EXACT_REFERENCE_FIELDS = {
    "protocol_revision_sha256",
    "work_revision_sha256",
    "source_version_revision_sha256",
    "capture_revision_sha256",
    "dossier_revision_sha256",
    "terminal_capture_revision_sha256",
    "operation_revision_sha256",
    "claim_revision_sha256",
    "freeze_record_sha256",
    "prior_emission_receipt_sha256",
    "receipt_record_sha256",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _object_id(record_id: str) -> str:
    marker = record_id.rfind(".r")
    return record_id[:marker] if marker >= 0 else record_id


def _record_intent_material(record: CanonicalRecordV1) -> dict[str, Any]:
    material = record.model_dump(mode="json", by_alias=True, exclude=_MANAGED_FIELDS)
    if isinstance(record, RevisionRecordV1):
        for key in _REVISION_MANAGED_FIELDS:
            material.pop(key, None)
    return material


class LiteratureStore:
    """The only writer for version-controlled P3 canonical metadata."""

    def __init__(self, project_root: str | Path = ".", *, layout: StorageLayout | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = layout or load_storage_layout(self.project_root)
        expected_root = self.project_root / LITERATURE_RELATIVE
        expected_runtime = self.project_root / LITERATURE_RUNTIME_RELATIVE
        if self.layout.literature_root != expected_root:
            raise ValueError(f"literature_root must be exactly {LITERATURE_RELATIVE!r}")
        if self.layout.literature_runtime_root != expected_runtime:
            raise ValueError(f"literature_runtime_root must be exactly {LITERATURE_RUNTIME_RELATIVE!r}")

    @contextmanager
    def lock(self, *, exclusive: bool) -> Iterator[None]:
        with repository_file_lock(self.project_root, _LOCK_RELATIVE, exclusive=exclusive):
            yield

    def records(self) -> list[CanonicalRecordV1]:
        with self.lock(exclusive=False):
            return self._load_and_validate()

    def validate(self, *, verify_artifacts: bool = True) -> dict[str, Any]:
        with self.lock(exclusive=False):
            records = self._load_and_validate()
            missing: list[str] = []
            if verify_artifacts:
                for record in records:
                    if not isinstance(record, SourceCaptureRevisionV1):
                        continue
                    if record.status not in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
                        continue
                    for kind, digest in (
                        ("artifacts", record.content_sha256),
                        ("extracted", record.extracted_representation_sha256),
                    ):
                        try:
                            data = self._verify_artifact_unlocked(str(digest), kind=kind)
                            expected_size = record.content_bytes if kind == "artifacts" else record.extracted_bytes
                            if len(data) != expected_size:
                                raise LiteratureIntegrityError(
                                    f"{kind} artifact size mismatch: {digest}"
                                )
                        except (FileNotFoundError, LiteratureIntegrityError):
                            missing.append(f"{kind}:{digest}")
            if missing:
                raise LiteratureIntegrityError(
                    "referenced literature artifacts are unavailable or invalid: " + ", ".join(sorted(missing))
                )
            counts: dict[str, int] = {item.family: 0 for item in CANONICAL_RECORD_TYPES}
            for record in records:
                counts[type(record).family] += 1
            latest_operations: dict[str, P2EmissionOperationRevisionV1] = {}
            for record in records:
                if isinstance(record, P2EmissionOperationRevisionV1):
                    latest_operations[record.operation_id] = record
            unresolved = [
                {
                    "operation_id": operation.operation_id,
                    "affected_observation_id": impact.affected_observation_id,
                    "affected_observation_revision_sha256": impact.affected_observation_revision_sha256,
                    "dependent_entry_id": impact.dependent_entry_id,
                    "dependent_entry_revision_sha256": impact.dependent_entry_revision_sha256,
                    "dependent_entry_state": impact.dependent_entry_state,
                    "reason": impact.inability_reason,
                }
                for operation in latest_operations.values()
                for impact in operation.dependency_impacts
                if impact.impact_status == "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"
            ]
            return {
                "schema": "alphaquest.literature-validation/v1",
                "status": "PASS",
                "operational_status": (
                    "NEEDS_MANUAL_REVIEW" if unresolved else "CURRENT_RESEARCH_CLEAN"
                ),
                "operational_reason": (
                    "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY" if unresolved else None
                ),
                "unresolved_dependency_impacts": unresolved,
                "record_count": len(records),
                "family_count": len(CANONICAL_RECORD_TYPES),
                "counts": counts,
                "store_head_sha256": records[-1].record_sha256 if records else None,
                "artifacts_verified": verify_artifacts,
            }

    def get(self, record_id: str) -> CanonicalRecordV1:
        matches = [record for record in self.records() if record.record_id == record_id]
        if len(matches) != 1:
            raise KeyError(f"canonical P3 record not found: {record_id}")
        return matches[0]

    def latest(self, record_type: type[T], object_id: str) -> T:
        matches = [
            record for record in self.records() if isinstance(record, record_type) and _object_id(record.record_id) == object_id
        ]
        if not matches:
            raise KeyError(f"{record_type.family} object not found: {object_id}")
        return matches[-1]  # type: ignore[return-value]

    def append_protocol(
        self,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> ResearchProtocolRevisionV1:
        material = dict(payload)
        protocol_id = str(material["protocol_id"])
        previous = self._latest_optional(ResearchProtocolRevisionV1, protocol_id)
        if previous is not None and material.get("execution_lineage_id") != previous.execution_lineage_id:
            raise LiteratureConflictError("protocol identity cannot move to another execution lineage")
        material["revision"] = 1 if previous is None else previous.revision + 1
        material["previous_revision_sha256"] = previous.record_sha256 if previous else None
        material["record_id"] = f"{protocol_id}.r{material['revision']:06d}"
        computed = methodology_sha256(material)
        supplied = material.get("methodology_sha256")
        if supplied is not None and supplied != computed:
            raise LiteratureConflictError("methodology_sha256 does not match protocol methodology")
        material["methodology_sha256"] = computed
        lineage_id = str(material["execution_lineage_id"])
        started = [
            item
            for item in self.records()
            if isinstance(item, SearchRunRevisionV1)
            and item.execution_lineage_id == lineage_id
            and item.revision == 1
        ]
        if started:
            frozen_protocol = self._record_by_hash(started[0].protocol_revision_sha256, ResearchProtocolRevisionV1)
            if computed != frozen_protocol.methodology_sha256:
                raise LiteratureConflictError(
                    "search methodology is frozen after the first STARTED search; create a new execution lineage"
                )
        protocols = [
            item
            for item in self.records()
            if isinstance(item, ResearchProtocolRevisionV1)
            and item.execution_lineage_id == lineage_id
            and item.protocol_id != protocol_id
        ]
        if protocols and any(item.methodology_sha256 != computed for item in protocols):
            raise LiteratureConflictError("one execution lineage cannot carry competing protocol methodology")
        if material.get("lineage_kind") == "RESULT_INFORMED_EXTENSION":
            parent = str(material.get("parent_execution_lineage_id"))
            if parent == lineage_id or not any(
                isinstance(item, ResearchProtocolRevisionV1) and item.execution_lineage_id == parent
                for item in self.records()
            ):
                raise LiteratureConflictError("result-informed extension requires a distinct existing parent lineage")
        return self._append(ResearchProtocolRevisionV1, material, actor, idempotency_key, recorded_at)

    def start_search(
        self,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> SearchRunRevisionV1:
        material = dict(payload)
        search_id = str(material["search_run_id"])
        if self._latest_optional(SearchRunRevisionV1, search_id) is not None:
            raise LiteratureConflictError(f"search run already exists: {search_id}")
        protocol = self._record_by_hash(str(material["protocol_revision_sha256"]), ResearchProtocolRevisionV1)
        if protocol.protocol_id != material.get("protocol_id"):
            raise LiteratureConflictError("search protocol ID/hash mismatch")
        if protocol.execution_lineage_id != material.get("execution_lineage_id"):
            raise LiteratureConflictError("search execution lineage does not match protocol")
        lane = next((item for item in protocol.lanes if item.lane == material.get("lane")), None)
        if lane is None:
            raise LiteratureConflictError("search lane is not in the frozen protocol")
        existing = [
            item
            for item in self.records()
            if isinstance(item, SearchRunRevisionV1)
            and item.execution_lineage_id == protocol.execution_lineage_id
            and item.revision == 1
        ]
        lane_existing = [item for item in existing if item.lane == lane.lane]
        if material.get("provider_id") not in lane.provider_order:
            raise LiteratureConflictError("search provider is outside the frozen provider set")
        query_kind = material.get("query_kind")
        if query_kind == "INITIAL" and material.get("query") not in lane.required_initial_queries:
            raise LiteratureConflictError("initial query is not precommitted in the protocol")
        if query_kind == "ADAPTIVE":
            if int(material.get("adaptive_depth", 0)) > lane.adaptive_max_depth:
                raise LiteratureConflictError("adaptive query exceeds frozen depth budget")
            parent = self.latest(SearchRunRevisionV1, str(material.get("parent_search_run_id")))
            if parent.execution_lineage_id != protocol.execution_lineage_id or parent.lane != lane.lane:
                raise LiteratureConflictError("adaptive query parent is outside the frozen lane/lineage")
            if int(material.get("adaptive_depth", 0)) != parent.adaptive_depth + 1:
                raise LiteratureConflictError("adaptive depth must advance exactly one level from its parent")
        existing_queries = {item.query for item in lane_existing}
        if material.get("query") not in existing_queries and len(existing_queries) >= lane.maximum_queries:
            raise LiteratureConflictError("frozen lane query budget is exhausted")
        same_query_attempts = [item for item in lane_existing if item.query == material.get("query")]
        expected_ordinal = len(same_query_attempts) + 1
        supplied_ordinal = int(material.get("provider_attempt_ordinal", expected_ordinal))
        if supplied_ordinal != expected_ordinal:
            raise LiteratureConflictError("provider attempt ordinal must be gap-free for one query")
        if supplied_ordinal > len(lane.provider_order):
            raise LiteratureConflictError("provider attempt exceeds the frozen provider order")
        if material.get("provider_id") != lane.provider_order[supplied_ordinal - 1]:
            raise LiteratureConflictError("provider attempt does not follow the exact frozen provider order")
        material.update(
            {
                "revision": 1,
                "previous_revision_sha256": None,
                "record_id": f"{search_id}.r000001",
                "status": "STARTED",
                "results_inspected": 0,
                "capture_attempts": 0,
                "inspected_results": [],
                "capture_attempt_records": [],
                "bytes_retrieved": 0,
                "elapsed_seconds": 0,
                "result_set_sha256": None,
                "saturation_claimed": False,
                "provider_attempt_ordinal": supplied_ordinal,
                "failure_reason": None,
            }
        )
        return self._append(SearchRunRevisionV1, material, actor, idempotency_key, recorded_at)

    def finish_search(
        self,
        search_run_id: str,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> SearchRunRevisionV1:
        previous = self.latest(SearchRunRevisionV1, search_run_id)
        if previous.status != "STARTED":
            raise LiteratureConflictError("search run is already terminal")
        unexpected = set(payload) - _SEARCH_TERMINAL_FIELDS
        if unexpected:
            raise LiteratureConflictError(
                "finish_search accepts only terminal outcome fields: " + ", ".join(sorted(unexpected))
            )
        material = previous.model_dump(
            mode="json", by_alias=True, exclude=_MANAGED_FIELDS | {"revision", "previous_revision_sha256", "record_id"}
        )
        material.update(payload)
        if material.get("status") == "STARTED":
            raise LiteratureConflictError("finish_search requires a terminal status")
        inspected = list(material.get("inspected_results", []))
        capture_attempts = list(material.get("capture_attempt_records", []))
        material.update(
            {
                "record_id": f"{search_run_id}.r000002",
                "revision": 2,
                "previous_revision_sha256": previous.record_sha256,
                "results_inspected": len(inspected),
                "capture_attempts": len(capture_attempts),
                "result_set_sha256": hashlib.sha256(
                    canonical_json_bytes(inspected, trailing_lf=False)
                ).hexdigest(),
            }
        )
        candidate_material = {
            **material,
            "schema": SearchRunRevisionV1.schema_literal,
            "append_sequence": 1,
            "previous_store_record_sha256": None,
            "recorded_at": recorded_at or _now(),
            "actor": actor.model_dump(mode="json"),
            "idempotency_key": idempotency_key,
            "intent_sha256": "0" * 64,
        }
        candidate_material["record_sha256"] = record_sha256(candidate_material)
        candidate = SearchRunRevisionV1.model_validate_json(canonical_json_bytes(candidate_material))
        protocol = self._record_by_hash(candidate.protocol_revision_sha256, ResearchProtocolRevisionV1)
        lane = next(item for item in protocol.lanes if item.lane == candidate.lane)
        terminal = [
            item
            for item in self.records()
            if isinstance(item, SearchRunRevisionV1)
            and item.execution_lineage_id == candidate.execution_lineage_id
            and item.lane == candidate.lane
            and item.revision == 2
        ]
        if sum(item.results_inspected for item in terminal) + candidate.results_inspected > lane.maximum_results:
            raise LiteratureConflictError("terminal search would exceed frozen lane result budget")
        if sum(item.capture_attempts for item in terminal) + candidate.capture_attempts > lane.maximum_captures:
            raise LiteratureConflictError("terminal search would exceed frozen lane capture budget")
        if sum(item.bytes_retrieved for item in terminal) + candidate.bytes_retrieved > lane.maximum_bytes:
            raise LiteratureConflictError("terminal search would exceed frozen lane byte budget")
        if sum(item.elapsed_seconds for item in terminal) + candidate.elapsed_seconds > lane.maximum_elapsed_seconds:
            raise LiteratureConflictError("terminal search would exceed frozen lane elapsed-time budget")
        return self._append(SearchRunRevisionV1, material, actor, idempotency_key, recorded_at)

    def append_work(self, payload: Mapping[str, Any], **kwargs: Any) -> SourceIdentityRevisionV1:
        for locator in payload.get("locators", []):
            assert_no_pnl_repository_reference(str(locator))
        return self._append_revision(SourceIdentityRevisionV1, "work_id", payload, **kwargs)

    def append_source_version(self, payload: Mapping[str, Any], **kwargs: Any) -> SourceVersionIdentityRevisionV1:
        material = dict(payload)
        work = self._record_by_hash(str(material["work_revision_sha256"]), SourceIdentityRevisionV1)
        if work.work_id != material.get("work_id"):
            raise LiteratureConflictError("source version work ID/hash mismatch")
        previous = self._latest_optional(SourceVersionIdentityRevisionV1, str(material["source_version_id"]))
        if previous is not None and material.get("work_id") != previous.work_id:
            raise LiteratureConflictError("source-version identity cannot migrate to another work")
        return self._append_revision(SourceVersionIdentityRevisionV1, "source_version_id", material, **kwargs)

    def append_source_relationship(self, payload: Mapping[str, Any], **kwargs: Any) -> SourceRelationshipRevisionV1:
        for reference in payload.get("assertion_evidence_refs", []):
            self._record_by_hash_any(str(reference["record_sha256"]), str(reference["record_id"]))
        identity_types = {"WORK": SourceIdentityRevisionV1, "SOURCE_VERSION": SourceVersionIdentityRevisionV1}
        self.latest(identity_types[str(payload["subject_kind"])], str(payload["subject_id"]))
        self.latest(identity_types[str(payload["object_kind"])], str(payload["object_id"]))
        relationship_id = str(payload["relationship_id"])
        previous = self._latest_optional(SourceRelationshipRevisionV1, relationship_id)
        if previous is not None:
            for field in ("subject_kind", "subject_id", "predicate", "object_kind", "object_id"):
                if payload.get(field) != getattr(previous, field):
                    raise LiteratureConflictError("source relationship assertion cannot change inside one identity")
            if previous.status != "ACTIVE":
                raise LiteratureConflictError("retracted/superseded source relationship cannot be reactivated")
        return self._append_revision(SourceRelationshipRevisionV1, "relationship_id", payload, **kwargs)

    def append_capture(self, payload: Mapping[str, Any], **kwargs: Any) -> SourceCaptureRevisionV1:
        material = dict(payload)
        capture_id = str(material["capture_id"])
        previous = self._latest_optional(SourceCaptureRevisionV1, capture_id)
        if previous is not None:
            if previous.status != "STARTED":
                raise LiteratureConflictError("terminal capture is immutable; recapture requires a new capture_id")
            unexpected = set(material) - ({"capture_id"} | _CAPTURE_TERMINAL_FIELDS)
            if unexpected:
                raise LiteratureConflictError(
                    "capture completion accepts only terminal outcome fields: "
                    + ", ".join(sorted(unexpected))
                )
            terminal = {key: value for key, value in material.items() if key in _CAPTURE_TERMINAL_FIELDS}
            material = previous.model_dump(
                mode="json",
                by_alias=True,
                exclude=_MANAGED_FIELDS | {"revision", "previous_revision_sha256", "record_id"},
            )
            material.update(terminal)
            if material.get("status") == "STARTED":
                raise LiteratureConflictError("capture STARTED state cannot be appended twice")
        assert_no_pnl_repository_reference(str(material["retrieval_locator"]))
        version = self._record_by_hash(str(material["source_version_revision_sha256"]), SourceVersionIdentityRevisionV1)
        if version.source_version_id != material.get("source_version_id"):
            raise LiteratureConflictError("capture source-version ID/hash mismatch")
        if material.get("status") in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
            content = self.verify_artifact(str(material.get("content_sha256")), kind="artifacts")
            extracted = self.verify_artifact(str(material.get("extracted_representation_sha256")), kind="extracted")
            if len(content) != material.get("content_bytes") or len(extracted) != material.get("extracted_bytes"):
                raise LiteratureConflictError("capture artifact byte counts do not match stored artifacts")
        return self._append_revision(SourceCaptureRevisionV1, "capture_id", material, **kwargs)

    def append_claim(self, payload: Mapping[str, Any], **kwargs: Any) -> ClaimExtractionRevisionV1:
        material = dict(payload)
        work = self._record_by_hash(str(material["work_revision_sha256"]), SourceIdentityRevisionV1)
        version = self._record_by_hash(
            str(material["source_version_revision_sha256"]), SourceVersionIdentityRevisionV1
        )
        capture = self._record_by_hash(str(material["capture_revision_sha256"]), SourceCaptureRevisionV1)
        if work.work_id != material.get("work_id"):
            raise LiteratureConflictError("claim work ID/hash mismatch")
        if version.source_version_id != material.get("source_version_id"):
            raise LiteratureConflictError("claim source-version ID/hash mismatch")
        if version.work_id != work.work_id or version.work_revision_sha256 != work.record_sha256:
            raise LiteratureConflictError("claim work/source-version provenance chain is inconsistent")
        if capture.capture_id != material.get("capture_id"):
            raise LiteratureConflictError("claim capture ID/hash mismatch")
        if (
            capture.source_version_id != version.source_version_id
            or capture.source_version_revision_sha256 != version.record_sha256
        ):
            raise LiteratureConflictError("claim source-version/capture provenance chain is inconsistent")
        if capture.status not in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
            raise LiteratureConflictError("claim extraction requires captured full text or a genuine abstract")
        if capture.content_sha256 != material.get("content_sha256"):
            raise LiteratureConflictError("claim content hash does not match capture")
        if capture.extracted_representation_sha256 != material.get("extracted_representation_sha256"):
            raise LiteratureConflictError("claim extracted-text hash does not match capture")
        extracted = self.verify_artifact(str(capture.extracted_representation_sha256), kind="extracted")
        location = material["location"]
        start, end = int(location["byte_start"]), int(location["byte_end"])
        if end > len(extracted):
            raise LiteratureConflictError("claim location exceeds extracted representation")
        if hashlib.sha256(extracted[start:end]).hexdigest() != location["span_sha256"]:
            raise LiteratureConflictError("claim span hash does not match extracted representation")
        if material.get("statement_kind") == "SOURCE_QUOTE":
            try:
                span_text = extracted[start:end].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise LiteratureConflictError("SOURCE_QUOTE span is not valid UTF-8") from exc
            if material.get("statement") != span_text:
                raise LiteratureConflictError("SOURCE_QUOTE statement must exactly equal its bound byte span")
        previous = self._latest_optional(ClaimExtractionRevisionV1, str(material["claim_id"]))
        if previous is not None and material.get("reliability") == "WITHDRAWN_INVALID":
            if material.get("statement") != previous.statement:
                raise LiteratureConflictError("unsupported withdrawal cannot manufacture a replacement statement")
        return self._append_revision(ClaimExtractionRevisionV1, "claim_id", material, **kwargs)

    def append_evidence_relation(self, payload: Mapping[str, Any], **kwargs: Any) -> EvidenceRelationRevisionV1:
        for reference in payload["claim_refs"]:
            self._record_by_hash(str(reference["record_sha256"]), ClaimExtractionRevisionV1)
        previous = self._latest_optional(EvidenceRelationRevisionV1, str(payload["evidence_relation_id"]))
        if previous is not None and previous.status != "ACTIVE":
            raise LiteratureConflictError("retracted/superseded evidence relation cannot be reactivated")
        return self._append_revision(EvidenceRelationRevisionV1, "evidence_relation_id", payload, **kwargs)

    @staticmethod
    def _current_searches(
        records: list[CanonicalRecordV1], *, lineage_id: str, lane_name: str
    ) -> list[SearchRunRevisionV1]:
        latest: dict[str, SearchRunRevisionV1] = {}
        for record in records:
            if (
                isinstance(record, SearchRunRevisionV1)
                and record.execution_lineage_id == lineage_id
                and record.lane == lane_name
            ):
                latest[record.search_run_id] = record
        return sorted(latest.values(), key=lambda item: item.search_run_id)

    @staticmethod
    def _validate_lane_search_proof(lane: Any, searches: list[SearchRunRevisionV1]) -> bool:
        attempts_by_query: dict[str, list[SearchRunRevisionV1]] = {}
        for search in searches:
            attempts_by_query.setdefault(search.query, []).append(search)
        for attempts in attempts_by_query.values():
            ordered = sorted(attempts, key=lambda item: item.provider_attempt_ordinal)
            ordinals = [item.provider_attempt_ordinal for item in ordered]
            if ordinals != list(range(1, len(ordered) + 1)):
                raise LiteratureIntegrityError("provider attempts must be gap-free for each exact query")
            if len(ordered) > len(lane.provider_order):
                raise LiteratureIntegrityError("search attempts exceed the frozen provider order")
            if [item.provider_id for item in ordered] != list(lane.provider_order[: len(ordered)]):
                raise LiteratureIntegrityError("search attempts violate the exact frozen provider order")

        terminal = [item for item in searches if item.status != "STARTED"]
        if len(attempts_by_query) > lane.maximum_queries:
            raise LiteratureIntegrityError("search history exceeds the frozen distinct-query budget")
        if sum(item.results_inspected for item in terminal) > lane.maximum_results:
            raise LiteratureIntegrityError("search history exceeds the frozen result budget")
        if sum(item.capture_attempts for item in terminal) > lane.maximum_captures:
            raise LiteratureIntegrityError("search history exceeds the frozen capture budget")
        if sum(item.bytes_retrieved for item in terminal) > lane.maximum_bytes:
            raise LiteratureIntegrityError("search history exceeds the frozen byte budget")
        if sum(item.elapsed_seconds for item in terminal) > lane.maximum_elapsed_seconds:
            raise LiteratureIntegrityError("search history exceeds the frozen elapsed-time budget")

        inspected: list[Any] = []
        captures: list[Any] = []
        capture_ids: set[str] = set()
        for search in terminal:
            expected_provider_rank = list(lane.provider_order).index(search.provider_id) + 1
            if any(item.provider_rank != expected_provider_rank for item in search.inspected_results):
                raise LiteratureIntegrityError("inspected-result provider rank does not match frozen provider order")
            ranks = [item.result_rank for item in search.inspected_results]
            if ranks != list(range(1, len(ranks) + 1)):
                raise LiteratureIntegrityError("inspected-result ranks must be ordered and gap-free per provider attempt")
            inspected.extend(search.inspected_results)
            for attempt in search.capture_attempt_records:
                if attempt.capture_attempt_id in capture_ids:
                    raise LiteratureIntegrityError("capture-attempt identity is duplicated across the lane")
                capture_ids.add(attempt.capture_attempt_id)
                captures.append(attempt)
        ordered_results = sorted(
            inspected,
            key=lambda item: (item.provider_rank, item.result_rank, item.locator_sha256, item.result_identity_sha256),
        )
        if [item.selection_ordinal for item in captures] != list(range(1, len(captures) + 1)):
            raise LiteratureIntegrityError("capture selection ordinals must be lane-global, ordered, and gap-free")
        if [item.result_identity_sha256 for item in captures] != [
            item.result_identity_sha256 for item in ordered_results[: len(captures)]
        ]:
            raise LiteratureIntegrityError("capture attempts deviate from the frozen deterministic selection rule")

        successful = [item for item in terminal if item.status in {"SUCCEEDED", "PARTIAL"}]
        successful_initial = {item.query for item in successful if item.query_kind == "INITIAL"}
        distinct_results = {item.result_identity_sha256 for run in successful for item in run.inspected_results}
        distinct_capture_results = {
            item.result_identity_sha256 for run in successful for item in run.capture_attempt_records
        }
        per_query_results = {
            query: {
                item.result_identity_sha256
                for run in successful
                if run.query == query
                for item in run.inspected_results
            }
            for query in lane.required_initial_queries
        }
        satisfied = (
            set(lane.required_initial_queries).issubset(successful_initial)
            and len(successful) >= lane.minimum_provider_attempts
            and len(distinct_results) >= lane.minimum_distinct_results_inspected
            and all(
                len(per_query_results[query]) >= lane.minimum_results_inspected_per_query
                for query in lane.required_initial_queries
            )
            and len(distinct_capture_results) >= lane.minimum_capture_attempts
        )

        saturation_claims = [item for item in terminal if item.saturation_claimed]
        if saturation_claims:
            if lane.saturation is None or not lane.saturation.enabled:
                raise LiteratureIntegrityError("search claims saturation without a frozen saturation criterion")
            if not satisfied:
                raise LiteratureIntegrityError("saturation cannot be claimed before frozen minimum obligations are met")
            query_order: list[str] = []
            for item in sorted(terminal, key=lambda value: (value.append_sequence, value.search_run_id)):
                if item.query not in query_order:
                    query_order.append(item.query)
            if len(query_order) < lane.saturation.minimum_queries_before_check:
                raise LiteratureIntegrityError("saturation was claimed before the frozen query minimum")
            seen_work: set[str] = set()
            no_new_work = 0
            for query in query_order:
                works = {
                    result.work_identity_sha256
                    for run in terminal
                    if run.query == query
                    for result in run.inspected_results
                }
                new_work = works - seen_work
                no_new_work = 0 if new_work else no_new_work + 1
                seen_work.update(works)
            if no_new_work < lane.saturation.consecutive_queries_without_new_work:
                raise LiteratureIntegrityError("claimed saturation does not meet the frozen no-new-work criterion")
            final_search = max(terminal, key=lambda item: (item.append_sequence, item.search_run_id))
            if len(saturation_claims) != 1 or saturation_claims[0].search_run_id != final_search.search_run_id:
                raise LiteratureIntegrityError("only the final applicable search may bind lane saturation")
        return satisfied

    @classmethod
    def _derive_lane_completions(
        cls, protocol: ResearchProtocolRevisionV1, records: list[CanonicalRecordV1]
    ) -> list[dict[str, Any]]:
        completions: list[dict[str, Any]] = []
        for lane in protocol.lanes:
            searches = cls._current_searches(
                records, lineage_id=protocol.execution_lineage_id, lane_name=lane.lane
            )
            satisfied = cls._validate_lane_search_proof(lane, searches)
            terminal = all(item.status != "STARTED" for item in searches)
            provider_failure = any(
                item.status in {"FAILED", "ABANDONED_AFTER_CRASH"} for item in searches
            )
            if satisfied and terminal:
                obligation = "SATISFIED"
                gap_reason = None
            elif provider_failure:
                obligation = "UNSATISFIED_PROVIDER_FAILURE"
                gap_reason = "PROVIDER_FAILURE_OR_CRASH"
            else:
                obligation = "UNSATISFIED_RESOURCE_OR_SAFETY_LIMIT"
                gap_reason = "FROZEN_MINIMUM_NOT_MET"
            completions.append(
                {
                    "lane": lane.lane,
                    "execution_status": "TERMINAL" if terminal else "NONTERMINAL",
                    "obligation_status": obligation,
                    "search_run_refs": [
                        {"record_id": item.record_id, "record_sha256": item.record_sha256}
                        for item in searches
                    ],
                    "gap_reason": gap_reason,
                }
            )
        return completions

    def append_dossier(self, payload: Mapping[str, Any], **kwargs: Any) -> EdgeDossierRevisionV1:
        material = dict(payload)
        records = self.records()
        protocol = self._record_by_hash(str(material["protocol_revision_sha256"]), ResearchProtocolRevisionV1)
        if protocol.execution_lineage_id != material.get("execution_lineage_id"):
            raise LiteratureConflictError("dossier execution lineage does not match protocol")
        derived_completions = self._derive_lane_completions(protocol, records)
        if canonical_json_bytes(material.get("lane_completions"), trailing_lf=False) != canonical_json_bytes(
            derived_completions, trailing_lf=False
        ):
            raise LiteratureConflictError("dossier lane completion must exactly include all canonical lane searches")
        derived_completion_status = (
            "COMPLETE_WITHIN_DECLARED_BOUNDS"
            if all(item["obligation_status"] == "SATISFIED" for item in derived_completions)
            else "TERMINATED_WITH_DECLARED_GAPS"
        )
        if material.get("search_completion_status") != derived_completion_status:
            raise LiteratureConflictError("dossier completion status is not derived from exact lane evidence")
        claim_set: set[tuple[str, str]] = set()
        relationships = [item for item in records if isinstance(item, SourceRelationshipRevisionV1)]
        from alphaquest.research.literature.mapper import effective_claim_reliability

        for reference in material["claim_refs"]:
            claim = self._record_by_hash(str(reference["claim_revision_sha256"]), ClaimExtractionRevisionV1)
            if claim.claim_id != reference["claim_id"]:
                raise LiteratureConflictError("dossier claim ID/hash mismatch")
            identity = (claim.record_id, claim.record_sha256)
            if identity in claim_set:
                raise LiteratureConflictError("dossier claim references must be exactly ordered and unique")
            claim_set.add(identity)
            if (
                effective_claim_reliability(claim, relationships) == "SOURCE_RETRACTED"
                and reference["p2_role"] in {"MOTIVATING", "SUPPORTING"}
            ):
                raise LiteratureConflictError("actively retracted source evidence cannot remain current positive support")

        def require_dossier_claim(reference: Mapping[str, Any]) -> None:
            identity = (str(reference["record_id"]), str(reference["record_sha256"]))
            if identity not in claim_set:
                raise LiteratureConflictError("nested dossier basis claim is outside the exact dossier claim set")

        for statement in material["material_statements"]:
            for reference in statement["claim_refs"]:
                require_dossier_claim(reference)
        for reference in material["evidence_relation_refs"]:
            relation = self._record_by_hash(str(reference["record_sha256"]), EvidenceRelationRevisionV1)
            if relation.record_id != reference["record_id"]:
                raise LiteratureConflictError("dossier evidence-relation ID/hash mismatch")
            for claim_reference in relation.claim_refs:
                if (claim_reference.record_id, claim_reference.record_sha256) not in claim_set:
                    raise LiteratureConflictError("dossier evidence relation uses a claim outside the dossier")
        for descriptor in material["quality_descriptors"]:
            for reference in descriptor["basis_claims"]:
                require_dossier_claim(reference)
        for mapping in material["taxonomy_proposal"]["dimension_mappings"]:
            for reference in mapping["basis_claims"]:
                require_dossier_claim(reference)
        previous = self._latest_optional(EdgeDossierRevisionV1, str(material["dossier_id"]))
        if material.get("p2_entry_id") is not None:
            receipt = self._record_by_hash(
                str(material["prior_emission_receipt_sha256"]), P2EmissionReceiptV1
            )
            receipt_entry_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
            if receipt_entry_id != material["p2_entry_id"]:
                raise LiteratureConflictError("dossier P2 entry does not match its prior emission receipt")
            prior_freeze = self._record_by_hash(receipt.freeze_record_sha256, DossierFreezeV1)
            if prior_freeze.dossier_id != material["dossier_id"]:
                raise LiteratureConflictError("prior emission receipt belongs to another dossier")
        if previous is not None and previous.p2_entry_id is not None:
            if material.get("p2_entry_id") != previous.p2_entry_id:
                raise LiteratureConflictError("emitted dossier cannot change canonical P2 entry identity")
        return self._append_revision(EdgeDossierRevisionV1, "dossier_id", material, **kwargs)

    def append_codex_attempt(self, payload: Mapping[str, Any], **kwargs: Any) -> CodexTaskAttemptRevisionV1:
        return self._append_revision(CodexTaskAttemptRevisionV1, "attempt_id", payload, **kwargs)

    def freeze_dossier(
        self,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> DossierFreezeV1:
        supplied = dict(payload)
        allowed = {"freeze_id", "dossier_id", "dossier_revision_sha256"}
        unexpected = set(supplied) - allowed
        if unexpected:
            raise LiteratureConflictError(
                "freeze_dossier derives authoritative fields; unexpected caller fields: "
                + ", ".join(sorted(unexpected))
            )
        dossier = self._record_by_hash(str(supplied["dossier_revision_sha256"]), EdgeDossierRevisionV1)
        if dossier.dossier_id != supplied.get("dossier_id"):
            raise LiteratureConflictError("freeze dossier ID/hash mismatch")
        from alphaquest.research.literature.mapper import effective_claim_reliability

        current_records = self.records()
        relationships = [
            item for item in current_records if isinstance(item, SourceRelationshipRevisionV1)
        ]
        records_by_hash = {item.record_sha256: item for item in current_records}
        for reference in dossier.claim_refs:
            claim = records_by_hash.get(reference.claim_revision_sha256)
            if (
                isinstance(claim, ClaimExtractionRevisionV1)
                and effective_claim_reliability(claim, relationships) == "SOURCE_RETRACTED"
                and reference.p2_role in {"MOTIVATING", "SUPPORTING"}
            ):
                raise LiteratureConflictError("cannot freeze actively retracted positive evidence")
        material = self._dossier_freeze_material(dossier, freeze_id=str(supplied["freeze_id"]))
        return self._append(DossierFreezeV1, material, actor, idempotency_key, recorded_at)

    @staticmethod
    def _dossier_freeze_material(
        dossier: EdgeDossierRevisionV1, *, freeze_id: str
    ) -> dict[str, Any]:
        return {
            "record_id": freeze_id,
            "freeze_id": freeze_id,
            "dossier_id": dossier.dossier_id,
            "dossier_revision_sha256": dossier.record_sha256,
            "protocol_revision_sha256": dossier.protocol_revision_sha256,
            "execution_lineage_id": dossier.execution_lineage_id,
            "lane_completions": [item.model_dump(mode="json") for item in dossier.lane_completions],
            "claim_refs": [item.model_dump(mode="json") for item in dossier.claim_refs],
            "evidence_relation_refs": [
                item.model_dump(mode="json") for item in dossier.evidence_relation_refs
            ],
            "quality_descriptors": [
                item.model_dump(mode="json") for item in dossier.quality_descriptors
            ],
            "material_statements": [item.model_dump(mode="json") for item in dossier.material_statements],
            "search_completion_status": dossier.search_completion_status,
            "unsatisfied_lanes": [
                item.lane for item in dossier.lane_completions if item.obligation_status != "SATISFIED"
            ],
            "taxonomy_proposal": dossier.taxonomy_proposal.model_dump(mode="json"),
            "p2_entry_id": dossier.p2_entry_id,
            "prior_emission_receipt_sha256": dossier.prior_emission_receipt_sha256,
            "scientific_validation_status": dossier.scientific_validation_status,
            "hypothesis_status": dossier.hypothesis_status,
            "causal_admission_status": dossier.causal_admission_status,
        }

    def append_emission_operation(self, payload: Mapping[str, Any], **kwargs: Any) -> P2EmissionOperationRevisionV1:
        return self._append_revision(P2EmissionOperationRevisionV1, "operation_id", payload, **kwargs)

    def append_emission_receipt(
        self,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> P2EmissionReceiptV1:
        return self._append(P2EmissionReceiptV1, dict(payload), actor, idempotency_key, recorded_at)

    def put_artifact(self, data: bytes, *, kind: str) -> str:
        if kind not in {"artifacts", "extracted", "provider-traces", "codex-io"}:
            raise ValueError("unsupported literature artifact kind")
        digest = hashlib.sha256(data).hexdigest()
        relative = self._artifact_relative(digest, kind=kind)
        with self.lock(exclusive=True):
            existing = read_repository_file_optional(self.project_root, relative)
            if existing is not None:
                if existing != data:
                    raise LiteratureIntegrityError("content-addressed artifact collision")
                return digest
            exclusive_write_repository_file(self.project_root, relative, data)
        return digest

    def verify_artifact(self, digest: str, *, kind: str) -> bytes:
        with self.lock(exclusive=False):
            return self._verify_artifact_unlocked(digest, kind=kind)

    def _verify_artifact_unlocked(self, digest: str, *, kind: str) -> bytes:
        if not re_full_sha256(digest):
            raise ValueError("artifact digest must be lowercase SHA-256")
        data = read_repository_file(self.project_root, self._artifact_relative(digest, kind=kind))
        if hashlib.sha256(data).hexdigest() != digest:
            raise LiteratureIntegrityError(f"{kind} artifact hash mismatch: {digest}")
        return data

    def _artifact_relative(self, digest: str, *, kind: str) -> str:
        return f"{LITERATURE_RUNTIME_RELATIVE}/{kind}/sha256/{digest[:2]}/{digest}"

    def _append_revision(
        self,
        record_type: type[T],
        id_field: str,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> T:
        material = dict(payload)
        object_id = str(material[id_field])
        previous = self._latest_optional(record_type, object_id)
        material["revision"] = 1 if previous is None else int(previous.revision) + 1  # type: ignore[attr-defined]
        material["previous_revision_sha256"] = previous.record_sha256 if previous else None
        material["record_id"] = f"{object_id}.r{material['revision']:06d}"
        return self._append(record_type, material, actor, idempotency_key, recorded_at)

    def _append(
        self,
        record_type: type[T],
        payload: Mapping[str, Any],
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None,
    ) -> T:
        clean = {key: value for key, value in dict(payload).items() if key not in _MANAGED_FIELDS}
        assert_no_pnl_control_fields(clean)
        with self.lock(exclusive=True):
            records = self._load_and_validate()
            sequence = len(records) + 1
            material = {
                **clean,
                "schema": record_type.schema_literal,
                "append_sequence": sequence,
                "previous_store_record_sha256": records[-1].record_sha256 if records else None,
                "recorded_at": recorded_at or _now(),
                "actor": actor.model_dump(mode="json"),
                "idempotency_key": idempotency_key,
                "intent_sha256": "0" * 64,
            }
            material["record_sha256"] = record_sha256(material)
            try:
                provisional = record_type.model_validate_json(
                    canonical_json_bytes(material), context=_TRUSTED_CANONICAL_WRITER_CONTEXT
                )
            except ValidationError as exc:
                raise LiteratureConflictError(str(exc)) from exc
            intent = intent_sha256(_record_intent_material(provisional))
            for record in records:
                if record.idempotency_key != idempotency_key:
                    continue
                if record.intent_sha256 != intent or not isinstance(record, record_type):
                    raise LiteratureConflictError(f"idempotency key {idempotency_key!r} identifies different intent")
                return record  # type: ignore[return-value]
            material = provisional.model_dump(mode="json", by_alias=True)
            material["intent_sha256"] = intent
            material["record_sha256"] = record_sha256(material)
            try:
                record = record_type.model_validate_json(canonical_json_bytes(material))
            except ValidationError as exc:
                raise LiteratureConflictError(str(exc)) from exc
            if isinstance(record, RevisionRecordV1):
                self._validate_pending_revision(record, records)
            self._validate_cross_record_state([*records, record])
            relative = self._record_relative(record)
            exclusive_write_repository_file(self.project_root, relative, canonical_json_bytes(record))
            return record

    def _validate_pending_revision(
        self, record: RevisionRecordV1, records: list[CanonicalRecordV1]
    ) -> None:
        prior = [
            item
            for item in records
            if isinstance(item, type(record)) and _object_id(item.record_id) == _object_id(record.record_id)
        ]
        if record.revision != len(prior) + 1:
            raise LiteratureConflictError("revision sequence must be contiguous")
        if prior and record.previous_revision_sha256 != prior[-1].record_sha256:
            raise LiteratureConflictError("revision predecessor hash mismatch")
        if not prior and record.previous_revision_sha256 is not None:
            raise LiteratureConflictError("first revision cannot have a predecessor")
        if isinstance(record, P2EmissionOperationRevisionV1):
            self._validate_emission_transition(record, prior)

    def _validate_emission_transition(
        self,
        record: P2EmissionOperationRevisionV1,
        prior: list[CanonicalRecordV1],
    ) -> None:
        if not prior:
            if record.state not in {"PREPARED", "BLOCKED"}:
                raise LiteratureConflictError("first emission operation revision must be PREPARED or BLOCKED")
            if (
                record.observation_bindings
                or record.entry_binding is not None
                or record.dependency_entry_bindings
                or record.duplicate_snapshot is not None
                or record.receipt_record_sha256 is not None
            ):
                raise LiteratureConflictError(
                    "first emission operation revision cannot claim post-prepare bindings"
                )
            return
        previous = prior[-1]
        assert isinstance(previous, P2EmissionOperationRevisionV1)
        immutable = {
            "operation_id",
            "freeze_id",
            "freeze_record_sha256",
            "target_entry_id",
            "target_entry_revision_sha256",
            "target_entry_state",
            "target_entry_link_chain_sha256",
            "p2_snapshot_before_append_sequence",
            "emission_action",
            "reservations",
            "observation_plans",
            "entry_plan",
            "dependency_impacts",
            "search_completion_status",
            "unsatisfied_lanes",
            "prior_staled_decision_sha256",
            "operational_status",
        }
        for field in immutable:
            if getattr(record, field) != getattr(previous, field):
                raise LiteratureConflictError(f"prepared emission field is immutable: {field}")
        allowed = {
            "PREPARED": {"OBSERVATIONS_WRITTEN", "CONFLICT"},
            "OBSERVATIONS_WRITTEN": {"ENTRY_WRITTEN", "CONFLICT"},
            "ENTRY_WRITTEN": {"SNAPSHOT_BOUND", "CONFLICT"},
            "SNAPSHOT_BOUND": {"COMPLETED", "CONFLICT"},
            "BLOCKED": set(),
            "CONFLICT": set(),
            "COMPLETED": set(),
        }
        if record.state not in allowed[previous.state]:
            raise LiteratureConflictError(
                f"invalid emission state transition: {previous.state} -> {record.state}"
            )
        observation_written_states = {
            "OBSERVATIONS_WRITTEN",
            "ENTRY_WRITTEN",
            "SNAPSHOT_BOUND",
            "COMPLETED",
        }
        binding_state = previous.state if record.state == "CONFLICT" else record.state
        actual_observation_ids = [
            item.record_id.rsplit(".r", 1)[0] for item in record.observation_bindings
        ]
        expected_observation_ids = [item.observation_id for item in record.observation_plans]
        if binding_state in observation_written_states:
            if actual_observation_ids != expected_observation_ids:
                raise LiteratureConflictError(
                    "observation stage requires the exact ordered binding for every plan"
                )
        elif record.observation_bindings:
            raise LiteratureConflictError("observation bindings cannot exist before observation writing")
        if binding_state in {"ENTRY_WRITTEN", "SNAPSHOT_BOUND", "COMPLETED"} and record.entry_binding is None:
            raise LiteratureConflictError("entry-written stage requires an exact P2 entry binding")
        expected_dependency_entries = sorted({
            item.dependent_entry_id
            for item in record.dependency_impacts
            if item.impact_status == "PLANNED_MUTABLE_REVISION"
        })
        actual_dependency_entries = [
            item.record_id.rsplit(".r", 1)[0] for item in record.dependency_entry_bindings
        ]
        if binding_state in {"ENTRY_WRITTEN", "SNAPSHOT_BOUND", "COMPLETED"}:
            if actual_dependency_entries != expected_dependency_entries:
                raise LiteratureConflictError("entry-written stage lacks exact dependency correction bindings")
        elif record.dependency_entry_bindings:
            raise LiteratureConflictError("dependency bindings cannot exist before entry-written state")
        if binding_state in {"SNAPSHOT_BOUND", "COMPLETED"} and record.duplicate_snapshot is None:
            raise LiteratureConflictError("snapshot-bound stage requires an exact duplicate snapshot")

    def _record_relative(self, record: CanonicalRecordV1) -> str:
        family = type(record).family
        if isinstance(record, RevisionRecordV1):
            return f"{LITERATURE_RELATIVE}/{family}/{_object_id(record.record_id)}/revisions/{record.revision:06d}.json"
        return f"{LITERATURE_RELATIVE}/{family}/{record.record_id}.json"

    def _latest_optional(self, record_type: type[T], object_id: str) -> T | None:
        matches = [
            record
            for record in self.records()
            if isinstance(record, record_type) and _object_id(record.record_id) == object_id
        ]
        return matches[-1] if matches else None  # type: ignore[return-value]

    def _record_by_hash(self, digest: str, record_type: type[T]) -> T:
        matches = [record for record in self.records() if isinstance(record, record_type) and record.record_sha256 == digest]
        if len(matches) != 1:
            raise LiteratureConflictError(f"missing exact {record_type.family} record: {digest}")
        return matches[0]  # type: ignore[return-value]

    def _record_by_hash_any(self, digest: str, record_id: str) -> CanonicalRecordV1:
        matches = [record for record in self.records() if record.record_sha256 == digest and record.record_id == record_id]
        if len(matches) != 1:
            raise LiteratureConflictError(f"missing exact canonical P3 record reference: {record_id}@{digest}")
        return matches[0]

    def _lineage_has_started_search(self, lineage_id: str) -> bool:
        return any(
            isinstance(record, SearchRunRevisionV1)
            and record.execution_lineage_id == lineage_id
            and record.revision == 1
            for record in self.records()
        )

    def _load_and_validate(self) -> list[CanonicalRecordV1]:
        raw_files = _read_canonical_record_files(self.project_root)
        records: list[CanonicalRecordV1] = []
        seen_paths: set[str] = set()
        for relative, raw in raw_files:
            if relative in seen_paths:
                raise LiteratureIntegrityError(f"duplicate canonical path: {relative}")
            seen_paths.add(relative)
            try:
                decoded = json.loads(raw.decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise ValueError("canonical record must be a JSON object")
                record_type = SCHEMA_TYPES.get(decoded.get("schema"))
                if record_type is None:
                    raise ValueError(f"unknown P3 schema: {decoded.get('schema')!r}")
                record = record_type.model_validate_json(raw)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
                raise LiteratureIntegrityError(f"invalid canonical P3 record {relative}: {exc}") from exc
            if raw != canonical_json_bytes(record):
                raise LiteratureIntegrityError(f"noncanonical P3 record bytes: {relative}")
            if decoded.get("record_sha256") != record_sha256(decoded):
                raise LiteratureIntegrityError(f"persisted P3 record hash mismatch: {relative}")
            expected = self._record_relative(record)
            if relative != expected:
                raise LiteratureIntegrityError(f"record path/identity mismatch: {relative} != {expected}")
            records.append(record)
        records.sort(key=lambda item: item.append_sequence)
        seen_ids: set[str] = set()
        seen_idempotency: dict[str, tuple[str, str]] = {}
        previous_hash: str | None = None
        revisions: dict[tuple[type[CanonicalRecordV1], str], CanonicalRecordV1] = {}
        for expected_sequence, record in enumerate(records, start=1):
            if record.append_sequence != expected_sequence:
                raise LiteratureIntegrityError("global P3 append_sequence must be gap-free")
            if record.previous_store_record_sha256 != previous_hash:
                raise LiteratureIntegrityError("global P3 store hash chain is broken")
            if record.record_id in seen_ids:
                raise LiteratureIntegrityError(f"duplicate P3 record_id: {record.record_id}")
            seen_ids.add(record.record_id)
            if record.intent_sha256 != intent_sha256(_record_intent_material(record)):
                raise LiteratureIntegrityError("canonical record intent_sha256 is invalid")
            existing_intent = seen_idempotency.get(record.idempotency_key)
            current_intent = (record.intent_sha256, record.schema_name)
            if existing_intent is not None and existing_intent != current_intent:
                raise LiteratureIntegrityError("idempotency key identifies conflicting canonical intent")
            if existing_intent is not None:
                raise LiteratureIntegrityError("idempotency key appears in more than one canonical record")
            seen_idempotency[record.idempotency_key] = current_intent
            if isinstance(record, RevisionRecordV1):
                key = (type(record), _object_id(record.record_id))
                previous = revisions.get(key)
                if record.revision != (1 if previous is None else previous.revision + 1):  # type: ignore[attr-defined]
                    raise LiteratureIntegrityError("object revision chain is not contiguous")
                if record.previous_revision_sha256 != (previous.record_sha256 if previous else None):
                    raise LiteratureIntegrityError("object revision predecessor hash is broken")
                revisions[key] = record
            previous_hash = record.record_sha256
        self._validate_cross_record_state(records)
        return records

    def _validate_protocol_search_history(self, records: list[CanonicalRecordV1]) -> None:
        records_by_hash = {item.record_sha256: item for item in records}
        protocol_revisions: dict[str, list[ResearchProtocolRevisionV1]] = {}
        protocols_by_lineage: dict[str, list[ResearchProtocolRevisionV1]] = {}
        search_revisions: dict[str, list[SearchRunRevisionV1]] = {}
        for record in records:
            if isinstance(record, ResearchProtocolRevisionV1):
                protocol_revisions.setdefault(record.protocol_id, []).append(record)
                protocols_by_lineage.setdefault(record.execution_lineage_id, []).append(record)
            elif isinstance(record, SearchRunRevisionV1):
                search_revisions.setdefault(record.search_run_id, []).append(record)

        for history in protocol_revisions.values():
            lineage = history[0].execution_lineage_id
            if any(item.execution_lineage_id != lineage for item in history):
                raise LiteratureIntegrityError("persisted protocol revision migrated execution lineage")
        for protocol in [item for history in protocol_revisions.values() for item in history]:
            if protocol.lineage_kind != "RESULT_INFORMED_EXTENSION":
                continue
            parent = protocol.parent_execution_lineage_id
            if (
                parent == protocol.execution_lineage_id
                or parent not in protocols_by_lineage
            ):
                raise LiteratureIntegrityError(
                    "persisted result-informed extension lacks a distinct existing parent lineage"
                )
        for lineage, history in protocols_by_lineage.items():
            started = [
                item
                for item in records
                if isinstance(item, SearchRunRevisionV1)
                and item.execution_lineage_id == lineage
                and item.revision == 1
            ]
            if started:
                first_started = min(started, key=lambda item: item.append_sequence)
                frozen = records_by_hash.get(first_started.protocol_revision_sha256)
                if not isinstance(frozen, ResearchProtocolRevisionV1):
                    raise LiteratureIntegrityError("STARTED search lacks exact protocol revision")
                if any(
                    item.append_sequence > first_started.append_sequence
                    and item.methodology_sha256 != frozen.methodology_sha256
                    for item in history
                ):
                    raise LiteratureIntegrityError("non-administrative protocol field changed after STARTED")
                for item in started:
                    exact_protocol = records_by_hash.get(item.protocol_revision_sha256)
                    if (
                        not isinstance(exact_protocol, ResearchProtocolRevisionV1)
                        or exact_protocol.methodology_sha256 != frozen.methodology_sha256
                    ):
                        raise LiteratureIntegrityError(
                            "search started under a competing execution contract in one lineage"
                        )

        for search_id, history in search_revisions.items():
            if len(history) not in {1, 2} or history[0].revision != 1 or history[0].status != "STARTED":
                raise LiteratureIntegrityError(f"search history must begin with exactly one STARTED revision: {search_id}")
            if len(history) == 2:
                started, terminal = history
                if terminal.revision != 2 or terminal.status == "STARTED":
                    raise LiteratureIntegrityError("search revision 2 must be terminal")
                for field in _SEARCH_IMMUTABLE_FIELDS:
                    if getattr(terminal, field) != getattr(started, field):
                        raise LiteratureIntegrityError(f"persisted search identity changed: {field}")
            current = history[-1]
            protocol = records_by_hash.get(current.protocol_revision_sha256)
            if not isinstance(protocol, ResearchProtocolRevisionV1):
                raise LiteratureIntegrityError("search has no exact protocol revision")
            if (
                current.protocol_id != protocol.protocol_id
                or current.execution_lineage_id != protocol.execution_lineage_id
                or current.lane not in {item.lane for item in protocol.lanes}
            ):
                raise LiteratureIntegrityError("search identity does not match exact frozen protocol")

        for lineage, history in protocols_by_lineage.items():
            protocol = history[0]
            for lane in protocol.lanes:
                searches = self._current_searches(records, lineage_id=lineage, lane_name=lane.lane)
                self._validate_lane_search_proof(lane, searches)

    def _validate_source_provenance_history(self, records: list[CanonicalRecordV1]) -> None:
        records_by_hash = {item.record_sha256: item for item in records}
        versions: dict[str, list[SourceVersionIdentityRevisionV1]] = {}
        captures: dict[str, list[SourceCaptureRevisionV1]] = {}
        relationships: dict[str, list[SourceRelationshipRevisionV1]] = {}
        for record in records:
            if isinstance(record, SourceVersionIdentityRevisionV1):
                versions.setdefault(record.source_version_id, []).append(record)
                work = records_by_hash.get(record.work_revision_sha256)
                if not isinstance(work, SourceIdentityRevisionV1) or work.work_id != record.work_id:
                    raise LiteratureIntegrityError("source version has an invalid exact work binding")
            elif isinstance(record, SourceCaptureRevisionV1):
                captures.setdefault(record.capture_id, []).append(record)
                version = records_by_hash.get(record.source_version_revision_sha256)
                if (
                    not isinstance(version, SourceVersionIdentityRevisionV1)
                    or version.source_version_id != record.source_version_id
                ):
                    raise LiteratureIntegrityError("capture has an invalid exact source-version binding")
            elif isinstance(record, SourceRelationshipRevisionV1):
                relationships.setdefault(record.relationship_id, []).append(record)
            elif isinstance(record, ClaimExtractionRevisionV1):
                work = records_by_hash.get(record.work_revision_sha256)
                version = records_by_hash.get(record.source_version_revision_sha256)
                capture = records_by_hash.get(record.capture_revision_sha256)
                if not isinstance(work, SourceIdentityRevisionV1) or work.work_id != record.work_id:
                    raise LiteratureIntegrityError("claim has an invalid exact work binding")
                if (
                    not isinstance(version, SourceVersionIdentityRevisionV1)
                    or version.source_version_id != record.source_version_id
                    or version.work_id != work.work_id
                    or version.work_revision_sha256 != work.record_sha256
                ):
                    raise LiteratureIntegrityError("claim work-to-version provenance is inconsistent")
                if (
                    not isinstance(capture, SourceCaptureRevisionV1)
                    or capture.capture_id != record.capture_id
                    or capture.source_version_id != version.source_version_id
                    or capture.source_version_revision_sha256 != version.record_sha256
                    or capture.content_sha256 != record.content_sha256
                    or capture.extracted_representation_sha256
                    != record.extracted_representation_sha256
                ):
                    raise LiteratureIntegrityError("claim version-to-capture/hash provenance is inconsistent")
        for history in versions.values():
            if any(item.work_id != history[0].work_id for item in history):
                raise LiteratureIntegrityError("persisted source version migrated to another work")
        for history in captures.values():
            first = history[0]
            for later in history[1:]:
                for field in _CAPTURE_IMMUTABLE_FIELDS:
                    if getattr(later, field) != getattr(first, field):
                        raise LiteratureIntegrityError(f"persisted capture identity changed: {field}")
        for history in relationships.values():
            first = history[0]
            for later in history[1:]:
                for field in ("subject_kind", "subject_id", "predicate", "object_kind", "object_id"):
                    if getattr(later, field) != getattr(first, field):
                        raise LiteratureIntegrityError(f"persisted source relationship identity changed: {field}")

    def _validate_dossier_history(self, records: list[CanonicalRecordV1]) -> None:
        records_by_hash = {item.record_sha256: item for item in records}
        from alphaquest.research.literature.mapper import effective_claim_reliability

        for record in records:
            if isinstance(record, EdgeDossierRevisionV1):
                protocol = records_by_hash.get(record.protocol_revision_sha256)
                if not isinstance(protocol, ResearchProtocolRevisionV1):
                    raise LiteratureIntegrityError("dossier has no exact protocol revision")
                prior_records = [item for item in records if item.append_sequence < record.append_sequence]
                expected_completions = self._derive_lane_completions(protocol, prior_records)
                actual_completions = [item.model_dump(mode="json") for item in record.lane_completions]
                if actual_completions != expected_completions:
                    raise LiteratureIntegrityError("persisted dossier omits or alters canonical lane searches")
                expected_status = (
                    "COMPLETE_WITHIN_DECLARED_BOUNDS"
                    if all(item["obligation_status"] == "SATISFIED" for item in expected_completions)
                    else "TERMINATED_WITH_DECLARED_GAPS"
                )
                if record.search_completion_status != expected_status:
                    raise LiteratureIntegrityError("persisted dossier completion status is not derived")
                claim_set = {
                    (f"{item.claim_id}.r{records_by_hash[item.claim_revision_sha256].revision:06d}", item.claim_revision_sha256)
                    for item in record.claim_refs
                    if isinstance(records_by_hash.get(item.claim_revision_sha256), ClaimExtractionRevisionV1)
                }
                if len(claim_set) != len(record.claim_refs):
                    raise LiteratureIntegrityError("dossier has duplicate or unresolved exact claim references")
                relationships = [
                    item
                    for item in prior_records
                    if isinstance(item, SourceRelationshipRevisionV1)
                ]
                for reference in record.claim_refs:
                    claim = records_by_hash.get(reference.claim_revision_sha256)
                    if not isinstance(claim, ClaimExtractionRevisionV1) or claim.claim_id != reference.claim_id:
                        raise LiteratureIntegrityError("dossier claim identity/hash mismatch")
                    if (
                        effective_claim_reliability(claim, relationships) == "SOURCE_RETRACTED"
                        and reference.p2_role in {"MOTIVATING", "SUPPORTING"}
                    ):
                        raise LiteratureIntegrityError("retracted source remains positive in persisted dossier")
                nested_refs = [
                    reference
                    for descriptor in record.quality_descriptors
                    for reference in descriptor.basis_claims
                ] + [
                    reference
                    for statement in record.material_statements
                    for reference in statement.claim_refs
                ] + [
                    reference
                    for mapping in record.taxonomy_proposal.dimension_mappings
                    for reference in mapping.basis_claims
                ]
                if any((item.record_id, item.record_sha256) not in claim_set for item in nested_refs):
                    raise LiteratureIntegrityError("nested dossier basis claim is outside exact claim set")
            elif isinstance(record, DossierFreezeV1):
                dossier = records_by_hash.get(record.dossier_revision_sha256)
                if not isinstance(dossier, EdgeDossierRevisionV1) or dossier.dossier_id != record.dossier_id:
                    raise LiteratureIntegrityError("dossier freeze has no exact dossier revision")
                expected = self._dossier_freeze_material(dossier, freeze_id=record.freeze_id)
                actual = record.model_dump(mode="json", by_alias=True, exclude=_MANAGED_FIELDS)
                if actual != expected:
                    raise LiteratureIntegrityError("dossier freeze is not the exact deterministic dossier derivation")
                relationships = [
                    item
                    for item in records
                    if isinstance(item, SourceRelationshipRevisionV1)
                    and item.append_sequence < record.append_sequence
                ]
                for reference in dossier.claim_refs:
                    claim = records_by_hash.get(reference.claim_revision_sha256)
                    if (
                        isinstance(claim, ClaimExtractionRevisionV1)
                        and effective_claim_reliability(claim, relationships) == "SOURCE_RETRACTED"
                        and reference.p2_role in {"MOTIVATING", "SUPPORTING"}
                    ):
                        raise LiteratureIntegrityError("freeze retained retracted evidence as current support")

    def _validate_cross_record_state(self, records: list[CanonicalRecordV1]) -> None:
        self._validate_protocol_search_history(records)
        self._validate_source_provenance_history(records)
        self._validate_dossier_history(records)
        hashes = {record.record_sha256 for record in records}
        records_by_hash = {record.record_sha256: record for record in records}
        operation_histories: dict[str, list[P2EmissionOperationRevisionV1]] = {}
        for record in records:
            if isinstance(record, P2EmissionOperationRevisionV1):
                operation_histories.setdefault(record.operation_id, []).append(record)
        for history in operation_histories.values():
            for index, record in enumerate(history):
                try:
                    self._validate_emission_transition(record, list(history[:index]))
                except LiteratureConflictError as exc:
                    raise LiteratureIntegrityError(
                        f"persisted emission transition is invalid: {exc}"
                    ) from exc

        def require_reference(reference: Any, expected: type[CanonicalRecordV1] | None = None) -> CanonicalRecordV1:
            target = records_by_hash.get(reference.record_sha256)
            if target is None or target.record_id != reference.record_id:
                raise LiteratureIntegrityError("unresolved exact canonical P3 record reference")
            if expected is not None and not isinstance(target, expected):
                raise LiteratureIntegrityError("canonical P3 reference has the wrong record family")
            return target

        for record in records:
            dumped = record.model_dump(mode="json")
            for key, value in _walk_key_values(dumped):
                if key in _P3_EXACT_REFERENCE_FIELDS:
                    if value is not None and value not in hashes:
                        raise LiteratureIntegrityError(f"unresolved exact P3 revision reference: {key}={value}")
            if isinstance(record, SourceRelationshipRevisionV1):
                identity_type = SourceIdentityRevisionV1 if record.subject_kind == "WORK" else SourceVersionIdentityRevisionV1
                object_type = SourceIdentityRevisionV1 if record.object_kind == "WORK" else SourceVersionIdentityRevisionV1
                if not any(
                    isinstance(item, identity_type) and _object_id(item.record_id) == record.subject_id
                    for item in records
                ) or not any(
                    isinstance(item, object_type) and _object_id(item.record_id) == record.object_id
                    for item in records
                ):
                    raise LiteratureIntegrityError("source relationship references an unknown canonical identity")
                for reference in record.assertion_evidence_refs:
                    require_reference(reference)
            elif isinstance(record, ClaimExtractionRevisionV1):
                for reference in record.conflict_refs:
                    require_reference(reference)
            elif isinstance(record, EvidenceRelationRevisionV1):
                for reference in record.claim_refs:
                    require_reference(reference, ClaimExtractionRevisionV1)
            elif isinstance(record, EdgeDossierRevisionV1):
                for completion in record.lane_completions:
                    for reference in completion.search_run_refs:
                        require_reference(reference, SearchRunRevisionV1)
                for reference in record.evidence_relation_refs:
                    require_reference(reference, EvidenceRelationRevisionV1)
                for descriptor in record.quality_descriptors:
                    for reference in descriptor.basis_claims:
                        require_reference(reference, ClaimExtractionRevisionV1)
                for statement in record.material_statements:
                    for reference in statement.claim_refs:
                        require_reference(reference, ClaimExtractionRevisionV1)
                for mapping in record.taxonomy_proposal.dimension_mappings:
                    for reference in mapping.basis_claims:
                        require_reference(reference, ClaimExtractionRevisionV1)
            elif isinstance(record, DossierFreezeV1):
                for reference in record.claim_refs:
                    claim = records_by_hash.get(reference.claim_revision_sha256)
                    if not isinstance(claim, ClaimExtractionRevisionV1) or claim.claim_id != reference.claim_id:
                        raise LiteratureIntegrityError("freeze claim identity/hash mismatch")
                for reference in record.evidence_relation_refs:
                    require_reference(reference, EvidenceRelationRevisionV1)
            elif isinstance(record, CodexTaskAttemptRevisionV1):
                for reference in record.referenced_records:
                    require_reference(reference)
        reservations: dict[str, tuple[Any, ...]] = {}
        for record in records:
            if not isinstance(record, P2EmissionOperationRevisionV1) or record.revision != 1:
                continue
            self._validate_prepared_emission(record, records, records_by_hash)
            for item in record.reservations:
                identity = (
                    item.p2_source_id,
                    item.source_kind,
                    item.canonical_locator,
                    item.capture_id,
                    item.terminal_capture_revision_sha256,
                    item.content_sha256,
                    item.extracted_representation_sha256,
                    item.evidence_time.model_dump(mode="json"),
                    item.relationship_state_sha256,
                    item.reservation_operation_id,
                )
                previous = reservations.get(item.canonical_source_version_id)
                if previous is not None and previous != identity:
                    raise LiteratureIntegrityError(
                        "one canonical source version has conflicting P2 evidence reservations"
                    )
                if previous is None and item.reservation_operation_id != record.operation_id:
                    raise LiteratureIntegrityError(
                        "first P2 evidence reservation must be owned by its PREPARED operation"
                    )
                reservations[item.canonical_source_version_id] = identity
        for record in records:
            if not isinstance(record, P2EmissionReceiptV1):
                continue
            operation = records_by_hash.get(record.operation_revision_sha256)
            if not isinstance(operation, P2EmissionOperationRevisionV1) or operation.state != "SNAPSHOT_BOUND":
                raise LiteratureIntegrityError("emission receipt must bind an exact SNAPSHOT_BOUND operation")
            for field in (
                "operation_id",
                "freeze_id",
                "freeze_record_sha256",
                "reservations",
                "observation_bindings",
                "entry_binding",
                "duplicate_snapshot",
                "dependency_impacts",
                "dependency_entry_bindings",
                "prior_staled_decision_sha256",
                "search_completion_status",
                "unsatisfied_lanes",
                "operational_status",
            ):
                if getattr(record, field) != getattr(operation, field):
                    raise LiteratureIntegrityError(f"emission receipt does not repeat operation field: {field}")

    def _validate_prepared_emission(
        self,
        operation: P2EmissionOperationRevisionV1,
        records: list[CanonicalRecordV1],
        records_by_hash: dict[str, CanonicalRecordV1],
    ) -> None:
        from alphaquest.research.edge_backlog import EdgeBacklogStore
        from alphaquest.research.literature.emission import (
            _dependency_impacts,
            _hypothesis_link_at_prefix,
            _with_new_dossier_observations,
        )
        from alphaquest.research.literature.mapper import (
            canonical_source_version_resolution,
            effective_claim_reliability,
            map_claim_to_observation,
            map_dossier_entry,
            reserve_p2_evidence,
        )

        freeze = records_by_hash.get(operation.freeze_record_sha256)
        if not isinstance(freeze, DossierFreezeV1) or freeze.freeze_id != operation.freeze_id:
            raise LiteratureIntegrityError("prepared emission freeze identity/hash mismatch")
        dossier = records_by_hash.get(freeze.dossier_revision_sha256)
        if not isinstance(dossier, EdgeDossierRevisionV1):
            raise LiteratureIntegrityError("prepared emission freeze lacks its exact dossier")
        if operation.search_completion_status != dossier.search_completion_status:
            raise LiteratureIntegrityError("prepared operation altered dossier search completion status")
        expected_unsatisfied = [
            item.lane for item in dossier.lane_completions if item.obligation_status != "SATISFIED"
        ]
        if operation.unsatisfied_lanes != expected_unsatisfied:
            raise LiteratureIntegrityError("prepared operation altered exact dossier lane gaps")
        relationships = [
            item
            for item in records
            if isinstance(item, SourceRelationshipRevisionV1)
            and item.append_sequence < operation.append_sequence
        ]
        earlier_reservations: dict[str, Any] = {}
        for record in records:
            if (
                isinstance(record, P2EmissionOperationRevisionV1)
                and record.revision == 1
                and record.append_sequence < operation.append_sequence
            ):
                for reservation in record.reservations:
                    earlier_reservations.setdefault(
                        reservation.canonical_source_version_id, reservation
                    )
        backlog = EdgeBacklogStore(self.project_root)
        resolved_claims = []
        for reference in dossier.claim_refs:
            claim = records_by_hash.get(reference.claim_revision_sha256)
            if not isinstance(claim, ClaimExtractionRevisionV1) or claim.claim_id != reference.claim_id:
                raise LiteratureIntegrityError("prepared plan dossier claim identity/hash mismatch")
            capture = records_by_hash.get(claim.capture_revision_sha256)
            version = records_by_hash.get(claim.source_version_revision_sha256)
            work = records_by_hash.get(claim.work_revision_sha256)
            if not isinstance(capture, SourceCaptureRevisionV1):
                raise LiteratureIntegrityError("prepared claim lacks exact capture")
            if not isinstance(version, SourceVersionIdentityRevisionV1):
                raise LiteratureIntegrityError("prepared claim lacks exact source version")
            if not isinstance(work, SourceIdentityRevisionV1):
                raise LiteratureIntegrityError("prepared claim lacks exact work")
            canonical_id, _state_hash, component = canonical_source_version_resolution(
                version.source_version_id, relationships
            )
            resolved_claims.append(
                (
                    canonical_id,
                    version.source_version_id != canonical_id,
                    version.source_version_id,
                    capture.capture_id,
                    claim.claim_id,
                    reference,
                    claim,
                    capture,
                    version,
                    work,
                    component,
                )
            )
        expected_reservations: dict[str, Any] = {}
        expected_plans = []
        for (
            canonical_id,
            _noncanonical,
            _version_id,
            _capture_id,
            _claim_id,
            reference,
            claim,
            capture,
            version,
            work,
            component,
        ) in sorted(resolved_claims, key=lambda item: item[:5]):
            candidates = [
                item
                for key, item in earlier_reservations.items()
                if key == canonical_id or key in component
            ]
            if len(candidates) > 1:
                raise LiteratureIntegrityError("relationship state merges incompatible prior reservations")
            existing = expected_reservations.get(canonical_id) or next(iter(candidates), None)
            reservation = reserve_p2_evidence(
                operation_id=operation.operation_id,
                work=work,
                version=version,
                capture=capture,
                relationships=relationships,
                existing=existing,
            )
            expected_reservations[canonical_id] = reservation
            try:
                prior_observation = backlog.latest_observation_at_prefix(
                    f"obs.p3.{hashlib.sha256(f'alphaquest-p3-claim|{claim.claim_id}'.encode()).hexdigest()[:32]}",
                    operation.p2_snapshot_before_append_sequence,
                )
            except FileNotFoundError:
                prior_observation = None
            expected_plans.append(
                map_claim_to_observation(
                    claim=claim,
                    role=reference.p2_role,
                    reservation=reservation,
                    prior_observation=prior_observation,
                    effective_reliability=effective_claim_reliability(claim, relationships),
                )
            )
        if list(operation.reservations) != list(expected_reservations.values()):
            raise LiteratureIntegrityError("prepared reservations are not the complete exact dossier derivation")
        if list(operation.observation_plans) != expected_plans:
            raise LiteratureIntegrityError("prepared observation plans are not the complete exact dossier derivation")

        if operation.target_entry_id is None:
            expected_action = "CREATE_NEW_ENTRY"
            expected_target_sha = expected_target_state = expected_link_chain = expected_stale = None
            target_entry = None
        else:
            try:
                target_entry = backlog.latest_entry_at_prefix(
                    operation.target_entry_id, operation.p2_snapshot_before_append_sequence
                )
            except FileNotFoundError as exc:
                raise LiteratureIntegrityError("prepared target entry did not exist at its P2 prefix") from exc
            expected_target_sha = target_entry.record_sha256
            expected_target_state = backlog.entry_state_at_prefix(
                target_entry.entry_id, operation.p2_snapshot_before_append_sequence
            )
            expected_link_chain = backlog.entry_link_chain_sha256_at_prefix(
                target_entry.entry_id, operation.p2_snapshot_before_append_sequence
            )
            bound = dossier.p2_entry_id == target_entry.entry_id
            has_hypothesis = _hypothesis_link_at_prefix(
                backlog, target_entry.entry_id, operation.p2_snapshot_before_append_sequence
            )
            if expected_target_state == "SUSPENDED" or (
                bound and (has_hypothesis or expected_target_state in {"REJECTED", "DUPLICATE"})
            ):
                expected_action = "BLOCKED"
            elif has_hypothesis or expected_target_state in {"REJECTED", "DUPLICATE"}:
                expected_action = "CREATE_NEW_ENTRY"
            else:
                expected_action = "REVISE_SAME_ENTRY"
            decisions = [
                item
                for item in backlog.decisions(target_entry.entry_id)
                if item.append_sequence < operation.p2_snapshot_before_append_sequence
            ]
            expected_stale = (
                decisions[-1].record_sha256
                if decisions
                and expected_target_state != "UNREVIEWED"
                and expected_action == "REVISE_SAME_ENTRY"
                else None
            )
        if (
            operation.emission_action != expected_action
            or operation.target_entry_revision_sha256 != expected_target_sha
            or operation.target_entry_state != expected_target_state
            or operation.target_entry_link_chain_sha256 != expected_link_chain
            or operation.prior_staled_decision_sha256 != expected_stale
        ):
            raise LiteratureIntegrityError("prepared target action is not the exact P2 prefix derivation")

        expected_entry_plan = map_dossier_entry(dossier, expected_plans)
        if expected_action == "REVISE_SAME_ENTRY" and target_entry is not None:
            preserved = [
                {
                    "observation_id": item.observation_id,
                    "role": "CONTRADICTING",
                    "frozen_revision_sha256": item.observation_revision_sha256,
                }
                for item in target_entry.observation_refs
                if item.role == "CONTRADICTING"
            ]
            expected_entry_plan = expected_entry_plan.model_copy(
                update={
                    "observation_roles": [
                        *expected_entry_plan.observation_roles,
                        *[type(expected_entry_plan.observation_roles[0]).model_validate(item) for item in preserved],
                    ]
                }
            )
        expected_impacts = _dependency_impacts(
            backlog,
            expected_plans,
            before_append_sequence=operation.p2_snapshot_before_append_sequence,
        )
        if expected_action == "REVISE_SAME_ENTRY" and target_entry is not None:
            target_impact = next(
                (
                    item
                    for item in expected_impacts
                    if item.dependent_entry_id == target_entry.entry_id
                    and item.impact_status == "PLANNED_MUTABLE_REVISION"
                ),
                None,
            )
            if target_impact is not None:
                assert target_impact.entry_plan is not None
                expected_entry_plan = _with_new_dossier_observations(
                    target_impact.entry_plan, expected_plans
                )
        if operation.entry_plan != expected_entry_plan:
            raise LiteratureIntegrityError("prepared entry plan is not the exact dossier/P2 derivation")
        if list(operation.dependency_impacts) != expected_impacts:
            raise LiteratureIntegrityError("prepared reverse-dependency snapshot is incomplete or altered")
        expected_operational = (
            "NEEDS_MANUAL_REVIEW"
            if any(
                item.impact_status == "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"
                for item in expected_impacts
            )
            else "CLEAN"
        )
        if operation.operational_status != expected_operational:
            raise LiteratureIntegrityError("prepared operation hides unresolved dependency impact")


def _walk_key_values(value: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk_key_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_key_values(child)


def _read_canonical_record_files(project_root: Path) -> list[tuple[str, bytes]]:
    output: list[tuple[str, bytes]] = []
    allowed_families = {item.family for item in CANONICAL_RECORD_TYPES}
    try:
        with repository_directory_fd(project_root, LITERATURE_RELATIVE, allow_missing=True) as root_fd:
            if root_fd is None:
                return output
            for name in sorted(os.listdir(root_fd)):
                metadata = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if name == "README.md":
                    if not stat.S_ISREG(metadata.st_mode):
                        raise LiteratureIntegrityError("literature README must be a regular file")
                    continue
                if name not in allowed_families or not stat.S_ISDIR(metadata.st_mode):
                    raise LiteratureIntegrityError(f"unexpected canonical literature component: {name}")
                family_fd = os.open(name, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC, dir_fd=root_fd)
                try:
                    _read_tree(family_fd, f"{LITERATURE_RELATIVE}/{name}", output)
                finally:
                    os.close(family_fd)
    except OSError as exc:
        raise LiteratureIntegrityError(f"unsafe canonical literature topology: {exc}") from exc
    return output


def _read_tree(directory_fd: int, relative: str, output: list[tuple[str, bytes]]) -> None:
    for name in sorted(os.listdir(directory_fd)):
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        child_relative = f"{relative}/{name}"
        if stat.S_ISDIR(metadata.st_mode):
            child_fd = os.open(name, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC, dir_fd=directory_fd)
            try:
                _read_tree(child_fd, child_relative, output)
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(metadata.st_mode) or not name.endswith(".json"):
            raise LiteratureIntegrityError(f"unexpected literature record object: {child_relative}")
        descriptor = os.open(name, os.O_RDONLY | _NOFOLLOW | _CLOEXEC, dir_fd=directory_fd)
        try:
            before = os.fstat(descriptor)
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                raw = handle.read()
            after = os.fstat(descriptor)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise LiteratureIntegrityError(f"canonical record changed while read: {child_relative}")
            output.append((child_relative, raw))
        finally:
            os.close(descriptor)


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = ["LITERATURE_RELATIVE", "LITERATURE_RUNTIME_RELATIVE", "LiteratureStore"]
