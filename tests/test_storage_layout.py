from __future__ import annotations

import json
from pathlib import Path

import yaml

from alphaquest.research.storage import load_storage_layout, resolve_recorded_path


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
    assert resolve_recorded_path(
        "backtest-campaigns/campaign/variant/ES/run1", project_root=tmp_path
    ) == target


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
