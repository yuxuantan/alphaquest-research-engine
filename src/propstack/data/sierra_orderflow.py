from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re

import numpy as np
import pandas as pd

from propstack.utils.time import parse_time


SIERRA_FILE_PATTERNS = ("*.csv", "*.txt")

COLUMN_ALIASES = {
    "askvolume": "ask_volume",
    "ask_volume": "ask_volume",
    "ask_vol": "ask_volume",
    "bidvolume": "bid_volume",
    "bid_volume": "bid_volume",
    "bid_vol": "bid_volume",
    "close": "close",
    "datetime": "timestamp",
    "date_time": "timestamp",
    "dt": "timestamp",
    "h": "high",
    "high": "high",
    "l": "low",
    "last": "close",
    "low": "low",
    "num_trades": "trades",
    "number_of_trades": "trades",
    "numberoftrades": "trades",
    "o": "open",
    "open": "open",
    "time_stamp": "timestamp",
    "timestamp": "timestamp",
    "trades": "trades",
    "v": "volume",
    "vol": "volume",
    "volume": "volume",
}

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
    "trades",
]


def build_sierra_orderflow_cache(
    *,
    raw_path: str | Path,
    output_csv: str | Path,
    input_timezone: str = "America/New_York",
    output_timezone: str = "America/New_York",
    root_symbol: str = "ES",
    contract_symbol: str | None = None,
    rth_start: str = "09:30:00",
    rth_end: str = "16:00:00",
    complete_session_end: str | None = "15:59:00",
    active_contract_mode: str = "none",
    chunksize: int | None = 1_000_000,
    status_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """Build a 1-minute orderflow cache from Sierra Chart text/CSV exports.

    Sierra `AskVolume` is treated as aggressive buy volume, `BidVolume` as
    aggressive sell volume, and signed volume is `AskVolume - BidVolume`.
    The output intentionally contains only bar-level aggregate fields.
    """

    files = list_sierra_orderflow_files(raw_path)
    if not files:
        raise ValueError(f"No Sierra CSV/TXT files found in {raw_path}.")

    parts: list[pd.DataFrame] = []
    for path in files:
        inferred_contract = contract_symbol or _contract_symbol_from_path(path)
        _emit(status_callback, f"Reading Sierra orderflow export: {path}")
        for raw in _read_sierra_chunks(path, chunksize):
            part = aggregate_sierra_orderflow_frame(
                raw,
                input_timezone=input_timezone,
                output_timezone=output_timezone,
                root_symbol=root_symbol,
                contract_symbol=inferred_contract,
                rth_start=rth_start,
                rth_end=rth_end,
            )
            if not part.empty:
                parts.append(part)

    bars = _combine_minute_parts(parts)
    if bars.empty:
        bars = pd.DataFrame(columns=OUTPUT_COLUMNS)
    else:
        if active_contract_mode not in {"none", "dominant_session_volume"}:
            raise ValueError(
                "active_contract_mode must be one of: 'none', 'dominant_session_volume'."
            )
        if active_contract_mode == "dominant_session_volume":
            bars = _select_dominant_session_contract(bars)
        if complete_session_end:
            bars = _drop_incomplete_sessions(bars, complete_session_end)
        bars = bars.sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)
        bars = bars[OUTPUT_COLUMNS]

    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(out, index=False)
    _emit(status_callback, f"Wrote {len(bars):,} Sierra orderflow bars to {out}")
    return bars


def aggregate_sierra_orderflow_frame(
    raw: pd.DataFrame,
    *,
    input_timezone: str = "America/New_York",
    output_timezone: str = "America/New_York",
    root_symbol: str = "ES",
    contract_symbol: str = "ES",
    rth_start: str = "09:30:00",
    rth_end: str = "16:00:00",
) -> pd.DataFrame:
    """Normalize Sierra rows and aggregate them to 1-minute orderflow bars."""

    normalised = _normalise_sierra_frame(
        raw,
        input_timezone=input_timezone,
        output_timezone=output_timezone,
        root_symbol=root_symbol,
        contract_symbol=contract_symbol,
    )
    if normalised.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    start = parse_time(rth_start)
    end = parse_time(rth_end)
    tod = normalised["timestamp"].dt.time
    normalised = normalised[(tod >= start) & (tod < end)].copy()
    if normalised.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    normalised["minute"] = normalised["timestamp"].dt.floor("min")
    normalised = normalised.sort_values(["minute", "timestamp"], kind="mergesort")
    bars = (
        normalised.groupby(["minute", "symbol", "contract_symbol"], sort=True, observed=True)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            signed_volume=("signed_volume", "sum"),
            buy_volume=("buy_volume", "sum"),
            sell_volume=("sell_volume", "sum"),
            trades=("trades", "sum"),
        )
        .reset_index()
        .rename(columns={"minute": "timestamp"})
    )
    return bars[OUTPUT_COLUMNS]


