from __future__ import annotations

from datetime import datetime
import csv
import json
from pathlib import Path
import shutil
from typing import Any

from alphaquest.utils.config import update_runs_index, write_json


AUDIT_PATH = Path("research_artifacts/invalid_config_run_cleanup_20260621.json")

INVALID_RUN_ROOTS = [
    {
        "root": "backtest-campaigns/es_market_plumbing_liquidity_capacity/dealer_lending_pressure_long_1130/ES/run1",
        "reason": "unsupported generated data.feature_set market_plumbing_priority_lag1_no_lookahead; source/run2 uses feature_set none",
    },
    {
        "root": "backtest-campaigns/es_market_plumbing_liquidity_capacity/dealer_lending_pressure_long_1330/ES/run1",
        "reason": "unsupported generated data.feature_set market_plumbing_priority_lag1_no_lookahead; source/run2 uses feature_set none",
    },
    {
        "root": "backtest-campaigns/es_market_plumbing_liquidity_capacity/dual_pressure_priority_long_1130/ES/run1",
        "reason": "unsupported generated data.feature_set market_plumbing_priority_lag1_no_lookahead; source/methodology-fix run uses feature_set none",
    },
    {
        "root": "backtest-campaigns/es_market_plumbing_liquidity_capacity/vx_oi_crowding_short_1330/ES/run1",
        "reason": "unsupported generated data.feature_set market_plumbing_priority_lag1_no_lookahead; source/run2 uses feature_set none",
    },
    {
        "root": "backtest-campaigns/es_market_plumbing_liquidity_capacity/vx_oi_stress_long_1330/ES/run1",
        "reason": "unsupported generated data.feature_set market_plumbing_priority_lag1_no_lookahead; source/run2 uses feature_set none",
    },
    {
        "root": "backtest-campaigns/es_opening_drive_inventory_absorption/open60_flow_continuation_1130/ES/rescue1",
        "reason": "stale generated rescue has target_r_multiple 0.75; authored source/rescue configs use target_r_multiple >= 1.0",
    },
    {
        "root": "backtest-campaigns/es_orderflow_absorption_exhaustion_reversal/late_morning_15m_absorption_fade_1130/ES/run1",
        "reason": "stale generated run has target_r_multiple 0.75; authored source config uses target_r_multiple >= 1.0",
    },
    {
        "root": "backtest-campaigns/es_semivariance_orderflow_confirmation/badvol_signed_multitime_short/ES/rescue1",
        "reason": "stale generated rescue has target_r_multiple 0.75; authored source config uses target_r_multiple >= 1.0",
    },
    {
        "root": "backtest-campaigns/es_vpin_toxicity_continuation/slow_bucket_toxicity_long_1330/ES/run1",
        "reason": "stale generated WFA run has target_r_multiple 0.75; authored source config uses target_r_multiple >= 1.0",
    },
]


def main() -> int:
    deleted = []
    deleted_roots = [Path(item["root"]) for item in INVALID_RUN_ROOTS]
    affected_es_roots = {root.parent for root in deleted_roots}
    affected_campaign_roots = {Path(*root.parts[:2]) for root in deleted_roots if len(root.parts) >= 2}

    for item in INVALID_RUN_ROOTS:
        root = Path(item["root"])
        event = {
            **item,
            "existed": root.exists(),
            "file_count": sum(1 for path in root.rglob("*") if path.is_file()) if root.exists() else 0,
        }
        if root.exists():
            shutil.rmtree(root)
            event["deleted"] = True
        else:
            event["deleted"] = False
        deleted.append(event)

    rebuilt_indexes = rebuild_runs_indexes(affected_es_roots)
    summary_updates = scrub_campaign_summaries(affected_campaign_roots, deleted_roots)
    csv_updates = scrub_campaign_csvs(affected_campaign_roots, deleted_roots)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disposition": "deleted_invalid_generated_run_roots_kept_valid_authored_variants",
        "deleted_runs": deleted,
        "rebuilt_runs_indexes": rebuilt_indexes,
        "summary_updates": summary_updates,
        "csv_updates": csv_updates,
    }
    write_json(AUDIT_PATH, report)
    print(f"deleted={sum(1 for item in deleted if item['deleted'])}")
    print(f"rebuilt_runs_indexes={len(rebuilt_indexes)}")
    print(f"summary_updates={len(summary_updates)}")
    print(f"csv_updates={len(csv_updates)}")
    print(f"wrote {AUDIT_PATH}")
    return 0


