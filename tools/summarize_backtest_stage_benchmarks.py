from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from alphaquest.research import campaign_stages as cs


DEFAULT_OUT_STEM = Path("research_artifacts/backtest_campaign_stage_benchmarks")
STATUS_COLUMNS = ("passed", "failed", "skipped", "error", "other")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize backtest-campaigns stage outcomes grouped by the stored benchmark criteria."
    )
    parser.add_argument("--root", type=Path, default=Path("backtest-campaigns"))
    parser.add_argument("--out-stem", type=Path, default=_dated_default_stem())
    args = parser.parse_args()

    rows = collect_stage_rows(args.root)
    aggregate = aggregate_rows(rows)
    definitions = benchmark_definitions(rows)
    write_outputs(rows, aggregate, definitions, args.out_stem)
    print_summary(rows, aggregate, args.out_stem)
    return 0


def _dated_default_stem() -> Path:
    return DEFAULT_OUT_STEM.with_name(f"{DEFAULT_OUT_STEM.name}_{datetime.now().strftime('%Y%m%d')}")


def collect_stage_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*/*/*/*/stage_result.json")):
        rel = path.relative_to(root)
        if len(rel.parts) != 6:
            continue
        campaign_id, variant_id, symbol, run_id, stage_name, _ = rel.parts
        payload = _read_json(path)
        stage = str(payload.get("stage") or stage_name)
        status = normalize_status(payload.get("status"), payload.get("passed"))
        criteria = payload.get("criteria") if isinstance(payload.get("criteria"), list) else []
        signature = criteria_signature(criteria)
        benchmark_hash = benchmark_id(stage, signature)
        label = benchmark_label(stage, signature, status)
        failed_metrics = [str(item.get("metric")) for item in criteria if isinstance(item, dict) and not item.get("passed")]
        rows.append(
            {
                "campaign_id": campaign_id,
                "variant_id": variant_id,
                "symbol": symbol,
                "run_id": run_id,
                "stage": stage,
                "status": status,
                "passed": status == "passed",
                "benchmark_id": benchmark_hash,
                "benchmark_label": label,
                "criteria_count": len(signature),
                "failed_metrics": "|".join(failed_metrics),
                "stage_result_path": str(path),
                "criteria_signature": json.dumps(signature, sort_keys=True, separators=(",", ":")),
            }
        )
    return rows


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["stage"], row["benchmark_id"], row["benchmark_label"])
        bucket = buckets.setdefault(
            key,
            {
                "stage": row["stage"],
                "benchmark_id": row["benchmark_id"],
                "benchmark_label": row["benchmark_label"],
                "total": 0,
                "distinct_campaigns": set(),
                "distinct_variants": set(),
                "distinct_runs": set(),
                **{f"{status}_count": 0 for status in STATUS_COLUMNS},
            },
        )
        bucket["total"] += 1
        status = row["status"] if row["status"] in STATUS_COLUMNS else "other"
        bucket[f"{status}_count"] += 1
        bucket["distinct_campaigns"].add(row["campaign_id"])
        bucket["distinct_variants"].add((row["campaign_id"], row["variant_id"]))
        bucket["distinct_runs"].add((row["campaign_id"], row["variant_id"], row["symbol"], row["run_id"]))

    out = []
    for bucket in buckets.values():
        item = dict(bucket)
        item["distinct_campaigns"] = len(bucket["distinct_campaigns"])
        item["distinct_variants"] = len(bucket["distinct_variants"])
        item["distinct_runs"] = len(bucket["distinct_runs"])
        out.append(item)
    return sorted(out, key=lambda item: (item["stage"], item["benchmark_label"], item["benchmark_id"]))


def benchmark_definitions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["stage"], row["benchmark_id"])
        if key not in seen:
            seen[key] = {
                "stage": row["stage"],
                "benchmark_id": row["benchmark_id"],
                "benchmark_label": row["benchmark_label"],
                "criteria_signature": json.loads(row["criteria_signature"]),
            }
    return sorted(seen.values(), key=lambda item: (item["stage"], item["benchmark_label"], item["benchmark_id"]))


