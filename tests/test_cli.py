import json
from pathlib import Path
import sqlite3

import yaml

from alphaquest.cli import main


def test_cli_help(capsys):
    assert main([]) == 0
    assert "Institutional futures research operations CLI" in capsys.readouterr().out


def test_studio_status_is_available_without_optional_process(tmp_path, capsys):
    assert main(["studio", "status", "--project-root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["running"] is False
    assert payload["stale_state"] is False


def test_draft_validate_reports_strict_errors_without_yaml(tmp_path, capsys):
    from alphaquest.studio.drafts import DraftStore

    DraftStore(tmp_path).save("es_unfinished", {"title": "Unfinished"}, wizard_step=1)

    assert main(["draft", "validate", "es_unfinished", "--project-root", str(tmp_path), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["errors"]


def test_studio_worker_once_is_a_nonblocking_health_check(tmp_path, capsys):
    assert main(["studio", "worker", "--project-root", str(tmp_path), "--once"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["jobs_handled"] == 0
    assert Path(payload["database"]).is_file()


def test_studio_attempt_cli_enforces_substantive_reason_before_source_changes(tmp_path, capsys):
    code = main(
        [
            "studio",
            "attempt",
            "create",
            "demo",
            "--kind",
            "replication",
            "--reason",
            "too short",
            "--created-by",
            "researcher",
            "--project-root",
            str(tmp_path),
        ]
    )

    assert code == 2
    error = capsys.readouterr().err
    assert "at least 80 characters" in error or "min_length" in error
    assert not (tmp_path / "research/campaigns/active/demo/follow_up_attempts").exists()


def test_campaign_new_creates_five_variant_scaffold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code = main(["campaign", "new", "demo_edge", "--symbol", "ES", "--edge-family", "demo"])

    assert code == 0
    campaign = yaml.safe_load(
        (tmp_path / "research/campaigns/active/demo_edge/campaign.yaml").read_text(encoding="utf-8")
    )
    assert campaign["governance_contract_version"] == 2
    assert campaign["variants"] == ["v01", "v02", "v03", "v04", "v05"]
    assert set(campaign["variant_distinctions"]) == set(campaign["variants"])
    assert "economic_edge_fingerprint" in campaign
    assert "duplicate_edge_review" in campaign
    assert len(
        list((tmp_path / "research/campaigns/active/demo_edge/variants").glob("*/config.yaml"))
    ) == 5
    first_modules = (
        tmp_path / "research/campaigns/active/demo_edge/variants/v01/strategy_modules"
    )
    assert {path.name for path in first_modules.iterdir()} == {"README.md", "entry.py", "stop.py", "target.py"}
    first_config = yaml.safe_load((first_modules.parent / "config.yaml").read_text(encoding="utf-8"))
    assert first_config["attempt_id"] == "original"
    assert first_config["attempt_kind"] == "original"
    assert first_config["attempt_provenance"] == "authored"
    gate = first_config["research_metadata"]["validation_gate"]
    assert gate["required"] is True
    assert gate["evidence_dir"].startswith("research/evidence/runs/")
    assert gate["approval_path"].startswith("research_artifacts/validation_approvals/")
    assert (first_modules.parent / "validation" / "approval.template.json").is_file()


def test_campaign_new_rejects_unsafe_identifier(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code = main(["campaign", "new", "../outside", "--symbol", "ES", "--edge-family", "demo"])

    assert code == 2
    assert not (tmp_path.parent / "outside").exists()
    assert "campaign ID" in capsys.readouterr().err


def test_research_search_filters_registry(tmp_path, capsys):
    database = tmp_path / "registry.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE campaigns (
                campaign_id TEXT, title TEXT, edge_family TEXT, lifecycle_state TEXT,
                authored_decision TEXT, run_count INTEGER, latest_updated_at TEXT, definition_path TEXT
            )"""
        )
        connection.execute("CREATE TABLE runs (campaign_id TEXT, verdict TEXT, failed_stage TEXT, updated_at TEXT)")
        connection.execute(
            "INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("es_demo", "Demo", "fixture", "closed", "FAIL", 1, "2026-07-11", "campaigns/es_demo/campaign.yaml"),
        )
        connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?)", ("es_demo", "FAIL", "limited_core_grid_test", "2026-07-11"))

    code = main(["research", "search", "--database", str(database), "--symbol", "ES", "--json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)[0]["campaign_id"] == "es_demo"


def test_data_inspect_csv(tmp_path, capsys):
    path = tmp_path / "bars.csv"
    path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")

    assert main(["data", "inspect", str(path), "--json"]) == 0

    assert json.loads(capsys.readouterr().out)["columns"] == ["timestamp", "open", "high", "low", "close", "volume"]
