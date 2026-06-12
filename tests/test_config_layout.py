from pathlib import Path

import pytest

from propstack.utils.config import variant_root


def test_variant_root_includes_campaign_dataset_timeframe_and_variant():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    assert str(variant_root(config)) == (
        "data/reports/campaigns/pdh_pdl_sweep/ES/1m_20221201_20260529/5m/baseline"
    )


def test_variant_root_requires_dataset_id():
    with pytest.raises(ValueError, match="dataset_id"):
        variant_root(
            {
                "campaign_id": "pdh_pdl_sweep",
                "variant_id": "baseline",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
                "timeframe": "1m",
            }
        )


def test_variant_root_requires_timeframe():
    with pytest.raises(ValueError, match="timeframe"):
        variant_root(
            {
                "campaign_id": "pdh_pdl_sweep",
                "variant_id": "baseline",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
                "dataset_id": "1m_20221201_20260529",
            }
        )


def test_variant_root_requires_variant_id():
    with pytest.raises(ValueError, match="variant_id"):
        variant_root(
            {
                "campaign_id": "pdh_pdl_sweep",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
                "dataset_id": "1m_20221201_20260529",
                "timeframe": "1m",
            }
        )


def test_active_configs_do_not_reference_invalid_prefixed_sierra_cache():
    invalid_tokens = [
        "sierra_trade_orderflow_1m_20110105_20260610_full_rth",
        "es_sierra_trade_orderflow_1m_20101214_20260610_full_rth.parquet",
        "es_sierra_recent_pocket_combo_signal_1m_20110105_20260610",
        "es_sierra_cross_pocket_meta_signal_1m_20110105_20260610",
        "es_sierra_footprint_extreme_1m_20110105_20260610",
    ]
    offenders = []
    for path in Path("configs/campaigns").rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in invalid_tokens):
            offenders.append(str(path))

    assert offenders == []
