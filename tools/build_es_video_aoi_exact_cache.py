from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    from tools.build_sierra_trade_orderflow_cache import (
        active_periods,
        datetime_to_scid_us,
        is_bar_like_contract,
        scid_us_to_new_york_datetime,
    )
except ModuleNotFoundError:
    from build_sierra_trade_orderflow_cache import (
        active_periods,
        datetime_to_scid_us,
        is_bar_like_contract,
        scid_us_to_new_york_datetime,
    )


LARGE200_COLUMNS = [
    "large200_record_volume",
    "large200_record_signed_volume",
    "large200_record_buy_volume",
    "large200_record_sell_volume",
    "large200_record_count",
    "large200_record_max_volume",
]

OVERNIGHT_COLUMNS = [
    "prior_vap_session_yyyymmdd",
    "prior_vap_poc",
    "prior_vap_vah",
    "prior_vap_val",
    "prior_vap_lvn_near_high",
    "prior_vap_lvn_near_low",
    "prior_vap_lvn_count",
    "prior_vap_total_volume",
    "prior_vap_price_levels",
    "overnight_high",
    "overnight_low",
    "overnight_midpoint",
    "overnight_range_points",
    "overnight_return_points",
    "overnight_volume",
    "overnight_bars",
    "overnight_range_rank_252",
    "overnight_range_mean_252_prior",
    "overnight_range_median_252_prior",
]

ORB_30S_COLUMNS = [
    "orb_30s_high",
    "orb_30s_low",
    "orb_30s_range_points",
    "orb_30s_volume",
    "orb_30s_trades",
    "orb_30s_first_timestamp",
    "orb_30s_last_timestamp",
    "orb_30s_available_after_open_seconds",
]

ORB_PRINT_COLUMNS = [
    "scid_datetime_us",
    "high",
    "low",
    "volume",
    "num_trades",
]


def main() -> None:
    args = parse_args()
    base = pd.read_parquet(args.developing_vap_3m_cache)
    supplemental = pd.read_parquet(args.overnight_large200_1m_cache)
    base["timestamp"] = pd.to_datetime(base["timestamp"])
    supplemental["timestamp"] = pd.to_datetime(supplemental["timestamp"])

    if args.start_date:
        start = pd.Timestamp(args.start_date)
        base = base[base["timestamp"] >= start].copy()
        supplemental = supplemental[supplemental["timestamp"] >= start].copy()
    if args.end_date:
        end = pd.Timestamp(args.end_date) + pd.Timedelta(days=1)
        base = base[base["timestamp"] < end].copy()
        supplemental = supplemental[supplemental["timestamp"] < end].copy()
    if base.empty or supplemental.empty:
        raise SystemExit("Selected base or supplemental cache is empty.")

    supplemental_3m = aggregate_supplemental_1m_to_3m(supplemental, bar_minutes=args.bar_minutes)
    out = base.merge(supplemental_3m, on="timestamp", how="left", validate="one_to_one")
    if not args.skip_orb_30s:
        orb_30s = build_orb_30s_features(
            raw_dir=args.raw_dir,
            roll_calendar=args.roll_calendar,
            root_symbol=args.root_symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            batch_size=args.batch_size,
        )
        out["_session_date"] = out["timestamp"].dt.normalize()
        out = out.merge(orb_30s, on="_session_date", how="left", validate="many_to_one")
        out = out.drop(columns=["_session_date"])
    for column in LARGE200_COLUMNS:
        if column not in out.columns:
            out[column] = 0.0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    for column in OVERNIGHT_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
        out[column] = pd.to_numeric(out[column], errors="coerce")
    for column in ORB_30S_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out = out.sort_values("timestamp").reset_index(drop=True)
    args.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.output_parquet, index=False, compression="zstd")

    report = {
        "developing_vap_3m_cache": str(args.developing_vap_3m_cache),
        "overnight_large200_1m_cache": str(args.overnight_large200_1m_cache),
        "output_parquet": str(args.output_parquet),
        "rows": int(len(out)),
        "first_timestamp": str(out["timestamp"].min()),
        "last_timestamp": str(out["timestamp"].max()),
        "bar_minutes": args.bar_minutes,
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()),
        "bars_with_developing_vap": int(out["developing_vap_poc"].notna().sum()),
        "bars_with_overnight_levels": int(out["overnight_high"].notna().sum()),
        "bars_with_large200_record": int((out["large200_record_max_volume"] >= args.min_record_volume).sum()),
        "bars_with_orb_30s": int(out["orb_30s_high"].notna().sum()),
        "source_quality_label": (
            "Joined 3-minute Sierra developing VAP cache with 1-minute Sierra overnight AOI and "
            "large-200 record proxy fields aggregated to native 3-minute RTH bars. "
            "Adds raw Sierra 09:30:00-09:30:30 ET opening-range high/low per session. "
            "Large-record fields are aggregate proxies, not full MBO/DOM sequencing."
        ),
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


