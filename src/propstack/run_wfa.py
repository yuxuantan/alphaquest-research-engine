from __future__ import annotations

import argparse

from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.research.wfa import run_wfa
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.reports import market_timezone, write_report_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip writing cleaned/features validation CSVs before the run. Recommended for repeated full-history WFA runs.",
    )
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    wfa_cfg = campaign["wfa"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("wfa", args.config, campaign)
    subset = subset_from_config(campaign, "wfa")
    output_dir = None if args.skip_validation else validation_dir(out)
    print("Preparing WFA data...", flush=True)
    data, _ = prepare_data(
        campaign["data"],
        output_dir,
        subset,
        status_callback=_print_status,
        show_progress=True,
    )
    print(f"Prepared {len(data):,} bars. Starting walk-forward analysis...", flush=True)
    results, summary, trades = run_wfa(
        data,
        campaign,
        wfa_cfg,
        benchmarks,
        include_trade_log=True,
        train_grid_dir=out,
    )
    report_timezone = market_timezone(campaign)
    trade_log_path = out / "wfa_oos_trade_log.csv"
    summary["stitched_oos_trade_log"] = str(trade_log_path)
    write_report_csv(results, out / "wfa_results.csv", report_timezone, index=False)
    write_report_csv(trades, trade_log_path, report_timezone, index=False)
    write_json(out / "wfa_summary.json", summary)
    print("Recording input data hash and run metadata...", flush=True)
    input_hash = data_source_hash(campaign["data"], subset)
    record_campaign_result(out, campaign, args.config, input_hash, "wfa", summary)
    print(out)


def _print_status(message: str) -> None:
    print(message, flush=True)


if __name__ == "__main__":
    main()
