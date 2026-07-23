from __future__ import annotations

import csv

import pytest
import yaml

from alphaquest.studio.workflow import StudioWorkflowService


@pytest.mark.parametrize("lifecycle", ["active", "archive"])
def test_studio_draft_rejects_id_reserved_in_configured_campaign_roots(tmp_path, lifecycle: str) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "authored/open",
                "archive_campaign_roots": ["authored/history"],
            }
        ),
        encoding="utf-8",
    )
    source_root = tmp_path / ("authored/open" if lifecycle == "active" else "authored/history")
    campaign = source_root / "es_reserved_edge"
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "campaign_id: es_reserved_edge\ntitle: Existing research\n",
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError, match="campaign ID is already reserved by authored research"):
        StudioWorkflowService(tmp_path).create_draft(
            campaign_id="es_reserved_edge",
            title="A different title",
            instrument="ES",
        )

    assert not (tmp_path / "research/drafts/es_reserved_edge").exists()


def test_studio_draft_rejects_id_reserved_only_in_ledger_history(tmp_path) -> None:
    ledger = tmp_path / "research_ledger.csv"
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["campaign_id", "result"])
        writer.writeheader()
        writer.writerow({"campaign_id": "es_ledger_reserved", "result": "FAIL"})

    with pytest.raises(FileExistsError, match="reserved by research ledger history"):
        StudioWorkflowService(tmp_path).create_draft(
            campaign_id="es_ledger_reserved",
            title="Reused historical identity",
            instrument="ES",
        )

    assert not (tmp_path / "research/drafts/es_ledger_reserved").exists()
