from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SCID_EPOCH = datetime(1899, 12, 30)
ET = ZoneInfo("America/New_York")

SCID_RECORD_COLUMNS = [
    "scid_datetime_us",
    "open",
    "high",
    "low",
    "close",
    "num_trades",
    "volume",
    "bid_volume",
    "ask_volume",
]

SCID_RECORD_PRICE_PATH_SEMANTICS = "scid_record_close_only_v1"

_SCID_EXECUTION_COLUMNS = [
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
    "trades",
    "num_trades",
    "scid_datetime_us",
    "execution_granularity",
    "price_path_semantics",
    "raw_scid_open",
    "raw_scid_high",
    "raw_scid_low",
    "raw_scid_close",
]


def load_scid_record_execution_data(
    config: dict,
    *,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    """Load active-contract Sierra SCID-derived records for tick-style execution.

    The local Sierra Parquet files are SCID records, not MBO events. They are
    useful for deterministic record replay when the strategy explicitly accepts
    this source-quality limitation. For execution-path decisions, the loader
    treats the record close as the only traded-price proxy and exposes
    open/high/low equal to close. Raw SCID OHLC fields are retained separately
    for audit, but are not used as traded-price extrema.
    """

    raw_dir = Path(config.get("raw_dir", "data/raw/ES/sierra-es-trades"))
    roll_calendar = Path(
        config.get("roll_calendar", "data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv")
    )
    root_symbol = str(config.get("root_symbol", config.get("symbol", "ES")))
    batch_size = int(config.get("batch_size", 1_000_000))
    timezone = str(config.get("timezone", "America/New_York"))
    rth_start_minute = _time_to_minute(config.get("rth_start", "09:30:00"))
    rth_end_minute = _time_to_minute(config.get("rth_end", "16:00:00"))

    files = {path.stem.replace("-CME", ""): path for path in raw_dir.glob("*.parquet")}
    if not files:
        raise ValueError(f"No Sierra SCID Parquet files found in {raw_dir}")

    periods = _active_periods(roll_calendar, files, root_symbol)
    start, end = _bounds_to_utc_naive(date_bounds, timezone)
    parts = []
    for period in periods:
        period_start = max(period["start"], start) if start is not None else period["start"]
        period_end = min(period["end"], end) if end is not None else period["end"]
        if period_start >= period_end:
            continue
        part = _load_period_records(
            period["path"],
            root_symbol=root_symbol,
            contract_symbol=period["symbol"],
            start=period_start,
            end=period_end,
            batch_size=batch_size,
            rth_start_minute=rth_start_minute,
            rth_end_minute=rth_end_minute,
        )
        if not part.empty:
            parts.append(part)

    if not parts:
        out = pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    else:
        out = pd.concat(parts, ignore_index=True).sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    out.attrs["detail_granularity"] = "scid_record"
    out.attrs["price_path_semantics"] = SCID_RECORD_PRICE_PATH_SEMANTICS
    out.attrs["source_quality_label"] = (
        "Sierra SCID record close-only replay; raw SCID high/low retained for audit, "
        "not used as traded-price extrema; not exchange MBO sequencing."
    )
    return out


def _load_period_records(
    path: Path,
    *,
    root_symbol: str,
    contract_symbol: str,
    start: datetime,
    end: datetime,
    batch_size: int,
    rth_start_minute: int,
    rth_end_minute: int,
) -> pd.DataFrame:
    start_us = _datetime_to_scid_us(start)
    end_us = _datetime_to_scid_us(end)
    parts = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=SCID_RECORD_COLUMNS):
        part = _records_from_batch(
            batch,
            root_symbol=root_symbol,
            contract_symbol=contract_symbol,
            start_us=start_us,
            end_us=end_us,
            rth_start_minute=rth_start_minute,
            rth_end_minute=rth_end_minute,
        )
        if not part.empty:
            parts.append(part)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _records_from_batch(
    batch,
    *,
    root_symbol: str,
    contract_symbol: str,
    start_us: int,
    end_us: int,
    rth_start_minute: int,
    rth_end_minute: int,
) -> pd.DataFrame:
    ts = batch.column(batch.schema.get_field_index("scid_datetime_us")).to_numpy(zero_copy_only=False).astype(
        np.int64, copy=False
    )
    raw_open = batch.column(batch.schema.get_field_index("open")).to_numpy(zero_copy_only=False)
    raw_high = batch.column(batch.schema.get_field_index("high")).to_numpy(zero_copy_only=False)
    raw_low = batch.column(batch.schema.get_field_index("low")).to_numpy(zero_copy_only=False)
    close = batch.column(batch.schema.get_field_index("close")).to_numpy(zero_copy_only=False)
    volume = batch.column(batch.schema.get_field_index("volume")).to_numpy(zero_copy_only=False)
    bid = batch.column(batch.schema.get_field_index("bid_volume")).to_numpy(zero_copy_only=False)
    ask = batch.column(batch.schema.get_field_index("ask_volume")).to_numpy(zero_copy_only=False)
    trades = batch.column(batch.schema.get_field_index("num_trades")).to_numpy(zero_copy_only=False)

    mask = (
        (ts >= start_us)
        & (ts < end_us)
        & np.isfinite(close)
        & (close > 0)
        & np.isfinite(volume)
        & (volume > 0)
    )
    if not mask.any():
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)

    ts = ts[mask]
    raw_open = np.where(np.isfinite(raw_open[mask]), raw_open[mask], np.nan).astype(np.float64, copy=False)
    raw_high = np.where(np.isfinite(raw_high[mask]), raw_high[mask], np.nan).astype(np.float64, copy=False)
    raw_low = np.where(np.isfinite(raw_low[mask]), raw_low[mask], np.nan).astype(np.float64, copy=False)
    close = close[mask].astype(np.float64, copy=False)
    volume = volume[mask].astype(np.int64, copy=False)
    bid = bid[mask].astype(np.int64, copy=False)
    ask = ask[mask].astype(np.int64, copy=False)
    trades = trades[mask].astype(np.int64, copy=False)
    trades = np.where(trades <= 0, 1, trades)

    order = np.argsort(ts, kind="stable")
    ts = ts[order]
    raw_open = raw_open[order]
    raw_high = raw_high[order]
    raw_low = raw_low[order]
    close = close[order]
    volume = volume[order]
    bid = bid[order]
    ask = ask[order]
    trades = trades[order]
    signed = ask - bid
    timestamps = pd.Series(pd.to_datetime([SCID_EPOCH + timedelta(microseconds=int(value)) for value in ts]))
    timestamps = timestamps.dt.tz_localize("UTC").dt.tz_convert(ET)
    minute_of_day = timestamps.dt.hour * 60 + timestamps.dt.minute
    rth_mask = (minute_of_day >= rth_start_minute) & (minute_of_day < rth_end_minute)
    if not bool(rth_mask.any()):
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    ts = ts[rth_mask.to_numpy()]
    timestamps = timestamps[rth_mask].reset_index(drop=True)
    close = close[rth_mask.to_numpy()]
    raw_open = raw_open[rth_mask.to_numpy()]
    raw_high = raw_high[rth_mask.to_numpy()]
    raw_low = raw_low[rth_mask.to_numpy()]
    volume = volume[rth_mask.to_numpy()]
    bid = bid[rth_mask.to_numpy()]
    ask = ask[rth_mask.to_numpy()]
    trades = trades[rth_mask.to_numpy()]
    signed = signed[rth_mask.to_numpy()]
    traded_open = close.copy()
    traded_high = close.copy()
    traded_low = close.copy()

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": root_symbol,
            "contract_symbol": contract_symbol,
            "open": traded_open,
            "high": traded_high,
            "low": traded_low,
            "close": close,
            "volume": volume,
            "signed_volume": signed,
            "buy_volume": ask,
            "sell_volume": bid,
            "trades": trades,
            "num_trades": trades,
            "scid_datetime_us": ts,
            "execution_granularity": "scid_record",
            "price_path_semantics": SCID_RECORD_PRICE_PATH_SEMANTICS,
            "raw_scid_open": raw_open,
            "raw_scid_high": raw_high,
            "raw_scid_low": raw_low,
            "raw_scid_close": close,
        }
    )


