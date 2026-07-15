import hashlib
import json
from pathlib import Path

import yaml

from alphaquest.research.explain import explain_research, explanation_markdown
from alphaquest.research.lineage import inspect_run_lineage
from alphaquest.research.registry import build_registry


def _workspace(tmp_path: Path):
    run_uid = "11111111-1111-4111-8111-111111111111"
    campaign_dir = tmp_path / "campaigns/demo"
    config_path = campaign_dir / "variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    data_path = tmp_path / "data/raw/ES/bars.csv"
    data_path.parent.mkdir(parents=True)
    data_path.write_text("timestamp,open,high,low,close,volume\n2024-01-02T14:30:00Z,1,2,0,1,10\n")
    campaign = {
        "campaign_id": "demo",
        "title": "Demo Campaign",
        "edge_family": "liquidity_dislocation",
        "hypothesis": "Temporary liquidity withdrawal creates a causal intraday dislocation.",
        "sources": [{"title": "Source", "authors": "Author", "year": 2024}],
        "variants": ["v01"],
        "variant_distinctions": {
            "v01": {
                "mechanic": "Completed-bar dislocation entry with fixed invalidation.",
                "material_difference": "This fixture has one selected mechanical expression.",
            }
        },
        "decision": "FAIL",
    }
    (campaign_dir / "campaign.yaml").write_text(yaml.safe_dump(campaign), encoding="utf-8")
    config = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "symbol": "ES",
        "dataset_id": "fixture",
        "timeframe": "1m",
        "data": {
            "source": "csv",
            "vendor": "fixture_vendor",
            "raw_csv": str(data_path),
            "timezone": "America/New_York",
            "session": "RTH",
            "continuous_contract": "none",
            "start_date": "2024-01-02",
            "end_date": "2024-01-02",
        },
        "core": {"tick_size": 0.25, "point_value": 50, "commission_per_contract": 2.5, "slippage_ticks": 1},
        "strategy": {
            "entry": {"module": "demo", "params": {"threshold": 1}},
            "sl": {"module": "fixed", "params": {"ticks": 4}},
            "tp": {"module": "fixed", "params": {"ticks": 8}},
            "flatten_time": "15:55:00",
        },
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    source_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()

    run_dir = tmp_path / "backtest-campaigns/demo/v01/ES/run1"
    run_dir.mkdir(parents=True)
    (run_dir / "source_config.yaml").write_bytes(config_path.read_bytes())
    (run_dir / "effective_config.yaml").write_bytes(config_path.read_bytes())
    (run_dir / "input_data_hash.txt").write_text("input-hash", encoding="utf-8")
    (run_dir / "run_uid.txt").write_text(run_uid, encoding="utf-8")
    summary = {
        "run_uid": run_uid,
        "campaign_id": "demo",
        "variant_id": "v01",
        "test_run_id": "run1",
        "symbol": "ES",
        "dataset_id": "fixture",
        "timeframe": "1m",
        "data_source": "csv",
        "passed": False,
        "halted": True,
        "decision": "FAIL",
        "config_hash": source_hash,
        "source_config_hash": source_hash,
        "input_data_hash": "input-hash",
        "source_config_path": "campaigns/demo/variants/v01/config.yaml",
        "output_dir": "backtest-campaigns/demo/v01/ES/run1",
        "updated_at": "2026-07-15T00:00:00+00:00",
        "stages": [{"stage": "limited_core_grid_test", "status": "failed", "passed": False, "reason": "gate"}],
    }
    (run_dir / "campaign_test_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_uid": run_uid,
                "campaign_id": "demo",
                "variant_id": "v01",
                "test_run_id": "run1",
                "config_source": "campaigns/demo/variants/v01/config.yaml",
                "effective_config": "backtest-campaigns/demo/v01/ES/run1/effective_config.yaml",
                "source_config_snapshot": "backtest-campaigns/demo/v01/ES/run1/source_config.yaml",
                "config_hash": source_hash,
                "source_config_hash": source_hash,
                "input_data_hash": "input-hash",
            }
        ),
        encoding="utf-8",
    )
    database = tmp_path / "catalogs/research_registry.sqlite"
    build_registry(project_root=tmp_path, database_path=database)
    return database, run_dir, run_uid


def test_explanation_traces_campaign_variant_run_and_strict_verdict(tmp_path):
    database, _, run_uid = _workspace(tmp_path)

    payload = explain_research("demo", database_path=database, project_root=tmp_path, variant_id="v01", run_id=run_uid)
    markdown = explanation_markdown(payload)

    assert payload["campaign"]["hypothesis"].startswith("Temporary liquidity withdrawal")
    assert payload["variants"][0]["mechanics"]["entry"]["module"] == "demo"
    assert payload["run"]["run_uid"] == run_uid
    assert payload["final_verdict"] == "FAIL"
    assert "Generated projection" in markdown
    assert "Data, Execution, And Lineage" in markdown


def test_lineage_fails_closed_on_config_hash_mismatch(tmp_path):
    _, run_dir, _ = _workspace(tmp_path)
    (run_dir / "source_config.yaml").write_text("changed: true\n", encoding="utf-8")

    report = inspect_run_lineage(run_dir, project_root=tmp_path)

    assert report["lineage_verdict"] == "FAIL"
    assert "source_config hash mismatch" in report["errors"]
