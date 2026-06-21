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
from propstack.utils.params import apply_dotted_params


ROOT_BASE = Path("backtest-campaigns")
AUDIT_PATH = Path("research_artifacts/stress_cleanup_rerun_audit_20260621.jsonl")
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
STRESS_SUMMARY_FILES = {
    "limited_monkey_test": "trade_path_stress_summary.json",
    "wfa_oos_monkey_test": "wfa_oos_trade_path_stress_summary.json",
    "simulated_incubation_monkey": "incubation_trade_path_stress_summary.json",
}
STRESS_RESULTS_FILES = {
    "limited_monkey_test": "trade_path_stress_results.csv",
    "wfa_oos_monkey_test": "wfa_oos_trade_path_stress_results.csv",
    "simulated_incubation_monkey": "incubation_trade_path_stress_results.csv",
}
MONKEY_SUMMARY_FILES = {
    "limited_monkey_test": "monkey_summary.json",
    "wfa_oos_monkey_test": "wfa_oos_monkey_summary.json",
    "simulated_incubation_monkey": "incubation_monkey_summary.json",
}
FUTURE_AFTER = {stage: STAGE_ORDER[i + 1 :] for i, stage in enumerate(STAGE_ORDER)}
PASS_ONLY_FILES = ["candidate_strategy_report.md", "methodology_audit.md", "candidate_strategy_report.json"]