def _active_periods(roll_calendar: Path, files: dict[str, Path], root_symbol: str) -> list[dict]:
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
        _roll_contract_to_file_symbol(start, contract, root_symbol)
        for start, contract in zip(calendar["start_et"], calendar["contract_symbol"], strict=False)
    ]

    periods = []
    for row in calendar.itertuples(index=False):
        path = files.get(row.symbol)
        if path is None or _is_bar_like_contract(row.symbol, path):
            continue
        file_start, file_end = _parquet_timestamp_bounds(path)
        start = max(row.start_utc.to_pydatetime(), file_start)
        end = min(row.end_utc.to_pydatetime() if pd.notna(row.end_utc) else file_end, file_end)
        if start < end:
            periods.append({"symbol": row.symbol, "path": path, "start": start, "end": end})
    return periods


def _is_bar_like_contract(symbol: str, path: Path) -> bool:
    if symbol in {"ESM10", "ESU10", "ESZ10"}:
        return True
    return pq.ParquetFile(path).metadata.num_rows < 1_000_000


def _roll_contract_to_file_symbol(start: pd.Timestamp, contract: str, root_symbol: str) -> str:
    month = _contract_month_code(contract)
    year = start.year + 1 if month == "H" else start.year
    return f"{root_symbol}{month}{year % 100:02d}"


def _contract_month_code(contract: str) -> str:
    for char in str(contract):
        if char in {"H", "M", "U", "Z"}:
            return char
    raise ValueError(f"Could not infer quarterly month code from contract symbol: {contract!r}")


def _parquet_timestamp_bounds(path: Path) -> tuple[datetime, datetime]:
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


def _bounds_to_utc_naive(bounds: dict | None, timezone: str) -> tuple[datetime | None, datetime | None]:
    if not bounds:
        return None, None
    tz = ZoneInfo(timezone)
    start = bounds.get("start_timestamp") or bounds.get("start_date")
    end = bounds.get("end_timestamp")
    if not end and bounds.get("end_date"):
        end = pd.Timestamp(bounds["end_date"]) + pd.Timedelta(days=1)
    return _bound_to_utc_naive(start, tz), _bound_to_utc_naive(end, tz)


def _bound_to_utc_naive(value, timezone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone)
    else:
        ts = ts.tz_convert(timezone)
    return ts.tz_convert("UTC").tz_localize(None).to_pydatetime()


def _datetime_to_scid_us(value: datetime) -> int:
    return int((value - SCID_EPOCH).total_seconds() * 1_000_000)


def _time_to_minute(value) -> int:
    ts = pd.Timestamp(f"2000-01-01 {value}")
    return int(ts.hour * 60 + ts.minute)
