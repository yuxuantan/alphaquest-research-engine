from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from propstack.data.footprint import FOOTPRINT_FEATURE_COLUMNS, add_footprint_imbalance_features
from tools.build_sierra_trade_orderflow_cache import (
    PRINT_COLUMNS,
    RTH_START_MINUTE,
    active_periods,
    datetime_to_scid_us,
    is_bar_like_contract,
    new_york_datetime_to_scid_us,
    scid_us_to_new_york_datetime,
)


def main() -> None:
    args = parse_args()
    base = pd.read_parquet(args.base_cache)
    if args.start_date:
        base = base[base["timestamp"] >= pd.Timestamp(args.start_date)].copy()
    if args.end_date:
        base = base[base["timestamp"] <= pd.Timestamp(args.end_date) + pd.Timedelta(days=1)].copy()
    if base.empty:
        raise SystemExit("Base cache selection is empty.")
    if args.bar_minutes > 1:
        base = aggregate_base_bars(base, bar_minutes=args.bar_minutes)

    files = {path.stem.replace("-CME", ""): path for path in args.raw_dir.glob("*.parquet")}
    periods = active_periods(args.roll_calendar, files, args.root_symbol)
    periods = _filter_periods(periods, base["timestamp"].min(), base["timestamp"].max())
    if not periods:
        raise SystemExit("No active raw Sierra periods overlap the selected base cache range.")

    feature_parts = []
    period_reports = []
    for idx, period in enumerate(periods, start=1):
        symbol = period["symbol"]
        path = period["path"]
        if is_bar_like_contract(symbol, path):
            period_reports.append({"symbol": symbol, "status": "skipped_bar_like"})
            continue
        print(f"[{idx}/{len(periods)}] footprint {symbol}: {path.name}", flush=True)
        price_volume = aggregate_footprint_price_volume_period(
            path,
            start=period["start"],
            end=period["end"],
            tick_size=args.tick_size,
            batch_size=args.batch_size,
            bar_minutes=args.bar_minutes,
        )
        if price_volume.empty:
            period_reports.append({"symbol": symbol, "status": "empty_price_volume"})
            continue
        period_bars = base[base["contract_symbol"].astype(str) == symbol].copy()
        if period_bars.empty:
            period_reports.append(
                {
                    "symbol": symbol,
                    "status": "no_base_bars",
                    "price_volume_rows": int(len(price_volume)),
                }
            )
            continue
        enriched = add_footprint_imbalance_features(
            period_bars[["timestamp", "open", "high", "low", "close", "volume"]],
            price_volume,
            tick_size=args.tick_size,
            imbalance_ratio=args.imbalance_ratio,
            min_level_volume=args.min_level_volume,
        )
        features = enriched[["timestamp", *FOOTPRINT_FEATURE_COLUMNS]].copy()
        feature_parts.append(features)
        period_reports.append(
            {
                "symbol": symbol,
                "status": "built",
                "base_rows": int(len(period_bars)),
                "price_volume_rows": int(len(price_volume)),
                "feature_rows": int(len(features)),
                "absorption_long_bars": int((features["footprint_absorption_long"] > 0).sum()),
                "absorption_short_bars": int((features["footprint_absorption_short"] > 0).sum()),
            }
        )

    features = pd.concat(feature_parts, ignore_index=True) if feature_parts else pd.DataFrame(columns=["timestamp"])
    if not features.empty:
        features = features.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    out = base.merge(features, on="timestamp", how="left")
    for column in FOOTPRINT_FEATURE_COLUMNS:
        if column not in out.columns:
            out[column] = 0.0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    out = out.sort_values("timestamp").reset_index(drop=True)

    args.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.output_parquet, index=False, compression="zstd")
    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.output_csv, index=False)

    report = {
        "base_cache": str(args.base_cache),
        "raw_dir": str(args.raw_dir),
        "roll_calendar": str(args.roll_calendar),
        "output_parquet": str(args.output_parquet),
        "rows": int(len(out)),
        "first_timestamp": str(out["timestamp"].min()),
        "last_timestamp": str(out["timestamp"].max()),
        "tick_size": args.tick_size,
        "bar_minutes": args.bar_minutes,
        "imbalance_ratio": args.imbalance_ratio,
        "min_level_volume": args.min_level_volume,
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()),
        "feature_columns": FOOTPRINT_FEATURE_COLUMNS,
        "absorption_long_bars": int((out["footprint_absorption_long"] > 0).sum()),
        "absorption_short_bars": int((out["footprint_absorption_short"] > 0).sum()),
        "periods": period_reports,
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["rows", "duplicate_timestamps", "absorption_long_bars", "absorption_short_bars"]}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local Sierra footprint-derived feature cache.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/ES/sierra-es-trades"))
    parser.add_argument(
        "--roll-calendar",
        type=Path,
        default=Path("data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv"),
    )
    parser.add_argument(
        "--base-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"),
    )
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--bar-minutes", type=int, default=1)
    parser.add_argument("--imbalance-ratio", type=float, default=3.0)
    parser.add_argument("--min-level-volume", type=float, default=10.0)
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    return parser.parse_args()


