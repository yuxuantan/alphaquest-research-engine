from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from alphaquest.research.registry import _classify_unreviewed_variants, _classify_unreviewed_verdicts
from alphaquest.studio.sequential_variants import SequentialVariantService


def _run(source: Path | None, *, run_uid: str) -> dict:
    return {
        "run_uid": run_uid,
        "campaign_id": "demo",
        "variant_id": "v01",
        "verdict": "FAIL",
        "summary_path": "research/evidence/runs/demo/v01/summary.json",
        "source_config_path": str(source) if source else None,
        "output_dir": "research/evidence/runs/demo/v01/ES/run1",
    }


def test_terminal_verdict_without_manual_mechanics_review_is_soft_archived(tmp_path: Path) -> None:
    runs = [_run(None, run_uid="unreviewed")]

    archived = _classify_unreviewed_verdicts(tmp_path, runs)
    variants = [{"campaign_id": "demo", "variant_id": "v01", "definition_path": "campaigns/demo/v01"}]
    archived_variants = _classify_unreviewed_variants(variants, runs)

    assert archived[0]["original_verdict"] == "FAIL"
    assert runs[0]["archived"] == 1
    assert runs[0]["verdict"] == "FAIL"
    assert archived_variants[0]["variant_id"] == "v01"
    assert variants[0]["archived"] == 1


