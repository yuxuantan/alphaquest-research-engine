import json

import pandas as pd
import yaml

from alphaquest.backtest.equity_report import write_equity_report
from alphaquest.data.quality import save_pipeline_outputs
from tools.cleanup_redundant_generated_artifacts import find_heavy_generated_payloads, find_redundant_runs


def _write_run(root, run_id, *, status):
    run = root / "campaign" / "variant" / "ES" / run_id
    run.mkdir(parents=True)
    config = {
        "campaign_id": "campaign",
        "variant_id": "variant",
        "test_run_id": run_id,
        "symbol": "ES",
        "data": {"dataset_id": "fixture"},
        "strategy": {"entry": {"module": "demo", "params": {"threshold": 1}}},
    }
    (run / "effective_config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    stage = {"stage": "limited_core_grid_test", "status": status, "passed": False}
    if status == "error":
        stage["error"] = "fixture error"
    (run / "campaign_test_summary.json").write_text(
        json.dumps({"updated_at": f"2026-07-11T00:00:0{run_id[-1]}", "stages": [stage]}),
        encoding="utf-8",
    )
    return run


def test_cleanup_detects_only_error_run_replaced_by_same_effective_config(tmp_path):
    root = tmp_path / "backtest-campaigns"
    old = _write_run(root, "run1", status="error")
    current = _write_run(root, "run2", status="failed")

    redundant = find_redundant_runs(root)

    assert len(redundant) == 1
    assert redundant[0]["remove_path"] == old
    assert redundant[0]["keep_path"] == current


def test_cleanup_keeps_error_run_when_replacement_config_differs(tmp_path):
    root = tmp_path / "backtest-campaigns"
    old = _write_run(root, "run1", status="error")
    current = _write_run(root, "run2", status="failed")
    config = yaml.safe_load((current / "effective_config.yaml").read_text(encoding="utf-8"))
    config["strategy"]["entry"]["params"]["threshold"] = 2
    (current / "effective_config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    assert find_redundant_runs(root) == []


def test_cleanup_payload_inventory_is_scoped_to_reconstructable_files(tmp_path):
    root = tmp_path / "backtest-campaigns"
    validation = root / "campaign" / "variant" / "ES" / "run1" / "stage" / "validation"
    validation.mkdir(parents=True)
    heavy = validation / "features_data.csv"
    retained = validation / "data_quality_report.csv"
    heavy.write_text("large", encoding="utf-8")
    retained.write_text("summary", encoding="utf-8")

    groups = find_heavy_generated_payloads(root)

    assert heavy in groups["validation_feature_frames"]
    assert all(retained not in paths for paths in groups.values())


def test_pipeline_outputs_default_to_compact_validation_artifacts(tmp_path):
    timestamp = pd.Timestamp("2024-01-03 09:30", tz="America/New_York")
    frame = pd.DataFrame(
        [{"timestamp": timestamp, "session_date": timestamp.date(), "is_rth": True, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}]
    )

    save_pipeline_outputs(frame, frame, {"rows": 1}, pd.DataFrame(), tmp_path, "America/New_York")

    assert not (tmp_path / "cleaned_data.csv").exists()
    assert not (tmp_path / "features_data.csv").exists()
    assert (tmp_path / "data_quality_report.csv").is_file()
    assert (tmp_path / "tradingview_comparison.csv").is_file()


def test_equity_report_can_omit_redundant_html(tmp_path):
    trades = pd.DataFrame(
        [{"trade_id": 1, "exit_timestamp": "2024-01-03T10:00:00-05:00", "net_pnl": 25.0}]
    )

    report = write_equity_report(trades, tmp_path, write_html=False)

    assert (tmp_path / "equity_curve.csv").is_file()
    assert not (tmp_path / "equity_curve.html").exists()
    assert report["equity_curve_html"] is None
