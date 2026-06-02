from __future__ import annotations

import argparse

from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.research.core_grid import run_core_grid
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.reports import market_timezone, write_report_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip writing cleaned/features validation CSVs before the run.",
    )
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    grid_cfg = campaign["core_grid"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("core_grid", args.config, campaign)
    subset = subset_from_config(campaign, "core_grid")
    output_dir = None if args.skip_validation else validation_dir(out)
    data, _ = prepare_data(campaign["data"], output_dir, subset)
    input_hash = data_source_hash(campaign["data"], subset)
    report_dir = out if grid_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_core_grid(data, campaign, grid_cfg, benchmarks, report_dir=report_dir)
    write_report_csv(results, out / "core_grid_results.csv", market_timezone(campaign), index=False)
    write_json(out / "core_grid_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "core_grid", summary)
    print(out)


if __name__ == "__main__":
    main()
