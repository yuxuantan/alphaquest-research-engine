from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


CATALOG_COLUMNS = (
    "campaign_id",
    "variant_id",
    "test_run_id",
    "symbol",
    "dataset_id",
    "timeframe",
    "data_source",
    "passed",
    "halted",
    "failed_stage",
    "stage_count",
    "research_policy_version",
    "research_policy_hash",
    "engine_contract_version",
    "config_hash",
    "source_config_hash",
    "input_data_hash",
    "output_dir",
    "summary_path",
    "source_config_path",
    "attempt_id",
    "attempt_kind",
    "attempt_provenance",
    "parent_attempt_id",
    "updated_at",
)


def catalog_rows(root: str | Path = "backtest-campaigns") -> list[dict[str, Any]]:
    rows = [_catalog_row(path) for path in _summary_paths(Path(root))]
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("campaign_id") or ""),
            str(row.get("variant_id") or ""),
            str(row.get("symbol") or ""),
            str(row.get("test_run_id") or ""),
            str(row.get("summary_path") or ""),
        ),
    )


def write_run_catalog(
    root: str | Path = "backtest-campaigns",
    output_csv: str | Path = "research_artifacts/run_catalog.csv",
) -> Path:
    rows = catalog_rows(root)
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in CATALOG_COLUMNS})
    return out


def _summary_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    # The engine enforces campaign/variant/symbol/run. Avoid recursively walking
    # large stage payloads just to discover summaries at known depths.
    campaign_paths = sorted(
        [*root.glob("*/campaign_test_summary.json"), *root.glob("*/*/*/*/campaign_test_summary.json")]
    )
    campaign_parent_dirs = {path.parent for path in campaign_paths}
    variant_paths = [
        path
        for path in sorted(root.glob("*/*/*/*/variant_test_summary.json"))
        if path.parent not in campaign_parent_dirs
    ]
    return [*campaign_paths, *variant_paths]


def _catalog_row(path: Path) -> dict[str, Any]:
    summary = json.loads(path.read_text(encoding="utf-8"))
    policy = summary.get("research_policy") or {}
    stages = summary.get("stages") if isinstance(summary.get("stages"), list) else []
    return {
        "campaign_id": summary.get("campaign_id"),
        "variant_id": summary.get("variant_id"),
        "test_run_id": summary.get("test_run_id") or path.parent.name,
        "symbol": summary.get("symbol"),
        "dataset_id": summary.get("dataset_id"),
        "timeframe": summary.get("timeframe"),
        "data_source": summary.get("data_source"),
        "passed": summary.get("passed"),
        "halted": summary.get("halted"),
        "failed_stage": _first_failed_stage(stages),
        "stage_count": len(stages),
        "research_policy_version": policy.get("version"),
        "research_policy_hash": policy.get("hash"),
        "engine_contract_version": summary.get("engine_contract_version"),
        "config_hash": summary.get("config_hash"),
        "source_config_hash": summary.get("source_config_hash"),
        "input_data_hash": summary.get("input_data_hash"),
        "output_dir": summary.get("output_dir") or str(path.parent),
        "summary_path": str(path),
        "source_config_path": summary.get("source_config_path"),
        "attempt_id": summary.get("attempt_id"),
        "attempt_kind": summary.get("attempt_kind"),
        "attempt_provenance": summary.get("attempt_provenance"),
        "parent_attempt_id": summary.get("parent_attempt_id"),
        "updated_at": summary.get("updated_at") or summary.get("created_at"),
    }


def _first_failed_stage(stages: list[dict[str, Any]]) -> str | None:
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        if stage.get("status") in {"failed", "error"} or stage.get("passed") is False:
            return str(stage.get("stage") or "")
    return None
