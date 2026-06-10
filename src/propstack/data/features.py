from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from propstack.utils.time import parse_time


def add_previous_rth_levels(df: pd.DataFrame, reset_on_contract_change: bool = False) -> pd.DataFrame:
    out = df.copy()
    rth = out[out["is_rth"]]
    agg = {
        "rth_high": ("high", "max"),
        "rth_low": ("low", "min"),
        "rth_open": ("open", "first"),
        "rth_close": ("close", "last"),
        "total_rth_volume": ("volume", "sum"),
        "first_rth_timestamp": ("timestamp", "first"),
        "last_rth_timestamp": ("timestamp", "last"),
    }
    if "contract_symbol" in rth.columns:
        agg["rth_contract_symbol"] = ("contract_symbol", "first")
    daily = rth.groupby("session_date").agg(**agg)
    high_idx = rth.groupby("session_date")["high"].idxmax()
    low_idx = rth.groupby("session_date")["low"].idxmin()
    daily["rth_high_timestamp"] = rth.loc[high_idx].set_index("session_date")["timestamp"]
    daily["rth_low_timestamp"] = rth.loc[low_idx].set_index("session_date")["timestamp"]
    prev_cols = ["rth_high", "rth_low", "rth_open", "rth_close", "rth_high_timestamp", "rth_low_timestamp"]
    if "rth_contract_symbol" in daily.columns:
        prev_cols.append("rth_contract_symbol")
    prev = daily[prev_cols].shift(1).rename(
        columns={
            "rth_high": "prev_rth_high",
            "rth_low": "prev_rth_low",
            "rth_open": "prev_rth_open",
            "rth_close": "prev_rth_close",
            "rth_high_timestamp": "prev_rth_high_timestamp",
            "rth_low_timestamp": "prev_rth_low_timestamp",
            "rth_contract_symbol": "prev_rth_contract_symbol",
        }
    )
    out = out.merge(prev, left_on="session_date", right_index=True, how="left")
    if reset_on_contract_change and {"contract_symbol", "prev_rth_contract_symbol"}.issubset(out.columns):
        contract_changed = (
            out["prev_rth_contract_symbol"].notna()
            & (out["contract_symbol"].astype(str) != out["prev_rth_contract_symbol"].astype(str))
        )
        out.loc[
            contract_changed,
            [
                "prev_rth_high",
                "prev_rth_low",
                "prev_rth_open",
                "prev_rth_close",
                "prev_rth_high_timestamp",
                "prev_rth_low_timestamp",
            ],
        ] = pd.NA
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


