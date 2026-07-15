from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil
import traceback
from typing import Any

from alphaquest.research.campaign_stages import run_campaign_stage_tests


REPORT_ROOT = Path("backtest-campaigns")
ARCHIVE_ROOT = REPORT_ROOT / "archive_not_likely_20260614"
LEGACY_ARCHIVE_ROOT = REPORT_ROOT / "archive_not_close_20260614"
DEFAULT_ARTIFACT_STEM = Path("_archived/research_artifacts/campaign_benchmark_likely_refresh_20260614")
SNAPSHOT_SOURCE_DIR = Path("_archived/research_artifacts/campaign_benchmark_likely_refresh_20260614_source_snapshots")


LIKELY_GATES = [
    ("limited_core_grid_test", "summary.total_combinations_tested", "min", 100.0),
    ("limited_core_grid_test", "summary.percentage_profitable_iterations", "min", 0.70),
    ("limited_monkey_test", "summary.core_beats_monkey_net_profit_rate", "min", 0.90),
    ("limited_monkey_test", "summary.core_beats_monkey_max_drawdown_rate", "min", 0.90),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.profit_factor", "exclusive_min", 1.50),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.mar", "exclusive_min", 0.50),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.expectancy_r", "exclusive_min", 0.20),
    ("walk_forward_analysis", "summary.stitched_oos_metrics.total_trades", "exclusive_min", 500.0),
    ("wfa_oos_monkey_test", "summary.core_beats_monkey_net_profit_rate", "min", 0.90),
    ("wfa_oos_monkey_test", "summary.core_beats_monkey_max_drawdown_rate", "min", 0.90),
    ("wfa_oos_monte_carlo", "summary.probability_profit_before_drawdown", "exclusive_min", 0.50),
    ("simulated_incubation_core", "metrics.profit_factor", "exclusive_min", 1.20),
    ("simulated_incubation_core", "metrics.mar", "exclusive_min", 1.20),
    ("simulated_incubation_core", "metrics.expectancy_r", "exclusive_min", 0.15),
    ("simulated_incubation_core", "metrics.total_trades", "exclusive_min", 75.0),
    ("simulated_incubation_monkey", "summary.core_beats_monkey_net_profit_rate", "min", 0.80),
    ("simulated_incubation_monkey", "summary.core_beats_monkey_max_drawdown_rate", "min", 0.80),
    ("acceptance_oos_test", "metrics.profit_factor", "exclusive_min", 1.20),
    ("acceptance_oos_test", "metrics.mar", "exclusive_min", 1.20),
    ("acceptance_oos_test", "metrics.expectancy_r", "exclusive_min", 0.15),
    ("acceptance_oos_test", "metrics.total_trades", "exclusive_min", 25.0),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Archive campaign reports whose existing results are not likely to pass the "
            "current live-trading benchmark; rerun only likely-pass candidates."
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Write manifests without moving or rerunning.")
    parser.add_argument("--archive-root", default=str(ARCHIVE_ROOT))
    parser.add_argument("--artifact-stem", default=str(DEFAULT_ARTIFACT_STEM))
    parser.add_argument("--limit-reruns", type=int, help="Limit likely-candidate reruns for debugging.")
    args = parser.parse_args()

    archive_root = Path(args.archive_root)
    artifact_stem = Path(args.artifact_stem)
    if not args.dry_run and archive_root == ARCHIVE_ROOT:
        migrate_legacy_archive(archive_root)

    rows = build_plan(archive_root)
    write_manifest(rows, artifact_stem)
    print_counts(rows)
    if args.dry_run:
        print(f"dry run wrote {artifact_stem}.json and {artifact_stem}.csv")
        return

    archive_not_likely(rows)
    write_manifest(rows, artifact_stem)

    likely_rows = [row for row in rows if row["decision"] == "retest_likely"]
    if args.limit_reruns is not None:
        likely_rows = likely_rows[: args.limit_reruns]
    for index, row in enumerate(likely_rows, start=1):
        print(f"[{index}/{len(likely_rows)}] rerun {row['campaign_tests_dir']}", flush=True)
        rerun_likely(row)
        write_manifest(rows, artifact_stem)

    write_manifest(rows, artifact_stem)
    print_counts(rows)
    print(f"wrote {artifact_stem}.json and {artifact_stem}.csv")


def migrate_legacy_archive(archive_root: Path) -> None:
    if not LEGACY_ARCHIVE_ROOT.exists() or LEGACY_ARCHIVE_ROOT == archive_root:
        return
    archive_root.mkdir(parents=True, exist_ok=True)
    for child in sorted(LEGACY_ARCHIVE_ROOT.iterdir()):
        shutil.move(str(child), str(_unique_archive_path(archive_root / child.name)))
    try:
        LEGACY_ARCHIVE_ROOT.rmdir()
    except OSError:
        pass


