from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil
import traceback
from typing import Any

from propstack.research.campaign_stages import run_campaign_stage_tests


REPORT_ROOT = Path("data/reports/campaigns")
ARCHIVE_ROOT = REPORT_ROOT / "archive_not_likely_20260614"
DEFAULT_ARTIFACT_STEM = Path("research_artifacts/campaign_benchmark_shortlist_refresh_20260614")
SNAPSHOT_SOURCE_DIR = Path("research_artifacts/campaign_benchmark_shortlist_refresh_20260614_source_snapshots")


SHORTLIST_GATES = [
    ("limited_core_grid_test", "summary.total_combinations_tested", "min", 100.0),
    ("limited_core_grid_test", "summary.percentage_profitable_iterations", "min", 0.70),
    ("limited_monkey_test", "summary.core_beats_monkey_net_profit_rate", "min", 0.90),
    ("limited_monkey_test", "summary.core_beats_monkey_max_drawdown_rate", "min", 0.90),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.profit_factor", "min", 1.20),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.mar", "min", 0.40),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.total_trades", "min", 500.0),
    ("wfa_oos_monkey_test", "summary.core_beats_monkey_net_profit_rate", "min", 0.80),
    ("wfa_oos_monkey_test", "summary.core_beats_monkey_max_drawdown_rate", "min", 0.80),
    ("wfa_oos_monte_carlo", "summary.probability_profit_before_drawdown", "exclusive_min", 0.50),
    ("simulated_incubation_core", "metrics.profit_factor", "min", 1.00),
    ("simulated_incubation_core", "metrics.mar", "min", 1.00),
    ("simulated_incubation_core", "metrics.total_trades", "min", 75.0),
    ("simulated_incubation_monkey", "summary.core_beats_monkey_net_profit_rate", "min", 0.80),
    ("simulated_incubation_monkey", "summary.core_beats_monkey_max_drawdown_rate", "min", 0.80),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rerun only archived reports likely to pass the seven shortlist-selection tests."
    )
    parser.add_argument("--dry-run", action="store_true", help="Write manifest without moving or rerunning.")
    parser.add_argument("--artifact-stem", default=str(DEFAULT_ARTIFACT_STEM))
    parser.add_argument("--limit-reruns", type=int, help="Limit shortlisted reruns for debugging.")
    args = parser.parse_args()

    artifact_stem = Path(args.artifact_stem)
    rows = build_plan()
    write_manifest(rows, artifact_stem)
    print_counts(rows)
    if args.dry_run:
        print(f"dry run wrote {artifact_stem}.json and {artifact_stem}.csv")
        return

    rerun_rows = [row for row in rows if row["decision"] == "retest_shortlist_likely"]
    if args.limit_reruns is not None:
        rerun_rows = rerun_rows[: args.limit_reruns]
    for index, row in enumerate(rerun_rows, start=1):
        print(f"[{index}/{len(rerun_rows)}] rerun {row['active_campaign_tests_dir']}", flush=True)
        rerun_shortlist(row)
        write_manifest(rows, artifact_stem)

    write_manifest(rows, artifact_stem)
    print_counts(rows)
    print(f"wrote {artifact_stem}.json and {artifact_stem}.csv")


def build_plan() -> list[dict[str, Any]]:
    rows = []
    for campaign_tests_dir in _candidate_campaign_tests_dirs():
        summary = read_summary(campaign_tests_dir)
        is_archived = _path_is_inside(campaign_tests_dir, ARCHIVE_ROOT)
        decision, reason, evidence, failures = classify_summary(summary, is_archived=is_archived)
        source_config = source_config_for(summary, campaign_tests_dir)
        if is_archived:
            archived_variant_root = campaign_tests_dir.parent
            active_variant_root = REPORT_ROOT / campaign_tests_dir.parent.relative_to(ARCHIVE_ROOT)
        else:
            archived_variant_root = None
            active_variant_root = campaign_tests_dir.parent
        rows.append(
            {
                "archived_campaign_tests_dir": str(campaign_tests_dir),
                "archived_variant_root": str(archived_variant_root) if archived_variant_root else "",
                "active_campaign_tests_dir": str(active_variant_root / "campaign_tests"),
                "active_variant_root": str(active_variant_root),
                "source_config": str(source_config) if source_config else "",
                "campaign_id": summary.get("campaign_id"),
                "variant_id": summary.get("variant_id"),
                "symbol": summary.get("symbol"),
                "dataset_id": summary.get("dataset_id"),
                "timeframe": summary.get("timeframe"),
                "decision": decision,
                "reason": reason,
                "status": "pending" if decision == "retest_shortlist_likely" else "archived",
                "passed": None,
                "failed_stage": "",
                "error": "",
                "shortlist_fail_count": len(failures),
                "evidence": evidence,
            }
        )
    return rows


def _candidate_campaign_tests_dirs() -> list[Path]:
    paths = set(ARCHIVE_ROOT.rglob("campaign_tests")) if ARCHIVE_ROOT.exists() else set()
    for path in REPORT_ROOT.rglob("campaign_tests"):
        if _path_is_inside(path, ARCHIVE_ROOT):
            continue
        paths.add(path)
    return sorted(paths)


