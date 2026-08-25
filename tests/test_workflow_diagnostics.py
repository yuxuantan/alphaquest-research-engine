from pathlib import Path

from alphaquest.studio.workflow_diagnostics import (
    dataset_readiness_forecast,
    global_next_actions,
    workload_forecast,
    workspace_diagnostics,
)


def test_data_readiness_uses_sequential_wfa_and_holdout_coverage() -> None:
    ready = dataset_readiness_forecast(
        {
            "quality_verdict": "PASS",
            "coverage_start": "2015-01-01T00:00:00Z",
            "coverage_end": "2025-01-01T00:00:00Z",
        }
    )
    short = dataset_readiness_forecast(
        {
            "quality_verdict": "PASS",
            "coverage_start": "2020-01-01T00:00:00Z",
            "coverage_end": "2025-01-01T00:00:00Z",
        }
    )
    assert ready["required_months"] == 102
    assert ready["status"] == "READY"
    assert short["status"] == "NOT_READY"
    assert short["blockers"]


def test_workload_forecast_reports_counts_without_wall_clock_claim() -> None:
    result = workload_forecast(
        {"core_grid": {"parameters": {"entry.a": [1, 2], "sl.b": [3, 4, 5]}}}
    )
    assert result["parameter_combinations"] == 6
    assert result["monte_carlo_paths"] == 8000
    assert "not a wall-clock" in result["limitations"]


def test_global_next_actions_orders_failures_reviews_campaigns_and_drafts() -> None:
    actions = global_next_actions(
        drafts=[{"campaign_id": "draft", "wizard_step": 3}],
        campaigns=[
            {
                "campaign_id": "campaign",
                "workflow_context": {"primary_action": {"label": "Queue run", "section": "testing"}},
            }
        ],
        reviews=[{"campaign_id": "review", "type": "mechanics"}],
        jobs=[{"campaign_id": "blocked", "state": "FAILED_OPERATIONAL", "error": "boom"}],
    )
    assert [item["kind"] for item in actions] == [
        "operational_exception",
        "review",
        "campaign",
        "draft",
    ]


def test_workspace_diagnostics_never_authorizes_legacy_removal(tmp_path: Path) -> None:
    result = workspace_diagnostics(tmp_path, index_refresh={"refreshed": False})
    assert result["legacy_parity"]["safe_to_remove"] is False
    assert result["cache_policy"]["cross_attempt_result_cache"] == "DISABLED"

