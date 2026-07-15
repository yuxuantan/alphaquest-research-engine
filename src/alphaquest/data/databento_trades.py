from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from alphaquest.utils.time import parse_time


DEFAULT_LARGE_TRADE_SIZES = (10, 20)


def aggregate_trade_orderflow_1m(
    trades: pd.DataFrame,
    *,
    timezone: str = "America/New_York",
    root_symbol: str = "ES",
    contract_symbol_regex: str = r"^ES[HMUZ]\d$",
    rth_start: str = "09:30:00",
    rth_end: str = "16:00:00",
    complete_session_end: str | None = "15:59:00",
    large_trade_sizes: Iterable[int] = DEFAULT_LARGE_TRADE_SIZES,
) -> pd.DataFrame:
    """Aggregate Databento trade prints into active-contract RTH orderflow bars.

    Databento `side` is interpreted from the aggressor's perspective:
    `B` contributes positive signed volume and `A` contributes negative signed volume.
    For each RTH session, the active contract is selected by highest RTH trade volume.
    """

    if trades.empty:
        return _empty_orderflow_frame(large_trade_sizes)

    raw = _normalise_trade_frame(trades, timezone)
    if "action" in raw.columns:
        raw = raw[raw["action"].astype(str).eq("T")].copy()
    raw = raw[raw["contract_symbol"].astype(str).str.match(contract_symbol_regex, na=False)].copy()
    if raw.empty:
        return _empty_orderflow_frame(large_trade_sizes)

    start = parse_time(rth_start)
    end = parse_time(rth_end)
    tod = raw["timestamp"].dt.time
    raw = raw[(tod >= start) & (tod < end)].copy()
    if raw.empty:
        return _empty_orderflow_frame(large_trade_sizes)

    raw["session_date"] = raw["timestamp"].dt.tz_localize(None).dt.normalize()
    raw["minute"] = raw["timestamp"].dt.floor("min").dt.tz_localize(None)
    raw["size"] = pd.to_numeric(raw["size"], errors="coerce").fillna(0.0).astype(float)
    raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
    raw = raw.dropna(subset=["price"])
    if raw.empty:
        return _empty_orderflow_frame(large_trade_sizes)

    active = (
        raw.groupby(["session_date", "contract_symbol"], observed=True)["size"]
        .sum()
        .reset_index()
        .sort_values(["session_date", "size", "contract_symbol"])
        .groupby("session_date", observed=True)
        .tail(1)
    )
    active_map = dict(zip(active["session_date"], active["contract_symbol"], strict=False))
    raw = raw[raw["contract_symbol"].eq(raw["session_date"].map(active_map))].copy()
    if raw.empty:
        return _empty_orderflow_frame(large_trade_sizes)

    side = raw["side"].astype(str).str.upper()
    sign = np.select([side.eq("B"), side.eq("A")], [1.0, -1.0], default=0.0)
    raw["signed_size"] = raw["size"] * sign
    raw["buy_volume"] = np.where(sign > 0, raw["size"], 0.0)
    raw["sell_volume"] = np.where(sign < 0, raw["size"], 0.0)
    sizes = tuple(int(value) for value in large_trade_sizes)
    for threshold in sizes:
        raw[f"large{threshold}_signed_size"] = np.where(raw["size"] >= threshold, raw["signed_size"], 0.0)
        raw[f"large{threshold}_volume"] = np.where(raw["size"] >= threshold, raw["size"], 0.0)

    agg_spec = {
        "open": ("price", "first"),
        "high": ("price", "max"),
        "low": ("price", "min"),
        "close": ("price", "last"),
        "volume": ("size", "sum"),
        "signed_volume": ("signed_size", "sum"),
        "buy_volume": ("buy_volume", "sum"),
        "sell_volume": ("sell_volume", "sum"),
        "trades": ("size", "size"),
        "contract_symbol": ("contract_symbol", "last"),
    }
    for threshold in sizes:
        agg_spec[f"large{threshold}_signed_volume"] = (f"large{threshold}_signed_size", "sum")
        agg_spec[f"large{threshold}_volume"] = (f"large{threshold}_volume", "sum")

    bars = raw.groupby(["session_date", "minute"], observed=True).agg(**agg_spec).reset_index()
    bars = bars.rename(columns={"minute": "timestamp"})
    bars["symbol"] = root_symbol
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    if complete_session_end:
        session_max_time = bars.groupby("session_date")["timestamp"].max().dt.time
        complete_time = parse_time(complete_session_end)
        complete_sessions = session_max_time[session_max_time >= complete_time].index
        bars = bars[bars["session_date"].isin(complete_sessions)].copy()
    return _order_columns(bars, sizes).sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)


