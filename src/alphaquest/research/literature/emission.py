"""Recoverable offline P3-to-P2 emission transaction journal."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TypeVar

from pydantic import BaseModel

from alphaquest.research.edge_backlog import (
    EdgeBacklogEntryRevisionV1,
    EdgeBacklogStore,
    HashedRecord,
    ObservationRevisionV1,
)
from alphaquest.research.literature.contracts import (
    ActorProvenanceV1,
    CanonicalRecordV1,
    ClaimExtractionRevisionV1,
    DossierFreezeV1,
    EdgeDossierRevisionV1,
    LiteratureConflictError,
    LiteratureIntegrityError,
    P2DependencyImpactV1,
    P2EntryPlanV1,
    P2EmissionOperationRevisionV1,
    P2EmissionReceiptV1,
    P2EvidenceReservationV1,
    P2ObservationPlanV1,
    P2ObservationRolePlanV1,
    P2RecordBindingV1,
    SourceCaptureRevisionV1,
    SourceIdentityRevisionV1,
    SourceRelationshipRevisionV1,
    SourceVersionIdentityRevisionV1,
    canonical_json_bytes,
)
from alphaquest.research.literature.mapper import (
    canonical_source_version_resolution,
    effective_claim_reliability,
    map_claim_to_observation,
    map_dossier_entry,
    p2_entry_payload,
    reserve_p2_evidence,
)
from alphaquest.research.literature.store import LiteratureStore


R = TypeVar("R", bound=CanonicalRecordV1)
_P3_MANAGED = {
    "schema",
    "record_id",
    "append_sequence",
    "previous_store_record_sha256",
    "recorded_at",
    "actor",
    "idempotency_key",
    "intent_sha256",
    "record_sha256",
    "revision",
    "previous_revision_sha256",
}


def _by_hash(records: Iterable[CanonicalRecordV1], digest: str, expected: type[R]) -> R:
    matches = [item for item in records if isinstance(item, expected) and item.record_sha256 == digest]
    if len(matches) != 1:
        raise LiteratureConflictError(f"missing exact {expected.family} record: {digest}")
    return matches[0]


def _latest_reservations(records: Sequence[CanonicalRecordV1]) -> dict[str, P2EvidenceReservationV1]:
    output: dict[str, P2EvidenceReservationV1] = {}
    for record in records:
        if not isinstance(record, P2EmissionOperationRevisionV1) or record.revision != 1:
            continue
        for reservation in record.reservations:
            output.setdefault(reservation.canonical_source_version_id, reservation)
    return output


def _current_hypothesis_link(backlog: EdgeBacklogStore, entry_id: str) -> bool:
    return any(item.relationship == "HYPOTHESIS_PROPOSAL" for item in backlog.links(entry_id))


def _hypothesis_link_at_prefix(
    backlog: EdgeBacklogStore, entry_id: str, before_append_sequence: int
) -> bool:
    return any(
        item.relationship == "HYPOTHESIS_PROPOSAL"
        and item.append_sequence < before_append_sequence
        for item in backlog.links(entry_id)
    )


def _lifecycle_action(
    backlog: EdgeBacklogStore,
    dossier: EdgeDossierRevisionV1,
    target_entry_id: str | None,
) -> tuple[str, str | None, str | None, str | None, str | None, str | None]:
    """Return action, exact entry SHA/state/link chain, stale decision, blocker."""

    if target_entry_id is None:
        return "CREATE_NEW_ENTRY", None, None, None, None, None
    entry = backlog.latest_entry(target_entry_id)
    state = backlog.entry_state(target_entry_id)
    link_chain = backlog.entry_link_chain_sha256(target_entry_id)
    decisions = backlog.decisions(target_entry_id)
    decision_sha = decisions[-1].record_sha256 if decisions and state != "UNREVIEWED" else None
    bound = dossier.p2_entry_id == target_entry_id
    if state == "SUSPENDED":
        return "BLOCKED", entry.record_sha256, state, link_chain, None, "BOUND_ENTRY_SUSPENDED" if bound else "TARGET_ENTRY_SUSPENDED"
    if _current_hypothesis_link(backlog, target_entry_id):
        if bound:
            return "BLOCKED", entry.record_sha256, state, link_chain, None, "BOUND_ENTRY_HAS_CURRENT_HYPOTHESIS_PROPOSAL"
        return "CREATE_NEW_ENTRY", entry.record_sha256, state, link_chain, None, None
    if state in {"REJECTED", "DUPLICATE"}:
        if bound:
            return "BLOCKED", entry.record_sha256, state, link_chain, None, f"BOUND_ENTRY_TERMINAL_{state}"
        return "CREATE_NEW_ENTRY", entry.record_sha256, state, link_chain, None, None
    if state not in {"UNREVIEWED", "REVIEWED_CONTINUE", "RESUMED"}:
        raise LiteratureConflictError(f"unsupported authoritative P2 state: {state}")
    return "REVISE_SAME_ENTRY", entry.record_sha256, state, link_chain, decision_sha, None


def _entry_plan_after_corrections(
    entry: EdgeBacklogEntryRevisionV1,
    corrections: Mapping[tuple[str, str], P2ObservationPlanV1],
) -> P2EntryPlanV1 | None:
    roles: list[P2ObservationRolePlanV1] = []
    for reference in entry.observation_refs:
        plan = corrections.get((reference.observation_id, reference.observation_revision_sha256))
        if plan is None:
            roles.append(
                P2ObservationRolePlanV1(
                    observation_id=reference.observation_id,
                    role=reference.role,
                    frozen_revision_sha256=reference.observation_revision_sha256,
                )
            )
            continue
        if reference.role == "CONTRADICTING":
            roles.append(
                P2ObservationRolePlanV1(
                    observation_id=reference.observation_id,
                    role="CONTRADICTING",
                    frozen_revision_sha256=reference.observation_revision_sha256,
                )
            )
            roles.append(
                P2ObservationRolePlanV1(
                    observation_id=reference.observation_id,
                    role="CONTRADICTING",
                    frozen_revision_sha256=None,
                )
            )
            continue
        invalid_for_positive_support = plan.withdrawn_from_current_support or any(
            marker.startswith("P3_CONFLICT|INVALID_EXTRACTION_WITHDRAWN|")
            or marker.startswith("P3_CONFLICT|SOURCE_RETRACTED|")
            for marker in plan.payload.known_conflicts
        )
        if invalid_for_positive_support and reference.role in {"MOTIVATING", "SUPPORTING"}:
            continue
        roles.append(
            P2ObservationRolePlanV1(
                observation_id=reference.observation_id,
                role=reference.role,
                frozen_revision_sha256=None,
            )
        )
    if not roles:
        return None
    return P2EntryPlanV1(
        classification_status=entry.classification_status,
        taxonomy_ref=entry.taxonomy_ref,
        governance_scope=entry.governance_scope,
        p1_evidence_eligibility=entry.p1_evidence_eligibility,
        economic_concepts=entry.economic_concepts,
        unclassified_reason=entry.unclassified_reason,
        observation_roles=roles,
    )


def _with_new_dossier_observations(
    entry_plan: P2EntryPlanV1,
    plans: Sequence[P2ObservationPlanV1],
) -> P2EntryPlanV1:
    """Add current dossier observations after dependency correction of the bound entry."""

    roles = list(entry_plan.observation_roles)
    present = {item.observation_id for item in roles}
    for plan in plans:
        if plan.withdrawn_from_current_support or plan.observation_id in present:
            continue
        roles.append(
            P2ObservationRolePlanV1(
                observation_id=plan.observation_id,
                role=plan.role,
                frozen_revision_sha256=None,
            )
        )
        present.add(plan.observation_id)
    return entry_plan.model_copy(update={"observation_roles": roles})


def _dependency_impacts(
    backlog: EdgeBacklogStore,
    plans: Sequence[Any],
    *,
    before_append_sequence: int,
) -> list[P2DependencyImpactV1]:
    corrections = {
        (plan.observation_id, str(plan.prior_observation_revision_sha256)): plan
        for plan in plans
        if plan.prior_observation_revision_sha256 is not None
        and (
            plan.withdrawn_from_current_support
            or any(value.startswith("P3_CONFLICT|") for value in plan.payload.known_conflicts)
        )
    }
    dependent_entries: dict[str, EdgeBacklogEntryRevisionV1] = {}
    for observation_id, prior_sha in corrections:
        for entry in backlog.observation_dependents_at_prefix(
            observation_id, prior_sha, before_append_sequence
        ):
            dependent_entries[entry.entry_id] = entry
    impacts: list[P2DependencyImpactV1] = []
    for entry in sorted(dependent_entries.values(), key=lambda item: item.entry_id):
        state = backlog.entry_state_at_prefix(entry.entry_id, before_append_sequence)
        link_chain = backlog.entry_link_chain_sha256_at_prefix(
            entry.entry_id, before_append_sequence
        )
        has_hypothesis = _hypothesis_link_at_prefix(
            backlog, entry.entry_id, before_append_sequence
        )
        mutable = state in {"UNREVIEWED", "REVIEWED_CONTINUE", "RESUMED"} and not has_hypothesis
        entry_plan = _entry_plan_after_corrections(entry, corrections) if mutable else None
        if mutable and entry_plan is None:
            mutable = False
            reason = "P2_ENTRY_REQUIRES_AT_LEAST_ONE_CURRENT_OBSERVATION"
        elif has_hypothesis:
            reason = "CURRENT_HYPOTHESIS_PROPOSAL"
        elif state in {"SUSPENDED", "REJECTED", "DUPLICATE"}:
            reason = f"P2_ENTRY_{state}"
        else:
            reason = None
        decisions = [
            item
            for item in backlog.decisions(entry.entry_id)
            if item.append_sequence < before_append_sequence
        ]
        stale_decision = (
            decisions[-1].record_sha256
            if mutable and state == "REVIEWED_CONTINUE" and decisions
            else None
        )
        for (observation_id, prior_sha), plan in sorted(corrections.items()):
            if not any(
                ref.observation_id == observation_id and ref.observation_revision_sha256 == prior_sha
                for ref in entry.observation_refs
            ):
                continue
            impacts.append(
                P2DependencyImpactV1(
                    affected_observation_id=observation_id,
                    affected_observation_revision_sha256=prior_sha,
                    dependent_entry_id=entry.entry_id,
                    dependent_entry_revision_sha256=entry.record_sha256,
                    dependent_entry_state=state,
                    relevant_link_chain_sha256=link_chain,
                    impact_status=(
                        "PLANNED_MUTABLE_REVISION"
                        if mutable
                        else "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"
                    ),
                    inability_reason=None if mutable else reason,
                    prior_staled_decision_sha256=stale_decision,
                    entry_plan=entry_plan,
                )
            )
    return impacts


def prepare_emission(
    project_root: str | Path,
    *,
    freeze_id: str,
    operation_id: str,
    actor: ActorProvenanceV1,
    idempotency_key: str,
    target_entry_id: str | None = None,
) -> P2EmissionOperationRevisionV1:
    """Reserve evidence and append PREPARED before any P2 write."""

    literature = LiteratureStore(project_root)
    backlog = EdgeBacklogStore(project_root)
    records = literature.records()
    freeze = next((item for item in records if isinstance(item, DossierFreezeV1) and item.freeze_id == freeze_id), None)
    if freeze is None:
        raise LiteratureConflictError(f"dossier freeze not found: {freeze_id}")
    literature.assert_freeze_emission_eligible(freeze)
    dossier = _by_hash(records, freeze.dossier_revision_sha256, EdgeDossierRevisionV1)
    if dossier.p2_entry_id is not None:
        if target_entry_id is not None and target_entry_id != dossier.p2_entry_id:
            raise LiteratureConflictError("bound dossier cannot change its canonical P2 entry identity")
        target_entry_id = dossier.p2_entry_id
    action, target_sha, target_state, target_link_chain, staled_decision, blocked_reason = _lifecycle_action(
        backlog, dossier, target_entry_id
    )
    # Serialize snapshot acquisition with the canonical reservation lock.  This
    # also makes first-use creation of the P2 read lock deterministic.
    with literature.lock(exclusive=True):
        p2_snapshot_before_append_sequence = backlog.next_append_sequence()
    relationships = [item for item in records if isinstance(item, SourceRelationshipRevisionV1)]
    existing_reservations = _latest_reservations(records)
    reservations: dict[str, P2EvidenceReservationV1] = {}
    plans = []
    resolved_claims = []
    for reference in dossier.claim_refs:
        claim = _by_hash(records, reference.claim_revision_sha256, ClaimExtractionRevisionV1)
        capture = _by_hash(records, claim.capture_revision_sha256, SourceCaptureRevisionV1)
        version = _by_hash(records, claim.source_version_revision_sha256, SourceVersionIdentityRevisionV1)
        work = _by_hash(records, claim.work_revision_sha256, SourceIdentityRevisionV1)
        canonical_version_id, _relationship_hash, component = canonical_source_version_resolution(
            version.source_version_id, relationships
        )
        resolved_claims.append(
            (
                canonical_version_id,
                version.source_version_id != canonical_version_id,
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
    for (
        canonical_version_id,
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
        prior_candidates = [
            item
            for key, item in existing_reservations.items()
            if key == canonical_version_id or key in component
        ]
        if len(prior_candidates) > 1:
            raise LiteratureConflictError(
                "current SAME_VERSION_AS state merges incompatible historical P2 reservations"
            )
        existing = reservations.get(canonical_version_id) or next(iter(prior_candidates), None)
        reservation = reserve_p2_evidence(
            operation_id=operation_id,
            work=work,
            version=version,
            capture=capture,
            relationships=relationships,
            existing=existing,
        )
        reservations[canonical_version_id] = reservation
        observation_id = hashlib.sha256(f"alphaquest-p3-claim|{claim.claim_id}".encode()).hexdigest()
        logical_id = f"obs.p3.{observation_id[:32]}"
        try:
            prior = backlog.latest_observation(logical_id)
        except FileNotFoundError:
            prior = None
        plans.append(
            map_claim_to_observation(
                claim=claim,
                role=reference.p2_role,
                reservation=reservation,
                prior_observation=prior,
                effective_reliability=effective_claim_reliability(claim, relationships),
            )
        )
    entry_plan = map_dossier_entry(dossier, plans)
    if action == "REVISE_SAME_ENTRY" and target_entry_id is not None:
        prior_entry = backlog.latest_entry(target_entry_id)
        preserved = [
            P2ObservationRolePlanV1(
                observation_id=item.observation_id,
                role="CONTRADICTING",
                frozen_revision_sha256=item.observation_revision_sha256,
            )
            for item in prior_entry.observation_refs
            if item.role == "CONTRADICTING"
        ]
        entry_plan = entry_plan.model_copy(
            update={"observation_roles": [*entry_plan.observation_roles, *preserved]}
        )
    dependency_impacts = _dependency_impacts(
        backlog,
        plans,
        before_append_sequence=p2_snapshot_before_append_sequence,
    )
    if action == "REVISE_SAME_ENTRY" and target_entry_id is not None:
        target_impact = next(
            (
                item
                for item in dependency_impacts
                if item.dependent_entry_id == target_entry_id
                and item.impact_status == "PLANNED_MUTABLE_REVISION"
            ),
            None,
        )
        if target_impact is not None:
            assert target_impact.entry_plan is not None
            entry_plan = _with_new_dossier_observations(target_impact.entry_plan, plans)
    unsatisfied = [
        item.lane for item in dossier.lane_completions if item.obligation_status != "SATISFIED"
    ]
    payload = {
        "operation_id": operation_id,
        "freeze_id": freeze.freeze_id,
        "freeze_record_sha256": freeze.record_sha256,
        "target_entry_id": target_entry_id,
        "target_entry_revision_sha256": target_sha,
        "target_entry_state": target_state,
        "target_entry_link_chain_sha256": target_link_chain,
        "p2_snapshot_before_append_sequence": p2_snapshot_before_append_sequence,
        "emission_action": action,
        "state": "BLOCKED" if action == "BLOCKED" else "PREPARED",
        "reservations": [item.model_dump(mode="json") for item in reservations.values()],
        "observation_plans": [item.model_dump(mode="json") for item in plans],
        "entry_plan": entry_plan.model_dump(mode="json"),
        "dependency_impacts": [item.model_dump(mode="json") for item in dependency_impacts],
        "search_completion_status": dossier.search_completion_status,
        "unsatisfied_lanes": unsatisfied,
        "observation_bindings": [],
        "entry_binding": None,
        "dependency_entry_bindings": [],
        "duplicate_snapshot": None,
        "prior_staled_decision_sha256": staled_decision,
        "receipt_record_sha256": None,
        "blocked_reason": blocked_reason,
        "conflict_reason": None,
        "operational_status": (
            "NEEDS_MANUAL_REVIEW"
            if any(
                item.impact_status == "UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY"
                for item in dependency_impacts
            )
            else "CLEAN"
        ),
    }
    return literature.append_emission_operation(
        payload,
        actor=actor,
        idempotency_key=idempotency_key,
    )


def _p2_payload(record: ObservationRevisionV1) -> dict[str, Any]:
    return record.model_dump(
        mode="json",
        by_alias=True,
        include={"observation_id", "statement", "statement_kind", "evidence_refs", "known_conflicts"},
    )


def _plan_payload(plan: Any) -> dict[str, Any]:
    return plan.payload.model_dump(mode="json")


def _same_payload(record: ObservationRevisionV1, plan: Any) -> bool:
    return _p2_payload(record) == _plan_payload(plan)


def _same_entry_payload(record: EdgeBacklogEntryRevisionV1, payload: Mapping[str, Any]) -> bool:
    actual = record.model_dump(
        mode="json",
        by_alias=True,
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
    return actual == dict(payload)


def _advance(
    literature: LiteratureStore,
    operation: P2EmissionOperationRevisionV1,
    *,
    state: str,
    actor: ActorProvenanceV1,
    suffix: str,
    **updates: Any,
) -> P2EmissionOperationRevisionV1:
    payload = operation.model_dump(mode="json", by_alias=True, exclude=_P3_MANAGED)
    payload.update(updates)
    payload["state"] = state
    return literature.append_emission_operation(
        payload,
        actor=actor,
        idempotency_key=f"{operation.operation_id}.{suffix}",
    )


def _binding(record: HashedRecord) -> dict[str, str]:
    return {"record_id": record.record_id, "record_sha256": record.record_sha256}


def _find_task_entries(
    backlog: EdgeBacklogStore, operation_id: str
) -> dict[str, EdgeBacklogEntryRevisionV1]:
    records = [item for item in backlog.records_by_task_id(operation_id) if isinstance(item, EdgeBacklogEntryRevisionV1)]
    output: dict[str, EdgeBacklogEntryRevisionV1] = {}
    for record in records:
        if record.entry_id in output:
            raise LiteratureConflictError("emission recovery found repeated task-authored P2 entry revisions")
        output[record.entry_id] = record
    return output


def _assert_dependency_snapshot_current(
    backlog: EdgeBacklogStore,
    operation: P2EmissionOperationRevisionV1,
    task_entries: Mapping[str, EdgeBacklogEntryRevisionV1],
) -> None:
    expected = {
        (
            item.affected_observation_id,
            item.affected_observation_revision_sha256,
            item.dependent_entry_id,
            item.dependent_entry_revision_sha256,
            item.dependent_entry_state,
            item.relevant_link_chain_sha256,
        )
        for item in operation.dependency_impacts
    }
    actual = {
        item
        for item in expected
        if item[2] in task_entries
    }
    task_entry_ids = {item[2] for item in expected if item[2] in task_entries}
    affected = {
        (item.affected_observation_id, item.affected_observation_revision_sha256)
        for item in operation.dependency_impacts
    }
    for observation_id, revision_sha in affected:
        for entry in backlog.current_observation_dependents(observation_id, revision_sha):
            if entry.entry_id in task_entry_ids:
                continue
            actual.add(
                (
                    observation_id,
                    revision_sha,
                    entry.entry_id,
                    entry.record_sha256,
                    backlog.entry_state(entry.entry_id),
                    backlog.entry_link_chain_sha256(entry.entry_id),
                )
            )
    if actual != expected:
        raise LiteratureConflictError("P2 reverse-dependency snapshot changed after PREPARED")


def emit_prepared(
    project_root: str | Path,
    *,
    operation_id: str,
    actor: ActorProvenanceV1,
) -> P2EmissionReceiptV1 | P2EmissionOperationRevisionV1:
    """Apply or recover one prepared operation using only EdgeBacklogStore writes."""

    literature = LiteratureStore(project_root)
    backlog = EdgeBacklogStore(project_root)
    with literature.lock(exclusive=True):
        records = literature._load_and_validate()
        recoverable_tail = literature._recoverable_completion_tail(records)
        if (
            recoverable_tail is not None
            and recoverable_tail.operation_id != operation_id
        ):
            raise LiteratureConflictError(
                "recoverable completion tail must be reconciled before another emission: "
                f"{recoverable_tail.operation_id}"
            )
        operations = [
            item
            for item in records
            if isinstance(item, P2EmissionOperationRevisionV1)
            and item.operation_id == operation_id
        ]
        if not operations:
            raise LiteratureConflictError(f"p2-emissions object not found: {operation_id}")
        operation = operations[-1]
        if operation.state == "CONFLICT":
            raise LiteratureConflictError(str(operation.conflict_reason))
        literature._ensure_durable_canonical_prefix(records)
        if operation.state == "BLOCKED":
            return operation
        if operation.state == "COMPLETED":
            return _by_hash(records, str(operation.receipt_record_sha256), P2EmissionReceiptV1)
    freeze = _by_hash(
        records, operation.freeze_record_sha256, DossierFreezeV1
    )
    literature.assert_freeze_emission_eligible(freeze)

    if operation.state == "PREPARED":
        bindings: list[dict[str, str]] = []
        for plan in operation.observation_plans:
            payload = _plan_payload(plan)
            try:
                current = backlog.latest_observation(plan.observation_id)
            except FileNotFoundError:
                current = backlog.capture_observation(
                    payload,
                    actor_id=actor.actor_id,
                    task_id=operation.operation_id,
                )
            else:
                if not _same_payload(current, plan):
                    claim = _by_hash(literature.records(), plan.claim_revision_sha256, ClaimExtractionRevisionV1)
                    relationship_derived_correction = any(
                        marker.startswith("P3_CONFLICT|SOURCE_RETRACTED|")
                        or marker.startswith("P3_CONFLICT|SOURCE_VERSION_CORRECTED|")
                        for marker in plan.payload.known_conflicts
                    )
                    if (
                        claim.revision == 1
                        and claim.reliability == "ACTIVE"
                        and not relationship_derived_correction
                    ):
                        operation = _advance(
                            literature,
                            operation,
                            state="CONFLICT",
                            actor=actor,
                            suffix="observation-conflict",
                            conflict_reason=f"logical observation collision: {plan.observation_id}",
                        )
                        raise LiteratureConflictError(str(operation.conflict_reason))
                    current = backlog.revise_observation(
                        plan.observation_id,
                        payload,
                        actor_id=actor.actor_id,
                        task_id=operation.operation_id,
                    )
            bindings.append(_binding(current))
        operation = _advance(
            literature,
            operation,
            state="OBSERVATIONS_WRITTEN",
            actor=actor,
            suffix="observations-written",
            observation_bindings=bindings,
        )

    if operation.state == "OBSERVATIONS_WRITTEN":
        observation_hashes = {
            binding.record_id.split(".r", 1)[0]: binding.record_sha256
            for binding in operation.observation_bindings
        }
        entry_payload = p2_entry_payload(operation.entry_plan, observation_hashes)
        task_entries = _find_task_entries(backlog, operation.operation_id)
        if operation.dependency_impacts:
            try:
                _assert_dependency_snapshot_current(backlog, operation, task_entries)
            except LiteratureConflictError as exc:
                operation = _advance(
                    literature,
                    operation,
                    state="CONFLICT",
                    actor=actor,
                    suffix="dependency-snapshot-conflict",
                    conflict_reason=str(exc),
                )
                raise
        entry: EdgeBacklogEntryRevisionV1 | None = (
            task_entries.get(str(operation.target_entry_id))
            if operation.emission_action == "REVISE_SAME_ENTRY"
            else next(
                (
                    item
                    for item in task_entries.values()
                    if item.entry_id not in {impact.dependent_entry_id for impact in operation.dependency_impacts}
                ),
                None,
            )
        )
        if operation.emission_action == "REVISE_SAME_ENTRY":
            if entry is not None:
                if entry.entry_id != operation.target_entry_id or not _same_entry_payload(entry, entry_payload):
                    raise LiteratureConflictError("recovered P2 entry does not match the prepared target/payload")
            else:
                current = backlog.latest_entry(str(operation.target_entry_id))
                state = backlog.entry_state(current.entry_id)
                if (
                    current.record_sha256 != operation.target_entry_revision_sha256
                    or state != operation.target_entry_state
                    or backlog.entry_link_chain_sha256(current.entry_id)
                    != operation.target_entry_link_chain_sha256
                    or _current_hypothesis_link(backlog, current.entry_id)
                ):
                    operation = _advance(
                        literature,
                        operation,
                        state="CONFLICT",
                        actor=actor,
                        suffix="target-conflict",
                        conflict_reason="target P2 entry state changed after PREPARED",
                    )
                    raise LiteratureConflictError(str(operation.conflict_reason))
                entry = backlog.revise_entry(
                    current.entry_id,
                    entry_payload,
                    actor_id=actor.actor_id,
                    task_id=operation.operation_id,
                )
        elif operation.emission_action == "CREATE_NEW_ENTRY":
            if entry is None:
                entry = backlog.create_entry(
                    entry_payload,
                    actor_id=actor.actor_id,
                    task_id=operation.operation_id,
                )
            elif not _same_entry_payload(entry, entry_payload):
                raise LiteratureConflictError("recovered P2 entry does not match the prepared payload")
        else:  # pragma: no cover - strict contract prevents this state
            raise LiteratureConflictError("blocked emission cannot reach P2 entry writing")
        assert entry is not None
        dependency_bindings: dict[str, dict[str, str]] = {}
        mutable_impacts: dict[str, Any] = {}
        for impact in operation.dependency_impacts:
            if impact.impact_status == "PLANNED_MUTABLE_REVISION":
                mutable_impacts.setdefault(impact.dependent_entry_id, impact)
                if mutable_impacts[impact.dependent_entry_id].entry_plan != impact.entry_plan:
                    raise LiteratureConflictError("one dependent entry has competing correction plans")
        for dependent_id, impact in sorted(mutable_impacts.items()):
            assert impact.entry_plan is not None
            dependent_payload = p2_entry_payload(impact.entry_plan, observation_hashes)
            if dependent_id == entry.entry_id:
                dependent = entry
            else:
                dependent = task_entries.get(dependent_id)
                if dependent is not None:
                    if not _same_entry_payload(dependent, dependent_payload):
                        raise LiteratureConflictError("recovered dependent entry differs from prepared correction")
                else:
                    current = backlog.latest_entry(dependent_id)
                    if (
                        current.record_sha256 != impact.dependent_entry_revision_sha256
                        or backlog.entry_state(dependent_id) != impact.dependent_entry_state
                        or backlog.entry_link_chain_sha256(dependent_id) != impact.relevant_link_chain_sha256
                        or _current_hypothesis_link(backlog, dependent_id)
                    ):
                        operation = _advance(
                            literature,
                            operation,
                            state="CONFLICT",
                            actor=actor,
                            suffix=f"dependency-{dependent_id}-conflict",
                            conflict_reason=f"dependent P2 entry state changed after PREPARED: {dependent_id}",
                        )
                        raise LiteratureConflictError(str(operation.conflict_reason))
                    dependent = backlog.revise_entry(
                        dependent_id,
                        dependent_payload,
                        actor_id=actor.actor_id,
                        task_id=operation.operation_id,
                    )
            dependency_bindings[dependent_id] = _binding(dependent)
        operation = _advance(
            literature,
            operation,
            state="ENTRY_WRITTEN",
            actor=actor,
            suffix="entry-written",
            entry_binding=_binding(entry),
            dependency_entry_bindings=[
                dependency_bindings[key] for key in sorted(dependency_bindings)
            ],
        )

    if operation.state == "ENTRY_WRITTEN":
        assert operation.entry_binding is not None
        bound_entry_id = operation.entry_binding.record_id.rsplit(".r", 1)[0]
        exact_entry = backlog.exact_entry_revision(
            bound_entry_id,
            operation.entry_binding.record_sha256,
        )
        before_sequence = exact_entry.append_sequence + 1
        snapshot = backlog.duplicate_snapshot_at_prefix(
            bound_entry_id,
            entry_revision_sha256=operation.entry_binding.record_sha256,
            before_append_sequence=before_sequence,
        )
        binding = {
            "entry_id": snapshot["entry_id"],
            "entry_revision_sha256": snapshot["entry_revision_sha256"],
            "before_append_sequence": snapshot["before_append_sequence"],
            "entry_link_chain_sha256": snapshot["entry_link_chain_sha256"],
            "historical_source_commit": snapshot["historical_source_commit"],
            "historical_universe_sha256": snapshot["historical_universe_sha256"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "candidate_bindings": [
                {
                    "candidate_id": item["candidate_id"],
                    "candidate_record_sha256": item["candidate_record_sha256"],
                    "candidate_decision_sha256": item["candidate_decision_sha256"],
                    "candidate_link_chain_sha256": item["candidate_link_chain_sha256"],
                }
                for item in snapshot["candidates"]
            ],
        }
        operation = _advance(
            literature,
            operation,
            state="SNAPSHOT_BOUND",
            actor=actor,
            suffix="snapshot-bound",
            duplicate_snapshot=binding,
        )

    if operation.state == "SNAPSHOT_BOUND":
        receipt_id = "receipt." + hashlib.sha256(operation.operation_id.encode()).hexdigest()[:32]
        receipt, _completion = literature.complete_emission_operation(
            operation_id=operation.operation_id,
            snapshot_revision_sha256=operation.record_sha256,
            receipt_payload={
                "record_id": receipt_id,
                "receipt_id": receipt_id,
                "operation_id": operation.operation_id,
                "operation_revision_sha256": operation.record_sha256,
                "freeze_id": operation.freeze_id,
                "freeze_record_sha256": operation.freeze_record_sha256,
                "reservations": [
                    item.model_dump(mode="json") for item in operation.reservations
                ],
                "observation_bindings": [
                    item.model_dump(mode="json")
                    for item in operation.observation_bindings
                ],
                "entry_binding": operation.entry_binding.model_dump(mode="json"),
                "duplicate_snapshot": operation.duplicate_snapshot.model_dump(
                    mode="json"
                ),
                "dependency_impacts": [
                    item.model_dump(mode="json") for item in operation.dependency_impacts
                ],
                "dependency_entry_bindings": [
                    item.model_dump(mode="json")
                    for item in operation.dependency_entry_bindings
                ],
                "prior_staled_decision_sha256": operation.prior_staled_decision_sha256,
                "search_completion_status": operation.search_completion_status,
                "unsatisfied_lanes": operation.unsatisfied_lanes,
                "operational_status": operation.operational_status,
            },
            actor=actor,
            receipt_idempotency_key=f"{operation.operation_id}.receipt",
            completion_idempotency_key=f"{operation.operation_id}.completed",
        )
        return receipt
    raise LiteratureConflictError(f"unsupported recoverable emission state: {operation.state}")


def reconcile_emission(
    project_root: str | Path,
    *,
    operation_id: str,
    actor: ActorProvenanceV1,
) -> P2EmissionReceiptV1 | P2EmissionOperationRevisionV1:
    """Validate both stores, then resume the deterministic transaction."""

    validation = LiteratureStore(project_root).validate()
    recoverable_tail = validation["recoverable_completion_tail"]
    if (
        recoverable_tail is not None
        and recoverable_tail["operation_id"] != operation_id
    ):
        raise LiteratureConflictError(
            "reconciliation must complete the exact recoverable tail first: "
            f"{recoverable_tail['operation_id']}"
        )
    EdgeBacklogStore(project_root).validate()
    result = emit_prepared(project_root, operation_id=operation_id, actor=actor)
    completed_validation = LiteratureStore(project_root).validate()
    if completed_validation["status"] != "PASS":
        raise LiteratureIntegrityError(
            "emission reconciliation did not restore a fully completed P3 store"
        )
    EdgeBacklogStore(project_root).validate()
    return result


__all__ = ["emit_prepared", "prepare_emission", "reconcile_emission"]
