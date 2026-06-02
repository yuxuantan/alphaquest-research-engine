from __future__ import annotations

import argparse

from propstack.backtest.engine import BacktestEngine
from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.reports import market_timezone, write_report_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    core_cfg = cfg.get("core", {})
    out = create_run_dir("core", args.config, cfg)
    subset = subset_from_config(cfg, "core")
    data, _ = prepare_data(cfg["data"], validation_dir(out), subset)
    input_hash = data_source_hash(cfg["data"], subset)
    result = BacktestEngine(cfg, show_progress=True).run(data)
    trades = result["trades"]
    report_timezone = market_timezone(cfg)
    write_report_csv(trades, out / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], out / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "data_subset": core_cfg.get("data_subset", {})}
    write_json(out / "metrics.json", metrics)
    if len(trades):
        sample = trades.head(20)
        random = trades.sample(min(20, len(trades)), random_state=1)
        sample = sample._append(random).drop_duplicates(subset=["trade_id"])
    else:
        sample = trades
    write_report_csv(sample, out / "sample_trades_for_tv_validation.csv", report_timezone, index=False)
    record_campaign_result(out, cfg, args.config, input_hash, "core", metrics)
    print(out)


if __name__ == "__main__":
    main()
