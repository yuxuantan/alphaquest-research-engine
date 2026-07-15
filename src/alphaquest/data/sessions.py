from __future__ import annotations

from datetime import timedelta
import pandas as pd

from alphaquest.utils.time import parse_time


def assign_sessions(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    ts = out["timestamp"]
    t = ts.dt.time
    rth_start = parse_time(config.get("rth_start", "08:30:00"))
    rth_end = parse_time(config.get("rth_end", "15:00:00"))
    eth_start = parse_time(config.get("eth_start", "17:00:00"))
    eth_end = parse_time(config.get("eth_end", "08:29:00"))

    is_eth = (t >= eth_start) | (t <= eth_end)
    is_rth = (t >= rth_start) & (t <= rth_end) & ~is_eth
    out["is_rth"] = is_rth
    out["is_eth"] = is_eth
    out["session_label"] = "closed"
    out.loc[is_eth, "session_label"] = "ETH"
    out.loc[is_rth, "session_label"] = "RTH"

    session_dates = ts.dt.date
    evening_eth = t >= eth_start
    session_dates = pd.Series(session_dates, index=out.index)
    session_dates.loc[evening_eth] = session_dates.loc[evening_eth].apply(
        lambda d: d + timedelta(days=1)
    )
    out["session_date"] = pd.to_datetime(session_dates).dt.date
    return out


def filter_trading_sessions(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["session_label"].isin(["RTH", "ETH"])].copy()
