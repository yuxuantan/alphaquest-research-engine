from __future__ import annotations

import pandas as pd


def apply_data_subset(data: pd.DataFrame, subset_config: dict | None) -> pd.DataFrame:
    if not subset_config:
        return data

    filtered = data
    if subset_config.get("start_date"):
        sessions = pd.to_datetime(filtered["session_date"]).dt.date
        start_date = pd.Timestamp(subset_config["start_date"]).date()
        filtered = filtered[sessions >= start_date]
    if subset_config.get("end_date"):
        sessions = pd.to_datetime(filtered["session_date"]).dt.date
        end_date = pd.Timestamp(subset_config["end_date"]).date()
        filtered = filtered[sessions <= end_date]
    if subset_config.get("start_timestamp"):
        filtered = filtered[filtered["timestamp"] >= _parse_timestamp_bound(data, subset_config["start_timestamp"])]
    if subset_config.get("end_timestamp"):
        filtered = filtered[filtered["timestamp"] <= _parse_timestamp_bound(data, subset_config["end_timestamp"])]

    return filtered.reset_index(drop=True)


def _parse_timestamp_bound(data: pd.DataFrame, value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    data_tz = data["timestamp"].dt.tz
    if data_tz is not None and ts.tzinfo is None:
        return ts.tz_localize(data_tz)
    if data_tz is not None:
        return ts.tz_convert(data_tz)
    if ts.tzinfo is not None:
        return ts.tz_localize(None)
    return ts
