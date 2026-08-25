from __future__ import annotations

import json

import pytest

from alphaquest.research.experiment_registry import (
    AttemptFinalizationRecovery,
    AttemptReservation,
    AttemptResolution,
    AttemptStatusTransition,
    ExperimentConflictError,
    ExperimentIntegrityError,
    ExperimentRegistry,
    ExperimentRegistryError,
    ExperimentTransitionError,
    reservation_from_campaign_config,
)


def _hash(value) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _reservation(
    *,
    attempt_id="attempt_001",
    variant_id="v01",
    edge="a" * 64,
    parent=None,
    parent_registered=True,
    parent_evidence="8" * 64,
    config="c" * 64,
):
    return AttemptReservation(
        campaign_id="demo",
        variant_id=variant_id,
        attempt_id=attempt_id,
        parent_attempt_id=parent,
        parent_recorded_in_registry=(None if parent is None else parent_registered),
        parent_evidence_sha256=(
            None if parent is None or parent_registered else parent_evidence
        ),
        kind="initial" if parent is None else "rescue",
        economic_edge_fingerprint_sha256=edge,
        research_objectives_sha256="b" * 64,
        config_sha256=config,
        data_sha256="d" * 64,
        parameter_grid_sha256="e" * 64,
        stages=("core_grid", "walk_forward_analysis", "monte_carlo"),
        reserved_at="2026-08-14T08:00:00+00:00",
    )


def test_experiment_reservation_is_idempotent_conflict_safe_and_counted_by_edge(tmp_path):
    path = tmp_path / "experiment_registry.jsonl"
    registry = ExperimentRegistry(path)
    reservation = _reservation()

    first = registry.reserve(reservation)
    retried = registry.reserve(reservation)

    assert first == retried
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    receipt = json.loads(path.with_suffix(".jsonl.head.json").read_text(encoding="utf-8"))
    assert receipt["record_count"] == 1
    assert receipt["terminal_record_sha256"] == first["record_sha256"]
    assert registry.current_status("demo", "v01", "attempt_001") == "RESERVED"
    assert registry.trial_count("a" * 64) == 1
    assert registry.trial_counts_by_edge() == {"a" * 64: 1}

    with pytest.raises(ExperimentConflictError, match="different immutable inputs"):
        registry.reserve(_reservation(config="9" * 64))

    # A conflicting retry never mutates the retained reservation.
    assert len(registry.events()) == 1
    assert registry.attempts()[0]["config_sha256"] == "c" * 64


def test_experiment_transitions_and_resolutions_are_append_only_and_immutable(tmp_path):
    path = tmp_path / "experiment_registry.jsonl"
    registry = ExperimentRegistry(path)
    registry.reserve(_reservation())
    transition = AttemptStatusTransition(
        campaign_id="demo",
        variant_id="v01",
        attempt_id="attempt_001",
        from_status="RESERVED",
        to_status="RUNNING",
        recorded_at="2026-08-14T08:01:00+00:00",
        reason="Generic research runner accepted the hash-bound reservation.",
    )
    resolution = AttemptResolution(
        campaign_id="demo",
        variant_id="v01",
        attempt_id="attempt_001",
        from_status="RUNNING",
        terminal_status="COMPLETED",
        recorded_at="2026-08-14T09:00:00+00:00",
        reason="All reserved PnL-bearing stages reached a terminal scientific verdict.",
        research_verdict="FAIL",
        result_sha256="f" * 64,
    )

    registry.transition(transition)
    registry.transition(transition)
    registry.resolve(resolution)
    registry.resolve(resolution)

    assert len(registry.events()) == 3
    assert registry.current_status("demo", "v01", "attempt_001") == "COMPLETED"
    attempt = registry.attempts()[0]
    assert attempt["current_status"] == "COMPLETED"
    assert attempt["resolution"]["research_verdict"] == "FAIL"
    assert registry.trial_count("a" * 64) == 1

    with pytest.raises(ExperimentTransitionError, match="COMPLETED"):
        registry.resolve(
            AttemptResolution(
                campaign_id="demo",
                variant_id="v01",
                attempt_id="attempt_001",
                from_status="RUNNING",
                terminal_status="FAILED",
                recorded_at="2026-08-14T09:01:00+00:00",
                reason="Conflicting second terminal disposition.",
                research_verdict="NEEDS MANUAL REVIEW",
            )
        )


