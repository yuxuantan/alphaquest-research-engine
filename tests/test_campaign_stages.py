import pandas as pd

from propstack.research.campaign_stages import evaluate_criteria
from propstack.research import campaign_stages


def test_stage_criteria_reports_pass_and_fail():
    payload = {
        "summary": {"percentage_profitable_iterations": 0.75},
        "metrics": {"profit_factor": 1.1},
    }

    results = evaluate_criteria(
        payload,
        [
            {"metric": "summary.percentage_profitable_iterations", "min": 0.70},
            {"metric": "metrics.profit_factor", "min": 1.20},
        ],
    )

    assert results[0]["passed"] is True
    assert results[1]["passed"] is False
    assert results[1]["actual"] == 1.1


def test_default_stage_criteria_fail_apex_rule_violations():
    criteria = campaign_stages._criteria_for_stage("simulated_incubation_core", {})
    results = evaluate_criteria(
        {
            "metrics": {
                "profit_factor": 2.0,
                "mar": 2.0,
                "expectancy_r": 0.3,
                "total_trades": 100,
                "win_rate": 0.5,
                "apex_rule_violations": 1,
            }
        },
        criteria,
    )

    apex = [item for item in results if item["metric"] == "metrics.apex_rule_violations"]
    assert apex
    assert apex[0]["passed"] is False


def test_incubation_params_are_selected_from_best_wfa_oos_window():
    wfa_results = pd.DataFrame(
        [
            {
                "selected_params": {"tp.params.target_r_multiple": 1.0},
                "test_profit_factor": 1.5,
                "test_mar": 2.0,
                "test_net_profit": 100.0,
            },
            {
                "selected_params": {"tp.params.target_r_multiple": 2.0},
                "test_profit_factor": 2.0,
                "test_mar": 1.0,
                "test_net_profit": 80.0,
            },
        ]
    )

    assert campaign_stages._select_incubation_params(wfa_results) == {
        "tp.params.target_r_multiple": 2.0
    }


def test_last_months_stage_subset_uses_config_end_date():
    subset = campaign_stages._subset_from_window(
        {"start_date": "2021-01-01", "end_date": "2026-06-01"},
        {"mode": "last_months", "months": 18},
    )

    assert subset == {"start_date": "2024-12-01", "end_date": "2026-06-01"}
