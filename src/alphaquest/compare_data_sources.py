from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from alphaquest.data.compare_sources import (
    compare_ohlcv_sources,
    infer_bounds_from_csv,
    load_databento_all_contract_bars,
    load_csv_bars,
    load_databento_bars,
)
from alphaquest.data.load import filter_timestamp_bounds


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Rithmic/MotiveWave CSV bars with Databento DBN bars.")
    parser.add_argument("--csv", default="data/raw/ES/es_1m_20221201-20260529.csv")
    parser.add_argument("--dbn-dir", default="data/raw/ES/GLBX-20260601-U6S3S4F4GM")
    parser.add_argument("--cache-dir")
    parser.add_argument("--out", default="data/reports/data_compare/ES/rithmic_vs_databento_1m")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--start-timestamp")
    parser.add_argument("--end-timestamp")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument(
        "--continuous-contract",
        default="dominant_session_volume",
        choices=["dominant_session_volume", "session_volume", "explicit_roll_calendar", "none"],
    )
    parser.add_argument("--roll-calendar")
    parser.add_argument("--price-tolerance", type=float, default=0.0)
    parser.add_argument("--volume-tolerance", type=float, default=0.0)
    parser.add_argument("--detail-limit", type=int, default=100_000)
    parser.add_argument("--skip-alternate-contract-check", action="store_true")
    args = parser.parse_args()

    if args.continuous_contract == "explicit_roll_calendar" and not args.roll_calendar:
        parser.error("--roll-calendar is required with --continuous-contract explicit_roll_calendar")

    session_config = {
        "symbol": args.symbol,
        "timezone": args.timezone,
        "exchange_timezone": args.timezone,
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "eth_start": "16:00:00",
        "eth_end": "09:29:00",
    }
    csv_config = {
        **session_config,
        "csv_format": "yyyymmdd_hhmmss_ohlcv",
        "has_header": False,
        "timestamp_format": "%Y%m%d %H%M%S",
    }
    dbn_config = {
        **session_config,
        "source": "databento_dbn",
        "raw_dir": args.dbn_dir,
        "cache_dir": args.cache_dir or str(Path("data/cache/databento") / Path(args.dbn_dir).name),
        "continuous_contract": args.continuous_contract,
        "include_spreads": False,
    }
    if args.roll_calendar:
        dbn_config["roll_calendar"] = args.roll_calendar

    explicit_bounds = _date_bounds_from_args(args)
    csv_df = load_csv_bars(args.csv, csv_config, date_bounds=explicit_bounds)
    bounds = explicit_bounds or infer_bounds_from_csv(csv_df)
    if explicit_bounds is None:
        csv_df = filter_timestamp_bounds(csv_df, bounds, args.timezone).reset_index(drop=True)
    dbn_df = load_databento_bars(dbn_config, date_bounds=bounds)
    dbn_all_contracts_df = None
    if not args.skip_alternate_contract_check:
        dbn_all_contracts_df = load_databento_all_contract_bars(dbn_config, date_bounds=bounds)

    summary = compare_ohlcv_sources(
        csv_df,
        dbn_df,
        args.out,
        price_tolerance=args.price_tolerance,
        volume_tolerance=args.volume_tolerance,
        detail_limit=args.detail_limit,
        dbn_all_contracts_df=dbn_all_contracts_df,
    )
    print(args.out)
    print(pd.Series(summary).to_string())


def _date_bounds_from_args(args) -> dict | None:
    bounds = {}
    if args.start_timestamp:
        bounds["start_timestamp"] = args.start_timestamp
    elif args.start_date:
        bounds["start_date"] = args.start_date
    if args.end_timestamp:
        bounds["end_timestamp"] = args.end_timestamp
    elif args.end_date:
        bounds["end_date"] = args.end_date
    return bounds or None


if __name__ == "__main__":
    main()
