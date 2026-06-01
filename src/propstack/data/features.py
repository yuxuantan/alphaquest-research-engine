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
    high_idx = rth.groupby("session_date")["high"].idxmax()
    low_idx = rth.groupby("session_date")["low"].idxmin()
    daily["rth_high_timestamp"] = rth.loc[high_idx].set_index("session_date")["timestamp"]
    daily["rth_low_timestamp"] = rth.loc[low_idx].set_index("session_date")["timestamp"]
    prev = daily[["rth_high", "rth_low", "rth_high_timestamp", "rth_low_timestamp"]].shift(1).rename(
        columns={
            "rth_high": "prev_rth_high",
            "rth_low": "prev_rth_low",
            "rth_high_timestamp": "prev_rth_high_timestamp",
            "rth_low_timestamp": "prev_rth_low_timestamp",
        }
    )
    out = out.merge(prev, left_on="session_date", right_index=True, how="left")
    out = add_previous_rth_freshness(out)
    return out


def add_previous_rth_freshness(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prev_rth_high_fresh"] = False
    out["prev_rth_low_fresh"] = False
    ordered = out.sort_values("timestamp")

    high_keys = ordered[["prev_rth_high", "prev_rth_high_timestamp"]].dropna().drop_duplicates()
    for row in high_keys.itertuples(index=False):
        level = float(row.prev_rth_high)
        created_at = row.prev_rth_high_timestamp
        breached = (ordered["timestamp"] > created_at) & (ordered["high"] > level)
        breached_before_bar = breached.cumsum().shift(fill_value=0).astype(bool)
        uses_level = (ordered["prev_rth_high"] == level) & (ordered["prev_rth_high_timestamp"] == created_at)
        out.loc[ordered.index[uses_level], "prev_rth_high_fresh"] = ~breached_before_bar[uses_level].to_numpy()

    low_keys = ordered[["prev_rth_low", "prev_rth_low_timestamp"]].dropna().drop_duplicates()
    for row in low_keys.itertuples(index=False):
        level = float(row.prev_rth_low)
        created_at = row.prev_rth_low_timestamp
        breached = (ordered["timestamp"] > created_at) & (ordered["low"] < level)
        breached_before_bar = breached.cumsum().shift(fill_value=0).astype(bool)
        uses_level = (ordered["prev_rth_low"] == level) & (ordered["prev_rth_low_timestamp"] == created_at)
        out.loc[ordered.index[uses_level], "prev_rth_low_fresh"] = ~breached_before_bar[uses_level].to_numpy()

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
