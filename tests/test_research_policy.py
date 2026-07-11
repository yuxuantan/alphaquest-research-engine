from propstack.research import campaign_stages
from propstack.research.policy import load_research_policy


def test_research_policy_yaml_is_stage_runner_source_of_truth():
    policy = load_research_policy()

    assert policy.version
    assert policy.file_hash
    assert list(policy.stage_order) == campaign_stages.DEFAULT_STAGE_ORDER
    assert policy.monkey_runs == campaign_stages.DEFAULT_MONKEY_RUNS
    assert policy.shortlist_data_window == campaign_stages.DEFAULT_SHORTLIST_DATA_WINDOW
    assert policy.wfa_data_window == campaign_stages.DEFAULT_WFA_DATA_WINDOW
    assert policy.stage_criteria == campaign_stages.DEFAULT_STAGE_CRITERIA


def test_canonicalized_config_stamps_policy_metadata():
    cfg = campaign_stages.canonicalize_campaign_config({}, include_acceptance=False)
    metadata = cfg["research_policy"]

    assert metadata["version"] == load_research_policy().version
    assert metadata["hash"] == load_research_policy().file_hash
    assert metadata["stage_order"] == campaign_stages.DEFAULT_STAGE_ORDER
    assert cfg["campaign_tests"]["research_policy"] == metadata