def build_plan(archive_root: Path) -> list[dict[str, Any]]:
    rows = []
    for summary_path in sorted(REPORT_ROOT.rglob("campaign_test_summary.json")):
        campaign_tests_dir = summary_path.parent
        if _is_archive_path(campaign_tests_dir):
            rows.append(_row_for_archived(campaign_tests_dir))
            continue
        summary = read_summary(campaign_tests_dir)
        decision, reason, evidence = classify_report(summary)
        source_config = source_config_for(summary, campaign_tests_dir)
        rows.append(
            _base_row(
                campaign_tests_dir=campaign_tests_dir,
                archive_path=archive_root / campaign_tests_dir.relative_to(REPORT_ROOT),
                source_config=source_config,
                summary=summary,
                decision=decision,
                reason=reason,
                status="pending",
                evidence=evidence,
            )
        )
    return rows


def _row_for_archived(campaign_tests_dir: Path) -> dict[str, Any]:
    summary = read_summary(campaign_tests_dir)
    return _base_row(
        campaign_tests_dir=campaign_tests_dir,
        archive_path=campaign_tests_dir,
        source_config=source_config_for(summary, campaign_tests_dir),
        summary=summary,
        decision="archive_not_likely",
        reason="already_archived",
        status="archived",
        evidence={},
    )


def _base_row(
    *,
    campaign_tests_dir: Path,
    archive_path: Path,
    source_config: Path | None,
    summary: dict,
    decision: str,
    reason: str,
    status: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "campaign_tests_dir": str(campaign_tests_dir),
        "variant_root": str(campaign_tests_dir),
        "archive_path": str(archive_path),
        "source_config": str(source_config) if source_config else "",
        "campaign_id": summary.get("campaign_id"),
        "variant_id": summary.get("variant_id"),
        "symbol": summary.get("symbol"),
        "dataset_id": summary.get("dataset_id"),
        "timeframe": summary.get("timeframe"),
        "decision": decision,
        "reason": reason,
        "status": status,
        "passed": None,
        "failed_stage": "",
        "error": "",
        "evidence": evidence,
    }


def classify_report(summary: dict) -> tuple[str, str, dict[str, Any]]:
    if not summary:
        return "archive_not_likely", "missing_campaign_test_summary", {}

    failed = []
    evidence = {}
    for stage_name, metric, op, expected in LIKELY_GATES:
        stage = _stage(summary, stage_name)
        actual = _metric_value(stage, metric)
        if actual is None and stage_name == "wfa_oos_monte_carlo":
            actual = _metric_value(stage, "summary.probability_payout_eligible")
        evidence[f"{stage_name}.{metric}"] = actual
        if actual is None:
            failed.append(f"{stage_name}.{metric}=missing")
            continue
        passed = actual >= expected if op == "min" else actual > expected
        if not passed:
            symbol = ">=" if op == "min" else ">"
            failed.append(f"{stage_name}.{metric}={actual:.6g} not {symbol} {expected:g}")

    if failed:
        return "archive_not_likely", "old_metrics_reject:" + "; ".join(failed[:4]), evidence
    return "retest_likely", "old_metrics_satisfy_new_benchmark", evidence


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
    snapshot = campaign_tests_dir / "config.yaml"
    if snapshot.is_file():
        return snapshot
    return None


def archive_not_likely(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row["decision"] != "archive_not_likely" or row["status"] != "pending":
            continue
        src = Path(row["variant_root"])
        dst = _unique_archive_path(Path(row["archive_path"]))
        try:
            if not src.exists():
                row["status"] = "blocked"
                row["error"] = "variant root missing"
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            row["archive_path"] = str(dst)
            row["status"] = "archived"
        except Exception as exc:
            row["status"] = "blocked"
            row["error"] = f"{type(exc).__name__}: {exc}"


def rerun_likely(row: dict[str, Any]) -> None:
    source = Path(row["source_config"]) if row.get("source_config") else None
    target = Path(row["campaign_tests_dir"])
    if source is None or not source.is_file():
        row["status"] = "blocked"
        row["error"] = "missing source config"
        return
    try:
        if _path_is_inside(source, target):
            copied = SNAPSHOT_SOURCE_DIR / f"{_safe_name(str(target))}.yaml"
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copied)
            source = copied
            row["source_config"] = str(source)
        if target.is_dir():
            shutil.rmtree(target)
        summary = run_campaign_stage_tests(
            source,
            skip_validation=True,
            continue_on_failure=True,
            out_dir=target,
        )
        row["status"] = "passed" if summary.get("passed") else "failed"
        row["passed"] = bool(summary.get("passed"))
        row["failed_stage"] = _first_failed_stage(summary)
    except Exception as exc:
        row["status"] = "blocked"
        row["passed"] = False
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()


def write_manifest(rows: list[dict[str, Any]], artifact_stem: Path) -> None:
    artifact_stem.parent.mkdir(parents=True, exist_ok=True)
    artifact_stem.with_suffix(".json").write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
    fieldnames = [
        "campaign_tests_dir",
        "variant_root",
        "archive_path",
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


def _is_archive_path(path: Path) -> bool:
    try:
        rel = path.relative_to(REPORT_ROOT)
    except ValueError:
        return False
    return any(part.startswith("archive_") for part in rel.parts)


def _unique_archive_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.name}__{index:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique archive path for {path}")


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")


if __name__ == "__main__":
    main()