def normalize_status(status: Any, passed: Any) -> str:
    if status in {"passed", "failed", "skipped", "error"}:
        return str(status)
    if passed is True:
        return "passed"
    if passed is False:
        return "failed"
    return "other"


def criteria_signature(criteria: list[Any]) -> list[dict[str, Any]]:
    signature = []
    for item in criteria:
        if not isinstance(item, dict):
            continue
        signature.append({"metric": item.get("metric"), "expected": item.get("expected") or {}})
    return signature


def benchmark_id(stage: str, signature: list[dict[str, Any]]) -> str:
    if not signature:
        return "no_criteria"
    payload = json.dumps({"stage": stage, "criteria": signature}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def benchmark_label(stage: str, signature: list[dict[str, Any]], status: str) -> str:
    if not signature:
        return f"no_criteria_{status}"
    if signature == current_signature(stage):
        return "current_default"
    metrics = {str(item.get("metric")) for item in signature}
    expected_by_metric = {str(item.get("metric")): item.get("expected") or {} for item in signature}
    if stage == "limited_core_grid_test":
        if "summary.number_passing_benchmark" in metrics:
            return "legacy_core_requires_passing_benchmark_combo"
        if expected_by_metric.get("summary.total_combinations_tested") == {"min": 100}:
            return "legacy_core_min_100_combinations"
    if stage == "walk_forward_analysis":
        if "summary.windows" in metrics or "stitched_oos_metrics.expectancy_r" in metrics:
            return "legacy_strict_wfa_shortlist"
    if stage == "wfa_oos_monte_carlo":
        if "summary.probability_profit_before_drawdown" in metrics:
            return "legacy_prop_profit_before_drawdown"
    if any("trade_path_stress" in metric for metric in metrics):
        return "legacy_trade_path_stress_gate"
    return "custom_or_legacy"


def current_signature(stage: str) -> list[dict[str, Any]]:
    criteria = cs.DEFAULT_STAGE_CRITERIA.get(stage) or []
    return [{"metric": item["metric"], "expected": expected_from_rule(item)} for item in criteria]


def expected_from_rule(rule: dict[str, Any]) -> dict[str, Any]:
    expected: dict[str, Any] = {}
    for key in ("min", "exclusive_min", "max", "equals"):
        if key in rule:
            expected[key] = rule[key]
    if rule.get("valid_parameter_combination_count"):
        expected["valid_parameter_combination_count"] = "1 fixed combo or 8-120 tunable combos"
    if "dynamic_min" in rule:
        expected["dynamic_min"] = rule["dynamic_min"]
    return expected


def write_outputs(
    rows: list[dict[str, Any]],
    aggregate: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    stem: Path,
) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, stem.with_name(f"{stem.name}_detail.csv"))
    write_csv(aggregate, stem.with_name(f"{stem.name}_aggregate.csv"))
    stem.with_name(f"{stem.name}_benchmark_definitions.json").write_text(
        json.dumps(definitions, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    stem.with_suffix(".md").write_text(markdown_summary(rows, aggregate), encoding="utf-8")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_summary(rows: list[dict[str, Any]], aggregate: list[dict[str, Any]]) -> str:
    lines = [
        "# Backtest Campaign Stage Benchmarks",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Stage result rows scanned: {len(rows)}",
        "",
        "## Counts By Stage And Benchmark",
        "",
        "| Stage | Benchmark used | Total | Pass | Fail | Skipped | Error | Variants | Runs |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        lines.append(
            "| {stage} | {benchmark_label} `{benchmark_id}` | {total} | {passed_count} | "
            "{failed_count} | {skipped_count} | {error_count} | {distinct_variants} | {distinct_runs} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def print_summary(rows: list[dict[str, Any]], aggregate: list[dict[str, Any]], stem: Path) -> None:
    print(f"stage rows: {len(rows)}")
    print(f"stage/benchmark groups: {len(aggregate)}")
    print(f"wrote {stem.with_name(f'{stem.name}_detail.csv')}")
    print(f"wrote {stem.with_name(f'{stem.name}_aggregate.csv')}")
    print(f"wrote {stem.with_name(f'{stem.name}_benchmark_definitions.json')}")
    print(f"wrote {stem.with_suffix('.md')}")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