def classify_summary(summary: dict, *, is_archived: bool = True) -> tuple[str, str, dict[str, Any], list[str]]:
    if not summary:
        if not is_archived:
            return "retest_shortlist_likely", "active_partial_or_missing_summary", {}, []
        return "archive_not_shortlist_likely", "missing_campaign_test_summary", {}, ["missing_summary"]
    failures = []
    evidence = {}
    for stage_name, metric, op, expected in SHORTLIST_GATES:
        stage = _stage(summary, stage_name)
        actual = _metric_value(stage, metric)
        if actual is None and stage_name == "wfa_oos_monte_carlo":
            actual = _metric_value(stage, "summary.probability_payout_eligible")
        key = f"{stage_name}.{metric}"
        evidence[key] = actual
        if actual is None:
            failures.append(f"{key}=missing")
            continue
        passed = actual >= expected if op == "min" else actual > expected
        if not passed:
            symbol = ">=" if op == "min" else ">"
            failures.append(f"{key}={actual:.6g} not {symbol} {expected:g}")

    if not failures:
        return "retest_shortlist_likely", "old_metrics_satisfy_shortlist_benchmark", evidence, failures
    if len(failures) <= 2 and all(_near_failure(failure) for failure in failures):
        return "retest_shortlist_likely", "near_shortlist_gate:" + "; ".join(failures), evidence, failures
    return "archive_not_shortlist_likely", "old_metrics_reject:" + "; ".join(failures[:4]), evidence, failures


def _near_failure(failure: str) -> bool:
    if "missing" in failure or " not " not in failure:
        return False
    actual_text = failure.split("=", 1)[1].split(" not ", 1)[0]
    expected_text = failure.rsplit(" ", 1)[-1]
    try:
        actual = float(actual_text)
        expected = float(expected_text)
    except ValueError:
        return False
    return actual >= expected * 0.90


def rerun_shortlist(row: dict[str, Any]) -> None:
    archived_variant = Path(row["archived_variant_root"]) if row.get("archived_variant_root") else None
    active_variant = Path(row["active_variant_root"])
    source = Path(row["source_config"]) if row.get("source_config") else None
    if source is None or not source.is_file():
        row["status"] = "blocked"
        row["error"] = "missing source config"
        return
    try:
        if (archived_variant is not None and _path_is_inside(source, archived_variant)) or _path_is_inside(
            source,
            active_variant,
        ):
            source_root = archived_variant if archived_variant is not None else active_variant
            copied = SNAPSHOT_SOURCE_DIR / f"{_safe_name(str(source_root))}.yaml"
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copied)
            source = copied
            row["source_config"] = str(source)

        if archived_variant is not None:
            _unarchive_variant(archived_variant, active_variant)
        target = active_variant / "campaign_tests"
        if target.is_dir():
            shutil.rmtree(target)
        summary = run_campaign_stage_tests(
            source,
            skip_validation=True,
            continue_on_failure=True,
            out_dir=target,
            include_acceptance=False,
        )
        row["status"] = "passed" if summary.get("passed") else "failed"
        row["passed"] = bool(summary.get("passed"))
        row["failed_stage"] = _first_failed_stage(summary)
    except Exception as exc:
        row["status"] = "blocked"
        row["passed"] = False
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()


def _unarchive_variant(archived_variant: Path, active_variant: Path) -> None:
    if not archived_variant.exists():
        return
    active_variant.parent.mkdir(parents=True, exist_ok=True)
    if not active_variant.exists():
        shutil.move(str(archived_variant), str(active_variant))
        return
    for child in sorted(archived_variant.iterdir()):
        dst = active_variant / child.name
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        shutil.move(str(child), str(dst))
    try:
        archived_variant.rmdir()
    except OSError:
        pass


def read_summary(campaign_tests_dir: Path) -> dict:
    return read_json(campaign_tests_dir / "campaign_test_summary.json")


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
    snapshot = campaign_tests_dir / "config_snapshot.yaml"
    if snapshot.is_file():
        return snapshot
    return None


def write_manifest(rows: list[dict[str, Any]], artifact_stem: Path) -> None:
    artifact_stem.parent.mkdir(parents=True, exist_ok=True)
    artifact_stem.with_suffix(".json").write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
    fieldnames = [
        "archived_campaign_tests_dir",
        "active_campaign_tests_dir",
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
        "failed_stage",
        "shortlist_fail_count",
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


def _stage(summary: dict, name: str) -> dict:
    for stage in summary.get("stages", []):
        if stage.get("stage") == name:
            return stage
    return {}


def _metric_value(stage: dict, dotted: str) -> float | None:
    value: Any = stage
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_failed_stage(summary: dict) -> str:
    for stage in summary.get("stages", []):
        if stage.get("status") in {"failed", "error"}:
            return str(stage.get("stage") or "")
    return ""


def _path_is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")


if __name__ == "__main__":
    main()
