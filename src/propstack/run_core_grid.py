from __future__ import annotations

import argparse

from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.research.core_grid import run_core_grid
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    grid_cfg = campaign["core_grid"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("core_grid", args.config, campaign)
    subset = subset_from_config(campaign, "core_grid")
    data, _ = prepare_data(campaign["data"], validation_dir(out), subset)
    input_hash = data_source_hash(campaign["data"], subset)
    report_dir = out if grid_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_core_grid(data, campaign, grid_cfg, benchmarks, report_dir=report_dir)
    results.to_csv(out / "core_grid_results.csv", index=False)
    write_json(out / "core_grid_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "core_grid", summary)
    print(out)


if __name__ == "__main__":
    main()
