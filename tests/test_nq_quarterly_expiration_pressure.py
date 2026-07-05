from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("campaigns/nq_quarterly_expiration_pressure")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"


def test_nq_quarterly_expiration_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_quarterly_expiration_pressure"
    assert campaign["symbol"] == "NQ"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_monthly_opex_pressure" in checked
    assert "nq_vix_expiration_pressure" in checked
    assert "nq_spx_0dte_expiration_pressure" in checked
    assert "nq_preholiday_effect" in checked
    assert "es_quarterly_expiration_pressure" in checked


def test_nq_quarterly_expiration_variant_configs_use_nq_data_and_sparse_event_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_quarterly_expiration_pressure"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert cfg["benchmarks"]["min_profit_factor"] == 1.2
        assert cfg["benchmarks"]["min_expectancy_r"] == 0.03
        assert cfg["benchmarks"]["min_mar"] == 0.4
        assert cfg["benchmarks"]["min_trades_per_year"] == 5
        assert cfg["wfa"]["selection_exclusive_min_trades_per_year"] == 5
        assert combo_count == 9
        assert set(params) == {"sl.params.stop_pct", "tp.params.target_r_multiple"}
        assert params["sl.params.stop_pct"] == [0.0015, 0.0025, 0.004]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.5, 2.0]
        assert cfg["wfa"]["parameters"] == params
