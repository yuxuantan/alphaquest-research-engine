import pytest

from alphaquest.research.schemas import (
    SchemaValidationError,
    validate_campaign_config_contract,
    validate_run_summary_contract,
    validate_stage_result_contract,
)


def test_campaign_config_contract_accepts_modular_strategy():
    validate_campaign_config_contract(
        {
            "campaign_id": "c",
            "variant_id": "v",
            "symbol": "ES",
            "dataset_id": "fixture",
            "timeframe": "1m",
            "data": {"timezone": "America/New_York", "raw_csv": "bars.csv"},
            "strategy": {
                "entry": {"module": "calendar_session_bias", "params": {}},
                "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
                "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            },
            "core": {"tick_size": 0.25, "point_value": 50.0},
        }
    )


def test_campaign_config_contract_rejects_missing_strategy_section():
    with pytest.raises(SchemaValidationError, match="sl"):
        validate_campaign_config_contract(
            {
                "campaign_id": "c",
                "variant_id": "v",
                "symbol": "ES",
                "dataset_id": "fixture",
                "timeframe": "1m",
                "data": {},
                "strategy": {
                    "entry": {"module": "calendar_session_bias", "params": {}},
                    "tp": {"module": "fixed_r", "params": {}},
                },
                "core": {},
            }
        )


def test_stage_result_contract_rejects_unknown_status():
    with pytest.raises(SchemaValidationError, match="status"):
        validate_stage_result_contract(
            {
                "stage": "limited_core_grid_test",
                "label": "Limited Core Grid Test",
                "status": "maybe",
                "passed": False,
                "criteria": [],
            }
        )


def test_run_summary_contract_requires_policy_metadata():
    stage = {
        "stage": "limited_core_grid_test",
        "label": "Limited Core Grid Test",
        "status": "skipped",
        "passed": False,
        "criteria": [],
    }
    with pytest.raises(SchemaValidationError, match="research_policy"):
        validate_run_summary_contract(
            {
                "campaign_id": "c",
                "variant_id": "v",
                "test_run_id": "run1",
                "symbol": "ES",
                "dataset_id": "fixture",
                "timeframe": "1m",
                "config_hash": "hash",
                "source_config_hash": "hash",
                "output_dir": "backtest-campaigns/c/v/ES/run1",
                "created_at": "2026-07-11T00:00:00",
                "updated_at": "2026-07-11T00:00:00",
                "passed": False,
                "halted": True,
                "stages": [stage],
            }
        )
