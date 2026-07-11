import json

from propstack.research.catalog import catalog_rows, write_run_catalog


def test_run_catalog_extracts_policy_and_failed_stage(tmp_path):
    root = tmp_path / "backtest-campaigns"
    run = root / "c" / "v" / "ES" / "run1"
    run.mkdir(parents=True)
    (run / "campaign_test_summary.json").write_text(
        json.dumps(
            {
                "campaign_id": "c",
                "variant_id": "v",
                "test_run_id": "run1",
                "symbol": "ES",
                "dataset_id": "fixture",
                "timeframe": "1m",
                "data_source": "csv",
                "passed": False,
                "halted": True,
                "config_hash": "effective",
                "source_config_hash": "source",
                "output_dir": str(run),
                "updated_at": "2026-07-11T00:00:00",
                "research_policy": {"version": "test", "hash": "policy-hash"},
                "engine_contract_version": "test-engine",
                "stages": [
                    {"stage": "limited_core_grid_test", "status": "passed", "passed": True},
                    {"stage": "limited_monkey_test", "status": "failed", "passed": False},
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = catalog_rows(root)

    assert len(rows) == 1
    assert rows[0]["failed_stage"] == "limited_monkey_test"
    assert rows[0]["research_policy_hash"] == "policy-hash"
    assert rows[0]["engine_contract_version"] == "test-engine"


def test_write_run_catalog_writes_csv(tmp_path):
    root = tmp_path / "empty"
    out = tmp_path / "catalog.csv"

    written = write_run_catalog(root, out)

    assert written == out
    assert out.read_text(encoding="utf-8").startswith("campaign_id,variant_id,test_run_id")


def test_run_catalog_includes_variant_summaries_without_campaign_summary(tmp_path):
    root = tmp_path / "backtest-campaigns"
    campaign_run = root / "c" / "v1" / "ES" / "run1"
    variant_run = root / "c" / "v2" / "ES" / "run2"
    campaign_run.mkdir(parents=True)
    variant_run.mkdir(parents=True)
    base_summary = {
        "campaign_id": "c",
        "test_run_id": "run",
        "symbol": "ES",
        "dataset_id": "fixture",
        "timeframe": "1m",
        "passed": True,
        "halted": False,
        "research_policy": {"version": "test", "hash": "policy-hash"},
        "stages": [],
    }
    (campaign_run / "campaign_test_summary.json").write_text(
        json.dumps({**base_summary, "variant_id": "v1", "test_run_id": "run1"}),
        encoding="utf-8",
    )
    (campaign_run / "variant_test_summary.json").write_text(
        json.dumps({**base_summary, "variant_id": "v1", "test_run_id": "run1"}),
        encoding="utf-8",
    )
    (variant_run / "variant_test_summary.json").write_text(
        json.dumps({**base_summary, "variant_id": "v2", "test_run_id": "run2"}),
        encoding="utf-8",
    )

    rows = catalog_rows(root)

    assert [(row["variant_id"], row["test_run_id"]) for row in rows] == [("v1", "run1"), ("v2", "run2")]
