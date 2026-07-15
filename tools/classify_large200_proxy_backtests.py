from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path("backtest-campaigns")
OUTPUT = Path("data/reports/data_quality/ES/sierra_large200_proxy_backtest_remediation_20260714")
DIRECT_EVENT_RERUNS = {
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/video_model1_range_midpoint_scid_intrabar_poc_3m_1500/ES/run11_poc",
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/yush_trend_47/ES/run91_6mo_short_lvn_no_market_delta10_no_lunch_fixed1r_signedcap_prop50k_2c_forward",
    "backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/yush_trend_52/ES/run96_3mo_short_lvn_no_market_delta10_no_lunch_fraction050r_signedcap_prop50k_3c_unseen",
}


def main() -> None:
    rows = []
    for config in sorted(ROOT.glob("**/effective_config.yaml")):
        text = config.read_text(encoding="utf-8")
        if "min_large200_record_volume:" not in text:
            continue
        root = str(config.parent)
        direct = root in DIRECT_EVENT_RERUNS and "source: databento_zip_trades" in text
        rows.append(
            {
                "run_root": root,
                "source_issue": "raw Sierra component-row >=200 proxy is not a reconstructed trade-event >=200 test",
                "action": "RETAIN_DIRECT_EVENT_RERUN" if direct else "DELETE_GENERATED_RUN",
                "reason": (
                    "intrabar large-event state is rebuilt from direct Databento trade messages"
                    if direct
                    else "historical ledger records the failed result; generated proxy-dependent evidence is invalid"
                ),
            }
        )
    frame = pd.DataFrame(rows).sort_values(["action", "run_root"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "classification.csv", index=False)
    delete = frame.loc[frame["action"].eq("DELETE_GENERATED_RUN"), "run_root"]
    (OUTPUT / "delete_run_roots.txt").write_text("\n".join(delete) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(
        "\n".join(
            [
                "# Sierra large-200 proxy backtest remediation",
                "",
                "**Verdict: FAIL**",
                "",
                f"Generated: {datetime.now(timezone.utc).isoformat()}",
                "",
                "The legacy cache classified an individual raw SCID component row with volume >=200 as a large trade. "
                "Databento comparison proved that FIRST/LAST component rows must first be reconstructed into one trade event; "
                "therefore completed-bar results that consume the legacy large200 fields are not valid evidence.",
                "",
                f"- Proxy-dependent generated runs deleted: {len(delete)}",
                f"- Direct-event reruns retained: {int((frame['action'] == 'RETAIN_DIRECT_EVENT_RERUN').sum())}",
                "- Authored campaign definitions and research ledger rows retained: yes",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}: {len(delete)} delete, {len(frame) - len(delete)} direct retain")


if __name__ == "__main__":
    main()
