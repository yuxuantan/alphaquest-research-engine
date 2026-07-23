import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from alphaquest.research.registry import _campaign_lifecycle, build_registry, generate_views, registry_summary
from alphaquest.studio.results import ResultBundleBuilder


def _write_fixture(root: Path, *, passed: bool = False) -> None:
    campaign = root / "campaigns" / "demo"
    variant = campaign / "variants" / "base"
    rescue = campaign / "rescue_attempts" / "rescue_01" / "base"
    run = root / "backtest-campaigns" / "demo" / "base" / "ES" / "run1"
    variant.mkdir(parents=True)
    rescue.mkdir(parents=True)
    run.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "campaign_id: demo\ntitle: Demo\nedge_family: fixture\n", encoding="utf-8"
    )
    config = "campaign_id: demo\nvariant_id: base\nsymbol: ES\ntimeframe: 1m\ndataset_id: fixture\n"
    (variant / "config.yaml").write_text(config, encoding="utf-8")
    (rescue / "config.yaml").write_text(config + "test_run_id: rescue1\n", encoding="utf-8")
    summary = {
        "campaign_id": "demo",
        "variant_id": "base",
        "test_run_id": "run1",
        "symbol": "ES",
        "dataset_id": "fixture",
        "timeframe": "1m",
        "passed": passed,
        "halted": not passed,
        "updated_at": "2026-07-11T00:00:00Z",
        "source_config_path": "campaigns/demo/variants/base/config.yaml",
        "stages": [{"stage": "limited_core_grid_test", "status": "passed" if passed else "failed", "passed": passed}],
    }
    (run / "campaign_test_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _write_complete_studio_manifest(
    root: Path,
    reporting: Path,
    *,
    verdict: str,
) -> None:
    job_id = "registry-result-job"
    journal = root / ".alphaquest-studio/recovery/registry-result-job.json"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-recovery-journal/v1",
                "job_id": job_id,
                "phase": "FINALIZED",
                "terminal": True,
                "automatic_replay_permitted": False,
                "events": [{"phase": "FINALIZED"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary = reporting.parent / "campaign_test_summary.json"
    reporting_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in reporting.iterdir()
        if path.is_file() and path.name != "finalization_manifest.json"
    }
    (reporting / "finalization_manifest.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-finalization/v1",
                "job_id": job_id,
                "campaign_id": "demo",
                "variant_id": "base",
                "run_id": "run1",
                "research_verdict": verdict,
                "automatic_replay_permitted": False,
                "result_bundle": "result_bundle_v2.json",
                "evidence_issues": [],
                "evidence_artifact_sha256": {
                    summary.name: hashlib.sha256(summary.read_bytes()).hexdigest()
                },
                "reporting_artifact_sha256": reporting_hashes,
                "ledger_recorded": True,
                "registry_published": True,
                "registry_counts": {},
                "recovery_journal": str(journal.resolve()),
                "terminal_recovery_phase": "FINALIZED",
                "terminal_recovery_journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest(),
                "transaction_complete": True,
            }
        ),
        encoding="utf-8",
    )


def test_registry_records_source_lineage_runs_and_stages(tmp_path):
    _write_fixture(tmp_path)
    database = tmp_path / "catalogs" / "registry.sqlite"

    counts = build_registry(project_root=tmp_path, database_path=database)

    assert counts == {
        "campaigns": 1,
        "variants": 1,
        "attempts": 2,
        "runs": 1,
        "archived_unreviewed_runs": 1,
        "archived_unreviewed_variants": 1,
        "research_artifacts": 1,
    }
    summary = registry_summary(database)
    assert summary["campaign_lifecycle"] == {"review_queue": 1}
    assert summary["run_verdicts"] == {"FAIL": 1}
    with sqlite3.connect(database) as connection:
        attempts = connection.execute(
            "SELECT attempt_id, provenance, run_uid FROM attempts ORDER BY provenance"
        ).fetchall()
        assert attempts[0][0] == "legacy_" + connection.execute("SELECT REPLACE(run_uid, '-', '') FROM runs").fetchone()[0]
        assert attempts[0][1] == "inferred_legacy"
        assert attempts[0][2]
        assert attempts[1][0] == "rescue_01"
        assert attempts[1][1] == "legacy_authored_definition"
        assert connection.execute("SELECT COUNT(DISTINCT attempt_id) FROM runs").fetchone()[0] == 1
        assert connection.execute("SELECT archived FROM runs").fetchone()[0] == 1
        assert connection.execute("SELECT archived FROM variants").fetchone()[0] == 1
        assert connection.execute("SELECT stage_name FROM stages").fetchone()[0] == "limited_core_grid_test"
        assert connection.execute("SELECT COUNT(*) FROM artifact_objects").fetchone()[0] >= 1
        assert connection.execute("SELECT MIN(LENGTH(sha256)) FROM artifacts").fetchone()[0] == 64


