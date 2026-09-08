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
            return {
                "schema": "alphaquest.literature-validation/v1",
                "status": "PASS",
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
        if len(lane_existing) >= lane.maximum_queries:
            raise LiteratureConflictError("frozen lane query budget is exhausted")
        material.update(
            {
                "revision": 1,
                "previous_revision_sha256": None,
                "record_id": f"{search_id}.r000001",
                "status": "STARTED",
                "results_inspected": 0,
                "capture_attempts": 0,
                "bytes_retrieved": 0,
                "elapsed_seconds": 0,
                "result_set_sha256": None,
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
        material = previous.model_dump(
            mode="json", by_alias=True, exclude=_MANAGED_FIELDS | {"revision", "previous_revision_sha256", "record_id"}
        )
        material.update(payload)
        material.update(
            {
                "record_id": f"{search_run_id}.r000002",
                "revision": 2,
                "previous_revision_sha256": previous.record_sha256,
            }
        )
        candidate = SearchRunRevisionV1.model_validate_json(
            canonical_json_bytes({
                **material,
                "schema": SearchRunRevisionV1.schema_literal,
                "append_sequence": 1,
                "previous_store_record_sha256": None,
                "recorded_at": recorded_at or _now(),
                "actor": actor.model_dump(mode="json"),
                "idempotency_key": idempotency_key,
                "intent_sha256": "0" * 64,
                "record_sha256": "0" * 64,
            })
        )
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
        assert_no_pnl_repository_reference(str(material["retrieval_locator"]))
        capture_id = str(material["capture_id"])
        previous = self._latest_optional(SourceCaptureRevisionV1, capture_id)
        if previous is not None:
            if previous.status != "STARTED":
                raise LiteratureConflictError("terminal capture is immutable; recapture requires a new capture_id")
            if material.get("status") == "STARTED":
                raise LiteratureConflictError("capture STARTED state cannot be appended twice")
            for field in ("source_version_id", "source_version_revision_sha256", "retrieval_locator", "captured_at"):
                material.setdefault(field, getattr(previous, field))
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
        capture = self._record_by_hash(str(material["capture_revision_sha256"]), SourceCaptureRevisionV1)
        if capture.capture_id != material.get("capture_id"):
            raise LiteratureConflictError("claim capture ID/hash mismatch")
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

    def append_dossier(self, payload: Mapping[str, Any], **kwargs: Any) -> EdgeDossierRevisionV1:
        material = dict(payload)
        protocol = self._record_by_hash(str(material["protocol_revision_sha256"]), ResearchProtocolRevisionV1)
        if protocol.execution_lineage_id != material.get("execution_lineage_id"):
            raise LiteratureConflictError("dossier execution lineage does not match protocol")
        for reference in material["claim_refs"]:
            claim = self._record_by_hash(str(reference["claim_revision_sha256"]), ClaimExtractionRevisionV1)
            if claim.claim_id != reference["claim_id"]:
                raise LiteratureConflictError("dossier claim ID/hash mismatch")
        for statement in material["material_statements"]:
            for reference in statement["claim_refs"]:
                self._record_by_hash(str(reference["record_sha256"]), ClaimExtractionRevisionV1)
        for reference in material["evidence_relation_refs"]:
            relation = self._record_by_hash(str(reference["record_sha256"]), EvidenceRelationRevisionV1)
            if relation.record_id != reference["record_id"]:
                raise LiteratureConflictError("dossier evidence-relation ID/hash mismatch")
        for descriptor in material["quality_descriptors"]:
            for reference in descriptor["basis_claims"]:
                self._record_by_hash(str(reference["record_sha256"]), ClaimExtractionRevisionV1)
        for mapping in material["taxonomy_proposal"]["dimension_mappings"]:
            for reference in mapping["basis_claims"]:
                self._record_by_hash(str(reference["record_sha256"]), ClaimExtractionRevisionV1)
        lane_protocols = {item.lane: item for item in protocol.lanes}
        for completion in material["lane_completions"]:
            lane_name = completion["lane"]
            lane_protocol = lane_protocols[lane_name]
            searches: list[SearchRunRevisionV1] = []
            for reference in completion["search_run_refs"]:
                search = self._record_by_hash(str(reference["record_sha256"]), SearchRunRevisionV1)
                if search.record_id != reference["record_id"]:
                    raise LiteratureConflictError("lane search reference ID/hash mismatch")
                if search.execution_lineage_id != protocol.execution_lineage_id or search.lane != lane_name:
                    raise LiteratureConflictError("prior-lineage or cross-lane searches cannot satisfy this protocol")
                searches.append(search)
            terminal = all(item.status != "STARTED" for item in searches)
            if (completion["execution_status"] == "TERMINAL") != terminal:
                raise LiteratureConflictError("lane execution status does not match referenced search records")
            satisfied = self._lane_obligation_satisfied(lane_protocol, searches)
            if (completion["obligation_status"] == "SATISFIED") != satisfied:
                raise LiteratureConflictError("lane obligation status does not match frozen protocol minimums")
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

    @staticmethod
    def _lane_obligation_satisfied(lane: Any, searches: list[SearchRunRevisionV1]) -> bool:
        terminal = [item for item in searches if item.status in {"SUCCEEDED", "PARTIAL"}]
        initial_queries = {item.query for item in terminal if item.query_kind == "INITIAL"}
        return (
            set(lane.required_initial_queries).issubset(initial_queries)
            and len(terminal) >= lane.minimum_provider_attempts
            and sum(item.results_inspected for item in terminal)
            >= lane.minimum_distinct_results_inspected
            and all(
                item.results_inspected >= lane.minimum_results_inspected_per_query
                for item in terminal
                if item.query_kind == "INITIAL"
            )
            and sum(item.capture_attempts for item in terminal) >= lane.minimum_capture_attempts
        )

    def freeze_dossier(
        self,
        payload: Mapping[str, Any],
        *,
        actor: ActorProvenanceV1,
        idempotency_key: str,
        recorded_at: datetime | None = None,
    ) -> DossierFreezeV1:
        material = dict(payload)
        dossier = self._record_by_hash(str(material["dossier_revision_sha256"]), EdgeDossierRevisionV1)
        if dossier.dossier_id != material.get("dossier_id"):
            raise LiteratureConflictError("freeze dossier ID/hash mismatch")
        if dossier.protocol_revision_sha256 != material.get("protocol_revision_sha256"):
            raise LiteratureConflictError("freeze protocol binding does not match dossier")
        expected_claims = {(item.claim_id, item.claim_revision_sha256) for item in dossier.claim_refs}
        actual_claims = {(_object_id(item["record_id"]), item["record_sha256"]) for item in material["claim_refs"]}
        if expected_claims != actual_claims:
            raise LiteratureConflictError("freeze claim set does not match dossier")
        expected_relations = {
            (item.record_id, item.record_sha256) for item in dossier.evidence_relation_refs
        }
        actual_relations = {
            (item["record_id"], item["record_sha256"]) for item in material["evidence_relation_refs"]
        }
        if expected_relations != actual_relations:
            raise LiteratureConflictError("freeze evidence-relation set does not match dossier")
        expected_unsatisfied = sorted(
            item.lane for item in dossier.lane_completions if item.obligation_status != "SATISFIED"
        )
        if sorted(material["unsatisfied_lanes"]) != expected_unsatisfied:
            raise LiteratureConflictError("freeze unsatisfied lanes do not match dossier completion evidence")
        return self._append(DossierFreezeV1, material, actor, idempotency_key, recorded_at)

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
                "record_sha256": "0" * 64,
            }
            try:
                provisional = record_type.model_validate_json(canonical_json_bytes(material))
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
            draft = record_type.model_validate_json(canonical_json_bytes(material))
            sealed_material = draft.model_dump(mode="json", by_alias=True)
            sealed_material["record_sha256"] = record_sha256(sealed_material)
            record = record_type.model_validate_json(canonical_json_bytes(sealed_material))
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
            "emission_action",
            "reservations",
            "observation_plans",
            "entry_plan",
            "search_completion_status",
            "unsatisfied_lanes",
            "prior_staled_decision_sha256",
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
        if record.state == "OBSERVATIONS_WRITTEN" and len(record.observation_bindings) != len(record.observation_plans):
            raise LiteratureConflictError("observation stage requires one exact binding per plan")
        if record.state in {"ENTRY_WRITTEN", "SNAPSHOT_BOUND", "COMPLETED"} and record.entry_binding is None:
            raise LiteratureConflictError("entry-written stage requires an exact P2 entry binding")
        if record.state in {"SNAPSHOT_BOUND", "COMPLETED"} and record.duplicate_snapshot is None:
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

    def _validate_cross_record_state(self, records: list[CanonicalRecordV1]) -> None:
        hashes = {record.record_sha256 for record in records}
        records_by_hash = {record.record_sha256: record for record in records}

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
                    require_reference(reference, ClaimExtractionRevisionV1)
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
                "prior_staled_decision_sha256",
                "search_completion_status",
                "unsatisfied_lanes",
            ):
                if getattr(record, field) != getattr(operation, field):
                    raise LiteratureIntegrityError(f"emission receipt does not repeat operation field: {field}")

    @staticmethod
    def _validate_prepared_emission(
        operation: P2EmissionOperationRevisionV1,
        records: list[CanonicalRecordV1],
        records_by_hash: dict[str, CanonicalRecordV1],
    ) -> None:
        from alphaquest.research.literature.mapper import (
            canonical_p2_locator,
            canonical_source_version_resolution,
            derive_p2_observation_id,
            derive_p2_source_id,
            p2_source_kind_for_work,
            selected_evidence_time,
        )

        freeze = records_by_hash.get(operation.freeze_record_sha256)
        if not isinstance(freeze, DossierFreezeV1) or freeze.freeze_id != operation.freeze_id:
            raise LiteratureIntegrityError("prepared emission freeze identity/hash mismatch")
        relationships = [
            item
            for item in records
            if isinstance(item, SourceRelationshipRevisionV1)
            and item.append_sequence < operation.append_sequence
        ]
        reservation_by_source = {item.p2_source_id: item for item in operation.reservations}
        for reservation in operation.reservations:
            capture = records_by_hash.get(reservation.terminal_capture_revision_sha256)
            if not isinstance(capture, SourceCaptureRevisionV1) or capture.capture_id != reservation.capture_id:
                raise LiteratureIntegrityError("P2 evidence reservation capture identity/hash mismatch")
            if capture.status not in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
                raise LiteratureIntegrityError("P2 evidence reservation capture is not terminal evidence")
            if (
                capture.content_sha256 != reservation.content_sha256
                or capture.extracted_representation_sha256 != reservation.extracted_representation_sha256
            ):
                raise LiteratureIntegrityError("P2 evidence reservation bytes do not match its capture")
            if reservation.p2_source_id != derive_p2_source_id(reservation.canonical_source_version_id):
                raise LiteratureIntegrityError("P2 source ID is not derived from canonical source-version identity")
            if reservation.reservation_operation_id == operation.operation_id:
                version = records_by_hash.get(capture.source_version_revision_sha256)
                if not isinstance(version, SourceVersionIdentityRevisionV1):
                    raise LiteratureIntegrityError("reservation capture has no exact source-version record")
                work = records_by_hash.get(version.work_revision_sha256)
                if not isinstance(work, SourceIdentityRevisionV1):
                    raise LiteratureIntegrityError("reservation source version has no exact work record")
                canonical_id, relationship_hash, _component = canonical_source_version_resolution(
                    capture.source_version_id, relationships
                )
                if (
                    canonical_id != reservation.canonical_source_version_id
                    or relationship_hash != reservation.relationship_state_sha256
                    or canonical_p2_locator(work, capture) != reservation.canonical_locator
                    or p2_source_kind_for_work(work) != reservation.source_kind
                    or selected_evidence_time(version, capture) != reservation.evidence_time
                ):
                    raise LiteratureIntegrityError("first P2 reservation does not match frozen SAME_VERSION_AS state")
        planned_roles = []
        for plan in operation.observation_plans:
            claim = records_by_hash.get(plan.claim_revision_sha256)
            if not isinstance(claim, ClaimExtractionRevisionV1) or claim.claim_id != plan.claim_id:
                raise LiteratureIntegrityError("P2 observation plan claim identity/hash mismatch")
            if plan.observation_id != derive_p2_observation_id(claim.claim_id):
                raise LiteratureIntegrityError("logical P3 claim did not map to deterministic P2 observation ID")
            expected_payload_sha = hashlib.sha256(
                canonical_json_bytes(plan.payload, trailing_lf=False)
            ).hexdigest()
            if plan.payload_sha256 != expected_payload_sha:
                raise LiteratureIntegrityError("P2 observation plan payload hash is invalid")
            evidence_sources = {item.source_id for item in plan.payload.evidence_refs}
            if not evidence_sources or not evidence_sources.issubset(reservation_by_source):
                raise LiteratureIntegrityError("P2 observation plan is not covered by prepared reservations")
            for source_id in evidence_sources:
                reservation = reservation_by_source[source_id]
                if any(
                    item.content_sha256 != reservation.content_sha256
                    or item.locator != reservation.canonical_locator
                    or item.evidence_time != reservation.evidence_time.evidence_time
                    for item in plan.payload.evidence_refs
                    if item.source_id == source_id
                ):
                    raise LiteratureIntegrityError("P2 observation evidence differs from its reservation")
            if not plan.withdrawn_from_current_support:
                planned_roles.append((plan.observation_id, plan.role))
        current_roles = [
            (item.observation_id, item.role)
            for item in operation.entry_plan.observation_roles
            if item.frozen_revision_sha256 is None
        ]
        if planned_roles != current_roles:
            raise LiteratureIntegrityError("P2 entry plan roles do not match current observation plans")


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
