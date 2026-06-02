from __future__ import annotations

from pathlib import Path

import pandas as pd


def market_timezone(config: dict | None) -> str | None:
    if not config:
        return None
    data = config.get("data") if "data" in config else config
    if not isinstance(data, dict):
        return None
    return data.get("exchange_timezone") or data.get("timezone")


def normalize_report_timestamps(frame: pd.DataFrame, timezone: str | None) -> pd.DataFrame:
    if frame.empty or not timezone:
        return frame

    out = frame.copy()
    for column in out.columns:
        if _should_convert_column(out[column], column):
            converted = _convert_series(out[column], timezone)
            if converted is not None:
                out[column] = converted
    return out


def write_report_csv(frame: pd.DataFrame, path: str | Path, timezone: str | None, **kwargs) -> None:
    normalize_report_timestamps(frame, timezone).to_csv(path, **kwargs)


def _should_convert_column(series: pd.Series, column: object) -> bool:
    name = str(column).lower()
    if name.endswith("_utc"):
        return False
    if "timestamp" in name:
        return True
    return isinstance(series.dtype, pd.DatetimeTZDtype)


def _convert_series(series: pd.Series, timezone: str) -> pd.Series | None:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    non_null = series.notna()
    if non_null.any() and not parsed[non_null].notna().any():
        return None
    converted = parsed.dt.tz_convert(timezone)
    return converted.map(lambda value: "" if pd.isna(value) else value.isoformat(sep=" "))
