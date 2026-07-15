"""Prepare an append-only human-review packet for unresolved historical runs.

This tool never edits authored configs or generated run evidence. It reconciles
the current lineage audit with the durable research ledger, closes false-positive
review items whose ledger verdict is already FAIL, and prepares deterministic
trade samples for the remaining manual-review boundary.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from alphaquest.dashboard.validation_app import (
    REVIEW_SAMPLE_MODES,
    build_review_queue,
    prepare_trade_table,
    validation_check_summary,
)
from alphaquest.validation import load_validation_run


ROOT = Path(__file__).resolve().parents[1]
CATEGORY_MODES = {
    "first_trade": ("First 20 trades chronologically", 1),
    "last_trade": ("Last 20 trades chronologically", 1),
    "random_trades": ("Random 20 trades", 5),
    "best_trade": ("Best 20 trades by R", 3),
    "worst_trade": ("Worst 20 trades by R", 3),
    "forced_flattens": ("All forced-flatten trades", 200),
    "same_bar_ambiguity": ("All same-bar ambiguous trades", 200),
    "warnings": ("All trades with mismatch warnings", 200),
    "strategy_edge_cases": ("High-impact edge cases", 20),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    stamp = datetime.now().date().isoformat().replace("-", "")
    parser.add_argument(
        "--audit-json",
        default=f"research_artifacts/cleanup/research_repository_rationalization_{stamp}.json",
    )
    parser.add_argument(
        "--output-dir",
        default=f"research_artifacts/remediation/historical_review_{stamp}",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "unresolved"),
        default="all",
        help="Classify every registered run or only unresolved/error runs.",
    )
    args = parser.parse_args(argv)

    audit_path = ROOT / args.audit_json
    output_dir = ROOT / args.output_dir
    queue_dir = output_dir / "review_queues"
    if queue_dir.is_dir():
        for stale in queue_dir.glob("*.csv"):
            stale.unlink()
    report = prepare_review_packet(ROOT, audit_path, output_dir, scope=args.scope)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review_manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(_markdown(report), encoding="utf-8")
    _write_disposition_csv(output_dir / "automatic_dispositions.csv", report["automatic_dispositions"])
    _write_disposition_csv(output_dir / "manual_review_queue.csv", report["manual_review_queue"])
    print(f"WROTE {(output_dir / 'README.md').relative_to(ROOT)}")
    print(f"WROTE {(output_dir / 'review_manifest.json').relative_to(ROOT)}")
    print(f"MANUAL_REVIEW_ITEMS {len(report['manual_review_queue'])}")
    return 0


def prepare_review_packet(
    root: Path,
    audit_path: Path,
    output_dir: Path,
    *,
    scope: str = "all",
) -> dict[str, Any]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    ledger = pd.read_csv(root / "research_ledger.csv", dtype=str).fillna("")
    active_count = _csv_rows(root / "views/active/campaigns.csv")
    candidate_count = _csv_rows(root / "views/candidate/campaigns.csv")
    all_runs = audit["lineage_coverage"]["runs"]
    selected = (
        all_runs
        if scope == "all"
        else [
            row
            for row in all_runs
            if row.get("recorded_verdict") == "NEEDS MANUAL REVIEW" or row.get("errors")
        ]
    )

    automatic: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    for row in selected:
        run_dir = root / row["run_dir"]
        ledger_row = _latest_ledger_row(ledger, row)
        ledger_decision = str(ledger_row.get("decision") or "").upper()
        ledger_result = str(ledger_row.get("result") or "").upper()
        ledger_verdict = _ledger_verdict(ledger_row)
        validation_dirs = sorted((run_dir / "validation_runs").glob("*"))
        validation_dirs = [path for path in validation_dirs if path.is_dir() and (path / "metadata.json").is_file()]
        base = {
            "run_uid": row.get("run_uid"),
            "campaign_id": row.get("campaign_id"),
            "variant_id": row.get("variant_id"),
            "test_run_id": row.get("test_run_id"),
            "run_dir": row.get("run_dir"),
            "recorded_verdict": row.get("recorded_verdict"),
            "lineage_verdict": row.get("lineage_verdict"),
            "lineage_errors": row.get("errors") or [],
            "missing_evidence": row.get("missing_evidence") or [],
            "latest_ledger_decision": ledger_decision or None,
            "latest_ledger_result": ledger_result or None,
            "latest_ledger_verdict": ledger_verdict,
            "latest_ledger_failure_reason": ledger_row.get("failure_reason") or None,
            "evidence_hashes": _evidence_hashes(run_dir),
        }
        if row.get("errors"):
            base.update(
                {
                    "disposition": "RETAIN_INVALID_HISTORICAL_RUN",
                    "reason": "A rejected historical run has a hash mismatch. Do not repair or rerun it for promotion.",
                }
            )
            automatic.append(base)
            continue
        if ledger_verdict == "FAIL" or row.get("recorded_verdict") == "FAIL":
            base.update(
                {
                    "disposition": "RETAIN_REJECTED_HISTORICAL_RUN",
                    "reason": (
                        "The durable ledger or terminal run summary records rejection; missing modern validation is "
                        "not a reason to retest it."
                    ),
                }
            )
            automatic.append(base)
            continue
        latest_variant_row = _latest_variant_row(ledger, row)
        if not validation_dirs and _ledger_verdict(latest_variant_row) == "FAIL":
            base.update(
                {
                    "disposition": "RETAIN_SUPERSEDED_INCOMPLETE_RUN",
                    "reason": (
                        "This zero/no-evidence run is superseded for decision purposes by a later same-variant "
                        "ledger rejection; do not backfill or rerun it."
                    ),
                    "superseding_ledger_report": latest_variant_row.get("report_path") or None,
                    "superseding_ledger_failure_reason": latest_variant_row.get("failure_reason") or None,
                }
            )
            automatic.append(base)
            continue

        if validation_dirs:
            review = _prepare_validation_review(root, validation_dirs[0], output_dir, base)
            review["manual_action"] = (
                "Review the deterministic trade queues, then decide whether to reject/archive the POC or authorize "
                "a new frozen-mechanics requalification attempt. Do not approve the historical run itself."
            )
        else:
            review = dict(base)
            review.update(
                {
                    "review_type": "data_scope_disposition",
                    "validation_evidence_dir": None,
                    "manual_action": (
                        "Decide whether the missing full-history input should remain a permanent data-gated closure. "
                        "There are no trades to validate and no automatic rerun is justified."
                    ),
                    "promotion_blockers": [
                        "no validation evidence export",
                        "no reviewable trades",
                        "campaign is closed and no active/candidate campaign exists",
                    ],
                }
            )
        manual.append(review)

    dispositions = Counter(row["disposition"] for row in automatic)
    dispositions.update({"MANUAL_REVIEW_REQUIRED": len(manual)})
    classified = len(automatic) + len(manual)
    return {
        "schema": "alphaquest.historical-remediation-review/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_audit": str(audit_path.relative_to(root)),
        "policy": {
            "historical_runs_immutable": True,
            "automatic_performance_reruns": False,
            "human_approval_written": False,
            "active_campaign_count": active_count,
            "candidate_campaign_count": candidate_count,
            "stop_boundary": "human disposition and mechanics review",
            "scope": scope,
        },
        "coverage": {
            "registered_run_count": len(all_runs),
            "selected_run_count": len(selected),
            "classified_run_count": classified,
            "coverage_complete": classified == len(selected),
            "disposition_counts": dict(sorted(dispositions.items())),
        },
        "automatic_dispositions": automatic,
        "manual_review_queue": manual,
    }


def _prepare_validation_review(root: Path, validation_dir: Path, output_dir: Path, base: dict[str, Any]) -> dict[str, Any]:
    run = load_validation_run(validation_dir, include_tick_windows=False)
    table = prepare_trade_table(run.trades, run.exit_audits, run.validation_checks)
    categories: dict[str, list[str]] = {}
    category_rows: list[pd.DataFrame] = []
    for category, (mode, sample_size) in CATEGORY_MODES.items():
        if mode not in REVIEW_SAMPLE_MODES:
            raise ValueError(f"unsupported dashboard review mode: {mode}")
        queue = build_review_queue(
            table,
            run.condition_snapshots,
            run.exit_audits,
            run.bar_windows,
            sample_mode=mode,
            sample_size=sample_size,
            random_seed=7,
            tick_size=run.metadata.get("tick_size"),
        )
        ids = [_trade_id(value) for value in queue.get("trade_id", pd.Series(dtype=object)).tolist()]
        categories[category] = list(dict.fromkeys(ids))
        if not queue.empty:
            scoped = queue.copy()
            scoped.insert(0, "sampling_category", category)
            category_rows.append(scoped)

    queue_path = output_dir / "review_queues" / f"{base['run_uid']}.csv"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    if category_rows:
        combined = pd.concat(category_rows, ignore_index=True)
        keep = [
            column
            for column in (
                "sampling_category",
                "trade_id",
                "review_reason",
                "session_date",
                "direction",
                "entry_time",
                "entry_price",
                "stop_price",
                "target_price",
                "exit_time",
                "exit_price",
                "exit_reason",
                "r_multiple",
                "check_error_count",
                "check_warning_count",
                "check_flags",
            )
            if column in combined.columns
        ]
        combined[keep].to_csv(queue_path, index=False, quoting=csv.QUOTE_MINIMAL)
    else:
        pd.DataFrame(columns=["sampling_category", "trade_id", "review_reason"]).to_csv(queue_path, index=False)

    metadata = run.metadata
    checks = validation_check_summary(run.validation_checks)
    required_categories = {
        "identity",
        "time_ordering",
        "price_logic",
        "filter_logic",
        "exit_logic",
        "data_quality",
        "reconciliation",
    }
    actual_categories = set(run.validation_checks.get("category", pd.Series(dtype=str)).dropna().astype(str))
    blockers = [
        "historical validation metadata is not a current hash-bound promotion-gate decision",
        "campaign is closed and no active/candidate campaign exists",
    ]
    if not metadata.get("validation_lane"):
        blockers.append("validation_lane is absent from historical metadata")
    missing_categories = sorted(required_categories - actual_categories)
    if missing_categories:
        blockers.append(f"automated validation categories missing: {', '.join(missing_categories)}")
    if checks["errors"]:
        blockers.append(f"automated validation contains {checks['errors']} error(s)")

    result = dict(base)
    result.update(
        {
            "review_type": "trade_mechanics_and_requalification_disposition",
            "validation_evidence_dir": str(validation_dir.relative_to(root)),
            "review_queue_csv": str(queue_path.relative_to(root)),
            "validation_metadata": {
                "schema_version": metadata.get("schema_version"),
                "validation_lane": metadata.get("validation_lane"),
                "config_hash": metadata.get("config_hash"),
                "input_data_hash": metadata.get("input_data_hash"),
                "trade_count": len(run.trades),
            },
            "automated_check_summary": checks,
            "proposed_sampling_categories": categories,
            "promotion_blockers": blockers,
        }
    )
    return result


def _latest_ledger_row(ledger: pd.DataFrame, row: dict[str, Any]) -> dict[str, str]:
    matched = ledger[
        ledger["campaign_id"].eq(str(row.get("campaign_id") or ""))
        & ledger["variant_id"].eq(str(row.get("variant_id") or ""))
    ]
    run_dir = str(row.get("run_dir") or "")
    if run_dir and not matched.empty:
        exact = matched[matched["report_path"].str.startswith(run_dir, na=False)]
        if not exact.empty:
            matched = exact
    if matched.empty:
        return {}
    return {str(key): str(value) for key, value in matched.iloc[-1].to_dict().items()}


def _latest_variant_row(ledger: pd.DataFrame, row: dict[str, Any]) -> dict[str, str]:
    matched = ledger[
        ledger["campaign_id"].eq(str(row.get("campaign_id") or ""))
        & ledger["variant_id"].eq(str(row.get("variant_id") or ""))
    ]
    if matched.empty:
        return {}
    return {str(key): str(value) for key, value in matched.iloc[-1].to_dict().items()}


def _ledger_verdict(row: dict[str, str]) -> str | None:
    result = str(row.get("result") or "").strip().upper().replace("_", " ")
    decision = str(row.get("decision") or "").strip().upper().replace("_", " ")
    if result == "FAIL" or decision in {"FAIL", "REJECT", "REJECTED"}:
        return "FAIL"
    if result == "PASS" or decision == "PASS":
        return "PASS"
    if result == "NEEDS MANUAL REVIEW" or decision == "NEEDS MANUAL REVIEW":
        return "NEEDS MANUAL REVIEW"
    return None


def _evidence_hashes(run_dir: Path) -> dict[str, str]:
    names = (
        "run_uid.txt",
        "run_manifest.json",
        "variant_test_summary.json",
        "campaign_test_summary.json",
        "source_config.yaml",
        "effective_config.yaml",
        "input_data_hash.txt",
    )
    return {name: _sha256(run_dir / name) for name in names if (run_dir / name).is_file()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trade_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _csv_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def _write_disposition_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "run_uid",
        "campaign_id",
        "variant_id",
        "test_run_id",
        "run_dir",
        "recorded_verdict",
        "lineage_verdict",
        "latest_ledger_verdict",
        "disposition",
        "review_type",
        "review_queue_csv",
        "reason",
        "manual_action",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([{column: row.get(column) for column in columns} for row in rows], columns=columns)
    frame.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def _markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    lines = [
        "# Historical Remediation Review Boundary",
        "",
        f"Created: `{report['created_at']}`",
        "",
        "Historical run evidence was not edited. No performance rerun or human approval was written.",
        "",
        "## Coverage",
        "",
        f"- Registered runs: `{coverage['registered_run_count']}`",
        f"- Runs classified in this scope: `{coverage['classified_run_count']}`",
        f"- Coverage complete: `{coverage['coverage_complete']}`",
        f"- Automatic dispositions: `{len(report['automatic_dispositions'])}`",
        f"- Manual review items: `{len(report['manual_review_queue'])}`",
        "",
        "## Disposition Counts",
        "",
    ]
    for disposition, count in coverage["disposition_counts"].items():
        lines.append(f"- `{disposition}`: `{count}`")
    exceptions = [row for row in report["automatic_dispositions"] if row["disposition"] != "RETAIN_REJECTED_HISTORICAL_RUN"]
    lines.extend(["", "## Non-Standard Automatic Dispositions", ""])
    if exceptions:
        for row in exceptions:
            lines.append(f"- `{row['run_uid']}` — **{row['disposition']}** — {row['reason']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Manual Review Queue", ""])
    for index, row in enumerate(report["manual_review_queue"], start=1):
        lines.extend(
            [
                f"### {index}. {row['campaign_id']} / {row['variant_id']}",
                "",
                f"- Run UID: `{row['run_uid']}`",
                f"- Run: `{row['run_dir']}`",
                f"- Review type: `{row['review_type']}`",
                f"- Latest ledger decision: `{row.get('latest_ledger_decision')}`",
                f"- Validation evidence: `{row.get('validation_evidence_dir')}`",
                f"- Review queue: `{row.get('review_queue_csv')}`",
                f"- Required human action: {row['manual_action']}",
                "- Promotion blockers:",
            ]
        )
        lines.extend(f"  - {item}" for item in row.get("promotion_blockers", []))
        lines.append("")
    lines.extend(
        [
            "## Stop Boundary",
            "",
            "Choose reject/archive or explicitly authorize a new frozen-mechanics requalification attempt for each queue item. "
            "Do not change an historical verdict and do not mark an old POC `approved_for_testing`.",
            "",
            "**NEEDS MANUAL REVIEW**",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
