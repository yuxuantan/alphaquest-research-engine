from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading

import pytest
from jsonschema import Draft202012Validator

from alphaquest.research.edge_backlog import EdgeBacklogIntegrityError, EdgeBacklogStore
from alphaquest.research.edge_backlog_taxonomy import bundled_taxonomy_ref
from alphaquest.research.literature.contracts import (
    ActorProvenanceV1,
    CANONICAL_RECORD_TYPES,
    ClaimExtractionRevisionV1,
    LiteratureAuthorityError,
    LiteratureConflictError,
    LiteratureIntegrityError,
    RevisionRecordV1,
    SCHEMA_TYPES,
    canonical_json_bytes,
    intent_sha256,
    methodology_sha256,
    record_sha256,
)
from alphaquest.research.literature.emission import emit_prepared, prepare_emission, reconcile_emission
from alphaquest.research.literature.mapper import (
    derive_p2_observation_id,
    derive_p2_source_id,
    selected_evidence_time,
)
from alphaquest.research.literature.security import codex_workspace_inputs
from alphaquest.research.literature.store import LiteratureStore


REPO = Path(__file__).parents[1]
FIXTURES = REPO / "tests/fixtures/literature"
NOW = datetime(2026, 9, 1, 14, 0, tzinfo=timezone.utc)
MANAGED_FIELDS = {
    "schema",
    "append_sequence",
    "previous_store_record_sha256",
    "recorded_at",
    "actor",
    "idempotency_key",
    "intent_sha256",
    "record_sha256",
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, stdout=subprocess.DEVNULL)


def _project(root: Path) -> Path:
    (root / "config").mkdir(parents=True)
    shutil.copy2(REPO / "config/storage_layout.yaml", root / "config/storage_layout.yaml")
    destination = root / "research/edge_backlog/contracts"
    destination.mkdir(parents=True)
    for source in (REPO / "research/edge_backlog/contracts").glob("*.json"):
        shutil.copy2(source, destination / source.name)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "P3 Tests")
    _git(root, "config", "user.email", "p3@example.test")
    _git(root, "add", "config/storage_layout.yaml", "research/edge_backlog/contracts")
    _git(root, "commit", "-q", "-m", "fixture authority")
    return root


def _actor(name: str = "engine") -> ActorProvenanceV1:
    return ActorProvenanceV1(actor_class="ALPHAQUEST_DETERMINISTIC_ENGINE", actor_id=name)


def _lane(name: str, *, maximum_results: int = 10, maximum_captures: int = 5) -> dict:
    return {
        "lane": name,
        "required_initial_queries": [f"fixed query for {name.lower()}"],
        "provider_order": ["fixture-provider"],
        "minimum_provider_attempts": 1,
        "minimum_results_inspected_per_query": 1,
        "minimum_distinct_results_inspected": 1,
        "minimum_capture_attempts": 1,
        "capture_selection_rule": "PROVIDER_RANK_THEN_RESULT_RANK_THEN_LOCATOR_HASH",
        "adaptive_max_depth": 1,
        "maximum_queries": 2,
        "maximum_results": maximum_results,
        "maximum_captures": maximum_captures,
        "maximum_bytes": 100000,
        "maximum_elapsed_seconds": 60,
        "saturation": {
            "enabled": True,
            "minimum_queries_before_check": 1,
            "consecutive_queries_without_new_work": 1,
        },
    }


LANES = (
    "SUPPORTING_OR_MOTIVATING",
    "NULL_OR_CONTRARY",
    "FAILED_REPLICATION",
    "REGIME_DEPENDENCE",
    "TRANSACTION_COST_OR_EXECUTION_OBJECTION",
    "ALTERNATIVE_EXPLANATION",
    "DATA_MINING_OR_MULTIPLE_TESTING",
)


def _protocol(store: LiteratureStore, *, protocol_id: str = "protocol.fixture", lineage: str = "lineage.fixture", **extra):
    payload = {
        "protocol_id": protocol_id,
        "execution_lineage_id": lineage,
        "lineage_kind": "PRE_RESULT_PROTOCOL",
        "parent_execution_lineage_id": None,
        "observed_result_set_sha256": None,
        "research_question": "Does opening imbalance motivate a pre-hypothesis edge?",
        "market_scope": ["ES futures"],
        "inclusion_rules": ["Public, inspectable source"],
        "exclusion_rules": ["PnL-bearing AlphaQuest artifacts"],
        "lanes": [_lane(name) for name in LANES],
        "administrative_annotations": [],
        "change_reason": "Initial frozen fixture protocol",
    }
    payload.update(extra)
    key = hashlib.sha256(canonical_json_bytes(payload, trailing_lf=False)).hexdigest()[:16]
    return store.append_protocol(payload, actor=_actor(), idempotency_key=f"{protocol_id}.{key}")


def _location(data: bytes, *, representation: str = "PLAIN_TEXT") -> dict:
    material = {
        "representation_kind": representation,
        "page_number": 1 if representation == "PDF" else None,
        "section_anchor": "fixture",
        "block_ordinal": 0,
        "byte_start": 0,
        "byte_end": len(data),
        "span_sha256": hashlib.sha256(data).hexdigest(),
    }
    material["locator_sha256"] = hashlib.sha256(canonical_json_bytes(material, trailing_lf=False)).hexdigest()
    return material


def _search_result(locator: str, *, provider_rank: int = 1, result_rank: int = 1) -> dict:
    work_hash = hashlib.sha256(f"work|{locator}".encode()).hexdigest()
    locator_hash = hashlib.sha256(locator.encode()).hexdigest()
    identity = hashlib.sha256(
        canonical_json_bytes(
            {"canonical_locator": locator, "work_identity_sha256": work_hash},
            trailing_lf=False,
        )
    ).hexdigest()
    return {
        "result_identity_sha256": identity,
        "work_identity_sha256": work_hash,
        "canonical_locator": locator,
        "locator_sha256": locator_hash,
        "provider_rank": provider_rank,
        "result_rank": result_rank,
    }


def _search_outcome(locator: str, *, capture: bool = True, **overrides) -> dict:
    result = _search_result(locator)
    material = {
        "status": "SUCCEEDED",
        "inspected_results": [result],
        "capture_attempt_records": (
            [
                {
                    "capture_attempt_id": "attempt." + result["result_identity_sha256"][:24],
                    "result_identity_sha256": result["result_identity_sha256"],
                    "selection_ordinal": 1,
                }
            ]
            if capture
            else []
        ),
        "bytes_retrieved": 0,
        "elapsed_seconds": 1,
        "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        "failure_reason": None,
        "saturation_claimed": False,
    }
    material.update(overrides)
    return material


def _source(
    store: LiteratureStore,
    name: str,
    text: bytes,
    *,
    category: str = "ACADEMIC",
    capture_status: str = "FULL_TEXT_CAPTURED",
    availability_precision: str = "EXACT_INSTANT",
    availability_verification: str = "VERIFIED",
    identity_status: str = "VERIFIED_STRONG",
    processing: str = "ALLOWED_EXTERNAL_PROCESSOR",
    statement_kind: str = "SOURCE_QUOTE",
):
    work = store.append_work(
        {
            "work_id": f"work.{name}",
            "source_category": category,
            "title": f"Fixture {name}",
            "authors": ["Fixture Author"],
            "strong_identifiers": {"doi": f"10.0000/{name}"},
            "locators": [f"https://example.test/{name}"],
            "identity_status": identity_status,
            "change_reason": "Offline fixture",
        },
        actor=_actor(),
        idempotency_key=f"work.{name}.r1",
    )
    version = store.append_source_version(
        {
            "source_version_id": f"version.{name}",
            "work_id": work.work_id,
            "work_revision_sha256": work.record_sha256,
            "version_kind": "ORIGINAL",
            "version_label": "v1",
            "strong_identifiers": {"doi": f"10.0000/{name}"},
            "public_availability": {
                "original_value": "2026-08-31T14:00:00Z" if availability_precision == "EXACT_INSTANT" else "2026-08-31",
                "parsed_value": "2026-08-31T14:00:00Z" if availability_precision == "EXACT_INSTANT" else None,
                "precision": availability_precision,
                "verification": availability_verification,
                "timezone_basis": "UTC" if availability_precision == "EXACT_INSTANT" else None,
                "provenance_record_ids": [],
            },
            "identity_status": identity_status,
            "change_reason": "Offline fixture version",
        },
        actor=_actor(),
        idempotency_key=f"version.{name}.r1",
    )
    if capture_status in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
        content_sha = store.put_artifact(text, kind="artifacts")
        extracted_sha = store.put_artifact(text, kind="extracted")
        evidence_fields = {
            "media_type": "text/plain",
            "content_sha256": content_sha,
            "content_bytes": len(text),
            "extracted_representation_sha256": extracted_sha,
            "extracted_bytes": len(text),
            "extractor_id": "fixture-extractor",
            "extractor_version": "1",
            "extractor_config_sha256": hashlib.sha256(b"fixture extractor config").hexdigest(),
        }
    else:
        evidence_fields = {
            "media_type": None,
            "content_sha256": None,
            "content_bytes": None,
            "extracted_representation_sha256": None,
            "extracted_bytes": None,
            "extractor_id": None,
            "extractor_version": None,
            "extractor_config_sha256": None,
        }
    capture = store.append_capture(
        {
            "capture_id": f"capture.{name}",
            "source_version_id": version.source_version_id,
            "source_version_revision_sha256": version.record_sha256,
            "retrieval_locator": f"https://example.test/{name}",
            "status": capture_status,
            "captured_at": NOW,
            "access_basis": "OPEN_PUBLIC" if capture_status != "LOCATOR_METADATA_ONLY" else "INACCESSIBLE",
            "local_retention_permission": "ALLOWED" if capture_status != "LOCATOR_METADATA_ONLY" else "UNKNOWN",
            "redistribution_permission": "RESTRICTED",
            "external_model_processing_permission": processing,
            "failure_reason": None,
            **evidence_fields,
        },
        actor=_actor(),
        idempotency_key=f"capture.{name}.r1",
    )
    if capture_status not in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
        return work, version, capture, None
    claim = store.append_claim(
        {
            "claim_id": f"claim.{name}",
            "work_id": work.work_id,
            "work_revision_sha256": work.record_sha256,
            "source_version_id": version.source_version_id,
            "source_version_revision_sha256": version.record_sha256,
            "capture_id": capture.capture_id,
            "capture_revision_sha256": capture.record_sha256,
            "content_sha256": capture.content_sha256,
            "extracted_representation_sha256": capture.extracted_representation_sha256,
            "location": _location(text, representation="STRUCTURED_ABSTRACT" if capture_status == "GENUINE_ABSTRACT_CAPTURED" else "PLAIN_TEXT"),
            "statement": text.decode(),
            "statement_kind": statement_kind,
            "source_epistemic_form": "NULL_RESULT" if name == "contrary" else "ASSOCIATION_REPORTED",
            "reliability": "ACTIVE",
            "correction_reason": None,
            "conflict_refs": [],
        },
        actor=_actor(),
        idempotency_key=f"claim.{name}.r1",
    )
    return work, version, capture, claim


def _concepts() -> dict:
    return {
        "instrument_ids": ["ES"],
        "market_behavior_code": "INVENTORY_IMBALANCE",
        "causal_mechanism_code": "DELAYED_INVENTORY_ADJUSTMENT",
        "beneficiary_counterparty_codes": ["LIQUIDITY_PROVIDERS"],
        "cost_bearer_counterparty_codes": ["HEDGERS"],
        "transfer_rationale_code": "INVENTORY_RISK_COMPENSATION",
        "information_input_codes": ["POSITIONING_AND_INVENTORY_PROXY", "PRICE"],
        "information_availability_code": "AVAILABLE_AFTER_INTERVAL",
        "expected_effect_code": "PRICE_CONTINUATION",
        "holding_horizon_code": "INTRASESSION",
        "market_context_codes": ["OPENING_AUCTION"],
    }


def _dossier(store: LiteratureStore, protocol, claims, *, dossier_id: str = "dossier.fixture", p2_entry_id=None, prior_receipt=None):
    refs = [
        {
            "claim_id": claim.claim_id,
            "claim_revision_sha256": claim.record_sha256,
            "p2_role": role,
        }
        for claim, role in claims
    ]
    record_refs = [{"record_id": claim.record_id, "record_sha256": claim.record_sha256} for claim, _ in claims]
    relation_refs = []
    if len(record_refs) >= 2:
        relation = store.append_evidence_relation(
            {
                "evidence_relation_id": f"relation.{dossier_id}",
                "relationship": "CONTRADICTS",
                "claim_refs": record_refs[:2],
                "relationship_basis": "ALPHAQUEST_EXPLICIT_INFERENCE",
                "rationale": "Keep cross-paper economic disagreement separate from P3 conflict strings.",
                "status": "ACTIVE",
                "superseded_by_relation_id": None,
            },
            actor=_actor(),
            idempotency_key=f"relation.{dossier_id}.r{1 if p2_entry_id is None else 2}",
        )
        relation_refs = [{"record_id": relation.record_id, "record_sha256": relation.record_sha256}]
    dossier = store.append_dossier(
        {
            "dossier_id": dossier_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "search_completion_status": "TERMINATED_WITH_DECLARED_GAPS",
            "lane_completions": store._derive_lane_completions(protocol, store.records()),
            "claim_refs": refs,
            "evidence_relation_refs": relation_refs,
            "quality_descriptors": [
                {
                    "descriptor": "peer_review_status",
                    "value": "fixture_only",
                    "verification": "UNVERIFIED",
                    "basis_claims": [],
                }
            ],
            "material_statements": [
                {
                    "statement_id": "statement.fixture",
                    "text": "The source record motivates research and preserves contrary evidence.",
                    "basis": "CLAIM_LINKED",
                    "claim_refs": record_refs,
                    "inference_rationale": None,
                }
            ],
            "taxonomy_proposal": {
                "classification_status": "CLASSIFIED",
                "taxonomy_ref": bundled_taxonomy_ref().model_dump(mode="json"),
                "economic_concepts": _concepts(),
                "unclassified_reason": None,
                "dimension_mappings": [
                    {
                        "dimension": "market_behavior_code",
                        "taxonomy_codes": ["INVENTORY_IMBALANCE"],
                        "mapping_basis": "ALPHAQUEST_EXPLICIT_INFERENCE",
                        "basis_claims": [record_refs[0]],
                        "rationale": "Unambiguous fixture classification; not causal validation.",
                    }
                ],
            },
            "p2_entry_id": p2_entry_id,
            "prior_emission_receipt_sha256": prior_receipt,
            "change_reason": "Offline deterministic dossier",
        },
        actor=_actor(),
        idempotency_key=f"{dossier_id}.r{1 if p2_entry_id is None else 2}",
    )
    freeze_id = f"freeze.{dossier_id}.{dossier.revision}"
    freeze = store.freeze_dossier(
        {
            "freeze_id": freeze_id,
            "dossier_id": dossier.dossier_id,
            "dossier_revision_sha256": dossier.record_sha256,
        },
        actor=_actor(),
        idempotency_key=freeze_id,
    )
    return dossier, freeze


