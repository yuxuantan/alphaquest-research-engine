from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("research/archived_generations/clean_slate_20260720/campaigns/archive/nq_overnight_range_compression_orderflow_breakout")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"
FEATURE_CSV = "data/external/nq_overnight_range_features_20110103_20260529.csv"


def test_nq_overnight_range_breakout_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_overnight_range_compression_orderflow_breakout"
    assert campaign["symbol"] == "NQ"
    assert campaign["source_es_campaign"] == "es_overnight_range_compression_orderflow_breakout"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_range_compression_breakout" in checked
    assert "nq_opening_gap_orderflow_continuation" in checked
    assert "nq_opening_gap_orderflow_absorption_fade" in checked
    assert "nq_overnight_inventory_sweep_reversion" in checked


def test_nq_overnight_range_breakout_variant_configs_use_nq_data_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_overnight_range_compression_orderflow_breakout"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["strategy"]["entry"]["module"] == "overnight_range_orderflow_breakout"
        assert cfg["strategy"]["entry"]["params"]["feature_csv"] == FEATURE_CSV
        assert cfg["strategy"]["entry"]["params"]["breakout_buffer_ticks"] == 0
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["core"]["data_subset"]["start_date"] == "2011-01-03"
        assert cfg["core"]["data_subset"]["end_date"] == "2026-05-29"
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert combo_count == 81
        assert set(params) == {
            "entry.params.max_overnight_range_rank",
            "entry.params.min_orderflow_imbalance",
            "sl.params.stop_offset_ticks",
            "tp.params.target_r_multiple",
        }
        assert params["entry.params.max_overnight_range_rank"] == [0.4, 0.5, 0.6]
        assert len(params["entry.params.min_orderflow_imbalance"]) == 3
        assert params["sl.params.stop_offset_ticks"] == [1, 2, 4]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.25, 1.5]
        assert cfg["wfa"]["parameters"] == params
