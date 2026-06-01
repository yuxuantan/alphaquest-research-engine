import pytest

from propstack.utils.config import campaign_root


def test_campaign_root_includes_dataset_id():
    config = {
        "campaign_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
    }

    assert str(campaign_root(config)) == (
        "data/reports/strategies/pdh_pdl_sweep/ES/1m_20221201_20260529/baseline"
    )


def test_campaign_root_requires_dataset_id():
    with pytest.raises(ValueError, match="dataset_id"):
        campaign_root(
            {
                "campaign_id": "baseline",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
            }
        )
