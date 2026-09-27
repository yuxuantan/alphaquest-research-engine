from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from alphaquest.research.campaign_stages import PRE_ACCEPTANCE_STAGE_ORDER
from alphaquest.run_mvp_diagnostic import build_diagnostic_index
from alphaquest.utils.hashing import file_sha256


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _fixture(root: Path, *, synthetic: bool = True) -> Path:
    (root / "config").mkdir(parents=True)
    (root / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "dataset_root": "research/datasets",
                "evidence_roots": ["research/evidence/runs"],
            }
        ),
        encoding="utf-8",
    )
    dataset_id = "synthetic_fixture_es" if synthetic else "governed_es"
    canonical = root / f"research/datasets/{dataset_id}/bars.csv"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("timestamp,open,high,low,close,volume\n2026-01-01T14:30:00Z,1,1,1,1,1\n", encoding="utf-8")
    canonical_hash = file_sha256(canonical)
    _write_json(
        canonical.parent / "dataset_manifest.json",
        {
            "schema": "alphaquest.dataset-manifest/v1",
            "dataset_id": dataset_id,
            "source": "csv",
            "path": str(canonical.relative_to(root)),
            "canonical_sha256": canonical_hash,
        },
    )

    evidence_dir = root / "research/evidence/mechanics/validation_runs/core"
    evidence_dir.mkdir(parents=True)
    _write_json(evidence_dir / "metadata.json", {"schema_version": "1.6"})
    approval_path = root / "research_artifacts/validation_approvals/demo/v01/approval.json"
    source_path = root / "research/campaigns/active/demo/variants/v01/config.yaml"
    source_config = {
        "campaign_id": "synthetic_tutorial_demo" if synthetic else "real_demo",
        "variant_id": "v01",
        "symbol": "ES",
        "research_metadata": {
            "validation_gate": {
                "required": True,
                "evidence_dir": str(evidence_dir.relative_to(root)),
                "approval_path": str(approval_path.relative_to(root)),
            }
        },
        "data": {
            "dataset_id": dataset_id,
            "symbol": "ES",
            "source": "csv",
            "raw_csv": str(canonical.relative_to(root)),
            "canonical_sha256": canonical_hash,
        },
    }
    source_path.parent.mkdir(parents=True)
    source_path.write_text(yaml.safe_dump(source_config, sort_keys=False), encoding="utf-8")
    source_hash = file_sha256(source_path)
    reviewer = "SIMULATED_MVP_FIXTURE_ONLY" if synthetic else "owner-reviewer"
    _write_json(
        approval_path,
        {
            "schema": "alphaquest.validation-approval/v1",
            "status": "approved_for_testing",
            "reviewer": reviewer,
            "config_hash": source_hash,
            "input_data_hash": canonical_hash,
        },
    )

    run = root / "research/evidence/runs/demo/v01/ES/run1"
    run.mkdir(parents=True)
    snapshot = run / "source_config.yaml"
    snapshot.write_bytes(source_path.read_bytes())
    effective = run / "effective_config.yaml"
    effective.write_text(yaml.safe_dump({**source_config, "campaign_tests": {"stage_order": PRE_ACCEPTANCE_STAGE_ORDER}}), encoding="utf-8")
    gate = {
        "required": True,
        "status": "APPROVED_FOR_TESTING",
        "verdict": "PASS",
        "errors": [],
        "warnings": [],
        "evidence_dir": str(evidence_dir),
        "approval_path": str(approval_path),
        "config_hash": source_hash,
        "input_data_hash": canonical_hash,
        "approval_status": "approved_for_testing",
        "reviewer": reviewer,
    }
    stages = []
    for stage in PRE_ACCEPTANCE_STAGE_ORDER:
        item = {
            "stage": stage,
            "label": stage,
            "status": "error",
            "passed": False,
            "error": "fixture evidence retained",
            "criteria": [],
            "scientific_validity_verdict": "NEEDS MANUAL REVIEW",
            "scientific_validity_passed": False,
            "generic_objective_verdict": "NEEDS MANUAL REVIEW",
            "generic_objective_passed": False,
        }
        stages.append(item)
        _write_json(run / stage / "stage_result.json", item)
    identity = {
        "run_uid": "run-uid-1",
        "campaign_id": source_config["campaign_id"],
        "variant_id": "v01",
        "test_run_id": "run1",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "parent_attempt_id": None,
        "symbol": "ES",
        "dataset_id": dataset_id,
    }
    preflight = {"passed": True, "failures": [], "warnings": []}
    summary = {
        **identity,
        "diagnostic_only": True,
        "diagnostic_reasons": ["mandatory acceptance_oos_test was omitted"],
        "skip_validation": False,
        "fast_runtime_defaults": False,
        "research_verdict": "NEEDS MANUAL REVIEW",
        "passed": False,
        "submission_preflight": preflight,
        "mechanics_validation_gate": gate,
        "config_hash": file_sha256(effective),
        "source_config_hash": source_hash,
        "source_config_path": str(source_path),
        "config_path": str(effective.relative_to(root)),
        "effective_config_path": str(effective.relative_to(root)),
        "source_config_snapshot_path": str(snapshot.relative_to(root)),
        "stages": stages,
    }
    manifest = {
        **identity,
        "diagnostic_only": True,
        "diagnostic_reasons": ["mandatory acceptance_oos_test was omitted"],
        "research_verdict": "NEEDS MANUAL REVIEW",
        "submission_preflight": preflight,
        "mechanics_validation_gate": gate,
        "config_hash": file_sha256(effective),
        "source_config_hash": source_hash,
        "config_source": str(source_path),
        "effective_config": str(effective.relative_to(root)),
        "source_config_snapshot": str(snapshot.relative_to(root)),
        "stage_order": PRE_ACCEPTANCE_STAGE_ORDER,
    }
    _write_json(run / "campaign_test_summary.json", summary)
    _write_json(run / "variant_test_summary.json", summary)
    _write_json(run / "run_manifest.json", manifest)
    return run


