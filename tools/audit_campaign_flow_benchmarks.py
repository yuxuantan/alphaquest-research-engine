from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from alphaquest.research import campaign_stages as cs


SUMMARY_FILENAMES = ("campaign_test_summary.json", "variant_test_summary.json")
NON_BENCHMARKED_STATUSES = {"skipped", "error"}
DEFAULT_ROOTS = (Path("backtest-campaigns"), Path("_archived/reports"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit saved campaign stage artifacts against the current authoritative "
            "campaign_stages backtest-flow criteria."
        )
    )
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        dest="roots",
        help="Artifact root to scan. May be supplied more than once.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=_default_output_path("json"),
        help="Path for the JSON audit manifest.",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=_default_output_path("csv"),
        help="Path for the CSV issue table.",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Return a non-zero exit code when any benchmark drift issue is found.",
    )
    args = parser.parse_args()

    roots = args.roots or [root for root in DEFAULT_ROOTS if root.exists()]
    report = audit_roots(roots)
    write_report(report, args.json_out, args.csv_out)
    print_summary(report, args.json_out, args.csv_out)
    return 1 if args.fail_on_issues and report["summary"]["issue_count"] else 0


def _default_output_path(suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return Path("research_artifacts") / f"campaign_flow_benchmark_audit_{stamp}.{suffix}"


def audit_roots(roots: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    scanned_stage_artifacts = 0
    scanned_summary_artifacts = 0
    run_roots: set[str] = set()

    for root in roots:
        if not root.exists():
            issues.append(
                _issue(
                    path=root,
                    issue_type="scan_root_missing",
                    detail="scan root does not exist",
                )
            )
            continue
        for stage_path in sorted(root.rglob("stage_result.json")):
            scanned_stage_artifacts += 1
            run_roots.add(_display_path(run_root_for_stage_result(stage_path)))
            issues.extend(audit_stage_result_path(stage_path, source="stage_result"))
        for summary_name in SUMMARY_FILENAMES:
            for summary_path in sorted(root.rglob(summary_name)):
                scanned_summary_artifacts += 1
                run_roots.add(_display_path(summary_path.parent))
                issues.extend(audit_summary_path(summary_path))

    by_issue_type: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    for item in issues:
        by_issue_type[item["issue_type"]] = by_issue_type.get(item["issue_type"], 0) + 1
        stage = item.get("stage")
        if stage:
            by_stage[stage] = by_stage.get(stage, 0) + 1

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "authoritative_flow": {
            "stage_order": list(cs.DEFAULT_STAGE_ORDER),
            "criteria": {stage: cs.DEFAULT_STAGE_CRITERIA[stage] for stage in cs.DEFAULT_STAGE_ORDER},
        },
        "scan_roots": [_display_path(root) for root in roots],
        "summary": {
            "run_roots_scanned": len(run_roots),
            "stage_artifacts_scanned": scanned_stage_artifacts,
            "summary_artifacts_scanned": scanned_summary_artifacts,
            "issue_count": len(issues),
            "issue_count_by_type": dict(sorted(by_issue_type.items())),
            "issue_count_by_stage": dict(sorted(by_stage.items())),
        },
        "issues": issues,
    }


def audit_stage_result_path(path: Path, *, source: str) -> list[dict[str, Any]]:
    try:
        payload = _read_json(path)
    except Exception as exc:  # pragma: no cover - exact JSON errors vary by version
        return [
            _issue(
                path=path,
                artifact_type=source,
                issue_type="unreadable_json",
                detail=repr(exc),
            )
        ]
    return audit_stage_payload(payload, path=path, artifact_type=source)


def audit_summary_path(path: Path) -> list[dict[str, Any]]:
    try:
        payload = _read_json(path)
    except Exception as exc:  # pragma: no cover - exact JSON errors vary by version
        return [
            _issue(
                path=path,
                artifact_type=path.name,
                issue_type="unreadable_json",
                detail=repr(exc),
            )
        ]

    issues: list[dict[str, Any]] = []
    stages = payload.get("stages")
    if not isinstance(stages, list):
        if is_campaign_level_summary(payload, path):
            return []
        return [
            _issue(
                path=path,
                artifact_type=path.name,
                issue_type="summary_missing_stages",
                detail="summary has no stages list to audit",
            )
        ]

    expected_summary_passed, flow_issues = summary_flow_assessment(
        stages,
        path=path,
        artifact_type=path.name,
    )
    issues.extend(flow_issues)
    stored_summary_passed = bool(payload.get("passed"))
    if stored_summary_passed != expected_summary_passed:
        issues.append(
            _issue(
                path=path,
                artifact_type=path.name,
                issue_type="summary_pass_mismatch",
                detail="top-level summary pass flag disagrees with current stage-flow semantics",
                stored_passed=stored_summary_passed,
                expected_passed=expected_summary_passed,
            )
        )

    for stage_payload in stages:
        if isinstance(stage_payload, dict):
            issues.extend(audit_stage_payload(stage_payload, path=path, artifact_type=path.name))
    return issues


def audit_stage_payload(payload: dict[str, Any], *, path: Path, artifact_type: str) -> list[dict[str, Any]]:
    stage = str(payload.get("stage") or path.parent.name)
    status = str(payload.get("status") or "")
    if status in NON_BENCHMARKED_STATUSES:
        return []
    if stage not in cs.DEFAULT_STAGE_CRITERIA:
        return [
            _issue(
                path=path,
                artifact_type=artifact_type,
                stage=stage,
                issue_type="unknown_stage",
                detail="stage is not part of the current campaign flow",
            )
        ]

    current_criteria = cs._criteria_for_stage(stage, {})
    expected_results = cs.evaluate_criteria(payload, current_criteria)
    expected_passed = all(item["passed"] for item in expected_results)
    expected_status = "passed" if expected_passed else "failed"
    stored_passed = bool(payload.get("passed"))
    stored_status = status or ("passed" if stored_passed else "failed")
    failed_metrics = [item["metric"] for item in expected_results if not item["passed"]]
    issues: list[dict[str, Any]] = []

    stored_signature = criteria_signature(payload.get("criteria") or [])
    expected_signature = criteria_signature(expected_results)
    if stored_signature and stored_signature != expected_signature:
        issues.append(
            _issue(
                path=path,
                artifact_type=artifact_type,
                stage=stage,
                issue_type="criteria_mismatch",
                detail="stored criteria do not match the current authoritative stage criteria",
                stored_criteria=stored_signature,
                expected_criteria=expected_signature,
                failed_current_metrics=failed_metrics,
            )
        )
    if stored_passed != expected_passed:
        issues.append(
            _issue(
                path=path,
                artifact_type=artifact_type,
                stage=stage,
                issue_type="pass_mismatch",
                detail="stored passed flag disagrees with current criteria re-evaluation",
                stored_passed=stored_passed,
                expected_passed=expected_passed,
                stored_status=stored_status,
                expected_status=expected_status,
                failed_current_metrics=failed_metrics,
            )
        )
    elif stored_status in {"passed", "failed"} and stored_status != expected_status:
        issues.append(
            _issue(
                path=path,
                artifact_type=artifact_type,
                stage=stage,
                issue_type="status_mismatch",
                detail="stored status disagrees with current criteria re-evaluation",
                stored_passed=stored_passed,
                expected_passed=expected_passed,
                stored_status=stored_status,
                expected_status=expected_status,
                failed_current_metrics=failed_metrics,
            )
        )
    return issues


def criteria_signature(criteria_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signature = []
    for item in criteria_results:
        if not isinstance(item, dict):
            continue
        signature.append(
            {
                "metric": item.get("metric"),
                "expected": item.get("expected") or {},
            }
        )
    return signature


def summary_flow_assessment(
    stages: list[dict[str, Any]],
    *,
    path: Path,
    artifact_type: str,
) -> tuple[bool, list[dict[str, Any]]]:
    """Return current top-level pass semantics and flow-completeness issues.

    A skipped downstream stage is acceptable only when a prior stage still fails
    under the current criteria or the stage was explicitly disabled. If an older
    stale gate caused the skip, the run is incomplete under the current flow.
    """

    issues: list[dict[str, Any]] = []
    prior_current_failure = False
    any_current_pass = False
    all_current_pass_or_skip = True
    flow_incomplete = False

    for payload in stages:
        if not isinstance(payload, dict):
            flow_incomplete = True
            all_current_pass_or_skip = False
            issues.append(
                _issue(
                    path=path,
                    artifact_type=artifact_type,
                    issue_type="summary_malformed_stage",
                    detail="summary stages list contains a non-object item",
                )
            )
            continue

        stage = str(payload.get("stage") or "")
        status = str(payload.get("status") or "")
        skip_reason = str(payload.get("skip_reason") or "")
        if status == "skipped":
            if skip_reason == "prior stage failed" and not prior_current_failure:
                flow_incomplete = True
                all_current_pass_or_skip = False
                issues.append(
                    _issue(
                        path=path,
                        artifact_type=artifact_type,
                        stage=stage,
                        issue_type="flow_incomplete_after_reclassification",
                        detail=(
                            "stage was skipped because a prior stage failed under stale criteria, "
                            "but no prior stage fails under the current criteria"
                        ),
                    )
                )
            continue
        if status == "error":
            prior_current_failure = True
            all_current_pass_or_skip = False
            continue
        if stage not in cs.DEFAULT_STAGE_CRITERIA:
            prior_current_failure = True
            all_current_pass_or_skip = False
            continue

        expected_results = cs.evaluate_criteria(payload, cs._criteria_for_stage(stage, {}))
        current_passed = all(item["passed"] for item in expected_results)
        any_current_pass = any_current_pass or current_passed
        if not current_passed:
            prior_current_failure = True
            all_current_pass_or_skip = False

    expected_passed = (not flow_incomplete) and all_current_pass_or_skip and any_current_pass
    return expected_passed, issues


def is_campaign_level_summary(payload: dict[str, Any], path: Path) -> bool:
    if path.name != "campaign_test_summary.json":
        return False
    campaign_level_keys = {
        "variants",
        "variants_tested",
        "runs",
        "original_runs",
        "original_run_count",
        "rescue_runs",
        "rescue_run_count",
        "terminal_stage",
        "terminal_counts",
        "terminal_counts_corrected_gates",
        "best_original",
        "best_rescue",
        "best_runs_by_core",
        "best_runs_by_core_net_profit",
    }
    return any(key in payload for key in campaign_level_keys)


def run_root_for_stage_result(path: Path) -> Path:
    return path.parent.parent


def write_report(report: dict[str, Any], json_out: Path, csv_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    write_issues_csv(report["issues"], csv_out)


def write_issues_csv(issues: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "issue_type",
        "stage",
        "artifact_type",
        "run_root",
        "path",
        "stored_status",
        "expected_status",
        "stored_passed",
        "expected_passed",
        "failed_current_metrics",
        "detail",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for issue in issues:
            row = dict(issue)
            row["failed_current_metrics"] = "|".join(row.get("failed_current_metrics") or [])
            writer.writerow(row)


def print_summary(report: dict[str, Any], json_out: Path, csv_out: Path) -> None:
    summary = report["summary"]
    print(f"run roots scanned: {summary['run_roots_scanned']}")
    print(f"stage artifacts scanned: {summary['stage_artifacts_scanned']}")
    print(f"summary artifacts scanned: {summary['summary_artifacts_scanned']}")
    print(f"issues: {summary['issue_count']}")
    for issue_type, count in summary["issue_count_by_type"].items():
        print(f"  {issue_type}: {count}")
    print(f"wrote {json_out}")
    print(f"wrote {csv_out}")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _issue(path: Path, issue_type: str, detail: str, **extra: Any) -> dict[str, Any]:
    issue = {
        "issue_type": issue_type,
        "path": _display_path(path),
        "detail": detail,
    }
    issue.update(extra)
    if "run_root" not in issue:
        issue["run_root"] = _display_path(_issue_run_root(path, issue.get("artifact_type")))
    return issue


def _issue_run_root(path: Path, artifact_type: Any) -> Path:
    if artifact_type == "stage_result":
        return path.parent.parent
    if artifact_type in SUMMARY_FILENAMES:
        return path.parent
    return path.parent if path.name else path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
