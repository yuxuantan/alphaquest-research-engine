from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


SCID_EPOCH = datetime(1899, 12, 30)
ET = ZoneInfo("America/New_York")
DAY_US = 86_400_000_000
MINUTE_US = 60_000_000
RTH_START_MINUTE = 9 * 60 + 30
RTH_END_MINUTE = 15 * 60 + 59
FULL_RTH_MINUTES = RTH_END_MINUTE - RTH_START_MINUTE + 1

PRINT_COLUMNS = [
    "scid_datetime_us",
    "close",
    "num_trades",
    "volume",
    "bid_volume",
    "ask_volume",
]
OUTPUT_COLUMNS = [
    "timestamp",
    "symbol",
    "contract_symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "signed_volume",
    "buy_volume",
    "sell_volume",
    "large10_signed_volume",
    "large20_signed_volume",
    "large10_volume",
    "large20_volume",
    "trades",
]


def main() -> None:
    args = parse_args()
    raw_dir = args.raw_dir
    files = {path.stem.replace("-CME", ""): path for path in raw_dir.glob("*.parquet")}
    if not files:
        raise SystemExit(f"No Parquet files found in {raw_dir}")

    periods = active_periods(args.roll_calendar, files, args.root_symbol)
    if not periods:
        raise SystemExit("No roll-calendar periods overlap the available Sierra Parquet files.")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    if args.output_parquet:
        args.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
    if args.dropped_sessions_csv:
        args.dropped_sessions_csv.parent.mkdir(parents=True, exist_ok=True)

    skipped_files = sorted(
        symbol for symbol, path in files.items() if is_bar_like_contract(symbol, path)
    )
    frames = []
    period_reports = []
    for idx, period in enumerate(periods, start=1):
        symbol = period["symbol"]
        path = period["path"]
        if symbol in skipped_files:
            period_reports.append(
                {
                    "symbol": symbol,
                    "status": "skipped_bar_like",
                    "rows": int(pq.ParquetFile(path).metadata.num_rows),
                    "start": str(period["start"]),
                    "end": str(period["end"]),
                }
            )
            print(f"[{idx}/{len(periods)}] skip bar-like {symbol}: {path.name}", flush=True)
            continue

        print(f"[{idx}/{len(periods)}] aggregate {symbol}: {path.name}", flush=True)
        bars = aggregate_active_period(
            path,
            root_symbol=args.root_symbol,
            symbol=symbol,
            start=period["start"],
            end=period["end"],
            batch_size=args.batch_size,
        )
        period_reports.append(
            {
                "symbol": symbol,
                "status": "aggregated",
                "minute_rows": int(len(bars)),
                "first_timestamp": str(bars["timestamp"].min()) if len(bars) else None,
                "last_timestamp": str(bars["timestamp"].max()) if len(bars) else None,
                "start": str(period["start"]),
                "end": str(period["end"]),
            }
        )
        if not bars.empty:
            frames.append(bars)

    raw_bars = pd.concat(frames, ignore_index=True) if frames else empty_output_frame()
    raw_bars = raw_bars.sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)
    raw_bars = raw_bars.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    print(f"Aggregated active RTH bars before session policy: {len(raw_bars):,}", flush=True)

    ready, dropped_sessions = apply_session_policy(
        raw_bars,
        min_side_coverage=args.min_side_coverage,
    )
    ready = ready[OUTPUT_COLUMNS]
    print(f"Backtest-ready full-session bars: {len(ready):,}", flush=True)
    print(f"Dropped sessions: {len(dropped_sessions):,}", flush=True)

    ready.to_csv(args.output_csv, index=False)
    if args.output_parquet:
        ready.to_parquet(args.output_parquet, index=False, compression="zstd")
    if args.dropped_sessions_csv:
        dropped_sessions.to_csv(args.dropped_sessions_csv, index=False)

    validation = validate_ready_cache(ready)
    report = {
        "raw_dir": str(raw_dir),
        "roll_calendar": str(args.roll_calendar),
        "output_csv": str(args.output_csv),
        "output_parquet": str(args.output_parquet) if args.output_parquet else None,
        "rows": int(len(ready)),
        "sessions": int(ready["timestamp"].dt.normalize().nunique()) if len(ready) else 0,
        "first_timestamp": str(ready["timestamp"].min()) if len(ready) else None,
        "last_timestamp": str(ready["timestamp"].max()) if len(ready) else None,
        "skipped_bar_like_contracts": skipped_files,
        "dropped_sessions": int(len(dropped_sessions)),
        "dropped_sessions_by_reason": dropped_sessions["reason"].value_counts().to_dict()
        if not dropped_sessions.empty
        else {},
        "periods": period_reports,
        "validation": validation,
        "session_policy": {
            "source_timestamp_timezone": "UTC",
            "output_timestamp_timezone": "America/New_York",
            "timezone": "America/New_York",
            "rth_start": "09:30:00",
            "rth_end": "15:59:00",
            "regular_sessions_only": True,
            "incomplete_regular_sessions": "drop",
            "early_close_sessions": "drop",
            "holiday_sessions": "drop",
            "synthetic_fill": False,
            "min_side_coverage": args.min_side_coverage,
        },
    }
    if args.report_json:
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["validation"], indent=2, sort_keys=True), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a backtest-ready active-contract 1-minute orderflow cache from Sierra SCID Parquet prints."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/ES/sierra-es-trades"),
        help="Directory containing one Sierra SCID Parquet file per contract.",
    )
    parser.add_argument(
        "--roll-calendar",
        type=Path,
        default=Path("configs/data/ES/motivewave_rithmic_roll_calendar.csv"),
        help="Explicit ES roll calendar.",
    )
    parser.add_argument(
        "--root-symbol",
        default="ES",
        help="Root futures symbol to emit and use for contract file lookup, e.g. ES or NQ.",
    )
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-parquet", type=Path)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--dropped-sessions-csv", type=Path)
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    parser.add_argument(
        "--min-side-coverage",
        type=float,
        default=0.99,
        help="Drop sessions where (buy_volume + sell_volume) / volume is below this threshold.",
    )
    return parser.parse_args()


