from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("research/campaigns/archive/nq_intraday_periodicity_persistence")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"
NQ_FEATURE_CSV = "data/external/nq_intraday_periodicity_features_20110103_20260612.csv"


def test_nq_intraday_periodicity_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_intraday_periodicity_persistence"
    assert campaign["symbol"] == "NQ"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    assert campaign["parameter_space"]["per_variant_combinations"] == 54
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_rth_intraday_risk_premium" in checked
    assert "nq_signed_orderflow_persistence" in checked
    assert "nq_daily_short_term_reversal" in checked
    assert "es_intraday_periodicity_persistence" in checked


def test_nq_intraday_periodicity_variant_configs_use_nq_data_features_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert Path(NQ_FEATURE_CSV).exists()
    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_intraday_periodicity_persistence"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["strategy"]["entry"]["module"] == "intraday_periodicity_persistence"
        assert cfg["strategy"]["entry"]["params"]["feature_csv"] == NQ_FEATURE_CSV
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert combo_count == 54
        assert set(params) == {
            "entry.params.lookback_days",
            "entry.params.min_mean_return_bps",
            "sl.params.stop_pct",
            "tp.params.target_r_multiple",
        }
        assert params["entry.params.lookback_days"] == [10, 20, 40]
        assert params["entry.params.min_mean_return_bps"] == [0.5, 1.0, 1.5]
        assert params["sl.params.stop_pct"] == [0.001, 0.0015, 0.0025]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.25]
        assert cfg["wfa"]["parameters"] == params
