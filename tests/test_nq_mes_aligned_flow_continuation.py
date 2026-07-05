from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("campaigns/nq_mes_aligned_flow_continuation")
NQ_MES_DATASET_ID = "nq_mes_flow_divergence_1m_20190506_20260612_full_rth_ny"


def test_nq_mes_aligned_flow_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_mes_aligned_flow_continuation"
    assert campaign["symbol"] == "NQ"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_mes_micro_flow_divergence_reversion" in checked
    assert "nq_mes_participation_crowding_reversion" in checked
    assert "nq_mes_flow_price_extension_reversion" in checked
    assert "es_mes_aligned_flow_continuation" in checked


def test_nq_mes_aligned_flow_variant_configs_use_nq_mes_data_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_mes_aligned_flow_continuation"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_MES_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_csv"].endswith(f"{NQ_MES_DATASET_ID}.csv")
        assert cfg["strategy"]["entry"]["module"] == "es_mes_aligned_flow_continuation"
        assert cfg["strategy"]["entry"]["params"]["primary_prefix"] == "nq"
        assert "min_es_return_ticks" not in cfg["strategy"]["entry"]["params"]
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["core"]["data_subset"]["start_date"] == "2019-05-06"
        assert cfg["core"]["data_subset"]["end_date"] == "2026-06-12"
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert combo_count == 54
        assert set(params) == {
            "entry.params.min_primary_return_ticks",
            "entry.params.min_mes_flow_imbalance",
            "sl.params.stop_offset_ticks",
            "tp.params.target_r_multiple",
        }
        assert len(params["entry.params.min_primary_return_ticks"]) == 3
        assert len(params["entry.params.min_mes_flow_imbalance"]) == 3
        assert params["sl.params.stop_offset_ticks"] == [1, 2, 4]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.5]
        assert cfg["wfa"]["parameters"] == params
