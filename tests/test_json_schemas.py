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


def test_campaign_schema_accepts_representative_authored_campaign():
    schema = _schema("campaign.schema.json")
    campaign = yaml.safe_load(
        Path("research/campaigns/archive/es_amihud_illiquidity_price_impact/campaign.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert list(Draft202012Validator(schema).iter_errors(campaign)) == []


def test_variant_schema_accepts_representative_authored_config():
    schema = _schema("variant-config.schema.json")
    config_path = next(
        Path("research/campaigns/archive/es_amihud_illiquidity_price_impact/variants").glob(
            "*/config.yaml"
        )
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(config)) == []


def test_storage_layout_schema_accepts_repository_configuration():
    schema = _schema("storage-layout.schema.json")
    config = yaml.safe_load(Path("config/storage_layout.yaml").read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(config)) == []
