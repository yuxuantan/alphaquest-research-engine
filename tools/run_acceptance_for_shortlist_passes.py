from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import shutil
import traceback
from typing import Any

from propstack.research.campaign_stages import (
    ACCEPTANCE_STAGE,
    DEFAULT_STAGE_ORDER,
    PRE_ACCEPTANCE_STAGE_ORDER,
    canonicalize_campaign_config,
    load_yaml,
    write_json,
    _markdown_summary,
    _run_stage,
    _stage_config,
)
from propstack.utils.config import VARIANT_TEST_SUMMARY_FILENAME, ensure_variant_metadata, update_runs_index
from propstack.utils.hashing import file_sha256


REPORT_ROOT = Path("backtest-campaigns")
ARCHIVE_DIR_NAME = "archive_not_likely_20260614"
DEFAULT_ARTIFACT_STEM = Path("_archived/research_artifacts/acceptance_oos_shortlist_passes_20260615")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run only acceptance OOS for active shortlist-pass reports.")
    parser.add_argument("--dry-run", action="store_true", help="Write the manifest without running acceptance.")
    parser.add_argument("--artifact-stem", default=str(DEFAULT_ARTIFACT_STEM))
    args = parser.parse_args()

    artifact_stem = Path(args.artifact_stem)
    rows = build_plan()
    write_manifest(rows, artifact_stem)
    print_counts(rows)
    if args.dry_run:
        print(f"dry run wrote {artifact_stem}.json and {artifact_stem}.csv")
        return

    run_rows = [row for row in rows if row["decision"] == "run_acceptance_oos"]
    for index, row in enumerate(run_rows, start=1):
        print(f"[{index}/{len(run_rows)}] acceptance {row['campaign_tests_dir']}", flush=True)
        run_acceptance(row)
        write_manifest(rows, artifact_stem)

    print_counts(rows)
    print(f"wrote {artifact_stem}.json and {artifact_stem}.csv")


def build_plan() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(REPORT_ROOT.rglob("campaign_test_summary.json")):
        if ARCHIVE_DIR_NAME in summary_path.parts:
            continue
        campaign_tests_dir = summary_path.parent
        summary = read_json(summary_path)
        if not summary:
            continue
        stages = summary.get("stages") or []
        acceptance_stage = _stage(stages, ACCEPTANCE_STAGE)
        has_acceptance = bool(acceptance_stage)
        pre_acceptance_passed = _pre_acceptance_passed(stages)
        passed = bool(summary.get("passed"))
        source_config = source_config_for(summary, campaign_tests_dir)
        decision = "skip"
        reason = ""
        status = "skipped"
        if pre_acceptance_passed and not has_acceptance:
            decision = "run_acceptance_oos"
            reason = "active shortlist pass without acceptance_oos_test"
            status = "pending"
        elif pre_acceptance_passed and has_acceptance:
            decision = "acceptance_oos_present"
            reason = "acceptance_oos_test present; terminal result recorded"
            status = str(acceptance_stage.get("status") or "unknown")
        elif not passed:
            reason = "summary did not pass shortlist/full-stack gates"
        row = {
            "campaign_tests_dir": str(campaign_tests_dir),
            "source_config": str(source_config) if source_config else "",
            "campaign_id": summary.get("campaign_id"),
            "variant_id": summary.get("variant_id"),
            "symbol": summary.get("symbol"),
            "dataset_id": summary.get("dataset_id"),
            "timeframe": summary.get("timeframe"),
            "decision": decision,
            "reason": reason,
            "status": status,
            "passed": "",
            "failed_criteria": "",
            "acceptance_profit_factor": "",
            "acceptance_mar": "",
            "acceptance_total_trades": "",
            "selected_params": "",
            "error": "",
        }
        if pre_acceptance_passed and has_acceptance:
            _populate_acceptance_fields(row, acceptance_stage, summary_passed=passed)
        rows.append(row)
    return rows


