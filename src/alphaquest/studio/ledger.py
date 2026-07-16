"""Append-only novice workflow ledger events."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from alphaquest.research.storage import display_path, load_storage_layout


LEDGER_FIELDS = (
    "timestamp",
    "campaign_id",
    "variant_id",
    "instrument",
    "timeframe",
    "edge",
    "variant_mechanic",
    "parameter_space",
    "data_scope",
    "config_path",
    "report_path",
    "stage",
    "result",
    "decision",
    "failure_reason",
    "rescue_attempt",
)


def append_duplicate_closure(
    draft: dict[str, Any],
    *,
    project_root: str | Path = ".",
    failure_reason: str,
) -> Path:
    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    path = root / "research_ledger.csv"
    campaign_id = str(draft.get("campaign_id") or "")
    if not campaign_id:
        raise ValueError("campaign ID is required for ledger closure")
    failure_reason = failure_reason.strip()
    if len(failure_reason) < 80:
        raise ValueError("duplicate closure requires a substantive failure reason of at least 80 characters")
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "campaign_id": campaign_id,
        "variant_id": "",
        "instrument": draft.get("instrument") or "",
        "timeframe": draft.get("timeframe") or "",
        "edge": draft.get("hypothesis") or draft.get("title") or "",
        "variant_mechanic": "Closed before PnL after duplicate-edge review",
        "parameter_space": "not_tested",
        "data_scope": "not_loaded",
        "config_path": display_path(layout.draft_root / campaign_id / "draft.json", root),
        "report_path": "",
        "stage": "duplicate_review",
        "result": "FAIL",
        "decision": "REJECT",
        "failure_reason": failure_reason,
        "rescue_attempt": "none",
    }
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            if fields != LEDGER_FIELDS:
                raise ValueError("research_ledger.csv header does not match the governed append contract")
            if any(
                existing.get("campaign_id") == campaign_id
                and existing.get("stage") == "duplicate_review"
                and existing.get("result") == "FAIL"
                for existing in reader
            ):
                return path
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=LEDGER_FIELDS).writeheader()
    with path.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=LEDGER_FIELDS).writerow(row)
    return path


def append_planned_publication(
    draft: Any,
    *,
    project_root: str | Path = ".",
    active_campaign_root: str | Path | None = None,
) -> tuple[int, Path]:
    """Atomically append missing planned campaign/variant rows.

    The file is replaced as one fsynced snapshot so publication can roll back
    without leaving a half-written CSV. Existing rows are never changed.
    """

    root = Path(project_root).resolve()
    campaign_source_root = (
        Path(active_campaign_root).resolve()
        if active_campaign_root is not None
        else load_storage_layout(root).active_campaign_root
    )
    campaign_root = campaign_source_root / str(draft.campaign_id)
    path = root / "research_ledger.csv"
    existing: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
                raise ValueError("research_ledger.csv header does not match the governed append contract")
            existing = list(reader)
    campaign_id = str(draft.campaign_id)
    existing_keys = {
        (row.get("campaign_id"), row.get("variant_id"), row.get("stage"), row.get("result"))
        for row in existing
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    base = {
        "timestamp": timestamp,
        "campaign_id": campaign_id,
        "instrument": str(draft.instrument),
        "timeframe": str(draft.timeframe),
        "edge": str(draft.hypothesis),
        "data_scope": str(draft.dataset.dataset_id),
        "report_path": "",
        "stage": "stage_1",
        "result": "planned",
        "decision": "TEST",
        "failure_reason": "",
        "rescue_attempt": "none",
    }
    candidates = [
        {
            **base,
            "variant_id": "",
            "variant_mechanic": "Studio campaign published with five frozen, predeclared mechanics",
            "parameter_space": "declared in five immutable variant configs",
            "config_path": display_path(campaign_root / "campaign.yaml", root),
        }
    ]
    for variant in draft.variants:
        candidates.append(
            {
                **base,
                "variant_id": variant.variant_id,
                "variant_mechanic": variant.mechanic_rationale,
                "parameter_space": f"{variant.parameter_combinations} predeclared combination(s)",
                "config_path": display_path(
                    campaign_root / "variants" / variant.variant_id / "config.yaml",
                    root,
                ),
            }
        )
    additions = [
        row
        for row in candidates
        if (row["campaign_id"], row["variant_id"], row["stage"], row["result"]) not in existing_keys
    ]
    if not additions:
        return 0, path
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, prefix=".research_ledger.", suffix=".tmp", newline="", encoding="utf-8", delete=False) as handle:
        temporary = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(existing)
        writer.writerows(additions)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(additions), path


def append_planned_follow_up(
    *,
    campaign: dict[str, Any],
    attempt_id: str,
    attempt_kind: str,
    parent_attempt_id: str,
    reason: str,
    dataset_id: str,
    config_paths: dict[str, str],
    project_root: str | Path = ".",
) -> tuple[int, Path]:
    """Atomically append one idempotent planned row per follow-up variant."""

    root = Path(project_root).resolve()
    path = root / "research_ledger.csv"
    existing: list[dict[str, str]] = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
                raise ValueError("research_ledger.csv header does not match the governed append contract")
            existing = list(reader)
    stage = f"follow_up_attempt/{attempt_id}"
    existing_keys = {
        (row.get("campaign_id"), row.get("variant_id"), row.get("stage"))
        for row in existing
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    campaign_id = str(campaign.get("campaign_id") or "")
    candidates = [
        {
            "timestamp": timestamp,
            "campaign_id": campaign_id,
            "variant_id": variant_id,
            "instrument": str(campaign.get("instrument") or campaign.get("symbol") or ""),
            "timeframe": str(campaign.get("timeframe") or ""),
            "edge": str(campaign.get("hypothesis") or campaign.get("title") or ""),
            "variant_mechanic": (
                f"Explicit {attempt_kind} from {parent_attempt_id}; reviewed reason: {reason}"
            ),
            "parameter_space": "frozen in follow-up strategy_spec.yaml",
            "data_scope": dataset_id,
            "config_path": config_path,
            "report_path": "",
            "stage": stage,
            "result": "planned",
            "decision": "TEST",
            "failure_reason": "",
            "rescue_attempt": attempt_id if attempt_kind == "rescue" else "none",
        }
        for variant_id, config_path in config_paths.items()
    ]
    additions = [
        row
        for row in candidates
        if (row["campaign_id"], row["variant_id"], row["stage"]) not in existing_keys
    ]
    if not additions:
        return 0, path
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        dir=path.parent,
        prefix=".research_ledger.",
        suffix=".tmp",
        newline="",
        encoding="utf-8",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(existing)
        writer.writerows(additions)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(additions), path


__all__ = ["append_duplicate_closure", "append_planned_follow_up", "append_planned_publication"]
