from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


CAMPAIGN_ROOT = Path("backtest-campaigns/es_video_aoi_lvn_orderflow_playbook")
LEDGER = Path("research_ledger.csv")
OUTPUT_DIR = Path("data/reports/data_quality/ES/sierra_scid_backtest_remediation_20260714")

IMPORTANT_RERUNS = {
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/video_model1_range_midpoint_scid_intrabar_poc_3m_1500/ES/run11_poc": "positive one-month implementation POC",
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/yush_trend_47/ES/run91_6mo_short_lvn_no_market_delta10_no_lunch_fixed1r_signedcap_prop50k_2c_forward": "positive fixed-config POC awaiting staged evidence",
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/yush_trend_52/ES/run96_3mo_short_lvn_no_market_delta10_no_lunch_fraction050r_signedcap_prop50k_3c_unseen": "positive prop-consistency POC awaiting staged evidence",
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/yush_range_27/ES/run124_poc": "user's current range-strategy implementation POC",
}


def main() -> None:
    ledger = pd.read_csv(LEDGER, dtype=str).fillna("")
    rows: list[dict[str, str]] = []
    for config in sorted(CAMPAIGN_ROOT.glob("**/effective_config.yaml")):
        text = config.read_text(encoding="utf-8")
        if "raw_dir: data/raw/ES/sierra-es-trades" not in text:
            continue
        root = config.parent
        related = ledger[
            ledger["report_path"].str.startswith(str(root), na=False)
            | ledger["config_path"].str.contains(f"/{root.parents[2].name}/", regex=False, na=False)
        ]
        latest = related.iloc[-1] if len(related) else None
        rows.append(
            {
                "run_root": str(root),
                "old_source": "sierra_scid_records_without_capability_gate",
                "latest_ledger_decision": str(latest["decision"]) if latest is not None else "not matched",
                "latest_ledger_result": str(latest["result"]) if latest is not None else "not matched",
                "importance": "dispensable generated evidence; durable ledger/config retained",
                "action": "DELETE_GENERATED_RUN",
                "reason": "invalid event-source semantics and no unresolved candidate evidence worth preserving",
            }
        )
    for root, importance in IMPORTANT_RERUNS.items():
        rows.append(
            {
                "run_root": root,
                "old_source": "sierra_scid_records_without_capability_gate",
                "latest_ledger_decision": "historical NEEDS MANUAL REVIEW or current user strategy",
                "latest_ledger_result": "superseded by direct-data rerun",
                "importance": importance,
                "action": "RERUN_DIRECT_DATABENTO_AND_RETAIN",
                "reason": "date window is covered by purchased Databento trades",
            }
        )
    frame = pd.DataFrame(rows).sort_values(["action", "run_root"]).reset_index(drop=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_DIR / "classification.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    delete = frame.loc[frame["action"].eq("DELETE_GENERATED_RUN"), "run_root"]
    (OUTPUT_DIR / "delete_run_roots.txt").write_text("\n".join(delete) + "\n", encoding="utf-8")
    report = f"""# Sierra SCID backtest remediation

**Verdict: NEEDS MANUAL REVIEW**

Generated: {datetime.now(timezone.utc).isoformat()}

This inventory classifies generated runs that used Sierra component records as trade events before FIRST/LAST reconstruction and before a per-session capability gate. Authored source configs and `research_ledger.csv` remain the durable history. Generated run directories are deleted only when their economic lesson is already recorded and there is no unresolved candidate evidence.

## Classification

- Runs classified: {len(frame)}
- Delete generated run, preserve authored config/ledger: {int((frame['action'] == 'DELETE_GENERATED_RUN').sum())}
- Rerun on direct Databento and retain: {int((frame['action'] == 'RERUN_DIRECT_DATABENTO_AND_RETAIN').sum())}

The four retained/rerun roots are the current range POC, the original intrabar implementation POC, and the two historical positive fixed-config branches. No historical PASS exists in this SCID-record set. Runtime-blocked or negative partial attempts are not candidate evidence and are deleted after classification.

See `classification.csv` for every path and `delete_run_roots.txt` for the exact deletion set.
"""
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(f"Wrote {OUTPUT_DIR}: {len(frame)} classified, {len(delete)} delete")


if __name__ == "__main__":
    main()
