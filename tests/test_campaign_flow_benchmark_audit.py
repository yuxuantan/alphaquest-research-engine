import importlib.util
import json
from pathlib import Path
import sys


def _load_tool_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_campaign_flow_benchmarks.py"
    spec = importlib.util.spec_from_file_location("audit_campaign_flow_benchmarks", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _old_limited_core_payload() -> dict:
    return {
        "stage": "limited_core_grid_test",
        "status": "failed",
        "passed": False,
        "summary": {
            "total_combinations_tested": 81,
            "percentage_profitable_iterations": 0.90,
            "number_passing_benchmark": 0,
            "apex_rule_violating_iterations": 0,
        },
        "criteria": [
            {
                "metric": "summary.total_combinations_tested",
                "actual": 81,
                "expected": {"valid_parameter_combination_count": "1 fixed combo or 8-120 tunable combos"},
                "passed": True,
            },
            {
                "metric": "summary.number_passing_benchmark",
                "actual": 0,
                "expected": {"min": 1},
                "passed": False,
            },
            {
                "metric": "summary.apex_rule_violating_iterations",
                "actual": 0,
                "expected": {"max": 0},
                "passed": True,
            },
        ],
    }


def test_audit_flags_old_limited_core_benchmark_gate(tmp_path):
    tool = _load_tool_module()
    path = tmp_path / "limited_core_grid_test" / "stage_result.json"

    issues = tool.audit_stage_payload(_old_limited_core_payload(), path=path, artifact_type="stage_result")

    by_type = {issue["issue_type"]: issue for issue in issues}
    assert "criteria_mismatch" in by_type
    assert "pass_mismatch" in by_type
    assert by_type["pass_mismatch"]["expected_passed"] is True
    expected_metrics = {
        item["metric"] for item in by_type["criteria_mismatch"]["expected_criteria"]
    }
    assert "summary.percentage_profitable_iterations" in expected_metrics
    assert "summary.number_passing_benchmark" not in expected_metrics


def test_summary_audit_flags_downstream_skip_after_reclassified_stage(tmp_path):
    tool = _load_tool_module()
    path = tmp_path / "campaign_test_summary.json"
    summary = {
        "passed": False,
        "stages": [
            _old_limited_core_payload(),
            {
                "stage": "limited_monkey_test",
                "status": "skipped",
                "passed": False,
                "skip_reason": "prior stage failed",
                "criteria": [],
            },
        ],
    }
    path.write_text(json.dumps(summary), encoding="utf-8")

    issues = tool.audit_summary_path(path)

    assert {issue["issue_type"] for issue in issues} >= {
        "criteria_mismatch",
        "pass_mismatch",
        "flow_incomplete_after_reclassification",
    }