def add_vpin_toxicity_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    feature_cfg = config.get("vpin_toxicity_features") or {}
    entry_time = parse_time(feature_cfg.get("entry_time", "13:30:00"))
    bucket_fraction = float(feature_cfg.get("bucket_fraction", 0.01))
    bucket_lookback = int(feature_cfg.get("bucket_lookback", 5))
    bucket_min_periods = int(feature_cfg.get("bucket_min_periods", max(3, bucket_lookback // 2)))
    vpin_rank_window = int(feature_cfg.get("vpin_rank_window", 21))
    vpin_rank_min_periods = int(feature_cfg.get("vpin_rank_min_periods", max(10, vpin_rank_window // 2)))
    drawdown_rank_window = int(feature_cfg.get("drawdown_rank_window", 63))
    drawdown_rank_min_periods = int(
        feature_cfg.get("drawdown_rank_min_periods", max(10, drawdown_rank_window // 2))
    )

    if bucket_fraction <= 0:
        raise ValueError("data.vpin_toxicity_features.bucket_fraction must be greater than 0.")
    if bucket_lookback <= 0 or vpin_rank_window <= 0 or drawdown_rank_window <= 0:
        raise ValueError("data.vpin_toxicity_features windows must be greater than 0.")

    vpin_col = _vpin_proxy_column(bucket_fraction, bucket_lookback)
    session_ret_col = "vpin_session_ret"
    drawdown_col = "vpin_session_drawdown_pct"
    vpin_rank_col = f"vpin_prior_rank{vpin_rank_window}_at_{_time_suffix(entry_time)}"
    drawdown_rank_col = f"vpin_prior_drawdown_rank{drawdown_rank_window}_at_{_time_suffix(entry_time)}"
    for col in [vpin_col, session_ret_col, drawdown_col, vpin_rank_col, drawdown_rank_col]:
        out[col] = np.nan

    if out.empty or "volume" not in out.columns:
        return out
    if "is_rth" in out.columns:
        rth_mask = out["is_rth"].fillna(False).astype(bool)
    else:
        rth_mask = pd.Series(True, index=out.index)
    if not rth_mask.any():
        return out

    rth = out.loc[rth_mask].sort_values("timestamp").copy()
    by_day = rth.groupby("session_date", sort=True)
    volume = pd.to_numeric(rth["volume"], errors="coerce").astype(float)
    close = pd.to_numeric(rth["close"], errors="coerce").astype(float)
    returns = close.groupby(rth["session_date"]).pct_change().fillna(0.0)
    signed_direction = np.sign(returns).replace(0.0, np.nan)
    signed_direction = signed_direction.groupby(rth["session_date"]).ffill().fillna(0.0)
    signed_volume = signed_direction * volume

    daily_volume = volume.groupby(rth["session_date"]).transform("sum").astype(float)
    cumulative_volume = volume.groupby(rth["session_date"]).cumsum().astype(float)
    denominator = (daily_volume * bucket_fraction).replace(0.0, np.nan)
    bucket_id = np.floor(cumulative_volume / denominator).astype("Int64")
    bucket_frame = pd.DataFrame(
        {
            "session_date": rth["session_date"].to_numpy(),
            "bucket_id": bucket_id.to_numpy(),
            "signed_volume": signed_volume.to_numpy(dtype=float),
            "volume": volume.to_numpy(dtype=float),
        },
        index=rth.index,
    )
    bucket = (
        bucket_frame.dropna(subset=["bucket_id"])
        .groupby(["session_date", "bucket_id"], sort=True)
        .agg(signed_volume=("signed_volume", "sum"), volume=("volume", "sum"))
    )
    if not bucket.empty:
        bucket["toxicity"] = bucket["signed_volume"].abs() / bucket["volume"].replace(0.0, np.nan)
        bucket = bucket.reset_index()
        bucket[vpin_col] = (
            bucket.groupby("session_date")["toxicity"]
            .rolling(bucket_lookback, min_periods=bucket_min_periods)
            .mean()
            .reset_index(level=0, drop=True)
        )
        mapped = pd.merge(
            pd.DataFrame(
                {
                    "session_date": rth["session_date"].to_numpy(),
                    "bucket_id": bucket_id.to_numpy(),
                },
                index=rth.index,
            ),
            bucket[["session_date", "bucket_id", vpin_col]],
            on=["session_date", "bucket_id"],
            how="left",
        )[vpin_col].to_numpy(dtype=float)
        out.loc[rth.index, vpin_col] = mapped

    rth[session_ret_col] = close.groupby(rth["session_date"]).transform(lambda s: s / s.iloc[0] - 1.0)
    session_high = pd.to_numeric(rth["high"], errors="coerce").astype(float).groupby(rth["session_date"]).cummax()
    session_open = pd.to_numeric(rth["open"], errors="coerce").astype(float).groupby(rth["session_date"]).transform("first")
    rth[drawdown_col] = (session_high - close) / session_open.replace(0.0, np.nan)
    out.loc[rth.index, session_ret_col] = rth[session_ret_col].to_numpy(dtype=float)
    out.loc[rth.index, drawdown_col] = rth[drawdown_col].to_numpy(dtype=float)

    before_entry = rth[pd.to_datetime(rth["timestamp"]).dt.time < entry_time].copy()
    if before_entry.empty:
        return out
    last_before_entry = before_entry.groupby("session_date", sort=True).tail(1).copy()
    session_index = pd.to_datetime(last_before_entry["session_date"]).dt.normalize()
    vpin_values = pd.Series(
        out.loc[last_before_entry.index, vpin_col].to_numpy(dtype=float),
        index=session_index,
    ).sort_index()
    drawdown_values = pd.Series(
        last_before_entry[drawdown_col].to_numpy(dtype=float),
        index=session_index,
    ).sort_index()
    vpin_rank = _shifted_rolling_rank(vpin_values, vpin_rank_window, vpin_rank_min_periods)
    drawdown_rank = _shifted_rolling_rank(drawdown_values, drawdown_rank_window, drawdown_rank_min_periods)
    out_sessions = pd.to_datetime(out["session_date"]).dt.normalize()
    out[vpin_rank_col] = out_sessions.map(vpin_rank).astype(float)
    out[drawdown_rank_col] = out_sessions.map(drawdown_rank).astype(float)
    return out


def add_trade_orderflow_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    feature_cfg = config.get("trade_orderflow_features") or {}
    windows = [int(value) for value in feature_cfg.get("windows", [5, 15, 30, 60])]
    tick_size = float(feature_cfg.get("tick_size", config.get("tick_size", 0.25)))
    large_trade_sizes = [int(value) for value in feature_cfg.get("large_trade_sizes", [10, 20])]
    min_period_fraction = float(feature_cfg.get("min_period_fraction", 0.5))

    if tick_size <= 0:
        raise ValueError("data.trade_orderflow_features.tick_size must be greater than 0.")
    if not windows or any(window <= 0 for window in windows):
        raise ValueError("data.trade_orderflow_features.windows must contain positive integers.")
    if not (0 < min_period_fraction <= 1):
        raise ValueError("data.trade_orderflow_features.min_period_fraction must be in (0, 1].")
    required = {"signed_volume", "volume"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(
            "trade_orderflow_features requires minute bars with trade-side columns. "
            f"Missing: {sorted(missing)}."
        )

    group_cols = ["session_date"]
    for optional in ["symbol", "contract_symbol", "contract_instrument_id"]:
        if optional in out.columns:
            group_cols.append(optional)

    frames = []
    for _, group in out.sort_values("timestamp").groupby(group_cols, sort=False, dropna=False):
        group = group.copy()
        for window in windows:
            min_periods = max(1, int(window * min_period_fraction))
            close = pd.to_numeric(group["close"], errors="coerce")
            source_open = pd.to_numeric(group["open"], errors="coerce").shift(window - 1)
            ret_points = close - source_open
            suffix = str(window)
            group[f"trade_orderflow_return_points_{suffix}"] = ret_points
            group[f"trade_orderflow_return_ticks_{suffix}"] = ret_points / tick_size
            volume = pd.to_numeric(group["volume"], errors="coerce").rolling(
                window, min_periods=min_periods
            ).sum()
            signed = pd.to_numeric(group["signed_volume"], errors="coerce").rolling(
                window, min_periods=min_periods
            ).sum()
            group[f"trade_orderflow_volume_{suffix}"] = volume
            group[f"trade_orderflow_signed_volume_{suffix}"] = signed
            group[f"trade_orderflow_imbalance_{suffix}"] = signed / volume.replace(0.0, np.nan)
            for size in large_trade_sizes:
                large_signed_col = f"large{size}_signed_volume"
                large_volume_col = f"large{size}_volume"
                if {large_signed_col, large_volume_col}.issubset(group.columns):
                    large_signed = pd.to_numeric(group[large_signed_col], errors="coerce").rolling(
                        window, min_periods=min_periods
                    ).sum()
                    large_volume = pd.to_numeric(group[large_volume_col], errors="coerce").rolling(
                        window, min_periods=min_periods
                    ).sum()
                    group[f"trade_orderflow_large{size}_signed_volume_{suffix}"] = large_signed
                    group[f"trade_orderflow_large{size}_volume_{suffix}"] = large_volume
                    group[f"trade_orderflow_large{size}_imbalance_{suffix}"] = (
                        large_signed / large_volume.replace(0.0, np.nan)
                    )
        frames.append(group)

    if not frames:
        return out
    out = pd.concat(frames).sort_index()
    return out.replace([np.inf, -np.inf], np.nan)


def build_features(
    df: pd.DataFrame,
    config: dict,
    status_callback: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    feature_set = str(config.get("feature_set", "full")).lower()
    _emit(status_callback, f"Using feature set: {feature_set}")
    _validate_feature_set(feature_set)

    policy = config.get("roll_boundary_policy") or {}
    out = df.copy()
    if feature_set in {"none", "opening_range"}:
        _emit(status_callback, "Skipping derived global features for this feature set.")
    else:
        if feature_set in {"full", "pdh_pdl_sweep"}:
            _emit(status_callback, "Building previous RTH level features...")
            out = add_previous_rth_levels(out, bool(policy.get("reset_previous_day_levels", False)))
        if feature_set == "full":
            _emit(status_callback, "Building overnight level features...")
            out = add_overnight_levels(out)
        if feature_set in {"full", "intraday_capitulation_mr"}:
            _emit(status_callback, "Building VWAP features...")
            out = add_vwap(out)
        if feature_set in {"full", "pdh_pdl_sweep"}:
            _emit(status_callback, "Building rolling-volume features...")
            out = add_rolling_volume(out, int(config.get("rolling_volume_window", 20)))
    if (config.get("vpin_toxicity_features") or {}).get("enabled", False):
        _emit(status_callback, "Building VPIN toxicity proxy features...")
        out = add_vpin_toxicity_features(out, config)
    if (config.get("trade_orderflow_features") or {}).get("enabled", False):
        _emit(status_callback, "Building trade-side orderflow features...")
        out = add_trade_orderflow_features(out, config)
    return out


def _validate_feature_set(feature_set: str) -> None:
    valid = {"full", "none", "opening_range", "pdh_pdl_sweep", "intraday_capitulation_mr"}
    if feature_set not in valid:
        raise ValueError(f"Unsupported data.feature_set: {feature_set}. Expected one of {sorted(valid)}.")


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)


def _shifted_rolling_rank(values: pd.Series, window: int, min_periods: int) -> pd.Series:
    return values.shift(1).rolling(window, min_periods=min_periods).rank(pct=True)


def _vpin_proxy_column(bucket_fraction: float, bucket_lookback: int) -> str:
    return f"vpin_proxy_b{int(round(bucket_fraction * 1000)):03d}_l{bucket_lookback}"


def _time_suffix(value) -> str:
    parsed = parse_time(value)
    return f"{parsed.hour:02d}{parsed.minute:02d}"
