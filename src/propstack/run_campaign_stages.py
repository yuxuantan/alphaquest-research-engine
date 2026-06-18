from __future__ import annotations

import argparse

from propstack.research.campaign_stages import run_campaign_stage_tests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Authored campaign source config.yaml path.")
    parser.add_argument(
        "--out",
        help="Optional output directory. Defaults to backtest-campaigns/{campaign_id}/{variant_id}/{symbol}/{run_id}/.",
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
    parser.add_argument(
        "--no-acceptance",
        action="store_true",
        help="Skip acceptance_oos_test in this staged run.",
    )
    parser.add_argument(
        "--fast-runtime-defaults",
        action="store_true",
        help="Apply parallel runtime defaults and skip staged validation outputs.",
    )
    args = parser.parse_args()
    summary = run_campaign_stage_tests(
        args.config,
        skip_validation=args.skip_validation or args.fast_runtime_defaults,
        continue_on_failure=args.continue_on_failure,
        out_dir=args.out,
        include_acceptance=not args.no_acceptance,
        fast_runtime_defaults=args.fast_runtime_defaults,
    )
    print(summary["output_dir"])
    print("passed" if summary["passed"] else "failed")


if __name__ == "__main__":
    main()
