from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import traceback
from typing import Any

from propstack.research import campaign_stages as cs
from propstack.utils.config import write_json

import rerun_monkey_stages_8000 as m8
from summarize_backtest_stage_benchmarks import (
    benchmark_id,
    benchmark_label,
    collect_stage_rows,
    criteria_signature,
)


AUDIT_PATH = Path("research_artifacts/noncurrent_benchmark_rerun_audit_20260621.jsonl")
SUMMARY_FILES = ("campaign_test_summary.json", "variant_test_summary.json")
TRIGGER = "current_default_benchmark_rerun"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replace non-current benchmark criteria in backtest-campaigns stage results with current_default "
            "criteria, rerunning downstream stages when a stage changes from failed to passed."
        )
    )
    parser.add_argument("--root", type=Path, default=Path("backtest-campaigns"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    targets = noncurrent_targets(args.root)
    if args.limit is not None:
        targets = targets[: args.limit]
    counts: dict[str, int] = {}
    for target in targets:
        event = process_target(target, dry_run=args.dry_run)
        counts[event["outcome"]] = counts.get(event["outcome"], 0) + 1
        log_event(event)
        print(
            f"{event['outcome']} {target['stage']} {target['root']} "
            f"{event.get('old_status')}->{event.get('new_status')}",
            flush=True,
        )
    print(f"processed={len(targets)} counts={counts}")
    return 0


def noncurrent_targets(root: Path) -> list[dict[str, Any]]:
    rows = collect_stage_rows(root)
    out = []
    for row in rows:
        if row["benchmark_label"] == "current_default":
            continue
        stage = row["stage"]
        if stage not in cs.DEFAULT_STAGE_CRITERIA:
            continue
        stage_path = Path(row["stage_result_path"])
        out.append(
            {
                **row,
                "root": str(stage_path.parent.parent),
                "stage_path": str(stage_path),
            }
        )
    stage_index = {stage: idx for idx, stage in enumerate(cs.DEFAULT_STAGE_ORDER)}
    return sorted(out, key=lambda row: (row["root"], stage_index.get(row["stage"], 999), row["stage"]))


def process_target(target: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    path = Path(target["stage_path"])
    root = Path(target["root"])
    if not path.exists():
        return {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "root": str(root),
            "stage": target["stage"],
            "stage_result_path": str(path),
            "old_benchmark_label": target["benchmark_label"],
            "old_benchmark_id": target["benchmark_id"],
            "dry_run": dry_run,
            "outcome": "skipped_missing_after_prior_correction",
        }
    payload = read_json(path)
    old_status = str(payload.get("status") or target.get("status") or "")
    old_passed = bool(payload.get("passed"))
    current_label = benchmark_label(
        target["stage"],
        criteria_signature(payload.get("criteria") or []),
        old_status,
    )
    if current_label == "current_default":
        return {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "root": str(root),
            "stage": target["stage"],
            "stage_result_path": str(path),
            "old_status": old_status,
            "old_passed": old_passed,
            "old_benchmark_label": target["benchmark_label"],
            "old_benchmark_id": target["benchmark_id"],
            "dry_run": dry_run,
            "outcome": "skipped_already_current_after_prior_correction",
        }
    event = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "stage": target["stage"],
        "stage_result_path": str(path),
        "old_status": old_status,
        "old_passed": old_passed,
        "old_benchmark_label": target["benchmark_label"],
        "old_benchmark_id": target["benchmark_id"],
        "dry_run": dry_run,
    }
    if old_status == "error" or not criteria_signature(payload.get("criteria") or []):
        rerun_event = rerun_stage(root, target["stage"], payload, dry_run=dry_run)
        event.update(rerun_event)
        return event

    current_criteria = copy.deepcopy(cs.DEFAULT_STAGE_CRITERIA[target["stage"]])
    criteria_results = cs.evaluate_criteria(payload, current_criteria)
    new_passed = all(item["passed"] for item in criteria_results)
    new_status = "passed" if new_passed else "failed"
    new_payload = copy.deepcopy(payload)
    new_payload["criteria"] = criteria_results
    new_payload["passed"] = bool(new_passed)
    new_payload["status"] = new_status
    new_payload["rerun_override"] = {
        "trigger": TRIGGER,
        "mode": "rescore_existing_stage_payload",
        "previous_status": old_status,
        "previous_passed": old_passed,
        "previous_benchmark_label": target["benchmark_label"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    event.update(
        {
            "outcome": "dry_run_rescore" if dry_run else "rescored",
            "new_status": new_status,
            "new_passed": bool(new_passed),
            "new_benchmark_id": benchmark_id(target["stage"], criteria_signature(criteria_results)),
            "new_benchmark_label": benchmark_label(target["stage"], criteria_signature(criteria_results), new_status),
            "failed_metrics": [item["metric"] for item in criteria_results if not item["passed"]],
        }
    )
    if dry_run:
        return event

    write_json(path, new_payload)
    if old_passed and not new_passed:
        pruned = m8.prune_future(root, target["stage"])
        m8.recompute_summary(root, m8.load_cfg(root), new_payload, pruned=m8.FUTURE_AFTER.get(target["stage"], []))
        event["pruned"] = pruned
        event["outcome"] = "rescored_pass_to_fail_pruned"
    else:
        m8.recompute_summary(root, m8.load_cfg(root), new_payload, pruned=[])
        if (not old_passed) and new_passed:
            downstream = m8.run_downstream_after(root, target["stage"])
            event["downstream_stages"] = [
                {"stage": item.get("stage"), "status": item.get("status"), "passed": item.get("passed")}
                for item in downstream
            ]
            event["outcome"] = "rescored_fail_to_pass_downstream_run"
    try:
        cs.update_runs_index(root)
    except Exception as exc:
        event["runs_index_error"] = repr(exc)
    return event


def rerun_stage(root: Path, stage: str, old_payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    event = {
        "outcome": "dry_run_actual_rerun_required" if dry_run else "actual_rerun_required",
        "rerun_reason": "stage had no criteria or ended in error",
    }
    if dry_run:
        return event

    cfg = m8.load_cfg(root)
    try:
        result = run_stage_from_scratch(root, cfg, stage)
    except Exception as exc:
        result = cs._error_stage(stage, exc)
        result["rerun_override"] = {
            "trigger": TRIGGER,
            "mode": "actual_stage_rerun_error",
            "previous_status": old_payload.get("status"),
            "error_fail_closed": True,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        stage_dir = root / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        write_json(stage_dir / "stage_result.json", result)
        event["traceback"] = traceback.format_exc()

    new_passed = bool(result.get("passed"))
    event.update(
        {
            "new_status": result.get("status"),
            "new_passed": new_passed,
            "new_benchmark_id": benchmark_id(stage, criteria_signature(result.get("criteria") or [])),
            "new_benchmark_label": benchmark_label(stage, criteria_signature(result.get("criteria") or []), str(result.get("status") or "")),
            "failed_metrics": [
                item.get("metric") for item in result.get("criteria", []) if isinstance(item, dict) and not item.get("passed")
            ],
        }
    )
    if new_passed:
        m8.recompute_summary(root, cfg, result, pruned=[])
        downstream = m8.run_downstream_after(root, stage)
        event["downstream_stages"] = [
            {"stage": item.get("stage"), "status": item.get("status"), "passed": item.get("passed")}
            for item in downstream
        ]
        event["outcome"] = "actual_rerun_passed_downstream_run"
    else:
        pruned = m8.prune_future(root, stage)
        m8.recompute_summary(root, cfg, result, pruned=m8.FUTURE_AFTER.get(stage, []))
        event["pruned"] = pruned
        event["outcome"] = "actual_rerun_failed_pruned"
    try:
        cs.update_runs_index(root)
    except Exception as exc:
        event["runs_index_error"] = repr(exc)
    return event


def run_stage_from_scratch(root: Path, cfg: dict, stage: str) -> dict[str, Any]:
    context: dict[str, Any]
    if stage == "limited_core_grid_test":
        context = {"_prepared_data_cache": {}}
    elif stage == "limited_monkey_test":
        context = m8.context_for_limited(root, cfg)
    elif stage == "walk_forward_analysis":
        context = {"_prepared_data_cache": {}}
    elif stage == "wfa_oos_monkey_test":
        context = m8.context_for_wfa_oos(root, cfg)
    else:
        context = {"_prepared_data_cache": {}}

    stage_dir = root / stage
    m8.clear_stage_dir(stage_dir)
    result = cs._run_stage(
        stage,
        cfg,
        root / "effective_config.yaml",
        m8.stage_config_for(cfg, stage),
        stage_dir,
        True,
        context,
    )
    result["rerun_override"] = {
        "trigger": TRIGGER,
        "mode": "actual_stage_rerun",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(stage_dir / "stage_result.json", result)
    return result


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def log_event(event: dict[str, Any]) -> None:
    if event.get("dry_run"):
        return
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, default=str) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
