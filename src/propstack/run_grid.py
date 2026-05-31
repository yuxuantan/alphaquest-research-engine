from __future__ import annotations

import argparse

from propstack.research.grid import run_grid
from propstack.run_backtest import prepare_data
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    grid_cfg = campaign["grid"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("grid", args.config, campaign)
    data, _ = prepare_data(campaign["data"], validation_dir(out))
    input_hash = file_sha256(campaign["data"]["raw_csv"])
    results, summary = run_grid(data, campaign, grid_cfg, benchmarks)
    results.to_csv(out / "grid_results.csv", index=False)
    write_json(out / "grid_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "grid", summary)
    print(out)


if __name__ == "__main__":
    main()
