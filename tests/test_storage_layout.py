from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from alphaquest.research.storage import (
    campaign_definition_paths,
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.studio.ledger import append_duplicate_closure
from alphaquest.studio.workspace import refresh_generated_indexes_if_stale


def test_duplicate_closure_requires_substantive_failure_reason(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 80 characters"):
        append_duplicate_closure(
            {"campaign_id": "duplicate_draft"},
            project_root=tmp_path,
            failure_reason="Same idea.",
        )

    assert not (tmp_path / "research_ledger.csv").exists()


def test_storage_layout_is_configurable_and_resolves_legacy_prefixes(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "work/active",
                "archive_campaign_roots": ["work/archive"],
                "evidence_roots": ["evidence/runs"],
                "research_artifact_root": "artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
                "migration_manifest": "artifacts/migration.json",
                "legacy_prefixes": {"backtest-campaigns/": "evidence/runs/"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    target = tmp_path / "evidence/runs/campaign/variant/ES/run1"
    target.mkdir(parents=True)
    layout = load_storage_layout(tmp_path)
    assert layout.active_campaign_root == tmp_path / "work/active"
    assert layout.draft_root == tmp_path / "research/drafts"
    assert layout.dataset_root == tmp_path / "research/datasets"
    assert layout.handoff_root == tmp_path / "research/handoffs"
    assert layout.studio_runtime_root == tmp_path / "run-store/studio-runtime"
    assert resolve_recorded_path(
        "backtest-campaigns/campaign/variant/ES/run1", project_root=tmp_path
    ) == target


def test_studio_indexes_views_and_duplicate_draft_paths_honor_custom_layout(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "source/active",
                "archive_campaign_roots": ["source/archive"],
                "evidence_roots": ["evidence/runs"],
                "research_artifact_root": "durable",
                "catalog_root": "generated/catalog",
                "views_root": "generated/views",
                "run_store_root": "generated/run-store",
                "draft_root": "authoring/drafts",
                "dataset_root": "authoring/datasets",
                "handoff_root": "authoring/handoffs",
                "studio_runtime_root": "runtime/studio",
            }
        ),
        encoding="utf-8",
    )
    campaign = tmp_path / "source/active/example"
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "campaign_id: example\ntitle: Example\nvariants: []\n",
        encoding="utf-8",
    )

    refreshed = refresh_generated_indexes_if_stale(tmp_path, force=True)
    ledger = append_duplicate_closure(
        {
            "campaign_id": "duplicate_draft",
            "title": "Duplicate draft",
            "instrument": "ES",
            "timeframe": "1m",
        },
        project_root=tmp_path,
        failure_reason=(
            "The exact economic edge and causal mechanism already exist in governed prior research, "
            "so another parameterized copy would not represent independent evidence."
        ),
    )

    assert refreshed["refreshed"] is True
    assert (tmp_path / "generated/catalog/research_registry.sqlite").is_file()
    assert (tmp_path / "generated/views/.generated_by_alphaquest").is_file()
    assert not (tmp_path / "catalogs/research_registry.sqlite").exists()
    assert "authoring/drafts/duplicate_draft/draft.json" in ledger.read_text(encoding="utf-8")


def test_campaign_context_resolves_configured_active_and_archive_roots(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "source/open",
                "archive_campaign_roots": ["history/closed"],
                "evidence_roots": ["evidence/runs"],
                "research_artifact_root": "artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
            }
        ),
        encoding="utf-8",
    )
    active_config = tmp_path / "source/open/live_edge/variants/v01/config.yaml"
    archive_config = tmp_path / "history/closed/old_edge/variants/v01/config.yaml"

    active = resolve_campaign_context(active_config, project_root=tmp_path)
    archived = resolve_campaign_context(archive_config, project_root=tmp_path)

    assert active is not None
    assert active.campaign_id == "live_edge"
    assert active.campaign_root == tmp_path / "source/open/live_edge"
    assert active.lifecycle == "active"
    assert archived is not None
    assert archived.campaign_id == "old_edge"
    assert archived.campaign_root == tmp_path / "history/closed/old_edge"
    assert archived.lifecycle == "archive"


def test_campaign_definition_discovery_includes_ledger_referenced_history(tmp_path: Path) -> None:
    historical = tmp_path / "historical/ledger_only_edge"
    historical.mkdir(parents=True)
    definition = historical / "campaign.yaml"
    definition.write_text("campaign_id: ledger_only_edge\n", encoding="utf-8")
    config = historical / "variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("campaign_id: ledger_only_edge\n", encoding="utf-8")
    (tmp_path / "research_ledger.csv").write_text(
        "campaign_id,config_path\n"
        "ledger_only_edge,historical/ledger_only_edge/variants/v01/config.yaml\n",
        encoding="utf-8",
    )

    definitions = campaign_definition_paths(project_root=tmp_path)

    assert definition.resolve() in definitions


def test_campaign_context_does_not_treat_generated_evidence_as_authored_source(tmp_path: Path) -> None:
    evidence = tmp_path / "research/evidence/runs/demo"
    evidence.mkdir(parents=True)
    (evidence / "campaign.yaml").write_text("campaign_id: demo\n", encoding="utf-8")
    generated_config = evidence / "v01/ES/run1/effective_config.yaml"
    generated_config.parent.mkdir(parents=True)
    generated_config.write_text("campaign_id: demo\n", encoding="utf-8")

    assert resolve_campaign_context(generated_config, project_root=tmp_path) is None


def test_applied_repository_migration_preserves_every_registered_uid_and_path() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "research_artifacts/migrations/research_storage_layout_20260715.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "APPLIED_VERIFIED"
    verification = manifest["verification"]
    assert verification["failures"] == []
    assert verification["resolved_run_uids"] == verification["expected_run_uids"]
    assert verification["resolved_after_migration"] == verification["previously_resolvable_paths"]
    layout = load_storage_layout(root)
    for item in manifest["resolution_snapshot"]["paths"]:
        if item["existed_before"]:
            assert resolve_recorded_path(
                item["recorded_path"], project_root=root, layout=layout
            ).exists()