def aggregate_base_bars(base: pd.DataFrame, *, bar_minutes: int) -> pd.DataFrame:
    if bar_minutes <= 0:
        raise ValueError("--bar-minutes must be positive.")
    if bar_minutes == 1:
        return base.sort_values("timestamp").reset_index(drop=True).copy()

    out = base.sort_values("timestamp").reset_index(drop=True).copy()
    timestamps = pd.to_datetime(out["timestamp"])
    minute_of_day = timestamps.dt.hour * 60 + timestamps.dt.minute
    bucket_minutes = ((minute_of_day - RTH_START_MINUTE) // bar_minutes) * bar_minutes + RTH_START_MINUTE
    out["_bar_timestamp"] = timestamps.dt.normalize() + pd.to_timedelta(bucket_minutes, unit="m")

    group_cols = ["_bar_timestamp", "symbol", "contract_symbol"]
    agg = {
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
        "volume": ("volume", "sum"),
        "signed_volume": ("signed_volume", "sum"),
        "buy_volume": ("buy_volume", "sum"),
        "sell_volume": ("sell_volume", "sum"),
        "large10_signed_volume": ("large10_signed_volume", "sum"),
        "large20_signed_volume": ("large20_signed_volume", "sum"),
        "large10_volume": ("large10_volume", "sum"),
        "large20_volume": ("large20_volume", "sum"),
        "trades": ("trades", "sum"),
        "source_bar_count": ("timestamp", "count"),
    }
    aggregated = out.groupby(group_cols, sort=True, dropna=False).agg(**agg).reset_index()
    aggregated = aggregated.rename(columns={"_bar_timestamp": "timestamp"})
    aggregated["timeframe_minutes"] = int(bar_minutes)
    return aggregated.sort_values("timestamp").reset_index(drop=True)


def aggregate_footprint_price_volume_period(
    path: Path,
    *,
    start: datetime,
    end: datetime,
    tick_size: float,
    batch_size: int,
    bar_minutes: int = 1,
) -> pd.DataFrame:
    start_us = datetime_to_scid_us(start)
    end_us = datetime_to_scid_us(end) + 1
    parts = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=PRINT_COLUMNS):
        part = aggregate_footprint_price_volume_batch(
            batch,
            start_us=start_us,
            end_us=end_us,
            tick_size=tick_size,
            bar_minutes=bar_minutes,
        )
        if not part.empty:
            parts.append(part)
    if not parts:
        return pd.DataFrame(columns=["timestamp", "price", "volume", "bid_volume", "ask_volume"])
    combined = pd.concat(parts, ignore_index=True)
    combined = (
        combined.groupby(["bar_us", "price"], sort=True, observed=True)
        .agg(volume=("volume", "sum"), bid_volume=("bid_volume", "sum"), ask_volume=("ask_volume", "sum"))
        .reset_index()
    )
    combined["timestamp"] = pd.to_datetime(
        [pd.Timestamp("1899-12-30") + pd.Timedelta(microseconds=int(value)) for value in combined["bar_us"]]
    )
    return combined[["timestamp", "price", "volume", "bid_volume", "ask_volume"]]


