from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from alphaquest.data.sierra_events import (
    SIERRA_EVENT_PRICE_PATH_SEMANTICS,
    SIERRA_TIMESTAMP_PRECISION_NS,
    reconstruct_sierra_trade_events,
)

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

SCID_RECORD_PRICE_PATH_SEMANTICS = SIERRA_EVENT_PRICE_PATH_SEMANTICS

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
    "last_scid_datetime_us",
    "source_ordinal",
    "side",
    "component_rows",
    "timestamp_precision_ns",
    "timestamp_uncertainty_ns",
    "quality_capability",
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
    """Load Databento-validated, reconstructed Sierra trade events.

    Every requested session must pass the configured capability in the quality
    manifest, unless the caller explicitly chooses the ``blackout`` policy.
    Unbundled FIRST/LAST component rows are collapsed before replay.
    """

    raw_dir = Path(config.get("raw_dir", "data/raw/ES/sierra-es-trades"))
    roll_calendar = Path(
        config.get("roll_calendar", "data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv")
    )
    root_symbol = str(config.get("root_symbol", config.get("symbol", "ES")))
    timezone = str(config.get("timezone", "America/New_York"))
    rth_start_minute = _time_to_minute(config.get("rth_start", "09:30:00"))
    rth_end_minute = _time_to_minute(config.get("rth_end", "16:00:00"))
    verified_start_minute = _time_to_minute(config.get("verified_window_start", "09:30:00"))
    verified_end_minute = _time_to_minute(config.get("verified_window_end", "11:00:00"))
    if rth_start_minute < verified_start_minute or rth_end_minute > verified_end_minute:
        raise ValueError(
            "Sierra event replay window exceeds the independently verified 09:30-11:00 ET scope."
        )
    quality_manifest = Path(
        config.get(
            "quality_manifest",
            "data/reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv",
        )
    )
    required_capability = str(config.get("required_capability", "full_strategy_events"))
    ineligible_policy = str(config.get("ineligible_session_policy", "error")).lower()
    allow_unverified_for_tests = bool(config.get("allow_unverified_for_tests", False))

    files = {path.stem.replace("-CME", ""): path for path in raw_dir.glob("*.parquet")}
    if not files:
        raise ValueError(f"No Sierra SCID Parquet files found in {raw_dir}")

    periods = _active_periods(roll_calendar, files, root_symbol)
    start, end = _bounds_to_utc_naive(date_bounds, timezone)
    manifest = _load_quality_manifest(
        quality_manifest,
        required_capability=required_capability,
        allow_unverified_for_tests=allow_unverified_for_tests,
    )
    requested = _requested_manifest_rows(manifest, start=start, end=end, periods=periods)
    ineligible = requested.loc[~requested[required_capability].map(_as_bool)].copy()
    if len(ineligible) and ineligible_policy != "blackout":
        sample = ", ".join(ineligible["session_date"].astype(str).head(8))
        raise ValueError(
            f"{len(ineligible)} requested Sierra sessions fail capability {required_capability!r} "
            f"({sample}). Set ineligible_session_policy=blackout only for explicit session exclusion."
        )
    eligible = requested.loc[requested[required_capability].map(_as_bool)].copy()
    parts = []
    period_by_symbol = {period["symbol"]: period for period in periods}
    for row in eligible.itertuples(index=False):
        period = period_by_symbol.get(str(row.contract))
        if period is None:
            continue
        part = _load_session_events(
            period["path"],
            session_date=str(row.session_date),
            root_symbol=root_symbol,
            contract_symbol=str(row.contract),
            rth_start_minute=rth_start_minute,
            rth_end_minute=rth_end_minute,
            required_capability=required_capability,
        )
        if not part.empty:
            parts.append(part)

    if not parts:
        out = pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    else:
        out = pd.concat(parts, ignore_index=True)
        out = out.sort_values(["timestamp", "source_ordinal"], kind="mergesort").reset_index(drop=True)
    out.attrs["detail_granularity"] = "normalized_trade_event"
    out.attrs["price_path_semantics"] = SCID_RECORD_PRICE_PATH_SEMANTICS
    out.attrs["source_quality_label"] = (
        "Databento-compared Sierra trade-event replay after FIRST/LAST unbundled-trade "
        "reconstruction; source order retained; not exchange MBO sequencing."
    )
    out.attrs["required_capability"] = required_capability
    out.attrs["eligible_session_dates"] = eligible["session_date"].astype(str).tolist()
    out.attrs["blackout_session_dates"] = ineligible["session_date"].astype(str).tolist()
    out.attrs["timestamp_precision_ns"] = SIERRA_TIMESTAMP_PRECISION_NS
    return out