def rebuild_runs_indexes(es_roots: set[Path]) -> list[dict[str, Any]]:
    out = []
    for es_root in sorted(es_roots):
        index_path = es_root / "runs_index.csv"
        if index_path.exists():
            index_path.unlink()
        rebuilt_from = []
        for run_dir in sorted(path for path in es_root.iterdir() if path.is_dir()):
            if (run_dir / "variant_test_summary.json").exists():
                update_runs_index(run_dir)
                rebuilt_from.append(str(run_dir))
        out.append({"path": str(index_path), "runs": rebuilt_from, "row_count": len(rebuilt_from)})
    return out


def scrub_campaign_summaries(campaign_roots: set[Path], deleted_roots: list[Path]) -> list[dict[str, Any]]:
    updates = []
    deleted_strings = [str(root) for root in deleted_roots]
    for campaign_root in sorted(campaign_roots):
        path = campaign_root / "campaign_test_summary.json"
        if not path.exists():
            continue
        payload = read_json(path)
        before = json.dumps(payload, sort_keys=True, default=str)

        cleanup = payload.setdefault("invalid_config_cleanup_20260621", {})
        cleanup.pop("deleted_generated_run_roots", None)
        relevant_deleted = [root for root in deleted_strings if root.startswith(f"{campaign_root}/")]
        cleanup["deleted_generated_run_count"] = len(relevant_deleted)
        cleanup["audit_path"] = str(AUDIT_PATH)
        cleanup["reason"] = "Generated run root failed current config/methodology validation; valid authored variants remain."
        cleanup["updated_at"] = datetime.now().isoformat(timespec="seconds")

        if isinstance(payload.get("results"), list):
            payload["results"] = [item for item in payload["results"] if not contains_deleted_root(item, deleted_strings)]
            if all(isinstance(item, dict) for item in payload["results"]):
                payload["original_runs"] = sum(1 for item in payload["results"] if str(item.get("run_id", "")).startswith("run"))
                payload["rescue_runs"] = sum(1 for item in payload["results"] if "rescue" in str(item.get("run_id", "")))

        for key in ("best_original", "best_rescue"):
            if key in payload and contains_deleted_root(payload[key], deleted_strings):
                payload[key] = None

        after = json.dumps(payload, sort_keys=True, default=str)
        if after != before:
            write_json(path, payload)
            updates.append({"path": str(path)})
    return updates


def scrub_campaign_csvs(campaign_roots: set[Path], deleted_roots: list[Path]) -> list[dict[str, Any]]:
    updates = []
    deleted_strings = [str(root) for root in deleted_roots]
    for campaign_root in sorted(campaign_roots):
        for path in sorted(campaign_root.glob("*.csv")):
            removed = remove_csv_rows_containing(path, deleted_strings)
            if removed:
                updates.append({"path": str(path), "removed_rows": removed})
    return updates


def remove_csv_rows_containing(path: Path, needles: list[str]) -> int:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if not rows:
        return 0
    kept = [rows[0]]
    removed = 0
    for row in rows[1:]:
        text = "\n".join(row)
        if any(needle in text for needle in needles):
            removed += 1
        else:
            kept.append(row)
    if removed:
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerows(kept)
    return removed


def contains_deleted_root(value: Any, deleted_strings: list[str]) -> bool:
    text = json.dumps(value, sort_keys=True, default=str)
    return any(root in text for root in deleted_strings)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