def log_event(event: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    with AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cfg(root: Path) -> dict:
    cfg = cs.canonicalize_campaign_config(load_yaml(root / "effective_config.yaml"), include_acceptance=True)
    cfg.setdefault("monkey", {})["retain_iteration_reports"] = False
    cfg["monkey"]["parallel"] = {
        "enabled": True,
        "scope": "runs",
        "workers": min(max(os.cpu_count() or 1, 1), 8),
    }
    return cfg


def monkey_summary_path(root: Path, stage: str) -> Path:
    return root / stage / MONKEY_SUMMARY_FILES[stage]


def stress_summary_path(root: Path, stage: str) -> Path:
    return root / stage / STRESS_SUMMARY_FILES[stage]


def has_non_skipped_stress(root: Path, stage: str) -> bool:
    for payload in stress_payloads(root, stage):
        if payload and not bool(payload.get("skipped")):
            return True
    return False


def stress_payloads(root: Path, stage: str) -> list[dict]:
    payloads: list[dict] = []
    for path in [
        stress_summary_path(root, stage),
        monkey_summary_path(root, stage),
        root / stage / "stage_result.json",
        root / "campaign_test_summary.json",
        root / "variant_test_summary.json",
    ]:
        if not path.exists():
            continue
        try:
            payload = read_json(path)
        except Exception:
            payloads.append({"enabled": True, "unreadable": str(path)})
            continue
        if path.name in {"campaign_test_summary.json", "variant_test_summary.json"}:
            for item in payload.get("stages", []):
                if item.get("stage") == stage:
                    stress = (item.get("summary") or {}).get("trade_path_stress")
                    if isinstance(stress, dict):
                        payloads.append(stress)
        elif path.name == "stage_result.json":
            stress = (payload.get("summary") or {}).get("trade_path_stress")
            if isinstance(stress, dict):
                payloads.append(stress)
        else:
            stress = payload.get("trade_path_stress") if path.name in MONKEY_SUMMARY_FILES.values() else payload
            if isinstance(stress, dict):
                payloads.append(stress)
    return payloads


def target_runs_for(root: Path, stage: str, cfg: dict) -> int:
    for path in [monkey_summary_path(root, stage), root / stage / "stage_result.json"]:
        if not path.exists():
            continue
        try:
            payload = read_json(path)
        except Exception:
            continue
        candidates = [payload.get("number_of_runs")]
        if isinstance(payload.get("summary"), dict):
            candidates.append(payload["summary"].get("number_of_runs"))
        for candidate in candidates:
            try:
                runs = int(candidate)
            except (TypeError, ValueError):
                continue
            if runs > 0:
                return runs
    campaign_tests = cfg.get("campaign_tests") or {}
    stage_cfg = cs._stage_config(campaign_tests, stage)
    monkey_cfg = cs._merged_section(cfg, "monkey", stage_cfg)
    return int(monkey_cfg.get("runs", 8000))


def stage_order_for(root: Path, cfg: dict) -> list[str]:
    summary_path = root / "campaign_test_summary.json"
    if summary_path.exists():
        try:
            existing = read_json(summary_path)
            if existing.get("stage_order"):
                return list(existing["stage_order"])
            stages = [s.get("stage") for s in existing.get("stages", []) if s.get("stage")]
            if stages:
                return stages
        except Exception:
            pass
    return cs._stage_order(cfg.get("campaign_tests") or {})


def skipped_stage(stage: str, reason: str, trigger: str) -> dict:
    out = cs._skipped_stage(stage, reason)
    out["rerun_override"] = {
        "trigger": trigger,
        "reason": reason,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return out


def skipped_stress_summary(source_summary: dict | None = None) -> dict:
    _results, stress = cs._skipped_trade_path_stress()
    source_summary = source_summary or {}
    for key in ["configured_data_subset", "resolved_data_subset", "data_subset", "actual_data_period"]:
        if key in source_summary:
            stress[key] = copy.deepcopy(source_summary[key])
    return stress


def write_skipped_stress_artifacts(root: Path, stage: str, source_summary: dict | None = None) -> dict:
    stage_dir = root / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    stress = skipped_stress_summary(source_summary)
    pd.DataFrame(columns=["run_id", "skipped", "skip_reason"]).to_csv(
        stage_dir / STRESS_RESULTS_FILES[stage],
        index=False,
    )
    write_json(stress_summary_path(root, stage), stress)
    return stress


def recompute_summary(
    root: Path,
    cfg: dict,
    new_stage: dict,
    pruned: list[str],
    *,
    trigger: str,
    skip_reason: str | None = None,
) -> None:
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
        existing_by_stage[stage] = skipped_stage(stage, skip_reason or "prior stage failed", trigger)
    stages = [
        existing_by_stage.get(stage, skipped_stage(stage, "not rerun after stress-cleanup audit", trigger))
        for stage in order
    ]
    any_failed = any(s.get("status") == "failed" for s in stages)
    incomplete_skip = any(
        s.get("status") == "skipped"
        and str(s.get("skip_reason", "")).startswith("not rerun after stress-cleanup audit")
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
            "trigger": trigger,
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
        manifest_payload["rerun_override"] = {"trigger": trigger, "updated_at": now}
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


def context_for_incubation_monkey(root: Path, cfg: dict) -> dict:
    stage_result = read_json(root / "simulated_incubation_core" / "stage_result.json")
    summary = stage_result.get("summary") or {}
    subset = (
        summary.get("resolved_data_subset")
        or summary.get("data_subset")
        or ((cfg.get("incubation") or {}).get("data_subset"))
        or ((cfg.get("core") or {}).get("data_subset"))
        or {}
    )
    cache: dict = {}
    market, detail, _quality, _input_hash = cs._prepare_stage_data_cached(
        cfg,
        subset,
        root / "simulated_incubation_monkey",
        True,
        data_cache=cache,
    )
    params = summary.get("incubation_selected_params") or {}
    test_cfg = apply_dotted_params(cfg, params) if params else cfg
    trades = pd.read_csv(root / "simulated_incubation_core" / "trade_log.csv")
    return {
        "_prepared_data_cache": cache,
        "incubation_trades": trades,
        "incubation_market": market,
        "incubation_detail": detail,
        "incubation_config": test_cfg,
    }


def context_for_stage(root: Path, cfg: dict, stage: str) -> dict:
    if stage == "limited_monkey_test":
        return context_for_limited(root, cfg)
    if stage == "wfa_oos_monkey_test":
        return context_for_wfa_oos(root, cfg)
    if stage == "simulated_incubation_monkey":
        return context_for_incubation_monkey(root, cfg)
    raise ValueError(f"Unsupported monkey stage {stage}")


def stage_config_for(cfg: dict, stage: str, target_runs: int | None = None) -> dict:
    campaign_tests = cfg.get("campaign_tests") or {}
    stage_cfg = copy.deepcopy(cs._stage_config(campaign_tests, stage))
    if stage in MONKEY_STAGES:
        runs = int(target_runs or cs._merged_section(cfg, "monkey", stage_cfg).get("runs", 8000))
        stage_cfg["runs"] = runs
        stage_cfg["parallel"] = {
            "enabled": True,
            "scope": "runs",
            "workers": min(max(os.cpu_count() or 1, 1), 8),
        }
        stage_cfg["retain_iteration_reports"] = False
    return stage_cfg


def run_internal_stage(
    root: Path,
    cfg: dict,
    stage: str,
    context: dict,
    *,
    trigger: str,
    target_runs: int | None = None,
    clear_existing: bool = False,
) -> dict:
    stage_cfg = stage_config_for(cfg, stage, target_runs)
    stage_dir = root / stage
    if clear_existing:
        clear_stage_dir(stage_dir)
    else:
        stage_dir.mkdir(parents=True, exist_ok=True)
    result = cs._run_stage(stage, cfg, root / "effective_config.yaml", stage_cfg, stage_dir, True, context)
    override = {
        "trigger": trigger,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if stage in MONKEY_STAGES:
        override["monkey_runs"] = int(stage_cfg.get("runs", target_runs or 0))
        override["trade_path_stress"] = "skipped_by_global_disable"
    result["rerun_override"] = override
    write_json(stage_dir / "stage_result.json", result)
    return result


def error_summary(stage: str, exc: Exception, target_runs: int) -> dict:
    return {
        "number_of_runs": int(target_runs),
        "status": "failed",
        "error_fail_closed": True,
        "failure_reason": repr(exc),
        "stage": stage,
        "trade_path_stress": cs._skipped_trade_path_stress()[1],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def fail_stage_closed(root: Path, stage: str, exc: Exception, target_runs: int) -> tuple[dict, list[str]]:
    cfg = load_cfg(root)
    stage_dir = root / stage
    clear_stage_dir(stage_dir)
    result = cs._error_stage(stage, exc)
    result["rerun_override"] = {
        "trigger": "legacy_stress_cleanup",
        "error_fail_closed": True,
        "monkey_runs": int(target_runs),
        "trade_path_stress": "skipped_by_global_disable",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(stage_dir / "stage_result.json", result)
    if stage in MONKEY_STAGES:
        write_json(monkey_summary_path(root, stage), error_summary(stage, exc, target_runs))
        write_json(stress_summary_path(root, stage), cs._skipped_trade_path_stress()[1])
    pruned = prune_future(root, stage)
    recompute_summary(
        root,
        cfg,
        result,
        pruned=FUTURE_AFTER.get(stage, []),
        trigger="legacy_stress_cleanup",
        skip_reason="prior stage failed",
    )
    try:
        cs.update_runs_index(root)
    except Exception as index_exc:
        log_event({"event": "runs_index_update_error", "root": str(root), "stage": stage, "error": repr(index_exc)})
    return result, pruned


def run_stage(root: Path, stage: str) -> tuple[dict, list[str], int]:
    cfg = load_cfg(root)
    target_runs = target_runs_for(root, stage, cfg)
    context = context_for_stage(root, cfg, stage)
    result = run_internal_stage(
        root,
        cfg,
        stage,
        context,
        trigger="legacy_stress_cleanup",
        target_runs=target_runs,
        clear_existing=True,
    )
    pruned: list[str] = []
    if not result.get("passed"):
        pruned = prune_future(root, stage)
    recompute_summary(
        root,
        cfg,
        result,
        pruned=FUTURE_AFTER.get(stage, []) if not result.get("passed") else [],
        trigger="legacy_stress_cleanup",
        skip_reason="prior stage failed" if not result.get("passed") else None,
    )
    try:
        cs.update_runs_index(root)
    except Exception as exc:
        log_event({"event": "runs_index_update_error", "root": str(root), "stage": stage, "error": repr(exc)})
    return result, pruned, target_runs


def fast_cleanup_stage(root: Path, stage: str) -> tuple[dict, list[str], int] | None:
    stage_result_path = root / stage / "stage_result.json"
    summary_path = monkey_summary_path(root, stage)
    if not stage_result_path.exists() or not summary_path.exists():
        return None

    cfg = load_cfg(root)
    target_runs = target_runs_for(root, stage, cfg)
    stage_result = read_json(stage_result_path)
    monkey_summary = read_json(summary_path)
    stress = write_skipped_stress_artifacts(root, stage, monkey_summary)
    monkey_summary["trade_path_stress"] = stress
    write_json(summary_path, monkey_summary)

    stage_result["summary"] = monkey_summary
    criteria = cs._criteria_for_stage(stage, cs._stage_config(cfg.get("campaign_tests") or {}, stage))
    criteria_results = cs.evaluate_criteria(stage_result, criteria)
    passed = all(item["passed"] for item in criteria_results)
    stage_result["criteria"] = criteria_results
    stage_result["passed"] = bool(passed)
    stage_result["status"] = "passed" if passed else "failed"
    stage_result["rerun_override"] = {
        "trigger": "legacy_stress_cleanup_fast_revalue",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "monkey_runs": int(target_runs),
        "trade_path_stress": "skipped_by_global_disable",
        "random_monkey": "preserved_existing_artifacts",
    }
    write_json(stage_result_path, stage_result)

    pruned: list[str] = []
    if not passed:
        pruned = prune_future(root, stage)
    recompute_summary(
        root,
        cfg,
        stage_result,
        pruned=FUTURE_AFTER.get(stage, []) if not passed else [],
        trigger="legacy_stress_cleanup_fast_revalue",
        skip_reason="prior stage failed" if not passed else None,
    )
    try:
        cs.update_runs_index(root)
    except Exception as exc:
        log_event({"event": "runs_index_update_error", "root": str(root), "stage": stage, "error": repr(exc)})
    return stage_result, pruned, target_runs


def run_downstream_after(root: Path, start_stage: str) -> list[dict]:
    cfg = load_cfg(root)
    order = stage_order_for(root, cfg)
    if start_stage not in order:
        raise ValueError(f"{start_stage} is not in configured stage order for {root}")
    context = context_for_stage(root, cfg, start_stage)
    completed: list[dict] = []
    campaign_tests = cfg.get("campaign_tests") or {}
    remaining = order[order.index(start_stage) + 1 :]
    log_event({"event": "downstream_start", "root": str(root), "after_stage": start_stage, "remaining": remaining})
    print(f"  downstream after {start_stage}: {remaining}", flush=True)

    for stage in remaining:
        stage_cfg = cs._stage_config(campaign_tests, stage)
        if stage_cfg.get("enabled", True) is False:
            result = skipped_stage(stage, "disabled", "legacy_stress_cleanup_continuation")
            recompute_summary(root, cfg, result, pruned=[], trigger="legacy_stress_cleanup_continuation")
            completed.append(result)
            log_event({"event": "downstream_stage_skipped", "root": str(root), "stage": stage, "reason": "disabled"})
            continue

        t0 = time.time()
        print(f"  downstream run {stage} {root}", flush=True)
        try:
            target_runs = target_runs_for(root, stage, cfg) if stage in MONKEY_STAGES else None
            result = run_internal_stage(
                root,
                cfg,
                stage,
                context,
                trigger="legacy_stress_cleanup_continuation",
                target_runs=target_runs,
                clear_existing=stage in MONKEY_STAGES and has_non_skipped_stress(root, stage),
            )
        except Exception as exc:
            stage_dir = root / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
            result = cs._error_stage(stage, exc)
            result["rerun_override"] = {
                "trigger": "legacy_stress_cleanup_continuation",
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
            trigger="legacy_stress_cleanup_continuation",
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


def discover_stress_roots(root_prefix: str | None = None) -> list[tuple[Path, str]]:
    roots: set[tuple[Path, str]] = set()
    for path in ROOT_BASE.rglob("*trade_path_stress_summary.json"):
        if "_archived" in path.parts:
            continue
        stage = path.parent.name
        if stage not in MONKEY_STAGES:
            continue
        root = path.parent.parent
        if root_prefix and not str(root).startswith(str(Path(root_prefix))):
            continue
        if has_non_skipped_stress(root, stage):
            roots.add((root, stage))
    for summary_path in [*ROOT_BASE.rglob("campaign_test_summary.json"), *ROOT_BASE.rglob("variant_test_summary.json")]:
        if "_archived" in summary_path.parts:
            continue
        root = summary_path.parent
        if root_prefix and not str(root).startswith(str(Path(root_prefix))):
            continue
        try:
            payload = read_json(summary_path)
        except Exception:
            continue
        for item in payload.get("stages", []):
            stage = item.get("stage")
            if stage in MONKEY_STAGES and has_non_skipped_stress(root, stage):
                roots.add((root, stage))
    stage_rank = {stage: i for i, stage in enumerate(STAGE_ORDER)}
    return sorted(roots, key=lambda item: (stage_rank.get(item[1], 99), str(item[0])))


def run_all(root_prefix: str | None = None) -> int:
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    started = time.time()
    processed = 0
    errors = 0
    downstream_processed = 0
    newly_failed: list[str] = []
    newly_passed: list[str] = []
    stage_items = discover_stress_roots(root_prefix)
    print(f"legacy_stress_stages={len(stage_items)} root_prefix={root_prefix}", flush=True)
    log_event({"event": "start", "root_prefix": root_prefix, "legacy_stress_stages": len(stage_items)})

    idx = 0
    while True:
        stage_items = discover_stress_roots(root_prefix)
        if not stage_items:
            break
        root, stage = stage_items[0]
        idx += 1
        prev = read_json(root / stage / "stage_result.json") if (root / stage / "stage_result.json").exists() else {}
        print(f"[{idx}] rerun {stage} {root}", flush=True)
        t0 = time.time()
        try:
            fast = fast_cleanup_stage(root, stage)
            if fast is not None:
                result, pruned, target_runs = fast
                mode = "fast_revalue"
            else:
                result, pruned, target_runs = run_stage(root, stage)
                mode = "rerun"
            processed += 1
            if prev.get("passed") and not result.get("passed"):
                newly_failed.append(f"{root}::{stage}")
            failed_to_passed = (not bool(prev.get("passed"))) and bool(result.get("passed"))
            if failed_to_passed:
                newly_passed.append(f"{root}::{stage}")
            print(
                f"[{idx}] done mode={mode} status={result.get('status')} passed={result.get('passed')} "
                f"runs={target_runs} pruned={pruned} seconds={time.time() - t0:.1f}",
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
                    "mode": mode,
                    "target_runs": target_runs,
                    "pruned": pruned,
                    "seconds": round(time.time() - t0, 3),
                }
            )
            if failed_to_passed:
                print(f"[{idx}] failed->passed after removing stress; running downstream {root}", flush=True)
                downstream = run_downstream_after(root, stage)
                downstream_processed += len(downstream)
        except Exception as exc:
            errors += 1
            target_runs = 0
            try:
                cfg = load_cfg(root)
                target_runs = target_runs_for(root, stage, cfg)
                result, pruned = fail_stage_closed(root, stage, exc, target_runs)
                processed += 1
                if prev.get("passed"):
                    newly_failed.append(f"{root}::{stage}")
                print(
                    f"[{idx}] fail-closed status={result.get('status')} passed={result.get('passed')} "
                    f"runs={target_runs} pruned={pruned} error={exc!r}",
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
                        "target_runs": target_runs,
                        "pruned": pruned,
                        "error": repr(exc),
                        "seconds": round(time.time() - t0, 3),
                    }
                )
            except Exception as fail_exc:
                print(f"[{idx}] ERROR {root}::{stage}: {exc!r}; fail-close also failed: {fail_exc!r}", flush=True)
                log_event(
                    {
                        "event": "stage_error",
                        "root": str(root),
                        "stage": stage,
                        "error": repr(exc),
                        "fail_close_error": repr(fail_exc),
                    }
                )
                break

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
        print("newly_failed:")
        for item in newly_failed:
            print(item)
    if newly_passed:
        print("newly_passed:")
        for item in newly_passed:
            print(item)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun legacy monkey stages that still contain real trade-path stress artifacts.")
    parser.add_argument("--root-prefix", help="Optional backtest-campaigns run-root prefix to limit cleanup.")
    args = parser.parse_args()
    return run_all(root_prefix=args.root_prefix)


if __name__ == "__main__":
    raise SystemExit(main())
