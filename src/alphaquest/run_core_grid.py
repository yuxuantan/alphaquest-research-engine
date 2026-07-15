from __future__ import annotations

import argparse

from alphaquest.backtest.equity_report import write_equity_report_from_trade_log
from alphaquest.data.pipeline import prepare_data
from alphaquest.data.source import data_source_hash
from alphaquest.data.subset import subset_from_config
from alphaquest.research.core_grid import run_core_grid
from alphaquest.utils.config import config_timeframe, create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from alphaquest.utils.reports import market_timezone, write_report_csv


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
    timeframe = config_timeframe(campaign)
    grid_cfg = campaign["core_grid"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("core_grid", args.config, campaign)
    subset = subset_from_config(campaign, "core_grid")
    output_dir = None if args.skip_validation else validation_dir(out)
    data, _, execution_data = prepare_data(
        campaign["data"],
        output_dir,
        subset,
        timeframe=timeframe,
        include_execution_data=True,
    )
    input_hash = data_source_hash(campaign["data"], subset)
    report_dir = out if grid_cfg.get("retain_iteration_reports", True) else None
    detail_data = execution_data if timeframe != "1m" else None
    results, summary = run_core_grid(data, campaign, grid_cfg, benchmarks, report_dir=report_dir, detail_data=detail_data)
    report_timezone = market_timezone(campaign)
    write_report_csv(results, out / "core_grid_results.csv", report_timezone, index=False)
    iteration_trades = out / "core_grid_iteration_trades.csv"
    if report_dir is not None and iteration_trades.exists():
        summary.update(
            write_equity_report_from_trade_log(
                iteration_trades,
                initial_balance=float(campaign.get("core", {}).get("initial_balance", 0.0)),
                timezone=report_timezone,
                title=(
                    f"{campaign.get('campaign_id', 'campaign')} / "
                    f"{campaign.get('variant_id', 'variant')} core grid equity curves"
                ),
                run_column="run_id",
            )
        )
    write_json(out / "core_grid_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "core_grid", summary)
    print(out)


if __name__ == "__main__":
    main()