def _initial_slice(root: Path):
    store = LiteratureStore(root)
    protocol = _protocol(store)
    supporting = _source(store, "supporting", (FIXTURES / "supporting.txt").read_bytes())[-1]
    contrary = _source(store, "contrary", (FIXTURES / "contrary.txt").read_bytes())[-1]
    dossier, freeze = _dossier(store, protocol, [(supporting, "SUPPORTING"), (contrary, "CONTRADICTING")])
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.initial",
        actor=_actor(),
        idempotency_key="emission.initial.prepared",
    )
    receipt = emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    return store, protocol, supporting, contrary, dossier, freeze, operation, receipt


def _all_family_slice(root: Path) -> LiteratureStore:
    store, protocol, support, contrary, _dossier_record, _freeze, _operation, _receipt = (
        _initial_slice(root)
    )
    lane = next(item for item in protocol.lanes if item.lane == "SUPPORTING_OR_MOTIVATING")
    started = store.start_search(
        {
            "search_run_id": "search.all-families",
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": lane.lane,
            "query": lane.required_initial_queries[0],
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": lane.provider_order[0],
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        },
        actor=_actor(),
        idempotency_key="search.all-families.start",
    )
    store.finish_search(
        started.search_run_id,
        _search_outcome("https://example.test/all-families"),
        actor=_actor(),
        idempotency_key="search.all-families.finish",
    )
    store.append_source_relationship(
        {
            "relationship_id": "relationship.all-families",
            "subject_kind": "WORK",
            "subject_id": support.work_id,
            "predicate": "POSSIBLE_SAME_WORK",
            "object_kind": "WORK",
            "object_id": contrary.work_id,
            "status": "ACTIVE",
            "assertion_evidence_refs": [],
            "superseded_by_relationship_id": None,
            "change_reason": "Exercise the canonical relationship family",
        },
        actor=_actor(),
        idempotency_key="relationship.all-families.r1",
    )
    sha = hashlib.sha256(b"canonical task fixture").hexdigest()
    store.append_codex_attempt(
        {
            "attempt_id": "attempt.all-families",
            "task_type": "CLAIM_EXTRACTOR",
            "status": "STARTED",
            "model": None,
            "settings_sha256": sha,
            "prompt_sha256": sha,
            "input_manifest_sha256": sha,
            "workspace_manifest_sha256": None,
            "output_sha256": None,
            "referenced_records": [],
            "isolation_backend": "offline-fixture",
            "failure_reason": None,
        },
        actor=_actor(),
        idempotency_key="attempt.all-families.r1",
    )
    assert {type(item).family for item in store.records()} == {
        item.family for item in CANONICAL_RECORD_TYPES
    }
    return store


def _canonical_paths(root: Path) -> list[Path]:
    return sorted((root / "research/literature").glob("**/*.json"))


def _deep_hash_replace(value, replacements: dict[str, str]):
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_deep_hash_replace(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _deep_hash_replace(item, replacements) for key, item in value.items()}
    return value


def _rewrite_valid_hash_chains(root: Path, mutate) -> None:
    """Tamper semantically, then rebuild hashes so full-history checks are reached."""

    rows = [(path, json.loads(path.read_text())) for path in _canonical_paths(root)]
    rows.sort(key=lambda item: item[1]["append_sequence"])
    replacements: dict[str, str] = {}
    revision_heads: dict[tuple[str, str], str] = {}
    previous_store: str | None = None
    for path, original in rows:
        old_hash = original["record_sha256"]
        record = _deep_hash_replace(original, replacements)
        mutate(record)
        record["previous_store_record_sha256"] = previous_store
        record_type = SCHEMA_TYPES[record["schema"]]
        if issubclass(record_type, RevisionRecordV1):
            object_id = record["record_id"].rsplit(".r", 1)[0]
            key = (record["schema"], object_id)
            record["previous_revision_sha256"] = revision_heads.get(key)
        intent_material = {
            key: value for key, value in record.items() if key not in MANAGED_FIELDS
        }
        if issubclass(record_type, RevisionRecordV1):
            for key in ("record_id", "revision", "previous_revision_sha256"):
                intent_material.pop(key, None)
        record["intent_sha256"] = intent_sha256(intent_material)
        record["record_sha256"] = record_sha256(record)
        replacements[old_hash] = record["record_sha256"]
        previous_store = record["record_sha256"]
        if issubclass(record_type, RevisionRecordV1):
            revision_heads[(record["schema"], record["record_id"].rsplit(".r", 1)[0])] = record[
                "record_sha256"
            ]
        path.write_bytes(canonical_json_bytes(record))


PROTOCOL_FROZEN_MUTATIONS = (
    "execution_lineage_id",
    "lineage_provenance",
    "research_question",
    "market_scope",
    "inclusion_rules",
    "exclusion_rules",
    "required_initial_queries",
    "provider_order",
    "minimum_provider_attempts",
    "minimum_results_inspected_per_query",
    "minimum_distinct_results_inspected",
    "minimum_capture_attempts",
    "capture_selection_rule",
    "adaptive_max_depth",
    "maximum_queries",
    "maximum_results",
    "maximum_captures",
    "maximum_bytes",
    "maximum_elapsed_seconds",
    "saturation",
)


def _mutate_protocol_contract(payload: dict, field: str) -> None:
    if field == "execution_lineage_id":
        payload[field] = "lineage.mutated"
    elif field == "lineage_provenance":
        payload["lineage_kind"] = "RESULT_INFORMED_EXTENSION"
        payload["parent_execution_lineage_id"] = "lineage.parent"
        payload["observed_result_set_sha256"] = "a" * 64
    elif field in {"research_question"}:
        payload[field] = "Mutated research question"
    elif field in {"market_scope", "inclusion_rules", "exclusion_rules"}:
        payload[field] = [f"mutated {field}"]
    elif field == "required_initial_queries":
        payload["lanes"][0][field] = ["mutated initial query"]
    elif field == "provider_order":
        payload["lanes"][0][field] = ["mutated-provider"]
    elif field == "capture_selection_rule":
        payload["lanes"][0][field] = "MUTATED_SELECTION_RULE"
    elif field == "saturation":
        payload["lanes"][0][field] = None
    else:
        payload["lanes"][0][field] += 1


def _protocol_with_lane(store: LiteratureStore, lane_override: dict):
    lanes = [_lane(name) for name in LANES]
    lanes[0].update(lane_override)
    return _protocol(store, lanes=lanes)


def _start_lane_search(store: LiteratureStore, protocol, search_id: str, provider: str):
    lane = protocol.lanes[0]
    return store.start_search(
        {
            "search_run_id": search_id,
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": lane.lane,
            "query": lane.required_initial_queries[0],
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": provider,
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        },
        actor=_actor(),
        idempotency_key=f"{search_id}.start",
    )


def _start_capture(store: LiteratureStore, version, capture_id: str):
    return store.append_capture(
        {
            "capture_id": capture_id,
            "source_version_id": version.source_version_id,
            "source_version_revision_sha256": version.record_sha256,
            "retrieval_locator": f"https://example.test/{capture_id}",
            "status": "STARTED",
            "captured_at": NOW,
            "access_basis": "OPEN_PUBLIC",
            "local_retention_permission": "ALLOWED",
            "redistribution_permission": "RESTRICTED",
            "external_model_processing_permission": "ALLOWED_EXTERNAL_PROCESSOR",
            "media_type": None,
            "content_sha256": None,
            "content_bytes": None,
            "extracted_representation_sha256": None,
            "extracted_bytes": None,
            "extractor_id": None,
            "extractor_version": None,
            "extractor_config_sha256": None,
            "failure_reason": None,
        },
        actor=_actor(),
        idempotency_key=f"{capture_id}.start",
    )


