from __future__ import annotations

import argparse

from propstack.data.pipeline import prepare_data
from propstack.research.monkey import run_monkey
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, write_json
from propstack.utils.hashing import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    monkey_cfg = campaign["monkey"]
    benchmarks = campaign.get("benchmarks", {})
    out = create_run_dir("monkey", args.config, campaign)
    data, _ = prepare_data(campaign["data"], validation_dir(out))
    input_hash = file_sha256(campaign["data"]["raw_csv"])
    results, summary = run_monkey(data, campaign, monkey_cfg, benchmarks)
    results.to_csv(out / "monkey_results.csv", index=False)
    write_json(out / "monkey_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "monkey", summary)
    print(out)


if __name__ == "__main__":
    main()