def test_registry_derives_one_unique_inferred_legacy_attempt_per_run(tmp_path):
    _write_fixture(tmp_path)
    first = tmp_path / "backtest-campaigns/demo/base/ES/run1/campaign_test_summary.json"
    second = tmp_path / "backtest-campaigns/demo/base/ES/run2/campaign_test_summary.json"
    second.parent.mkdir(parents=True)
    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["test_run_id"] = "run2"
    second.write_text(json.dumps(payload), encoding="utf-8")
    database = tmp_path / "catalogs/registry.sqlite"

    build_registry(project_root=tmp_path, database_path=database)

    summary = registry_summary(database)
    assert summary["run_verdicts"] == {"FAIL": 2}
    assert summary["attempt_provenance"]["inferred_legacy"] == 2
    assert summary["one_run_attempt_violations"] == 0
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT attempt_id, attempt_provenance FROM runs ORDER BY test_run_id"
        ).fetchall()
    assert len({row[0] for row in rows}) == 2
    assert {row[1] for row in rows} == {"inferred_legacy"}


def test_registry_keeps_ambiguous_legacy_run_needs_manual_review(tmp_path):
    _write_fixture(tmp_path)
    path = tmp_path / "backtest-campaigns/demo/base/ES/run1/campaign_test_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("passed")
    payload.pop("halted")
    payload["stages"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")
    database = tmp_path / "catalogs/registry.sqlite"

    build_registry(project_root=tmp_path, database_path=database)

    summary = registry_summary(database)
    assert summary["run_verdicts"] == {"NEEDS MANUAL REVIEW": 1}
    assert summary["ambiguous_attempts"] == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT lineage_status FROM attempts WHERE run_uid IS NOT NULL").fetchone()[0] == (
            "NEEDS MANUAL REVIEW"
        )


def test_registry_honors_explicit_diagnostic_needs_manual_review(tmp_path):
    _write_fixture(tmp_path)
    path = tmp_path / "backtest-campaigns/demo/base/ES/run1/campaign_test_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["research_verdict"] = "NEEDS MANUAL REVIEW"
    payload["diagnostic_only"] = True
    payload["halted"] = False
    payload["stages"] = [
        {"stage": "limited_core_grid_test", "status": "passed", "passed": True}
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    database = tmp_path / "catalogs/registry.sqlite"

    build_registry(project_root=tmp_path, database_path=database)

    summary = registry_summary(database)
    assert summary["run_verdicts"] == {"NEEDS MANUAL REVIEW": 1}
    assert summary["campaign_lifecycle"] == {"review_queue": 1}


def test_registry_prefers_complete_result_bundle_over_runner_pass(tmp_path):
    _write_fixture(tmp_path, passed=True)
    run = tmp_path / "backtest-campaigns/demo/base/ES/run1"
    reporting = run / "reporting_v2"
    ResultBundleBuilder().build_and_write(
        pd.DataFrame(columns=["net_pnl"]),
        reporting,
        campaign_id="demo",
        variant_id="base",
        run_id="run1",
        verdict="NEEDS MANUAL REVIEW",
    )
    _write_complete_studio_manifest(
        tmp_path,
        reporting,
        verdict="NEEDS MANUAL REVIEW",
    )

    build_registry(
        project_root=tmp_path,
        database_path=tmp_path / "catalogs/registry.sqlite",
    )

    summary = registry_summary(tmp_path / "catalogs/registry.sqlite")
    assert summary["run_verdicts"] == {"NEEDS MANUAL REVIEW": 1}
    assert summary["campaign_lifecycle"] == {"review_queue": 1}


def test_registry_marks_incomplete_studio_finalization_nmr_even_with_pass_bundle(tmp_path):
    _write_fixture(tmp_path, passed=True)
    run = tmp_path / "backtest-campaigns/demo/base/ES/run1"
    reporting = run / "reporting_v2"
    ResultBundleBuilder().build_and_write(
        pd.DataFrame(columns=["net_pnl"]),
        reporting,
        campaign_id="demo",
        variant_id="base",
        run_id="run1",
        verdict="PASS",
    )
    (reporting / "finalization_manifest.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-finalization/v1",
                "campaign_id": "demo",
                "variant_id": "base",
                "research_verdict": "PASS",
                "transaction_complete": False,
            }
        ),
        encoding="utf-8",
    )

    build_registry(
        project_root=tmp_path,
        database_path=tmp_path / "catalogs/registry.sqlite",
    )

    summary = registry_summary(tmp_path / "catalogs/registry.sqlite")
    assert summary["run_verdicts"] == {"NEEDS MANUAL REVIEW": 1}
    assert summary["campaign_lifecycle"] == {"review_queue": 1}


