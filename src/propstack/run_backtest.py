from __future__ import annotations

import argparse
import yaml

from propstack.backtest.engine import BacktestEngine
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.data.quality import save_pipeline_outputs
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256


def prepare_data(data_config: dict, output_dir=None):
    cleaned, quality_report, missing = clean_data(data_config)
    features = build_features(cleaned, data_config)
    if output_dir:
        save_pipeline_outputs(cleaned, features, quality_report, missing, output_dir)
    return features, quality_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    out = create_run_dir("backtest", args.config, cfg)
    data, quality_report = prepare_data(cfg["data"], validation_dir(out))
    input_hash = file_sha256(cfg["data"]["raw_csv"])
    result = BacktestEngine(cfg, show_progress=True).run(data)
    trades = result["trades"]
    trades.to_csv(out / "trade_log.csv", index=False)
    result["daily"].to_csv(out / "daily_results.csv", index=False)
    write_json(out / "metrics.json", result["metrics"])
    if len(trades):
        sample = trades.head(20)
        random = trades.sample(min(20, len(trades)), random_state=1)
        sample = sample._append(random).drop_duplicates(subset=["trade_id"])
    else:
        sample = trades
    sample.to_csv(out / "sample_trades_for_tv_validation.csv", index=False)
    record_campaign_result(out, cfg, args.config, input_hash, "backtest", result["metrics"])
    print(out)


if __name__ == "__main__":
    main()
