from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

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
    monkeypatch.setattr(service, "_draft", lambda _campaign_id: SimpleNamespace(variants=[SimpleNamespace(variant_id="v01")]))
    monkeypatch.setattr(service, "_campaign_root", lambda _campaign_id: campaign_root)
    monkeypatch.setattr(service, "_latest_result", lambda *_args: (result, {"verdict": "FAIL"}))
    monkeypatch.setattr(
        "alphaquest.studio.sequential_variants.MechanicsApprovalService.inspect",
        lambda _self, _path: {"status": "APPROVED_FOR_TESTING"},
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