def test_finalization_recovery_amends_only_unbound_operational_failure(tmp_path):
    registry = ExperimentRegistry(tmp_path / "experiment_registry.jsonl")
    registry.reserve(_reservation())
    registry.transition(
        AttemptStatusTransition(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="attempt_001",
            from_status="RESERVED",
            to_status="RUNNING",
            recorded_at="2026-08-14T08:01:00+00:00",
            reason="Runner accepted the reservation.",
        )
    )
    failed = registry.resolve(
        AttemptResolution(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="attempt_001",
            from_status="RUNNING",
            terminal_status="FAILED",
            recorded_at="2026-08-14T09:00:00+00:00",
            reason="Post-publication finalization failed after the runner completed.",
            research_verdict="NEEDS MANUAL REVIEW",
        )
    )
    recovery = AttemptFinalizationRecovery(
        campaign_id="demo",
        variant_id="v01",
        attempt_id="attempt_001",
        prior_resolution_sha256=failed["record_sha256"],
        recorded_at="2026-08-14T09:05:00+00:00",
        reason="Hash-valid publication recovered without replaying the runner.",
        research_verdict="FAIL",
        result_sha256="f" * 64,
    )

    first = registry.recover_finalization(recovery)
    repeated = registry.recover_finalization(recovery)

    assert first == repeated
    assert registry.current_status("demo", "v01", "attempt_001") == "COMPLETED"
    attempt = registry.attempts()[0]
    assert attempt["resolution"]["event_type"] == "ATTEMPT_FINALIZATION_RECOVERED"
    assert attempt["resolution"]["research_verdict"] == "FAIL"
    assert attempt["resolution"]["result_sha256"] == "f" * 64
    assert registry.trial_count("a" * 64) == 1


def test_experiment_registry_requires_preexisting_parent_and_counts_all_reserved_trials(tmp_path):
    registry = ExperimentRegistry(tmp_path / "experiment_registry.jsonl")

    with pytest.raises(ExperimentConflictError, match="Parent attempt"):
        registry.reserve(
            _reservation(attempt_id="attempt_002", variant_id="v02", parent="attempt_001")
        )

    registry.reserve(_reservation())
    registry.reserve(
        _reservation(attempt_id="attempt_002", variant_id="v02", parent="attempt_001")
    )
    registry.resolve(
        AttemptResolution(
            campaign_id="demo",
            variant_id="v02",
            attempt_id="attempt_002",
            from_status="RESERVED",
            terminal_status="CANCELLED",
            recorded_at="2026-08-14T08:02:00+00:00",
            reason="Data hash became unavailable before runner start.",
            research_verdict="NEEDS MANUAL REVIEW",
        )
    )

    # Cancelled and failed starts still consume experiment degrees of freedom.
    assert registry.trial_count("a" * 64) == 2
    assert registry.trial_counts_by_edge() == {"a" * 64: 2}


def test_experiment_registry_accepts_explicit_hash_bound_legacy_external_parent(tmp_path):
    registry = ExperimentRegistry(tmp_path / "experiment_registry.jsonl")

    registry.reserve(
        _reservation(
            attempt_id="rescue_legacy_001",
            variant_id="v02",
            parent="original",
            parent_registered=False,
            parent_evidence="7" * 64,
        )
    )

    attempt = registry.attempts()[0]
    assert attempt["parent_attempt_id"] == "original"
    assert attempt["parent_recorded_in_registry"] is False
    assert attempt["parent_evidence_sha256"] == "7" * 64
    assert registry.trial_count("a" * 64) == 1


