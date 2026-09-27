from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
import yaml

import alphaquest.run_mvp_diagnostic as mvp
from alphaquest.research.campaign_stages import (
    PRE_ACCEPTANCE_STAGE_ORDER,
    STAGE_LABELS,
    _annotate_stage_decisions,
    _error_stage,
    canonicalize_campaign_config,
)
from alphaquest.research.factory_policy import research_factory_binding, research_objectives_sha256
from alphaquest.utils.hashing import file_sha256
from alphaquest.validation.promotion_gate import SAMPLING_POLICY_SHA256, SAMPLING_POLICY_VERSION
from alphaquest.version import ENGINE_CONTRACT_VERSION


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _project(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    root = tmp_path / "project"
    _write_yaml(
        root / "config/storage_layout.yaml",
        {
            "schema": "alphaquest.storage-layout/v1",
            "active_campaign_root": "research/campaigns/active",
            "evidence_roots": ["research/evidence/runs"],
            "dataset_root": "research/datasets",
        },
    )
    dataset_id = "synthetic_fixture_es"
    canonical = root / f"research/datasets/{dataset_id}/bars.csv"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-05T14:30:00Z,100,101,99,100.5,10\n",
        encoding="utf-8",
    )
    canonical_hash = file_sha256(canonical)
    dataset_manifest = {
        "schema": "alphaquest.dataset-manifest/v1",
        "dataset_id": dataset_id,
        "source": "csv",
        "path": str(canonical.relative_to(root)),
        "symbol": "ES",
        "timeframe": "1m",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "timestamp_semantics": "bar_open",
        "source_timestamp_semantics": "bar_open",
        "source_sha256": canonical_hash,
        "canonical_sha256": canonical_hash,
        "coverage_start": "2023-06-30T13:30:00+00:00",
        "coverage_end": "2026-01-16T15:30:00+00:00",
        "roll_policy": "single_contract",
        "continuous_contract": "none",
        "contract_column": None,
        "source_contract_column": None,
        "contract_count": 1,
        "roll_calendar": None,
        "roll_calendar_sha256": None,
        "transformations": ["test fixture canonicalization"],
        "row_count": 1,
        "dropped_row_count": 0,
        "gap_count": 0,
        "duplicate_count": 0,
        "out_of_order_count": 0,
        "invalid_ohlc_count": 0,
        "cadence_violation_count": 0,
        "certified_features": [],
        "quality_verdict": "PASS",
        "quality_notes": [],
        "event_source": None,
    }
    _write_json(canonical.parent / "dataset_manifest.json", dataset_manifest)

    campaign_root = root / "research/campaigns/active/synthetic_recipe_demo"
    source_path = campaign_root / "variants/v01/config.yaml"
    evidence_dir = root / "research/evidence/mechanics/validation_runs/core"
    evidence_dir.mkdir(parents=True)
    _write_json(evidence_dir / "metadata.json", {"schema_version": "1.6"})
    approval_path = root / "research_artifacts/validation_approvals/synthetic_recipe_demo/v01/approval.json"
    objectives = {
        "schema": "alphaquest.research-objectives/v1",
        "development_goal": "Exercise the isolated synthetic diagnostic path.",
        "development_deadline": "2099-12-31",
        "evaluation_horizon_months": 24,
        "minimum_annualized_return_fraction": 0.2,
        "minimum_mar": 0.4,
        "maximum_drawdown_fraction": 0.1,
        "minimum_complete_wfa_windows": 3,
        "minimum_wfa_oos_trades": 50,
        "minimum_acceptance_oos_trades": 30,
        "monte_carlo_min_runs": 8000,
        "monte_carlo_horizon_months": 6,
        "minimum_net_profit_probability": 0.7,
        "maximum_account_breach_probability": 0.1,
        "forward_incubation_min_calendar_days": 90,
        "forward_incubation_min_trades": 30,
        "maximum_variants": 1,
        "abandonment_rules": ["Stop after this fixture demonstration."],
        "retirement_rules": ["Never promote this synthetic fixture."],
        "confirmed": True,
    }
    research_factory = research_factory_binding(
        objectives,
        dataset={
            "dataset_id": dataset_id,
            "canonical_sha256": canonical_hash,
            "source_sha256": canonical_hash,
            "coverage_start": dataset_manifest["coverage_start"],
            "coverage_end": dataset_manifest["coverage_end"],
        },
    )
    objectives_sha256 = research_objectives_sha256(objectives)
    source = {
        "campaign_id": "synthetic_recipe_demo",
        "variant_id": "v01",
        "test_run_id": "run1",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "parent_attempt_id": None,
        "strategy_name": "v01",
        "symbol": "ES",
        "dataset_id": dataset_id,
        "timeframe": "1m",
        "research_objectives": objectives,
        "research_objectives_sha256": objectives_sha256,
        "research_factory": research_factory,
        "research_metadata": {
            "mechanics_review_required": True,
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "parameter_mode": "declared_defaults",
                "manual_review_random_sample_size": 5,
                "manual_review_seed": 7,
                "evidence_dir": str(evidence_dir.relative_to(root)),
                "approval_path": str(approval_path.relative_to(root)),
            },
        },
        "data": {
            "dataset_id": dataset_id,
            "source": "csv",
            "raw_csv": str(canonical.relative_to(root)),
            "symbol": "ES",
            "source_timeframe": "1m",
            "timezone": "America/New_York",
            "source_timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
            "timestamp_semantics": "bar_open",
            "source_timestamp_semantics": "bar_open",
            "source_sha256": canonical_hash,
            "canonical_sha256": canonical_hash,
            "coverage_start": dataset_manifest["coverage_start"],
            "coverage_end": dataset_manifest["coverage_end"],
            "roll_policy": "single_contract",
            "continuous_contract": "none",
            "contract_column": None,
            "contract_count": 1,
            "certified_features": [],
        },
        "strategy": {
            "entry": {
                "module": "calendar_session_bias",
                "params": {"signal_time": "09:35:00", "weekday_directions": {"0": "long"}},
            },
            "sl": {"module": "points_from_entry", "params": {"stop_points": 10.0}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.5}},
            "flatten_time": "10:25:00",
        },
        "core": {
            "tick_size": 0.25,
            "point_value": 50.0,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
        },
        "apex_rules": {
            "enabled": True,
            "force_flatten_enabled": True,
            "force_flatten_time": "10:25:00",
            "latest_flat_time": "10:26:00",
            "latest_entry_time": "10:15:00",
        },
        "core_grid": {"parameters": {}},
        "wfa": {"parameters": {}},
    }
    _write_yaml(source_path, source)
    source_hash = file_sha256(source_path)
    _write_json(
        approval_path,
        {
            "schema": "alphaquest.validation-approval/v1",
            "status": "approved_for_testing",
            "reviewer": "SIMULATED_MVP_FIXTURE_ONLY",
            "reviewed_at": "2026-09-27T00:00:00+00:00",
            "notes": "Synthetic mechanics decision without owner authority.",
            "config_hash": source_hash,
            "input_data_hash": canonical_hash,
            "lane": "bar",
            "validation_schema_version": "1.6",
            "fixed_random_sample_size": 5,
            "fixed_random_seed": 7,
            "parameter_mode": "declared_defaults",
            "review_scope": "implementation_matches_frozen_specification",
            "profitability_approval": False,
            "sampled_trade_ids": [1, 2, 3, 4, 5],
            "sampling_categories": {
                "random_trades": [1, 2, 3, 4, 5],
                "warning_representatives": [],
                "resolved_ambiguities": [],
                "universal_coverage": [],
            },
            "sampling_policy_version": SAMPLING_POLICY_VERSION,
            "sampling_policy_sha256": SAMPLING_POLICY_SHA256,
        },
    )
    signature = "85bf616b7744fbef864ffddca3775d556941f5a10c91ca4f5c06202419bd7270"
    draft_sha256 = "2" * 64
    campaign = {
        "campaign_id": source["campaign_id"],
        "created_at": "2026-09-27",
        "instrument": "ES",
        "timeframe": "1m",
        "variant_protocol": "sequential_failure_informed",
        "research_objectives": objectives,
        "research_objectives_sha256": objectives_sha256,
        "authoring_lane": "certified_recipe",
        "certified_recipe": "calendar_session_bias",
        "event_strategy": None,
        "research_factory": research_factory,
        "variants": ["v01"],
        "variant_distinctions": {"v01": {"mechanic_signature": signature}},
    }
    strategy_spec = {
        "schema": "alphaquest.strategy-spec/v1",
        "campaign_id": source["campaign_id"],
        "draft_sha256": draft_sha256,
        "research_objectives": objectives,
        "research_objectives_sha256": objectives_sha256,
        "frozen": True,
        "authoring_lane": "certified_recipe",
        "certified_recipe": "calendar_session_bias",
        "event_strategy": None,
        "strategy_certification": None,
        "variant_strategy_certifications": {},
        "research_factory": research_factory,
        "dataset": dataset_manifest,
        "variants": [
            {
                "variant_id": "v01",
                "mechanic_signature": signature,
                "entry": {**source["strategy"]["entry"], "parameter_grid": {}},
                "stop": {**source["strategy"]["sl"], "parameter_grid": {}},
                "target": {**source["strategy"]["tp"], "parameter_grid": {}},
            }
        ],
    }
    _write_yaml(campaign_root / "campaign.yaml", campaign)
    _write_yaml(campaign_root / "strategy_spec.yaml", strategy_spec)
    compiled = {
        "campaign.yaml": mvp._compiled_object_sha256(campaign),
        "strategy_spec.yaml": mvp._compiled_object_sha256(strategy_spec),
        "variants/v01/config.yaml": mvp._compiled_object_sha256(source),
    }
    _write_json(
        campaign_root / "authoring_manifest.json",
        {
            "schema": "alphaquest.authoring-manifest/v1",
            "campaign_id": source["campaign_id"],
            "draft_schema": "alphaquest.campaign-draft/v1",
            "draft_sha256": draft_sha256,
            "research_objectives_sha256": objectives_sha256,
            "authoring_lane": "certified_recipe",
            "certified_recipe": "calendar_session_bias",
            "event_strategy": None,
            "strategy_certification": None,
            "variant_strategy_certifications": {},
            "compiler": "alphaquest.authoring.CampaignCompiler/v1",
            "created_at": "2026-09-27",
            "dataset_id": dataset_id,
            "dataset_canonical_sha256": canonical_hash,
            "research_factory": research_factory,
            "variant_count": 1,
            "variant_protocol": "sequential_failure_informed",
            "max_variants": 1,
            "planned_files": [
                "campaign.yaml",
                "strategy_spec.yaml",
                "authoring_manifest.json",
                "variants/v01/config.yaml",
            ],
            "variant_mechanic_signatures": {"v01": signature},
            "compiled_document_sha256": compiled,
            "generated_python_stubs": False,
        },
    )

    run = root / "research/evidence/runs/synthetic_recipe_demo/v01/ES/run1"
    run.mkdir(parents=True)
    (run / "source_config.yaml").write_bytes(source_path.read_bytes())
    effective = canonicalize_campaign_config(source, include_acceptance=False)
    _write_yaml(run / "effective_config.yaml", effective)
    run_uid = "920c43cb-7c65-413e-9491-f8a0e375d8e5"
    (run / "run_uid.txt").write_text(run_uid, encoding="utf-8")
    gate = {
        "required": True,
        "status": "APPROVED_FOR_TESTING",
        "verdict": "PASS",
        "errors": [],
        "warnings": [],
        "config_path": str(source_path),
        "lane": "bar",
        "evidence_dir": str(evidence_dir),
        "approval_path": str(approval_path),
        "config_hash": source_hash,
        "input_data_hash": canonical_hash,
        "strategy_implementation_version": None,
        "strategy_implementation_sha256": None,
        "strategy_certification_manifest_sha256": None,
        "validation_schema_version": "1.6",
        "approval_status": "approved_for_testing",
        "reviewer": "SIMULATED_MVP_FIXTURE_ONLY",
        "reviewed_at": "2026-09-27T00:00:00+00:00",
    }
    stages: list[dict[str, object]] = []
    for index, stage in enumerate(PRE_ACCEPTANCE_STAGE_ORDER):
        stage_dir = run / stage
        if index == 0:
            output = stage_dir / "summary.json"
            _write_json(output, {"fixture": True})
            result: dict[str, object] = {
                "stage": stage,
                "label": STAGE_LABELS[stage],
                "status": "failed",
                "passed": False,
                "started_at": "2026-09-27T00:00:00",
                "completed_at": "2026-09-27T00:00:01",
                "duration_seconds": 1.0,
                "criteria": [
                    {
                        "metric": "summary.total_combinations_tested",
                        "actual": 1,
                        "expected": {"valid_parameter_combination_count": "1 fixed combo or 8-120 tunable combos"},
                        "passed": True,
                        "decision_role": "scientific_validity",
                    },
                    {
                        "metric": "summary.percentage_profitable_iterations",
                        "actual": 0.0,
                        "expected": {"min": 0.7},
                        "passed": False,
                        "decision_role": "scientific_validity",
                    }
                ],
                "artifacts": [str(output.relative_to(root))],
            }
            result = _annotate_stage_decisions(result)
        else:
            result = _annotate_stage_decisions(
                _error_stage(stage, RuntimeError("upstream fixture evidence unavailable"))
            )
        stages.append(result)
        _write_json(stage_dir / "stage_result.json", result)
    preflight: dict[str, object] = {
        "passed": True,
        "configs_checked": [str(source_path.relative_to(root))],
        "failures": [],
        "warnings": [],
        "tests_ran": False,
        "include_generated_results": False,
        "data_sources_checked": 1,
        "data_cache_hits": 0,
        "terminal_configs_not_executed": 0,
    }
    receipt = root / "pre-run-preflight.json"
    _write_json(receipt, preflight)
    identity = {
        "run_uid": run_uid,
        "campaign_id": source["campaign_id"],
        "variant_id": "v01",
        "test_run_id": "run1",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "parent_attempt_id": None,
        "symbol": "ES",
        "dataset_id": dataset_id,
        "timeframe": "1m",
    }
    mechanic = {
        "entry_module": "calendar_session_bias",
        "take_profit_module": "fixed_r",
        "stop_loss_module": "points_from_entry",
        "flatten_time": "10:25:00",
    }
    variant_path = run / "variant.yaml"
    _write_yaml(
        variant_path,
        {
            "campaign_id": source["campaign_id"],
            "variant_id": "v01",
            "strategy_name": "v01",
            "mechanic": mechanic,
            "rescue_policy": {},
        },
    )
    variant_metadata = {
        "path": str(variant_path.relative_to(root)),
        "hash": file_sha256(variant_path),
        "mechanic": mechanic,
        "rescue_policy": {},
    }
    results_index = campaign_root / "results_index.yaml"
    _write_yaml(results_index, {"campaign_id": source["campaign_id"], "runs": []})
    summary = {
        **identity,
        "data_source": "csv",
        "raw_csv": str(canonical.relative_to(root)),
        "raw_parquet": None,
        "raw_dir": None,
        "campaign_metadata": None,
        "variant_metadata": variant_metadata,
        "config_hash": file_sha256(run / "effective_config.yaml"),
        "source_config_hash": source_hash,
        "config_path": str((run / "effective_config.yaml").relative_to(root)),
        "effective_config_path": str((run / "effective_config.yaml").relative_to(root)),
        "source_config_path": str(source_path),
        "source_config_snapshot_path": str((run / "source_config.yaml").relative_to(root)),
        "output_dir": str(run.relative_to(root)),
        "created_at": "2026-09-27T00:00:00",
        "updated_at": "2026-09-27T00:00:00",
        "passed": False,
        "halted": False,
        "stages": stages,
        "research_policy": effective["research_policy"],
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "diagnostic_only": True,
        "diagnostic_reasons": ["mandatory acceptance_oos_test was omitted"],
        "skip_validation": False,
        "fast_runtime_defaults": False,
        "authoritative_parallel_workers": None,
        "authoritative_core_grid_workers": None,
        "research_verdict": "NEEDS MANUAL REVIEW",
        "generic_objective_verdict": "NEEDS MANUAL REVIEW",
        "scientific_validity_verdict": "NEEDS MANUAL REVIEW",
        "submission_preflight": preflight,
        "mechanics_validation_gate": gate,
        "source_results_index_path": str(results_index.relative_to(root)),
    }
    manifest = {
        **identity,
        "data_source": summary["data_source"],
        "raw_csv": summary["raw_csv"],
        "raw_parquet": summary["raw_parquet"],
        "raw_dir": summary["raw_dir"],
        "campaign_metadata": summary["campaign_metadata"],
        "variant_metadata": summary["variant_metadata"],
        "research_policy": summary["research_policy"],
        "engine_contract_version": summary["engine_contract_version"],
        "config_source": str(source_path),
        "effective_config": str((run / "effective_config.yaml").relative_to(root)),
        "source_config_snapshot": str((run / "source_config.yaml").relative_to(root)),
        "config_hash": summary["config_hash"],
        "source_config_hash": source_hash,
        "source_results_index": str(results_index.relative_to(root)),
        "created_at": summary["created_at"],
        "updated_at": summary["updated_at"],
        "stage_order": PRE_ACCEPTANCE_STAGE_ORDER,
        "mechanics_validation_gate": gate,
        "submission_preflight": preflight,
        "diagnostic_only": True,
        "diagnostic_reasons": ["mandatory acceptance_oos_test was omitted"],
        "authoritative_parallel_workers": None,
        "authoritative_core_grid_workers": None,
        "research_verdict": "NEEDS MANUAL REVIEW",
        "generic_objective_verdict": "NEEDS MANUAL REVIEW",
        "scientific_validity_verdict": "NEEDS MANUAL REVIEW",
        "layout": "campaign_variant_symbol_run",
    }
    _write_json(run / "campaign_test_summary.json", summary)
    _write_json(run / "variant_test_summary.json", summary)
    _write_json(run / "run_manifest.json", manifest)
    return root, run, preflight


