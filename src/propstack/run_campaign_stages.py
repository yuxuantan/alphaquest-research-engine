from __future__ import annotations

import argparse

from propstack.research.campaign_stages import run_campaign_stage_tests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Variant YAML path.")
    parser.add_argument(
        "--out",
        help="Optional output directory. Defaults to the variant report root under campaign_tests/.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip cleaned/features validation CSVs for each staged data slice.",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue running later stages after a failed stage.",
    )
    args = parser.parse_args()
    summary = run_campaign_stage_tests(
        args.config,
        skip_validation=args.skip_validation,
        continue_on_failure=args.continue_on_failure,
        out_dir=args.out,
    )
    print(summary["output_dir"])
    print("passed" if summary["passed"] else "failed")


if __name__ == "__main__":
    main()