def test_hash_bound_fixed_sample_review_keeps_terminal_verdict_active(tmp_path: Path) -> None:
    config = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    approval = tmp_path / "research_artifacts/validation_approvals/demo/v01/approval.json"
    evidence = tmp_path / "research/evidence/runs/demo/v01/ES/mechanics_validation/validation_runs/core"
    config.parent.mkdir(parents=True)
    approval.parent.mkdir(parents=True)
    evidence.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "research_metadata": {
                    "validation_gate": {
                        "required": True,
                        "approval_path": str(approval.relative_to(tmp_path)),
                        "evidence_dir": str(evidence.relative_to(tmp_path)),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    metadata = {"schema_version": "alphaquest.validation/v1", "input_data_hash": "d" * 64}
    (evidence / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    approval.write_text(
        json.dumps(
            {
                "schema": "alphaquest.validation-approval/v1",
                "status": "approved_for_testing",
                "review_scope": "implementation_matches_frozen_specification",
                "config_hash": config_hash,
                "input_data_hash": "d" * 64,
                "validation_schema_version": "alphaquest.validation/v1",
                "fixed_random_sample_size": 5,
                "fixed_random_seed": 0,
                "parameter_mode": "declared_defaults",
            }
        ),
        encoding="utf-8",
    )
    runs = [_run(config, run_uid="reviewed")]

    archived = _classify_unreviewed_verdicts(tmp_path, runs)

    assert archived == []
    assert runs[0]["archived"] == 0


def test_next_variant_unlocks_only_after_reviewed_fail(tmp_path: Path, monkeypatch) -> None:
    service = SequentialVariantService(tmp_path)
    campaign_root = tmp_path / "research/campaigns/active/demo"
    config = campaign_root / "variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("campaign_id: demo\nvariant_id: v01\n", encoding="utf-8")
    result = tmp_path / "research/evidence/runs/demo/v01/ES/run1/reporting_v2/result_bundle_v2.json"
    result.parent.mkdir(parents=True)
    result.write_text('{"campaign_id":"demo","variant_id":"v01","verdict":"FAIL"}\n', encoding="utf-8")
    (result.parent.parent / "source_config.yaml").write_text(
        "campaign_id: demo\nvariant_id: v01\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        service, "_draft", lambda _campaign_id: SimpleNamespace(variants=[SimpleNamespace(variant_id="v01")])
    )
    monkeypatch.setattr(service, "_campaign_root", lambda _campaign_id: campaign_root)
    monkeypatch.setattr(service, "_latest_result", lambda *_args: (result, {"verdict": "FAIL"}))
    monkeypatch.setattr(
        "alphaquest.studio.sequential_variants.inspect_historical_validation_approval",
        lambda _cfg, _path: {"status": "APPROVED_FOR_TESTING"},
    )

    state = service.eligibility("demo")

    assert state["eligible"] is True
    assert state["next_variant_id"] == "v02"

    draft_payload = {
        "title": "Demo edge",
        "expected_mechanism": "a repeatable completed-bar behavior",
        "certified_recipe": "opening_range_breakout",
        "execution": {},
        "known_failure_modes": ["The behavior may be absent."],
        "variants": [
            {
                "variant_id": "v01",
                "stop": {"module": "points_from_entry"},
                "target": {"module": "fixed_r"},
            }
        ],
    }
    monkeypatch.setattr(
        service,
        "_draft",
        lambda _campaign_id: SimpleNamespace(
            variants=[SimpleNamespace(variant_id="v01")],
            model_dump=lambda **_kwargs: draft_payload,
        ),
    )
    failure = {
        "verdict": "FAIL",
        "stage_criteria": [
            {
                "stage": "wfa_oos_monte_carlo",
                "metric": "ruin_probability",
                "result": "FAIL",
                "actual": {"value": 0.4},
                "threshold": {"value": 0.1},
                "reason": "drawdown paths exceeded the limit",
            }
        ],
    }
    monkeypatch.setattr(service, "_latest_result", lambda *_args: (result, failure))
    proposed = service.suggestion("demo")
    assert proposed["failure_context"]["metric"] == "ruin_probability"
    assert proposed["variant"]["stop"]["module"] == "fixed_dollar_per_contract"
    assert "wfa_oos_monte_carlo/ruin_probability" in proposed["variant"]["mechanic_rationale"]

    monkeypatch.setattr(service, "_latest_result", lambda *_args: (result, {"verdict": "PASS"}))
    blocked = service.eligibility("demo")
    assert blocked["eligible"] is False
    assert any("only FAIL" in item for item in blocked["blockers"])


def test_event_replay_next_variant_uses_the_sole_active_unused_certification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SequentialVariantService(tmp_path)
    draft_payload = {
        "title": "Event edge",
        "authoring_lane": "certified_event_replay",
        "known_failure_modes": ["The economic behavior may be absent."],
        "variants": [
            {
                "variant_id": "v03",
                "entry": {"module": "event_v3"},
                "stop": {"module": "old_stop"},
                "target": {"module": "old_target"},
            }
        ],
    }
    draft = SimpleNamespace(
        authoring_lane="certified_event_replay",
        variants=[SimpleNamespace(variant_id="v03")],
        model_dump=lambda **_kwargs: draft_payload,
    )
    state = {
        "eligible": True,
        "campaign_id": "demo",
        "current_variant_id": "v03",
        "next_variant_id": "v04",
        "variant_count": 3,
        "max_variants": 5,
        "mechanics_approval_status": "APPROVED_FOR_TESTING",
        "predecessor_verdict": "FAIL",
        "predecessor_result_path": "result_bundle_v2.json",
        "blockers": [],
    }
    certification = SimpleNamespace(
        strategy_id="event_v4",
        lane="canonical_event_replay",
        entry_module="event_v4",
        stop_module="event_fill_stop",
        target_module="event_opposite_value_target",
        parameters={
            "fixed_value": SimpleNamespace(default=10, tunable=False, choices=()),
            "entry_choice": SimpleNamespace(default=0.2, tunable=True, choices=(0.1, 0.2, 0.3)),
            "stop_choice": SimpleNamespace(default=1.5, tunable=True, choices=(1.25, 1.5, 1.75)),
        },
        studio={
            "visible": True,
            "label": "Event strategy v04",
            "description": "Adds separate post-event confirmation and a materially different frozen target.",
            "mechanics_review": {
                "mechanic_expresses_edge": "The successor preserves the same event-replay economic edge.",
                "entry_logic_rationale": "Entry uses a separate causal confirmation after the predecessor event.",
                "stop_loss_rationale": "The stop is resolved from the causal fill path.",
                "target_exit_rationale": "The target is frozen before entry from causal context.",
                "session_logic_rationale": "The same governed intraday session and flatten boundary apply.",
                "known_failure_modes": "Confirmation may arrive late and the target may remain unreachable.",
            },
        },
    )
    monkeypatch.setattr(service, "eligibility", lambda _campaign_id: state)
    monkeypatch.setattr(service, "_draft", lambda _campaign_id: draft)
    monkeypatch.setattr(
        service,
        "_latest_result",
        lambda *_args: (
            Path("result_bundle_v2.json"),
            {"verdict": "FAIL", "verdict_message": "The predecessor failed its frozen objective."},
        ),
    )
    monkeypatch.setattr(
        "alphaquest.studio.sequential_variants.load_strategy_certifications",
        lambda *_args, **_kwargs: {"event_v4": certification},
    )
    monkeypatch.setattr(
        "alphaquest.studio.sequential_variants.suggest_variant_card",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("event campaigns must not use the generic recipe generator")
        ),
    )

    proposed = service.suggestion("demo")

    variant = proposed["variant"]
    assert variant["variant_id"] == "v04"
    assert variant["entry"]["module"] == "event_v4"
    assert variant["entry"]["params"]["mechanics"] == {
        "fixed_value": 10,
        "entry_choice": 0.2,
        "stop_choice": 1.5,
    }
    assert variant["stop"]["module"] == "event_fill_stop"
    assert variant["target"]["module"] == "event_opposite_value_target"
    assert variant["event_parameter_grid"] == {
        "entry_choice": [0.1, 0.2, 0.3],
        "stop_choice": [1.25, 1.5, 1.75],
    }
    assert variant["confirmed"] is False
    assert "sole active, unused certified event successor" in variant["mechanic_rationale"]

    draft_payload["variants"][0]["entry"]["module"] = "event_v4"
    with pytest.raises(ValueError, match="no unused active certified event strategy"):
        service.suggestion("demo")


def test_next_variant_inherits_the_terminal_predecessor_execution_contract(
    tmp_path: Path,
) -> None:
    service = SequentialVariantService(tmp_path)

    execution = service._predecessor_execution_settings(
        {
            "data": {"rth_start": "09:30:00", "rth_end": "16:00:00"},
            "core": {
                "initial_balance": 50_000.0,
                "tick_size": 0.25,
                "point_value": 50.0,
                "tick_value": 12.5,
                "commission_per_contract": 1.55,
                "entry_slippage_ticks": 1,
                "contracts": 2,
            },
            "apex_rules": {
                "latest_entry_time": "15:30:00",
                "force_flatten_time": "15:55:00",
                "latest_flat_time": "15:55:00",
            },
            "prop_rules": {"profile": "configured_local_profile"},
        }
    )

    assert execution == {
        "session_start": "09:30:00",
        "session_end": "16:00:00",
        "latest_entry_time": "15:30:00",
        "flatten_time": "15:55:00",
        "latest_flat_time": "15:55:00",
        "overnight_allowed": False,
        "initial_balance": 50_000.0,
        "tick_size": 0.25,
        "point_value": 50.0,
        "tick_value": 12.5,
        "commission_per_contract": 1.55,
        "slippage_ticks": 1.0,
        "contracts": 2,
        "prop_profile": "configured_local_profile",
    }