def active_periods(roll_calendar: Path, files: dict[str, Path], root_symbol: str = "ES") -> list[dict]:
    calendar = pd.read_csv(roll_calendar)
    starts_utc = pd.to_datetime(calendar["start_timestamp"], utc=True)
    starts_et = starts_utc.dt.tz_convert(ET)
    calendar = (
        calendar.assign(
            start_utc=starts_utc.dt.tz_localize(None),
            start_et=starts_et.dt.tz_localize(None),
        )
        .sort_values("start_utc")
        .reset_index(drop=True)
    )
    calendar["end_utc"] = calendar["start_utc"].shift(-1)
    calendar["symbol"] = [
        roll_contract_to_file_symbol(start, contract, root_symbol)
        for start, contract in zip(calendar["start_et"], calendar["contract_symbol"], strict=False)
    ]

    periods: list[dict] = []
    for row in calendar.itertuples(index=False):
        path = files.get(row.symbol)
        if path is None:
            continue
        file_start, file_end = parquet_timestamp_bounds(path)
        start = max(row.start_utc.to_pydatetime(), file_start)
        end = min(row.end_utc.to_pydatetime() if pd.notna(row.end_utc) else file_end, file_end)
        if start <= end:
            periods.append({"symbol": row.symbol, "path": path, "start": start, "end": end})
    return periods


def roll_contract_to_file_symbol(start: pd.Timestamp, contract: str, root_symbol: str = "ES") -> str:
    month = contract_month_code(contract)
    year = start.year + 1 if month == "H" else start.year
    return f"{root_symbol}{month}{year % 100:02d}"


def contract_month_code(contract: str) -> str:
    for char in str(contract):
        if char in {"H", "M", "U", "Z"}:
            return char
    raise ValueError(f"Could not infer quarterly month code from contract symbol: {contract!r}")


def parquet_timestamp_bounds(path: Path) -> tuple[datetime, datetime]:
    pf = pq.ParquetFile(path)
    lo = hi = None
    for row_group in range(pf.num_row_groups):
        stats = pf.metadata.row_group(row_group).column(0).statistics
        if stats is None or stats.min is None or stats.max is None:
            continue
        lo = int(stats.min) if lo is None else min(lo, int(stats.min))
        hi = int(stats.max) if hi is None else max(hi, int(stats.max))
    if lo is None or hi is None:
        raise ValueError(f"No timestamp statistics available in {path}")
    return SCID_EPOCH + timedelta(microseconds=lo), SCID_EPOCH + timedelta(microseconds=hi)