def test_builds_synthetic_report_with_fixed_nmr_and_bound_artifacts(tmp_path: Path) -> None:
    run = _fixture(tmp_path)

    report = build_diagnostic_index(project_root=tmp_path, run_dir=run, mode="synthetic")

    assert report["overall_verdict"] == "NEEDS MANUAL REVIEW"
    assert report["passed"] is False
    assert report["assurance"] == {
        "source_review_verified": False,
        "implementation_admission_verified": False,
        "canonical_result_bundle_finalized": False,
        "scientific_pass_or_fail_claimed": False,
        "candidate_promoted": False,
        "trading_ready": False,
        "p3_qualified": False,
    }
    assert [item["summary"]["stage"] for item in report["stages"]] == PRE_ACCEPTANCE_STAGE_ORDER
    assert all(item["stage_result"] == item["summary"] for item in report["stages"])
    assert report["dataset"]["canonical_file"]["sha256"]
    assert report["mechanics"]["approval"]["sha256"]
    assert any("simulated" in label.lower() for label in report["labels"])


def test_rejects_stage_result_drift(tmp_path: Path) -> None:
    run = _fixture(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    result_path = run / first / "stage_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["error"] = "changed after summary"
    _write_json(result_path, result)

    with pytest.raises(ValueError, match="stage result mismatch"):
        build_diagnostic_index(project_root=tmp_path, run_dir=run, mode="synthetic")


def test_real_mode_rejects_evident_fixture_markers(tmp_path: Path) -> None:
    run = _fixture(tmp_path, synthetic=True)
    with pytest.raises(ValueError, match="real mode rejects"):
        build_diagnostic_index(project_root=tmp_path, run_dir=run, mode="real")


def test_real_mode_remains_nmr_without_source_or_admission_assurance(tmp_path: Path) -> None:
    run = _fixture(tmp_path, synthetic=False)

    report = build_diagnostic_index(project_root=tmp_path, run_dir=run, mode="real")

    assert report["overall_verdict"] == "NEEDS MANUAL REVIEW"
    assert report["assurance"]["source_review_verified"] is False
    assert report["assurance"]["implementation_admission_verified"] is False
    assert report["mechanics"]["gate_currently_revalidated"] is False


def test_cli_exclusive_create_and_refuses_output_inside_run(tmp_path: Path) -> None:
    run = _fixture(tmp_path)
    outside = tmp_path / "diagnostics/index.json"
    command = [
        sys.executable,
        "-m",
        "alphaquest.run_mvp_diagnostic",
        "--project-root",
        str(tmp_path),
        "--run-dir",
        str(run),
        "--output",
        str(outside),
        "--mode",
        "synthetic",
    ]
    first = subprocess.run(command, text=True, capture_output=True)
    assert first.returncode == 0, first.stderr
    assert outside.is_file()
    second = subprocess.run(command, text=True, capture_output=True)
    assert second.returncode != 0
    assert "FileExistsError" in second.stderr

    inside = run / "diagnostic-index.json"
    blocked = subprocess.run([*command[:-4], "--output", str(inside), "--mode", "synthetic"], text=True, capture_output=True)
    assert blocked.returncode != 0
    assert "outside the run directory" in blocked.stderr
    assert not inside.exists()
