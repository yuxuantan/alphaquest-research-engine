from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
import yaml

import alphaquest.run_mvp_diagnostic as mvp
from alphaquest.research.campaign_stages import PRE_ACCEPTANCE_STAGE_ORDER, canonicalize_campaign_config
from alphaquest.utils.hashing import file_sha256


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
        "coverage_start": "2026-01-05T14:30:00+00:00",
        "coverage_end": "2026-01-05T14:30:00+00:00",
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
            "canonical_sha256": canonical_hash,
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
        },
    )
    campaign = {
        "campaign_id": source["campaign_id"],
        "authoring_lane": "certified_recipe",
        "certified_recipe": "calendar_session_bias",
    }
    strategy_spec = {"schema": "alphaquest.strategy-spec/v1", **campaign}
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
            "authoring_lane": "certified_recipe",
            "certified_recipe": "calendar_session_bias",
            "dataset_id": dataset_id,
            "compiled_document_sha256": compiled,
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
                "label": stage,
                "status": "failed",
                "passed": False,
                "criteria": [],
                "artifacts": [str(output.relative_to(root))],
                "scientific_validity_verdict": "FAIL",
                "scientific_validity_passed": False,
                "generic_objective_verdict": "FAIL",
                "generic_objective_passed": False,
            }
        else:
            result = {
                "stage": stage,
                "label": stage,
                "status": "error",
                "passed": False,
                "error": "upstream fixture evidence unavailable",
                "criteria": [],
                "scientific_validity_verdict": "NEEDS MANUAL REVIEW",
                "scientific_validity_passed": False,
                "generic_objective_verdict": "NEEDS MANUAL REVIEW",
                "generic_objective_passed": False,
            }
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
    summary = {
        **identity,
        "config_hash": file_sha256(run / "effective_config.yaml"),
        "source_config_hash": source_hash,
        "config_path": str((run / "effective_config.yaml").relative_to(root)),
        "effective_config_path": str((run / "effective_config.yaml").relative_to(root)),
        "source_config_path": str(source_path),
        "source_config_snapshot_path": str((run / "source_config.yaml").relative_to(root)),
        "output_dir": str(run.relative_to(root)),
        "created_at": "2026-09-27T00:00:00",
        "updated_at": "2026-09-27T00:00:01",
        "passed": False,
        "halted": False,
        "stages": stages,
        "research_policy": effective["research_policy"],
        "engine_contract_version": "test",
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
    }
    manifest = {
        **identity,
        "config_source": str(source_path),
        "effective_config": str((run / "effective_config.yaml").relative_to(root)),
        "source_config_snapshot": str((run / "source_config.yaml").relative_to(root)),
        "config_hash": summary["config_hash"],
        "source_config_hash": source_hash,
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


def test_unverified_mode_never_claims_real_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    report = _build(root, run, preflight, monkeypatch, mode="unverified")

    assert report["assurance"]["data_origin_verified"] is False
    assert all("real-data diagnostic evidence" not in label.lower() for label in report["labels"])
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
