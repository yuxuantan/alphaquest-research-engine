from __future__ import annotations

import argparse
import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.prop.rules import PropRules
from propstack.research.monte_carlo import run_monte_carlo
from propstack.run_backtest import prepare_data
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    mc_cfg = {**campaign.get("benchmarks", {}), **campaign["monte_carlo"]}
    out = create_run_dir("monte_carlo", args.config, campaign)
    if mc_cfg.get("trade_log"):
        trades = pd.read_csv(mc_cfg["trade_log"])
        input_hash = file_sha256(mc_cfg["trade_log"])
    else:
        data, _ = prepare_data(campaign["data"], validation_dir(out))
        trades = BacktestEngine(campaign).run(data)["trades"]
        trades.to_csv(out / "source_trade_log.csv", index=False)
        input_hash = file_sha256(campaign["data"]["raw_csv"])
    rules = PropRules.from_dict(campaign.get("prop_rules", {}))
    results, summary = run_monte_carlo(trades, mc_cfg, rules)
    results.to_csv(out / "monte_carlo_results.csv", index=False)
    write_json(out / "monte_carlo_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "monte_carlo", summary)
    print(out)


if __name__ == "__main__":
    main()
