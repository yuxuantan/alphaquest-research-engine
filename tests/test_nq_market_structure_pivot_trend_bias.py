from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("research/archived_generations/clean_slate_20260720/campaigns/archive/nq_market_structure_pivot_trend_bias")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"


def test_nq_market_structure_pivot_campaign_is_standalone_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_market_structure_pivot_trend_bias"
    assert campaign["symbol"] == "NQ"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_pivot_filtered_mes_participation_crowding_reversion" in checked
    assert "nq_pivot_mes_orderflow_confirmation" in checked
    assert "nq_self_lead_opening_range_breakout" in checked
    assert "nq_chartfanatics_measured_move_pullback" in checked


def test_nq_market_structure_pivot_variant_configs_use_nq_data_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_market_structure_pivot_trend_bias"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["strategy"]["entry"]["module"] == "market_structure_pivot_continuation"
        assert cfg["strategy"]["entry"]["params"]["tick_size"] == 0.25
        assert cfg["strategy"]["entry"]["params"]["signal_mode"] == "first_bias_in_window"
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["core"]["data_subset"]["start_date"] == "2011-01-03"
        assert cfg["core"]["data_subset"]["end_date"] == "2026-06-12"
        assert combo_count == 27
        assert set(params) == {
            "entry.params.min_pivot_move_ticks",
            "sl.params.stop_pct",
            "tp.params.target_r_multiple",
        }
        assert params["entry.params.min_pivot_move_ticks"] == [0, 2, 4]
        assert params["sl.params.stop_pct"] == [0.0015, 0.0025, 0.004]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.5, 2.0]
        assert cfg["wfa"]["parameters"] == params
