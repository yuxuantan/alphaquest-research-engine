from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("research/campaigns/archive/nq_bankruptcy_distress_regime_reversion")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"
FEATURE_FILE = "data/external/uscourts_bankruptcy_f2_quarterly_features.csv"


def test_nq_bankruptcy_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_bankruptcy_distress_regime_reversion"
    assert campaign["symbol"] == "NQ"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_cftc_tff_hedging_pressure" in checked
    assert "nq_chicagofed_cfnai_activity_pullback" in checked
    assert "nq_intraday_periodicity_persistence" in checked
    assert "es_bankruptcy_distress_regime_reversion" in checked


def test_nq_bankruptcy_variant_configs_use_nq_data_features_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert Path(FEATURE_FILE).exists()
    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_bankruptcy_distress_regime_reversion"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["strategy"]["entry"]["module"] == "bankruptcy_distress_reversion"
        assert cfg["strategy"]["entry"]["params"]["feature_file"] == FEATURE_FILE
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["core"]["data_subset"]["start_date"] == "2016-08-15"
        assert cfg["core"]["data_subset"]["end_date"] == "2026-06-12"
        assert combo_count == 27
        assert set(params) == {
            "entry.params.threshold",
            "sl.params.stop_pct",
            "tp.params.target_r_multiple",
        }
        assert len(params["entry.params.threshold"]) == 3
        assert params["sl.params.stop_pct"] == [0.003, 0.005, 0.007]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.5, 2.0]
        assert cfg["wfa"]["parameters"] == params
