from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_WINDOWS = (5, 15, 30, 60)


def build_es_nq_lead_lag_cache(
    *,
    es_path: str | Path,
    nq_path: str | Path,
    output_parquet: str | Path | None = None,
    output_csv: str | Path | None = None,
    windows: Iterable[int] = DEFAULT_WINDOWS,
    min_period_fraction: float = 1.0,
    status_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """Build an ES trading cache with completed NQ lead-lag features.

    The output keeps ES as the tradable market and adds NQ price/order-flow
    columns plus rolling ES/NQ returns. Rolling windows are grouped by RTH
    session date, include only the current completed minute and earlier
    minutes, and never use later bars.
    """

    windows = _positive_ints(windows, "windows")
    if not (0 < min_period_fraction <= 1):
        raise ValueError("min_period_fraction must be in (0, 1].")

    _emit(status_callback, f"Reading ES cache: {es_path}")
    es = _load_source_table(es_path, "ES")
    _emit(status_callback, f"Reading NQ cache: {nq_path}")
    nq = _load_source_table(nq_path, "NQ")
    _emit(status_callback, "Aligning ES and NQ bars by timestamp.")
    out = _align_sources(es, nq)
    _emit(status_callback, f"Aligned {len(out):,} shared ES/NQ minute bars.")
    out = _add_completed_lead_lag_features(
        out,
        windows=windows,
        min_period_fraction=min_period_fraction,
    )
    out = out.replace([np.inf, -np.inf], np.nan)

    if output_parquet is not None:
        output_path = Path(output_parquet)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(output_path, index=False)
        _emit(status_callback, f"Wrote ES/NQ lead-lag parquet: {output_path}")
    if output_csv is not None:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_out = out.copy()
        write_out["timestamp"] = write_out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        write_out.to_csv(output_path, index=False)
        _emit(status_callback, f"Wrote ES/NQ lead-lag CSV: {output_path}")
    return out


def _load_source_table(path: str | Path, expected_symbol: str) -> pd.DataFrame:
    source_path = Path(path)
    if source_path.suffix.lower() == ".parquet":
        df = pd.read_parquet(source_path)
    else:
        df = pd.read_csv(source_path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
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


def _align_sources(es: pd.DataFrame, nq: pd.DataFrame) -> pd.DataFrame:
    es_columns = list(es.columns)
    nq_feature_columns = [
        column for column in nq.columns if column not in {"timestamp", "symbol", "contract_symbol"}
    ]
    nq_prefixed = nq[["timestamp", *nq_feature_columns]].rename(
        columns={column: f"nq_{column}" for column in nq_feature_columns}
    )
    out = es[es_columns].merge(nq_prefixed, on="timestamp", how="inner", validate="one_to_one")
    out["symbol"] = "ES"
    return out.sort_values("timestamp").reset_index(drop=True)


def _add_completed_lead_lag_features(
    df: pd.DataFrame,
    *,
    windows: list[int],
    min_period_fraction: float,
) -> pd.DataFrame:
    frames = []
    work = df.copy()
    work["_session_date"] = work["timestamp"].dt.date
    for _, group in work.groupby("_session_date", sort=True, dropna=False):
        group = group.sort_values("timestamp").copy()
        feature_columns: dict[str, pd.Series] = {}
        for window in windows:
            min_periods = max(1, int(window * min_period_fraction))
            suffix = str(window)
            es_return_bps = _rolling_return_bps(group["open"], group["close"], window, min_periods)
            nq_return_bps = _rolling_return_bps(group["nq_open"], group["nq_close"], window, min_periods)
            feature_columns[f"es_return_bps_{suffix}"] = es_return_bps
            feature_columns[f"nq_return_bps_{suffix}"] = nq_return_bps
            feature_columns[f"nq_minus_es_return_bps_{suffix}"] = nq_return_bps - es_return_bps
            feature_columns[f"abs_nq_minus_abs_es_return_bps_{suffix}"] = (
                nq_return_bps.abs() - es_return_bps.abs()
            )
            if {"signed_volume", "volume", "nq_signed_volume", "nq_volume"}.issubset(group.columns):
                es_imbalance = _rolling_imbalance(group, "signed_volume", "volume", window, min_periods)
                nq_imbalance = _rolling_imbalance(group, "nq_signed_volume", "nq_volume", window, min_periods)
                feature_columns[f"es_signed_imbalance_{suffix}"] = es_imbalance
                feature_columns[f"nq_signed_imbalance_{suffix}"] = nq_imbalance
                feature_columns[f"nq_minus_es_signed_imbalance_{suffix}"] = nq_imbalance - es_imbalance
        frames.append(pd.concat([group, pd.DataFrame(feature_columns, index=group.index)], axis=1))
    return pd.concat(frames, ignore_index=True).drop(columns=["_session_date"])


def _rolling_return_bps(open_series: pd.Series, close_series: pd.Series, window: int, min_periods: int) -> pd.Series:
    start = pd.to_numeric(open_series, errors="coerce").shift(window - 1)
    close = pd.to_numeric(close_series, errors="coerce")
    enough = close.rolling(window, min_periods=min_periods).count() >= min_periods
    return ((close / start) - 1.0).where(enough) * 10000.0


def _rolling_imbalance(
    df: pd.DataFrame,
    signed_column: str,
    volume_column: str,
    window: int,
    min_periods: int,
) -> pd.Series:
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
