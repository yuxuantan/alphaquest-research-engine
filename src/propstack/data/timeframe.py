from __future__ import annotations

import re
from datetime import time

import pandas as pd

from propstack.utils.time import parse_time


_TIMEFRAME_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")


def parse_timeframe_minutes(value) -> int:
    if value is None:
        raise ValueError("Campaign variant must define a non-empty timeframe.")
    if isinstance(value, (int, float)):
        minutes = float(value)
    else:
        match = _TIMEFRAME_RE.match(str(value))
        if not match:
            raise ValueError(f"Unsupported timeframe: {value!r}. Expected values like 1m, 5m, or 15m.")
        amount = float(match.group(1))
        unit = match.group(2).lower() or "m"
        if unit in {"m", "min", "mins", "minute", "minutes"}:
            minutes = amount
        elif unit in {"h", "hr", "hrs", "hour", "hours"}:
            minutes = amount * 60.0
        else:
            raise ValueError(f"Unsupported timeframe unit: {unit!r}. Expected minutes or hours.")

    if minutes <= 0 or minutes != int(minutes):
        raise ValueError("timeframe must resolve to a positive whole number of minutes.")
    return int(minutes)


def canonical_timeframe(value) -> str:
    return f"{parse_timeframe_minutes(value)}m"


def aggregate_timeframe(df: pd.DataFrame, config: dict, timeframe) -> pd.DataFrame:
    minutes = parse_timeframe_minutes(timeframe)
    if minutes == 1 or df.empty:
        return df.sort_values("timestamp").reset_index(drop=True).copy()

    required = {"timestamp", "open", "high", "low", "close", "volume", "session_date", "session_label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Cannot aggregate timeframe; data is missing required columns: {sorted(missing)}")

    out = df.sort_values("timestamp").reset_index(drop=True).copy()
    out["_timeframe_timestamp"] = _timeframe_buckets(out, config, minutes)

    group_cols = ["_timeframe_timestamp", "symbol", "session_date", "session_label"]
    group_cols = [col for col in group_cols if col in out.columns]
    for optional in ["contract_symbol", "contract_instrument_id"]:
        if optional in out.columns:
            group_cols.append(optional)

    agg = {
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
        "volume": ("volume", "sum"),
        "source_bar_count": ("timestamp", "count"),
    }
    if "is_rth" in out.columns:
        agg["is_rth"] = ("is_rth", "any")
    if "is_eth" in out.columns:
        agg["is_eth"] = ("is_eth", "any")
    if "roll_boundary" in out.columns:
        agg["roll_boundary"] = ("roll_boundary", "any")

    aggregated = out.groupby(group_cols, sort=True, dropna=False).agg(**agg).reset_index()
    aggregated = aggregated.rename(columns={"_timeframe_timestamp": "timestamp"})
    aggregated["timeframe_minutes"] = minutes
    if "timestamp_utc" in out.columns:
        aggregated["timestamp_utc"] = aggregated["timestamp"].dt.tz_convert("UTC")
    if "is_rth" not in aggregated.columns:
        aggregated["is_rth"] = aggregated["session_label"] == "RTH"
    if "is_eth" not in aggregated.columns:
        aggregated["is_eth"] = aggregated["session_label"] == "ETH"

    ordered = [
        "timestamp",
        "timestamp_utc",
        "symbol",
        "contract_symbol",
        "contract_instrument_id",
        "session_date",
        "session_label",
        "is_rth",
        "is_eth",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "timeframe_minutes",
        "source_bar_count",
        "roll_boundary",
    ]
    cols = [col for col in ordered if col in aggregated.columns]
    cols.extend([col for col in aggregated.columns if col not in cols])
    return aggregated[cols].sort_values("timestamp").reset_index(drop=True)


def _timeframe_buckets(df: pd.DataFrame, config: dict, minutes: int) -> pd.Series:
    buckets = pd.Series(pd.NaT, index=df.index, dtype=df["timestamp"].dtype)
    group_cols = ["session_date", "session_label"]
    for optional in ["symbol", "contract_symbol", "contract_instrument_id"]:
        if optional in df.columns:
            group_cols.append(optional)

    for _, group in df.groupby(group_cols, sort=False, dropna=False):
        anchor = _session_anchor(group.iloc[0], config)
        elapsed = group["timestamp"] - anchor
        bucket_numbers = (elapsed.dt.total_seconds() // (minutes * 60)).astype(int)
        buckets.loc[group.index] = anchor + pd.to_timedelta(bucket_numbers * minutes, unit="m")
    return buckets


def _session_anchor(row: pd.Series, config: dict) -> pd.Timestamp:
    label = row.get("session_label")
    timestamp = pd.Timestamp(row["timestamp"])
    if label == "RTH":
        return _local_session_timestamp(row["session_date"], parse_time(config.get("rth_start", "09:30:00")), timestamp)
    if label == "ETH":
        session_date = pd.Timestamp(row["session_date"]) - pd.Timedelta(days=1)
        return _local_session_timestamp(session_date.date(), parse_time(config.get("eth_start", "17:00:00")), timestamp)
    return timestamp.floor("min")


def _local_session_timestamp(session_date, session_time: time, reference: pd.Timestamp) -> pd.Timestamp:
    naive = pd.Timestamp.combine(pd.Timestamp(session_date).date(), session_time)
    if reference.tzinfo is None:
        return naive
    return naive.tz_localize(reference.tz)
