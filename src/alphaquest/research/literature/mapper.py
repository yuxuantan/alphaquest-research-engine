"""Pure, deterministic P3-to-P2 projection functions.

No function in this module writes either canonical store.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Iterable, Mapping, Sequence

from alphaquest.research.edge_backlog import ObservationRevisionV1
from alphaquest.research.literature.contracts import (
    ClaimExtractionRevisionV1,
    EdgeDossierRevisionV1,
    EvidenceTimeBindingV1,
    LiteratureConflictError,
    P2EntryPlanV1,
    P2EvidenceReferencePlanV1,
    P2EvidenceReservationV1,
    P2ObservationPayloadV1,
    P2ObservationPlanV1,
    P2ObservationRolePlanV1,
    SourceCaptureRevisionV1,
    SourceIdentityRevisionV1,
    SourceRelationshipRevisionV1,
    SourceVersionIdentityRevisionV1,
    canonical_json_bytes,
)


_SOURCE_KIND = {
    "ACADEMIC": "PAPER",
    "WORKING_PAPER": "PAPER",
    "EXCHANGE": "EXCHANGE_RESEARCH",
    "REGULATOR": "OTHER",
    "PRACTITIONER": "PRACTITIONER_RESEARCH",
    "MARKET_MICROSTRUCTURE": "PAPER",
    "OTHER": "OTHER",
}


def derive_p2_source_id(source_version_id: str) -> str:
    digest = hashlib.sha256(f"alphaquest-p3-source-version|{source_version_id}".encode()).hexdigest()
    return f"p3src.{digest[:32]}"


def derive_p2_observation_id(claim_id: str) -> str:
    digest = hashlib.sha256(f"alphaquest-p3-claim|{claim_id}".encode()).hexdigest()
    return f"obs.p3.{digest[:32]}"


def canonical_source_version_resolution(
    source_version_id: str,
    relationships: Iterable[SourceRelationshipRevisionV1],
) -> tuple[str, str, frozenset[str]]:
    """Resolve one exact human-authoritative SAME_VERSION_AS state."""

    latest: dict[str, SourceRelationshipRevisionV1] = {}
    for record in relationships:
        latest[record.relationship_id] = record
    graph: dict[str, set[str]] = {}
    for record in latest.values():
        if record.predicate != "SAME_VERSION_AS" or record.status != "ACTIVE":
            continue
        graph.setdefault(record.subject_id, set()).add(record.object_id)
        graph.setdefault(record.object_id, set()).add(record.subject_id)
    component = {source_version_id}
    pending = [source_version_id]
    while pending:
        current = pending.pop()
        for neighbor in graph.get(current, set()):
            if neighbor not in component:
                component.add(neighbor)
                pending.append(neighbor)
    relevant = sorted(
        record.record_sha256
        for record in latest.values()
        if record.predicate == "SAME_VERSION_AS"
        and (record.subject_id in component or record.object_id in component)
    )
    state_hash = hashlib.sha256(canonical_json_bytes(relevant, trailing_lf=False)).hexdigest()
    return min(component), state_hash, frozenset(component)


def relationship_state_sha256(
    source_version_id: str,
    relationships: Iterable[SourceRelationshipRevisionV1],
) -> str:
    return canonical_source_version_resolution(source_version_id, relationships)[1]


def effective_claim_reliability(
    claim: ClaimExtractionRevisionV1,
    relationships: Iterable[SourceRelationshipRevisionV1],
) -> str:
    """Derive current claim reliability from canonical source relationships."""

    latest: dict[str, SourceRelationshipRevisionV1] = {}
    relationship_records = list(relationships)
    for relationship in relationship_records:
        latest[relationship.relationship_id] = relationship
    _canonical_id, _state_hash, component = canonical_source_version_resolution(
        claim.source_version_id, relationship_records
    )
    if any(
        item.status == "ACTIVE"
        and item.predicate == "RETRACTS"
        and item.object_id in component
        for item in latest.values()
    ):
        return "SOURCE_RETRACTED"
    if any(
        item.status == "ACTIVE"
        and item.predicate == "CORRECTS"
        and item.object_id in component
        for item in latest.values()
    ):
        return "SOURCE_VERSION_CORRECTED"
    return claim.reliability


def selected_evidence_time(
    version: SourceVersionIdentityRevisionV1,
    capture: SourceCaptureRevisionV1,
) -> EvidenceTimeBindingV1:
    availability = version.public_availability
    if (
        availability.precision == "EXACT_INSTANT"
        and availability.verification == "VERIFIED"
        and availability.parsed_value is not None
    ):
        return EvidenceTimeBindingV1(
            evidence_time=availability.parsed_value,
            basis="VERIFIED_PUBLIC_AVAILABILITY",
        )
    return EvidenceTimeBindingV1(
        evidence_time=capture.captured_at,
        basis="CAPTURE_FALLBACK_COARSE_OR_UNCERTAIN",
    )


def canonical_p2_locator(work: SourceIdentityRevisionV1, capture: SourceCaptureRevisionV1) -> str:
    doi = work.strong_identifiers.get("doi")
    if doi:
        return "https://doi.org/" + doi.strip().lower()
    return sorted({*work.locators, capture.retrieval_locator})[0]


def p2_source_kind_for_work(work: SourceIdentityRevisionV1) -> str:
    return _SOURCE_KIND[work.source_category]


def reserve_p2_evidence(
    *,
    operation_id: str,
    work: SourceIdentityRevisionV1,
    version: SourceVersionIdentityRevisionV1,
    capture: SourceCaptureRevisionV1,
    relationships: Sequence[SourceRelationshipRevisionV1],
    existing: P2EvidenceReservationV1 | None = None,
) -> P2EvidenceReservationV1:
    if capture.status not in {"FULL_TEXT_CAPTURED", "GENUINE_ABSTRACT_CAPTURED"}:
        raise LiteratureConflictError("P2 evidence reservation requires inspectable captured evidence")
    if capture.source_version_id != version.source_version_id or version.work_id != work.work_id:
        raise LiteratureConflictError("work/version/capture identity chain is inconsistent")
    if capture.content_sha256 is None or capture.extracted_representation_sha256 is None:
        raise LiteratureConflictError("captured evidence hashes are incomplete")
    canonical_version_id, relationship_hash, component = canonical_source_version_resolution(
        version.source_version_id, relationships
    )
    if existing is not None:
        if existing.canonical_source_version_id not in component:
            raise LiteratureConflictError("existing reservation belongs to another source version")
        if (
            capture.content_sha256 != existing.content_sha256
            or capture.extracted_representation_sha256 != existing.extracted_representation_sha256
        ):
            raise LiteratureConflictError(
                "byte-different content cannot reuse a canonical source-version P2 reservation"
            )
        return existing
    return P2EvidenceReservationV1(
        canonical_source_version_id=canonical_version_id,
        relationship_state_sha256=relationship_hash,
        p2_source_id=derive_p2_source_id(canonical_version_id),
        source_kind=p2_source_kind_for_work(work),
        canonical_locator=canonical_p2_locator(work, capture),
        capture_id=capture.capture_id,
        terminal_capture_revision_sha256=capture.record_sha256,
        content_sha256=capture.content_sha256,
        extracted_representation_sha256=capture.extracted_representation_sha256,
        evidence_time=selected_evidence_time(version, capture),
        reservation_operation_id=operation_id,
    )


def p3_conflict_marker(code: str, claim: ClaimExtractionRevisionV1) -> str:
    allowed = {
        "CLAIM_CORRECTED",
        "INVALID_EXTRACTION_WITHDRAWN",
        "SOURCE_RETRACTED",
        "SOURCE_VERSION_CORRECTED",
    }
    if code not in allowed:
        raise ValueError(f"unknown deterministic P3 conflict code: {code}")
    return f"P3_CONFLICT|{code}|claim_id={claim.claim_id}|claim_revision_sha256={claim.record_sha256}"


def map_claim_to_observation(
    *,
    claim: ClaimExtractionRevisionV1,
    role: str,
    reservation: P2EvidenceReservationV1,
    prior_observation: ObservationRevisionV1 | None = None,
    effective_reliability: str | None = None,
) -> P2ObservationPlanV1:
    observation_id = derive_p2_observation_id(claim.claim_id)
    if prior_observation is not None and prior_observation.observation_id != observation_id:
        raise LiteratureConflictError("prior P2 observation does not match logical P3 claim identity")
    claim_locator = (
        f"p3-claim:{claim.claim_id}:revision-sha256:{claim.record_sha256}:"
        f"locator-sha256:{claim.location.locator_sha256}"
    )
    evidence = P2EvidenceReferencePlanV1(
        source_id=reservation.p2_source_id,
        source_kind=reservation.source_kind,
        locator=reservation.canonical_locator,
        claim_locator=claim_locator,
        evidence_time=reservation.evidence_time.evidence_time,
        integrity="HASH_BOUND",
        content_sha256=reservation.content_sha256,
    )
    known_conflicts = list(prior_observation.known_conflicts) if prior_observation else []
    reliability = effective_reliability or claim.reliability
    withdrawn = reliability == "WITHDRAWN_INVALID"
    if withdrawn:
        if prior_observation is None:
            raise LiteratureConflictError("invalid extraction withdrawal requires its prior P2 observation")
        marker = p3_conflict_marker("INVALID_EXTRACTION_WITHDRAWN", claim)
        if marker not in known_conflicts:
            known_conflicts.append(marker)
        payload = P2ObservationPayloadV1(
            observation_id=observation_id,
            statement=prior_observation.statement,
            statement_kind=prior_observation.statement_kind,
            evidence_refs=[item.model_dump(mode="python") for item in prior_observation.evidence_refs],
            known_conflicts=known_conflicts,
        )
    else:
        marker_code = {
            "CORRECTED": "CLAIM_CORRECTED",
            "SOURCE_RETRACTED": "SOURCE_RETRACTED",
            "SOURCE_VERSION_CORRECTED": "SOURCE_VERSION_CORRECTED",
        }.get(reliability)
        if marker_code:
            marker = p3_conflict_marker(marker_code, claim)
            if marker not in known_conflicts:
                known_conflicts.append(marker)
        if reliability == "SOURCE_RETRACTED" and prior_observation is not None:
            payload = P2ObservationPayloadV1(
                observation_id=observation_id,
                statement=prior_observation.statement,
                statement_kind=prior_observation.statement_kind,
                evidence_refs=[item.model_dump(mode="python") for item in prior_observation.evidence_refs],
                known_conflicts=known_conflicts,
            )
        else:
            payload = P2ObservationPayloadV1(
                observation_id=observation_id,
                statement=claim.statement.strip(),
                statement_kind=claim.statement_kind,
                evidence_refs=[evidence],
                known_conflicts=known_conflicts,
            )
    payload_hash = hashlib.sha256(canonical_json_bytes(payload, trailing_lf=False)).hexdigest()
    return P2ObservationPlanV1(
        claim_id=claim.claim_id,
        claim_revision_sha256=claim.record_sha256,
        observation_id=observation_id,
        prior_observation_revision_sha256=(
            prior_observation.record_sha256 if prior_observation is not None else None
        ),
        role=role,
        withdrawn_from_current_support=(
            reliability in {"WITHDRAWN_INVALID", "SOURCE_RETRACTED"}
            and role in {"MOTIVATING", "SUPPORTING"}
        ),
        payload_sha256=payload_hash,
        payload=payload,
    )


def map_dossier_entry(
    dossier: EdgeDossierRevisionV1,
    observation_plans: Sequence[P2ObservationPlanV1],
) -> P2EntryPlanV1:
    roles = [
        P2ObservationRolePlanV1(observation_id=item.observation_id, role=item.role)
        for item in observation_plans
        if not item.withdrawn_from_current_support
    ]
    if not roles:
        raise LiteratureConflictError("tentative P2 emission requires at least one valid current observation")
    proposal = dossier.taxonomy_proposal
    return P2EntryPlanV1(
        classification_status=proposal.classification_status,
        taxonomy_ref=proposal.taxonomy_ref,
        governance_scope="PRE_HYPOTHESIS_BACKLOG_ONLY",
        p1_evidence_eligibility="NOT_CURRENT_P1_EVIDENCE",
        economic_concepts=proposal.economic_concepts,
        unclassified_reason=proposal.unclassified_reason,
        observation_roles=roles,
    )


def p2_entry_payload(
    plan: P2EntryPlanV1,
    observation_revision_hashes: Mapping[str, str],
) -> dict[str, object]:
    refs = []
    seen = set()
    for item in plan.observation_roles:
        revision_sha = item.frozen_revision_sha256 or observation_revision_hashes[item.observation_id]
        identity = (item.observation_id, revision_sha, item.role)
        if identity in seen:
            continue
        seen.add(identity)
        refs.append(
            {
                "observation_id": item.observation_id,
                "observation_revision_sha256": revision_sha,
                "role": item.role,
            }
        )
    return {
        "classification_status": plan.classification_status,
        "taxonomy_ref": plan.taxonomy_ref.model_dump(mode="json"),
        "governance_scope": plan.governance_scope,
        "p1_evidence_eligibility": plan.p1_evidence_eligibility,
        "economic_concepts": (
            plan.economic_concepts.model_dump(mode="json") if plan.economic_concepts is not None else None
        ),
        "unclassified_reason": plan.unclassified_reason,
        "observation_refs": refs,
    }


__all__ = [
    "derive_p2_observation_id",
    "derive_p2_source_id",
    "effective_claim_reliability",
    "canonical_source_version_resolution",
    "canonical_p2_locator",
    "map_claim_to_observation",
    "map_dossier_entry",
    "p2_entry_payload",
    "p2_source_kind_for_work",
    "p3_conflict_marker",
    "relationship_state_sha256",
    "reserve_p2_evidence",
    "selected_evidence_time",
]
