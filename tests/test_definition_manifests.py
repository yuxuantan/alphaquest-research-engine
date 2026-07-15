from pathlib import Path

import yaml

from alphaquest.research.definitions import definition_manifests, write_definition_manifests


def _fixture(root: Path) -> Path:
    campaign = root / "campaigns" / "demo"
    original = campaign / "variants" / "descriptive_original_name"
    rescue = campaign / "rescue_attempts" / "approved_rescue" / "descriptive_rescue_name"
    original.mkdir(parents=True)
    rescue.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text("campaign_id: demo\n", encoding="utf-8")
    (original / "config.yaml").write_text(
        "campaign_id: demo\nvariant_id: base\nsymbol: ES\ntimeframe: 1m\n", encoding="utf-8"
    )
    (rescue / "config.yaml").write_text(
        "campaign_id: demo\nvariant_id: base\ntest_run_id: rescue1\nsymbol: ES\ntimeframe: 1m\n",
        encoding="utf-8",
    )
    return campaign


def test_definition_manifests_flatten_navigation_without_moving_configs(tmp_path):
    campaign = _fixture(tmp_path)

    documents = definition_manifests(project_root=tmp_path)

    variant_document = documents[tmp_path / "catalogs" / "definitions" / "demo.yaml"]
    attempt_document = variant_document["attempts"][0]
    assert variant_document["variants"][0]["short_id"] == "v001"
    assert attempt_document["attempt_id"] == "approved_rescue"
    assert attempt_document["variants"][0]["config_path"].endswith("descriptive_rescue_name/config.yaml")


def test_definition_manifest_writer_is_idempotent(tmp_path):
    campaign = _fixture(tmp_path)

    first = write_definition_manifests(project_root=tmp_path, apply=True)
    second = write_definition_manifests(project_root=tmp_path, apply=True)

    assert first["created"] == 1
    assert second["unchanged"] == 1
    index = tmp_path / "catalogs" / "definitions" / "demo.yaml"
    assert yaml.safe_load(index.read_text(encoding="utf-8"))["generated"] is True


def test_supplemental_configs_are_indexed_without_promoting_them_to_variants(tmp_path):
    campaign = _fixture(tmp_path)
    rejected = campaign / "rejected_pre_pnl_density" / "rejected"
    rejected.mkdir(parents=True)
    (rejected / "config.yaml").write_text(
        "campaign_id: demo\nvariant_id: rejected\nsymbol: ES\ntimeframe: 1m\n", encoding="utf-8"
    )

    document = definition_manifests(project_root=tmp_path)[tmp_path / "catalogs" / "definitions" / "demo.yaml"]

    assert [item["variant_id"] for item in document["variants"]] == ["base"]
    assert document["supplemental_definitions"][0]["definition_state"] == "rejected_pre_pnl_density"
