from __future__ import annotations

import argparse

from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.research.monkey import run_monkey
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.reports import market_timezone, write_report_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    monkey_cfg = campaign["monkey"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("monkey", args.config, campaign)
    subset = subset_from_config(campaign, "monkey")
    data, _ = prepare_data(campaign["data"], validation_dir(out), subset)
    input_hash = data_source_hash(campaign["data"], subset)
    report_dir = out if monkey_cfg.get("retain_iteration_reports", False) else None
    results, summary = run_monkey(data, campaign, monkey_cfg, benchmarks, report_dir=report_dir)
    write_report_csv(results, out / "monkey_results.csv", market_timezone(campaign), index=False)
    write_json(out / "monkey_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "monkey", summary)
    print(out)


if __name__ == "__main__":
    main()