def test_registry_incomplete_attempt_marker_overrides_complete_pass(tmp_path):
    _write_fixture(tmp_path, passed=True)
    run = tmp_path / "backtest-campaigns/demo/base/ES/run1"
    (run / "studio_incomplete_attempt.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-incomplete-attempt/v1",
                "research_verdict": "NEEDS MANUAL REVIEW",
                "attempt_reserved": True,
                "automatic_replay_permitted": False,
            }
        ),
        encoding="utf-8",
    )

    build_registry(
        project_root=tmp_path,
        database_path=tmp_path / "catalogs/registry.sqlite",
    )

    summary = registry_summary(tmp_path / "catalogs/registry.sqlite")
    assert summary["run_verdicts"] == {"NEEDS MANUAL REVIEW": 1}


def test_registry_rejects_second_run_for_governance_v2_authored_attempt(tmp_path):
    campaign = tmp_path / "campaigns/demo"
    config = campaign / "variants/base/config.yaml"
    config.parent.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "campaign_id: demo\ngovernance_contract_version: 2\n",
        encoding="utf-8",
    )
    config.write_text(
        "campaign_id: demo\nvariant_id: base\nattempt_id: original\nattempt_kind: original\n"
        "attempt_provenance: authored\nsymbol: ES\ntimeframe: 1m\ndataset_id: fixture\n",
        encoding="utf-8",
    )
    for run_id in ("run1", "run2"):
        run = tmp_path / f"backtest-campaigns/demo/base/ES/{run_id}"
        run.mkdir(parents=True)
        (run / "campaign_test_summary.json").write_text(
            json.dumps(
                {
                    "campaign_id": "demo",
                    "variant_id": "base",
                    "attempt_id": "original",
                    "attempt_kind": "original",
                    "attempt_provenance": "authored",
                    "test_run_id": run_id,
                    "symbol": "ES",
                    "dataset_id": "fixture",
                    "timeframe": "1m",
                    "passed": False,
                    "halted": True,
                    "source_config_path": "campaigns/demo/variants/base/config.yaml",
                    "stages": [],
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(RuntimeError, match="one-run-per-attempt violation"):
        build_registry(project_root=tmp_path, database_path=tmp_path / "catalogs/registry.sqlite")


def test_registry_pass_waits_for_independent_candidate_review(tmp_path):
    _write_fixture(tmp_path, passed=True)
    database = tmp_path / "catalogs" / "registry.sqlite"
    build_registry(project_root=tmp_path, database_path=database)

    summary = registry_summary(database)

    assert summary["campaign_lifecycle"] == {"review_queue": 1}


def test_registry_promotes_only_after_valid_candidate_review_signal():
    lifecycle, reason = _campaign_lifecycle(
        None,
        None,
        [{"verdict": "PASS"}],
        candidate_reviewed=True,
    )

    assert lifecycle == "candidate"
    assert "independent candidate review" in reason


def test_generated_views_are_replaceable_and_link_to_definitions(tmp_path):
    _write_fixture(tmp_path, passed=True)
    database = tmp_path / "catalogs" / "registry.sqlite"
    build_registry(project_root=tmp_path, database_path=database)

    counts = generate_views(project_root=tmp_path, database_path=database)
    counts_again = generate_views(project_root=tmp_path, database_path=database)

    assert counts == counts_again
    assert counts["review_queue"] == 1
    assert (tmp_path / "views" / "review_queue" / "definitions" / "demo").resolve() == tmp_path / "campaigns" / "demo"
    assert (tmp_path / "views" / "recent_failures" / "runs.csv").is_file()
    readme = (tmp_path / "views" / "README.md").read_text(encoding="utf-8")
    assert "Manual review" in readme
    assert "review_runs/" not in readme
    assert (tmp_path / "views" / "by_symbol" / "OTHER.csv").is_file()


def test_registry_logically_partitions_durable_artifacts_without_moving_them(tmp_path):
    _write_fixture(tmp_path)
    artifacts = tmp_path / "research_artifacts"
    artifacts.mkdir()
    source = artifacts / "demo_density_audit_20260711.md"
    source.write_text("audit\n", encoding="utf-8")
    approval = artifacts / "validation_approvals" / "demo" / "v01" / "approval.json"
    approval.parent.mkdir(parents=True)
    approval.write_text("{}\n", encoding="utf-8")
    database = tmp_path / "catalogs" / "registry.sqlite"

    build_registry(project_root=tmp_path, database_path=database)
    generate_views(project_root=tmp_path, database_path=database)

    assert source.is_file()
    assert approval.is_file()
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM research_artifacts WHERE path = ?",
            ("research_artifacts/validation_approvals/demo/v01/approval.json",),
        ).fetchone()[0] == 1
    assert "demo_density" in (tmp_path / "views" / "artifacts" / "audits_density.csv").read_text(encoding="utf-8")
