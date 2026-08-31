from alphaquest.research import campaign_stages
from alphaquest.research.policy import load_research_policy


def _objectives(**overrides):
    value = {
        "schema": "alphaquest.research-objectives/v1",
        "development_goal": "Reject the candidate unless every frozen gate is satisfied.",
        "development_deadline": "2099-12-31",
        "evaluation_horizon_months": 24,
        "minimum_annualized_return_fraction": 0.20,
        "minimum_mar": 0.75,
        "maximum_drawdown_fraction": 0.10,
        "minimum_complete_wfa_windows": 4,
        "minimum_wfa_oos_trades": 80,
        "minimum_acceptance_oos_trades": 40,
        "monte_carlo_min_runs": 10000,
        "monte_carlo_horizon_months": 12,
        "minimum_net_profit_probability": 0.80,
        "maximum_account_breach_probability": 0.05,
        "forward_incubation_min_calendar_days": 120,
        "forward_incubation_min_trades": 40,
        "maximum_variants": 3,
        "abandonment_rules": ["Stop at the first terminal scientific failure."],
        "retirement_rules": ["Retire after a frozen live risk boundary is breached."],
        "confirmed": True,
    }
    value.update(overrides)
    return value


def test_research_policy_yaml_is_stage_runner_source_of_truth():
    policy = load_research_policy()

    assert policy.version
    assert policy.file_hash
    assert list(policy.stage_order) == campaign_stages.DEFAULT_STAGE_ORDER
    assert policy.monkey_runs == campaign_stages.DEFAULT_MONKEY_RUNS
    assert policy.shortlist_data_window == campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW
    assert policy.wfa_data_window == campaign_stages.DEFAULT_WFA_DATA_WINDOW
    assert policy.stage_criteria == campaign_stages.DEFAULT_STAGE_CRITERIA
    assert policy.mechanics_validation == {
        "selection_mode": "latest_eligible_sessions",
        "session_count": 10,
        "parameter_mode": "declared_defaults",
        "manual_review_random_sample_size": 5,
        "manual_review_seed": 7,
        "minimum_trade_samples": 5,
    }
    assert policy.walk_forward_analysis["train_months"] == 48
    assert policy.walk_forward_analysis["test_months"] == 12
    assert policy.walk_forward_analysis["step_months"] == 12
    assert policy.simulated_incubation == {"train_months": 48, "test_months": 12}
    assert policy.acceptance_oos == {"train_months": 24, "test_months": 6}
    assert policy.objective_floors["minimum_monte_carlo_runs"] == 8000
    assert policy.objective_floors["minimum_forward_incubation_calendar_days"] == 90


def test_canonicalized_config_stamps_policy_metadata():
    cfg = campaign_stages.canonicalize_campaign_config({}, include_acceptance=False)
    metadata = cfg["research_policy"]

    assert metadata["version"] == load_research_policy().version
    assert metadata["hash"] == load_research_policy().file_hash
    assert metadata["stage_order"] == campaign_stages.DEFAULT_STAGE_ORDER
    assert cfg["campaign_tests"]["research_policy"] == metadata


def test_strategy_owned_stage_overrides_are_replaced_by_policy():
    cfg = campaign_stages.canonicalize_campaign_config(
        {
            "research_metadata": {
                "validation_gate": {
                    "session_count": 200,
                    "manual_review_random_sample_size": 17,
                }
            },
            "core_grid": {"objective": "net_profit"},
            "monkey": {"runs": 12, "seed": 99},
            "wfa": {"train_months": 6, "test_months": 1, "step_months": 1},
            "monte_carlo": {"runs": 20, "seed": 4},
            "campaign_tests": {
                "simulated_incubation_core": {"train_months": 2, "test_months": 1},
                "acceptance_oos_test": {"train_months": 2, "test_months": 1},
            },
        }
    )

    assert cfg["research_metadata"]["validation_gate"]["session_count"] == 10
    assert cfg["research_metadata"]["validation_gate"]["manual_review_random_sample_size"] == 5
    assert cfg["core_grid"]["objective"] == "MAR"
    assert cfg["monkey"]["runs"] == 8000
    assert cfg["monkey"]["seed"] == 7
    assert cfg["wfa"]["train_months"] == 48
    assert cfg["wfa"]["test_months"] == 12
    assert cfg["wfa"]["step_months"] == 12
    assert cfg["monte_carlo"]["runs"] == 8000
    assert cfg["monte_carlo"]["seed"] == 11
    assert cfg["campaign_tests"]["simulated_incubation_core"]["train_months"] == 48
    assert cfg["campaign_tests"]["simulated_incubation_core"]["test_months"] == 12
    assert cfg["campaign_tests"]["acceptance_oos_test"]["train_months"] == 24
    assert cfg["campaign_tests"]["acceptance_oos_test"]["test_months"] == 6


def test_frozen_research_objectives_can_only_tighten_repository_gates():
    cfg = campaign_stages.canonicalize_campaign_config(
        {
            "core": {"initial_balance": 100000.0},
            "research_objectives": _objectives(),
        }
    )

    assert cfg["research_metadata"]["objective_contract"]["status"] == "frozen_pre_pnl"
    assert cfg["monte_carlo"]["runs"] == 10000
    assert cfg["monte_carlo"]["path_months"] == 12
    wfa = {
        item["metric"]: item
        for item in cfg["campaign_tests"]["walk_forward_analysis"]["criteria"]
    }
    assert wfa["summary.realized_oos_windows"]["min"] == 4
    assert wfa["summary.realized_oos_trades"]["min"] == 80
    assert wfa["stitched_oos_metrics.mar"]["min"] == 0.75
    mc = {
        item["metric"]: item
        for item in cfg["campaign_tests"]["wfa_oos_monte_carlo"]["criteria"]
    }
    assert mc["summary.number_of_runs"]["min"] == 10000
    assert "summary.probability_account_breach" not in mc
    assert mc["summary.p95_drawdown"]["max"] == 10000.0
    assert mc["summary.p95_drawdown"]["max"] == 10000.0


def test_weak_research_objectives_fail_closed():
    try:
        campaign_stages.canonicalize_campaign_config(
            {"research_objectives": _objectives(monte_carlo_min_runs=1000)}
        )
    except ValueError as exc:
        assert "monte_carlo_min_runs must be at least 8000" in str(exc)
    else:
        raise AssertionError("weak campaign-owned objectives must not weaken repository policy")
