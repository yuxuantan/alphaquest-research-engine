#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import yaml


RUN_ID = "tp_min_rr_rescue1"
RESCUE_ID = "tp_min_rr_floor_rescue_1"
MIN_TARGET_R_MULTIPLE = 1.0
TODAY = datetime.now().strftime("%Y-%m-%d")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGED_TIMEOUT_SECONDS = 45 * 60

TARGET_KEYS = {
    "tp.params.target_r_multiple",
    "entry.params.target_r_multiple",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class SelectedRun:
    campaign_id: str
    variant_id: str
    run_id: str
    run_dir: Path
    summary_path: Path
    source_config_path: Path
    score: tuple
    metrics: dict[str, Any]


def _num(value: Any, default: float = 0.0) -> float:
    if value in {None, ""}:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out):
        return default
    return out


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _run_parts(summary_path: Path) -> tuple[str, str, str, Path] | None:
    # backtest-campaigns/{campaign}/{variant}/ES/{run}/limited_core_grid_test/core_grid_summary.json
    try:
        rel = summary_path.relative_to(ROOT / "backtest-campaigns")
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 6 or parts[2] != "ES":
        return None
    campaign_id, variant_id, run_id = parts[0], parts[1], parts[3]
    run_dir = ROOT / "backtest-campaigns" / campaign_id / variant_id / "ES" / run_id
    return campaign_id, variant_id, run_id, run_dir