def test_experiment_registry_fails_closed_on_hash_chain_or_record_mutation(tmp_path):
    path = tmp_path / "experiment_registry.jsonl"
    registry = ExperimentRegistry(path)
    registry.reserve(_reservation())
    registry.transition(
        AttemptStatusTransition(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="attempt_001",
            from_status="RESERVED",
            to_status="RUNNING",
            recorded_at="2026-08-14T08:01:00+00:00",
            reason="Runner start.",
        )
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["config_sha256"] = "9" * 64
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ExperimentIntegrityError, match="record hash mismatch"):
        registry.events()


def test_experiment_registry_head_receipt_detects_last_record_truncation(tmp_path):
    path = tmp_path / "experiment_registry.jsonl"
    registry = ExperimentRegistry(path)
    registry.reserve(_reservation())
    registry.transition(
        AttemptStatusTransition(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="attempt_001",
            from_status="RESERVED",
            to_status="RUNNING",
            recorded_at="2026-08-14T08:01:00+00:00",
            reason="Runner start.",
        )
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n", encoding="utf-8")

    with pytest.raises(ExperimentIntegrityError, match="tail/count mismatch"):
        registry.events()


def test_experiment_registry_rejects_transition_without_reservation(tmp_path):
    registry = ExperimentRegistry(tmp_path / "experiment_registry.jsonl")
    transition = AttemptStatusTransition(
        campaign_id="demo",
        variant_id="v01",
        attempt_id="missing",
        from_status="RESERVED",
        to_status="RUNNING",
        recorded_at="2026-08-14T08:01:00+00:00",
        reason="Runner start.",
    )

    with pytest.raises(ExperimentTransitionError, match="no reservation"):
        registry.transition(transition)


def test_reservation_helper_binds_current_objectives_grid_and_stage_order():
    objectives = {"minimum_mar": 1.0, "maximum_drawdown_fraction": 0.1}
    fingerprint = {"market_behavior": "intraday continuation", "holding_period": "30m"}
    grid = {"entry.length": [10, 20], "sl.ticks": [6, 8]}
    config = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "attempt_id": "original",
        "attempt_kind": "original",
        "research_objectives": objectives,
        "research_objectives_sha256": _hash(objectives),
        "core_grid": {"parameters": grid},
        "campaign_tests": {
            "stage_order": ["limited_core_grid_test", "walk_forward_analysis"]
        },
    }

    reservation = reservation_from_campaign_config(
        config,
        config_sha256="1" * 64,
        data_sha256="2" * 64,
        economic_edge_fingerprint=fingerprint,
        reserved_at="2026-08-14T08:00:00+00:00",
    )

    assert reservation.research_objectives_sha256 == _hash(objectives)
    assert reservation.parameter_grid_sha256 == _hash(grid)
    assert reservation.economic_edge_fingerprint_sha256 == _hash(fingerprint)
    assert reservation.stages == ("limited_core_grid_test", "walk_forward_analysis")


def test_reservation_helper_requires_explicit_legacy_parent_evidence():
    objectives = {"minimum_mar": 1.0}
    config = {
        "campaign_id": "demo",
        "variant_id": "v02",
        "attempt_id": "rescue_legacy_001",
        "attempt_kind": "rescue",
        "parent_attempt_id": "original",
        "research_objectives": objectives,
        "research_objectives_sha256": _hash(objectives),
        "core_grid": {"parameters": {}},
        "campaign_tests": {"stage_order": ["limited_core_grid_test"]},
    }

    with pytest.raises(ExperimentRegistryError, match="explicit registered-parent decision"):
        reservation_from_campaign_config(
            config,
            config_sha256="1" * 64,
            data_sha256="2" * 64,
            economic_edge_fingerprint="3" * 64,
            reserved_at="2026-08-14T08:00:00+00:00",
        )

    reservation = reservation_from_campaign_config(
        config,
        config_sha256="1" * 64,
        data_sha256="2" * 64,
        economic_edge_fingerprint="3" * 64,
        reserved_at="2026-08-14T08:00:00+00:00",
        parent_recorded_in_registry=False,
        parent_evidence_sha256="4" * 64,
    )
    assert reservation.parent_recorded_in_registry is False
    assert reservation.parent_evidence_sha256 == "4" * 64
