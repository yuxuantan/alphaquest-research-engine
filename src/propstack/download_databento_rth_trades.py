from __future__ import annotations

import argparse
from pathlib import Path

from propstack.data.databento_rth_downloader import DownloadConfig
from propstack.data.databento_rth_downloader import build_download_plan
from propstack.data.databento_rth_downloader import download_rth_trades
from propstack.data.databento_rth_downloader import estimate_download_cost
from propstack.data.databento_rth_downloader import filter_available_sessions
from propstack.data.databento_rth_downloader import get_api_key
from propstack.data.databento_rth_downloader import get_dataset_conditions
from propstack.data.databento_rth_downloader import iter_rth_sessions
from propstack.data.databento_rth_downloader import write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download RTH-only Databento trades DBN files for ES futures. "
            "Uses one Databento API key from the selected environment variable."
        )
    )
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive end date, YYYY-MM-DD.")
    parser.add_argument("--out-dir", required=True, help="Directory for daily *.trades.dbn.zst files.")
    parser.add_argument("--api-key-env", default="DATABENTO_API_KEY")
    parser.add_argument("--dataset", default="GLBX.MDP3")
    parser.add_argument("--symbols", default="ES.FUT")
    parser.add_argument("--schema", default="trades")
    parser.add_argument("--stype-in", default="parent")
    parser.add_argument("--stype-out", default="instrument_id")
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--rth-start", default="09:30:00")
    parser.add_argument("--rth-end", default="16:00:00")
    parser.add_argument("--file-prefix", default="glbx-mdp3")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--request-rate-limit", type=float, default=50.0)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="Re-download files that already exist.")
    parser.add_argument(
        "--include-weekends",
        action="store_true",
        help="Include weekend dates. Usually unnecessary for RTH-only ES work.",
    )
    parser.add_argument(
        "--filter-dataset-condition",
        action="store_true",
        help="Call metadata.get_dataset_condition and keep only available/degraded dates.",
    )
    parser.add_argument(
        "--estimate-cost",
        choices=["none", "sample", "exact"],
        default="none",
        help="Estimate Databento cost before downloading.",
    )
    parser.add_argument("--sample-days", type=int, default=20)
    parser.add_argument(
        "--max-cost",
        type=float,
        help="Abort if the estimated cost exceeds this amount. Forces exact cost estimation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write manifest and print plan without downloading.",
    )
    parser.add_argument(
        "--manifest",
        help="Manifest JSON path. Defaults to <out-dir>/download_manifest.json.",
    )
    args = parser.parse_args()

    config = DownloadConfig(
        output_dir=Path(args.out_dir),
        dataset=args.dataset,
        symbols=args.symbols,
        schema=args.schema,
        stype_in=args.stype_in,
        stype_out=args.stype_out,
        timezone=args.timezone,
        file_prefix=args.file_prefix,
        workers=args.workers,
        request_rate_limit_per_sec=args.request_rate_limit,
        retries=args.retries,
        force=args.force,
    )
    estimate_mode = args.estimate_cost
    if args.max_cost is not None and estimate_mode != "exact":
        estimate_mode = "exact"
    needs_api_key = args.filter_dataset_condition or estimate_mode != "none" or not args.dry_run
    api_key = get_api_key(args.api_key_env) if needs_api_key else ""

    sessions = iter_rth_sessions(
        args.start_date,
        args.end_date,
        timezone=args.timezone,
        rth_start=args.rth_start,
        rth_end=args.rth_end,
        weekdays_only=not args.include_weekends,
    )
    print(f"Built {len(sessions):,} candidate RTH sessions.")

    if args.filter_dataset_condition:
        conditions = get_dataset_conditions(
            api_key=api_key,
            dataset=args.dataset,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        sessions = filter_available_sessions(sessions, conditions)
        print(f"Dataset-condition filter kept {len(sessions):,} sessions.")

    planned = build_download_plan(sessions, config)
    print(f"Download plan contains {len(planned):,} missing/new sessions.")

    cost_estimate = None
    if estimate_mode != "none":
        cost_estimate = estimate_download_cost(
            planned,
            api_key=api_key,
            config=config,
            mode=estimate_mode,
            sample_days=args.sample_days,
            status_callback=print,
        )
        print(f"Estimated Databento cost: ${cost_estimate['estimated_cost']:.2f}")
        if cost_estimate.get("samples"):
            print("Sampled session costs:")
            for sample in cost_estimate["samples"]:
                print(f"  {sample['date']}: ${sample['cost']:.4f}")
            print(f"Average sampled session cost: ${cost_estimate['average_session_cost']:.4f}")
        if args.max_cost is not None and cost_estimate["estimated_cost"] > args.max_cost:
            manifest = Path(args.manifest) if args.manifest else config.output_dir / "download_manifest.json"
            write_manifest(
                manifest,
                config=config,
                requested_sessions=sessions,
                planned_sessions=planned,
                cost_estimate=cost_estimate,
            )
            raise SystemExit(
                f"Aborting: estimated cost ${cost_estimate['estimated_cost']:.2f} "
                f"exceeds --max-cost ${args.max_cost:.2f}."
            )

    manifest = Path(args.manifest) if args.manifest else config.output_dir / "download_manifest.json"
    if args.dry_run:
        write_manifest(
            manifest,
            config=config,
            requested_sessions=sessions,
            planned_sessions=planned,
            cost_estimate=cost_estimate,
        )
        print(f"Dry run complete. Wrote {manifest}")
        return

    results = download_rth_trades(planned, api_key=api_key, config=config, status_callback=print)
    write_manifest(
        manifest,
        config=config,
        requested_sessions=sessions,
        planned_sessions=planned,
        results=results,
        cost_estimate=cost_estimate,
    )
    downloaded = sum(1 for row in results if row["status"] == "downloaded")
    skipped = sum(1 for row in results if row["status"] == "skipped")
    failed = sum(1 for row in results if row["status"] == "failed")
    print(f"Done. downloaded={downloaded:,} skipped={skipped:,} failed={failed:,}")
    print(f"Wrote {manifest}")


if __name__ == "__main__":
    main()
