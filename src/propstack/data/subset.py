from __future__ import annotations

import pandas as pd

SUBSET_KEYS = ("start_date", "end_date", "start_timestamp", "end_timestamp")


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
    if subset_config.get("session_labels"):
        if "session_label" not in filtered.columns:
            raise ValueError("data_subset.session_labels requires a session_label column.")
        allowed = {str(value) for value in subset_config["session_labels"]}
        filtered = filtered[filtered["session_label"].astype(str).isin(allowed)]
    if subset_config.get("rth_only"):
        if "is_rth" not in filtered.columns:
            raise ValueError("data_subset.rth_only requires an is_rth column.")
        filtered = filtered[filtered["is_rth"].fillna(False).astype(bool)]

    return filtered.reset_index(drop=True)


def subset_from_config(
    config: dict,
    section: str | None = None,
    fallback_sections: tuple[str, ...] = (),
) -> dict | None:
    sections = []
    if section:
        sections.append(section)
    sections.extend(fallback_sections)
    for key in sections:
        subset = (config.get(key) or {}).get("data_subset")
        if subset:
            return dict(subset)

    data_config = config.get("data") or {}
    return subset_from_data_config(data_config)


def subset_from_data_config(data_config: dict) -> dict | None:
    if data_config.get("data_subset"):
        return dict(data_config["data_subset"])
    subset = {key: data_config[key] for key in SUBSET_KEYS if data_config.get(key)}
    return subset or None


def load_bounds_with_warmup(
    subset_config: dict | None,
    data_config: dict,
) -> dict | None:
    if not subset_config:
        return None

    bounds = dict(subset_config)
    warmup_days = int(data_config.get("warmup_days", 7))
    if warmup_days <= 0:
        return bounds

    if bounds.get("start_timestamp"):
        start = pd.Timestamp(bounds["start_timestamp"]) - pd.Timedelta(days=warmup_days)
        bounds["start_timestamp"] = start.isoformat()
    elif bounds.get("start_date"):
        start = pd.Timestamp(bounds["start_date"]) - pd.Timedelta(days=warmup_days)
        bounds["start_date"] = start.date().isoformat()
    return bounds


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