def aggregate_supplemental_1m_to_3m(supplemental: pd.DataFrame, *, bar_minutes: int) -> pd.DataFrame:
    if bar_minutes <= 0:
        raise ValueError("bar_minutes must be positive.")
    work = supplemental.sort_values("timestamp").reset_index(drop=True).copy()
    timestamps = pd.to_datetime(work["timestamp"])
    minute_of_day = timestamps.dt.hour * 60 + timestamps.dt.minute
    rth_start_minute = 9 * 60 + 30
    bucket_minutes = ((minute_of_day - rth_start_minute) // bar_minutes) * bar_minutes + rth_start_minute
    work["_bar_timestamp"] = timestamps.dt.normalize() + pd.to_timedelta(bucket_minutes, unit="m")
    keep_columns = [column for column in [*LARGE200_COLUMNS, *OVERNIGHT_COLUMNS] if column in work.columns]
    aggregations = {}
    for column in keep_columns:
        if column == "large200_record_max_volume":
            aggregations[column] = (column, "max")
        elif column in LARGE200_COLUMNS:
            aggregations[column] = (column, "sum")
        else:
            aggregations[column] = (column, "last")
    out = work.groupby("_bar_timestamp", sort=True, dropna=False).agg(**aggregations).reset_index()
    return out.rename(columns={"_bar_timestamp": "timestamp"})


def build_orb_30s_features(
    *,
    raw_dir: Path,
    roll_calendar: Path,
    root_symbol: str,
    start_date: str | None,
    end_date: str | None,
    batch_size: int,
) -> pd.DataFrame:
    files = {path.stem.replace("-CME", ""): path for path in raw_dir.glob("*.parquet")}
    if not files:
        raise SystemExit(f"No Sierra Parquet files found in {raw_dir}")
    periods = active_periods(roll_calendar, files, root_symbol)
    if not periods:
        raise SystemExit("No roll-calendar periods overlap the available Sierra Parquet files.")

    start_utc, end_utc = _date_bounds_to_utc_naive(start_date, end_date)
    parts = []
    for index, period in enumerate(periods, start=1):
        symbol = period["symbol"]
        path = period["path"]
        if is_bar_like_contract(symbol, path):
            continue
        period_start = max(period["start"], start_utc) if start_utc is not None else period["start"]
        period_end = min(period["end"], end_utc) if end_utc is not None else period["end"]
        if period_start >= period_end:
            continue
        print(f"[orb30 {index}/{len(periods)}] aggregate {symbol}: {path.name}", flush=True)
        features = aggregate_orb_30s_active_period(
            path,
            start=period_start,
            end=period_end,
            batch_size=batch_size,
        )
        if not features.empty:
            features["orb_30s_contract_count"] = 1
            parts.append(features)
    if not parts:
        return empty_orb_30s_frame()
    return combine_orb_30s_parts(pd.concat(parts, ignore_index=True))


def aggregate_orb_30s_active_period(
    path: Path,
    *,
    start: datetime,
    end: datetime,
    batch_size: int,
) -> pd.DataFrame:
    start_us = datetime_to_scid_us(start)
    end_us = datetime_to_scid_us(end)
    parts = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=ORB_PRINT_COLUMNS):
        part = aggregate_orb_30s_batch(batch, start_us=start_us, end_us=end_us)
        if not part.empty:
            parts.append(part)
    if not parts:
        return empty_orb_30s_frame()
    return combine_orb_30s_parts(pd.concat(parts, ignore_index=True))


def aggregate_orb_30s_batch(batch, *, start_us: int, end_us: int) -> pd.DataFrame:
    ts = batch.column(batch.schema.get_field_index("scid_datetime_us")).to_numpy(
        zero_copy_only=False
    ).astype(np.int64, copy=False)
    high = batch.column(batch.schema.get_field_index("high")).to_numpy(zero_copy_only=False)
    low = batch.column(batch.schema.get_field_index("low")).to_numpy(zero_copy_only=False)
    volume = batch.column(batch.schema.get_field_index("volume")).to_numpy(zero_copy_only=False)
    trades = batch.column(batch.schema.get_field_index("num_trades")).to_numpy(zero_copy_only=False)

    mask = (
        (ts >= start_us)
        & (ts < end_us)
        & np.isfinite(high)
        & np.isfinite(low)
        & (high > 0)
        & (low > 0)
        & (high >= low)
        & (volume > 0)
    )
    if not mask.any():
        return empty_orb_30s_frame()

    ts = ts[mask]
    high = high[mask].astype(np.float64, copy=False)
    low = low[mask].astype(np.float64, copy=False)
    volume = volume[mask].astype(np.float64, copy=False)
    trades = trades[mask].astype(np.float64, copy=False)
    trades = np.where(trades <= 0, 1.0, trades)

    local_timestamp = scid_us_to_new_york_datetime(ts)
    seconds_from_midnight = (
        local_timestamp.hour * 3600
        + local_timestamp.minute * 60
        + local_timestamp.second
        + local_timestamp.microsecond / 1_000_000
    )
    orb_start = 9 * 3600 + 30 * 60
    orb_mask = (seconds_from_midnight >= orb_start) & (seconds_from_midnight < orb_start + 30)
    if not orb_mask.any():
        return empty_orb_30s_frame()

    return aggregate_orb_30s_prints(
        pd.DataFrame(
            {
                "timestamp": local_timestamp[orb_mask],
                "high": high[orb_mask],
                "low": low[orb_mask],
                "volume": volume[orb_mask],
                "num_trades": trades[orb_mask],
            }
        )
    )


