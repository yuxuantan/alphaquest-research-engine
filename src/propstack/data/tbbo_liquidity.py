from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from propstack.utils.time import parse_time


DEFAULT_WINDOWS = (3, 5)


def aggregate_tbbo_liquidity_1m(
    tbbo: pd.DataFrame,
    *,
    timezone: str = "America/New_York",
    root_symbol: str = "ES",
    contract_symbol_regex: str = r"^ES[HMUZ]\d$",
    rth_start: str = "09:30:00",
    rth_end: str = "16:00:00",
    complete_session_end: str | None = "15:59:00",
    windows: Iterable[int] = DEFAULT_WINDOWS,
    tick_size: float = 0.25,
    depth_floor: float = 1.0,
) -> pd.DataFrame:
    """Aggregate decoded Databento TBBO rows into 1-minute quote-liquidity bars.

    The output is a normal OHLCV cache that can be loaded through the existing CSV
    pipeline. TBBO rows are expected to include top-of-book prices and sizes; if a
    trade price is unavailable, the top-of-book midpoint is used for OHLC.
    """

    windows = _positive_ints(windows, "windows")
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    if depth_floor < 0:
        raise ValueError("depth_floor must be non-negative.")
    if tbbo.empty:
        return _empty_liquidity_frame(windows)

    raw = _normalise_tbbo_frame(tbbo, timezone)
    raw = raw[raw["contract_symbol"].astype(str).str.match(contract_symbol_regex, na=False)].copy()
    if raw.empty:
        return _empty_liquidity_frame(windows)

    start = parse_time(rth_start)
    end = parse_time(rth_end)
    tod = raw["timestamp"].dt.time
    raw = raw[(tod >= start) & (tod < end)].copy()
    if raw.empty:
        return _empty_liquidity_frame(windows)

    raw["session_date"] = raw["timestamp"].dt.tz_localize(None).dt.normalize()
    raw["minute"] = raw["timestamp"].dt.floor("min").dt.tz_localize(None)
    raw["mid_price"] = (raw["bid_price"] + raw["ask_price"]) / 2.0
    raw["price_for_ohlc"] = raw["price"].where(raw["price"].notna(), raw["mid_price"])
    raw = raw.dropna(subset=["price_for_ohlc", "bid_price", "ask_price", "bid_size", "ask_size"])
    if raw.empty:
        return _empty_liquidity_frame(windows)

    active = (
        raw.assign(_active_weight=raw["size"].where(raw["size"] > 0, 1.0))
        .groupby(["session_date", "contract_symbol"], observed=True)["_active_weight"]
        .sum()
        .reset_index()
        .sort_values(["session_date", "_active_weight", "contract_symbol"])
        .groupby("session_date", observed=True)
        .tail(1)
    )
    active_map = dict(zip(active["session_date"], active["contract_symbol"], strict=False))
    raw = raw[raw["contract_symbol"].eq(raw["session_date"].map(active_map))].copy()
    if raw.empty:
        return _empty_liquidity_frame(windows)

    side = raw["side"].astype(str).str.upper()
    sign = np.select([side.eq("B"), side.eq("A")], [1.0, -1.0], default=0.0)
    raw["signed_size"] = raw["size"] * sign
    raw["buy_volume"] = np.where(sign > 0, raw["size"], 0.0)
    raw["sell_volume"] = np.where(sign < 0, raw["size"], 0.0)
    raw["quote_imbalance"] = _quote_imbalance(raw["bid_size"], raw["ask_size"])
    raw["spread"] = raw["ask_price"] - raw["bid_price"]

    bars = (
        raw.groupby(["session_date", "minute"], observed=True)
        .agg(
            open=("price_for_ohlc", "first"),
            high=("price_for_ohlc", "max"),
            low=("price_for_ohlc", "min"),
            close=("price_for_ohlc", "last"),
            volume=("size", "sum"),
            signed_volume=("signed_size", "sum"),
            buy_volume=("buy_volume", "sum"),
            sell_volume=("sell_volume", "sum"),
            trades=("size", "size"),
            contract_symbol=("contract_symbol", "last"),
            tbbo_bid_price_close=("bid_price", "last"),
            tbbo_ask_price_close=("ask_price", "last"),
            tbbo_bid_size_close=("bid_size", "last"),
            tbbo_ask_size_close=("ask_size", "last"),
            tbbo_bid_size_min=("bid_size", "min"),
            tbbo_ask_size_min=("ask_size", "min"),
            tbbo_bid_size_mean=("bid_size", "mean"),
            tbbo_ask_size_mean=("ask_size", "mean"),
            tbbo_spread_close=("spread", "last"),
            tbbo_spread_max=("spread", "max"),
            tbbo_quote_imbalance_close=("quote_imbalance", "last"),
            tbbo_quote_imbalance_mean=("quote_imbalance", "mean"),
            tbbo_events=("price_for_ohlc", "size"),
        )
        .reset_index()
        .rename(columns={"minute": "timestamp"})
    )
    bars["symbol"] = root_symbol
    bars["tbbo_mid_price_close"] = (bars["tbbo_bid_price_close"] + bars["tbbo_ask_price_close"]) / 2.0
    bars["tbbo_spread_ticks_close"] = bars["tbbo_spread_close"] / tick_size
    bars["tbbo_spread_ticks_max"] = bars["tbbo_spread_max"] / tick_size
    bars["tbbo_aggressive_imbalance_1"] = _safe_divide(bars["signed_volume"], bars["volume"])
    bars = _add_rolling_liquidity_features(bars, windows, depth_floor)

    if complete_session_end:
        session_max_time = bars.groupby("session_date")["timestamp"].max().dt.time
        complete_time = parse_time(complete_session_end)
        complete_sessions = session_max_time[session_max_time >= complete_time].index
        bars = bars[bars["session_date"].isin(complete_sessions)].copy()

    bars = bars.drop(columns=["session_date"]).sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)
    return _order_columns(bars, windows)


