import json
import os

import pandas as pd
import yaml

from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
from alphaquest.tutorial import TUTORIAL_RANDOM_SEED, run_tutorial


def test_tutorial_generates_isolated_source_without_execution(tmp_path):
    output = tmp_path / "tutorial"

    result = run_tutorial(output_root=output, execute=False)

    assert result["status"] == "PASS"
    assert result["operational_status"] == "PASS"
    assert result["research_verdict"] == "FAIL"
    assert result["synthetic"] is True
    assert result["promotion_eligible"] is False
    assert result["production_ledger_update"] is False
    assert len(result["configs"]) == 5
    assert sum(step["minutes"] for step in result["walkthrough"]) == 15
    assert all(row["limited_core_test"] == "NOT_RUN" for row in result["stage_matrix"])
    manifest = json.loads((output / "tutorial_manifest.json").read_text(encoding="utf-8"))
    assert manifest["executed"] is False
    assert manifest["research_verdict"] == "FAIL"
    services = manifest["governed_services"]
    assert services["dataset_import"]["service"] == "DatasetImporter"
    assert services["publication"]["preflight_verdict"] == "PASS"
    assert services["publication"]["ledger_rows_appended"] == 6
    assert (output / "research/datasets/synthetic_tutorial_es_1m/dataset_manifest.json").is_file()
    assert (output / "research/campaigns/active/tutorial_calendar_bias/authoring_manifest.json").is_file()
    assert (output / "research/campaigns/active/tutorial_calendar_bias/strategy_spec.yaml").is_file()
    assert (output / "research_ledger.csv").is_file()
    assert (output / "stage_matrix.csv").is_file()
    assert not (tmp_path / "research_ledger.csv").exists()
    assert not (tmp_path / "research/campaigns/active").exists()


def test_tutorial_executes_all_variants_and_writes_mixed_stage_matrix(tmp_path):
    output = tmp_path / "tutorial"

    result = run_tutorial(output_root=output, execute=True)

    assert result["status"] == "PASS"
    assert result["operational_status"] == "PASS"
    assert result["research_verdict"] == "FAIL"
    assert result["lesson_demonstrated"] is True
    assert len(result["variant_runs"]) == 5
    assert result["governed_services"]["mechanics_approval"]["approved_variants"] == 5
    assert result["governed_services"]["mechanics_approval"]["profitability_approval"] is False
    assert result["governed_services"]["results"]["bundle_count"] == 5
    assert result["total_trades"] > 0
    assert result["apex_rule_violations"] == 0
    for index in range(1, 6):
        run_dir = output / "runs" / f"v{index:02d}"
        assert (run_dir / "trade_log.csv").is_file()
        assert (run_dir / "daily_results.csv").is_file()
        assert (run_dir / "result_bundle_v2.json").is_file()
        assert (run_dir / "yearly_breakdown.csv").is_file()
        assert (run_dir / "equity_curve.csv").is_file()

    matrix = pd.read_csv(output / "stage_matrix.csv", keep_default_na=False)
    assert matrix["variant_id"].tolist() == ["v01", "v02", "v03", "v04", "v05"]
    assert set(matrix["mechanics_approval"]) == {"PASS"}
    assert set(matrix["limited_core_test"]) == {"PASS", "FAIL"}
    assert set(matrix["randomized_entry_benchmark"]) == {"FAIL", "NOT_RUN"}
    assert set(matrix["research_verdict"]) == {"FAIL"}
    assert matrix.loc[matrix["variant_id"] == "v01", "first_failed_or_unresolved_gate"].item() == (
        "randomized_entry_benchmark"
    )


def test_profitable_lead_variant_fails_seeded_randomized_entry_benchmark(tmp_path):
    result = run_tutorial(output_root=tmp_path / "tutorial", execute=True)

    benchmark = result["randomized_entry_benchmark"]
    summary = benchmark["summary"]
    assert benchmark["seed"] == TUTORIAL_RANDOM_SEED
    assert summary["core_metrics"]["net_profit"] > 0
    assert summary["median_net_profit"] > summary["core_metrics"]["net_profit"]
    assert summary["core_beats_monkey_net_profit_rate"] < summary["beat_threshold"]
    assert summary["meets_monkey_goal"] is False
    assert result["research_verdict"] == "FAIL"


