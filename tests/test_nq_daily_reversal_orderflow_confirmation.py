from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("research/archived_generations/clean_slate_20260720/campaigns/archive/nq_daily_reversal_orderflow_confirmation")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"


def test_nq_daily_reversal_orderflow_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_daily_reversal_orderflow_confirmation"
    assert campaign["symbol"] == "NQ"
    assert campaign["source_es_campaign"] == "es_daily_reversal_orderflow_confirmation"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    assert campaign["parameter_space"]["total_combinations_per_variant"] == 54
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_daily_short_term_reversal" in checked
    assert "nq_signed_orderflow_persistence" in checked
    assert "nq_orderflow_absorption_exhaustion_reversal" in checked
    assert "nq_connors_rsi2_mean_reversion" in checked


def test_nq_daily_reversal_orderflow_configs_use_nq_data_features_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_daily_reversal_orderflow_confirmation"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["data"]["trade_orderflow_features"]["enabled"] is True
        assert cfg["data"]["trade_orderflow_features"]["windows"] == [12, 18, 24, 30]
        assert cfg["strategy"]["entry"]["module"] == "daily_reversal_orderflow_confirmation"
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert combo_count == 54
        assert set(params) == {
            "entry.params.min_abs_reversal_return_pct",
            "entry.params.min_reversal_flow_imbalance",
            "sl.params.stop_pct",
            "tp.params.target_r_multiple",
        }
        assert cfg["wfa"]["parameters"] == params