def _build(
    root: Path,
    run: Path,
    preflight: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "synthetic",
) -> dict[str, object]:
    monkeypatch.setattr(mvp, "run_preflight", lambda **_kwargs: preflight)
    return mvp.build_diagnostic_index(
        project_root=root,
        run_dir=run,
        preflight_receipt=root / "pre-run-preflight.json",
        mode=mode,
    )


def _update_summary_and_manifest(run: Path, update) -> None:
    summary_path = run / "campaign_test_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    update(summary)
    _write_json(summary_path, summary)
    _write_json(run / "variant_test_summary.json", summary)
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    update(manifest)
    _write_json(manifest_path, manifest)


def test_builds_bound_synthetic_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    report = _build(root, run, preflight, monkeypatch)

    assert report["overall_verdict"] == "NEEDS MANUAL REVIEW"
    assert report["passed"] is False
    assert set(report["assurance"].values()) == {False}
    assert report["assurance"]["data_origin_verified"] is False
    assert report["assurance"]["source_review_verified"] is False
    assert report["authoring"]["certified_recipe"] == "calendar_session_bias"
    published_config = next(
        document
        for document in report["authoring"]["documents"]
        if document["path"].endswith("variants/v01/config.yaml")
    )
    assert published_config["file_sha256"] == file_sha256(
        root / "research/campaigns/active/synthetic_recipe_demo/variants/v01/config.yaml"
    )
    assert published_config["compiled_object_sha256"]
    assert "sha256" not in published_config
    assert report["execution_contract"]["mechanic"]["entry_module"] == "calendar_session_bias"
    assert report["preflight"]["repository_engineering_tests_verified"] is False
    assert report["stages"][0]["referenced_artifacts"][0]["sha256"]
    assert report["dataset"]["manifest_historical_run_hash_recorded"] is False
    assert report["producer_bindings"]["source_results_index"]["sha256"]


