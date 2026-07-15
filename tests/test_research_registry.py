import json
from pathlib import Path
import sqlite3

from alphaquest.research.registry import build_registry, generate_views, registry_summary


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


def test_registry_records_source_lineage_runs_and_stages(tmp_path):
    _write_fixture(tmp_path)
    database = tmp_path / "catalogs" / "registry.sqlite"

    counts = build_registry(project_root=tmp_path, database_path=database)

    assert counts == {"campaigns": 1, "variants": 1, "attempts": 1, "runs": 1, "research_artifacts": 0}
    summary = registry_summary(database)
    assert summary["campaign_lifecycle"] == {"active": 1}
    assert summary["run_verdicts"] == {"FAIL": 1}
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT attempt_id FROM attempts").fetchone()[0] == "rescue_01"
        assert connection.execute("SELECT stage_name FROM stages").fetchone()[0] == "limited_core_grid_test"
        assert connection.execute("SELECT COUNT(*) FROM artifact_objects").fetchone()[0] >= 1
        assert connection.execute("SELECT MIN(LENGTH(sha256)) FROM artifacts").fetchone()[0] == 64


def test_registry_pass_is_candidate_not_tradeable(tmp_path):
    _write_fixture(tmp_path, passed=True)
    database = tmp_path / "catalogs" / "registry.sqlite"
    build_registry(project_root=tmp_path, database_path=database)

    summary = registry_summary(database)

    assert summary["campaign_lifecycle"] == {"candidate": 1}


def test_generated_views_are_replaceable_and_link_to_definitions(tmp_path):
    _write_fixture(tmp_path, passed=True)
    database = tmp_path / "catalogs" / "registry.sqlite"
    build_registry(project_root=tmp_path, database_path=database)

    counts = generate_views(project_root=tmp_path, database_path=database)
    counts_again = generate_views(project_root=tmp_path, database_path=database)

    assert counts == counts_again
    assert counts["candidate"] == 1
    assert (tmp_path / "views" / "candidate" / "definitions" / "demo").resolve() == tmp_path / "campaigns" / "demo"
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
