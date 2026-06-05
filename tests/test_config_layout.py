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
