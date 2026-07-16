from pathlib import Path

import yaml

from alphaquest.research import preflight


def _campaign_payload(variants):
    distinction = (
        "A distinct predeclared entry, invalidation, and exit expression tied to the same economic mechanism."
    )
    return {
        "campaign_id": "demo",
        "governance_contract_version": 2,
        "variants": variants,
        "economic_edge_fingerprint": {
            "market_behavior": "Liquidity withdrawal produces a short-lived price dislocation.",
            "causal_mechanism": "Constrained counterparties temporarily consume available depth.",
            "signal_inputs": "Causal price, volume, and completed order-flow observations.",
            "market_context": "ES regular trading hours after the opening auction completes.",
            "holding_period": "Intraday mean reversion before the mandatory flatten time.",
        },
        "duplicate_edge_review": {
            "reviewed_campaign_ids": ["older_edge"],
            "ledger_queries": ["liquidity withdrawal dislocation"],
            "conclusion": "distinct",
            "substantive_distinction": (
                "The reviewed campaign uses scheduled macro surprise while this edge requires endogenous liquidity withdrawal."
            ),
        },
        "variant_distinctions": {
            variant: {"mechanic": f"{variant}: {distinction}", "material_difference": f"{variant}: {distinction}"}
            for variant in variants
        },
        "rescue_policy": {"allowed": True, "max_rescues_per_failed_variant": 1},
    }


def _write_campaign(tmp_path: Path, variants):
    campaign = tmp_path / "campaigns" / "demo"
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(yaml.safe_dump(_campaign_payload(variants)), encoding="utf-8")
    for variant in variants:
        path = campaign / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "campaign_id": "demo",
                    "variant_id": variant,
                    "attempt_id": "original",
                    "attempt_kind": "original",
                    "attempt_provenance": "authored",
                    "research_metadata": {
                        "validation_gate": {
                            "required": True,
                            "lane": "bar",
                            "evidence_dir": f"campaigns/demo/variants/{variant}/validation/evidence",
                            "approval_path": f"campaigns/demo/variants/{variant}/validation/approval.json",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
    return campaign


def test_governance_v2_requires_exactly_five_initial_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    campaign = _write_campaign(tmp_path, ["v01", "v02", "v03", "v04"])
    failures = []

    preflight._validate_campaign_variant_count(campaign / "variants/v01/config.yaml", failures, [])

    assert any("requires exactly 5 initial variants" in item for item in failures)


def test_governance_v2_requires_duplicate_edge_review(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    variants = ["v01", "v02", "v03", "v04", "v05"]
    campaign = _write_campaign(tmp_path, variants)
    payload = yaml.safe_load((campaign / "campaign.yaml").read_text(encoding="utf-8"))
    payload.pop("duplicate_edge_review")
    (campaign / "campaign.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    failures = []

    preflight._validate_campaign_governance(campaign / "variants/v01/config.yaml", failures, [])

    assert any("duplicate_edge_review is required" in item for item in failures)


def test_governance_duplicate_scan_uses_configured_archive_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "workspace/open",
                "archive_campaign_roots": ["history/rejected"],
                "evidence_roots": ["evidence/runs"],
                "research_artifact_root": "artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
            }
        ),
        encoding="utf-8",
    )
    variants = ["v01", "v02", "v03", "v04", "v05"]
    active = tmp_path / "workspace/open/demo"
    active.mkdir(parents=True)
    (active / "campaign.yaml").write_text(
        yaml.safe_dump(_campaign_payload(variants)),
        encoding="utf-8",
    )
    config = active / "variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("campaign_id: demo\nvariant_id: v01\n", encoding="utf-8")
    archived = tmp_path / "history/rejected/prior_edge"
    archived.mkdir(parents=True)
    prior = _campaign_payload(variants)
    prior["campaign_id"] = "prior_edge"
    (archived / "campaign.yaml").write_text(yaml.safe_dump(prior), encoding="utf-8")
    failures = []

    preflight._validate_campaign_governance(config, failures, [])

    assert any("economic edge fingerprint duplicates history/rejected/prior_edge/campaign.yaml" in item for item in failures)


def test_governance_duplicate_scan_includes_ledger_only_definitions(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    variants = ["v01", "v02", "v03", "v04", "v05"]
    active = tmp_path / "research/campaigns/active/demo"
    active.mkdir(parents=True)
    (active / "campaign.yaml").write_text(
        yaml.safe_dump(_campaign_payload(variants)),
        encoding="utf-8",
    )
    config = active / "variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("campaign_id: demo\nvariant_id: v01\n", encoding="utf-8")
    historical = tmp_path / "historical/ledger_prior"
    historical.mkdir(parents=True)
    prior = _campaign_payload(variants)
    prior["campaign_id"] = "ledger_prior"
    (historical / "campaign.yaml").write_text(yaml.safe_dump(prior), encoding="utf-8")
    historical_config = historical / "variants/v01/config.yaml"
    historical_config.parent.mkdir(parents=True)
    historical_config.write_text("campaign_id: ledger_prior\n", encoding="utf-8")
    (tmp_path / "research_ledger.csv").write_text(
        "campaign_id,config_path\n"
        "ledger_prior,historical/ledger_prior/variants/v01/config.yaml\n",
        encoding="utf-8",
    )
    failures = []

    preflight._validate_campaign_governance(config, failures, [])

    assert any(
        "economic edge fingerprint duplicates historical/ledger_prior/campaign.yaml" in item
        for item in failures
    )


def test_governance_v2_limits_rescue_attempts_per_failed_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    variants = ["v01", "v02", "v03", "v04", "v05"]
    campaign = _write_campaign(tmp_path, variants)
    for attempt in ("rescue_one", "rescue_two"):
        path = campaign / "rescue_attempts" / attempt / "rescue_variant" / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            yaml.safe_dump({"research_metadata": {"parent_variant_id": "v01"}}), encoding="utf-8"
        )
    failures = []

    preflight._validate_campaign_governance(campaign / "variants/v01/config.yaml", failures, [])

    assert any("v01 has 2 rescue attempts" in item for item in failures)


def test_governance_v2_requires_unique_authored_attempt_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    variants = ["v01", "v02", "v03", "v04", "v05"]
    campaign = _write_campaign(tmp_path, variants)
    duplicate = campaign / "rescue_attempts/rescue_one/v01/config.yaml"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "variant_id": "v01",
                "attempt_id": "original",
                "attempt_kind": "rescue",
                "attempt_provenance": "authored",
                "parent_attempt_id": "original",
            }
        ),
        encoding="utf-8",
    )
    failures = []

    preflight._validate_attempt_declaration(campaign / "variants/v01/config.yaml", campaign, failures)

    assert any("must be unique" in item for item in failures)


def test_governance_v2_accepts_explicit_non_original_follow_up_outside_initial_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)
    variants = ["v01", "v02", "v03", "v04", "v05"]
    campaign = _write_campaign(tmp_path, variants)
    follow_up = campaign / "follow_up_attempts/replication_20260715/v01/config.yaml"
    follow_up.parent.mkdir(parents=True)
    follow_up.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "variant_id": "v01",
                "attempt_id": "replication_20260715",
                "attempt_kind": "replication",
                "attempt_provenance": "authored",
                "parent_attempt_id": "original",
            }
        ),
        encoding="utf-8",
    )
    failures = []

    preflight._validate_attempt_declaration(follow_up, campaign, failures)

    assert failures == []