def is_bar_like_contract(symbol: str, path: Path) -> bool:
    # The 2010 M/U/Z Sierra files contain minute bars, not individual trade prints:
    # ~100k rows, 60-second median spacing, num_trades=0, no bid/ask side volume.
    if symbol in {"ESM10", "ESU10", "ESZ10"}:
        return True
    return pq.ParquetFile(path).metadata.num_rows < 1_000_000


def aggregate_active_period(
    path: Path,
    *,
    root_symbol: str,
    symbol: str,
    start: datetime,
    end: datetime,
    batch_size: int,
) -> pd.DataFrame:
    start_us = datetime_to_scid_us(start)
    end_us = datetime_to_scid_us(end) + 1
    parts = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=PRINT_COLUMNS):
        part = aggregate_batch(batch, start_us=start_us, end_us=end_us)
        if not part.empty:
            parts.append(part)
    if not parts:
        return empty_output_frame()

    partial = pd.concat(parts, ignore_index=True)
    grouped = partial.groupby("minute_us", sort=True, observed=True)
    idx_open = grouped["first_ts"].idxmin()
    idx_close = grouped["last_ts"].idxmax()
    open_values = partial.loc[idx_open, ["minute_us", "open"]].set_index("minute_us")["open"]
    close_values = partial.loc[idx_close, ["minute_us", "close"]].set_index("minute_us")["close"]
    combined = grouped.agg(
        high=("high", "max"),
        low=("low", "min"),
        volume=("volume", "sum"),
        signed_volume=("signed_volume", "sum"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        large10_signed_volume=("large10_signed_volume", "sum"),
        large20_signed_volume=("large20_signed_volume", "sum"),
        large10_volume=("large10_volume", "sum"),
        large20_volume=("large20_volume", "sum"),
        trades=("trades", "sum"),
    )
    combined["open"] = open_values
    combined["close"] = close_values
    combined = combined.reset_index()
    combined["timestamp"] = pd.to_datetime(
        [SCID_EPOCH + timedelta(microseconds=int(value)) for value in combined["minute_us"]]
    )
    combined["symbol"] = root_symbol
    combined["contract_symbol"] = symbol
    return combined[OUTPUT_COLUMNS].sort_values("timestamp").reset_index(drop=True)


def aggregate_batch(batch, *, start_us: int, end_us: int) -> pd.DataFrame:
    ts = batch.column(batch.schema.get_field_index("scid_datetime_us")).to_numpy(
        zero_copy_only=False
    ).astype(np.int64, copy=False)
    price = batch.column(batch.schema.get_field_index("close")).to_numpy(zero_copy_only=False)
    volume = batch.column(batch.schema.get_field_index("volume")).to_numpy(zero_copy_only=False)
    bid = batch.column(batch.schema.get_field_index("bid_volume")).to_numpy(zero_copy_only=False)
    ask = batch.column(batch.schema.get_field_index("ask_volume")).to_numpy(zero_copy_only=False)
    trades = batch.column(batch.schema.get_field_index("num_trades")).to_numpy(zero_copy_only=False)

    mask = (
        (ts >= start_us)
        & (ts < end_us)
        & np.isfinite(price)
        & (price > 0)
        & (volume > 0)
    )
    if not mask.any():
        return pd.DataFrame()

    ts = ts[mask]
    price = price[mask].astype(np.float64, copy=False)
    volume = volume[mask].astype(np.int64, copy=False)
    bid = bid[mask].astype(np.int64, copy=False)
    ask = ask[mask].astype(np.int64, copy=False)
    trades = trades[mask].astype(np.int64, copy=False)
    trades = np.where(trades <= 0, 1, trades)

    local_timestamp = scid_us_to_new_york_datetime(ts)
    minute_of_day = local_timestamp.hour * 60 + local_timestamp.minute
    rth_mask = (minute_of_day >= RTH_START_MINUTE) & (minute_of_day <= RTH_END_MINUTE)
    if not rth_mask.any():
        return pd.DataFrame()

    ts = ts[rth_mask]
    price = price[rth_mask]
    volume = volume[rth_mask]
    bid = bid[rth_mask]
    ask = ask[rth_mask]
    trades = trades[rth_mask]
    local_timestamp = local_timestamp[rth_mask]

    signed = ask - bid
    order = np.argsort(ts, kind="stable")
    ts = ts[order]
    price = price[order]
    volume = volume[order]
    bid = bid[order]
    ask = ask[order]
    trades = trades[order]
    signed = signed[order]
    minute_us = new_york_datetime_to_scid_us(local_timestamp[order].floor("min"))

    df = pd.DataFrame(
        {
            "minute_us": minute_us,
            "timestamp_us": ts,
            "price": price,
            "volume": volume,
            "signed_volume": signed,
            "buy_volume": ask,
            "sell_volume": bid,
            "large10_signed_volume": np.where(volume >= 10, signed, 0),
            "large20_signed_volume": np.where(volume >= 20, signed, 0),
            "large10_volume": np.where(volume >= 10, volume, 0),
            "large20_volume": np.where(volume >= 20, volume, 0),
            "trades": trades,
        }
    )
    return (
        df.groupby("minute_us", sort=True, observed=True)
        .agg(
            first_ts=("timestamp_us", "first"),
            last_ts=("timestamp_us", "last"),
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("volume", "sum"),
            signed_volume=("signed_volume", "sum"),
            buy_volume=("buy_volume", "sum"),
            sell_volume=("sell_volume", "sum"),
            large10_signed_volume=("large10_signed_volume", "sum"),
            large20_signed_volume=("large20_signed_volume", "sum"),
            large10_volume=("large10_volume", "sum"),
            large20_volume=("large20_volume", "sum"),
            trades=("trades", "sum"),
        )
        .reset_index()
    )


def apply_session_policy(
    raw_bars: pd.DataFrame,
    *,
    min_side_coverage: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw_bars.empty:
        return raw_bars.copy(), pd.DataFrame()
    work = raw_bars.copy()
    work["session_date"] = work["timestamp"].dt.date
    work["minute_of_day"] = work["timestamp"].dt.hour * 60 + work["timestamp"].dt.minute
    regular_dates = regular_nyse_dates(work["session_date"].min(), work["session_date"].max())
    dropped_rows = []
    keep_dates = []
    for session_date, group in work.groupby("session_date", sort=True):
        minutes = set(int(value) for value in group["minute_of_day"])
        missing = [
            value
            for value in range(RTH_START_MINUTE, RTH_END_MINUTE + 1)
            if value not in minutes
        ]
        volume = float(group["volume"].sum())
        side_volume = float((group["buy_volume"] + group["sell_volume"]).sum())
        side_coverage = side_volume / volume if volume > 0 else 0.0
        is_regular = session_date in regular_dates
        if not is_regular:
            reason = "non_regular_or_early_close_session"
        elif missing:
            reason = "incomplete_regular_session"
        elif side_coverage < min_side_coverage:
            reason = "low_side_volume_coverage"
        else:
            keep_dates.append(session_date)
            continue
        dropped_rows.append(
            {
                "session_date": session_date.isoformat(),
                "contract_symbol": ",".join(sorted(group["contract_symbol"].astype(str).unique())),
                "minutes": int(len(minutes)),
                "missing_minutes": int(len(missing)),
                "side_coverage": side_coverage,
                "first_minute": minute_to_text(min(minutes)) if minutes else None,
                "last_minute": minute_to_text(max(minutes)) if minutes else None,
                "reason": reason,
            }
        )
    ready = work[work["session_date"].isin(keep_dates)].copy()
    ready = ready.drop(columns=["session_date", "minute_of_day"])
    dropped = pd.DataFrame(dropped_rows)
    return ready.reset_index(drop=True), dropped


def regular_nyse_dates(start: date, end: date) -> set[date]:
    holidays = nyse_holidays(start.year, end.year)
    early_closes = nyse_early_closes(start.year, end.year)
    out = set()
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays and current not in early_closes:
            out.add(current)
        current += timedelta(days=1)
    return out


def nyse_holidays(start_year: int, end_year: int) -> set[date]:
    holidays: set[date] = set()
    for year in range(start_year, end_year + 1):
        holidays.add(observed(date(year, 1, 1)))
        holidays.add(nth_weekday(year, 1, 0, 3))  # MLK Day
        holidays.add(nth_weekday(year, 2, 0, 3))  # Washington's Birthday
        holidays.add(good_friday(year))
        holidays.add(last_weekday(year, 5, 0))  # Memorial Day
        if year >= 2022:
            holidays.add(observed(date(year, 6, 19)))  # Juneteenth
        holidays.add(observed(date(year, 7, 4)))
        holidays.add(nth_weekday(year, 9, 0, 1))  # Labor Day
        holidays.add(nth_weekday(year, 11, 3, 4))  # Thanksgiving
        holidays.add(observed(date(year, 12, 25)))
    holidays.update({date(2012, 10, 29), date(2012, 10, 30), date(2018, 12, 5), date(2025, 1, 9)})
    return {value for value in holidays if value.weekday() < 5}


def nyse_early_closes(start_year: int, end_year: int) -> set[date]:
    closes: set[date] = set()
    holidays = nyse_holidays(start_year, end_year)
    for year in range(start_year, end_year + 1):
        day_after_thanksgiving = nth_weekday(year, 11, 3, 4) + timedelta(days=1)
        christmas_eve = date(year, 12, 24)
        july3 = date(year, 7, 3)
        for value in [day_after_thanksgiving, christmas_eve, july3]:
            if value.weekday() < 5 and value not in holidays:
                closes.add(value)
    return closes


def observed(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def good_friday(year: int) -> date:
    return easter_sunday(year) - timedelta(days=2)


def easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def validate_ready_cache(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "duplicate_timestamps": 0,
            "invalid_ohlc_rows": 0,
            "missing_session_segments": 0,
            "non_regular_sessions": 0,
            "min_session_side_coverage": None,
            "low_side_coverage_sessions": 0,
        }
    duplicate_timestamps = int(df.duplicated(subset=["timestamp"]).sum())
    invalid_ohlc = int(
        (~(
            (df["high"] >= df["open"])
            & (df["high"] >= df["close"])
            & (df["low"] <= df["open"])
            & (df["low"] <= df["close"])
            & (df["high"] >= df["low"])
            & (df[["open", "high", "low", "close"]] > 0).all(axis=1)
            & (df["volume"] > 0)
        )).sum()
    )
    dates = df["timestamp"].dt.date
    regular_dates = regular_nyse_dates(dates.min(), dates.max())
    non_regular_sessions = int(len(set(dates) - regular_dates))
    session_side = (
        df.assign(side_volume=df["buy_volume"] + df["sell_volume"], session_date=dates)
        .groupby("session_date", observed=True)
        .agg(volume=("volume", "sum"), side_volume=("side_volume", "sum"))
    )
    side_coverage = session_side["side_volume"] / session_side["volume"]
    missing_segments = 0
    for _, group in df.assign(session_date=dates).groupby("session_date", sort=True):
        minutes = pd.DatetimeIndex(group["timestamp"])
        expected = pd.date_range(minutes.min(), minutes.max(), freq="1min")
        missing_segments += int(len(expected.difference(minutes)) > 0)
        if len(minutes) != FULL_RTH_MINUTES:
            missing_segments += 1
    return {
        "duplicate_timestamps": duplicate_timestamps,
        "invalid_ohlc_rows": invalid_ohlc,
        "missing_session_segments": missing_segments,
        "non_regular_sessions": non_regular_sessions,
        "min_session_side_coverage": float(side_coverage.min()),
        "low_side_coverage_sessions": int((side_coverage < 0.99).sum()),
    }


def datetime_to_scid_us(value: datetime) -> int:
    return int((value - SCID_EPOCH).total_seconds() * 1_000_000)


def scid_us_to_new_york_datetime(values: np.ndarray) -> pd.DatetimeIndex:
    return pd.to_datetime(values, unit="us", origin=SCID_EPOCH, utc=True).tz_convert(ET).tz_localize(None)


def new_york_datetime_to_scid_us(values: pd.DatetimeIndex) -> np.ndarray:
    naive = pd.DatetimeIndex(values).tz_localize(None)
    return ((naive - pd.Timestamp(SCID_EPOCH)) // pd.Timedelta(microseconds=1)).to_numpy(dtype=np.int64)


def minute_to_text(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}:00"


def empty_output_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


if __name__ == "__main__":
    main()
