import json
from pathlib import Path
import sqlite3

import yaml

from propstack.cli import main


def test_cli_help(capsys):
    assert main([]) == 0
    assert "Institutional futures research operations CLI" in capsys.readouterr().out


def test_campaign_new_creates_five_variant_scaffold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code = main(["campaign", "new", "demo_edge", "--symbol", "ES", "--edge-family", "demo"])

    assert code == 0
    campaign = yaml.safe_load((tmp_path / "campaigns" / "demo_edge" / "campaign.yaml").read_text(encoding="utf-8"))
    assert campaign["variants"] == ["v01", "v02", "v03", "v04", "v05"]
    assert len(list((tmp_path / "campaigns" / "demo_edge" / "variants").glob("*/config.yaml"))) == 5
    first_modules = tmp_path / "campaigns" / "demo_edge" / "variants" / "v01" / "strategy_modules"
    assert {path.name for path in first_modules.iterdir()} == {"README.md", "entry.py", "stop.py", "target.py"}


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
