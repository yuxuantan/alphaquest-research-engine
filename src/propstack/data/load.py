from __future__ import annotations

import pandas as pd


COLUMN_ALIASES = {
    "date": "timestamp",
    "datetime": "timestamp",
    "time": "timestamp",
    "o": "open",
    "h": "high",
    "l": "low",
    "c": "close",
    "v": "volume",
    "vol": "volume",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        renamed[col] = COLUMN_ALIASES.get(key, key)
    return df.rename(columns=renamed)


def load_raw_csv(
    path: str,
    symbol: str = "ES",
    timezone: str = "America/Chicago",
    csv_format: str = "standard",
    has_header: bool = True,
    timestamp_format: str | None = None,
) -> pd.DataFrame:
    if csv_format == "yyyymmdd_hhmmss_ohlcv":
        df = pd.read_csv(
            path,
            header=None,
            names=["timestamp", "open", "high", "low", "close", "volume"],
        )
        timestamp_format = timestamp_format or "%Y%m%d %H%M%S"
    else:
        header = 0 if has_header else None
        df = pd.read_csv(path, header=header)
        if not has_header:
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"][: len(df.columns)]
        df = normalize_columns(df)

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format=timestamp_format)
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(timezone)
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert(timezone)
    if "symbol" not in df.columns:
        df["symbol"] = symbol
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)
