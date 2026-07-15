from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_WINDOWS = (3, 5, 15, 30, 60)
DEFAULT_LARGE_TRADE_SIZES = (10, 20)
DEFAULT_PRICE_CAP_TICKS = (8, 16, 24)


def build_es_mes_flow_divergence_cache(
    *,
    es_csv: str | Path,
    mes_csv: str | Path,
    output_csv: str | Path | None = None,
    windows: Iterable[int] = DEFAULT_WINDOWS,
    large_trade_sizes: Iterable[int] = DEFAULT_LARGE_TRADE_SIZES,
    price_cap_ticks: Iterable[int] = DEFAULT_PRICE_CAP_TICKS,
    tick_size: float = 0.25,
    min_period_fraction: float = 1.0,
    market_symbol: str = "ES",
    market_prefix: str = "es",
    status_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """Build a trading cache with MES-vs-market completed-flow features.

    The output keeps the market OHLCV/orderflow columns as the tradable market
    and adds rolling market/MES imbalance, return, and divergence columns.
    Rolling windows are grouped by session date, include the current completed
    minute, and never use later bars.
    """

    windows = _positive_ints(windows, "windows")
    large_trade_sizes = _positive_ints(large_trade_sizes, "large_trade_sizes")
    price_cap_ticks = _positive_ints(price_cap_ticks, "price_cap_ticks")
    market_symbol = str(market_symbol).upper()
    market_prefix = str(market_prefix).strip().lower()
    if not market_symbol:
        raise ValueError("market_symbol must be non-empty.")
    if not market_prefix or not market_prefix.replace("_", "").isalnum():
        raise ValueError("market_prefix must be a non-empty alphanumeric/underscore string.")
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    if not (0 < min_period_fraction <= 1):
        raise ValueError("min_period_fraction must be in (0, 1].")

    _emit(status_callback, f"Reading {market_symbol} trade-orderflow cache: {es_csv}")
    es = _load_source_csv(es_csv, market_symbol)
    _emit(status_callback, f"Reading MES trade-orderflow cache: {mes_csv}")
    mes = _load_source_csv(mes_csv, "MES")
    _emit(status_callback, f"Aligning {market_symbol} and MES bars by timestamp.")
    out = _align_sources(es, mes, market_symbol=market_symbol)
    _emit(status_callback, f"Aligned {len(out):,} shared {market_symbol}/MES minute bars.")
    out = _add_completed_flow_features(
        out,
        windows=windows,
        large_trade_sizes=large_trade_sizes,
        price_cap_ticks=price_cap_ticks,
        tick_size=tick_size,
        min_period_fraction=min_period_fraction,
        market_prefix=market_prefix,
    )
    out = out.replace([np.inf, -np.inf], np.nan)
    if output_csv is not None:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_out = out.copy()
        write_out["timestamp"] = write_out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        write_out.to_csv(output_path, index=False)
        _emit(status_callback, f"Wrote {market_symbol}/MES flow-divergence cache: {output_path}")
    return out


def _load_source_csv(path: str | Path, expected_symbol: str) -> pd.DataFrame:
    source_path = Path(path)
    if source_path.suffix.lower() == ".parquet":
        df = pd.read_parquet(source_path)
    else:
        df = pd.read_csv(source_path)
    required = {"timestamp", "open", "high", "low", "close", "volume", "signed_volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{expected_symbol} cache missing required columns: {sorted(missing)}")
    out = df.copy()
    out["timestamp"] = _parse_timestamp(out["timestamp"])
    out = out.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
    numeric_columns = [column for column in out.columns if column not in {"timestamp", "symbol", "contract_symbol"}]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if "symbol" not in out.columns:
        out["symbol"] = expected_symbol
    return out


def _parse_timestamp(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values)
    if timestamps.dt.tz is not None:
        timestamps = timestamps.dt.tz_convert("America/New_York").dt.tz_localize(None)
    return timestamps


def _align_sources(es: pd.DataFrame, mes: pd.DataFrame, *, market_symbol: str) -> pd.DataFrame:
    es_columns = list(es.columns)
    mes_feature_columns = [
        column for column in mes.columns if column not in {"timestamp", "symbol", "contract_symbol"}
    ]
    mes_prefixed = mes[["timestamp", *mes_feature_columns]].rename(
        columns={column: f"mes_{column}" for column in mes_feature_columns}
    )
    out = es[es_columns].merge(mes_prefixed, on="timestamp", how="inner", validate="one_to_one")
    out["symbol"] = market_symbol
    return out.sort_values("timestamp").reset_index(drop=True)


def _add_completed_flow_features(
    df: pd.DataFrame,
    *,
    windows: list[int],
    large_trade_sizes: list[int],
    price_cap_ticks: list[int],
    tick_size: float,
    min_period_fraction: float,
    market_prefix: str,
) -> pd.DataFrame:
    frames = []
    work = df.copy()
    work["_session_date"] = work["timestamp"].dt.date
    for _, group in work.groupby("_session_date", sort=True, dropna=False):
        group = group.sort_values("timestamp").copy()
        feature_columns: dict[str, pd.Series] = {}
        for window in windows:
            min_periods = max(1, int(window * min_period_fraction))
            market_imbalance = _rolling_imbalance(group, "signed_volume", "volume", window, min_periods)
            mes_imbalance = _rolling_imbalance(group, "mes_signed_volume", "mes_volume", window, min_periods)
            suffix = str(window)
            market_return_ticks = (
                pd.to_numeric(group["close"], errors="coerce")
                - pd.to_numeric(group["open"], errors="coerce").shift(window - 1)
            ) / tick_size
            mes_return_ticks = (
                pd.to_numeric(group["mes_close"], errors="coerce")
                - pd.to_numeric(group["mes_open"], errors="coerce").shift(window - 1)
            ) / tick_size
            feature_columns[f"{market_prefix}_trade_orderflow_imbalance_{suffix}"] = market_imbalance
            feature_columns[f"mes_trade_orderflow_imbalance_{suffix}"] = mes_imbalance
            feature_columns[f"{market_prefix}_minus_mes_imbalance_{suffix}"] = market_imbalance - mes_imbalance
            feature_columns[f"mes_minus_{market_prefix}_imbalance_{suffix}"] = mes_imbalance - market_imbalance
            feature_columns[f"{market_prefix}_trade_orderflow_return_ticks_{suffix}"] = market_return_ticks
            feature_columns[f"mes_trade_orderflow_return_ticks_{suffix}"] = mes_return_ticks
            feature_columns[f"{market_prefix}_minus_mes_return_ticks_{suffix}"] = market_return_ticks - mes_return_ticks
            feature_columns[f"mes_minus_{market_prefix}_return_ticks_{suffix}"] = mes_return_ticks - market_return_ticks
            for size in large_trade_sizes:
                market_large = _rolling_imbalance(
                    group,
                    f"large{size}_signed_volume",
                    f"large{size}_volume",
                    window,
                    min_periods,
                )
                mes_large = _rolling_imbalance(
                    group,
                    f"mes_large{size}_signed_volume",
                    f"mes_large{size}_volume",
                    window,
                    min_periods,
                )
                feature_columns[f"{market_prefix}_trade_orderflow_large{size}_imbalance_{suffix}"] = market_large
                feature_columns[f"mes_trade_orderflow_large{size}_imbalance_{suffix}"] = mes_large
                feature_columns[f"{market_prefix}_minus_mes_large{size}_imbalance_{suffix}"] = market_large - mes_large
                feature_columns[f"mes_minus_{market_prefix}_large{size}_imbalance_{suffix}"] = mes_large - market_large
                for cap_ticks in price_cap_ticks:
                    cap_col = f"mes_large{size}_imbalance_{market_prefix}_return_lte_{cap_ticks}_{suffix}"
                    feature_columns[cap_col] = mes_large.where(market_return_ticks <= cap_ticks)
        features = pd.DataFrame(feature_columns, index=group.index)
        frames.append(pd.concat([group, features], axis=1))
    return pd.concat(frames, ignore_index=True).drop(columns=["_session_date"])


def _rolling_imbalance(
    df: pd.DataFrame,
    signed_column: str,
    volume_column: str,
    window: int,
    min_periods: int,
) -> pd.Series:
    if {signed_column, volume_column} - set(df.columns):
        return pd.Series(np.nan, index=df.index)
    signed = pd.to_numeric(df[signed_column], errors="coerce").rolling(window, min_periods=min_periods).sum()
    volume = pd.to_numeric(df[volume_column], errors="coerce").rolling(window, min_periods=min_periods).sum()
    return signed / volume.replace(0.0, np.nan)


def _positive_ints(values: Iterable[int], name: str) -> list[int]:
    out = [int(value) for value in values]
    if not out or any(value <= 0 for value in out):
        raise ValueError(f"{name} must contain positive integers.")
    return out


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
