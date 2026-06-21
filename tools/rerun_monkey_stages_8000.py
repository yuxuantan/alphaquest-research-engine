from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import time

import pandas as pd

from propstack.research import campaign_stages as cs
from propstack.utils.config import load_yaml, write_json
from propstack.utils.hashing import file_sha256


TARGET_RUNS = 8000
ROOT_BASE = Path("backtest-campaigns")
AUDIT_PATH = Path("research_artifacts/monkey_8000_rerun_audit_20260620.jsonl")
SUMMARY_FILES = ["campaign_test_summary.json", "variant_test_summary.json"]
STAGE_ORDER = [
    "limited_core_grid_test",
    "limited_monkey_test",
    "walk_forward_analysis",
    "wfa_oos_monkey_test",
    "wfa_oos_monte_carlo",
    "simulated_incubation_core",
    "simulated_incubation_monkey",
    "acceptance_oos_test",
]
MONKEY_STAGES = {
    "limited_monkey_test",
    "wfa_oos_monkey_test",
    "simulated_incubation_monkey",
}
FUTURE_AFTER = {stage: STAGE_ORDER[i + 1 :] for i, stage in enumerate(STAGE_ORDER)}
PASS_ONLY_FILES = ["candidate_strategy_report.md", "methodology_audit.md", "candidate_strategy_report.json"]


def log_event(event: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    with AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def monkey_summary_path(root: Path, stage: str) -> Path:
    if stage == "limited_monkey_test":
        return root / stage / "monkey_summary.json"
    if stage == "wfa_oos_monkey_test":
        return root / stage / "wfa_oos_monkey_summary.json"
    if stage == "simulated_incubation_monkey":
        return root / stage / "incubation_monkey_summary.json"
    raise ValueError(stage)


def already_8000(root: Path, stage: str) -> bool:
    summary = monkey_summary_path(root, stage)
    stage_result = root / stage / "stage_result.json"
    if not stage_result.exists():
        return False
    try:
        r = read_json(stage_result)
    except Exception:
        return False
    override = r.get("rerun_override") or {}
    if override.get("monkey_runs") == TARGET_RUNS and override.get("error_fail_closed"):
        result_text = json.dumps(r, default=str)
        if "PermissionError" in result_text or "Operation not permitted" in result_text:
            return False
        summary_payload = read_json(summary) if summary.exists() else {}
        summary_text = json.dumps(summary_payload, default=str)
        if "PermissionError" in summary_text or "Operation not permitted" in summary_text:
            return False
        return True
    if not summary.exists():
        return False
    try:
        s = read_json(summary)
    except Exception:
        return False
    return (
        int(s.get("number_of_runs") or 0) == TARGET_RUNS
        and override.get("monkey_runs") == TARGET_RUNS
    )


def latest_stage_audit(root: Path, stage: str) -> dict | None:
    if not AUDIT_PATH.exists():
        return None
    latest = None
    root_text = str(root)
    with AUDIT_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                event.get("event") == "stage_done"
                and event.get("root") == root_text
                and event.get("stage") == stage
            ):
                latest = event
    return latest


def changed_failed_to_passed(root: Path, stage: str, prev: dict | None = None, result: dict | None = None) -> bool:
    if prev is not None and result is not None:
        return (not bool(prev.get("passed"))) and bool(result.get("passed"))
    event = latest_stage_audit(root, stage)
    if event is None:
        return False
    return (not bool(event.get("previous_passed"))) and bool(event.get("passed"))


def downstream_needs_run(root: Path, start_stage: str) -> bool:
    summary_path = root / "campaign_test_summary.json"
    if not summary_path.exists():
        return True
    try:
        summary = read_json(summary_path)
    except Exception:
        return True
    stages = {s.get("stage"): s for s in summary.get("stages", []) if s.get("stage")}
    order = summary.get("stage_order") or [s.get("stage") for s in summary.get("stages", []) if s.get("stage")] or STAGE_ORDER
    if start_stage not in order:
        return True
    for stage in order[order.index(start_stage) + 1 :]:
        stage_summary = stages.get(stage) or {}
        skip_reason = str(stage_summary.get("skip_reason", ""))
        status = stage_summary.get("status")
        if status == "failed":
            return False
        if status == "skipped":
            if skip_reason == "disabled":
                continue
            if skip_reason == "prior stage failed":
                return False
            if skip_reason.startswith("not rerun after 8000-iteration monkey audit"):
                return True
            return True
        if status == "passed":
            continue
        if status not in {"passed", "failed", "skipped"}:
            return True
    return False


