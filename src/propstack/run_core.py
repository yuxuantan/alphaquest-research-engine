from __future__ import annotations

import argparse

from propstack.backtest.engine import BacktestEngine
from propstack.data.pipeline import prepare_data
from propstack.data.subset import apply_data_subset
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    core_cfg = cfg.get("core", {})
    out = create_run_dir("core", args.config, cfg)
    data, _ = prepare_data(cfg["data"], validation_dir(out))
    data = apply_data_subset(data, core_cfg.get("data_subset"))
    input_hash = file_sha256(cfg["data"]["raw_csv"])
    result = BacktestEngine(cfg, show_progress=True).run(data)
    trades = result["trades"]
    trades.to_csv(out / "trade_log.csv", index=False)
    result["daily"].to_csv(out / "daily_results.csv", index=False)
    metrics = {**result["metrics"], "data_subset": core_cfg.get("data_subset", {})}
    write_json(out / "metrics.json", metrics)
    if len(trades):
        sample = trades.head(20)
        random = trades.sample(min(20, len(trades)), random_state=1)
        sample = sample._append(random).drop_duplicates(subset=["trade_id"])
    else:
        sample = trades
    sample.to_csv(out / "sample_trades_for_tv_validation.csv", index=False)
    record_campaign_result(out, cfg, args.config, input_hash, "core", metrics)
    print(out)


if __name__ == "__main__":
    main()
