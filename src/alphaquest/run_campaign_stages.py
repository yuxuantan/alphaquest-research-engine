from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphaquest.research.campaign_stages import run_campaign_stage_tests
from alphaquest.run_core import STRUCTURED_PROGRESS_PREFIX


def _structured_progress(update: dict) -> None:
    print(
        STRUCTURED_PROGRESS_PREFIX + json.dumps(update, sort_keys=True, separators=(",", ":")),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Authored campaign source config.yaml path.")
    parser.add_argument(
        "--out",
        help="Optional output directory. Defaults to the configured evidence root/{campaign_id}/{variant_id}/{symbol}/{run_id}/.",
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
    parser.add_argument(
        "--authoritative-parallel-workers",
        type=int,
        help="Apply result-invariant authoritative scheduling with this worker count.",
    )
    parser.add_argument(
        "--authoritative-core-grid-workers",
        type=int,
        help="Use this separate worker count for canonical core-grid session chunks.",
    )
    parser.add_argument(
        "--structured-progress",
        action="store_true",
        help="Emit machine-readable progress records for the owning Studio worker.",
    )
    parser.add_argument(
        "--result-json",
        help="Write the complete staged summary atomically to this path.",
    )
    args = parser.parse_args()
    summary = run_campaign_stage_tests(
        args.config,
        skip_validation=args.skip_validation or args.fast_runtime_defaults,
        continue_on_failure=args.continue_on_failure,
        out_dir=args.out,
        include_acceptance=not args.no_acceptance,
        fast_runtime_defaults=args.fast_runtime_defaults,
        authoritative_parallel_workers=args.authoritative_parallel_workers,
        authoritative_core_grid_workers=args.authoritative_core_grid_workers,
        progress_callback=_structured_progress if args.structured_progress else None,
    )
    if args.result_json:
        destination = Path(args.result_json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_text(
            json.dumps(summary, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(destination)
    print(summary["output_dir"])
    verdict = str(summary.get("research_verdict") or "").strip().upper()
    if verdict not in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}:
        verdict = "PASS" if summary["passed"] else "FAIL"
    print(verdict)


if __name__ == "__main__":
    main()
