from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("campaigns/nq_vwap_deviation_orderflow_reversion")


def test_nq_vwap_deviation_campaign_is_distinct_and_scaled_before_pnl():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_vwap_deviation_orderflow_reversion"
    assert campaign["symbol"] == "NQ"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    assert campaign["instrument_scaling"]["source_es_grid_ticks"] == [8, 12, 16]
    assert campaign["instrument_scaling"]["nq_grid_ticks"] == [28, 40, 56]
    assert "nq_vwap_pullback_continuation" in campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_rolling_stat_envelope_orderflow_reversion" in campaign["duplicate_edge_check"]["active_rejected_edges_checked"]


def test_nq_vwap_deviation_variant_configs_use_nq_data_economics_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)

        assert cfg["campaign_id"] == "nq_vwap_deviation_orderflow_reversion"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith("nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert cfg["benchmarks"]["min_profit_factor"] == 1.2
        assert cfg["benchmarks"]["min_expectancy_r"] == 0.03
        assert cfg["benchmarks"]["min_mar"] == 0.4
        assert cfg["strategy"]["entry"]["params"]["min_vwap_deviation_ticks"] == 40
        assert combo_count == 27
        assert params["entry.params.min_vwap_deviation_ticks"] == [28, 40, 56]
        assert params["entry.params.min_counterflow_imbalance"] == [0.0, 0.02, 0.04]
        assert params["tp.params.target_r_multiple"] == [1.0]
