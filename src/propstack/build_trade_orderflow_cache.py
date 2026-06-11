from __future__ import annotations

import argparse

from propstack.data.databento_trades import build_trade_orderflow_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 1-minute ES trade-side orderflow cache from Databento trades DBN files.")
    parser.add_argument("--raw-dir", required=True, help="Directory containing *.trades.dbn.zst files.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path for 1-minute orderflow bars.")
    parser.add_argument("--monthly-cache-dir", help="Optional parquet cache directory for per-file aggregated bars.")
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--contract-symbol-regex", default=r"^ES[HMUZ]\d$")
    parser.add_argument("--rth-start", default="09:30:00")
    parser.add_argument("--rth-end", default="16:00:00")
    parser.add_argument("--complete-session-end", default="15:59:00")
    parser.add_argument("--large-trade-sizes", default="10,20", help="Comma-separated trade-size thresholds.")
    parser.add_argument("--force", action="store_true", help="Ignore per-file parquet cache and rebuild.")
    args = parser.parse_args()
    sizes = [int(value.strip()) for value in args.large_trade_sizes.split(",") if value.strip()]
    build_trade_orderflow_cache(
        raw_dir=args.raw_dir,
        output_csv=args.out_csv,
        monthly_cache_dir=args.monthly_cache_dir,
        timezone=args.timezone,
        root_symbol=args.root_symbol,
        contract_symbol_regex=args.contract_symbol_regex,
        rth_start=args.rth_start,
        rth_end=args.rth_end,
        complete_session_end=args.complete_session_end or None,
        large_trade_sizes=sizes,
        force=args.force,
        status_callback=print,
    )


if __name__ == "__main__":
    main()