def build_trade_orderflow_cache(
    *,
    raw_dir: str | Path,
    output_csv: str | Path,
    monthly_cache_dir: str | Path | None = None,
    timezone: str = "America/New_York",
    root_symbol: str = "ES",
    contract_symbol_regex: str = r"^ES[HMUZ]\d$",
    rth_start: str = "09:30:00",
    rth_end: str = "16:00:00",
    complete_session_end: str | None = "15:59:00",
    large_trade_sizes: Iterable[int] = DEFAULT_LARGE_TRADE_SIZES,
    force: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    raw_path = Path(raw_dir)
    files = sorted(raw_path.glob("*.trades.dbn*"))
    if not files:
        raise ValueError(f"No Databento trades DBN files found in {raw_path}.")

    frames = []
    cache_dir = Path(monthly_cache_dir) if monthly_cache_dir else None
    for path in files:
        cached = _cache_path(cache_dir, path) if cache_dir else None
        if cached and cached.exists() and not force and cached.stat().st_mtime >= path.stat().st_mtime:
            _emit(status_callback, f"Using cached orderflow bars: {cached.name}")
            frames.append(pd.read_parquet(cached))
            continue

        _emit(status_callback, f"Reading Databento trades: {path.name}")
        raw = _read_databento_file(path)
        frame = aggregate_trade_orderflow_1m(
            raw,
            timezone=timezone,
            root_symbol=root_symbol,
            contract_symbol_regex=contract_symbol_regex,
            rth_start=rth_start,
            rth_end=rth_end,
            complete_session_end=None,
            large_trade_sizes=large_trade_sizes,
        )
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(cached, index=False)
        frames.append(frame)

    bars = pd.concat(frames, ignore_index=True) if frames else _empty_orderflow_frame(large_trade_sizes)
    if not bars.empty and complete_session_end:
        bars["session_date"] = pd.to_datetime(bars["timestamp"]).dt.normalize()
        session_max_time = bars.groupby("session_date")["timestamp"].max().dt.time
        complete_time = parse_time(complete_session_end)
        complete_sessions = session_max_time[session_max_time >= complete_time].index
        bars = bars[bars["session_date"].isin(complete_sessions)].drop(columns=["session_date"]).copy()
    bars = bars.sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(out, index=False)
    _emit(status_callback, f"Wrote {len(bars):,} orderflow bars to {out}")
    return bars


def _normalise_trade_frame(trades: pd.DataFrame, timezone: str) -> pd.DataFrame:
    raw = trades.copy()
    if "timestamp" not in raw.columns:
        if "ts_event" not in raw.columns:
            raise ValueError("Trades must include either timestamp or ts_event.")
        raw["timestamp"] = pd.to_datetime(raw["ts_event"], utc=True).dt.tz_convert(timezone)
    else:
        ts = pd.to_datetime(raw["timestamp"], utc=True)
        raw["timestamp"] = ts.dt.tz_convert(timezone)
    if "contract_symbol" not in raw.columns:
        if "symbol" not in raw.columns:
            raise ValueError("Trades must include symbol or contract_symbol.")
        raw["contract_symbol"] = raw["symbol"].astype(str)
    required = {"timestamp", "contract_symbol", "price", "size", "side"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Trades missing required column(s): {sorted(missing)}")
    return raw


def _read_databento_file(path: Path) -> pd.DataFrame:
    import databento as db

    return db.DBNStore.from_file(path).to_df().reset_index()


def _cache_path(cache_dir: Path | None, raw_file: Path) -> Path | None:
    if cache_dir is None:
        return None
    name = raw_file.name
    for suffix in [".trades.dbn.zst", ".trades.dbn", ".dbn.zst", ".dbn"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return cache_dir / f"{name}.rth_1m_orderflow.parquet"


def _order_columns(bars: pd.DataFrame, large_trade_sizes: Iterable[int]) -> pd.DataFrame:
    sizes = tuple(int(value) for value in large_trade_sizes)
    columns = [
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
    ]
    for threshold in sizes:
        columns.extend([f"large{threshold}_signed_volume", f"large{threshold}_volume"])
    columns.append("trades")
    return bars[columns]


def _empty_orderflow_frame(large_trade_sizes: Iterable[int]) -> pd.DataFrame:
    sizes = tuple(int(value) for value in large_trade_sizes)
    columns = [
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
    ]
    for threshold in sizes:
        columns.extend([f"large{threshold}_signed_volume", f"large{threshold}_volume"])
    columns.append("trades")
    return pd.DataFrame(columns=columns)


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
