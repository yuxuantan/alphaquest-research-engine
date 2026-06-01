from __future__ import annotations

import pandas as pd

from propstack.data.load import infer_data_source, load_raw_data
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


def apply_continuous_contract(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rule = config.get("continuous_contract")
    if rule is None and infer_data_source(config) == "databento_dbn":
        rule = "dominant_session_volume"
    if not rule or str(rule).lower() in {"none", "false"}:
        return df
    if str(rule).lower() not in {"dominant_session_volume", "session_volume"}:
        raise ValueError(f"Unsupported continuous_contract rule: {rule}")
    if df.empty:
        return df

    out = df.copy()
    if "contract_symbol" not in out.columns:
        out["contract_symbol"] = out["symbol"].astype(str)

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


def clean_data(
    config: dict,
    date_bounds: dict | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    df = load_raw_data(config, date_bounds=date_bounds)
    duplicate_count = int(df.duplicated(subset=["timestamp", "symbol"]).sum())
    df = df.drop_duplicates(subset=["timestamp", "symbol"], keep="last")
    valid_mask = validate_ohlc(df)
    invalid_count = int((~valid_mask).sum())
    df = df[valid_mask].copy()
    df = assign_sessions(df, config)
    df = apply_continuous_contract(df, config)
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
