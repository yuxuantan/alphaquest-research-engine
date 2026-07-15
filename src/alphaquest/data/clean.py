from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from alphaquest.data.load import infer_data_source, load_raw_data
from alphaquest.data.sessions import assign_sessions


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
    freq = _expected_bar_frequency(df)
    for (session_date, label), group in df.groupby(["session_date", "session_label"]):
        if label == "closed" or len(group) < 2:
            continue
        expected = pd.date_range(group["timestamp"].min(), group["timestamp"].max(), freq=freq)
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


def _expected_bar_frequency(df: pd.DataFrame) -> str:
    if "timeframe_minutes" in df.columns:
        values = pd.to_numeric(df["timeframe_minutes"], errors="coerce").dropna().unique()
        if len(values) == 1 and float(values[0]).is_integer() and values[0] > 0:
            return f"{int(values[0])}min"
    return "1min"


def apply_continuous_contract(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rule = config.get("continuous_contract")
    if rule is None and infer_data_source(config) == "databento_dbn":
        rule = "dominant_session_volume"
    if not rule or str(rule).lower() in {"none", "false"}:
        return df
    rule = str(rule).lower()
    if rule not in {"dominant_session_volume", "session_volume", "explicit_roll_calendar"}:
        raise ValueError(f"Unsupported continuous_contract rule: {rule}")
    if df.empty:
        return df

    out = df.copy()
    if "contract_symbol" not in out.columns:
        out["contract_symbol"] = out["symbol"].astype(str)

    if rule == "explicit_roll_calendar":
        out = _assign_explicit_roll_contract(out, config)
    else:
        volumes = (
            out.groupby(["session_date", "contract_symbol"], dropna=False)["volume"]
            .sum()
            .reset_index()
        )
        active_idx = volumes.groupby("session_date")["volume"].idxmax()
        active = volumes.loc[active_idx, ["session_date", "contract_symbol"]].rename(
            columns={"contract_symbol": "active_contract_symbol"}
        )
        out = out.merge(active, on="session_date", how="left")

    out = out[out["contract_symbol"] == out["active_contract_symbol"]].copy()
    out = out.drop(columns=["active_contract_symbol"])
    out["symbol"] = config.get("symbol", out["symbol"].iloc[0] if len(out) else "UNKNOWN")
    return out.sort_values("timestamp").reset_index(drop=True)


def _assign_explicit_roll_contract(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    path = config.get("roll_calendar")
    if not path:
        raise ValueError("continuous_contract: explicit_roll_calendar requires data.roll_calendar")

    calendar = load_roll_calendar(path, config.get("timezone", "America/Chicago"))
    if calendar.empty:
        raise ValueError(f"Roll calendar is empty: {path}")

    ordered = df.sort_values("timestamp").reset_index(drop=True)
    mapped = pd.merge_asof(
        ordered,
        calendar[["start_timestamp", "contract_symbol"]].rename(
            columns={"contract_symbol": "active_contract_symbol"}
        ),
        left_on="timestamp",
        right_on="start_timestamp",
        direction="backward",
    )
    missing = mapped["active_contract_symbol"].isna()
    if missing.any():
        first_missing = mapped.loc[missing, "timestamp"].min()
        first_calendar = calendar["start_timestamp"].min()
        raise ValueError(
            "Roll calendar does not cover requested Databento range. "
            f"First missing timestamp: {first_missing}. "
            f"First calendar timestamp: {first_calendar}. "
            f"Extend {path} or narrow the data_subset."
        )
    return mapped.drop(columns=["start_timestamp"])


def load_roll_calendar(path: str | Path, timezone: str) -> pd.DataFrame:
    calendar = pd.read_csv(path)
    required = {"start_timestamp", "contract_symbol"}
    missing = required - set(calendar.columns)
    if missing:
        raise ValueError(f"Roll calendar missing required columns: {sorted(missing)}")

    calendar = calendar.copy()
    calendar["start_timestamp"] = [
        _parse_roll_timestamp(value, timezone) for value in calendar["start_timestamp"]
    ]
    calendar["contract_symbol"] = calendar["contract_symbol"].astype(str)
    return calendar.sort_values("start_timestamp").reset_index(drop=True)


def _parse_roll_timestamp(value: object, timezone: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(timezone)
    return timestamp.tz_convert(timezone)


def apply_roll_boundary_policy(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    policy = config.get("roll_boundary_policy") or {}
    if df.empty or "contract_symbol" not in df.columns:
        return df, {"roll_boundary_sessions_skipped": 0}

    out = df.sort_values("timestamp").reset_index(drop=True)
    out["roll_boundary"] = out["contract_symbol"] != out["contract_symbol"].shift(1)
    out.loc[out.index[0], "roll_boundary"] = False

    skip_sessions = int(policy.get("skip_sessions_around_roll", 0) or 0)
    if skip_sessions <= 0:
        return out, {"roll_boundary_sessions_skipped": 0}

    roll_dates = set(out.loc[out["roll_boundary"], "session_date"])
    if not roll_dates:
        return out, {"roll_boundary_sessions_skipped": 0}

    sessions = pd.Series(sorted(out["session_date"].dropna().unique()))
    session_index = {session: idx for idx, session in enumerate(sessions)}
    drop_dates = set()
    for roll_date in roll_dates:
        idx = session_index.get(roll_date)
        if idx is None:
            continue
        lo = max(0, idx - skip_sessions)
        hi = min(len(sessions) - 1, idx + skip_sessions)
        drop_dates.update(sessions.iloc[lo : hi + 1].tolist())

    filtered = out[~out["session_date"].isin(drop_dates)].copy()
    return filtered.reset_index(drop=True), {"roll_boundary_sessions_skipped": len(drop_dates)}


def clean_data(
    config: dict,
    date_bounds: dict | None = None,
    status_callback: Callable[[str], None] | None = None,
    show_progress: bool = False,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    _emit(status_callback, "Loading raw market data...")
    df = load_raw_data(
        config,
        date_bounds=date_bounds,
        status_callback=status_callback,
        show_progress=show_progress,
    )
    _emit(status_callback, f"Loaded {len(df):,} raw bars. Removing duplicate bars...")
    duplicate_count = int(df.duplicated(subset=["timestamp", "symbol"]).sum())
    df = df.drop_duplicates(subset=["timestamp", "symbol"], keep="last")
    _emit(status_callback, "Validating OHLC rows...")
    valid_mask = validate_ohlc(df)
    invalid_count = int((~valid_mask).sum())
    df = df[valid_mask].copy()
    _emit(status_callback, f"OHLC validation kept {len(df):,} bars.")
    _emit(status_callback, "Assigning market sessions...")
    df = assign_sessions(df, config)
    _emit(status_callback, "Applying continuous-contract selection...")
    df = apply_continuous_contract(df, config)
    _emit(status_callback, f"Continuous-contract selection kept {len(df):,} bars.")
    _emit(status_callback, "Applying roll-boundary policy...")
    df, roll_policy_report = apply_roll_boundary_policy(df, config)
    _emit(status_callback, f"Roll-boundary policy kept {len(df):,} bars.")
    df["timestamp_utc"] = df["timestamp"].dt.tz_convert("UTC")
    df = df.sort_values("timestamp").reset_index(drop=True)
    _emit(status_callback, "Detecting missing session bars...")
    missing = detect_missing_bars(df)
    report = {
        "rows": int(len(df)),
        "duplicate_count": duplicate_count,
        "invalid_ohlc_count": invalid_count,
        "missing_session_segments": int(len(missing)),
        "first_timestamp": str(df["timestamp"].min()) if len(df) else None,
        "last_timestamp": str(df["timestamp"].max()) if len(df) else None,
        **roll_policy_report,
    }
    _emit(status_callback, f"Cleaned data ready: {len(df):,} bars, {len(missing):,} missing-session segments.")
    return df, report, missing


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
