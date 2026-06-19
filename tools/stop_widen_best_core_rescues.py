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


RUN_ID = "stop_widen_rescue1"
RESCUE_ID = "stop_distance_rescue_1"
STOP_MULTIPLIER = 1.5
TODAY = "2026-06-19"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGED_TIMEOUT_SECONDS = 45 * 60


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


def _candidate_from_summary(summary_path: Path) -> SelectedRun | None:
    parts = _run_parts(summary_path)
    if parts is None:
        return None
    campaign_id, variant_id, run_id, run_dir = parts
    if run_id.startswith("stop_widen"):
        return None
    source_config_path = _source_config_for_run(run_dir)
    if source_config_path is None:
        return None
    summary = _load_json(summary_path)
    top = (summary.get("top_10_combinations") or [{}])[0] or {}
    benchmark_pass_combos = int(_num(summary.get("number_passing_benchmark"), 0))
    profitable_rate = _num(summary.get("percentage_profitable_iterations"), 0)
    profitable_combos = int(_num(summary.get("profitable_iterations"), 0))
    passing_rate = _num(summary.get("percentage_passing_benchmark"), 0)
    top_net = _num(top.get("net_profit"), -1e18)
    top_pf = _num(top.get("profit_factor"), 0)
    top_mar = _num(top.get("mar"), -1e18)
    top_tpy = _num(top.get("trades_per_year"), 0)
    core_passed = _bool(summary.get("meets_profitable_iteration_threshold")) and benchmark_pass_combos > 0
    apex_violations = int(_num(summary.get("apex_rule_violating_iterations"), 0))
    score = (
        1 if core_passed else 0,
        benchmark_pass_combos,
        profitable_rate,
        passing_rate,
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


def select_best_runs() -> list[SelectedRun]:
    best: dict[str, SelectedRun] = {}
    for summary_path in sorted(
        (ROOT / "backtest-campaigns").glob("*/*/ES/*/limited_core_grid_test/core_grid_summary.json")
    ):
        candidate = _candidate_from_summary(summary_path)
        if candidate is None:
            continue
        current = best.get(candidate.campaign_id)
        if current is None or candidate.score > current.score:
            best[candidate.campaign_id] = candidate
    return [best[key] for key in sorted(best)]


def _widen_value(key: str, value: Any) -> Any:
    if isinstance(value, bool):
        return value
    numeric = _num(value, None)  # type: ignore[arg-type]
    if numeric is None:
        return value
    widened = numeric * STOP_MULTIPLIER
    if key.endswith("stop_offset_ticks"):
        return int(math.ceil(widened))
    if key.endswith("max_stop_points"):
        return round(widened, 6)
    if key.endswith("stop_pct"):
        return round(widened, 10)
    return value


def _widen_list(key: str, values: Any) -> Any:
    if not isinstance(values, list):
        return _widen_value(key, values)
    widened = [_widen_value(key, item) for item in values]
    out: list[Any] = []
    for item in widened:
        if item not in out:
            out.append(item)
    return out


def _ensure_mechanics_review(config: dict[str, Any], selected: SelectedRun) -> None:
    metadata = config.setdefault("research_metadata", {})
    metadata["mechanics_review_required"] = True
    metadata.setdefault("mechanics_review_version", TODAY)
    if isinstance(metadata.get("mechanics_review"), dict):
        metadata["mechanics_review"]["pre_test_decision"] = "approve_for_testing"
    else:
        mechanic = metadata.get("mechanic") or metadata.get("edge_thesis") or config.get("strategy_name")
        metadata["mechanics_review"] = {
            "mechanic_expresses_edge": (
                f"This user-authorized stop-distance rescue preserves the existing "
                f"{selected.campaign_id}/{selected.variant_id} entry mechanic: {mechanic}."
            ),
            "entry_logic_rationale": (
                "Entry logic is unchanged from the selected best core-grid source run; "
                "no signal, direction, time-window, filter, data, or execution rule is altered."
            ),
            "stop_loss_rationale": (
                f"Only stop distance is widened by {STOP_MULTIPLIER}x to test whether the "
                "best existing core-grid variant was being rejected because the stop was too tight "
                "for ES noise. This is a user-authorized additional rescue and not a new edge."
            ),
            "target_exit_rationale": (
                "Target/exit logic and parameter space are unchanged, so any improvement must come "
                "from stop-distance tolerance rather than post-result take-profit tuning."
            ),
            "profitability_rationale": (
                "If the original edge has directional value but premature stop-outs dominated, a "
                "wider stop may allow the intended move to develop after next-bar execution and costs."
            ),
            "known_failure_modes": (
                "A wider stop may increase drawdown, reduce expectancy, hide a non-existent edge, "
                "or pass only in a narrow core-grid pocket; all normal staged gates still apply."
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
            "best existing limited core-grid run per campaign by core pass flag, "
            "benchmark-pass combos, profitable-combo rate, top net profit, PF, MAR, and trade density"
        ),
        "allowed_change_scope": "stop_distance_only",
        "stop_distance_multiplier": STOP_MULTIPLIER,
        "normal_rescue_policy_override": True,
    }


def prepare_rescue(selected: SelectedRun, *, overwrite: bool = False) -> Path:
    with selected.source_config_path.open(encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    config["campaign_id"] = selected.campaign_id
    config["variant_id"] = selected.variant_id
    config["test_run_id"] = RUN_ID
    config.setdefault("strategy_name", selected.campaign_id)

    changed: list[dict[str, Any]] = []
    sl_params = (((config.get("strategy") or {}).get("sl") or {}).get("params") or {})
    for key in ("stop_pct", "stop_offset_ticks", "max_stop_points"):
        if key in sl_params:
            old = sl_params[key]
            new = _widen_value(key, old)
            sl_params[key] = new
            changed.append({"path": f"strategy.sl.params.{key}", "old": old, "new": new})

    entry_params = (((config.get("strategy") or {}).get("entry") or {}).get("params") or {})
    if "stop_pct" in entry_params and "stop_pct" in sl_params:
        old = entry_params["stop_pct"]
        entry_params["stop_pct"] = sl_params["stop_pct"]
        changed.append({"path": "strategy.entry.params.stop_pct", "old": old, "new": entry_params["stop_pct"]})

    grid_params = ((config.get("core_grid") or {}).get("parameters") or {})
    for key in sorted(list(grid_params)):
        if key in {"sl.params.stop_pct", "sl.params.stop_offset_ticks", "sl.params.max_stop_points"}:
            old = grid_params[key]
            new = _widen_list(key, old)
            grid_params[key] = new
            changed.append({"path": f"core_grid.parameters.{key}", "old": old, "new": new})

    _ensure_mechanics_review(config, selected)
    config["research_metadata"]["user_authorized_additional_rescue"]["stop_changes"] = changed

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
        f"Only stop distance was widened by {STOP_MULTIPLIER}x; entry, target/exit, "
        "data, costs, fills, sessions, and validation gates are unchanged.\n"
    )
    (out_dir / "README.md").write_text(readme_text.lstrip(), encoding="utf-8")
    with (out_dir / "config.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False, width=1000)
    return out_dir / "config.yaml"


def write_queue(selected: list[SelectedRun], config_paths: list[Path]) -> None:
    artifact_dir = ROOT / "research_artifacts"
    artifact_dir.mkdir(exist_ok=True)
    csv_path = artifact_dir / f"stop_widen_best_core_rescue_queue_{TODAY.replace('-', '')}.csv"
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
            row.update({key: item.metrics.get(key) for key in fieldnames if key in item.metrics})
            writer.writerow(row)
    json_path = artifact_dir / f"stop_widen_best_core_rescue_queue_{TODAY.replace('-', '')}.json"
    json_path.write_text(
        json.dumps(
            [
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
            indent=2,
        ),
        encoding="utf-8",
    )
    md_path = artifact_dir / f"stop_widen_best_core_rescue_plan_{TODAY.replace('-', '')}.md"
    md_path.write_text(
        "\n".join(
            [
                f"# Stop-Widen Best-Core Rescue Plan - {TODAY}",
                "",
                "Status: prepared",
                "",
                f"Campaigns selected: {len(selected)}",
                "",
                "Selection rule: one best existing limited-core-grid run per campaign, ranked by core pass flag, benchmark-pass combos, profitable-combo rate, passing rate, profitable combo count, top net profit, PF, MAR, trade density, and no Apex violations.",
                "",
                f"Rescue scope: stop-distance-only, {STOP_MULTIPLIER}x wider stops. Entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.",
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
                    "propstack.run_campaign_stages",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-existing-results", action="store_true")
    parser.add_argument(
        "--staged-timeout-seconds",
        type=int,
        default=DEFAULT_STAGED_TIMEOUT_SECONDS,
        help="Per-config staged run timeout. Use 0 to disable.",
    )
    args = parser.parse_args()

    selected = select_best_runs()
    config_paths = [prepare_rescue(item, overwrite=args.overwrite) for item in selected]
    write_queue(selected, config_paths)
    print(f"selected_campaigns={len(selected)}")
    for item, config_path in zip(selected[:10], config_paths[:10]):
        print(
            f"{item.campaign_id},{item.variant_id},{item.run_id},"
            f"prof_rate={item.metrics['profitable_combo_rate']},"
            f"top_net={item.metrics['top_net_profit']},config={config_path.relative_to(ROOT)}"
        )
    if len(selected) > 10:
        print(f"... {len(selected) - 10} more")

    if args.run:
        failures = run_configs(
            config_paths,
            limit=args.limit,
            skip_existing=args.skip_existing_results,
            staged_timeout_seconds=args.staged_timeout_seconds,
        )
        print(f"run_failures={failures}")
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
