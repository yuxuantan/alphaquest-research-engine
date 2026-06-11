from __future__ import annotations

import argparse

from propstack.data.sierra_orderflow import build_sierra_orderflow_cache


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build 1-minute ES bar-level orderflow cache from Sierra Chart CSV/TXT exports."
    )
    parser.add_argument("--raw-path", required=True, help="Sierra export file or directory of CSV/TXT exports.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path for 1-minute orderflow bars.")
    parser.add_argument("--input-timezone", default="America/New_York", help="Timezone used in the Sierra export.")
    parser.add_argument("--output-timezone", default="America/New_York", help="Timezone to write into the cache.")
    parser.add_argument("--symbol", default="ES", help="Backtest/root symbol to write.")
    parser.add_argument("--contract-symbol", help="Optional contract symbol override for all input files.")
    parser.add_argument("--rth-start", default="09:30:00")
    parser.add_argument("--rth-end", default="16:00:00")
    parser.add_argument("--complete-session-end", default="15:59:00")
    parser.add_argument(
        "--active-contract-mode",
        choices=["none", "dominant_session_volume"],
        default="none",
        help="Use dominant_session_volume only when a directory contains overlapping outright contracts.",
    )
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    args = parser.parse_args()

    build_sierra_orderflow_cache(
        raw_path=args.raw_path,
        output_csv=args.out_csv,
        input_timezone=args.input_timezone,
        output_timezone=args.output_timezone,
        root_symbol=args.symbol,
        contract_symbol=args.contract_symbol,
        rth_start=args.rth_start,
        rth_end=args.rth_end,
        complete_session_end=args.complete_session_end or None,
        active_contract_mode=args.active_contract_mode,
        chunksize=args.chunksize,
        status_callback=print,
    )


if __name__ == "__main__":
    main()