def list_sierra_orderflow_files(raw_path: str | Path) -> list[Path]:
    path = Path(raw_path)
    if path.is_file():
        return [path]
    files: list[Path] = []
    for pattern in SIERRA_FILE_PATTERNS:
        files.extend(path.glob(pattern))
    return sorted(files)


def _normalise_sierra_frame(
    raw: pd.DataFrame,
    *,
    input_timezone: str,
    output_timezone: str,
    root_symbol: str,
    contract_symbol: str,
) -> pd.DataFrame:
    out = raw.copy()
    out.columns = [_normalise_column_name(column) for column in out.columns]

    missing = {"open", "high", "low", "close", "volume", "bid_volume", "ask_volume"} - set(
        out.columns
    )
    if missing:
        raise ValueError(f"Sierra export missing required column(s): {sorted(missing)}")

    timestamp_text = _timestamp_text(out)
    out["timestamp"] = _parse_timestamps(timestamp_text, input_timezone, output_timezone)
    out = out.dropna(subset=["timestamp"]).copy()
    if out.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    for column in ["open", "high", "low", "close", "volume", "bid_volume", "ask_volume"]:
        out[column] = _numeric_series(out[column])
    if "trades" in out.columns:
        out["trades"] = _numeric_series(out["trades"])
    else:
        out["trades"] = 1.0

    out = out.dropna(subset=["open", "high", "low", "close", "volume", "bid_volume", "ask_volume"])
    if out.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    out["symbol"] = root_symbol
    out["contract_symbol"] = contract_symbol
    out["buy_volume"] = out["ask_volume"]
    out["sell_volume"] = out["bid_volume"]
    out["signed_volume"] = out["buy_volume"] - out["sell_volume"]
    return out[
        [
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
        ]
    ]


def _timestamp_text(df: pd.DataFrame) -> pd.Series:
    if "timestamp" in df.columns:
        return df["timestamp"].astype("string").str.strip()
    if {"date", "time"}.issubset(df.columns):
        return df["date"].astype("string").str.strip() + " " + df["time"].astype("string").str.strip()
    raise ValueError("Sierra export must include either timestamp/datetime or Date and Time columns.")


def _parse_timestamps(
    timestamp_text: pd.Series,
    input_timezone: str,
    output_timezone: str,
) -> pd.Series:
    parsed = pd.to_datetime(timestamp_text, errors="coerce")
    if parsed.dt.tz is None:
        localized = parsed.dt.tz_localize(
            input_timezone,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
    else:
        localized = parsed.dt.tz_convert(input_timezone)
    return localized.dt.tz_convert(output_timezone).dt.tz_localize(None)


def _numeric_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce")
    cleaned = values.astype("string").str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def _normalise_column_name(column: object) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
    compact = key.replace("_", "")
    return COLUMN_ALIASES.get(key, COLUMN_ALIASES.get(compact, key))


def _combine_minute_parts(parts: list[pd.DataFrame]) -> pd.DataFrame:
    if not parts:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    raw = pd.concat(parts, ignore_index=True)
    if raw.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    raw = raw.sort_values(["timestamp", "contract_symbol"], kind="mergesort")
    combined = (
        raw.groupby(["timestamp", "symbol", "contract_symbol"], sort=True, observed=True)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            signed_volume=("signed_volume", "sum"),
            buy_volume=("buy_volume", "sum"),
            sell_volume=("sell_volume", "sum"),
            trades=("trades", "sum"),
        )
        .reset_index()
    )
    return combined[OUTPUT_COLUMNS]


def _select_dominant_session_contract(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return bars
    work = bars.copy()
    work["session_date"] = pd.to_datetime(work["timestamp"]).dt.normalize()
    active = (
        work.groupby(["session_date", "contract_symbol"], observed=True)["volume"]
        .sum()
        .reset_index()
        .sort_values(["session_date", "volume", "contract_symbol"])
        .groupby("session_date", observed=True)
        .tail(1)
    )
    active_map = dict(zip(active["session_date"], active["contract_symbol"], strict=False))
    selected = work[work["contract_symbol"].eq(work["session_date"].map(active_map))].copy()
    return selected.drop(columns=["session_date"])


def _drop_incomplete_sessions(bars: pd.DataFrame, complete_session_end: str) -> pd.DataFrame:
    work = bars.copy()
    work["session_date"] = pd.to_datetime(work["timestamp"]).dt.normalize()
    session_max_time = work.groupby("session_date")["timestamp"].max().dt.time
    complete_time = parse_time(complete_session_end)
    complete_sessions = session_max_time[session_max_time >= complete_time].index
    return work[work["session_date"].isin(complete_sessions)].drop(columns=["session_date"]).copy()


def _read_sierra_chunks(path: Path, chunksize: int | None):
    reader = pd.read_csv(path, chunksize=chunksize, skipinitialspace=True)
    if isinstance(reader, pd.DataFrame):
        yield reader
    else:
        yield from reader


def _contract_symbol_from_path(path: Path) -> str:
    return path.stem.strip() or "ES"


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