def test_unverified_mode_never_claims_real_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    with pytest.raises(ValueError, match="explicit simulated fixture classification"):
        _build(root, run, preflight, monkeypatch, mode="unverified")

    approval_path = root / "research_artifacts/validation_approvals/synthetic_recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["reviewer"] = "UNVERIFIED_USER_SUPPLIED"
    _write_json(approval_path, approval)
    _update_summary_and_manifest(
        run,
        lambda document: document.get("mechanics_validation_gate", {}).__setitem__(
            "reviewer", "UNVERIFIED_USER_SUPPLIED"
        ),
    )
    report = _build(root, run, preflight, monkeypatch, mode="unverified")

    assert report["assurance"]["data_origin_verified"] is False
    assert report["input_classification"]["classification"] == "unverified"
    assert all("real-data diagnostic evidence" not in label.lower() for label in report["labels"])
    with pytest.raises(ValueError, match="synthetic mode requires"):
        _build(root, run, preflight, monkeypatch, mode="synthetic")
    with pytest.raises(ValueError, match="positive real-origin classification is unsupported"):
        _build(root, run, preflight, monkeypatch, mode="real")


@pytest.mark.parametrize("field", ["run_uid", "test_run_id", "attempt_id", "attempt_kind", "attempt_provenance"])
def test_rejects_empty_required_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    root, run, preflight = _project(tmp_path)
    _update_summary_and_manifest(run, lambda document: document.__setitem__(field, ""))
    with pytest.raises(ValueError, match=field):
        _build(root, run, preflight, monkeypatch)


