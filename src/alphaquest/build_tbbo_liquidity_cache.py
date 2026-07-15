from __future__ import annotations

import argparse

from alphaquest.data.tbbo_liquidity import build_tbbo_liquidity_cache


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build 1-minute ES top-of-book liquidity bars from Databento TBBO DBN files."
    )
    parser.add_argument("--raw-dir", required=True, help="Directory containing *.tbbo.dbn.zst files.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path for 1-minute liquidity bars.")
    parser.add_argument("--monthly-cache-dir", help="Optional parquet cache directory for per-file aggregated bars.")
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--contract-symbol-regex", default=r"^ES[HMUZ]\d$")
    parser.add_argument("--rth-start", default="09:30:00")
    parser.add_argument("--rth-end", default="16:00:00")
    parser.add_argument("--complete-session-end", default="15:59:00")
    parser.add_argument("--windows", default="3,5", help="Comma-separated rolling quote-liquidity windows.")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--depth-floor", type=float, default=1.0)
    parser.add_argument("--force", action="store_true", help="Ignore per-file parquet cache and rebuild.")
    args = parser.parse_args()

    build_tbbo_liquidity_cache(
        raw_dir=args.raw_dir,
        output_csv=args.out_csv,
        monthly_cache_dir=args.monthly_cache_dir,
        timezone=args.timezone,
        root_symbol=args.root_symbol,
        contract_symbol_regex=args.contract_symbol_regex,
        rth_start=args.rth_start,
        rth_end=args.rth_end,
        complete_session_end=args.complete_session_end or None,
        windows=_csv_ints(args.windows),
        tick_size=args.tick_size,
        depth_floor=args.depth_floor,
        force=args.force,
        status_callback=print,
    )


def _csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
