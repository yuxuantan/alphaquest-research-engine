from __future__ import annotations

import argparse

from propstack.research.wfa import run_wfa
from propstack.run_backtest import prepare_data
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    wfa_cfg = campaign["wfa"]
    grid_cfg = campaign["grid"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("wfa", args.config, campaign)
    data, _ = prepare_data(campaign["data"], validation_dir(out))
    input_hash = file_sha256(campaign["data"]["raw_csv"])
    results, summary = run_wfa(data, campaign, grid_cfg, wfa_cfg, benchmarks)
    results.to_csv(out / "wfa_results.csv", index=False)
    write_json(out / "wfa_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "wfa", summary)
    print(out)


if __name__ == "__main__":
    main()