def _source_config_for_run(run_dir: Path) -> Path | None:
    summary_path = run_dir / "campaign_test_summary.json"
    candidates: list[Path] = []
    if summary_path.exists():
        try:
            summary = _load_json(summary_path)
            for key in ("source_config_path", "source_config_snapshot_path", "effective_config_path", "config_path"):
                value = summary.get(key)
                if value:
                    candidates.append(ROOT / str(value))
        except Exception:
            pass
    candidates.extend(
        [
            run_dir / "source_config.yaml",
            run_dir / "effective_config.yaml",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    return None


def _target_columns_from_header(header: list[str]) -> list[str]:
    return [column for column in header if column in TARGET_KEYS]


def _load_grid_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _target_grid_signal(run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    header, rows = _load_grid_rows(run_dir / "limited_core_grid_test" / "core_grid_results.csv")
    target_columns = _target_columns_from_header(header)
    top = (summary.get("top_10_combinations") or [{}])[0] or {}
    if not rows or not target_columns:
        return {
            "target_key": "",
            "target_grid_values": [],
            "target_grid_values_below_1r": [],
            "target_grid_has_below_1r": False,
            "top_target_value": "",
            "top_target_is_grid_max": False,
            "higher_target_net_slope": 0.0,
            "higher_target_pf_slope": 0.0,
            "higher_target_profitable_rate_slope": 0.0,
            "higher_target_evidence_score": 0.0,
            "target_grid_note": "no_target_grid_column",
        }

    target_key = target_columns[0]
    buckets: dict[float, dict[str, float]] = {}
    for row in rows:
        target_value = _num(row.get(target_key), math.nan)
        if math.isnan(target_value):
            continue
        bucket = buckets.setdefault(
            target_value,
            {
                "count": 0.0,
                "net_sum": 0.0,
                "pf_sum": 0.0,
                "profitable_sum": 0.0,
            },
        )
        bucket["count"] += 1.0
        bucket["net_sum"] += _num(row.get("net_profit"), 0.0)
        bucket["pf_sum"] += _num(row.get("profit_factor"), 0.0)
        bucket["profitable_sum"] += 1.0 if _bool(row.get("profitable")) else 0.0

    if not buckets:
        return {
            "target_key": target_key,
            "target_grid_values": [],
            "target_grid_values_below_1r": [],
            "target_grid_has_below_1r": False,
            "top_target_value": top.get(target_key, ""),
            "top_target_is_grid_max": False,
            "higher_target_net_slope": 0.0,
            "higher_target_pf_slope": 0.0,
            "higher_target_profitable_rate_slope": 0.0,
            "higher_target_evidence_score": 0.0,
            "target_grid_note": "target_grid_unparseable",
        }

    values = sorted(buckets)
    below_1r_values = [value for value in values if value < MIN_TARGET_R_MULTIPLE]
    first = buckets[values[0]]
    last = buckets[values[-1]]
    first_count = max(first["count"], 1.0)
    last_count = max(last["count"], 1.0)
    first_net = first["net_sum"] / first_count
    last_net = last["net_sum"] / last_count
    first_pf = first["pf_sum"] / first_count
    last_pf = last["pf_sum"] / last_count
    first_profitable = first["profitable_sum"] / first_count
    last_profitable = last["profitable_sum"] / last_count
    top_target = _num(top.get(target_key), math.nan)
    top_is_max = not math.isnan(top_target) and top_target == values[-1] and len(values) > 1
    net_slope = last_net - first_net
    pf_slope = last_pf - first_pf
    profitable_slope = last_profitable - first_profitable
    evidence_score = (
        (1.0 if top_is_max else 0.0)
        + (1.0 if net_slope > 0 else 0.0)
        + (1.0 if pf_slope > 0 else 0.0)
        + (1.0 if profitable_slope >= 0 else 0.0)
    )
    return {
        "target_key": target_key,
        "target_grid_values": values,
        "target_grid_values_below_1r": below_1r_values,
        "target_grid_has_below_1r": bool(below_1r_values),
        "top_target_value": top_target if not math.isnan(top_target) else "",
        "top_target_is_grid_max": top_is_max,
        "higher_target_net_slope": net_slope,
        "higher_target_pf_slope": pf_slope,
        "higher_target_profitable_rate_slope": profitable_slope,
        "higher_target_evidence_score": evidence_score,
        "target_grid_note": "target_grid_evaluated",
    }


def _candidate_from_summary(summary_path: Path) -> SelectedRun | None:
    parts = _run_parts(summary_path)
    if parts is None:
        return None
    campaign_id, variant_id, run_id, run_dir = parts
    if run_id.startswith(("tp_widen", "tp_min_rr")):
        return None
    source_config_path = _source_config_for_run(run_dir)
    if source_config_path is None:
        return None
    summary = _load_json(summary_path)
    top = (summary.get("top_10_combinations") or [{}])[0] or {}
    target_signal = _target_grid_signal(run_dir, summary)
    benchmark_pass_combos = int(_num(summary.get("number_passing_benchmark"), 0))
    profitable_rate = _num(summary.get("percentage_profitable_iterations"), 0)
    profitable_combos = int(_num(summary.get("profitable_iterations"), 0))
    passing_rate = _num(summary.get("percentage_passing_benchmark"), 0)
    top_net = _num(top.get("net_profit"), -1e18)
    top_pf = _num(top.get("profit_factor"), 0)
    top_mar = _num(top.get("mar"), -1e18)
    top_tpy = _num(top.get("trades_per_year"), 0)
    core_passed = _bool(summary.get("meets_profitable_iteration_threshold")) and profitable_rate >= 0.70
    apex_violations = int(_num(summary.get("apex_rule_violating_iterations"), 0))
    # The target-specific fields come first because this batch is not a generic best-run rescue:
    # it should prefer variants whose own grid used sub-1R targets and hinted that larger
    # targets may help. The prepare step still enforces the hard eligibility rule.
    score = (
        1 if target_signal["target_grid_has_below_1r"] else 0,
        target_signal["higher_target_evidence_score"],
        1 if target_signal["top_target_is_grid_max"] else 0,
        target_signal["higher_target_net_slope"],
        target_signal["higher_target_pf_slope"],
        target_signal["higher_target_profitable_rate_slope"],
        1 if core_passed else 0,
        profitable_rate,
        passing_rate,
        benchmark_pass_combos,
        profitable_combos,
        top_net,
        top_pf,
        top_mar,
        top_tpy,
        -apex_violations,
    )
    metrics = {
        "core_passed": core_passed,
        "number_passing_benchmark": benchmark_pass_combos,
        "profitable_combo_rate": profitable_rate,
        "profitable_combos": profitable_combos,
        "percentage_passing_benchmark": passing_rate,
        "top_net_profit": top_net,
        "top_profit_factor": top_pf,
        "top_mar": top_mar,
        "top_trades_per_year": top_tpy,
        "top_trades": _num(top.get("total_trades"), 0),
        "top_failure_reason": top.get("failure_reason", ""),
        "core_summary_path": _display_path(summary_path),
        **target_signal,
    }
    return SelectedRun(
        campaign_id=campaign_id,
        variant_id=variant_id,
        run_id=run_id,
        run_dir=run_dir,
        summary_path=summary_path,
        source_config_path=source_config_path,
        score=score,
        metrics=metrics,
    )


def select_ranked_runs_by_campaign() -> dict[str, list[SelectedRun]]:
    grouped: dict[str, list[SelectedRun]] = {}
    for summary_path in sorted(
        (ROOT / "backtest-campaigns").glob("*/*/ES/*/limited_core_grid_test/core_grid_summary.json")
    ):
        candidate = _candidate_from_summary(summary_path)
        if candidate is None:
            continue
        grouped.setdefault(candidate.campaign_id, []).append(candidate)
    for candidates in grouped.values():
        candidates.sort(key=lambda item: item.score, reverse=True)
    return grouped


def select_best_runs() -> list[SelectedRun]:
    grouped = select_ranked_runs_by_campaign()
    return [grouped[key][0] for key in sorted(grouped) if grouped[key]]


def _floor_rr_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    numeric = _num(value, math.nan)
    if math.isnan(numeric):
        return value
    return round(max(numeric, MIN_TARGET_R_MULTIPLE), 4)


def _floor_rr_list(values: Any) -> Any:
    if not isinstance(values, list):
        return _floor_rr_value(values)
    floored = [_floor_rr_value(item) for item in values]
    out: list[Any] = []
    for item in floored:
        if item not in out:
            out.append(item)
    return out


def _ensure_mechanics_review(config: dict[str, Any], selected: SelectedRun) -> None:
    metadata = config.setdefault("research_metadata", {})
    metadata["mechanics_review_required"] = True
    metadata.setdefault("mechanics_review_version", TODAY)
    if isinstance(metadata.get("mechanics_review"), dict):
        metadata["mechanics_review"]["pre_test_decision"] = "approve_for_testing"
        metadata["mechanics_review"]["target_exit_rationale"] = (
            "User-authorized minimum-RR rescue: entry and stop mechanics are unchanged, "
            f"while any existing target_r_multiple below {MIN_TARGET_R_MULTIPLE:.1f}R is raised to "
            f"{MIN_TARGET_R_MULTIPLE:.1f}R. Targets already at or above 1.0R are not changed."
        )
    else:
        mechanic = metadata.get("mechanic") or metadata.get("edge_thesis") or config.get("strategy_name")
        metadata["mechanics_review"] = {
            "mechanic_expresses_edge": (
                f"This user-authorized minimum-RR rescue preserves the existing "
                f"{selected.campaign_id}/{selected.variant_id} entry mechanic: {mechanic}."
            ),
            "entry_logic_rationale": (
                "Entry logic is unchanged from the selected tested source run; no signal, direction, "
                "time-window, filter, data, or execution rule is altered."
            ),
            "stop_loss_rationale": (
                "Stop-loss logic and parameter space are unchanged. This rescue is isolated to "
                "a take-profit RR floor so the failure/success attribution remains auditable."
            ),
            "target_exit_rationale": (
                f"Only target_r_multiple values below {MIN_TARGET_R_MULTIPLE:.1f}R are raised to "
                f"{MIN_TARGET_R_MULTIPLE:.1f}R. Sub-1R variants can have their gross edge consumed "
                "by slippage, commissions, and exchange fees; this tests whether the same signal "
                "needs at least 1R payoff distance to survive costs."
            ),
            "profitability_rationale": (
                "If the original edge produces directional follow-through beyond a sub-1R target, "
                "a 1R floor should improve average win size without changing signal causality."
            ),
            "known_failure_modes": (
                "A 1R floor may reduce win rate, increase holding time, miss too many exits, "
                "or simply expose that the signal has no sustained follow-through; all normal staged "
                "gates still apply."
            ),
            "pre_test_decision": "approve_for_testing",
        }
    metadata["user_authorized_additional_rescue"] = {
        "id": RESCUE_ID,
        "created_at": f"{TODAY}T00:00:00",
        "source_campaign_id": selected.campaign_id,
        "source_variant_id": selected.variant_id,
        "source_run_id": selected.run_id,
        "source_config_path": _display_path(selected.source_config_path),
        "selection_rule": (
            "one existing tested run per campaign, preferring variants whose limited-core target grid "
            "used sub-1R target values and showed stronger performance at larger targets; candidates "
            "without any sub-1R target_r_multiple are skipped"
        ),
        "allowed_change_scope": "target_r_multiple_floor_only",
        "minimum_target_r_multiple": MIN_TARGET_R_MULTIPLE,
        "target_selection_metrics": {
            key: selected.metrics.get(key)
            for key in (
                "target_key",
                "target_grid_values",
                "target_grid_values_below_1r",
                "target_grid_has_below_1r",
                "top_target_value",
                "top_target_is_grid_max",
                "higher_target_net_slope",
                "higher_target_pf_slope",
                "higher_target_profitable_rate_slope",
                "higher_target_evidence_score",
                "target_grid_note",
            )
        },
        "normal_rescue_policy_override": True,
    }


def _floor_target_rr_tree(value: Any, *, path: str = "config") -> tuple[Any, list[dict[str, Any]]]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        changes: list[dict[str, Any]] = []
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key).endswith("target_r_multiple"):
                new_item = _floor_rr_list(item)
                out[key] = new_item
                if new_item != item:
                    changes.append({"path": child_path, "old": item, "new": new_item})
                continue
            new_item, child_changes = _floor_target_rr_tree(item, path=child_path)
            out[key] = new_item
            changes.extend(child_changes)
        return out, changes
    if isinstance(value, list):
        out_list: list[Any] = []
        changes: list[dict[str, Any]] = []
        for idx, item in enumerate(value):
            new_item, child_changes = _floor_target_rr_tree(item, path=f"{path}[{idx}]")
            out_list.append(new_item)
            changes.extend(child_changes)
        return out_list, changes
    return value, []


def prepare_rescue(selected: SelectedRun, *, overwrite: bool = False) -> Path:
    with selected.source_config_path.open(encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    config["campaign_id"] = selected.campaign_id
    config["variant_id"] = selected.variant_id
    config["test_run_id"] = RUN_ID
    config.setdefault("strategy_name", selected.campaign_id)

    config, changed = _floor_target_rr_tree(config)

    if not changed:
        raise ValueError(
            f"No target_r_multiple below {MIN_TARGET_R_MULTIPLE:.1f} found in "
            f"{_display_path(selected.source_config_path)} for "
            f"{selected.campaign_id}/{selected.variant_id}/{selected.run_id}"
        )

    _ensure_mechanics_review(config, selected)
    config["research_metadata"]["user_authorized_additional_rescue"]["target_changes"] = changed

    out_dir = (
        ROOT
        / "campaigns"
        / selected.campaign_id
        / "rescue_attempts"
        / RESCUE_ID
        / selected.variant_id
    )
    if out_dir.exists() and not overwrite:
        return out_dir / "config.yaml"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_dir = selected.source_config_path.parent
    modules_src = source_dir / "strategy_modules"
    modules_dst = out_dir / "strategy_modules"
    if modules_src.exists():
        if modules_dst.exists():
            shutil.rmtree(modules_dst)
        shutil.copytree(modules_src, modules_dst)
    readme_src = source_dir / "README.md"
    readme_text = ""
    if readme_src.exists():
        readme_text = readme_src.read_text(encoding="utf-8")
    readme_text += (
        f"\n\n## {RESCUE_ID}\n\n"
        f"User-authorized additional rescue created on {TODAY}. Source run: "
        f"`{selected.campaign_id}/{selected.variant_id}/{selected.run_id}`. "
        f"Only target_r_multiple values below {MIN_TARGET_R_MULTIPLE:.1f}R were raised to "
        f"{MIN_TARGET_R_MULTIPLE:.1f}R; entry, stop, data, costs, fills, sessions, "
        "and validation gates are unchanged.\n"
    )
    (out_dir / "README.md").write_text(readme_text.lstrip(), encoding="utf-8")
    with (out_dir / "config.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False, width=1000)
    return out_dir / "config.yaml"


def write_queue(selected: list[SelectedRun], config_paths: list[Path], skipped: list[dict[str, Any]]) -> None:
    artifact_dir = ROOT / "research_artifacts"
    artifact_dir.mkdir(exist_ok=True)
    stamp = TODAY.replace("-", "")
    csv_path = artifact_dir / f"tp_min_rr_best_core_rescue_queue_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [
            "campaign_id",
            "variant_id",
            "source_run_id",
            "source_config_path",
            "new_config_path",
            "core_passed",
            "number_passing_benchmark",
            "profitable_combo_rate",
            "top_net_profit",
            "top_profit_factor",
            "top_mar",
            "top_trades_per_year",
            "top_failure_reason",
            "target_key",
            "target_grid_values",
            "target_grid_values_below_1r",
            "target_grid_has_below_1r",
            "top_target_value",
            "top_target_is_grid_max",
            "higher_target_net_slope",
            "higher_target_pf_slope",
            "higher_target_profitable_rate_slope",
            "higher_target_evidence_score",
            "target_grid_note",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for item, config_path in zip(selected, config_paths):
            row = {
                "campaign_id": item.campaign_id,
                "variant_id": item.variant_id,
                "source_run_id": item.run_id,
                "source_config_path": _display_path(item.source_config_path),
                "new_config_path": _display_path(config_path),
            }
            for key in fieldnames:
                if key in item.metrics:
                    row[key] = item.metrics.get(key)
            writer.writerow(row)
    json_path = artifact_dir / f"tp_min_rr_best_core_rescue_queue_{stamp}.json"
    json_path.write_text(
        json.dumps(
            {
                "prepared_at": datetime.now().isoformat(timespec="seconds"),
                "rescue_id": RESCUE_ID,
                "run_id": RUN_ID,
                "minimum_target_r_multiple": MIN_TARGET_R_MULTIPLE,
                "selected": [
                    {
                        "campaign_id": item.campaign_id,
                        "variant_id": item.variant_id,
                        "source_run_id": item.run_id,
                        "source_config_path": _display_path(item.source_config_path),
                        "new_config_path": _display_path(config_path),
                        "metrics": item.metrics,
                    }
                    for item, config_path in zip(selected, config_paths)
                ],
                "skipped": skipped,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    md_path = artifact_dir / f"tp_min_rr_best_core_rescue_plan_{stamp}.md"
    md_path.write_text(
        "\n".join(
            [
                f"# TP Minimum-RR Best-Core Rescue Plan - {TODAY}",
                "",
                "Status: prepared",
                "",
                f"Campaigns selected: {len(selected)}",
                f"Campaigns skipped: {len(skipped)}",
                "",
                "Selection rule: one existing tested run per campaign, prioritizing variants whose limited-core target grid contained sub-1R targets and showed evidence that larger targets helped. Campaigns with no sub-1R target_r_multiple are skipped.",
                "",
                f"Rescue scope: minimum-RR floor only. target_r_multiple values below {MIN_TARGET_R_MULTIPLE:.1f}R are raised to {MIN_TARGET_R_MULTIPLE:.1f}R; 1.0R+ targets are unchanged. Entry, stop, data, costs, fills, sessions, and validation gates are unchanged.",
                "",
                f"Queue CSV: `{csv_path.relative_to(ROOT)}`",
                f"Queue JSON: `{json_path.relative_to(ROOT)}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _run_output_dir(config_path: Path) -> Path | None:
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    campaign_id = config.get("campaign_id")
    variant_id = config.get("variant_id")
    symbol = config.get("symbol", "ES")
    run_id = config.get("test_run_id")
    if not campaign_id or not variant_id or not run_id:
        return None
    return ROOT / "backtest-campaigns" / str(campaign_id) / str(variant_id) / str(symbol) / str(run_id)


def _tail(text: str, *, lines: int = 80) -> str:
    parts = text.splitlines()
    if len(parts) <= lines:
        return text
    return "\n".join(["... output truncated ...", *parts[-lines:]]) + "\n"


def run_configs(
    config_paths: list[Path],
    *,
    limit: int | None = None,
    skip_existing: bool = False,
    staged_timeout_seconds: int = DEFAULT_STAGED_TIMEOUT_SECONDS,
) -> int:
    selected = config_paths[:limit] if limit else config_paths
    failures = 0
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    for idx, config_path in enumerate(selected, start=1):
        out_dir = _run_output_dir(config_path)
        if skip_existing and out_dir and (out_dir / "campaign_test_summary.json").exists():
            print(f"[{idx}/{len(selected)}] skip existing {out_dir.relative_to(ROOT)}", flush=True)
            continue
        rel = config_path.relative_to(ROOT)
        print(f"[{idx}/{len(selected)}] preflight {rel}", flush=True)
        preflight = subprocess.run(
            [
                sys.executable,
                "-m",
                "research.preflight",
                "--skip-tests",
                "--config",
                str(rel),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if preflight.returncode != 0:
            failures += 1
            print(_tail(preflight.stdout), flush=True)
            continue
        print(f"[{idx}/{len(selected)}] staged {rel}", flush=True)
        try:
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alphaquest.run_campaign_stages",
                    "--config",
                    str(rel),
                    "--fast-runtime-defaults",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=staged_timeout_seconds if staged_timeout_seconds > 0 else None,
            )
        except subprocess.TimeoutExpired as exc:
            failures += 1
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            print(_tail(output), flush=True)
            print(
                f"[{idx}/{len(selected)}] staged timeout after {staged_timeout_seconds}s {rel}",
                flush=True,
            )
            continue
        print(_tail(run.stdout), flush=True)
        if run.returncode != 0:
            failures += 1
    return failures


def _summary_scalar(summary: dict[str, Any], path: str, default: Any = "") -> Any:
    cur: Any = summary
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    return default if cur is None else cur


def _stage_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stages = summary.get("stages") or []
    if isinstance(stages, dict):
        return {str(key): value for key, value in stages.items() if isinstance(value, dict)}
    if isinstance(stages, list):
        return {
            str(stage.get("stage")): stage
            for stage in stages
            if isinstance(stage, dict) and stage.get("stage")
        }
    return {}


def _terminal_stage(summary: dict[str, Any]) -> tuple[str, str, str]:
    stages = summary.get("stages") or []
    if not isinstance(stages, list):
        stages = list(_stage_map(summary).values())
    terminal: dict[str, Any] | None = None
    for stage in stages:
        if isinstance(stage, dict) and stage.get("status") == "failed":
            terminal = stage
            break
    if terminal is None:
        non_skipped = [
            stage
            for stage in stages
            if isinstance(stage, dict) and stage.get("status") not in {None, "skipped"}
        ]
        terminal = non_skipped[-1] if non_skipped else None
    if terminal is None:
        return "", "", ""
    failed_criteria = [
        f"{item.get('metric')}={item.get('actual')} expected {item.get('expected')}"
        for item in terminal.get("criteria", [])
        if isinstance(item, dict) and not item.get("passed", False)
    ]
    if failed_criteria:
        failure_reason = f"{terminal.get('stage')} failed: " + "; ".join(failed_criteria)
    else:
        failure_reason = terminal.get("skip_reason") or ""
    return str(terminal.get("stage") or ""), str(terminal.get("status") or ""), failure_reason


def _stage_scalar(stages: dict[str, dict[str, Any]], stage: str, path: str, default: Any = "") -> Any:
    return _summary_scalar(stages.get(stage) or {}, path, default)


def collect_results(config_paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config_path in config_paths:
        out_dir = _run_output_dir(config_path)
        if out_dir is None:
            continue
        summary_path = out_dir / "campaign_test_summary.json"
        core_path = out_dir / "limited_core_grid_test" / "core_grid_summary.json"
        summary: dict[str, Any] = {}
        core: dict[str, Any] = {}
        if summary_path.exists():
            summary = _load_json(summary_path)
        if core_path.exists():
            core = _load_json(core_path)
        stages = _stage_map(summary)
        terminal_stage, terminal_status, failure_reason = _terminal_stage(summary)
        top = (core.get("top_10_combinations") or [{}])[0] or {}
        row = {
            "campaign_id": _summary_scalar(summary, "campaign_id", out_dir.parts[-5]),
            "variant_id": _summary_scalar(summary, "variant_id", out_dir.parts[-4]),
            "symbol": _summary_scalar(summary, "symbol", "ES"),
            "timeframe": _summary_scalar(summary, "timeframe", ""),
            "test_run_id": _summary_scalar(summary, "test_run_id", RUN_ID),
            "decision": "PASS" if _bool(_summary_scalar(summary, "passed", False)) else "FAIL",
            "passed": _summary_scalar(summary, "passed", False),
            "terminal_stage": terminal_stage,
            "terminal_status": terminal_status,
            "failure_reason": failure_reason,
            "source_config_path": _display_path(config_path),
            "effective_config_path": _summary_scalar(summary, "effective_config_path", ""),
            "output_dir": _display_path(out_dir),
            "dataset_id": _summary_scalar(summary, "dataset_id", ""),
            "core_status": _stage_scalar(stages, "limited_core_grid_test", "status", ""),
            "core_expected_combinations": core.get("expected_combinations", ""),
            "core_total_combinations": core.get("total_combinations_tested", ""),
            "core_number_passing_benchmark": core.get("number_passing_benchmark", ""),
            "core_percentage_passing_benchmark": core.get("percentage_passing_benchmark", ""),
            "core_profitable_iterations": core.get("profitable_iterations", ""),
            "core_percentage_profitable_iterations": core.get("percentage_profitable_iterations", ""),
            "core_apex_rule_violating_iterations": core.get("apex_rule_violating_iterations", ""),
            "core_top_net_profit": top.get("net_profit", ""),
            "core_top_profit_factor": top.get("profit_factor", ""),
            "core_top_mar": top.get("mar", ""),
            "core_top_trades_per_year": top.get("trades_per_year", ""),
            "core_top_total_trades": top.get("total_trades", ""),
            "core_top_failure_reason": top.get("failure_reason", ""),
            "limited_monkey_status": _stage_scalar(stages, "limited_monkey_test", "status", ""),
            "wfa_status": _stage_scalar(stages, "walk_forward_analysis", "status", ""),
            "wfa_oos_net_profit": _stage_scalar(stages, "walk_forward_analysis", "summary.stitched_oos_metrics.net_profit", ""),
            "wfa_oos_profit_factor": _stage_scalar(stages, "walk_forward_analysis", "summary.stitched_oos_metrics.profit_factor", ""),
            "wfa_oos_mar": _stage_scalar(stages, "walk_forward_analysis", "summary.stitched_oos_metrics.mar", ""),
            "wfa_oos_trades_per_year": _stage_scalar(stages, "walk_forward_analysis", "summary.stitched_oos_metrics.trades_per_year", ""),
            "wfa_oos_monte_carlo_status": _stage_scalar(stages, "wfa_oos_monte_carlo", "status", ""),
            "mc_probability_profit_before_drawdown": _stage_scalar(stages, "wfa_oos_monte_carlo", "summary.probability_profit_before_drawdown", ""),
            "mc_probability_account_breach": _stage_scalar(stages, "wfa_oos_monte_carlo", "summary.probability_account_breach", ""),
            "mc_probability_payout_eligible": _stage_scalar(stages, "wfa_oos_monte_carlo", "summary.probability_payout_eligible", ""),
            "fixed_config_core_trade_log": (
                _display_path(out_dir / "limited_core_grid_test" / "fixed_config_core_trade_log.csv")
                if (out_dir / "limited_core_grid_test" / "fixed_config_core_trade_log.csv").exists()
                else ""
            ),
        }
        rows.append(row)
    return rows


def write_results(rows: list[dict[str, Any]]) -> None:
    artifact_dir = ROOT / "research_artifacts"
    artifact_dir.mkdir(exist_ok=True)
    stamp = TODAY.replace("-", "")
    skipped_count = ""
    queue_path = artifact_dir / f"tp_min_rr_best_core_rescue_queue_{stamp}.json"
    if queue_path.exists():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            skipped_count = str(len(queue.get("skipped") or []))
        except Exception:
            skipped_count = ""
    csv_path = artifact_dir / f"tp_min_rr_best_core_rescue_results_{stamp}.csv"
    fieldnames = [
        "campaign_id",
        "variant_id",
        "symbol",
        "timeframe",
        "test_run_id",
        "decision",
        "passed",
        "terminal_stage",
        "terminal_status",
        "failure_reason",
        "source_config_path",
        "effective_config_path",
        "output_dir",
        "dataset_id",
        "core_status",
        "core_expected_combinations",
        "core_total_combinations",
        "core_number_passing_benchmark",
        "core_percentage_passing_benchmark",
        "core_profitable_iterations",
        "core_percentage_profitable_iterations",
        "core_apex_rule_violating_iterations",
        "core_top_net_profit",
        "core_top_profit_factor",
        "core_top_mar",
        "core_top_trades_per_year",
        "core_top_total_trades",
        "core_top_failure_reason",
        "limited_monkey_status",
        "wfa_status",
        "wfa_oos_net_profit",
        "wfa_oos_profit_factor",
        "wfa_oos_mar",
        "wfa_oos_trades_per_year",
        "wfa_oos_monte_carlo_status",
        "mc_probability_profit_before_drawdown",
        "mc_probability_account_breach",
        "mc_probability_payout_eligible",
        "fixed_config_core_trade_log",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    json_path = artifact_dir / f"tp_min_rr_best_core_rescue_results_{stamp}.json"
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    stage_counts: dict[str, int] = {}
    passes = 0
    for row in rows:
        stage = str(row.get("terminal_stage") or "not_run")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        if _bool(row.get("passed")):
            passes += 1
    strongest = sorted(
        rows,
        key=lambda item: (
            _num(item.get("wfa_oos_profit_factor"), 0),
            _num(item.get("wfa_oos_mar"), -1e18),
            _num(item.get("core_percentage_profitable_iterations"), 0),
            _num(item.get("core_top_net_profit"), -1e18),
        ),
        reverse=True,
    )[:10]
    md_lines = [
        f"# TP Minimum-RR Best-Core Rescue Batch - {TODAY}",
        "",
        f"- Batch id: `{RESCUE_ID}_user_authorized_{stamp}`",
        f"- Runs summarized: {len(rows)}",
        f"- Campaigns skipped by minimum-RR rule: {skipped_count or 'unknown'}",
        f"- Full-stage passes: {passes}",
        f"- Fixed-config core trade logs found in result paths: {sum(1 for row in rows if row.get('fixed_config_core_trade_log'))}",
        "",
        "## Terminal Stage Counts",
        "",
    ]
    for stage, count in sorted(stage_counts.items(), key=lambda item: (-item[1], item[0])):
        md_lines.append(f"- `{stage}`: {count}")
    md_lines.extend(
        [
            "",
            "## Strongest Partial Results",
            "",
            "| campaign | variant | terminal | core profitable | core passing | WFA PF | WFA MAR | WFA trades/yr | MC pass chance |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in strongest:
        md_lines.append(
            "| {campaign_id} | {variant_id} | {terminal_stage} | {core_percentage_profitable_iterations} | "
            "{core_number_passing_benchmark}/{core_total_combinations} | {wfa_oos_profit_factor} | "
            "{wfa_oos_mar} | {wfa_oos_trades_per_year} | {mc_probability_profit_before_drawdown} |".format(**row)
        )
    md_lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "NEEDS MANUAL REVIEW. At least one minimum-RR rescue reached a full staged pass; "
                "review candidate reports and chart/trade logs before any incubation."
                if passes
                else "FAIL. This user-authorized minimum-RR rescue produced no full staged pass and no new candidate strategy report."
            ),
            "",
            f"- CSV: `{csv_path.relative_to(ROOT)}`",
            f"- JSON: `{json_path.relative_to(ROOT)}`",
            "",
        ]
    )
    (artifact_dir / f"tp_min_rr_best_core_rescue_results_{stamp}.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )


def append_ledger(rows: list[dict[str, Any]]) -> None:
    ledger_path = ROOT / "research_ledger.csv"
    fieldnames = [
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
    ]
    existing: list[dict[str, Any]] = []
    if ledger_path.exists():
        with ledger_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("timestamp") == TODAY and row.get("rescue_attempt") == RESCUE_ID:
                    continue
                existing.append(row)
    with ledger_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
        for row in rows:
            writer.writerow(
                {
                    "timestamp": TODAY,
                    "campaign_id": row.get("campaign_id", ""),
                    "variant_id": row.get("variant_id", ""),
                    "instrument": row.get("symbol", "ES"),
                    "timeframe": row.get("timeframe", ""),
                    "edge": f"{RESCUE_ID}: minimum target RR rescue",
                    "variant_mechanic": "Selected existing tested variant with sub-1R target exposure; entry and stop unchanged.",
                    "parameter_space": f"target_r_multiple floored at {MIN_TARGET_R_MULTIPLE:.1f}R; other parameters unchanged",
                    "data_scope": "local_only",
                    "config_path": row.get("source_config_path", ""),
                    "report_path": str(row.get("output_dir", "")) + "/campaign_test_summary.json",
                    "stage": row.get("terminal_stage", ""),
                    "result": "passed" if _bool(row.get("passed")) else "failed",
                    "decision": row.get("decision", "FAIL") or "FAIL",
                    "failure_reason": row.get("failure_reason", ""),
                    "rescue_attempt": RESCUE_ID,
                }
            )


def update_methodology_audit(rows: list[dict[str, Any]]) -> None:
    audit_path = ROOT / "methodology_audit.md"
    text = audit_path.read_text(encoding="utf-8") if audit_path.exists() else "# Methodology Audit\n"
    skipped_count = "unknown"
    queue_path = ROOT / "research_artifacts" / f"tp_min_rr_best_core_rescue_queue_{TODAY.replace('-', '')}.json"
    if queue_path.exists():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            skipped_count = str(len(queue.get("skipped") or []))
        except Exception:
            skipped_count = "unknown"
    passes = sum(1 for row in rows if _bool(row.get("passed")))
    stage_counts: dict[str, int] = {}
    for row in rows:
        stage = str(row.get("terminal_stage") or "not_run")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    block = [
        "",
        f"## TP Minimum-RR Rescue Batch - {TODAY}",
        "",
        f"- Scope: one selected original/rescue variant per eligible campaign, selected from existing tested runs; target_r_multiple values below {MIN_TARGET_R_MULTIPLE:.1f}R were raised to {MIN_TARGET_R_MULTIPLE:.1f}R only.",
        "- Rationale: user-authorized rule that no tested TP should be below 1.0 reward:risk because low-RR variants may lose too much gross PnL to slippage, commissions, and fees.",
        "- Controls: entry, stop, data, session, costs, fill assumptions, and staged gates unchanged.",
        f"- Runs summarized: {len(rows)}",
        f"- Campaigns skipped by minimum-RR rule: {skipped_count}",
        f"- Full-stage passes: {passes}",
        "- Terminal stage counts: "
        + ", ".join(f"{stage}={count}" for stage, count in sorted(stage_counts.items())),
        "- Result artifact: `research_artifacts/tp_min_rr_best_core_rescue_results_20260619.md`",
    ]
    heading = f"## TP Minimum-RR Rescue Batch - {TODAY}"
    if heading in text:
        before = text.split(heading, 1)[0].rstrip()
        audit_path.write_text(before + "\n" + "\n".join(block) + "\n", encoding="utf-8")
    else:
        audit_path.write_text(text.rstrip() + "\n" + "\n".join(block) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-existing-results", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--append-ledger", action="store_true")
    parser.add_argument(
        "--staged-timeout-seconds",
        type=int,
        default=DEFAULT_STAGED_TIMEOUT_SECONDS,
        help="Per-config staged run timeout. Use 0 to disable.",
    )
    args = parser.parse_args()

    config_paths: list[Path] = []
    kept: list[SelectedRun] = []
    skipped: list[dict[str, Any]] = []
    ranked_by_campaign = select_ranked_runs_by_campaign()
    for campaign_id in sorted(ranked_by_campaign):
        errors: list[dict[str, str]] = []
        for item in ranked_by_campaign[campaign_id]:
            try:
                config_path = prepare_rescue(item, overwrite=args.overwrite)
            except ValueError as exc:
                errors.append(
                    {
                        "variant_id": item.variant_id,
                        "source_run_id": item.run_id,
                        "reason": str(exc),
                    }
                )
                continue
            kept.append(item)
            config_paths.append(config_path)
            break
        else:
            skipped.append(
                {
                    "campaign_id": campaign_id,
                    "reason": f"No target_r_multiple below {MIN_TARGET_R_MULTIPLE:.1f} found in any tested run for this campaign.",
                    "attempted": errors[:10],
                }
            )
    write_queue(kept, config_paths, skipped)
    print(f"selected_campaigns={len(kept)}")
    print(f"skipped_campaigns={len(skipped)}")
    for item, config_path in zip(kept[:10], config_paths[:10]):
        print(
            f"{item.campaign_id},{item.variant_id},{item.run_id},"
            f"target_key={item.metrics['target_key']},"
            f"target_score={item.metrics['higher_target_evidence_score']},"
            f"prof_rate={item.metrics['profitable_combo_rate']},"
            f"top_net={item.metrics['top_net_profit']},config={config_path.relative_to(ROOT)}"
        )
    if len(kept) > 10:
        print(f"... {len(kept) - 10} more")

    exit_code = 0
    if args.run:
        failures = run_configs(
            config_paths,
            limit=args.limit,
            skip_existing=args.skip_existing_results,
            staged_timeout_seconds=args.staged_timeout_seconds,
        )
        print(f"run_failures={failures}")
        if failures:
            exit_code = 1

    if args.summarize:
        rows = collect_results(config_paths[: args.limit] if args.limit else config_paths)
        write_results(rows)
        update_methodology_audit(rows)
        if args.append_ledger:
            append_ledger(rows)
        print(f"summarized_runs={len(rows)}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