def _load_session_events(
    path: Path,
    *,
    session_date: str,
    root_symbol: str,
    contract_symbol: str,
    rth_start_minute: int,
    rth_end_minute: int,
    required_capability: str,
) -> pd.DataFrame:
    day = pd.Timestamp(session_date, tz=ET)
    start_et = day + pd.Timedelta(minutes=rth_start_minute)
    end_et = day + pd.Timedelta(minutes=rth_end_minute)
    start_utc = start_et.tz_convert("UTC").tz_localize(None).to_pydatetime()
    end_utc = end_et.tz_convert("UTC").tz_localize(None).to_pydatetime()
    buffer_us = 1_000_000
    raw = pq.read_table(
        path,
        columns=SCID_RECORD_COLUMNS,
        filters=[
            ("scid_datetime_us", ">=", _datetime_to_scid_us(start_utc) - buffer_us),
            ("scid_datetime_us", "<", _datetime_to_scid_us(end_utc) + buffer_us),
        ],
    ).to_pandas()
    if raw.empty:
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    raw["source_ordinal"] = np.arange(len(raw), dtype=np.int64)
    events, _ = reconstruct_sierra_trade_events(raw)
    in_window = events["scid_datetime_us"].between(
        _datetime_to_scid_us(start_utc), _datetime_to_scid_us(end_utc), inclusive="left"
    )
    events = events.loc[in_window].copy()
    if events.empty:
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    timestamps = pd.to_datetime(
        [SCID_EPOCH + timedelta(microseconds=int(value)) for value in events["scid_datetime_us"]]
    ).tz_localize("UTC").tz_convert(ET)
    price = events["price"].to_numpy(dtype=float)
    result = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": root_symbol,
            "contract_symbol": contract_symbol,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": events["volume"].to_numpy(dtype=np.int64),
            "signed_volume": events["signed_volume"].to_numpy(dtype=np.int64),
            "buy_volume": events["buy_volume"].to_numpy(dtype=np.int64),
            "sell_volume": events["sell_volume"].to_numpy(dtype=np.int64),
            "trades": np.ones(len(events), dtype=np.int64),
            "num_trades": np.ones(len(events), dtype=np.int64),
            "scid_datetime_us": events["scid_datetime_us"].to_numpy(dtype=np.int64),
            "last_scid_datetime_us": events["last_scid_datetime_us"].to_numpy(dtype=np.int64),
            "source_ordinal": events["source_ordinal"].to_numpy(dtype=np.int64),
            "side": events["side"].to_numpy(),
            "component_rows": events["component_rows"].to_numpy(dtype=np.int64),
            "timestamp_precision_ns": SIERRA_TIMESTAMP_PRECISION_NS,
            "timestamp_uncertainty_ns": SIERRA_TIMESTAMP_PRECISION_NS,
            "quality_capability": required_capability,
            "execution_granularity": "normalized_trade_event",
            "price_path_semantics": SCID_RECORD_PRICE_PATH_SEMANTICS,
            "raw_scid_open": price,
            "raw_scid_high": price,
            "raw_scid_low": price,
            "raw_scid_close": price,
        }
    )
    return result[_SCID_EXECUTION_COLUMNS]


def _load_quality_manifest(
    path: Path,
    *,
    required_capability: str,
    allow_unverified_for_tests: bool,
) -> pd.DataFrame:
    if allow_unverified_for_tests:
        return pd.DataFrame(
            columns=["session_date", "contract", required_capability]
        )
    if not path.exists():
        raise ValueError(f"Sierra event quality manifest not found: {path}")
    manifest = pd.read_csv(path, dtype={"session_date": "string", "contract": "string"})
    required = {"session_date", "contract", required_capability}
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"Sierra quality manifest is missing columns: {missing}")
    return manifest


def _requested_manifest_rows(
    manifest: pd.DataFrame,
    *,
    start: datetime | None,
    end: datetime | None,
    periods: list[dict],
) -> pd.DataFrame:
    if manifest.empty:
        dates = pd.date_range(
            pd.Timestamp(start).date(),
            (pd.Timestamp(end) - pd.Timedelta(microseconds=1)).date(),
            freq="B",
        )
        rows = []
        for date in dates:
            session_date = pd.Timestamp(date).date()
            period = next(
                (
                    item
                    for item in periods
                    if item["start"].date() <= session_date <= item["end"].date()
                ),
                None,
            )
            if period:
                rows.append(
                    {
                        "session_date": str(session_date),
                        "contract": period["symbol"],
                        next(
                            column
                            for column in manifest.columns
                            if column not in {"session_date", "contract"}
                        ): True,
                    }
                )
        return pd.DataFrame(rows, columns=manifest.columns)
    result = manifest.copy()
    dates = pd.to_datetime(result["session_date"])
    if start is not None:
        result = result.loc[dates >= pd.Timestamp(start).normalize()]
        dates = pd.to_datetime(result["session_date"])
    if end is not None:
        result = result.loc[dates < pd.Timestamp(end).normalize()]
    return result.reset_index(drop=True)


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


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