def test_tutorial_configs_are_five_materially_distinct_synthetic_variants(tmp_path):
    output = tmp_path / "tutorial"
    result = run_tutorial(output_root=output, execute=False)

    configs = [yaml.safe_load((output / path.relative_to(output)).read_text(encoding="utf-8")) for path in map(type(output), result["configs"])]
    signatures = {config["research_metadata"]["mechanic_signature"] for config in configs}
    assert len(signatures) == 5
    assert {config["strategy"]["entry"]["module"] for config in configs} == {"calendar_session_bias"}
    assert all(config["attempt_id"] == "original" for config in configs)
    assert result["promotion_eligible"] is False
    assert result["production_ledger_update"] is False


def test_tutorial_json_artifacts_are_strict_and_explain_undefined_metrics(tmp_path):
    output = tmp_path / "tutorial"
    run_tutorial(output_root=output, execute=True)

    metrics_text = (output / "runs" / "v01" / "result_bundle_v2.json").read_text(encoding="utf-8")
    summary_text = (output / "randomized_entry_benchmark" / "v01" / "summary.json").read_text(
        encoding="utf-8"
    )
    assert "Infinity" not in metrics_text
    assert "NaN" not in metrics_text
    assert "Infinity" not in summary_text
    assert "NaN" not in summary_text
    metrics = json.loads(metrics_text)
    assert metrics["schema"] == "alphaquest.result-bundle/v2"
    assert metrics["metrics"]["profit_factor"]["value"] is None
    assert metrics["metrics"]["profit_factor"]["reason"]


def test_tutorial_uses_durable_jobs_without_reserving_a_research_attempt(tmp_path):
    output = tmp_path / "tutorial"
    result = run_tutorial(output_root=output, execute=True)

    queue = SQLiteJobQueue(output / "run-store/studio-runtime/jobs.sqlite3")
    jobs = queue.list_jobs(limit=20)

    assert len(jobs) == 6
    assert all(job.state == OperationalState.SUCCEEDED for job in jobs)
    assert all(job.attempt_reserved is False for job in jobs)
    mechanics = [job for job in jobs if job.job_type == "mechanics_validation_run"]
    result_jobs = [job for job in jobs if job.job_type == "synthetic_tutorial_scientific_evaluation"]
    assert len(mechanics) == 5
    assert all(job.research_verdict == "NEEDS MANUAL REVIEW" for job in mechanics)
    assert len(result_jobs) == 1
    assert result_jobs[0].research_verdict == "FAIL"
    assert result["research_verdict"] == "FAIL"


def test_tutorial_forces_its_disposable_layout_over_a_production_env_override(tmp_path, monkeypatch):
    production = tmp_path / "production"
    production.mkdir()
    layout = production / "storage_layout.yaml"
    layout.write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": str(production / "active"),
                "archive_campaign_roots": [str(production / "archive")],
                "evidence_roots": [str(production / "evidence")],
                "research_artifact_root": str(production / "artifacts"),
                "catalog_root": str(production / "catalogs"),
                "views_root": str(production / "views"),
                "run_store_root": str(production / "run-store"),
                "draft_root": str(production / "drafts"),
                "dataset_root": str(production / "datasets"),
                "handoff_root": str(production / "handoffs"),
                "studio_runtime_root": str(production / "studio-runtime"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALPHAQUEST_STORAGE_LAYOUT", str(layout))

    output = tmp_path / "tutorial"
    result = run_tutorial(output_root=output, execute=False)

    assert result["governed_services"]["publication"]["publication_verdict"] == "PASS"
    assert (output / "research/campaigns/active/tutorial_calendar_bias/campaign.yaml").is_file()
    assert not (production / "active").exists()
    assert not (production / "evidence").exists()
    assert not (production / "datasets").exists()
    assert os.environ["ALPHAQUEST_STORAGE_LAYOUT"] == str(layout)


def test_tutorial_refuses_to_replace_unmarked_directory(tmp_path):
    output = tmp_path / "not_tutorial"
    output.mkdir()
    (output / "keep.txt").write_text("do not delete", encoding="utf-8")

    try:
        run_tutorial(output_root=output, execute=False)
    except RuntimeError as exc:
        assert "refusing to replace non-tutorial directory" in str(exc)
    else:
        raise AssertionError("tutorial replaced an unmarked directory")