def test_offline_canonical_slice_emits_receipt_and_prefix_snapshot(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, _protocol_record, _support, _contrary, _dossier_record, freeze, operation, receipt = _initial_slice(root)
    assert operation.state == "PREPARED"
    assert receipt.freeze_record_sha256 == freeze.record_sha256
    assert receipt.search_completion_status == "TERMINATED_WITH_DECLARED_GAPS"
    assert sorted(receipt.unsatisfied_lanes) == sorted(LANES)
    # Two observations are append sequences 1-2 and the entry is 3; the prefix is 4.
    assert receipt.duplicate_snapshot.before_append_sequence == 4
    assert receipt.duplicate_snapshot.candidate_bindings == []
    assert store.validate()["family_count"] == 13
    assert EdgeBacklogStore(root).validate()["status"] == "PASS"
    assert reconcile_emission(root, operation_id="emission.initial", actor=_actor()).record_sha256 == receipt.record_sha256


def test_evidence_time_uses_exact_availability_else_capture_without_midnight(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    _, exact_version, exact_capture, _ = _source(store, "exact", b"exact source")
    _, coarse_version, coarse_capture, _ = _source(
        store,
        "coarse",
        b"coarse source",
        availability_precision="DAY",
        availability_verification="SOURCE_REPORTED_UNVERIFIED",
    )
    exact = selected_evidence_time(exact_version, exact_capture)
    coarse = selected_evidence_time(coarse_version, coarse_capture)
    assert exact.evidence_time.isoformat() == "2026-08-31T14:00:00+00:00"
    assert exact.basis == "VERIFIED_PUBLIC_AVAILABILITY"
    assert coarse.evidence_time == NOW
    assert coarse.basis == "CAPTURE_FALLBACK_COARSE_OR_UNCERTAIN"


def test_offline_source_variants_recapture_changed_ambiguous_correction_and_retraction(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    _, version, first, claim = _source(store, "variants", b"stable bytes", statement_kind="FAITHFUL_PARAPHRASE")
    abstract = _source(store, "abstract", (FIXTURES / "abstract.txt").read_bytes(), capture_status="GENUINE_ABSTRACT_CAPTURED")
    lead = _source(store, "lead", b"", capture_status="LOCATOR_METADATA_ONLY")
    ambiguous = _source(store, "ambiguous", b"ambiguous", identity_status="AMBIGUOUS")
    assert abstract[2].status == "GENUINE_ABSTRACT_CAPTURED" and abstract[3] is not None
    assert lead[2].status == "LOCATOR_METADATA_ONLY" and lead[3] is None
    assert ambiguous[0].identity_status == "AMBIGUOUS"
    identical = store.append_capture(
        {
            **first.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"}),
            "capture_id": "capture.variants.identical",
        },
        actor=_actor(), idempotency_key="capture.variants.identical.r1",
    )
    changed_sha = store.put_artifact(b"changed bytes", kind="artifacts")
    changed_extracted = store.put_artifact(b"changed bytes", kind="extracted")
    changed_payload = first.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"})
    changed_payload.update(capture_id="capture.variants.changed", content_sha256=changed_sha, extracted_representation_sha256=changed_extracted, content_bytes=13, extracted_bytes=13)
    changed = store.append_capture(changed_payload, actor=_actor(), idempotency_key="capture.variants.changed.r1")
    corrected = store.append_claim(
        {
            **claim.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"}),
            "statement": "Stable bytes, faithfully corrected.",
            "reliability": "CORRECTED",
            "correction_reason": "Corrected paraphrase",
        },
        actor=_actor(), idempotency_key="claim.variants.r2",
    )
    correction_notice = _source(store, "correction", b"Correction notice")
    retraction_notice = _source(store, "retraction", b"Retraction notice")
    correction_rel = store.append_source_relationship(
        {"relationship_id": "relationship.correction", "subject_kind": "SOURCE_VERSION", "subject_id": correction_notice[1].source_version_id, "predicate": "CORRECTS", "object_kind": "SOURCE_VERSION", "object_id": version.source_version_id, "status": "ACTIVE", "assertion_evidence_refs": [], "superseded_by_relationship_id": None, "change_reason": "Fixture correction"},
        actor=_actor(), idempotency_key="relationship.correction.r1",
    )
    retraction_rel = store.append_source_relationship(
        {"relationship_id": "relationship.retraction", "subject_kind": "SOURCE_VERSION", "subject_id": retraction_notice[1].source_version_id, "predicate": "RETRACTS", "object_kind": "SOURCE_VERSION", "object_id": version.source_version_id, "status": "ACTIVE", "assertion_evidence_refs": [], "superseded_by_relationship_id": None, "change_reason": "Fixture retraction"},
        actor=_actor(), idempotency_key="relationship.retraction.r1",
    )
    assert identical.content_sha256 == first.content_sha256
    assert changed.content_sha256 != first.content_sha256
    assert corrected.previous_revision_sha256 == claim.record_sha256
    assert {correction_rel.predicate, retraction_rel.predicate} == {"CORRECTS", "RETRACTS"}


def test_malformed_missing_malicious_and_pnl_boundaries(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    with pytest.raises(Exception):
        ActorProvenanceV1(actor_class="EXTERNAL_SYSTEM", actor_id="bad")
    _, _, capture, _ = _source(
        store, "malicious", (FIXTURES / "malicious.txt").read_bytes(), processing="LOCAL_ONLY"
    )
    destination = root / "run-store/literature/codex-workspace"
    with pytest.raises(LiteratureAuthorityError, match="permission"):
        codex_workspace_inputs(capture, destination=destination)
    assert not destination.exists()
    with pytest.raises(LiteratureAuthorityError, match="PnL-bearing"):
        store.append_work(
            {"work_id": "work.pnl", "source_category": "OTHER", "title": "Forbidden", "authors": [], "strong_identifiers": {}, "locators": ["research/evidence/runs/campaign/result.json"], "identity_status": "PROVISIONAL", "change_reason": "bad"},
            actor=_actor(), idempotency_key="work.pnl.r1",
        )
    artifact_path = root / "run-store/literature/artifacts/sha256" / capture.content_sha256[:2] / capture.content_sha256
    artifact_path.unlink()
    with pytest.raises(LiteratureIntegrityError, match="artifacts"):
        store.validate()


def test_protocol_freeze_adaptive_bounds_new_lineage_and_gap_semantics(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol(store)
    supporting_lane = next(item for item in protocol.lanes if item.lane == "SUPPORTING_OR_MOTIVATING")
    started = store.start_search(
        {"search_run_id": "search.initial", "protocol_id": protocol.protocol_id, "protocol_revision_sha256": protocol.record_sha256, "execution_lineage_id": protocol.execution_lineage_id, "lane": supporting_lane.lane, "query": supporting_lane.required_initial_queries[0], "query_kind": "INITIAL", "parent_search_run_id": None, "adaptive_depth": 0, "provider_id": "fixture-provider", "provider_trace_completeness": "COMPLETE_FOR_REQUEST"},
        actor=_actor(), idempotency_key="search.initial.start",
    )
    finished = store.finish_search(
        "search.initial",
        _search_outcome("https://example.test/search-result"),
        actor=_actor(),
        idempotency_key="search.initial.finish",
    )
    administrative = _protocol(store, administrative_annotations=["Owner note"], change_reason="Administrative only")
    assert administrative.methodology_sha256 == protocol.methodology_sha256
    altered = protocol.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256", "methodology_sha256"})
    altered["lanes"][0]["maximum_results"] += 1
    altered["change_reason"] = "Result-responsive increase"
    with pytest.raises(LiteratureConflictError, match="frozen"):
        store.append_protocol(altered, actor=_actor(), idempotency_key="protocol.fixture.r3.bad")
    child = store.start_search(
        {"search_run_id": "search.child", "protocol_id": administrative.protocol_id, "protocol_revision_sha256": administrative.record_sha256, "execution_lineage_id": administrative.execution_lineage_id, "lane": supporting_lane.lane, "query": "predeclared bounded child", "query_kind": "ADAPTIVE", "parent_search_run_id": started.search_run_id, "adaptive_depth": 1, "provider_id": "fixture-provider", "provider_trace_completeness": "COMPLETE_FOR_REQUEST"},
        actor=_actor(), idempotency_key="search.child.start",
    )
    with pytest.raises(LiteratureConflictError, match="depth"):
        store.start_search(
            {"search_run_id": "search.too-deep", "protocol_id": administrative.protocol_id, "protocol_revision_sha256": administrative.record_sha256, "execution_lineage_id": administrative.execution_lineage_id, "lane": supporting_lane.lane, "query": "too deep", "query_kind": "ADAPTIVE", "parent_search_run_id": child.search_run_id, "adaptive_depth": 2, "provider_id": "fixture-provider", "provider_trace_completeness": "COMPLETE_FOR_REQUEST"},
            actor=_actor(), idempotency_key="search.too-deep.start",
        )
    extension = _protocol(
        store,
        protocol_id="protocol.extension",
        lineage="lineage.extension",
        lineage_kind="RESULT_INFORMED_EXTENSION",
        parent_execution_lineage_id=protocol.execution_lineage_id,
        observed_result_set_sha256=finished.result_set_sha256,
        research_question="Result-informed extension, explicitly labeled",
    )
    assert extension.lineage_kind == "RESULT_INFORMED_EXTENSION"
    source_claim = _source(store, "extension", b"extension evidence")[-1]
    bad_completions = [
        {"lane": name, "execution_status": "TERMINAL", "obligation_status": "UNSATISFIED_PROVIDER_FAILURE", "search_run_refs": [], "gap_reason": "gap"}
        for name in LANES
    ]
    bad_completions[0] = {"lane": "SUPPORTING_OR_MOTIVATING", "execution_status": "TERMINAL", "obligation_status": "SATISFIED", "search_run_refs": [{"record_id": finished.record_id, "record_sha256": finished.record_sha256}], "gap_reason": None}
    with pytest.raises(LiteratureConflictError, match="exactly include all canonical lane searches"):
        store.append_dossier(
            {"dossier_id": "dossier.extension", "protocol_revision_sha256": extension.record_sha256, "execution_lineage_id": extension.execution_lineage_id, "search_completion_status": "TERMINATED_WITH_DECLARED_GAPS", "lane_completions": bad_completions, "claim_refs": [{"claim_id": source_claim.claim_id, "claim_revision_sha256": source_claim.record_sha256, "p2_role": "SUPPORTING"}], "evidence_relation_refs": [], "quality_descriptors": [], "material_statements": [{"statement_id": "statement.extension", "text": "Extension", "basis": "CLAIM_LINKED", "claim_refs": [{"record_id": source_claim.record_id, "record_sha256": source_claim.record_sha256}], "inference_rationale": None}], "taxonomy_proposal": {"classification_status": "CLASSIFIED", "taxonomy_ref": bundled_taxonomy_ref().model_dump(mode="json"), "economic_concepts": _concepts(), "unclassified_reason": None, "dimension_mappings": []}, "p2_entry_id": None, "prior_emission_receipt_sha256": None, "change_reason": "bad prior-lineage satisfaction"},
            actor=_actor(), idempotency_key="dossier.extension.r1",
        )


def _review(backlog: EdgeBacklogStore, entry_id: str, disposition: str, decision_id: str, canonical_entry_id=None):
    snapshot = backlog.duplicate_snapshot(entry_id)
    return backlog.record_human_decision(
        entry_id,
        disposition=disposition,
        duplicate_resolution="DISTINCT_EDGE" if disposition != "DUPLICATE" else "SAME_EDGE",
        candidate_snapshot_sha256=snapshot["snapshot_sha256"],
        reason_codes=["OTHER"],
        rationale=f"Fixture {disposition}",
        revisit_conditions=["Explicit human resume required"] if disposition == "SUSPENDED" else [],
        reviewer_id="owner",
        decision_id=decision_id,
        canonical_entry_id=canonical_entry_id,
    )


def _bound_freeze(store, protocol, support, contrary, receipt, dossier_id="dossier.fixture"):
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    return _dossier(store, protocol, [(support, "SUPPORTING"), (contrary, "CONTRADICTING")], dossier_id=dossier_id, p2_entry_id=entry_id, prior_receipt=receipt.record_sha256)[1]


def test_reviewed_continue_revises_same_entry_stales_review_and_records_sha(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _dossier_record, _freeze, _operation, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    decision = _review(backlog, entry_id, "REVIEWED_CONTINUE", "decision.reviewed")
    freeze = _bound_freeze(store, protocol, support, contrary, receipt)
    operation = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.reviewed", target_entry_id=entry_id, actor=_actor(), idempotency_key="emission.reviewed.prepared")
    assert operation.emission_action == "REVISE_SAME_ENTRY"
    assert operation.prior_staled_decision_sha256 == decision.record_sha256
    second = emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    assert second.entry_binding.record_id.startswith(entry_id + ".r")
    assert EdgeBacklogStore(root).entry_state(entry_id) == "UNREVIEWED"


@pytest.mark.parametrize("disposition", ["REJECTED", "DUPLICATE"])
def test_terminal_p2_entries_are_not_revised(tmp_path: Path, disposition: str) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    canonical_entry_id = None
    if disposition == "DUPLICATE":
        current = backlog.latest_entry(entry_id)
        entry_payload = current.model_dump(
            mode="json",
            include={"classification_status", "taxonomy_ref", "governance_scope", "p1_evidence_eligibility", "economic_concepts", "unclassified_reason", "observation_refs"},
        )
        canonical_entry_id = backlog.create_entry(
            entry_payload, actor_id="fixture", task_id="duplicate.target"
        ).entry_id
    _review(backlog, entry_id, disposition, "decision.terminal", canonical_entry_id)
    freeze = _bound_freeze(store, protocol, support, contrary, receipt)
    operation = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.terminal", actor=_actor(), idempotency_key="emission.terminal.prepared")
    assert operation.state == "BLOCKED"
    assert disposition in operation.blocked_reason


def test_suspended_blocks_bound_dossier_and_exact_resume_permits_revision(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    _review(backlog, entry_id, "SUSPENDED", "decision.suspended")
    freeze = _bound_freeze(store, protocol, support, contrary, receipt)
    blocked = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.suspended", actor=_actor(), idempotency_key="emission.suspended.prepared")
    assert blocked.state == "BLOCKED" and blocked.blocked_reason == "BOUND_ENTRY_SUSPENDED"
    backlog.resume_entry(entry_id, reason_codes=["NEW_INFORMATION"], rationale="Owner resumes", reviewer_id="owner", decision_id="decision.resumed")
    resumed = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.resumed", actor=_actor(), idempotency_key="emission.resumed.prepared")
    assert resumed.target_entry_state == "RESUMED"
    result = emit_prepared(root, operation_id=resumed.operation_id, actor=_actor())
    assert result.entry_binding.record_id.startswith(entry_id + ".r")


def test_current_hypothesis_link_blocks_bound_same_entry_revision(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    target = root / "hypothesis.json"
    target.write_text('{"id":"hypothesis.fixture"}\n')
    backlog.record_hypothesis_proposal_link(entry_id, hypothesis_id="hypothesis.fixture", target_locator=target, actor_id="engine", link_id="link.hypothesis")
    freeze = _bound_freeze(store, protocol, support, contrary, receipt)
    operation = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.hypothesis", actor=_actor(), idempotency_key="emission.hypothesis.prepared")
    assert operation.state == "BLOCKED"
    assert operation.blocked_reason == "BOUND_ENTRY_HAS_CURRENT_HYPOTHESIS_PROPOSAL"


def test_prepared_reservation_is_recoverable_reused_and_rejects_byte_drift(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol(store)
    work, version, capture, claim = _source(store, "reservation", b"reserved bytes")
    _, freeze = _dossier(store, protocol, [(claim, "SUPPORTING")])
    first = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.crash", actor=_actor(), idempotency_key="emission.crash.prepared")
    assert EdgeBacklogStore(root).records_by_task_id("emission.crash") == []
    receipt = reconcile_emission(root, operation_id=first.operation_id, actor=_actor())
    assert receipt.reservations[0].reservation_operation_id == first.operation_id
    identical_capture_payload = capture.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"})
    identical_capture_payload["capture_id"] = "capture.reservation.identical"
    identical = store.append_capture(identical_capture_payload, actor=_actor(), idempotency_key="capture.reservation.identical.r1")
    assert identical.content_sha256 == receipt.reservations[0].content_sha256
    identical_claim = store.append_claim(
        {"claim_id": "claim.reservation.identical", "work_id": work.work_id, "work_revision_sha256": work.record_sha256, "source_version_id": version.source_version_id, "source_version_revision_sha256": version.record_sha256, "capture_id": identical.capture_id, "capture_revision_sha256": identical.record_sha256, "content_sha256": identical.content_sha256, "extracted_representation_sha256": identical.extracted_representation_sha256, "location": _location(b"reserved bytes"), "statement": "reserved bytes", "statement_kind": "SOURCE_QUOTE", "source_epistemic_form": "ASSOCIATION_REPORTED", "reliability": "ACTIVE", "correction_reason": None, "conflict_refs": []},
        actor=_actor(), idempotency_key="claim.reservation.identical.r1",
    )
    _, reuse_freeze = _dossier(
        store, protocol, [(identical_claim, "SUPPORTING")], dossier_id="dossier.reuse"
    )
    reused = prepare_emission(
        root,
        freeze_id=reuse_freeze.freeze_id,
        operation_id="emission.reuse",
        actor=_actor(),
        idempotency_key="emission.reuse.prepared",
    )
    assert reused.reservations[0] == receipt.reservations[0]
    assert reused.reservations[0].capture_id == capture.capture_id
    assert len([item for item in store.records() if type(item).__name__ == "SourceVersionIdentityRevisionV1"]) == 1
    drift_content = store.put_artifact(b"different bytes", kind="artifacts")
    drift_text = store.put_artifact(b"different bytes", kind="extracted")
    drift_payload = dict(identical_capture_payload)
    drift_payload.update(capture_id="capture.reservation.drift", content_sha256=drift_content, extracted_representation_sha256=drift_text, content_bytes=15, extracted_bytes=15)
    drift = store.append_capture(drift_payload, actor=_actor(), idempotency_key="capture.reservation.drift.r1")
    drift_claim = store.append_claim(
        {"claim_id": "claim.reservation.drift", "work_id": work.work_id, "work_revision_sha256": work.record_sha256, "source_version_id": version.source_version_id, "source_version_revision_sha256": version.record_sha256, "capture_id": drift.capture_id, "capture_revision_sha256": drift.record_sha256, "content_sha256": drift.content_sha256, "extracted_representation_sha256": drift.extracted_representation_sha256, "location": _location(b"different bytes"), "statement": "different bytes", "statement_kind": "SOURCE_QUOTE", "source_epistemic_form": "OTHER", "reliability": "ACTIVE", "correction_reason": None, "conflict_refs": []},
        actor=_actor(), idempotency_key="claim.reservation.drift.r1",
    )
    _, drift_freeze = _dossier(store, protocol, [(drift_claim, "SUPPORTING")], dossier_id="dossier.drift")
    with pytest.raises(LiteratureConflictError, match="byte-different"):
        prepare_emission(root, freeze_id=drift_freeze.freeze_id, operation_id="emission.drift", actor=_actor(), idempotency_key="emission.drift.prepared")


def test_crash_after_p2_entry_write_recovers_without_duplicate_or_false_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphaquest.research.literature.emission as emission_module

    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol(store)
    claim = _source(store, "entry-crash", b"entry crash evidence")[-1]
    _, freeze = _dossier(store, protocol, [(claim, "SUPPORTING")])
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.entry-crash",
        actor=_actor(),
        idempotency_key="emission.entry-crash.prepared",
    )
    real_advance = emission_module._advance

    def crash_before_entry_journal(*args, **kwargs):
        if kwargs.get("state") == "ENTRY_WRITTEN":
            raise RuntimeError("synthetic crash after P2 entry write")
        return real_advance(*args, **kwargs)

    monkeypatch.setattr(emission_module, "_advance", crash_before_entry_journal)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    assert len(EdgeBacklogStore(root).records_by_task_id(operation.operation_id)) == 2
    monkeypatch.setattr(emission_module, "_advance", real_advance)
    receipt = reconcile_emission(root, operation_id=operation.operation_id, actor=_actor())
    assert receipt.operation_id == operation.operation_id
    assert len(
        [
            item
            for item in EdgeBacklogStore(root).records_by_task_id(operation.operation_id)
            if item.record_id.startswith("edge.")
        ]
    ) == 1


def test_human_same_version_resolution_freezes_one_canonical_reservation(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol(store)
    left = _source(store, "aliasa", b"byte-identical version")
    right = _source(store, "aliasb", b"byte-identical version")
    relationship = store.append_source_relationship(
        {
            "relationship_id": "relationship.same-version",
            "subject_kind": "SOURCE_VERSION",
            "subject_id": left[1].source_version_id,
            "predicate": "SAME_VERSION_AS",
            "object_kind": "SOURCE_VERSION",
            "object_id": right[1].source_version_id,
            "status": "ACTIVE",
            "assertion_evidence_refs": [],
            "superseded_by_relationship_id": None,
            "change_reason": "Human verified identical version identity",
        },
        actor=ActorProvenanceV1(actor_class="HUMAN_OWNER_RESEARCHER", actor_id="owner"),
        idempotency_key="relationship.same-version.r1",
    )
    _, freeze = _dossier(
        store, protocol, [(left[3], "SUPPORTING"), (right[3], "CONTRADICTING")], dossier_id="dossier.same-version"
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.same-version",
        actor=_actor(),
        idempotency_key="emission.same-version.prepared",
    )
    assert len(operation.reservations) == 1
    reservation = operation.reservations[0]
    assert reservation.canonical_source_version_id == "version.aliasa"
    assert reservation.p2_source_id == derive_p2_source_id("version.aliasa")
    assert reservation.relationship_state_sha256 == hashlib.sha256(
        canonical_json_bytes([relationship.record_sha256], trailing_lf=False)
    ).hexdigest()
    with pytest.raises(Exception, match="human-owned"):
        store.append_source_relationship(
            {
                "relationship_id": "relationship.forbidden-equivalence",
                "subject_kind": "SOURCE_VERSION",
                "subject_id": left[1].source_version_id,
                "predicate": "SAME_VERSION_AS",
                "object_kind": "SOURCE_VERSION",
                "object_id": right[1].source_version_id,
                "status": "ACTIVE",
                "assertion_evidence_refs": [],
                "superseded_by_relationship_id": None,
                "change_reason": "Not human",
            },
            actor=_actor(),
            idempotency_key="relationship.forbidden-equivalence.r1",
        )


def test_concurrent_different_reservations_cannot_both_append(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol(store)
    work, version, first_capture, first_claim = _source(store, "concurrent", b"representation one")
    second_content = store.put_artifact(b"representation two", kind="artifacts")
    second_extracted = store.put_artifact(b"representation two", kind="extracted")
    second_capture_payload = first_capture.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"})
    second_capture_payload.update(capture_id="capture.concurrent.second", content_sha256=second_content, extracted_representation_sha256=second_extracted, content_bytes=18, extracted_bytes=18)
    second_capture = store.append_capture(second_capture_payload, actor=_actor(), idempotency_key="capture.concurrent.second.r1")
    second_claim = store.append_claim(
        {"claim_id": "claim.concurrent.second", "work_id": work.work_id, "work_revision_sha256": work.record_sha256, "source_version_id": version.source_version_id, "source_version_revision_sha256": version.record_sha256, "capture_id": second_capture.capture_id, "capture_revision_sha256": second_capture.record_sha256, "content_sha256": second_capture.content_sha256, "extracted_representation_sha256": second_capture.extracted_representation_sha256, "location": _location(b"representation two"), "statement": "representation two", "statement_kind": "SOURCE_QUOTE", "source_epistemic_form": "OTHER", "reliability": "ACTIVE", "correction_reason": None, "conflict_refs": []},
        actor=_actor(), idempotency_key="claim.concurrent.second.r1",
    )
    freezes = [
        _dossier(store, protocol, [(first_claim, "SUPPORTING")], dossier_id="dossier.concurrent.first")[1],
        _dossier(store, protocol, [(second_claim, "SUPPORTING")], dossier_id="dossier.concurrent.second")[1],
    ]
    barrier = threading.Barrier(2)

    def append(index: int):
        barrier.wait()
        return prepare_emission(
            root,
            freeze_id=freezes[index - 1].freeze_id,
            operation_id=f"emission.race{index}",
            actor=_actor(),
            idempotency_key=f"emission.race{index}.prepared",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(append, index) for index in (1, 2)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(type(future.result()).__name__)
            except (LiteratureConflictError, LiteratureIntegrityError):
                outcomes.append("CONFLICT")
    assert sorted(outcomes) == ["CONFLICT", "P2EmissionOperationRevisionV1"]


def test_invalid_claim_withdrawal_preserves_history_and_removes_current_support(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    withdrawn_payload = support.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"})
    withdrawn_payload.update(reliability="WITHDRAWN_INVALID", correction_reason="Extraction was invalid; no replacement exists")
    withdrawn = store.append_claim(withdrawn_payload, actor=_actor(), idempotency_key="claim.supporting.withdrawn")
    freeze = _dossier(store, protocol, [(withdrawn, "CONTRADICTING"), (contrary, "CONTRADICTING")], p2_entry_id=entry_id, prior_receipt=receipt.record_sha256)[1]
    operation = prepare_emission(root, freeze_id=freeze.freeze_id, operation_id="emission.withdrawn", actor=_actor(), idempotency_key="emission.withdrawn.prepared")
    updated_receipt = emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    backlog = EdgeBacklogStore(root)
    latest_entry = backlog.latest_entry(entry_id)
    support_id = derive_p2_observation_id(support.claim_id)
    contrary_id = derive_p2_observation_id(contrary.claim_id)
    assert all(
        item.observation_id != support_id or item.role == "CONTRADICTING"
        for item in latest_entry.observation_refs
    )
    assert any(item.observation_id == contrary_id and item.role == "CONTRADICTING" for item in latest_entry.observation_refs)
    history = backlog._all_entry_revisions(entry_id)
    assert len(history) == 2
    assert any(item.observation_id == support_id for item in history[0].observation_refs)
    revised_observation = backlog.latest_observation(support_id)
    assert revised_observation.statement == support.statement.strip()
    assert revised_observation.statement_kind != "RESEARCHER_SUMMARY"
    assert any(value.startswith("P3_CONFLICT|INVALID_EXTRACTION_WITHDRAWN|") for value in revised_observation.known_conflicts)
    assert updated_receipt.entry_binding.record_sha256 == latest_entry.record_sha256


def test_corrected_extraction_revises_same_logical_p2_observation(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    corrected_payload = support.model_dump(mode="json", exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256"})
    corrected_payload.update(
        statement="Opening imbalance is associated with continuation in the source sample.",
        statement_kind="FAITHFUL_PARAPHRASE",
        reliability="CORRECTED",
        correction_reason="The original extraction overstated prediction as universal.",
    )
    corrected = store.append_claim(
        corrected_payload, actor=_actor(), idempotency_key="claim.supporting.corrected"
    )
    assert store.validate()["operational_status"] == "NEEDS_MANUAL_REVIEW"
    freeze = _dossier(
        store,
        protocol,
        [(corrected, "SUPPORTING"), (contrary, "CONTRADICTING")],
        p2_entry_id=entry_id,
        prior_receipt=receipt.record_sha256,
    )[1]
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.corrected",
        actor=_actor(),
        idempotency_key="emission.corrected.prepared",
    )
    emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    assert store.validate()["operational_status"] == "CURRENT_RESEARCH_CLEAN"
    observation_id = derive_p2_observation_id(support.claim_id)
    revisions = EdgeBacklogStore(root)._all_observation_revisions(observation_id)
    assert len(revisions) == 2
    assert revisions[1].statement == corrected.statement
    assert revisions[1].previous_revision_sha256 == revisions[0].record_sha256
    assert any(value.startswith("P3_CONFLICT|CLAIM_CORRECTED|") for value in revisions[1].known_conflicts)


def test_prefix_snapshot_excludes_later_append_and_self(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _store, _protocol_record, _support, _contrary, _d, _f, _o, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    entry_id = receipt.entry_binding.record_id.split(".r", 1)[0]
    original = backlog.latest_entry(entry_id)
    payload = original.model_dump(
        mode="json",
        include={"classification_status", "taxonomy_ref", "governance_scope", "p1_evidence_eligibility", "economic_concepts", "unclassified_reason", "observation_refs"},
    )
    later = backlog.create_entry(payload, actor_id="fixture", task_id="later.append")
    old = backlog.duplicate_snapshot_at_prefix(
        entry_id,
        entry_revision_sha256=original.record_sha256,
        before_append_sequence=original.append_sequence + 1,
    )
    current = backlog.duplicate_snapshot(entry_id)
    assert old["candidates"] == []
    assert all(item["candidate_id"] != entry_id for item in current["candidates"])
    assert any(item["candidate_id"] == later.entry_id for item in current["candidates"])


def test_idempotent_retry_returns_same_record_and_conflicting_intent_fails(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    first = _protocol(store)
    retry_payload = first.model_dump(
        mode="json",
        exclude={"schema_name", "record_id", "append_sequence", "previous_store_record_sha256", "recorded_at", "actor", "idempotency_key", "intent_sha256", "record_sha256", "revision", "previous_revision_sha256", "methodology_sha256"},
    )
    retried = store.append_protocol(
        retry_payload, actor=_actor(), idempotency_key=first.idempotency_key
    )
    assert retried.record_sha256 == first.record_sha256
    retry_payload["administrative_annotations"] = ["different intent"]
    with pytest.raises(LiteratureConflictError, match="idempotency"):
        store.append_protocol(retry_payload, actor=_actor(), idempotency_key=first.idempotency_key)


def test_all_thirteen_schema_families_are_checked_in_and_require_discriminator() -> None:
    files = sorted((REPO / "schemas").glob("literature-*.schema.json"))
    assert len(files) == len(CANONICAL_RECORD_TYPES) == 13
    for path in files:
        schema = json.loads(path.read_text())
        assert "schema" in schema["required"]
        assert "const" in schema["properties"]["schema"]


def test_zero_and_wrong_record_hash_are_rejected_for_every_canonical_family(tmp_path: Path) -> None:
    base = tmp_path / "base"
    _all_family_slice(_project(base))
    representatives = {}
    for path in _canonical_paths(base):
        record = json.loads(path.read_text())
        family = SCHEMA_TYPES[record["schema"]].family
        representatives.setdefault(family, path.relative_to(base))
    assert set(representatives) == {item.family for item in CANONICAL_RECORD_TYPES}

    for family, relative in sorted(representatives.items()):
        for label, bad_hash in (("zero", "0" * 64), ("wrong", "f" * 64)):
            root = tmp_path / f"{family}-{label}"
            shutil.copytree(base, root)
            path = root / relative
            record = json.loads(path.read_text())
            assert record["record_sha256"] != bad_hash
            record["record_sha256"] = bad_hash
            path.write_bytes(canonical_json_bytes(record))
            with pytest.raises(LiteratureIntegrityError, match="record"):
                LiteratureStore(root).records()


def test_zero_hash_last_and_middle_with_forged_successor_are_rejected(tmp_path: Path) -> None:
    base = tmp_path / "base"
    _all_family_slice(_project(base))

    last_root = tmp_path / "last"
    shutil.copytree(base, last_root)
    last_path = max(
        _canonical_paths(last_root),
        key=lambda path: json.loads(path.read_text())["append_sequence"],
    )
    last = json.loads(last_path.read_text())
    last["record_sha256"] = "0" * 64
    last_path.write_bytes(canonical_json_bytes(last))
    with pytest.raises(LiteratureIntegrityError, match="record"):
        LiteratureStore(last_root).validate()

    middle_root = tmp_path / "middle"
    shutil.copytree(base, middle_root)
    rows = [(path, json.loads(path.read_text())) for path in _canonical_paths(middle_root)]
    rows.sort(key=lambda item: item[1]["append_sequence"])
    middle_index = len(rows) // 2
    forged_predecessor = rows[middle_index - 1][1]["record_sha256"]
    for index in range(middle_index, len(rows)):
        path, record = rows[index]
        record["previous_store_record_sha256"] = forged_predecessor
        if index == middle_index:
            record["record_sha256"] = "0" * 64
        else:
            record["record_sha256"] = record_sha256(record)
        forged_predecessor = record["record_sha256"]
        path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(LiteratureIntegrityError, match="record"):
        LiteratureStore(middle_root).records()


def test_valid_canonical_record_passes_and_trusted_draft_never_reaches_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alphaquest.research.literature.store as store_module

    root = _project(tmp_path)
    writes: list[bytes] = []
    real_write = store_module.exclusive_write_repository_file

    def inspect_write(project_root, relative, data):
        if str(relative).startswith("research/literature/"):
            writes.append(data)
            decoded = json.loads(data)
            assert decoded["record_sha256"] != "0" * 64
            assert decoded["record_sha256"] == record_sha256(decoded)
        return real_write(project_root, relative, data)

    monkeypatch.setattr(store_module, "exclusive_write_repository_file", inspect_write)
    protocol = _protocol(LiteratureStore(root))
    assert writes
    assert type(protocol).model_validate_json(canonical_json_bytes(protocol)) == protocol
    assert LiteratureStore(root).validate()["status"] == "PASS"


@pytest.mark.parametrize("field", PROTOCOL_FROZEN_MUTATIONS)
def test_started_protocol_rejects_each_nonadministrative_contract_mutation(
    tmp_path: Path, field: str
) -> None:
    store = LiteratureStore(_project(tmp_path))
    _protocol(store, protocol_id="protocol.parent", lineage="lineage.parent")
    protocol = _protocol(store, protocol_id="protocol.target", lineage="lineage.target")
    lane = protocol.lanes[0]
    store.start_search(
        {
            "search_run_id": "search.freeze-probe",
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": lane.lane,
            "query": lane.required_initial_queries[0],
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": lane.provider_order[0],
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        },
        actor=_actor(),
        idempotency_key="search.freeze-probe.start",
    )
    payload = protocol.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS
        | {"record_id", "revision", "previous_revision_sha256", "methodology_sha256"},
    )
    _mutate_protocol_contract(payload, field)
    with pytest.raises((LiteratureConflictError, ValueError)):
        store.append_protocol(
            payload,
            actor=_actor(),
            idempotency_key=f"protocol.target.mutate-{field}",
        )


def test_full_reload_reconstructs_protocol_contract_freeze_for_every_field(tmp_path: Path) -> None:
    base = tmp_path / "base"
    store = LiteratureStore(_project(base))
    _protocol(store, protocol_id="protocol.parent", lineage="lineage.parent")
    protocol = _protocol(store, protocol_id="protocol.target", lineage="lineage.target")
    lane = protocol.lanes[0]
    store.start_search(
        {
            "search_run_id": "search.persisted-freeze",
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": lane.lane,
            "query": lane.required_initial_queries[0],
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": lane.provider_order[0],
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        },
        actor=_actor(),
        idempotency_key="search.persisted-freeze.start",
    )
    administrative = _protocol(
        store,
        protocol_id="protocol.target",
        lineage="lineage.target",
        administrative_annotations=["allowed annotation"],
        change_reason="Administrative revision",
    )

    for field in PROTOCOL_FROZEN_MUTATIONS:
        root = tmp_path / f"persisted-{field}"
        shutil.copytree(base, root)

        def mutate(record, *, selected=field):
            if record.get("record_id") != administrative.record_id:
                return
            _mutate_protocol_contract(record, selected)
            if selected != "capture_selection_rule":
                record["methodology_sha256"] = methodology_sha256(record)

        _rewrite_valid_hash_chains(root, mutate)
        with pytest.raises(LiteratureIntegrityError):
            LiteratureStore(root).validate(verify_artifacts=False)


@pytest.mark.parametrize(
    "field",
    (
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
    ),
)
def test_finish_search_rejects_each_started_identity_field(tmp_path: Path, field: str) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol(store)
    lane = protocol.lanes[0]
    search = store.start_search(
        {
            "search_run_id": "search.immutable",
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": lane.lane,
            "query": lane.required_initial_queries[0],
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": lane.provider_order[0],
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        },
        actor=_actor(),
        idempotency_key="search.immutable.start",
    )
    payload = _search_outcome("https://example.test/immutable")
    payload[field] = "mutated" if field not in {"adaptive_depth", "provider_attempt_ordinal"} else 2
    with pytest.raises(LiteratureConflictError, match="terminal outcome fields"):
        store.finish_search(
            search.search_run_id,
            payload,
            actor=_actor(),
            idempotency_key=f"search.immutable.finish-{field}",
        )


def test_full_reload_rejects_each_mutated_terminal_search_identity(tmp_path: Path) -> None:
    base = tmp_path / "base"
    store = LiteratureStore(_project(base))
    protocol = _protocol(store)
    lane = protocol.lanes[0]
    started = store.start_search(
        {
            "search_run_id": "search.persisted-identity",
            "protocol_id": protocol.protocol_id,
            "protocol_revision_sha256": protocol.record_sha256,
            "execution_lineage_id": protocol.execution_lineage_id,
            "lane": lane.lane,
            "query": lane.required_initial_queries[0],
            "query_kind": "INITIAL",
            "parent_search_run_id": None,
            "adaptive_depth": 0,
            "provider_id": lane.provider_order[0],
            "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
        },
        actor=_actor(),
        idempotency_key="search.persisted-identity.start",
    )
    terminal = store.finish_search(
        started.search_run_id,
        _search_outcome("https://example.test/persisted-identity"),
        actor=_actor(),
        idempotency_key="search.persisted-identity.finish",
    )
    values = {
        "search_run_id": "search.mutated",
        "protocol_id": "protocol.mutated",
        "protocol_revision_sha256": "a" * 64,
        "execution_lineage_id": "lineage.mutated",
        "lane": "NULL_OR_CONTRARY",
        "query": "mutated query",
        "query_kind": "ADAPTIVE",
        "parent_search_run_id": "search.parent",
        "adaptive_depth": 1,
        "provider_id": "mutated-provider",
        "provider_attempt_ordinal": 2,
    }
    for field, value in values.items():
        root = tmp_path / f"terminal-{field}"
        shutil.copytree(base, root)

        def mutate(record, *, selected=field, replacement=value):
            if record.get("record_id") == terminal.record_id:
                record[selected] = replacement

        _rewrite_valid_hash_chains(root, mutate)
        with pytest.raises(LiteratureIntegrityError):
            LiteratureStore(root).validate(verify_artifacts=False)


def test_audit_provider_order_probe_and_duplicate_results_cannot_satisfy_lane(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol_with_lane(
        store,
        {
            "provider_order": ["first", "second"],
            "minimum_provider_attempts": 2,
            "minimum_distinct_results_inspected": 2,
            "minimum_capture_attempts": 0,
            "maximum_queries": 1,
        },
    )
    with pytest.raises(LiteratureConflictError, match="provider order"):
        _start_lane_search(store, protocol, "search.second-first", "second")
    first = _start_lane_search(store, protocol, "search.first", "first")
    store.finish_search(
        first.search_run_id,
        _search_outcome("https://example.test/duplicate-result", capture=False),
        actor=_actor(),
        idempotency_key="search.first.finish",
    )
    second = _start_lane_search(store, protocol, "search.second", "second")
    store.finish_search(
        second.search_run_id,
        _search_outcome(
            "https://example.test/duplicate-result",
            capture=False,
            inspected_results=[
                _search_result(
                    "https://example.test/duplicate-result", provider_rank=2
                )
            ],
        ),
        actor=_actor(),
        idempotency_key="search.second.finish",
    )
    completion = store._derive_lane_completions(protocol, store.records())[0]
    assert completion["obligation_status"] != "SATISFIED"

    first_terminal = store.latest(type(first), first.search_run_id)

    def mutate(record):
        if record.get("record_id") == first_terminal.record_id:
            record["provider_id"] = "second"

    _rewrite_valid_hash_chains(root, mutate)
    with pytest.raises(LiteratureIntegrityError, match="search identity changed|provider order"):
        LiteratureStore(root).validate(verify_artifacts=False)


def test_dossier_cannot_omit_any_applicable_search(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol_with_lane(
        store,
        {
            "provider_order": ["first", "second"],
            "minimum_provider_attempts": 2,
            "minimum_capture_attempts": 0,
            "maximum_queries": 1,
        },
    )
    for ordinal, provider in enumerate(("first", "second"), start=1):
        search = _start_lane_search(store, protocol, f"search.omission-{ordinal}", provider)
        store.finish_search(
            search.search_run_id,
            _search_outcome(
                f"https://example.test/omission-{ordinal}",
                capture=False,
                inspected_results=[
                    _search_result(
                        f"https://example.test/omission-{ordinal}", provider_rank=ordinal
                    )
                ],
            ),
            actor=_actor(),
            idempotency_key=f"search.omission-{ordinal}.finish",
        )
    claim = _source(store, "omission", b"omission evidence")[-1]
    dossier, _freeze = _dossier(store, protocol, [(claim, "SUPPORTING")])
    payload = dossier.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    payload["lane_completions"][0]["search_run_refs"].pop()
    payload["change_reason"] = "Attempt to omit one inconvenient search"
    with pytest.raises(LiteratureConflictError, match="exactly include all canonical lane searches"):
        store.append_dossier(
            payload,
            actor=_actor(),
            idempotency_key="dossier.fixture.omitted-search",
        )


def test_capture_selection_deviation_and_false_saturation_fail_closed(tmp_path: Path) -> None:
    selection_root = tmp_path / "selection"
    selection_store = LiteratureStore(_project(selection_root))
    protocol = _protocol_with_lane(
        selection_store,
        {"minimum_capture_attempts": 1, "minimum_distinct_results_inspected": 2},
    )
    search = _start_lane_search(selection_store, protocol, "search.selection", "fixture-provider")
    results = [
        _search_result("https://example.test/rank-1", result_rank=1),
        _search_result("https://example.test/rank-2", result_rank=2),
    ]
    with pytest.raises(LiteratureIntegrityError, match="selection rule"):
        selection_store.finish_search(
            search.search_run_id,
            _search_outcome(
                "https://example.test/rank-1",
                inspected_results=results,
                capture_attempt_records=[
                    {
                        "capture_attempt_id": "attempt.selection-deviation",
                        "result_identity_sha256": results[1]["result_identity_sha256"],
                        "selection_ordinal": 1,
                    }
                ],
            ),
            actor=_actor(),
            idempotency_key="search.selection.finish",
        )

    saturation_root = tmp_path / "saturation"
    saturation_store = LiteratureStore(_project(saturation_root))
    saturation_protocol = _protocol_with_lane(saturation_store, {})
    saturation_search = _start_lane_search(
        saturation_store,
        saturation_protocol,
        "search.false-saturation",
        "fixture-provider",
    )
    with pytest.raises(LiteratureIntegrityError, match="no-new-work"):
        saturation_store.finish_search(
            saturation_search.search_run_id,
            _search_outcome(
                "https://example.test/new-work", saturation_claimed=True
            ),
            actor=_actor(),
            idempotency_key="search.false-saturation.finish",
        )


def test_source_version_cannot_migrate_between_works(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    work_a, version_a, _capture_a, _claim_a = _source(store, "version-a", b"version a")
    work_b = _source(store, "version-b", b"version b")[0]
    payload = version_a.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    payload.update(work_id=work_b.work_id, work_revision_sha256=work_b.record_sha256)
    payload["change_reason"] = "Attempt to move the version to another work"
    with pytest.raises(LiteratureConflictError, match="cannot migrate"):
        store.append_source_version(
            payload,
            actor=_actor(),
            idempotency_key="version.version-a.migrate",
        )
    assert store.latest(type(work_a), work_a.work_id).record_sha256 == work_a.record_sha256


@pytest.mark.parametrize(
    "field,value",
    (
        ("source_version_id", "version.other"),
        ("source_version_revision_sha256", "a" * 64),
        ("retrieval_locator", "https://example.test/moved"),
        ("captured_at", datetime(2026, 9, 2, tzinfo=timezone.utc)),
        ("access_basis", "OWNER_PROVIDED"),
        ("local_retention_permission", "UNKNOWN"),
        ("redistribution_permission", "ALLOWED"),
        ("external_model_processing_permission", "LOCAL_ONLY"),
    ),
)
def test_capture_completion_rejects_each_identity_or_request_mutation(
    tmp_path: Path, field: str, value
) -> None:
    store = LiteratureStore(_project(tmp_path))
    version = _source(store, "capture-owner", b"owner")[-3]
    started = _start_capture(store, version, "capture.started")
    with pytest.raises(LiteratureConflictError, match="terminal outcome fields"):
        store.append_capture(
            {
                "capture_id": started.capture_id,
                "status": "FAILED",
                "failure_reason": "fixture failure",
                field: value,
            },
            actor=_actor(),
            idempotency_key=f"capture.started.finish-{field}",
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "work_id",
        "work_revision",
        "version_id",
        "version_revision",
        "capture_id",
        "capture_revision",
        "content_sha256",
        "extracted_sha256",
    ),
)
def test_claim_append_rejects_each_broken_transitive_provenance_link(
    tmp_path: Path, mutation: str
) -> None:
    store = LiteratureStore(_project(tmp_path))
    work_a, version_a, capture_a, claim_a = _source(store, "chain-a", b"chain a")
    work_b, version_b, capture_b, _claim_b = _source(store, "chain-b", b"chain b")
    work_a_r2_payload = work_a.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    work_a_r2_payload["change_reason"] = "New metadata revision"
    work_a_r2 = store.append_work(
        work_a_r2_payload,
        actor=_actor(),
        idempotency_key="work.chain-a.r2",
    )
    payload = claim_a.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    payload["reliability"] = "CORRECTED"
    payload["correction_reason"] = "Provenance mutation probe"
    if mutation == "work_id":
        payload["work_id"] = work_b.work_id
    elif mutation == "work_revision":
        payload["work_revision_sha256"] = work_a_r2.record_sha256
    elif mutation == "version_id":
        payload["source_version_id"] = version_b.source_version_id
    elif mutation == "version_revision":
        payload["source_version_revision_sha256"] = version_b.record_sha256
    elif mutation == "capture_id":
        payload["capture_id"] = capture_b.capture_id
    elif mutation == "capture_revision":
        payload["capture_revision_sha256"] = capture_b.record_sha256
    elif mutation == "content_sha256":
        payload["content_sha256"] = capture_b.content_sha256
    elif mutation == "extracted_sha256":
        payload["extracted_representation_sha256"] = capture_b.extracted_representation_sha256
    with pytest.raises(LiteratureConflictError):
        store.append_claim(
            payload,
            actor=_actor(),
            idempotency_key=f"claim.chain-a.bad-{mutation}",
        )
    assert store.latest(type(claim_a), claim_a.claim_id).record_sha256 == claim_a.record_sha256


def test_full_reload_reconstructs_exact_work_version_capture_claim_chain(tmp_path: Path) -> None:
    base = tmp_path / "base"
    store = LiteratureStore(_project(base))
    work_a, version_a, capture_a, claim_a = _source(store, "persist-a", b"persist a")
    work_b, version_b, capture_b, _claim_b = _source(store, "persist-b", b"persist b")
    work_payload = work_a.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    work_payload["change_reason"] = "New metadata revision"
    work_a_r2 = store.append_work(
        work_payload,
        actor=_actor(),
        idempotency_key="work.persist-a.r2",
    )
    assert store.validate()["status"] == "PASS"
    mutations = {
        "work_id": {"work_id": work_b.work_id},
        "stale_work_revision": {"work_revision_sha256": work_a_r2.record_sha256},
        "version_id": {"source_version_id": version_b.source_version_id},
        "version_revision": {"source_version_revision_sha256": version_b.record_sha256},
        "capture_id": {"capture_id": capture_b.capture_id},
        "capture_revision": {"capture_revision_sha256": capture_b.record_sha256},
        "content": {"content_sha256": capture_b.content_sha256},
        "extracted": {
            "extracted_representation_sha256": capture_b.extracted_representation_sha256
        },
    }
    for label, changes in mutations.items():
        root = tmp_path / f"persisted-chain-{label}"
        shutil.copytree(base, root)

        def mutate(record, *, replacement=changes):
            if record.get("record_id") == claim_a.record_id:
                record.update(replacement)

        _rewrite_valid_hash_chains(root, mutate)
        with pytest.raises(LiteratureIntegrityError):
            LiteratureStore(root).validate(verify_artifacts=False)

    assert version_a.work_revision_sha256 == work_a.record_sha256
    assert capture_a.source_version_revision_sha256 == version_a.record_sha256


def test_full_reload_rejects_version_migration_and_capture_identity_migration(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    store = LiteratureStore(_project(base))
    work_a, version_a, _capture_a, _claim_a = _source(store, "migration-a", b"a")
    work_b, version_b, _capture_b, _claim_b = _source(store, "migration-b", b"b")
    version_payload = version_a.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    version_payload["change_reason"] = "Valid metadata-only revision"
    version_a_r2 = store.append_source_version(
        version_payload,
        actor=_actor(),
        idempotency_key="version.migration-a.r2",
    )
    capture = _start_capture(store, version_a_r2, "capture.migration-started")
    terminal = store.append_capture(
        {
            "capture_id": capture.capture_id,
            "status": "FAILED",
            "failure_reason": "fixture terminal state",
        },
        actor=_actor(),
        idempotency_key="capture.migration-started.finish",
    )

    version_root = tmp_path / "version-migration"
    shutil.copytree(base, version_root)

    def migrate_version(record):
        if record.get("record_id") == version_a_r2.record_id:
            record["work_id"] = work_b.work_id
            record["work_revision_sha256"] = work_b.record_sha256

    _rewrite_valid_hash_chains(version_root, migrate_version)
    with pytest.raises(LiteratureIntegrityError, match="migrated|work binding"):
        LiteratureStore(version_root).validate(verify_artifacts=False)

    capture_root = tmp_path / "capture-migration"
    shutil.copytree(base, capture_root)

    def migrate_capture(record):
        if record.get("record_id") == terminal.record_id:
            record["source_version_id"] = version_b.source_version_id
            record["source_version_revision_sha256"] = version_b.record_sha256

    _rewrite_valid_hash_chains(capture_root, migrate_capture)
    with pytest.raises(LiteratureIntegrityError, match="capture identity changed|source-version binding"):
        LiteratureStore(capture_root).validate(verify_artifacts=False)


def _active_retraction(store: LiteratureStore, target_claim, name: str):
    notice = _source(
        store,
        name,
        f"Retraction notice for {target_claim.claim_id}".encode(),
        category="OTHER",
    )
    relationship = store.append_source_relationship(
        {
            "relationship_id": f"relationship.{name}",
            "subject_kind": "SOURCE_VERSION",
            "subject_id": notice[1].source_version_id,
            "predicate": "RETRACTS",
            "object_kind": "SOURCE_VERSION",
            "object_id": target_claim.source_version_id,
            "status": "ACTIVE",
            "assertion_evidence_refs": [
                {"record_id": notice[3].record_id, "record_sha256": notice[3].record_sha256}
            ],
            "superseded_by_relationship_id": None,
            "change_reason": "Captured source-bound retraction notice",
        },
        actor=_actor(),
        idempotency_key=f"relationship.{name}.r1",
    )
    return notice, relationship


def test_active_source_correction_is_derived_even_when_claim_remains_active(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    entry_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    notice = _source(store, "support-correction-notice", b"Correction notice", category="OTHER")
    store.append_source_relationship(
        {
            "relationship_id": "relationship.support-correction",
            "subject_kind": "SOURCE_VERSION",
            "subject_id": notice[1].source_version_id,
            "predicate": "CORRECTS",
            "object_kind": "SOURCE_VERSION",
            "object_id": support.source_version_id,
            "status": "ACTIVE",
            "assertion_evidence_refs": [
                {"record_id": notice[3].record_id, "record_sha256": notice[3].record_sha256}
            ],
            "superseded_by_relationship_id": None,
            "change_reason": "Captured correction notice",
        },
        actor=_actor(),
        idempotency_key="relationship.support-correction.r1",
    )
    _dossier_record, freeze = _dossier(
        store,
        protocol,
        [(support, "SUPPORTING"), (notice[3], "SUPPORTING"), (contrary, "CONTRADICTING")],
        p2_entry_id=entry_id,
        prior_receipt=receipt.record_sha256,
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.source-correction",
        actor=_actor(),
        idempotency_key="emission.source-correction.prepared",
    )
    emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    backlog = EdgeBacklogStore(root)
    revised = backlog.latest_observation(derive_p2_observation_id(support.claim_id))
    assert support.reliability == "ACTIVE"
    assert any(
        marker.startswith("P3_CONFLICT|SOURCE_VERSION_CORRECTED|")
        for marker in revised.known_conflicts
    )
    latest_entry = backlog.latest_entry(entry_id)
    assert any(
        ref.observation_id == derive_p2_observation_id(notice[3].claim_id)
        for ref in latest_entry.observation_refs
    )


def test_active_retraction_overrides_active_claim_and_removes_current_positive_support(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    entry_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    notice, _relationship = _active_retraction(store, support, "support-retraction")
    assert support.reliability == "ACTIVE"
    assert store.validate()["operational_status"] == "NEEDS_MANUAL_REVIEW"
    with pytest.raises(LiteratureConflictError, match="retracted"):
        _dossier(
            store,
            protocol,
            [(support, "SUPPORTING"), (contrary, "CONTRADICTING")],
            dossier_id="dossier.retracted-positive",
        )

    _dossier_record, freeze = _dossier(
        store,
        protocol,
        [
            (support, "CONTRADICTING"),
            (notice[3], "SUPPORTING"),
            (contrary, "CONTRADICTING"),
        ],
        p2_entry_id=entry_id,
        prior_receipt=receipt.record_sha256,
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.retraction",
        actor=_actor(),
        idempotency_key="emission.retraction.prepared",
    )
    assert operation.operational_status == "CLEAN"
    result = emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    assert store.validate()["operational_status"] == "CURRENT_RESEARCH_CLEAN"
    backlog = EdgeBacklogStore(root)
    latest = backlog.latest_entry(entry_id)
    support_id = derive_p2_observation_id(support.claim_id)
    notice_id = derive_p2_observation_id(notice[3].claim_id)
    contrary_id = derive_p2_observation_id(contrary.claim_id)
    assert not any(
        ref.observation_id == support_id and ref.role in {"MOTIVATING", "SUPPORTING"}
        for ref in latest.observation_refs
    )
    assert any(
        ref.observation_id == support_id and ref.role == "CONTRADICTING"
        for ref in latest.observation_refs
    )
    assert any(ref.observation_id == notice_id for ref in latest.observation_refs)
    assert any(
        ref.observation_id == contrary_id and ref.role == "CONTRADICTING"
        for ref in latest.observation_refs
    )
    revised = backlog.latest_observation(support_id)
    assert any(marker.startswith("P3_CONFLICT|SOURCE_RETRACTED|") for marker in revised.known_conflicts)
    assert len(backlog._all_entry_revisions(entry_id)) == 2
    assert result.dependency_entry_bindings


def test_retracted_prior_contradiction_remains_contradicting_and_visible(tmp_path: Path) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    entry_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    notice, _relationship = _active_retraction(store, contrary, "contrary-retraction")
    _dossier_record, freeze = _dossier(
        store,
        protocol,
        [(support, "SUPPORTING"), (contrary, "CONTRADICTING"), (notice[3], "SUPPORTING")],
        p2_entry_id=entry_id,
        prior_receipt=receipt.record_sha256,
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.contrary-retraction",
        actor=_actor(),
        idempotency_key="emission.contrary-retraction.prepared",
    )
    emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    backlog = EdgeBacklogStore(root)
    contrary_id = derive_p2_observation_id(contrary.claim_id)
    latest = backlog.latest_entry(entry_id)
    assert any(
        ref.observation_id == contrary_id and ref.role == "CONTRADICTING"
        for ref in latest.observation_refs
    )
    revised = backlog.latest_observation(contrary_id)
    assert any(marker.startswith("P3_CONFLICT|SOURCE_RETRACTED|") for marker in revised.known_conflicts)


def _clone_entry(backlog: EdgeBacklogStore, entry_id: str, task_id: str):
    current = backlog.latest_entry(entry_id)
    payload = current.model_dump(
        mode="json",
        include={
            "classification_status",
            "taxonomy_ref",
            "governance_scope",
            "p1_evidence_eligibility",
            "economic_concepts",
            "unclassified_reason",
            "observation_refs",
        },
    )
    return backlog.create_entry(payload, actor_id="fixture", task_id=task_id)


def _corrected_claim(store: LiteratureStore, claim, *, suffix: str = "matrix"):
    payload = claim.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    payload.update(
        statement="Corrected deterministic source statement.",
        statement_kind="FAITHFUL_PARAPHRASE",
        reliability="CORRECTED",
        correction_reason="Correction dependency matrix",
    )
    return store.append_claim(
        payload,
        actor=_actor(),
        idempotency_key=f"{claim.claim_id}.corrected-{suffix}",
    )


@pytest.mark.parametrize(
    "dependent_state",
    (
        "UNREVIEWED",
        "REVIEWED_CONTINUE",
        "SUSPENDED",
        "REJECTED",
        "DUPLICATE",
        "HYPOTHESIS_PROPOSAL",
        "RESUMED",
    ),
)
def test_shared_observation_correction_covers_complete_dependency_matrix(
    tmp_path: Path, dependent_state: str
) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    primary_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    dependent = _clone_entry(backlog, primary_id, f"matrix.{dependent_state.lower()}")
    decision = None
    if dependent_state in {"REVIEWED_CONTINUE", "SUSPENDED", "REJECTED"}:
        decision = _review(
            backlog,
            dependent.entry_id,
            dependent_state,
            f"decision.{dependent_state.lower()}",
        )
    elif dependent_state == "DUPLICATE":
        decision = _review(
            backlog,
            dependent.entry_id,
            "DUPLICATE",
            "decision.duplicate",
            canonical_entry_id=primary_id,
        )
    elif dependent_state == "HYPOTHESIS_PROPOSAL":
        target = root / "hypothesis-matrix.json"
        target.write_text('{"id":"hypothesis.matrix"}\n')
        backlog.record_hypothesis_proposal_link(
            dependent.entry_id,
            hypothesis_id="hypothesis.matrix",
            target_locator=target,
            actor_id="owner",
            link_id="link.matrix-hypothesis",
        )
    elif dependent_state == "RESUMED":
        _review(backlog, dependent.entry_id, "SUSPENDED", "decision.before-resume")
        backlog.resume_entry(
            dependent.entry_id,
            reason_codes=["NEW_INFORMATION"],
            rationale="Resume dependency matrix entry",
            reviewer_id="owner",
            decision_id="decision.resumed-matrix",
        )

    before_dependent = backlog.latest_entry(dependent.entry_id)
    withdrawn_payload = support.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    withdrawn_payload.update(
        reliability="WITHDRAWN_INVALID",
        correction_reason="Invalid extraction dependency matrix",
    )
    corrected = store.append_claim(
        withdrawn_payload,
        actor=_actor(),
        idempotency_key=f"{support.claim_id}.withdrawn-{dependent_state.lower()}",
    )
    _dossier_record, freeze = _dossier(
        store,
        protocol,
        [(corrected, "CONTRADICTING"), (contrary, "CONTRADICTING")],
        p2_entry_id=primary_id,
        prior_receipt=receipt.record_sha256,
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id=f"emission.matrix-{dependent_state.lower()}",
        actor=_actor(),
        idempotency_key=f"emission.matrix-{dependent_state.lower()}.prepared",
    )
    impacts = {item.dependent_entry_id: item for item in operation.dependency_impacts}
    assert set(impacts) == {primary_id, dependent.entry_id}
    mutable = dependent_state in {"UNREVIEWED", "REVIEWED_CONTINUE", "RESUMED"}
    assert impacts[dependent.entry_id].impact_status == (
        "PLANNED_MUTABLE_REVISION" if mutable else "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"
    )
    if dependent_state == "REVIEWED_CONTINUE":
        assert decision is not None
        assert impacts[dependent.entry_id].prior_staled_decision_sha256 == decision.record_sha256
    result = emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    corrected_observation = backlog.latest_observation(derive_p2_observation_id(support.claim_id))
    latest_primary = backlog.latest_entry(primary_id)
    assert any(
        ref.observation_revision_sha256 == corrected_observation.record_sha256
        for ref in latest_primary.observation_refs
    )
    latest_dependent = backlog.latest_entry(dependent.entry_id)
    if mutable:
        assert latest_dependent.record_sha256 != before_dependent.record_sha256
        assert all(
            ref.observation_id != derive_p2_observation_id(support.claim_id)
            or ref.role == "CONTRADICTING"
            for ref in latest_dependent.observation_refs
        )
        assert result.operational_status == "CLEAN"
    else:
        assert latest_dependent.record_sha256 == before_dependent.record_sha256
        assert result.operational_status == "NEEDS_MANUAL_REVIEW"
        validation = LiteratureStore(root).validate()
        assert validation["operational_status"] == "NEEDS_MANUAL_REVIEW"
        assert validation["operational_reason"] == "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"


@pytest.mark.parametrize("concurrent_change", ("create", "revise"))
def test_dependency_snapshot_detects_concurrent_create_or_revision(
    tmp_path: Path, concurrent_change: str
) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, _d, _f, _o, receipt = _initial_slice(root)
    backlog = EdgeBacklogStore(root)
    primary_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    dependent = _clone_entry(backlog, primary_id, "concurrency.existing")
    corrected = _corrected_claim(store, support, suffix=concurrent_change)
    _dossier_record, freeze = _dossier(
        store,
        protocol,
        [(corrected, "SUPPORTING"), (contrary, "CONTRADICTING")],
        p2_entry_id=primary_id,
        prior_receipt=receipt.record_sha256,
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id=f"emission.concurrent-{concurrent_change}",
        actor=_actor(),
        idempotency_key=f"emission.concurrent-{concurrent_change}.prepared",
    )
    if concurrent_change == "create":
        _clone_entry(backlog, primary_id, "concurrency.created-after-prepare")
    else:
        payload = dependent.model_dump(
            mode="json",
            include={
                "classification_status",
                "taxonomy_ref",
                "governance_scope",
                "p1_evidence_eligibility",
                "economic_concepts",
                "unclassified_reason",
                "observation_refs",
            },
        )
        backlog.revise_entry(
            dependent.entry_id,
            payload,
            actor_id="fixture",
            task_id="concurrency.revised-after-prepare",
        )
    with pytest.raises(LiteratureConflictError, match="reverse-dependency snapshot changed"):
        emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    assert LiteratureStore(root).latest(type(operation), operation.operation_id).state == "CONFLICT"


@pytest.mark.parametrize(
    "field,value",
    (
        ("claim_refs", [{"record_id": "claim.extra.r000001", "record_sha256": "a" * 64}]),
        ("evidence_relation_refs", []),
        ("protocol_revision_sha256", "a" * 64),
        ("execution_lineage_id", "lineage.mutated"),
        ("search_completion_status", "COMPLETE_WITHIN_DECLARED_BOUNDS"),
        ("unsatisfied_lanes", []),
        ("taxonomy_proposal", {}),
        ("material_statements", []),
    ),
)
def test_freeze_rejects_every_caller_authored_authoritative_summary_field(
    tmp_path: Path, field: str, value
) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol(store)
    support = _source(store, "freeze-support", b"support")[-1]
    contrary = _source(store, "freeze-contrary", b"contrary")[-1]
    dossier, _freeze = _dossier(store, protocol, [(support, "SUPPORTING"), (contrary, "CONTRADICTING")])
    payload = {
        "freeze_id": f"freeze.probe-{field}",
        "dossier_id": dossier.dossier_id,
        "dossier_revision_sha256": dossier.record_sha256,
        field: value,
    }
    with pytest.raises(LiteratureConflictError, match="derives authoritative fields"):
        store.freeze_dossier(
            payload,
            actor=_actor(),
            idempotency_key=f"freeze.probe-{field}",
        )


def test_dossier_rejects_duplicate_claim_and_unrelated_nested_basis(tmp_path: Path) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol(store)
    support = _source(store, "basis-support", b"support")[-1]
    contrary = _source(store, "basis-contrary", b"contrary")[-1]
    dossier, _freeze = _dossier(store, protocol, [(support, "SUPPORTING"), (contrary, "CONTRADICTING")])
    unrelated = _source(store, "basis-unrelated", b"unrelated")[-1]
    base = dossier.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    duplicate = json.loads(json.dumps(base))
    duplicate["claim_refs"].append(duplicate["claim_refs"][0])
    duplicate["change_reason"] = "Duplicate exact claim probe"
    with pytest.raises(LiteratureConflictError, match="ordered and unique"):
        store.append_dossier(
            duplicate,
            actor=_actor(),
            idempotency_key="dossier.fixture.duplicate-claim",
        )
    unrelated_basis = json.loads(json.dumps(base))
    unrelated_basis["material_statements"][0]["claim_refs"] = [
        {"record_id": unrelated.record_id, "record_sha256": unrelated.record_sha256}
    ]
    unrelated_basis["change_reason"] = "Unrelated nested basis probe"
    with pytest.raises(LiteratureConflictError, match="outside the exact dossier claim set"):
        store.append_dossier(
            unrelated_basis,
            actor=_actor(),
            idempotency_key="dossier.fixture.unrelated-basis",
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "omit_reservation",
        "omit_observation",
        "reverse_observations",
        "change_role",
        "incomplete_entry",
        "alter_completion",
        "alter_gaps",
    ),
)
def test_append_rejects_nonexact_prepared_operation_projection(
    tmp_path: Path, mutation: str
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol(store)
    support = _source(store, "prepared-support", b"support")[-1]
    contrary = _source(store, "prepared-contrary", b"contrary")[-1]
    _dossier_record, freeze = _dossier(
        store, protocol, [(support, "SUPPORTING"), (contrary, "CONTRADICTING")]
    )
    prepared = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.prepared-authority",
        actor=_actor(),
        idempotency_key="emission.prepared-authority.prepared",
    )
    payload = prepared.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    payload["operation_id"] = f"emission.mutated-{mutation}"
    if mutation == "omit_reservation":
        payload["reservations"].pop()
    elif mutation == "omit_observation":
        payload["observation_plans"].pop()
    elif mutation == "reverse_observations":
        payload["observation_plans"].reverse()
    elif mutation == "change_role":
        payload["observation_plans"][0]["role"] = "MOTIVATING"
    elif mutation == "incomplete_entry":
        payload["entry_plan"]["observation_roles"].pop()
    elif mutation == "alter_completion":
        payload["search_completion_status"] = "COMPLETE_WITHIN_DECLARED_BOUNDS"
    elif mutation == "alter_gaps":
        payload["unsatisfied_lanes"].pop()
    with pytest.raises((LiteratureIntegrityError, LiteratureConflictError)):
        store.append_emission_operation(
            payload,
            actor=_actor(),
            idempotency_key=f"emission.mutated-{mutation}.prepared",
        )


def test_full_reload_reconstructs_exact_freeze_and_prepared_projection(tmp_path: Path) -> None:
    base = tmp_path / "base"
    store = LiteratureStore(_project(base))
    protocol = _protocol(store)
    support = _source(store, "persisted-freeze-support", b"support")[-1]
    contrary = _source(store, "persisted-freeze-contrary", b"contrary")[-1]
    _dossier_record, freeze = _dossier(
        store, protocol, [(support, "SUPPORTING"), (contrary, "CONTRADICTING")]
    )
    operation = prepare_emission(
        base,
        freeze_id=freeze.freeze_id,
        operation_id="emission.persisted-prepared",
        actor=_actor(),
        idempotency_key="emission.persisted-prepared.prepared",
    )

    freeze_root = tmp_path / "tampered-freeze"
    shutil.copytree(base, freeze_root)

    def mutate_freeze(record):
        if record.get("record_id") == freeze.record_id:
            record["p2_entry_id"] = "edge.unrelated"

    _rewrite_valid_hash_chains(freeze_root, mutate_freeze)
    with pytest.raises(LiteratureIntegrityError, match="freeze is not the exact"):
        LiteratureStore(freeze_root).validate(verify_artifacts=False)

    operation_root = tmp_path / "tampered-operation"
    shutil.copytree(base, operation_root)

    def mutate_operation(record):
        if record.get("record_id") == operation.record_id:
            record["observation_plans"].pop()

    _rewrite_valid_hash_chains(operation_root, mutate_operation)
    with pytest.raises(LiteratureIntegrityError, match="observation plans"):
        LiteratureStore(operation_root).validate(verify_artifacts=False)


def test_generated_schemas_reject_zero_hash_for_all_families_and_new_contract_omissions(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    _all_family_slice(root)
    checked = set()
    for path in _canonical_paths(root):
        record = json.loads(path.read_text())
        record_type = SCHEMA_TYPES[record["schema"]]
        if record_type.family in checked:
            continue
        schema_path = next(
            item
            for item in (REPO / "schemas").glob("literature-*.schema.json")
            if json.loads(item.read_text())["properties"]["schema"]["const"] == record["schema"]
        )
        validator = Draft202012Validator(json.loads(schema_path.read_text()))
        assert list(validator.iter_errors(record)) == []
        zero = dict(record)
        zero["record_sha256"] = "0" * 64
        assert list(validator.iter_errors(zero))
        if record_type.family == "searches":
            missing = dict(record)
            missing.pop("provider_attempt_ordinal")
            assert list(validator.iter_errors(missing))
        if record_type.family == "dossier-freezes":
            missing = dict(record)
            missing.pop("material_statements")
            assert list(validator.iter_errors(missing))
        checked.add(record_type.family)
    assert checked == {item.family for item in CANONICAL_RECORD_TYPES}


def test_current_claim_head_invalidates_dependencies_stale_dossier_and_old_freeze(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    store, protocol, support, contrary, historical_dossier, historical_freeze, _operation, receipt = (
        _initial_slice(root)
    )
    backlog = EdgeBacklogStore(root)
    primary_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    dependent = _clone_entry(backlog, primary_id, "current-head.second-mutable")
    historical_dossier_sha = historical_dossier.record_sha256
    historical_freeze_sha = historical_freeze.record_sha256

    withdrawn_payload = support.model_dump(
        mode="json",
        exclude=MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"},
    )
    withdrawn_payload.update(
        reliability="WITHDRAWN_INVALID",
        correction_reason="Re-audit current-head invalidation probe",
    )
    withdrawn = store.append_claim(
        withdrawn_payload,
        actor=_actor(),
        idempotency_key="claim.current-head.withdrawn",
    )

    validation = store.validate()
    assert validation["operational_status"] == "NEEDS_MANUAL_REVIEW"
    assert {
        item["dependent_entry_id"]
        for item in validation["unresolved_dependency_impacts"]
    } == {primary_id, dependent.entry_id}
    old_eligibility = next(
        item
        for item in validation["freeze_emission_eligibility"]
        if item["freeze_id"] == historical_freeze.freeze_id
    )
    assert old_eligibility["emission_eligibility"] == "STALE_INELIGIBLE"

    with pytest.raises(LiteratureConflictError, match="eligible logical claim head"):
        _dossier(
            store,
            protocol,
            [(support, "SUPPORTING"), (contrary, "CONTRADICTING")],
            dossier_id="dossier.stale-positive",
        )
    with pytest.raises(LiteratureConflictError, match="stale for new P2 emission"):
        prepare_emission(
            root,
            freeze_id=historical_freeze.freeze_id,
            operation_id="emission.stale-old-freeze",
            actor=_actor(),
            idempotency_key="emission.stale-old-freeze.prepared",
        )

    _current_dossier, current_freeze = _dossier(
        store,
        protocol,
        [(withdrawn, "CONTRADICTING"), (contrary, "CONTRADICTING")],
        p2_entry_id=primary_id,
        prior_receipt=receipt.record_sha256,
    )
    correction = prepare_emission(
        root,
        freeze_id=current_freeze.freeze_id,
        operation_id="emission.current-head-correction",
        actor=_actor(),
        idempotency_key="emission.current-head-correction.prepared",
    )
    assert {
        item.dependent_entry_id for item in correction.dependency_impacts
    } == {primary_id, dependent.entry_id}
    emit_prepared(root, operation_id=correction.operation_id, actor=_actor())

    final_validation = store.validate()
    assert final_validation["operational_status"] == "CURRENT_RESEARCH_CLEAN"
    assert final_validation["unresolved_dependency_impacts"] == []
    assert store.get(historical_dossier.record_id).record_sha256 == historical_dossier_sha
    assert store.get(historical_freeze.record_id).record_sha256 == historical_freeze_sha


@pytest.mark.parametrize("donor_status", ("FAILED", "SUCCEEDED"))
def test_search_capture_must_belong_to_same_eligible_search_run(
    tmp_path: Path, donor_status: str
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol_with_lane(
        store,
        {
            "provider_order": ["first", "second"],
            "minimum_provider_attempts": 2,
            "minimum_distinct_results_inspected": 2,
            "minimum_capture_attempts": 1,
            "maximum_queries": 1,
        },
    )
    donor_result = _search_result(
        "https://example.test/donor-result", provider_rank=1
    )
    donor = _start_lane_search(store, protocol, "search.donor", "first")
    store.finish_search(
        donor.search_run_id,
        _search_outcome(
            "https://example.test/donor-result",
            status=donor_status,
            inspected_results=[donor_result],
            capture_attempt_records=[],
            failure_reason="provider failed after inspection"
            if donor_status == "FAILED"
            else None,
        ),
        actor=_actor(),
        idempotency_key="search.donor.finish",
    )
    receiver_result = _search_result(
        "https://example.test/receiver-result", provider_rank=2
    )
    receiver = _start_lane_search(store, protocol, "search.receiver", "second")
    with pytest.raises(LiteratureConflictError, match="same search run"):
        store.finish_search(
            receiver.search_run_id,
            _search_outcome(
                "https://example.test/receiver-result",
                inspected_results=[receiver_result],
                capture_attempt_records=[
                    {
                        "capture_attempt_id": "attempt.cross-run",
                        "result_identity_sha256": donor_result[
                            "result_identity_sha256"
                        ],
                        "selection_ordinal": 1,
                    }
                ],
            ),
            actor=_actor(),
            idempotency_key="search.receiver.finish",
        )
    if donor_status == "FAILED":
        store.finish_search(
            receiver.search_run_id,
            _search_outcome(
                "https://example.test/receiver-result",
                inspected_results=[receiver_result],
            ),
            actor=_actor(),
            idempotency_key="search.receiver.valid-finish",
        )
        completion = store._derive_lane_completions(protocol, store.records())[0]
        assert completion["obligation_status"] != "SATISFIED"


def test_search_capture_unknown_result_and_failed_run_capture_are_rejected(
    tmp_path: Path,
) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol_with_lane(store, {"minimum_capture_attempts": 0})
    search = _start_lane_search(store, protocol, "search.unknown-capture", "fixture-provider")
    result = _search_result("https://example.test/known-result")
    with pytest.raises(LiteratureConflictError, match="same search run"):
        store.finish_search(
            search.search_run_id,
            _search_outcome(
                "https://example.test/known-result",
                inspected_results=[result],
                capture_attempt_records=[
                    {
                        "capture_attempt_id": "attempt.unknown-result",
                        "result_identity_sha256": "a" * 64,
                        "selection_ordinal": 1,
                    }
                ],
            ),
            actor=_actor(),
            idempotency_key="search.unknown-capture.finish",
        )
    with pytest.raises(LiteratureConflictError, match="failed search runs"):
        store.finish_search(
            search.search_run_id,
            _search_outcome(
                "https://example.test/known-result",
                status="FAILED",
                failure_reason="provider failed after retrieval",
                inspected_results=[result],
                capture_attempt_records=[
                    {
                        "capture_attempt_id": "attempt.failed-run",
                        "result_identity_sha256": result["result_identity_sha256"],
                        "selection_ordinal": 1,
                    }
                ],
            ),
            actor=_actor(),
            idempotency_key="search.failed-capture.finish",
        )


@pytest.mark.parametrize("second_ordinal", (1, 3))
def test_search_capture_selection_ordinals_are_unique_and_gap_free(
    tmp_path: Path, second_ordinal: int
) -> None:
    store = LiteratureStore(_project(tmp_path))
    protocol = _protocol_with_lane(
        store,
        {
            "provider_order": ["first", "second"],
            "minimum_provider_attempts": 2,
            "minimum_distinct_results_inspected": 2,
            "minimum_capture_attempts": 2,
            "maximum_queries": 1,
        },
    )
    first_result = _search_result("https://example.test/ordinal-first", provider_rank=1)
    first = _start_lane_search(store, protocol, "search.ordinal-first", "first")
    store.finish_search(
        first.search_run_id,
        _search_outcome(
            "https://example.test/ordinal-first",
            inspected_results=[first_result],
        ),
        actor=_actor(),
        idempotency_key="search.ordinal-first.finish",
    )
    second_result = _search_result("https://example.test/ordinal-second", provider_rank=2)
    second = _start_lane_search(store, protocol, "search.ordinal-second", "second")
    with pytest.raises(LiteratureIntegrityError, match="gap-free"):
        store.finish_search(
            second.search_run_id,
            _search_outcome(
                "https://example.test/ordinal-second",
                inspected_results=[second_result],
                capture_attempt_records=[
                    {
                        "capture_attempt_id": "attempt.ordinal-second",
                        "result_identity_sha256": second_result[
                            "result_identity_sha256"
                        ],
                        "selection_ordinal": second_ordinal,
                    }
                ],
            ),
            actor=_actor(),
            idempotency_key="search.ordinal-second.finish",
        )


def test_search_capture_order_uses_explicit_ordinals_not_search_ids_and_reloads(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol_with_lane(
        store,
        {
            "provider_order": ["first", "second"],
            "minimum_provider_attempts": 2,
            "minimum_distinct_results_inspected": 2,
            "minimum_capture_attempts": 2,
            "maximum_queries": 1,
        },
    )
    first_result = _search_result("https://example.test/ordered-first", provider_rank=1)
    first = _start_lane_search(store, protocol, "search.z-first", "first")
    store.finish_search(
        first.search_run_id,
        _search_outcome(
            "https://example.test/ordered-first",
            inspected_results=[first_result],
        ),
        actor=_actor(),
        idempotency_key="search.z-first.finish",
    )
    second_result = _search_result("https://example.test/ordered-second", provider_rank=2)
    second = _start_lane_search(store, protocol, "search.a-second", "second")
    store.finish_search(
        second.search_run_id,
        _search_outcome(
            "https://example.test/ordered-second",
            inspected_results=[second_result],
            capture_attempt_records=[
                {
                    "capture_attempt_id": "attempt.ordered-second",
                    "result_identity_sha256": second_result["result_identity_sha256"],
                    "selection_ordinal": 2,
                }
            ],
        ),
        actor=_actor(),
        idempotency_key="search.a-second.finish",
    )
    completion = LiteratureStore(root)._derive_lane_completions(
        protocol, LiteratureStore(root).records()
    )[0]
    assert completion["obligation_status"] == "SATISFIED"

    tampered = tmp_path / "cross-run-persisted"
    shutil.copytree(root, tampered)

    def mutate(record):
        if record.get("record_id") == f"{second.search_run_id}.r000002":
            record["capture_attempt_records"][0]["result_identity_sha256"] = (
                first_result["result_identity_sha256"]
            )

    _rewrite_valid_hash_chains(tampered, mutate)
    with pytest.raises(LiteratureIntegrityError, match="same search run"):
        LiteratureStore(tampered).validate(verify_artifacts=False)


def test_search_two_phase_idempotency_precedes_lifecycle_rejection(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol_with_lane(store, {})
    start_payload = {
        "search_run_id": "search.idempotent",
        "protocol_id": protocol.protocol_id,
        "protocol_revision_sha256": protocol.record_sha256,
        "execution_lineage_id": protocol.execution_lineage_id,
        "lane": protocol.lanes[0].lane,
        "query": protocol.lanes[0].required_initial_queries[0],
        "query_kind": "INITIAL",
        "parent_search_run_id": None,
        "adaptive_depth": 0,
        "provider_id": "fixture-provider",
        "provider_trace_completeness": "COMPLETE_FOR_REQUEST",
    }
    start_key = "search.idempotent.start"
    started = store.start_search(
        start_payload, actor=_actor(), idempotency_key=start_key
    )
    with pytest.raises(LiteratureConflictError, match="phase"):
        store.start_search(
            {**start_payload, "search_run_id": "search.wrong-family-key"},
            actor=_actor(),
            idempotency_key=protocol.idempotency_key,
        )
    assert store.start_search(
        start_payload, actor=_actor(), idempotency_key=start_key
    ).record_sha256 == started.record_sha256
    assert LiteratureStore(root).start_search(
        start_payload, actor=_actor(), idempotency_key=start_key
    ).record_sha256 == started.record_sha256
    changed_start = {**start_payload, "provider_trace_completeness": "UNKNOWN"}
    with pytest.raises(LiteratureConflictError, match="idempotency"):
        store.start_search(changed_start, actor=_actor(), idempotency_key=start_key)
    with pytest.raises(LiteratureConflictError, match="phase"):
        store.finish_search(
            started.search_run_id,
            _search_outcome("https://example.test/idempotent"),
            actor=_actor(),
            idempotency_key=start_key,
        )
    with pytest.raises(LiteratureConflictError, match="idempotency"):
        store.start_search(
            {**start_payload, "search_run_id": "search.idempotent-other"},
            actor=_actor(),
            idempotency_key=start_key,
        )

    terminal_payload = _search_outcome("https://example.test/idempotent")
    finish_key = "search.idempotent.finish"
    terminal = store.finish_search(
        started.search_run_id,
        terminal_payload,
        actor=_actor(),
        idempotency_key=finish_key,
    )
    assert store.finish_search(
        started.search_run_id,
        terminal_payload,
        actor=_actor(),
        idempotency_key=finish_key,
    ).record_sha256 == terminal.record_sha256
    assert LiteratureStore(root).finish_search(
        started.search_run_id,
        terminal_payload,
        actor=_actor(),
        idempotency_key=finish_key,
    ).record_sha256 == terminal.record_sha256
    changed_terminal = {**terminal_payload, "elapsed_seconds": 2}
    with pytest.raises(LiteratureConflictError, match="idempotency"):
        store.finish_search(
            started.search_run_id,
            changed_terminal,
            actor=_actor(),
            idempotency_key=finish_key,
        )
    with pytest.raises(LiteratureConflictError, match="phase"):
        store.start_search(
            start_payload,
            actor=_actor(),
            idempotency_key=finish_key,
        )
    assert len(
        [
            item
            for item in store.records()
            if getattr(item, "search_run_id", None) == started.search_run_id
        ]
    ) == 2


@pytest.mark.parametrize("terminal_status", ("PARTIAL", "FAILED"))
def test_search_partial_and_failed_terminal_retries_are_idempotent(
    tmp_path: Path, terminal_status: str
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    protocol = _protocol_with_lane(store, {"minimum_capture_attempts": 0})
    started = _start_lane_search(
        store, protocol, f"search.retry-{terminal_status.lower()}", "fixture-provider"
    )
    payload = _search_outcome(
        f"https://example.test/retry-{terminal_status.lower()}",
        status=terminal_status,
        capture_attempt_records=[],
        failure_reason="terminal provider failure" if terminal_status == "FAILED" else None,
    )
    key = f"search.retry-{terminal_status.lower()}.finish"
    terminal = store.finish_search(
        started.search_run_id, payload, actor=_actor(), idempotency_key=key
    )
    assert LiteratureStore(root).finish_search(
        started.search_run_id, payload, actor=_actor(), idempotency_key=key
    ).record_sha256 == terminal.record_sha256


def test_capture_two_phase_idempotency_precedes_lifecycle_rejection(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    store = LiteratureStore(root)
    version = _source(store, "capture-idempotency-source", b"source")[-3]
    capture_id = "capture.idempotent-two-phase"
    start_payload = {
        "capture_id": capture_id,
        "source_version_id": version.source_version_id,
        "source_version_revision_sha256": version.record_sha256,
        "retrieval_locator": f"https://example.test/{capture_id}",
        "status": "STARTED",
        "captured_at": NOW,
        "access_basis": "OPEN_PUBLIC",
        "local_retention_permission": "ALLOWED",
        "redistribution_permission": "RESTRICTED",
        "external_model_processing_permission": "ALLOWED_EXTERNAL_PROCESSOR",
        "media_type": None,
        "content_sha256": None,
        "content_bytes": None,
        "extracted_representation_sha256": None,
        "extracted_bytes": None,
        "extractor_id": None,
        "extractor_version": None,
        "extractor_config_sha256": None,
        "failure_reason": None,
    }
    start_key = "capture.idempotent-two-phase.start"
    started = store.append_capture(
        start_payload, actor=_actor(), idempotency_key=start_key
    )
    with pytest.raises(LiteratureConflictError, match="family"):
        store.append_capture(
            {**start_payload, "capture_id": "capture.wrong-family-key"},
            actor=_actor(),
            idempotency_key=version.idempotency_key,
        )
    assert store.append_capture(
        start_payload, actor=_actor(), idempotency_key=start_key
    ).record_sha256 == started.record_sha256
    assert LiteratureStore(root).append_capture(
        start_payload, actor=_actor(), idempotency_key=start_key
    ).record_sha256 == started.record_sha256
    with pytest.raises(LiteratureConflictError, match="idempotency"):
        store.append_capture(
            {**start_payload, "retrieval_locator": "https://example.test/changed"},
            actor=_actor(),
            idempotency_key=start_key,
        )
    terminal_payload = {
        "capture_id": capture_id,
        "status": "FAILED",
        "failure_reason": "deterministic fixture failure",
    }
    with pytest.raises(LiteratureConflictError, match="phase"):
        store.append_capture(
            terminal_payload, actor=_actor(), idempotency_key=start_key
        )

    finish_key = "capture.idempotent-two-phase.finish"
    terminal = store.append_capture(
        terminal_payload, actor=_actor(), idempotency_key=finish_key
    )
    assert store.append_capture(
        terminal_payload, actor=_actor(), idempotency_key=finish_key
    ).record_sha256 == terminal.record_sha256
    assert LiteratureStore(root).append_capture(
        terminal_payload, actor=_actor(), idempotency_key=finish_key
    ).record_sha256 == terminal.record_sha256
    with pytest.raises(LiteratureConflictError, match="idempotency"):
        store.append_capture(
            {**terminal_payload, "failure_reason": "changed intent"},
            actor=_actor(),
            idempotency_key=finish_key,
        )
    with pytest.raises(LiteratureConflictError, match="phase"):
        store.append_capture(
            start_payload, actor=_actor(), idempotency_key=finish_key
        )
    with pytest.raises(LiteratureConflictError, match="object"):
        store.append_capture(
            {**terminal_payload, "capture_id": "capture.other-object"},
            actor=_actor(),
            idempotency_key=finish_key,
        )
    assert len(
        [
            item
            for item in store.records()
            if getattr(item, "capture_id", None) == capture_id
        ]
    ) == 2


def _receipt_with_duplicate_candidates(root: Path):
    store, protocol, _support, contrary, _dossier_record, _freeze, _operation, receipt = (
        _initial_slice(root)
    )
    backlog = EdgeBacklogStore(root)
    initial_entry_id = receipt.entry_binding.record_id.rsplit(".r", 1)[0]
    _clone_entry(backlog, initial_entry_id, "duplicate-semantic.first")
    _clone_entry(backlog, initial_entry_id, "duplicate-semantic.second")
    query_claim = _source(
        store,
        "duplicate-semantic-query",
        (FIXTURES / "supporting.txt").read_bytes(),
    )[-1]
    _dossier_record, freeze = _dossier(
        store,
        protocol,
        [(query_claim, "SUPPORTING"), (contrary, "CONTRADICTING")],
        dossier_id="dossier.duplicate-semantic-query",
    )
    operation = prepare_emission(
        root,
        freeze_id=freeze.freeze_id,
        operation_id="emission.duplicate-semantic-query",
        actor=_actor(),
        idempotency_key="emission.duplicate-semantic-query.prepared",
    )
    query_receipt = emit_prepared(root, operation_id=operation.operation_id, actor=_actor())
    assert len(query_receipt.duplicate_snapshot.candidate_bindings) >= 2
    return query_receipt


@pytest.mark.parametrize(
    "mutation",
    (
        "entry_revision_sha256",
        "query_entry_id",
        "before_append_sequence",
        "entry_link_chain_sha256",
        "historical_source_commit",
        "historical_universe_sha256",
        "candidate_id",
        "candidate_record_sha256",
        "candidate_ordering",
        "snapshot_sha256",
        "self_candidate",
        "omit_candidate",
    ),
)
def test_completed_duplicate_snapshot_is_reconstructed_from_exact_p2_prefix(
    tmp_path: Path, mutation: str
) -> None:
    base = tmp_path / "base"
    receipt = _receipt_with_duplicate_candidates(_project(base))
    root = tmp_path / mutation
    shutil.copytree(base, root)
    replacement_sha = "a" * 64

    def mutate(record):
        same_operation = record.get("operation_id") == receipt.operation_id
        is_operation = record.get("schema") == (
            "alphaquest.literature-p2-emission-operation-revision/v1"
        )
        is_receipt = record.get("schema") == (
            "alphaquest.literature-p2-emission-receipt/v1"
        )
        if not same_operation or not (is_operation or is_receipt):
            return
        if mutation == "entry_revision_sha256" and (
            is_receipt
            or record.get("state") in {"ENTRY_WRITTEN", "SNAPSHOT_BOUND", "COMPLETED"}
        ):
            record["entry_binding"]["record_sha256"] = replacement_sha
        snapshot = record.get("duplicate_snapshot")
        if snapshot is None:
            return
        if mutation == "entry_revision_sha256":
            snapshot["entry_revision_sha256"] = replacement_sha
        elif mutation == "query_entry_id":
            snapshot["entry_id"] = "edge.semantic-query-other"
        elif mutation == "before_append_sequence":
            snapshot["before_append_sequence"] += 1
        elif mutation == "entry_link_chain_sha256":
            snapshot["entry_link_chain_sha256"] = replacement_sha
        elif mutation == "historical_source_commit":
            snapshot["historical_source_commit"] = "f" * 40
        elif mutation == "historical_universe_sha256":
            snapshot["historical_universe_sha256"] = replacement_sha
        elif mutation == "candidate_id":
            snapshot["candidate_bindings"][0]["candidate_id"] = "edge.semantic-mutated"
        elif mutation == "candidate_record_sha256":
            snapshot["candidate_bindings"][0]["candidate_record_sha256"] = replacement_sha
        elif mutation == "candidate_ordering":
            snapshot["candidate_bindings"].reverse()
        elif mutation == "snapshot_sha256":
            snapshot["snapshot_sha256"] = replacement_sha
        elif mutation == "self_candidate":
            self_binding = dict(snapshot["candidate_bindings"][0])
            self_binding["candidate_id"] = snapshot["entry_id"]
            snapshot["candidate_bindings"].append(self_binding)
        elif mutation == "omit_candidate":
            snapshot["candidate_bindings"].pop()

    _rewrite_valid_hash_chains(root, mutate)
    with pytest.raises(LiteratureIntegrityError):
        LiteratureStore(root).validate(verify_artifacts=False)


def test_later_emission_stage_cannot_change_an_already_written_p2_binding(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    receipt = _receipt_with_duplicate_candidates(_project(base))
    root = tmp_path / "changed-later-binding"
    shutil.copytree(base, root)

    def mutate(record):
        if (
            record.get("operation_id") == receipt.operation_id
            and record.get("state") == "COMPLETED"
        ):
            record["entry_binding"]["record_sha256"] = "b" * 64

    _rewrite_valid_hash_chains(root, mutate)
    with pytest.raises(LiteratureIntegrityError, match="bindings are immutable"):
        LiteratureStore(root).validate(verify_artifacts=False)


def test_full_validation_fails_explicitly_when_p2_snapshot_dependency_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    _receipt_with_duplicate_candidates(root)

    def unavailable(*_args, **_kwargs):
        raise EdgeBacklogIntegrityError("fixture P2 dependency unavailable")

    monkeypatch.setattr(EdgeBacklogStore, "duplicate_snapshot_at_prefix", unavailable)
    with pytest.raises(
        LiteratureIntegrityError, match="P2_SEMANTIC_DEPENDENCY_UNAVAILABLE"
    ):
        LiteratureStore(root).validate(verify_artifacts=False)