def run_acceptance(row: dict[str, Any]) -> None:
    source = Path(row["source_config"]) if row.get("source_config") else None
    if source is None or not source.is_file():
        row["status"] = "blocked"
        row["passed"] = False
        row["error"] = "missing source config"
        return

    campaign_tests_dir = Path(row["campaign_tests_dir"])
    summary_path = campaign_tests_dir / "campaign_test_summary.json"
    local_config = campaign_tests_dir / "config.yaml"
    try:
        cfg = canonicalize_campaign_config(load_yaml(source), include_acceptance=True)
        variant_metadata = ensure_variant_metadata(cfg, root_path=campaign_tests_dir)
        campaign_tests = cfg.get("campaign_tests") or {}
        stage_cfg = _stage_config(campaign_tests, ACCEPTANCE_STAGE)
        stage_dir = campaign_tests_dir / ACCEPTANCE_STAGE
        if stage_dir.is_dir():
            shutil.rmtree(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)

        result = _run_stage(
            ACCEPTANCE_STAGE,
            cfg,
            source,
            stage_cfg,
            stage_dir,
            True,
            {},
        )
        write_json(stage_dir / "stage_result.json", result)
        if source.resolve() != local_config.resolve():
            shutil.copy2(source, local_config)

        summary = read_json(summary_path)
        stages = [stage for stage in summary.get("stages", []) if stage.get("stage") != ACCEPTANCE_STAGE]
        stages.append(result)
        summary["config_path"] = str(local_config)
        summary["source_config_path"] = str(source)
        completed_at = datetime.now().isoformat(timespec="seconds")
        summary["config_hash"] = file_sha256(local_config)
        summary["variant_metadata"] = variant_metadata
        summary["updated_at"] = completed_at
        summary["acceptance_oos_completed_at"] = completed_at
        summary["stages"] = _ordered_stages(stages)
        summary["halted"] = False
        summary["passed"] = all(
            stage.get("passed") or stage.get("status") == "skipped" for stage in summary["stages"]
        ) and any(stage.get("status") == "passed" for stage in summary["stages"])
        write_json(summary_path, summary)
        write_json(campaign_tests_dir / VARIANT_TEST_SUMMARY_FILENAME, summary)
        (campaign_tests_dir / "campaign_test_summary.md").write_text(_markdown_summary(summary), encoding="utf-8")
        update_runs_index(campaign_tests_dir)

        metrics = result.get("metrics") or {}
        row["status"] = "passed" if result.get("passed") else "failed"
        row["passed"] = bool(summary.get("passed"))
        row["failed_criteria"] = "; ".join(_failed_criteria(result))
        row["acceptance_profit_factor"] = metrics.get("profit_factor", "")
        row["acceptance_mar"] = metrics.get("mar", "")
        row["acceptance_total_trades"] = metrics.get("total_trades", "")
        row["selected_params"] = json.dumps(result.get("selected_params") or {}, sort_keys=True, default=str)
    except Exception as exc:
        row["status"] = "blocked"
        row["passed"] = False
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()


def _ordered_stages(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {stage.get("stage"): stage for stage in stages}
    ordered = [by_name[name] for name in DEFAULT_STAGE_ORDER if name in by_name]
    leftovers = [stage for stage in stages if stage.get("stage") not in DEFAULT_STAGE_ORDER]
    return ordered + leftovers


def _stage(stages: list[dict[str, Any]], stage_name: str) -> dict[str, Any]:
    for stage in stages:
        if stage.get("stage") == stage_name:
            return stage
    return {}


def _pre_acceptance_passed(stages: list[dict[str, Any]]) -> bool:
    by_name = {stage.get("stage"): stage for stage in stages}
    return all(bool(by_name.get(name, {}).get("passed")) for name in PRE_ACCEPTANCE_STAGE_ORDER)


def _populate_acceptance_fields(
    row: dict[str, Any],
    acceptance_stage: dict[str, Any],
    *,
    summary_passed: bool,
) -> None:
    metrics = acceptance_stage.get("metrics") or {}
    row["passed"] = summary_passed
    row["failed_criteria"] = "; ".join(_failed_criteria(acceptance_stage))
    row["acceptance_profit_factor"] = metrics.get("profit_factor", "")
    row["acceptance_mar"] = metrics.get("mar", "")
    row["acceptance_total_trades"] = metrics.get("total_trades", "")
    row["selected_params"] = json.dumps(acceptance_stage.get("selected_params") or {}, sort_keys=True, default=str)


def _failed_criteria(stage: dict[str, Any]) -> list[str]:
    failures = []
    for item in stage.get("criteria", []):
        if item.get("passed"):
            continue
        failures.append(f"{item.get('metric')} actual={item.get('actual')} expected={item.get('expected')}")
    if stage.get("error"):
        failures.append(str(stage["error"]))
    return failures


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def source_config_for(summary: dict, campaign_tests_dir: Path) -> Path | None:
    config_path = summary.get("config_path") if summary else None
    if config_path and Path(config_path).is_file():
        return Path(config_path)
    snapshot = campaign_tests_dir / "config.yaml"
    if snapshot.is_file():
        return snapshot
    return None


def write_manifest(rows: list[dict[str, Any]], artifact_stem: Path) -> None:
    artifact_stem.parent.mkdir(parents=True, exist_ok=True)
    artifact_stem.with_suffix(".json").write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
    fieldnames = [
        "campaign_tests_dir",
        "source_config",
        "campaign_id",
        "variant_id",
        "symbol",
        "dataset_id",
        "timeframe",
        "decision",
        "reason",
        "status",
        "passed",
        "failed_criteria",
        "acceptance_profit_factor",
        "acceptance_mar",
        "acceptance_total_trades",
        "selected_params",
        "error",
    ]
    with artifact_stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def print_counts(rows: list[dict[str, Any]]) -> None:
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["decision"], row["status"])
        counts[key] = counts.get(key, 0) + 1
    for key, value in sorted(counts.items()):
        print(f"{key[0]} {key[1]} {value}")


if __name__ == "__main__":
    main()