def build_tbbo_liquidity_cache(
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
    windows: Iterable[int] = DEFAULT_WINDOWS,
    tick_size: float = 0.25,
    depth_floor: float = 1.0,
    force: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    raw_path = Path(raw_dir)
    files = sorted(raw_path.glob("*.tbbo.dbn*"))
    if not files:
        raise ValueError(f"No Databento TBBO DBN files found in {raw_path}.")

    frames = []
    cache_dir = Path(monthly_cache_dir) if monthly_cache_dir else None
    for path in files:
        cached = _cache_path(cache_dir, path) if cache_dir else None
        if cached and cached.exists() and not force and cached.stat().st_mtime >= path.stat().st_mtime:
            _emit(status_callback, f"Using cached TBBO liquidity bars: {cached.name}")
            frames.append(pd.read_parquet(cached))
            continue

        _emit(status_callback, f"Reading Databento TBBO: {path.name}")
        raw = _read_databento_file(path)
        frame = aggregate_tbbo_liquidity_1m(
            raw,
            timezone=timezone,
            root_symbol=root_symbol,
            contract_symbol_regex=contract_symbol_regex,
            rth_start=rth_start,
            rth_end=rth_end,
            complete_session_end=None,
            windows=windows,
            tick_size=tick_size,
            depth_floor=depth_floor,
        )
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(cached, index=False)
        frames.append(frame)

    bars = pd.concat(frames, ignore_index=True) if frames else _empty_liquidity_frame(windows)
    if not bars.empty and complete_session_end:
        bars["session_date"] = pd.to_datetime(bars["timestamp"]).dt.normalize()
        session_max_time = bars.groupby("session_date")["timestamp"].max().dt.time
        complete_time = parse_time(complete_session_end)
        complete_sessions = session_max_time[session_max_time >= complete_time].index
        bars = bars[bars["session_date"].isin(complete_sessions)].drop(columns=["session_date"]).copy()
    bars = bars.sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_out = bars.copy()
    write_out["timestamp"] = pd.to_datetime(write_out["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    write_out.to_csv(out, index=False)
    _emit(status_callback, f"Wrote {len(bars):,} TBBO liquidity bars to {out}")
    return bars


def _normalise_tbbo_frame(tbbo: pd.DataFrame, timezone: str) -> pd.DataFrame:
    raw = tbbo.copy()
    if "timestamp" not in raw.columns:
        if "ts_event" not in raw.columns:
            raise ValueError("TBBO rows must include either timestamp or ts_event.")
        raw["timestamp"] = pd.to_datetime(raw["ts_event"], utc=True).dt.tz_convert(timezone)
    else:
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True).dt.tz_convert(timezone)
    if "contract_symbol" not in raw.columns:
        if "symbol" not in raw.columns:
            raise ValueError("TBBO rows must include symbol or contract_symbol.")
        raw["contract_symbol"] = raw["symbol"].astype(str)

    _coalesce(raw, "bid_price", ("bid_price", "bid_px", "bid_px_00"))
    _coalesce(raw, "ask_price", ("ask_price", "ask_px", "ask_px_00"))
    _coalesce(raw, "bid_size", ("bid_size", "bid_sz", "bid_sz_00"))
    _coalesce(raw, "ask_size", ("ask_size", "ask_sz", "ask_sz_00"))
    if "price" not in raw.columns:
        raw["price"] = np.nan
    if "size" not in raw.columns:
        raw["size"] = 0.0
    if "side" not in raw.columns:
        raw["side"] = ""

    required = {"timestamp", "contract_symbol", "bid_price", "ask_price", "bid_size", "ask_size"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"TBBO rows missing required column(s): {sorted(missing)}")
    for column in ["price", "size", "bid_price", "ask_price", "bid_size", "ask_size"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw["size"] = raw["size"].fillna(0.0)
    return raw


def _coalesce(df: pd.DataFrame, target: str, candidates: Iterable[str]) -> None:
    if target in df.columns:
        return
    for candidate in candidates:
        if candidate in df.columns:
            df[target] = df[candidate]
            return


def _add_rolling_liquidity_features(
    bars: pd.DataFrame,
    windows: list[int],
    depth_floor: float,
) -> pd.DataFrame:
    frames = []
    work = bars.sort_values("timestamp").copy()
    for _, group in work.groupby("session_date", sort=True, dropna=False):
        group = group.copy()
        for window in windows:
            suffix = str(window)
            volume = group["volume"].rolling(window, min_periods=1).sum()
            signed = group["signed_volume"].rolling(window, min_periods=1).sum()
            bid_min = group["tbbo_bid_size_min"].rolling(window, min_periods=1).min()
            ask_min = group["tbbo_ask_size_min"].rolling(window, min_periods=1).min()
            group[f"tbbo_volume_{suffix}"] = volume
            group[f"tbbo_signed_volume_{suffix}"] = signed
            group[f"tbbo_aggressive_imbalance_{suffix}"] = _safe_divide(signed, volume)
            group[f"tbbo_bid_size_min_{suffix}"] = bid_min
            group[f"tbbo_ask_size_min_{suffix}"] = ask_min
            group[f"tbbo_bid_refill_ratio_{suffix}"] = (group["tbbo_bid_size_close"] + depth_floor) / (
                bid_min + depth_floor
            )
            group[f"tbbo_ask_refill_ratio_{suffix}"] = (group["tbbo_ask_size_close"] + depth_floor) / (
                ask_min + depth_floor
            )
            group[f"tbbo_spread_ticks_max_{suffix}"] = group["tbbo_spread_ticks_max"].rolling(
                window, min_periods=1
            ).max()
            group[f"tbbo_quote_imbalance_change_{suffix}"] = group["tbbo_quote_imbalance_close"] - group[
                "tbbo_quote_imbalance_close"
            ].shift(window)
        frames.append(group)
    return pd.concat(frames, ignore_index=True)


def _quote_imbalance(bid_size: pd.Series, ask_size: pd.Series) -> pd.Series:
    return _safe_divide(bid_size - ask_size, bid_size + ask_size)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0.0, np.nan)


def _read_databento_file(path: Path) -> pd.DataFrame:
    import databento as db

    return db.DBNStore.from_file(path).to_df().reset_index()


def _cache_path(cache_dir: Path | None, raw_file: Path) -> Path | None:
    if cache_dir is None:
        return None
    name = raw_file.name
    for suffix in [".tbbo.dbn.zst", ".tbbo.dbn", ".dbn.zst", ".dbn"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return cache_dir / f"{name}.rth_1m_tbbo_liquidity.parquet"


def _order_columns(bars: pd.DataFrame, windows: Iterable[int]) -> pd.DataFrame:
    base = _liquidity_columns(windows)
    cols = [column for column in base if column in bars.columns]
    cols.extend([column for column in bars.columns if column not in cols])
    return bars[cols]


def _liquidity_columns(windows: Iterable[int]) -> list[str]:
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
        "trades",
        "tbbo_events",
        "tbbo_bid_price_close",
        "tbbo_ask_price_close",
        "tbbo_mid_price_close",
        "tbbo_bid_size_close",
        "tbbo_ask_size_close",
        "tbbo_bid_size_min",
        "tbbo_ask_size_min",
        "tbbo_bid_size_mean",
        "tbbo_ask_size_mean",
        "tbbo_spread_close",
        "tbbo_spread_max",
        "tbbo_spread_ticks_close",
        "tbbo_spread_ticks_max",
        "tbbo_quote_imbalance_close",
        "tbbo_quote_imbalance_mean",
        "tbbo_aggressive_imbalance_1",
    ]
    for window in windows:
        suffix = str(window)
        columns.extend(
            [
                f"tbbo_volume_{suffix}",
                f"tbbo_signed_volume_{suffix}",
                f"tbbo_aggressive_imbalance_{suffix}",
                f"tbbo_bid_size_min_{suffix}",
                f"tbbo_ask_size_min_{suffix}",
                f"tbbo_bid_refill_ratio_{suffix}",
                f"tbbo_ask_refill_ratio_{suffix}",
                f"tbbo_spread_ticks_max_{suffix}",
                f"tbbo_quote_imbalance_change_{suffix}",
            ]
        )
    return columns


def _empty_liquidity_frame(windows: Iterable[int]) -> pd.DataFrame:
    return pd.DataFrame(columns=_liquidity_columns(windows))


def _positive_ints(values: Iterable[int], name: str) -> list[int]:
    out = [int(value) for value in values]
    if not out or any(value <= 0 for value in out):
        raise ValueError(f"{name} must contain positive integers.")
    return out


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