def test_rejects_effective_strategy_drift_even_when_hashes_are_relabelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    effective_path = run / "effective_config.yaml"
    effective = yaml.safe_load(effective_path.read_text(encoding="utf-8"))
    effective["strategy"]["entry"]["module"] = "opening_range_breakout"
    _write_yaml(effective_path, effective)
    changed_hash = file_sha256(effective_path)
    _update_summary_and_manifest(run, lambda document: document.__setitem__("config_hash", changed_hash))

    with pytest.raises(ValueError, match="effective config canonicalization"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_invented_stage_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    stage_path = run / first / "stage_result.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["status"] = "invented"
    _write_json(stage_path, stage)

    def update(document):
        if "stages" in document:
            document["stages"][0] = stage

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match="status must be one of"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_stage_status_passed_disagreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    stage_path = run / first / "stage_result.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["passed"] = True
    _write_json(stage_path, stage)

    def update(document):
        if "stages" in document:
            document["stages"][0] = stage

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match="status and passed flag are inconsistent"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_integer_for_boolean_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("skip_validation", 0)
        if "stages" in document
        else None,
    )
    with pytest.raises(ValueError, match="skip_validation must be boolean"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_missing_referenced_stage_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    (run / first / "summary.json").unlink()
    with pytest.raises(ValueError, match="required artifact is not a file"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_approval_identity_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/synthetic_recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["reviewer"] = "different-reviewer"
    _write_json(approval_path, approval)
    with pytest.raises(ValueError, match="mechanics approval reviewer"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_dataset_without_pass_quality(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/datasets/synthetic_fixture_es/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["quality_verdict"] = "NEEDS MANUAL REVIEW"
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="dataset quality verdict"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_published_source_hash_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/campaigns/active/synthetic_recipe_demo/authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"]["variants/v01/config.yaml"] = "0" * 64
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="published source config hash"):
        _build(root, run, preflight, monkeypatch)


def test_formatting_preserves_compiled_object_hash_but_breaks_raw_run_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    source_path = root / "research/campaigns/active/synthetic_recipe_demo/variants/v01/config.yaml"
    manifest_path = source_path.parents[2] / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    prior_file_hash = file_sha256(source_path)

    source_path.write_text(yaml.safe_dump(source, sort_keys=True), encoding="utf-8")

    assert file_sha256(source_path) != prior_file_hash
    assert mvp._compiled_object_sha256(source) == manifest["compiled_document_sha256"][
        "variants/v01/config.yaml"
    ]
    with pytest.raises(ValueError, match="authored source config hash"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_preflight_receipt_that_claims_tests_ran(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    preflight["tests_ran"] = True
    _write_json(root / "pre-run-preflight.json", preflight)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("submission_preflight", preflight),
    )
    with pytest.raises(ValueError, match="pre-run preflight tests_ran"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_output_dir_and_run_uid_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)

    def change_output(document):
        if "stages" in document:
            document["output_dir"] = "research/evidence/runs/other"

    _update_summary_and_manifest(run, change_output)
    with pytest.raises(ValueError, match="summary output_dir"):
        _build(root, run, preflight, monkeypatch)

    root, run, preflight = _project(tmp_path / "second")
    (run / "run_uid.txt").write_text("different", encoding="utf-8")
    with pytest.raises(ValueError, match="run UID marker"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("halted", True, "run halted flag"),
        ("engine_contract_version", "contradictory", "summary engine contract"),
    ],
)
def test_rejects_producer_impossible_run_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    _update_summary_and_manifest(run, lambda document: document.__setitem__(field, value))
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_manifest_data_contract_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_source"] = "parquet"
    manifest["raw_csv"] = None
    manifest["raw_parquet"] = "different.parquet"
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest data_source"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("criteria_pass", "criteria aggregate"),
        ("verdict", "generic_objective_verdict"),
        ("metric", "criterion 0 metric"),
    ],
)
def test_rejects_producer_impossible_stage_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, message: str
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    result_path = run / stage_name / "stage_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if mutation == "criteria_pass":
        result["status"] = "passed"
        result["passed"] = True
    elif mutation == "verdict":
        result["generic_objective_verdict"] = "FAIL"
        result["generic_objective_passed"] = False
    else:
        result["criteria"][0]["metric"] = "invented.metric"
    _write_json(result_path, result)

    def update(document):
        if "stages" in document:
            document["stages"][0] = result

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_incomplete_authoring_document_topology(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/campaigns/active/synthetic_recipe_demo/authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"].pop("campaign.yaml")
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="compiled document topology"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_hash_valid_semantically_contradictory_authoring_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/synthetic_recipe_demo"
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("campaign.yaml", "strategy_spec.yaml"):
        path = campaign_root / name
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        document["certified_recipe"] = "opening_range_breakout"
        _write_yaml(path, document)
        manifest["compiled_document_sha256"][name] = mvp._compiled_object_sha256(document)
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="campaign certified recipe"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_hash_valid_forged_mechanic_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/synthetic_recipe_demo"
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    forged = "0" * 64
    campaign_path = campaign_root / "campaign.yaml"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    campaign["variant_distinctions"]["v01"]["mechanic_signature"] = forged
    _write_yaml(campaign_path, campaign)
    spec_path = campaign_root / "strategy_spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    spec["variants"][0]["mechanic_signature"] = forged
    _write_yaml(spec_path, spec)
    manifest["variant_mechanic_signatures"]["v01"] = forged
    manifest["compiled_document_sha256"]["campaign.yaml"] = mvp._compiled_object_sha256(campaign)
    manifest["compiled_document_sha256"]["strategy_spec.yaml"] = mvp._compiled_object_sha256(spec)
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="strategy spec mechanic signature"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("symbol", "NQ", "dataset manifest symbol"),
        ("timeframe", "5m", "dataset manifest timeframe"),
        ("timezone", "UTC", "dataset manifest timezone"),
        ("timestamp_semantics", "bar_close", "dataset manifest timestamp_semantics"),
        ("row_count", 999, "strategy spec dataset"),
    ],
)
def test_rejects_dataset_execution_metadata_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/datasets/synthetic_fixture_es/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("config_hash", "0" * 64, "mechanics gate config hash"),
        ("config_path", "research/campaigns/active/different/config.yaml", "mechanics gate config path"),
        ("verdict", "FAIL", "mechanics gate verdict"),
        ("lane", "event_replay", "mechanics gate lane"),
    ],
)
def test_rejects_recorded_mechanics_gate_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)

    def update(document):
        document["mechanics_validation_gate"][field] = value

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "unsupported/v9", "approval contract failed"),
        ("review_scope", "profitability", "review scope"),
        ("profitability_approval", True, "profitability approval"),
        ("sampling_categories", {}, "approval contract failed"),
    ],
)
def test_rejects_malformed_mechanics_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/synthetic_recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval[field] = value
    _write_json(approval_path, approval)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("configs", "data_sources", "message"),
    [
        (["research/campaigns/active/different/variants/v99/config.yaml"], 1, "config identity"),
        ([], 1, "config identity"),
        (
            [
                "research/campaigns/active/synthetic_recipe_demo/variants/v01/config.yaml",
                "research/campaigns/active/different/variants/v99/config.yaml",
            ],
            1,
            "config identity",
        ),
        (["research/campaigns/active/synthetic_recipe_demo/variants/v01/config.yaml"], 0, "data source count"),
    ],
)
def test_rejects_preflight_input_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configs: list[str],
    data_sources: int,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    preflight["configs_checked"] = configs
    preflight["data_sources_checked"] = data_sources
    _write_json(root / "pre-run-preflight.json", preflight)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("submission_preflight", preflight),
    )
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_preflight_accepts_equivalent_absolute_config_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    source_path = root / "research/campaigns/active/synthetic_recipe_demo/variants/v01/config.yaml"
    preflight["configs_checked"] = [str(source_path)]
    _write_json(root / "pre-run-preflight.json", preflight)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("submission_preflight", preflight),
    )
    report = _build(root, run, preflight, monkeypatch)
    assert report["preflight"]["recorded"]["configs_checked"] == [str(source_path)]


def test_cli_uses_exclusive_create_and_refuses_inside_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, _preflight = _project(tmp_path)
    document = {"overall_verdict": "NEEDS MANUAL REVIEW"}
    monkeypatch.setattr(mvp, "build_diagnostic_index", lambda **_kwargs: document)
    output = root / "diagnostics/index.json"
    arguments = [
        "run_mvp_diagnostic",
        "--project-root",
        str(root),
        "--run-dir",
        str(run),
        "--preflight-receipt",
        str(root / "pre-run-preflight.json"),
        "--output",
        str(output),
        "--mode",
        "synthetic",
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    mvp.main()
    with pytest.raises(FileExistsError):
        mvp.main()

    arguments[arguments.index(str(output))] = str(run / "inside.json")
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(ValueError, match="outside the run directory"):
        mvp.main()