def aggregate_orb_30s_prints(prints: pd.DataFrame) -> pd.DataFrame:
    if prints.empty:
        return empty_orb_30s_frame()
    work = prints.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"])
    seconds_from_midnight = (
        work["timestamp"].dt.hour * 3600
        + work["timestamp"].dt.minute * 60
        + work["timestamp"].dt.second
        + work["timestamp"].dt.microsecond / 1_000_000
    )
    orb_start = 9 * 3600 + 30 * 60
    work = work[(seconds_from_midnight >= orb_start) & (seconds_from_midnight < orb_start + 30)].copy()
    if work.empty:
        return empty_orb_30s_frame()
    work["_session_date"] = work["timestamp"].dt.normalize()
    work["num_trades"] = pd.to_numeric(work["num_trades"], errors="coerce").fillna(0.0)
    work.loc[work["num_trades"] <= 0, "num_trades"] = 1.0
    grouped = (
        work.groupby("_session_date", sort=True, observed=True)
        .agg(
            orb_30s_high=("high", "max"),
            orb_30s_low=("low", "min"),
            orb_30s_volume=("volume", "sum"),
            orb_30s_trades=("num_trades", "sum"),
            orb_30s_first_timestamp=("timestamp", "min"),
            orb_30s_last_timestamp=("timestamp", "max"),
        )
        .reset_index()
    )
    grouped["orb_30s_range_points"] = grouped["orb_30s_high"] - grouped["orb_30s_low"]
    grouped["orb_30s_available_after_open_seconds"] = 30.0
    grouped["orb_30s_first_timestamp"] = (
        pd.to_datetime(grouped["orb_30s_first_timestamp"]).astype("int64") // 1_000_000_000
    )
    grouped["orb_30s_last_timestamp"] = (
        pd.to_datetime(grouped["orb_30s_last_timestamp"]).astype("int64") // 1_000_000_000
    )
    return grouped[["_session_date", *ORB_30S_COLUMNS]]


def combine_orb_30s_parts(parts: pd.DataFrame) -> pd.DataFrame:
    if parts.empty:
        return empty_orb_30s_frame()
    grouped = (
        parts.groupby("_session_date", sort=True, observed=True)
        .agg(
            orb_30s_high=("orb_30s_high", "max"),
            orb_30s_low=("orb_30s_low", "min"),
            orb_30s_volume=("orb_30s_volume", "sum"),
            orb_30s_trades=("orb_30s_trades", "sum"),
            orb_30s_first_timestamp=("orb_30s_first_timestamp", "min"),
            orb_30s_last_timestamp=("orb_30s_last_timestamp", "max"),
            orb_30s_available_after_open_seconds=("orb_30s_available_after_open_seconds", "max"),
        )
        .reset_index()
    )
    grouped["orb_30s_range_points"] = grouped["orb_30s_high"] - grouped["orb_30s_low"]
    return grouped[["_session_date", *ORB_30S_COLUMNS]]


def empty_orb_30s_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["_session_date", *ORB_30S_COLUMNS])


def _date_bounds_to_utc_naive(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    start_utc = None
    end_utc = None
    if start_date:
        start_local = pd.Timestamp(start_date, tz="America/New_York")
        start_utc = start_local.tz_convert("UTC").tz_localize(None).to_pydatetime()
    if end_date:
        end_local = pd.Timestamp(end_date, tz="America/New_York") + pd.Timedelta(days=1)
        end_utc = end_local.tz_convert("UTC").tz_localize(None).to_pydatetime()
    return start_utc, end_utc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the joined ES video AOI exact-proxy 3-minute cache.")
    parser.add_argument(
        "--developing-vap-3m-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_footprint_developing_vap_3m_20101214_20260610_full_rth_ny.parquet"),
    )
    parser.add_argument(
        "--overnight-large200-1m-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_footprint_vap_overnight_large200_1m_20120103_20260529_rth_ny.parquet"),
    )
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--start-date", default="2012-01-03")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--bar-minutes", type=int, default=3)
    parser.add_argument("--min-record-volume", type=float, default=200.0)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/ES/sierra-es-trades"))
    parser.add_argument(
        "--roll-calendar",
        type=Path,
        default=Path("data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv"),
    )
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    parser.add_argument("--skip-orb-30s", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