def aggregate_footprint_price_volume_batch(
    batch,
    *,
    start_us: int,
    end_us: int,
    tick_size: float,
    bar_minutes: int = 1,
) -> pd.DataFrame:
    if bar_minutes <= 0:
        raise ValueError("--bar-minutes must be positive.")
    ts = batch.column(batch.schema.get_field_index("scid_datetime_us")).to_numpy(zero_copy_only=False).astype(
        np.int64, copy=False
    )
    price = batch.column(batch.schema.get_field_index("close")).to_numpy(zero_copy_only=False)
    volume = batch.column(batch.schema.get_field_index("volume")).to_numpy(zero_copy_only=False)
    bid = batch.column(batch.schema.get_field_index("bid_volume")).to_numpy(zero_copy_only=False)
    ask = batch.column(batch.schema.get_field_index("ask_volume")).to_numpy(zero_copy_only=False)
    mask = (ts >= start_us) & (ts < end_us) & np.isfinite(price) & (price > 0) & (volume > 0)
    if not mask.any():
        return pd.DataFrame()
    ts = ts[mask]
    price = price[mask].astype(np.float64, copy=False)
    volume = volume[mask].astype(np.int64, copy=False)
    bid = bid[mask].astype(np.int64, copy=False)
    ask = ask[mask].astype(np.int64, copy=False)

    local_timestamp = scid_us_to_new_york_datetime(ts)
    minute_of_day = local_timestamp.hour * 60 + local_timestamp.minute
    rth_mask = (minute_of_day >= 9 * 60 + 30) & (minute_of_day <= 15 * 60 + 59)
    if not rth_mask.any():
        return pd.DataFrame()
    local_timestamp = local_timestamp[rth_mask]
    price = price[rth_mask]
    volume = volume[rth_mask]
    bid = bid[rth_mask]
    ask = ask[rth_mask]
    price = np.round(price / tick_size) * tick_size
    bar_us = new_york_datetime_to_scid_us(_floor_local_timestamp_to_rth_bar(local_timestamp, bar_minutes))
    frame = pd.DataFrame(
        {
            "bar_us": bar_us,
            "price": price,
            "volume": volume,
            "bid_volume": bid,
            "ask_volume": ask,
        }
    )
    return (
        frame.groupby(["bar_us", "price"], sort=True, observed=True)
        .agg(volume=("volume", "sum"), bid_volume=("bid_volume", "sum"), ask_volume=("ask_volume", "sum"))
        .reset_index()
    )


def _floor_local_timestamp_to_rth_bar(local_timestamp: pd.DatetimeIndex, bar_minutes: int) -> pd.DatetimeIndex:
    floored = local_timestamp.floor("min")
    if bar_minutes == 1:
        return floored
    minute_of_day = floored.hour * 60 + floored.minute
    bucket_minutes = ((minute_of_day - RTH_START_MINUTE) // bar_minutes) * bar_minutes + RTH_START_MINUTE
    return floored.normalize() + pd.to_timedelta(bucket_minutes, unit="m")


def _filter_periods(periods: list[dict], start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    start_utc = start.tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).to_pydatetime()
    end_utc = end.tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).to_pydatetime()
    out = []
    for period in periods:
        if period["end"] < start_utc or period["start"] > end_utc:
            continue
        clipped = dict(period)
        clipped["start"] = max(period["start"], start_utc)
        clipped["end"] = min(period["end"], end_utc)
        out.append(clipped)
    return out


if __name__ == "__main__":
    main()
