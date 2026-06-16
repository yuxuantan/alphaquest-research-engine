from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_WINDOWS = (5, 15, 30, 60)


def build_es_term_structure_lead_lag_frame(
    front: pd.DataFrame,
    deferred: pd.DataFrame,
    *,
    windows: Iterable[int] = DEFAULT_WINDOWS,
    min_period_fraction: float = 1.0,
) -> pd.DataFrame:
    """Align front ES bars with next-contract bars and add completed-window features.

    Front-contract bars remain the tradable market. Deferred-contract values are
    joined only at the same completed timestamp. Rolling features are grouped by
    RTH session date and use only the current completed minute plus earlier
    minutes, never later bars.
    """

    windows = _positive_ints(windows, "windows")
    if not (0 < min_period_fraction <= 1):
        raise ValueError("min_period_fraction must be in (0, 1].")

    front_ready = _normalise_source(front, "front")
    deferred_ready = _normalise_source(deferred, "deferred")
    aligned = _align_sources(front_ready, deferred_ready)
    aligned = _add_completed_term_structure_features(
        aligned,
        windows=windows,
        min_period_fraction=min_period_fraction,
    )
    return aligned.replace([np.inf, -np.inf], np.nan)


def load_source_table(path: str | Path, expected_symbol: str = "ES") -> pd.DataFrame:
    source_path = Path(path)
    if source_path.suffix.lower() == ".parquet":
        df = pd.read_parquet(source_path)
    else:
        df = pd.read_csv(source_path)
    if "symbol" not in df.columns:
        df = df.copy()
        df["symbol"] = expected_symbol
    return _normalise_source(df, expected_symbol)


def write_term_structure_cache(
    df: pd.DataFrame,
    *,
    output_parquet: str | Path | None = None,
    output_csv: str | Path | None = None,
) -> None:
    if output_parquet is not None:
        output_path = Path(output_parquet)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False, compression="zstd")
    if output_csv is not None:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out = df.copy()
        out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out.to_csv(output_path, index=False)


def _normalise_source(df: pd.DataFrame, expected_symbol: str) -> pd.DataFrame:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{expected_symbol} source missing required columns: {sorted(missing)}")

    out = df.copy()
    out["timestamp"] = _parse_timestamp(out["timestamp"])
    if "symbol" not in out.columns:
        out["symbol"] = expected_symbol
    if "contract_symbol" not in out.columns:
        out["contract_symbol"] = expected_symbol
    for column in out.columns:
        if column in {"timestamp", "symbol", "contract_symbol"} or str(column).endswith("_contract_symbol"):
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return (
        out.drop_duplicates(subset=["timestamp", "contract_symbol"], keep="last")
        .sort_values(["timestamp", "contract_symbol"])
        .reset_index(drop=True)
    )


def _parse_timestamp(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values)
    if timestamps.dt.tz is not None:
        timestamps = timestamps.dt.tz_convert("America/New_York").dt.tz_localize(None)
    return timestamps


def _align_sources(front: pd.DataFrame, deferred: pd.DataFrame) -> pd.DataFrame:
    deferred_columns = [
        column
        for column in deferred.columns
        if column not in {"timestamp", "symbol"}
    ]
    deferred_prefixed = deferred[["timestamp", *deferred_columns]].rename(
        columns={column: f"deferred_{column}" for column in deferred_columns}
    )
    out = front.merge(deferred_prefixed, on="timestamp", how="inner", validate="one_to_one")
    out["symbol"] = "ES"
    return out.sort_values("timestamp").reset_index(drop=True)


def _add_completed_term_structure_features(
    df: pd.DataFrame,
    *,
    windows: list[int],
    min_period_fraction: float,
) -> pd.DataFrame:
    frames = []
    work = df.copy()
    work["_session_date"] = work["timestamp"].dt.date
    work["calendar_spread_points"] = work["close"] - work["deferred_close"]
    work["calendar_spread_bps"] = (work["calendar_spread_points"] / work["close"]) * 10000.0

    for _, group in work.groupby("_session_date", sort=True, dropna=False):
        group = group.sort_values("timestamp").copy()
        feature_columns: dict[str, pd.Series] = {}
        for window in windows:
            min_periods = max(1, int(window * min_period_fraction))
            suffix = str(window)
            front_return_bps = _rolling_return_bps(group["open"], group["close"], window, min_periods)
            deferred_return_bps = _rolling_return_bps(
                group["deferred_open"],
                group["deferred_close"],
                window,
                min_periods,
            )
            spread_change_points = group["calendar_spread_points"] - group["calendar_spread_points"].shift(window - 1)
            enough = group["calendar_spread_points"].rolling(window, min_periods=min_periods).count() >= min_periods
            spread_change_points = spread_change_points.where(enough)
            feature_columns[f"front_return_bps_{suffix}"] = front_return_bps
            feature_columns[f"deferred_return_bps_{suffix}"] = deferred_return_bps
            feature_columns[f"front_minus_deferred_return_bps_{suffix}"] = front_return_bps - deferred_return_bps
            feature_columns[f"deferred_minus_front_return_bps_{suffix}"] = deferred_return_bps - front_return_bps
            feature_columns[f"calendar_spread_change_points_{suffix}"] = spread_change_points
        frames.append(pd.concat([group, pd.DataFrame(feature_columns, index=group.index)], axis=1))
    return pd.concat(frames, ignore_index=True).drop(columns=["_session_date"])


def _rolling_return_bps(open_series: pd.Series, close_series: pd.Series, window: int, min_periods: int) -> pd.Series:
    start = pd.to_numeric(open_series, errors="coerce").shift(window - 1)
    close = pd.to_numeric(close_series, errors="coerce")
    enough = close.rolling(window, min_periods=min_periods).count() >= min_periods
    return ((close / start) - 1.0).where(enough) * 10000.0


def _positive_ints(values: Iterable[int], name: str) -> list[int]:
    out = [int(value) for value in values]
    if not out or any(value <= 0 for value in out):
        raise ValueError(f"{name} must contain positive integers.")
    return out
