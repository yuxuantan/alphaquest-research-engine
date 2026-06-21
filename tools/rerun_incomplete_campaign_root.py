from __future__ import annotations

import argparse
import multiprocessing as mp
from pathlib import Path

from propstack.research.campaign_stages import run_campaign_stage_tests


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun an incomplete campaign run root in-place.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--config-name", default="source_config.yaml")
    args = parser.parse_args()

    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass

    root = args.root
    summary = run_campaign_stage_tests(
        root / args.config_name,
        skip_validation=True,
        continue_on_failure=False,
        out_dir=root,
        include_acceptance=True,
    )
    print(f"passed={summary.get('passed')} halted={summary.get('halted')}")
    for stage in summary.get("stages", []):
        print(f"{stage.get('stage')} {stage.get('status')} passed={stage.get('passed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
