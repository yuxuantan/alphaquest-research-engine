from __future__ import annotations

import argparse
import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.prop.rules import PropRules
from propstack.research.monte_carlo import run_monte_carlo
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256
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
    mc_cfg = {**campaign.get("benchmarks", {}), **campaign["monte_carlo"]}
    out = create_run_dir("monte_carlo", args.config, campaign)
    if mc_cfg.get("trade_log"):
        trades = pd.read_csv(mc_cfg["trade_log"])
        input_hash = file_sha256(mc_cfg["trade_log"])
    else:
        subset = subset_from_config(campaign, "monte_carlo", fallback_sections=("core",))
        output_dir = None if args.skip_validation else validation_dir(out)
        data, _ = prepare_data(campaign["data"], output_dir, subset)
        trades = BacktestEngine(campaign).run(data)["trades"]
        write_report_csv(trades, out / "source_trade_log.csv", market_timezone(campaign), index=False)
        input_hash = data_source_hash(campaign["data"], subset)
    rules = PropRules.from_dict(campaign.get("prop_rules", {}))
    results, summary = run_monte_carlo(trades, mc_cfg, rules)
    write_report_csv(results, out / "monte_carlo_results.csv", market_timezone(campaign), index=False)
    write_json(out / "monte_carlo_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "monte_carlo", summary)
    print(out)


if __name__ == "__main__":
    main()
