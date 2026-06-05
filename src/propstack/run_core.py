from __future__ import annotations

import argparse

from propstack.backtest.equity_report import write_equity_report
from propstack.backtest.engine import BacktestEngine
from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.utils.config import config_timeframe, create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
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
    cfg = load_yaml(args.config)
    timeframe = config_timeframe(cfg)
    core_cfg = cfg.get("core", {})
    out = create_run_dir("core", args.config, cfg)
    subset = subset_from_config(cfg, "core")
    output_dir = None if args.skip_validation else validation_dir(out)
    data, _, execution_data = prepare_data(
        cfg["data"],
        output_dir,
        subset,
        timeframe=timeframe,
        include_execution_data=True,
    )
    input_hash = data_source_hash(cfg["data"], subset)
    detail_data = execution_data if timeframe != "1m" else None
    result = BacktestEngine(cfg, show_progress=True).run(data, detail_data=detail_data)
    trades = result["trades"]
    report_timezone = market_timezone(cfg)
    write_report_csv(trades, out / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], out / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "data_subset": core_cfg.get("data_subset", {})}
    metrics.update(
        write_equity_report(
            trades,
            out,
            initial_balance=float(core_cfg.get("initial_balance", 0.0)),
            timezone=report_timezone,
            title=f"{cfg.get('campaign_id', 'campaign')} / {cfg.get('variant_id', 'variant')} core equity curve",
        )
    )
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
