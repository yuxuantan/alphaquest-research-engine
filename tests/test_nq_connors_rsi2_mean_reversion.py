from __future__ import annotations

from functools import reduce
from operator import mul
from pathlib import Path

import yaml


CAMPAIGN_ROOT = Path("research/campaigns/archive/nq_connors_rsi2_mean_reversion")
NQ_DATASET_ID = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"


def test_nq_connors_rsi2_campaign_is_distinct_and_no_rescue():
    campaign = yaml.safe_load((CAMPAIGN_ROOT / "campaign.yaml").read_text())

    assert campaign["campaign_id"] == "nq_connors_rsi2_mean_reversion"
    assert campaign["symbol"] == "NQ"
    assert campaign["source_es_campaign"] == "es_connors_rsi2_mean_reversion"
    assert campaign["rescue_policy"]["allowed"] is False
    assert len(campaign["variants"]) == 5
    assert len(set(campaign["variants"])) == 5
    assert campaign["parameter_space"]["combinations_by_variant"]["five_min_long_vwap_extreme_1430"] == 81
    assert campaign["parameter_space"]["combinations_by_variant"]["fifteen_min_long_uptrend_pullback_1545"] == 54
    assert campaign["parameter_space"]["pre_pnl_density_prune"]["p_n_l_inspected_before_prune"] is False
    checked = campaign["duplicate_edge_check"]["active_rejected_edges_checked"]
    assert "nq_daily_short_term_reversal" in checked
    assert "nq_prior_session_ibs_reversion" in checked
    assert "nq_intraday_capitulation_mean_reversion" in checked
    assert "nq_vwap_deviation_orderflow_reversion" in checked
    assert "nq_ema_pullback_orderflow_continuation" in checked


def test_nq_connors_rsi2_variant_configs_use_nq_data_economics_and_grid():
    configs = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))

    assert len(configs) == 5
    for config_path in configs:
        cfg = yaml.safe_load(config_path.read_text())
        params = cfg["core_grid"]["parameters"]
        combo_count = reduce(mul, (len(values) for values in params.values()), 1)
        entry_params = cfg["strategy"]["entry"]["params"]

        assert cfg["campaign_id"] == "nq_connors_rsi2_mean_reversion"
        assert cfg["symbol"] == "NQ"
        assert cfg["dataset_id"] == NQ_DATASET_ID
        assert cfg["data"]["symbol"] == "NQ"
        assert cfg["data"]["raw_parquet"].endswith(f"{NQ_DATASET_ID}.parquet")
        assert cfg["strategy"]["entry"]["module"] == "connors_rsi2_mean_reversion"
        assert cfg["research_metadata"]["mechanics_review_required"] is True
        assert cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] == "approve_for_testing"
        assert cfg["core"]["point_value"] == 20.0
        assert cfg["core"]["tick_size"] == 0.25
        assert cfg["core"]["tick_value"] == 5.0
        assert cfg["core"]["data_subset"]["start_date"] == "2011-01-03"
        assert cfg["core"]["data_subset"]["end_date"] == "2026-06-12"
        assert cfg["monte_carlo"]["adverse_slippage_per_trade"] == 5.0
        assert combo_count == campaign_combo_count(cfg["variant_id"])
        assert len([key for key in params if key.startswith("entry.params.")]) == 2
        assert set(params) - {"sl.params.stop_pct", "tp.params.target_r_multiple"}
        assert params["sl.params.stop_pct"] == [0.0025, 0.004, 0.006]
        assert params["tp.params.target_r_multiple"] == [1.0, 1.5, 2.0]
        assert cfg["wfa"]["parameters"] == params
        assert entry_params["rsi_period"] == 2
        assert entry_params["tick_size"] == 0.25
        assert entry_params["max_trades_per_day"] == 1


def campaign_combo_count(variant_id: str) -> int:
    if variant_id in {"fifteen_min_long_uptrend_pullback_1545", "fifteen_min_short_downtrend_bounce_1545"}:
        return 54
    return 81
