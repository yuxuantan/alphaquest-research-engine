"""Write a durable current-truth and repository-rationalization audit."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

from alphaquest.research.lineage import lineage_coverage
from alphaquest.research.storage import load_storage_layout, resolve_recorded_path
from cleanup_redundant_generated_artifacts import (
    build_report as build_cleanup_report,
    find_heavy_generated_payloads,
    find_junk_paths,
    find_redundant_runs,
)


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_CLASSES = (
    "authored research definition",
    "invariant variant mechanics",
    "rescue attempt",
    "generated authoritative evidence",
    "compact terminal summary",
    "reproducible bulk output",
    "generated navigation/projection",
    "cache",
    "interrupted/incomplete run",
    "superseded duplicate",
    "orphaned or unreferenced object",
    "unknown/manual-review required",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory research definitions, evidence, lineage, and cleanup state.")
    parser.add_argument("--database", default="catalogs/research_registry.sqlite")
    parser.add_argument("--output-prefix", default=f"research_artifacts/cleanup/research_repository_rationalization_{datetime.now().date().isoformat().replace('-', '')}")
    args = parser.parse_args(argv)

    report = audit_repository(ROOT, ROOT / args.database)
    prefix = ROOT / args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".json").write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")
    prefix.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")
    print(f"WROTE {_display(ROOT, prefix.with_suffix('.md'))}")
    print(f"WROTE {_display(ROOT, prefix.with_suffix('.json'))}")
    print(f"VERDICT {report['repository_verdict']}")
    return 0


def audit_repository(root: Path, database: Path) -> dict[str, Any]:
    layout = load_storage_layout(root)
    campaign_roots = layout.campaign_roots
    evidence_roots = layout.evidence_roots
    objects, class_counts, class_bytes = _semantic_inventory(root, campaign_roots, evidence_roots)
    registry = _registry_inventory(database)
    run_dirs = [
        resolve_recorded_path(item["output_dir"], project_root=root, layout=layout)
        for item in registry["runs"]
        if item.get("output_dir")
    ]
    lineage = lineage_coverage(run_dirs, project_root=root)
    generated_summaries = {
        path.parent.resolve()
        for evidence_root in evidence_roots
        for path in evidence_root.glob("*/*/*/*/campaign_test_summary.json")
    }
    registered_dirs = {path.resolve() for path in run_dirs}
    orphaned = sorted(_display(root, path) for path in generated_summaries - registered_dirs)
    missing_registered = sorted(_display(root, path) for path in registered_dirs if not path.exists())

    payloads: dict[str, list[Path]] = defaultdict(list)
    for evidence_root in evidence_roots:
        for label, paths in find_heavy_generated_payloads(evidence_root).items():
            payloads[label].extend(paths)
    redundant = [item for evidence_root in evidence_roots for item in find_redundant_runs(evidence_root)]
    junk = find_junk_paths(root)
    cleanup = build_cleanup_report(payloads, redundant, junk, applied=False)
    applied_cleanup = _read_json(
        root / "research_artifacts" / "cleanup" /
        f"repository_cleanup_{datetime.now().date().isoformat().replace('-', '')}.json"
    )
    deleted = _working_tree_deletions(root)
    stale = _registry_staleness(root, database)
    incomplete = [
        row for row in lineage["runs"]
        if row["recorded_verdict"] == "NEEDS MANUAL REVIEW" or not row["stages"]
    ]
    missing_lineage = [row for row in lineage["runs"] if row["lineage_verdict"] != "PASS"]
    lineage_report = {key: value for key, value in lineage.items() if key != "runs"}
    lineage_report["runs"] = [_run_brief(row) for row in lineage["runs"]]
    authored_campaigns = {
        path.name for campaign_root in campaign_roots if campaign_root.exists()
        for path in campaign_root.iterdir() if path.is_dir()
    }
    generated_campaigns = {
        path.name for evidence_root in evidence_roots if evidence_root.exists()
        for path in evidence_root.iterdir() if path.is_dir()
    }
    unmatched_generated_campaigns = sorted(generated_campaigns - authored_campaigns)

    verdict = "PASS"
    if any(row["lineage_verdict"] == "FAIL" for row in lineage["runs"]):
        verdict = "FAIL"
    elif missing_lineage or incomplete or orphaned or stale["stale"]:
        verdict = "NEEDS MANUAL REVIEW"
    return {
        "schema": "alphaquest.repository-rationalization/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "worktree": {
            "status": _git(root, "status", "--short", "--branch"),
            "uncommitted_deletions": deleted,
            "uncommitted_deletion_count": len(deleted),
            "deletion_assessment": (
                "No pre-existing uncommitted deletions were present at audit time."
                if not deleted
                else "Every deleted generated config requires individual provenance review before acceptance."
            ),
        },
        "counts": {
            "authored_campaigns": len(authored_campaigns),
            "generated_campaign_roots": len(generated_campaigns),
            "registered_variants": registry["variant_count"],
            "registered_attempts": registry["attempt_count"],
            "registered_runs": registry["run_count"],
            "ledger_rows": _csv_data_rows(root / "research_ledger.csv"),
            "semantic_objects": len(objects),
            "orphaned_run_summaries": len(orphaned),
            "missing_registered_run_dirs": len(missing_registered),
            "incomplete_or_interrupted_runs": len(incomplete),
            "lineage_manual_review_or_fail": len(missing_lineage),
        },
        "artifact_classes": {
            name: {"object_count": class_counts.get(name, 0), "bytes": class_bytes.get(name, 0)}
            for name in SEMANTIC_CLASSES
        },
        "objects": objects,
        "registry": {
            "database": _display(root, database),
            "staleness": stale,
            "registered_run_verdicts": registry["verdicts"],
            "campaign_lifecycle": registry["lifecycle"],
        },
        "lineage_coverage": lineage_report,
        "validation_coverage": lineage["validation_coverage"],
        "incomplete_runs": [_run_brief(row) for row in incomplete],
        "missing_lineage": {
            "count": len(missing_lineage),
            "run_uids": [row.get("run_uid") for row in missing_lineage],
        },
        "orphaned_or_unreferenced": {
            "run_summaries_not_in_registry": orphaned,
            "registered_dirs_missing_on_disk": missing_registered,
            "generated_campaigns_without_authored_campaign": unmatched_generated_campaigns,
        },
        "duplicate_and_superseded_candidates": {
            "exact_superseded_error_runs": [_json_safe(item) for item in redundant],
            "count": len(redundant),
        },
        "cleanup_dry_run": _json_safe(cleanup),
        "applied_cleanup": applied_cleanup or None,
        "retention_matrix": _retention_matrix(),
        "authoritative_boundaries": {
            "research/campaigns/active/": "active authored research definitions",
            "research/campaigns/archive/": "closed authored research definitions",
            "research/evidence/runs/": "generated immutable run evidence",
            "views/": "rebuildable human navigation; never authoritative",
            "research_artifacts/": "durable audits and decisions",
            "catalogs/": "rebuildable registry and exports; never result authority",
        },
        "repository_verdict": verdict,
        "verdict_reason": (
            "At least one run has mismatched or missing declared source evidence."
            if verdict == "FAIL"
            else "Historical lineage and manual validation coverage are incomplete; absence is not treated as proof of correctness."
            if verdict == "NEEDS MANUAL REVIEW"
            else "All inventoried governance checks are complete."
        ),
    }


def _semantic_inventory(
    root: Path, campaign_roots: tuple[Path, ...], evidence_roots: tuple[Path, ...]
) -> tuple[list[dict[str, Any]], Counter, Counter]:
    objects: list[dict[str, Any]] = []
    counts: Counter = Counter()
    sizes: Counter = Counter()

    def add(path: Path, artifact_class: str, reason: str) -> None:
        size = _tree_size(path)
        objects.append({"path": _display(root, path), "artifact_class": artifact_class, "size_bytes": size, "reason": reason})
        counts[artifact_class] += 1
        sizes[artifact_class] += size

    for campaign in sorted(
        path for campaign_root in campaign_roots if campaign_root.exists()
        for path in campaign_root.iterdir() if path.is_dir()
    ):
        add(campaign / "campaign.yaml", "authored research definition", "campaign hypothesis and source definition")
        for config in sorted((campaign / "variants").glob("*/config.yaml")):
            add(config, "authored research definition", "original predeclared executable variant config")
            modules = config.parent / "strategy_modules"
            if modules.exists():
                add(modules, "invariant variant mechanics", "authored entry, stop, and target bindings")
        for config in sorted((campaign / "rescue_attempts").glob("*/*/config.yaml")):
            add(config, "rescue attempt", "explicit authored post-failure attempt; never merged into the original")
        if (campaign / "results_index.yaml").is_file():
            add(campaign / "results_index.yaml", "generated navigation/projection", "rebuildable source-to-run pointer")

    for summary in sorted(
        path for evidence_root in evidence_roots if evidence_root.exists()
        for path in evidence_root.glob("*/*/*/*/campaign_test_summary.json")
    ):
        run_dir = summary.parent
        complete = (run_dir / "run_manifest.json").is_file() and (
            (run_dir / "effective_config.yaml").is_file() or (run_dir / "source_config.yaml").is_file()
        )
        add(
            run_dir,
            "generated authoritative evidence" if complete else "interrupted/incomplete run",
            "registered run root with immutable evidence" if complete else "run root lacks terminal lineage artifacts",
        )
        add(summary, "compact terminal summary", "strict run-stage and verdict summary")

    for path in sorted((root / "research_artifacts").rglob("*")):
        if path.is_file():
            add(path, "generated authoritative evidence", "durable audit or research decision")
    for directory in (root / "views", root / "catalogs"):
        if directory.exists():
            add(directory, "generated navigation/projection", "rebuildable registry, export, or human navigation")
    for directory in (root / ".pytest_cache", root / ".ruff_cache"):
        if directory.exists():
            add(directory, "cache", "rebuildable tool cache")
    file_counts, file_sizes = _file_class_totals(root)
    return objects, file_counts, file_sizes


def _file_class_totals(root: Path) -> tuple[Counter, Counter]:
    counts: Counter = Counter()
    sizes: Counter = Counter()
    for base_name in ("research", "views", "catalogs", "research_artifacts", "data", "_archived"):
        base = root / base_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            artifact_class = _classify_file(path.relative_to(root))
            counts[artifact_class] += 1
            sizes[artifact_class] += path.stat().st_size
    for cache in (root / ".pytest_cache", root / ".ruff_cache"):
        if cache.exists():
            for path in cache.rglob("*"):
                if path.is_file():
                    counts["cache"] += 1
                    sizes["cache"] += path.stat().st_size
    return counts, sizes


def _classify_file(relative: Path) -> str:
    parts = relative.parts
    value = str(relative)
    name = relative.name
    if parts[:2] == ("research", "campaigns"):
        if "rescue_attempts" in parts:
            return "rescue attempt"
        if "strategy_modules" in parts:
            return "invariant variant mechanics"
        if name in {"results_index.yaml", "runs_index.csv"}:
            return "generated navigation/projection"
        return "authored research definition"
    if parts[0] in {"views", "catalogs"}:
        return "generated navigation/projection"
    if parts[0] == "data":
        return "cache" if "cache" in value or "generated" in parts else "generated authoritative evidence"
    if parts[0] == "research_artifacts":
        return "generated authoritative evidence"
    if parts[0] == "_archived":
        return "generated authoritative evidence"
    if parts[:2] == ("research", "evidence"):
        if name in {"campaign_test_summary.json", "variant_test_summary.json", "stage_result.json"}:
            return "compact terminal summary"
        if name.endswith(".html") or name in {
            "features_data.csv",
            "cleaned_data.csv",
            "monkey_results.csv",
            "wfa_oos_monkey_results.csv",
            "core_grid_iteration_trades.csv",
            "core_grid_iteration_daily.csv",
            "wfa_oos_monte_carlo_path_events.csv",
            "wfa_oos_monte_carlo_path_trades.csv",
        }:
            return "reproducible bulk output"
        return "generated authoritative evidence"
    return "unknown/manual-review required"


def _registry_inventory(database: Path) -> dict[str, Any]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        runs = [dict(row) for row in connection.execute("SELECT * FROM runs")]
        verdicts = dict(connection.execute("SELECT verdict, COUNT(*) FROM runs GROUP BY verdict").fetchall())
        lifecycle = dict(connection.execute("SELECT lifecycle_state, COUNT(*) FROM campaigns GROUP BY lifecycle_state").fetchall())
        return {
            "runs": runs,
            "run_count": len(runs),
            "variant_count": connection.execute("SELECT COUNT(*) FROM variants").fetchone()[0],
            "attempt_count": connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
            "verdicts": verdicts,
            "lifecycle": lifecycle,
        }


def _working_tree_deletions(root: Path) -> list[dict[str, Any]]:
    rows = []
    for line in _git(root, "diff", "--name-status", "HEAD").splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("D") and len(parts) > 1:
            path = parts[-1]
            rows.append({
                "path": path,
                "artifact_class": _classify_deleted_path(path),
                "only_durable_config_provenance": "NEEDS MANUAL REVIEW" if path.endswith(("source_config.yaml", "effective_config.yaml")) else False,
                "retention_decision": "manual_review",
                "reason": "uncommitted deletion detected; no restoration or finalization is automatic",
            })
    return rows


def _registry_staleness(root: Path, database: Path) -> dict[str, Any]:
    database_mtime = database.stat().st_mtime if database.is_file() else 0
    layout = load_storage_layout(root)
    watched = [
        path for base in (*layout.campaign_roots, *layout.evidence_roots) if base.exists()
        for path in base.rglob("*") if path.is_file() and path.name in {"campaign.yaml", "config.yaml", "campaign_test_summary.json", "run_manifest.json"}
    ]
    latest = max((path.stat().st_mtime for path in watched), default=0)
    return {
        "stale": not database.is_file() or latest > database_mtime,
        "database_mtime": datetime.fromtimestamp(database_mtime, tz=timezone.utc).isoformat() if database_mtime else None,
        "latest_source_or_evidence_mtime": datetime.fromtimestamp(latest, tz=timezone.utc).isoformat() if latest else None,
    }


def _retention_matrix() -> list[dict[str, str]]:
    return [
        {"artifact_class": "authored definitions and invariant mechanics", "decision": "KEEP", "reason": "irreplaceable source and mechanics lock"},
        {"artifact_class": "source/effective configs, manifests, hashes", "decision": "KEEP", "reason": "run provenance and reconciliation"},
        {"artifact_class": "terminal summaries, audits, fixed/OOS logs, Monte Carlo summaries", "decision": "KEEP", "reason": "compact authoritative evidence"},
        {"artifact_class": "interrupted or unknown runs", "decision": "KEEP + MANUAL REVIEW", "reason": "evidence until classified"},
        {"artifact_class": "views, registry, exports", "decision": "REGENERATE", "reason": "rebuildable navigation only"},
        {"artifact_class": "superseded but provenance-bearing material", "decision": "ARCHIVE", "reason": "preserve lineage while removing from active navigation"},
        {"artifact_class": "reproducible bulk payloads and caches", "decision": "DELETE VIA MANIFEST", "reason": "reconstructable from retained evidence"},
        {"artifact_class": "orphaned, referenced, or unknown objects", "decision": "MANUAL REVIEW", "reason": "fail closed; no deletion authority"},
    ]


def _markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lineage = report["lineage_coverage"]
    cleanup = report["cleanup_dry_run"]
    applied = report.get("applied_cleanup") or {}
    lines = [
        "# Research Repository Rationalization",
        "",
        f"Created: `{report['created_at']}`",
        "",
        "## Current Truth",
        "",
        f"- Authored campaigns: `{counts['authored_campaigns']}`",
        f"- Registered variants / attempts / runs: `{counts['registered_variants']}` / `{counts['registered_attempts']}` / `{counts['registered_runs']}`",
        f"- Research ledger rows: `{counts['ledger_rows']}`",
        f"- Incomplete or interrupted runs: `{counts['incomplete_or_interrupted_runs']}`",
        f"- Orphaned run summaries: `{counts['orphaned_run_summaries']}`",
        f"- Pre-existing uncommitted deletions: `{report['worktree']['uncommitted_deletion_count']}`",
        f"- Registry stale: `{report['registry']['staleness']['stale']}`",
        "",
        "The live checkout was inspected directly. Generated snapshots are treated as provenance only, never proof that a run was rerun.",
        "",
        "## Artifact Classes And Disk Use",
        "",
        "| Class | Objects | MiB |",
        "| --- | ---: | ---: |",
    ]
    for name, item in report["artifact_classes"].items():
        lines.append(f"| {name} | {item['object_count']} | {item['bytes'] / 1024**2:.1f} |")
    lines.extend(
        [
            "",
            "## Data Lineage And Validation Coverage",
            "",
            f"- Lineage verdicts: `{json.dumps(lineage['lineage_verdicts'], sort_keys=True)}`",
            f"- Validation coverage: `{json.dumps(lineage['validation_coverage'], sort_keys=True)}`",
            f"- Runs with incomplete lineage: `{counts['lineage_manual_review_or_fail']}`",
            "",
            "Missing historical evidence is classified as NEEDS MANUAL REVIEW. It is not backfilled and is not treated as proof that old data or mechanics were correct.",
            "",
            "## Duplicate, Incomplete, And Orphan Review",
            "",
            f"- Exact superseded error-run candidates: `{report['duplicate_and_superseded_candidates']['count']}`",
            f"- Missing registered run directories: `{counts['missing_registered_run_dirs']}`",
            f"- Generated campaigns without authored campaign: `{len(report['orphaned_or_unreferenced']['generated_campaigns_without_authored_campaign'])}`",
            "",
            "## Keep / Archive / Delete / Regenerate Matrix",
            "",
            "| Artifact class | Decision | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for row in report["retention_matrix"]:
        lines.append(f"| {row['artifact_class']} | {row['decision']} | {row['reason']} |")
    lines.extend(
        [
            "",
            "## Safe Cleanup Dry Run",
            "",
            f"- Candidate files/objects: `{cleanup['deleted_file_count']}`",
            f"- Candidate superseded runs: `{cleanup['removed_run_count']}`",
            f"- Reclaimable MiB: `{cleanup['reclaim_bytes'] / 1024**2:.1f}`",
            "",
            "The cleanup manifest records every deletion candidate before apply. Unknown, referenced, or provenance-bearing evidence is excluded.",
            f"- Applied cleanup status: `{applied.get('status') or 'not applied'}`",
            f"- Applied files removed: `{applied.get('deleted_file_count', 0)}`",
            f"- Applied reclaimed MiB: `{applied.get('reclaim_bytes', 0) / 1024**2:.1f}`",
            "",
            "## Repository Verdict",
            "",
            report["verdict_reason"],
            "",
            f"**{report['repository_verdict']}**",
            "",
        ]
    )
    return "\n".join(lines)


def _run_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_uid": row.get("run_uid"),
        "campaign_id": row.get("campaign_id"),
        "variant_id": row.get("variant_id"),
        "test_run_id": row.get("test_run_id"),
        "run_dir": row.get("run_dir"),
        "recorded_verdict": row.get("recorded_verdict"),
        "lineage_verdict": row.get("lineage_verdict"),
        "errors": row.get("errors"),
        "missing_evidence": row.get("missing_evidence"),
    }


def _classify_deleted_path(path: str) -> str:
    if path.startswith("campaigns/"):
        return "authored research definition"
    if path.endswith(("source_config.yaml", "effective_config.yaml")):
        return "generated authoritative evidence"
    if path.startswith("views/") or path.startswith("catalogs/"):
        return "generated navigation/projection"
    return "unknown/manual-review required"


def _csv_data_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    return result.stdout.strip()


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return _display(ROOT, value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