def set_effective_config_monkey_runs(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "monkey:" and not line.startswith((" ", "\t")):
            start = i
            break
    if start is None:
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if line.strip() in {"prop_rules:", "monte_carlo:"} and not line.startswith((" ", "\t")):
                insert_at = i
                break
        lines.insert(insert_at, f"monkey:\n  runs: {TARGET_RUNS}\n")
        path.write_text("".join(lines), encoding="utf-8")
        return True

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith((" ", "\t")):
            end = i
            break
    for i in range(start + 1, end):
        stripped = lines[i].lstrip(" ")
        indent = lines[i][: len(lines[i]) - len(stripped)]
        if stripped.startswith("runs:"):
            new = f"{indent}runs: {TARGET_RUNS}\n"
            if lines[i] != new:
                lines[i] = new
                path.write_text("".join(lines), encoding="utf-8")
                return True
            return False
    lines.insert(start + 1, f"  runs: {TARGET_RUNS}\n")
    path.write_text("".join(lines), encoding="utf-8")
    return True


def load_cfg(root: Path) -> dict:
    cfg_path = root / "effective_config.yaml"
    set_effective_config_monkey_runs(cfg_path)
    cfg = cs.canonicalize_campaign_config(load_yaml(cfg_path), include_acceptance=True)
    cfg.setdefault("monkey", {})["runs"] = TARGET_RUNS
    cfg["monkey"]["retain_iteration_reports"] = False
    cfg["monkey"]["parallel"] = {
        "enabled": True,
        "scope": "runs",
        "workers": min(max(os.cpu_count() or 1, 1), 8),
    }
    return cfg


def stage_order_for(root: Path, cfg: dict) -> list[str]:
    summary_path = root / "campaign_test_summary.json"
    if summary_path.exists():
        try:
            existing = read_json(summary_path)
            order = existing.get("stage_order")
            if order:
                return list(order)
            stages = [s.get("stage") for s in existing.get("stages", []) if s.get("stage")]
            if stages:
                return stages
        except Exception:
            pass
    return cs._stage_order(cfg.get("campaign_tests") or {})


def skipped_stage(stage: str, reason: str) -> dict:
    out = cs._skipped_stage(stage, reason)
    out["rerun_override"] = {
        "monkey_runs": TARGET_RUNS,
        "reason": reason,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return out


def recompute_summary(root: Path, cfg: dict, new_stage: dict, pruned: list[str], skip_reason: str | None = None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    order = stage_order_for(root, cfg)
    summaries = []
    for name in SUMMARY_FILES:
        path = root / name
        if path.exists():
            summaries.append((name, read_json(path)))
    if not summaries:
        return

    existing_by_stage = {s.get("stage"): s for s in summaries[0][1].get("stages", []) if s.get("stage")}
    existing_by_stage[new_stage["stage"]] = new_stage
    for stage in pruned:
        existing_by_stage[stage] = skipped_stage(stage, skip_reason or "prior stage failed")
    stages = [
        existing_by_stage.get(stage, skipped_stage(stage, "not rerun after 8000-iteration monkey audit"))
        for stage in order
    ]
    any_failed = any(s.get("status") == "failed" for s in stages)
    incomplete_skip = any(
        s.get("status") == "skipped"
        and str(s.get("skip_reason", "")).startswith("not rerun after 8000-iteration monkey audit")
        for s in stages
    )
    prior_failed_skip = any(s.get("status") == "skipped" and s.get("skip_reason") == "prior stage failed" for s in stages)
    halted = any_failed or incomplete_skip or prior_failed_skip
    passed = (not halted) and all(s.get("passed") is True or s.get("skip_reason") == "disabled" for s in stages)
    cfg_hash = file_sha256(root / "effective_config.yaml")

    for _, summary in summaries:
        summary["updated_at"] = now
        summary["stages"] = stages
        summary["passed"] = bool(passed)
        summary["halted"] = bool(halted)
        summary["config_hash"] = cfg_hash
        previous = set((summary.get("rerun_override") or {}).get("stages_rerun", []))
        previous.add(new_stage["stage"])
        summary["rerun_override"] = {
            "monkey_runs": TARGET_RUNS,
            "updated_at": now,
            "stages_rerun": sorted(previous),
        }
        if "effective_config_path" in summary:
            summary["effective_config_path"] = str(root / "effective_config.yaml")
        if "config_path" in summary:
            summary["config_path"] = str(root / "effective_config.yaml")
    for name, summary in summaries:
        write_json(root / name, summary)

    md_path = root / "campaign_test_summary.md"
    if md_path.exists():
        md_path.write_text(cs._markdown_summary(summaries[0][1]), encoding="utf-8")
    if summaries[0][1].get("passed"):
        try:
            cs._write_candidate_due_diligence_package(root, cfg, summaries[0][1], root / "effective_config.yaml")
        except Exception as exc:
            log_event({"event": "candidate_package_error", "root": str(root), "error": repr(exc)})
    else:
        for name in PASS_ONLY_FILES:
            path = root / name
            if path.exists():
                path.unlink()
    manifest = root / "run_manifest.json"
    if manifest.exists():
        manifest_payload = read_json(manifest)
        manifest_payload["updated_at"] = now
        manifest_payload["config_hash"] = cfg_hash
        manifest_payload["effective_config"] = str(root / "effective_config.yaml")
        manifest_payload["rerun_override"] = {"monkey_runs": TARGET_RUNS, "updated_at": now}
        write_json(manifest, manifest_payload)


def prune_future(root: Path, stage: str) -> list[str]:
    removed = []
    for future in FUTURE_AFTER.get(stage, []):
        path = root / future
        if path.exists():
            shutil.rmtree(path)
            removed.append(future)
    for name in PASS_ONLY_FILES:
        path = root / name
        if path.exists():
            path.unlink()
            removed.append(name)
    return removed


def clear_stage_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def error_summary(stage: str, exc: Exception) -> dict:
    return {
        "number_of_runs": TARGET_RUNS,
        "status": "failed",
        "error_fail_closed": True,
        "failure_reason": repr(exc),
        "stage": stage,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def fail_stage_closed(root: Path, stage: str, exc: Exception) -> tuple[dict, list[str]]:
    cfg = load_cfg(root)
    stage_dir = root / stage
    clear_stage_dir(stage_dir)
    result = cs._error_stage(stage, exc)
    result["rerun_override"] = {
        "monkey_runs": TARGET_RUNS,
        "error_fail_closed": True,
        "trigger": "monkey_8000_rerun",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(stage_dir / "stage_result.json", result)
    if stage in MONKEY_STAGES:
        write_json(monkey_summary_path(root, stage), error_summary(stage, exc))
    pruned = prune_future(root, stage)
    recompute_summary(
        root,
        cfg,
        result,
        pruned=FUTURE_AFTER.get(stage, []),
        skip_reason="prior stage failed",
    )
    try:
        cs.update_runs_index(root)
    except Exception as index_exc:
        log_event({"event": "runs_index_update_error", "root": str(root), "stage": stage, "error": repr(index_exc)})
    return result, pruned


def context_for_limited(root: Path, cfg: dict) -> dict:
    campaign_tests = cfg.get("campaign_tests") or {}
    limited_core_cfg = cs._stage_config(campaign_tests, "limited_core_grid_test")
    grid_cfg = cs._merged_section(cfg, "core_grid", limited_core_cfg)
    return {
        "_prepared_data_cache": {},
        "limited_core_grid_results": pd.read_csv(root / "limited_core_grid_test" / "core_grid_results.csv"),
        "limited_core_grid_parameters": grid_cfg.get("parameters", {}) or {},
    }


def context_for_wfa_oos(root: Path, cfg: dict) -> dict:
    wfa_stage = read_json(root / "walk_forward_analysis" / "stage_result.json")
    subset = (
        (wfa_stage.get("summary") or {}).get("resolved_data_subset")
        or (wfa_stage.get("summary") or {}).get("data_subset")
        or ((cfg.get("wfa") or {}).get("data_subset"))
        or ((cfg.get("core") or {}).get("data_subset"))
        or {}
    )
    cache: dict = {}
    market, detail, _quality, _input_hash = cs._prepare_stage_data_cached(
        cfg,
        subset,
        root / "wfa_oos_monkey_test",
        True,
        data_cache=cache,
    )
    trades = pd.read_csv(root / "walk_forward_analysis" / "wfa_oos_trade_log.csv")
    return {"_prepared_data_cache": cache, "wfa_trades": trades, "wfa_market": market, "wfa_detail": detail}


def stage_config_for(cfg: dict, stage: str) -> dict:
    campaign_tests = cfg.get("campaign_tests") or {}
    stage_cfg = copy.deepcopy(cs._stage_config(campaign_tests, stage))
    if stage in MONKEY_STAGES:
        stage_cfg["runs"] = TARGET_RUNS
        stage_cfg["parallel"] = {
            "enabled": True,
            "scope": "runs",
            "workers": min(max(os.cpu_count() or 1, 1), 8),
        }
    return stage_cfg


def run_internal_stage(
    root: Path,
    cfg: dict,
    stage: str,
    context: dict,
    *,
    trigger: str,
) -> dict:
    stage_cfg = stage_config_for(cfg, stage)
    stage_dir = root / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    result = cs._run_stage(stage, cfg, root / "effective_config.yaml", stage_cfg, stage_dir, True, context)
    override = {
        "trigger": trigger,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if stage in MONKEY_STAGES:
        override["monkey_runs"] = TARGET_RUNS
        override["trade_path_stress"] = "skipped_by_user_request"
    result["rerun_override"] = override
    write_json(stage_dir / "stage_result.json", result)
    return result


def run_stage(root: Path, stage: str) -> tuple[dict, list[str]]:
    cfg = load_cfg(root)
    if stage == "limited_monkey_test":
        context = context_for_limited(root, cfg)
    elif stage == "wfa_oos_monkey_test":
        context = context_for_wfa_oos(root, cfg)
    else:
        raise ValueError(f"Unsupported rerun stage {stage}")

    result = run_internal_stage(root, cfg, stage, context, trigger="monkey_8000_rerun")
    pruned = []
    if not result.get("passed"):
        pruned = prune_future(root, stage)
    recompute_summary(
        root,
        cfg,
        result,
        pruned=FUTURE_AFTER.get(stage, []) if not result.get("passed") else [],
        skip_reason="prior stage failed" if not result.get("passed") else None,
    )
    try:
        cs.update_runs_index(root)
    except Exception as exc:
        log_event({"event": "runs_index_update_error", "root": str(root), "stage": stage, "error": repr(exc)})
    return result, pruned


def run_downstream_after(root: Path, start_stage: str) -> list[dict]:
    cfg = load_cfg(root)
    order = stage_order_for(root, cfg)
    if start_stage not in order:
        raise ValueError(f"{start_stage} is not in configured stage order for {root}")
    if start_stage == "wfa_oos_monkey_test":
        context = context_for_wfa_oos(root, cfg)
    else:
        context = context_for_limited(root, cfg)
    completed: list[dict] = []
    campaign_tests = cfg.get("campaign_tests") or {}
    remaining = order[order.index(start_stage) + 1 :]
    log_event({"event": "downstream_start", "root": str(root), "after_stage": start_stage, "remaining": remaining})
    print(f"  downstream after {start_stage}: {remaining}", flush=True)

    for stage in remaining:
        stage_cfg = cs._stage_config(campaign_tests, stage)
        if stage_cfg.get("enabled", True) is False:
            result = skipped_stage(stage, "disabled")
            recompute_summary(root, cfg, result, pruned=[])
            completed.append(result)
            log_event({"event": "downstream_stage_skipped", "root": str(root), "stage": stage, "reason": "disabled"})
            continue

        t0 = time.time()
        print(f"  downstream run {stage} {root}", flush=True)
        try:
            result = run_internal_stage(
                root,
                cfg,
                stage,
                context,
                trigger=f"{start_stage}_failed_to_passed_8000_continuation",
            )
        except Exception as exc:
            stage_dir = root / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
            result = cs._error_stage(stage, exc)
            result["rerun_override"] = {
                "trigger": f"{start_stage}_failed_to_passed_8000_continuation",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            write_json(stage_dir / "stage_result.json", result)

        pruned: list[str] = []
        if not result.get("passed"):
            pruned = prune_future(root, stage)
        recompute_summary(
            root,
            cfg,
            result,
            pruned=FUTURE_AFTER.get(stage, []) if not result.get("passed") else [],
            skip_reason="prior stage failed" if not result.get("passed") else None,
        )
        try:
            cs.update_runs_index(root)
        except Exception as exc:
            log_event({"event": "runs_index_update_error", "root": str(root), "stage": stage, "error": repr(exc)})
        completed.append(result)
        print(
            f"  downstream done {stage} status={result.get('status')} passed={result.get('passed')} "
            f"pruned={pruned} seconds={time.time() - t0:.1f}",
            flush=True,
        )
        log_event(
            {
                "event": "downstream_stage_done",
                "root": str(root),
                "stage": stage,
                "passed": bool(result.get("passed")),
                "status": result.get("status"),
                "pruned": pruned,
                "seconds": round(time.time() - t0, 3),
            }
        )
        if not result.get("passed"):
            break

    log_event(
        {
            "event": "downstream_complete",
            "root": str(root),
            "after_stage": start_stage,
            "completed": [stage.get("stage") for stage in completed],
        }
    )
    return completed


def run_all(root_prefix: str | None = None) -> int:
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    roots = sorted(set(path.parents[1] for path in ROOT_BASE.glob("**/limited_monkey_test/stage_result.json")))
    wfa_roots = sorted(set(path.parents[1] for path in ROOT_BASE.glob("**/wfa_oos_monkey_test/stage_result.json")))
    if root_prefix:
        prefix = Path(root_prefix)
        roots = [root for root in roots if str(root).startswith(str(prefix))]
        wfa_roots = [root for root in wfa_roots if str(root).startswith(str(prefix))]
    print(f"roots_with_limited_monkey={len(roots)} wfa_oos_monkey={len(wfa_roots)} target_runs={TARGET_RUNS}", flush=True)
    log_event(
        {
            "event": "start",
            "limited_roots": len(roots),
            "root_prefix": root_prefix,
            "target_runs": TARGET_RUNS,
            "wfa_roots": len(wfa_roots),
        }
    )
    started = time.time()
    processed = 0
    errors = 0
    newly_failed = []
    newly_passed = []
    downstream_processed = 0

    for i, root in enumerate(roots, start=1):
        stage = "limited_monkey_test"
        prev = read_json(root / stage / "stage_result.json")
        if already_8000(root, stage):
            print(f"[{i}/{len(roots)}] skip already 8000 {root}", flush=True)
            if changed_failed_to_passed(root, stage) and downstream_needs_run(root, stage):
                print(f"[{i}/{len(roots)}] newly passed at 8000; running downstream before next limited monkey {root}", flush=True)
                try:
                    downstream = run_downstream_after(root, stage)
                    downstream_processed += len(downstream)
                except Exception as exc:
                    errors += 1
                    print(f"[{i}/{len(roots)}] downstream ERROR {root}: {exc!r}", flush=True)
                    log_event({"event": "downstream_error", "root": str(root), "after_stage": stage, "error": repr(exc)})
            continue
        print(f"[{i}/{len(roots)}] rerun {stage} {root}", flush=True)
        t0 = time.time()
        try:
            result, pruned = run_stage(root, stage)
            processed += 1
            if prev.get("passed") and not result.get("passed"):
                newly_failed.append(str(root))
            if changed_failed_to_passed(root, stage, prev=prev, result=result):
                newly_passed.append(str(root))
            print(
                f"[{i}/{len(roots)}] done status={result.get('status')} passed={result.get('passed')} "
                f"pruned={pruned} seconds={time.time() - t0:.1f}",
                flush=True,
            )
            log_event(
                {
                    "event": "stage_done",
                    "root": str(root),
                    "stage": stage,
                    "previous_passed": bool(prev.get("passed")),
                    "passed": bool(result.get("passed")),
                    "status": result.get("status"),
                    "pruned": pruned,
                    "seconds": round(time.time() - t0, 3),
                }
            )
            if changed_failed_to_passed(root, stage, prev=prev, result=result):
                print(
                    f"[{i}/{len(roots)}] newly passed at 8000; running downstream before next limited monkey {root}",
                    flush=True,
                )
                downstream = run_downstream_after(root, stage)
                downstream_processed += len(downstream)
        except Exception as exc:
            if isinstance(exc, PermissionError):
                log_event({"event": "stage_permission_error", "root": str(root), "stage": stage, "error": repr(exc)})
                raise
            result, pruned = fail_stage_closed(root, stage, exc)
            processed += 1
            if prev.get("passed"):
                newly_failed.append(str(root))
            print(
                f"[{i}/{len(roots)}] fail-closed status={result.get('status')} passed={result.get('passed')} "
                f"pruned={pruned} error={exc!r}",
                flush=True,
            )
            log_event(
                {
                    "event": "stage_fail_closed",
                    "root": str(root),
                    "stage": stage,
                    "previous_passed": bool(prev.get("passed")),
                    "passed": False,
                    "status": result.get("status"),
                    "pruned": pruned,
                    "error": repr(exc),
                    "seconds": round(time.time() - t0, 3),
                }
            )

    remaining_wfa = [root for root in wfa_roots if (root / "wfa_oos_monkey_test" / "stage_result.json").exists()]
    for i, root in enumerate(remaining_wfa, start=1):
        stage = "wfa_oos_monkey_test"
        prev = read_json(root / stage / "stage_result.json")
        if already_8000(root, stage):
            print(f"[wfa {i}/{len(remaining_wfa)}] skip already 8000 {root}", flush=True)
            if changed_failed_to_passed(root, stage) and downstream_needs_run(root, stage):
                print(f"[wfa {i}/{len(remaining_wfa)}] newly passed at 8000; running downstream {root}", flush=True)
                try:
                    downstream = run_downstream_after(root, stage)
                    downstream_processed += len(downstream)
                except Exception as exc:
                    errors += 1
                    print(f"[wfa {i}/{len(remaining_wfa)}] downstream ERROR {root}: {exc!r}", flush=True)
                    log_event({"event": "downstream_error", "root": str(root), "after_stage": stage, "error": repr(exc)})
            continue
        print(f"[wfa {i}/{len(remaining_wfa)}] rerun {stage} {root}", flush=True)
        t0 = time.time()
        try:
            result, pruned = run_stage(root, stage)
            processed += 1
            if prev.get("passed") and not result.get("passed"):
                newly_failed.append(str(root))
            if changed_failed_to_passed(root, stage, prev=prev, result=result):
                newly_passed.append(str(root))
            print(
                f"[wfa {i}/{len(remaining_wfa)}] done status={result.get('status')} passed={result.get('passed')} "
                f"pruned={pruned} seconds={time.time() - t0:.1f}",
                flush=True,
            )
            log_event(
                {
                    "event": "stage_done",
                    "root": str(root),
                    "stage": stage,
                    "previous_passed": bool(prev.get("passed")),
                    "passed": bool(result.get("passed")),
                    "status": result.get("status"),
                    "pruned": pruned,
                    "seconds": round(time.time() - t0, 3),
                }
            )
            if changed_failed_to_passed(root, stage, prev=prev, result=result):
                print(f"[wfa {i}/{len(remaining_wfa)}] newly passed at 8000; running downstream {root}", flush=True)
                downstream = run_downstream_after(root, stage)
                downstream_processed += len(downstream)
        except Exception as exc:
            if isinstance(exc, PermissionError):
                log_event({"event": "stage_permission_error", "root": str(root), "stage": stage, "error": repr(exc)})
                raise
            result, pruned = fail_stage_closed(root, stage, exc)
            processed += 1
            if prev.get("passed"):
                newly_failed.append(str(root))
            print(
                f"[wfa {i}/{len(remaining_wfa)}] fail-closed status={result.get('status')} "
                f"passed={result.get('passed')} pruned={pruned} error={exc!r}",
                flush=True,
            )
            log_event(
                {
                    "event": "stage_fail_closed",
                    "root": str(root),
                    "stage": stage,
                    "previous_passed": bool(prev.get("passed")),
                    "passed": False,
                    "status": result.get("status"),
                    "pruned": pruned,
                    "error": repr(exc),
                    "seconds": round(time.time() - t0, 3),
                }
            )

    elapsed = round(time.time() - started, 3)
    log_event(
        {
            "event": "complete",
            "processed": processed,
            "downstream_processed": downstream_processed,
            "errors": errors,
            "newly_failed": newly_failed,
            "newly_passed": newly_passed,
            "seconds": elapsed,
        }
    )
    print(
        f"complete processed={processed} downstream_processed={downstream_processed} "
        f"errors={errors} newly_failed={len(newly_failed)} newly_passed={len(newly_passed)} seconds={elapsed}",
        flush=True,
    )
    if newly_failed:
        print("newly_failed_roots:")
        for root in newly_failed:
            print(root)
    if newly_passed:
        print("newly_passed_roots:")
        for root in newly_passed:
            print(root)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun generated monkey stages at 8000 iterations.")
    parser.add_argument(
        "--root-prefix",
        help="Optional backtest-campaigns run-root prefix to limit the artifact rewrite.",
    )
    args = parser.parse_args()
    return run_all(root_prefix=args.root_prefix)


if __name__ == "__main__":
    raise SystemExit(main())
