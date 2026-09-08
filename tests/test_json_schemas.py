import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


SCHEMA_ROOT = Path("schemas")


def _schema(name: str) -> dict:
    value = json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def test_all_repository_schemas_are_valid_draft_202012():
    for path in SCHEMA_ROOT.glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_published_economic_edge_taxonomy_satisfies_final_v1_schema():
    schema = _schema("edge-backlog-economic-taxonomy-v1.schema.json")
    taxonomy = json.loads(
        Path("research/edge_backlog/contracts/economic-edge-taxonomy-v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert list(Draft202012Validator(schema).iter_errors(taxonomy)) == []


def test_economic_taxonomy_and_fingerprint_schemas_require_discriminators():
    taxonomy_schema = _schema("edge-backlog-economic-taxonomy-v1.schema.json")
    fingerprint_schema = _schema("edge-backlog-fingerprint-v1.schema.json")
    assert "schema" in taxonomy_schema["required"]
    assert "schema" in fingerprint_schema["required"]

    taxonomy = json.loads(
        Path("research/edge_backlog/contracts/economic-edge-taxonomy-v1.json").read_bytes()
    )
    del taxonomy["schema"]
    taxonomy_errors = list(Draft202012Validator(taxonomy_schema).iter_errors(taxonomy))
    assert any(error.validator == "required" and "schema" in error.message for error in taxonomy_errors)

    fingerprint = {
        "taxonomy_id": "alphaquest-economic-edge",
        "instrument_ids": ["ES"],
        "market_behavior_code": "INVENTORY_IMBALANCE",
        "causal_mechanism_code": "DELAYED_INVENTORY_ADJUSTMENT",
        "beneficiary_counterparty_codes": ["LIQUIDITY_PROVIDERS"],
        "cost_bearer_counterparty_codes": ["HEDGERS"],
        "transfer_rationale_code": "INVENTORY_RISK_COMPENSATION",
        "information_input_codes": ["PRICE"],
        "information_availability_code": "AVAILABLE_AFTER_INTERVAL",
        "expected_effect_code": "PRICE_CONTINUATION",
        "holding_horizon_code": "INTRASESSION",
        "market_context_codes": ["CONTINUOUS_SESSION"],
    }
    fingerprint_errors = list(
        Draft202012Validator(fingerprint_schema).iter_errors(fingerprint)
    )
    assert any(
        error.validator == "required" and "schema" in error.message
        for error in fingerprint_errors
    )


def test_all_canonical_backlog_schemas_require_global_append_sequence():
    for filename in (
        "edge-backlog-observation-revision-v1.schema.json",
        "edge-backlog-entry-revision-v1.schema.json",
        "edge-backlog-decision-v1.schema.json",
        "edge-backlog-link-v1.schema.json",
    ):
        schema = _schema(filename)
        assert "append_sequence" in schema["required"]


def test_campaign_schema_accepts_representative_authored_campaign():
    schema = _schema("campaign.schema.json")
    campaign = yaml.safe_load(
        Path("research/archived_generations/clean_slate_20260720/campaigns/archive/es_amihud_illiquidity_price_impact/campaign.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert list(Draft202012Validator(schema).iter_errors(campaign)) == []


def test_variant_schema_accepts_representative_authored_config():
    schema = _schema("variant-config.schema.json")
    config_path = next(
        Path("research/archived_generations/clean_slate_20260720/campaigns/archive/es_amihud_illiquidity_price_impact/variants").glob(
            "*/config.yaml"
        )
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(config)) == []


def test_storage_layout_schema_accepts_repository_configuration():
    schema = _schema("storage-layout.schema.json")
    config = yaml.safe_load(Path("config/storage_layout.yaml").read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(config)) == []


def test_research_settings_schema_accepts_frozen_objective_policy():
    schema = _schema("research-settings.schema.json")
    config = yaml.safe_load(Path("config/research_settings.yaml").read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(config)) == []
