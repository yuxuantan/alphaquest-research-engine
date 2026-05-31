from __future__ import annotations

import pandas as pd

from propstack.data.load import load_raw_csv
from propstack.data.sessions import assign_sessions


def validate_ohlc(df: pd.DataFrame) -> pd.Series:
    return (
        (df["high"] >= df["open"])
        & (df["high"] >= df["close"])
        & (df["low"] <= df["open"])
        & (df["low"] <= df["close"])
        & (df["high"] >= df["low"])
        & (df[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (df["volume"] >= 0)
    )


def detect_missing_bars(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (session_date, label), group in df.groupby(["session_date", "session_label"]):
        if label == "closed" or len(group) < 2:
            continue
        expected = pd.date_range(group["timestamp"].min(), group["timestamp"].max(), freq="1min")
        missing = expected.difference(pd.DatetimeIndex(group["timestamp"]))
        if len(missing):
            rows.append(
                {
                    "session_date": session_date,
                    "session_label": label,
                    "missing_count": len(missing),
                    "first_missing": missing[0],
                    "last_missing": missing[-1],
                }
            )
    return pd.DataFrame(rows)


def clean_data(config: dict) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    df = load_raw_csv(
        config["raw_csv"],
        symbol=config.get("symbol", "ES"),
        timezone=config.get("timezone", "America/Chicago"),
        csv_format=config.get("csv_format", "standard"),
        has_header=bool(config.get("has_header", True)),
        timestamp_format=config.get("timestamp_format"),
    )
    duplicate_count = int(df.duplicated(subset=["timestamp", "symbol"]).sum())
    df = df.drop_duplicates(subset=["timestamp", "symbol"], keep="last")
    valid_mask = validate_ohlc(df)
    invalid_count = int((~valid_mask).sum())
    df = df[valid_mask].copy()
    df = assign_sessions(df, config)
    df["timestamp_utc"] = df["timestamp"].dt.tz_convert("UTC")
    df = df.sort_values("timestamp").reset_index(drop=True)
    missing = detect_missing_bars(df)
    report = {
        "rows": int(len(df)),
        "duplicate_count": duplicate_count,
        "invalid_ohlc_count": invalid_count,
        "missing_session_segments": int(len(missing)),
        "first_timestamp": str(df["timestamp"].min()) if len(df) else None,
        "last_timestamp": str(df["timestamp"].max()) if len(df) else None,
    }
    return df, report, missing
