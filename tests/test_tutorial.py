import json

from propstack.tutorial import run_tutorial


def test_tutorial_generates_isolated_source_without_execution(tmp_path):
    output = tmp_path / "tutorial"

    result = run_tutorial(output_root=output, execute=False)

    assert result["status"] == "PASS"
    assert result["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert len(result["configs"]) == 5
    assert json.loads((output / "tutorial_manifest.json").read_text(encoding="utf-8"))["executed"] is False


def test_tutorial_executes_real_engine_and_writes_artifacts(tmp_path):
    output = tmp_path / "tutorial"

    result = run_tutorial(output_root=output, execute=True)

    assert result["status"] == "PASS"
    assert result["total_trades"] > 0
    assert result["apex_rule_violations"] == 0
    assert (output / "runs" / "v01" / "trade_log.csv").is_file()
