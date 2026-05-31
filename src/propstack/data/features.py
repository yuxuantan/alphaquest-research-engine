from __future__ import annotations

import pandas as pd


def add_previous_rth_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rth = out[out["is_rth"]]
    daily = rth.groupby("session_date").agg(
        rth_high=("high", "max"),
        rth_low=("low", "min"),
        rth_open=("open", "first"),
        rth_close=("close", "last"),
        total_rth_volume=("volume", "sum"),
        first_rth_timestamp=("timestamp", "first"),
        last_rth_timestamp=("timestamp", "last"),
    )
    prev = daily[["rth_high", "rth_low"]].shift(1).rename(
        columns={"rth_high": "prev_rth_high", "rth_low": "prev_rth_low"}
    )
    out = out.merge(prev, left_on="session_date", right_index=True, how="left")
    return out


def add_overnight_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    eth = out[out["is_eth"]]
    overnight = eth.groupby("session_date").agg(
        overnight_high=("high", "max"),
        overnight_low=("low", "min"),
    )
    return out.merge(overnight, left_on="session_date", right_index=True, how="left")


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    pv = typical * out["volume"]
    out["_pv"] = pv
    out["_cum_pv"] = out.groupby(["session_date", "session_label"])["_pv"].cumsum()
    out["_cum_vol"] = out.groupby(["session_date", "session_label"])["volume"].cumsum()
    out["vwap"] = out["_cum_pv"] / out["_cum_vol"].replace(0, pd.NA)
    return out.drop(columns=["_pv", "_cum_pv", "_cum_vol"])


def add_rolling_volume(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["rolling_volume"] = (
        out.groupby(["symbol", "session_label"])["volume"]
        .transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
        .fillna(0)
    )
    out["volume_ratio"] = out["volume"] / out["rolling_volume"].replace(0, pd.NA)
    out["volume_ratio"] = pd.to_numeric(out["volume_ratio"], errors="coerce").fillna(0.0)
    return out


def build_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = add_previous_rth_levels(df)
    out = add_overnight_levels(out)
    out = add_vwap(out)
    out = add_rolling_volume(out, int(config.get("rolling_volume_window", 20)))
    return out
