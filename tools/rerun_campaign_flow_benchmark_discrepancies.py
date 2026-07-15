from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import traceback
from typing import Any

from alphaquest.research import campaign_stages as cs
from alphaquest.utils.config import load_yaml


CONFIG_CANDIDATES = (
    "source_config.yaml",
    "effective_config.yaml",
    "config_snapshot.yaml",
    "variant_config.yaml",
    "config.yaml",
)
DEFAULT_AUDIT_PATH = Path("research_artifacts/campaign_flow_benchmark_audit_20260621.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rerun campaign roots flagged by the benchmark-flow audit through the current staged runner."
    )
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=_default_output_path("json"),
        help="Rerun ledger JSON path.",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=_default_output_path("csv"),
        help="Rerun ledger CSV path.",
    )
    parser.add_argument("--limit", type=int, help="Limit processed roots for debugging.")
    parser.add_argument("--dry-run", action="store_true", help="Classify roots without running backtests.")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    records = rerun_from_audit(args.audit, limit=args.limit, dry_run=args.dry_run)
    write_records(records, args.json_out, args.csv_out)
    print_summary(records, args.json_out, args.csv_out)
    blocked = any(record["status"].startswith("blocked") for record in records)
    return 1 if args.fail_on_blocked and blocked else 0


def _default_output_path(suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return Path("research_artifacts") / f"campaign_flow_benchmark_rerun_{stamp}.{suffix}"


def rerun_from_audit(audit_path: Path, *, limit: int | None = None, dry_run: bool = False) -> list[dict[str, Any]]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    roots = sorted({issue["run_root"] for issue in audit.get("issues", []) if issue.get("run_root")})
    if limit is not None:
        roots = roots[:limit]

    records: list[dict[str, Any]] = []
    for root_text in roots:
        root = Path(root_text)
        record = classify_root(root)
        record["dry_run"] = dry_run
        if dry_run or record["status"] != "ready":
            records.append(record)
            continue
        records.append(rerun_root(record))
    return records


def classify_root(root: Path) -> dict[str, Any]:
    config_path = find_config(root)
    record: dict[str, Any] = {
        "root": str(root),
        "status": "ready",
        "config_path": str(config_path) if config_path else None,
        "started_at": None,
        "completed_at": None,
        "output_dir": None,
        "passed": None,
        "halted": None,
        "failed_stage": None,
        "error": None,
    }
    if config_path is None:
        record["status"] = "blocked_no_config"
        record["error"] = "no executable config found at flagged root"
        return record

    try:
        cfg = cs.canonicalize_campaign_config(load_yaml(config_path), include_acceptance=True)
        cs._validate_pre_test_mechanics_review(cfg, config_path)
        record["output_dir"] = str(output_dir_for(root, cfg, config_path))
    except Exception as exc:
        record["status"] = "blocked_pre_test_contract"
        record["error"] = str(exc)
    return record


def rerun_root(record: dict[str, Any]) -> dict[str, Any]:
    config_path = Path(record["config_path"])
    output_dir = Path(record["output_dir"])
    record = dict(record)
    record["started_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        summary = cs.run_campaign_stage_tests(
            config_path,
            skip_validation=True,
            continue_on_failure=False,
            out_dir=output_dir,
            include_acceptance=True,
            fast_runtime_defaults=True,
        )
    except Exception as exc:  # pragma: no cover - depends on local data/runtime
        record["status"] = "error"
        record["error"] = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        record["traceback"] = traceback.format_exc()
    else:
        record["status"] = "rerun_completed"
        record["passed"] = bool(summary.get("passed"))
        record["halted"] = bool(summary.get("halted"))
        record["failed_stage"] = first_failed_stage(summary.get("stages") or [])
        record["summary_path"] = str(output_dir / "campaign_test_summary.json")
        record["variant_summary_path"] = str(output_dir / "variant_test_summary.json")
    record["completed_at"] = datetime.now().isoformat(timespec="seconds")
    return record


def find_config(root: Path) -> Path | None:
    for name in CONFIG_CANDIDATES:
        path = root / name
        if path.is_file():
            return path
    return None


def output_dir_for(root: Path, cfg: dict[str, Any], config_path: Path) -> Path:
    if is_current_run_root(root):
        return root
    run_id = f"archive_flow_rerun_{datetime.now().strftime('%Y%m%d')}_{short_hash(str(root))}"
    symbol = str((cfg.get("data") or {}).get("symbol") or cfg.get("symbol") or "UNKNOWN")
    return Path("backtest-campaigns") / str(cfg["campaign_id"]) / str(cfg["variant_id"]) / symbol / run_id


def is_current_run_root(root: Path) -> bool:
    parts = root.parts
    if "backtest-campaigns" not in parts:
        return False
    index = len(parts) - 1 - list(reversed(parts)).index("backtest-campaigns")
    return len(parts[index + 1 :]) == 4


def first_failed_stage(stages: list[dict[str, Any]]) -> str | None:
    for stage in stages:
        if stage.get("status") in {"failed", "error"} or stage.get("passed") is False:
            return str(stage.get("stage") or "")
    return None


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def write_records(records: list[dict[str, Any]], json_out: Path, csv_out: Path) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "records": records,
        "summary": summary_counts(records),
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    fields = [
        "status",
        "root",
        "config_path",
        "output_dir",
        "passed",
        "halted",
        "failed_stage",
        "error",
        "started_at",
        "completed_at",
    ]
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    with csv_out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def summary_counts(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return {"total_roots": len(records), "status_counts": dict(sorted(counts.items()))}


def print_summary(records: list[dict[str, Any]], json_out: Path, csv_out: Path) -> None:
    summary = summary_counts(records)
    print(f"roots processed: {summary['total_roots']}")
    for status, count in summary["status_counts"].items():
        print(f"  {status}: {count}")
    print(f"wrote {json_out}")
    print(f"wrote {csv_out}")


if __name__ == "__main__":
    raise SystemExit(main())
