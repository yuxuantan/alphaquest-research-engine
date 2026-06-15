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
    out["overnight_high"] = pd.NA
    out["overnight_low"] = pd.NA
    if out.empty or "is_eth" not in out.columns:
        return out

    ordered = out.sort_values("timestamp")
    eth_mask = ordered["is_eth"].fillna(False).astype(bool)
    if not eth_mask.any():
        return out

    eth = ordered.loc[eth_mask]
    cumulative_high = eth.groupby("session_date")["high"].cummax()
    cumulative_low = eth.groupby("session_date")["low"].cummin()
    out.loc[eth.index, "overnight_high"] = cumulative_high
    out.loc[eth.index, "overnight_low"] = cumulative_low

    completed = eth.groupby("session_date").agg(
        overnight_high=("high", "max"),
        overnight_low=("low", "min"),
    )
    rth_mask = out.get("is_rth", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    if rth_mask.any():
        mapped = out.loc[rth_mask, ["session_date"]].merge(
            completed,
            left_on="session_date",
            right_index=True,
            how="left",
        )
        out.loc[rth_mask, "overnight_high"] = mapped["overnight_high"].to_numpy()
        out.loc[rth_mask, "overnight_low"] = mapped["overnight_low"].to_numpy()
    return out


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
            group[f"trade_orderflow_abs_imbalance_{suffix}"] = group[
                f"trade_orderflow_imbalance_{suffix}"
            ].abs()
            group[f"trade_orderflow_signed_toxicity_{suffix}"] = group[
                f"trade_orderflow_abs_imbalance_{suffix}"
            ]
            if "trades" in group.columns:
                trades = pd.to_numeric(group["trades"], errors="coerce").rolling(
                    window, min_periods=min_periods
                ).sum()
                group[f"trade_orderflow_trades_{suffix}"] = trades
                group[f"trade_orderflow_avg_trade_size_{suffix}"] = volume / trades.replace(0.0, np.nan)
            group[f"trade_orderflow_effort_vs_result_{suffix}"] = (
                volume / group[f"trade_orderflow_return_ticks_{suffix}"].abs().clip(lower=1.0)
            )
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
    out = out.replace([np.inf, -np.inf], np.nan)
    inventory_cfg = feature_cfg.get("prior_session_inventory") or {}
    if inventory_cfg.get("enabled", False):
        out = _add_trade_orderflow_prior_session_inventory(out, inventory_cfg)
    opening_cfg = feature_cfg.get("opening_drive") or {}
    if opening_cfg.get("enabled", False):
        out = _add_trade_orderflow_opening_drive(out, opening_cfg, config, tick_size)
    rank_cfg = feature_cfg.get("same_clock_ranks") or {}
    if rank_cfg.get("enabled", False):
        out = _add_trade_orderflow_same_clock_ranks(out, rank_cfg)
    return out.replace([np.inf, -np.inf], np.nan)


def _add_trade_orderflow_prior_session_inventory(df: pd.DataFrame, inventory_cfg: dict) -> pd.DataFrame:
    out = df.sort_values("timestamp").copy()
    rank_windows = [int(value) for value in inventory_cfg.get("rank_windows", [252])]
    min_periods_cfg = inventory_cfg.get("rank_min_periods")
    if not rank_windows or any(window <= 0 for window in rank_windows):
        raise ValueError("data.trade_orderflow_features.prior_session_inventory.rank_windows must be positive.")
    session_frame = out
    if "session_label" in session_frame.columns:
        session_frame = session_frame[session_frame["session_label"].astype(str) == "RTH"]
    daily = (
        session_frame.groupby("session_date", sort=True)
        .agg(signed_volume=("signed_volume", "sum"), volume=("volume", "sum"))
        .sort_index()
    )
    daily["trade_orderflow_prior_session_signed_volume"] = daily["signed_volume"].shift(1)
    daily["trade_orderflow_prior_session_volume"] = daily["volume"].shift(1)
    daily["trade_orderflow_prior_session_imbalance"] = (
        daily["trade_orderflow_prior_session_signed_volume"]
        / daily["trade_orderflow_prior_session_volume"].replace(0.0, np.nan)
    )
    for window in rank_windows:
        min_periods = _same_clock_rank_min_periods(min_periods_cfg, window)
        daily[f"trade_orderflow_prior_session_imbalance_rank{window}"] = _prior_window_rank_series(
            daily["trade_orderflow_prior_session_imbalance"],
            window,
            min_periods,
        )
    for column in [
        "trade_orderflow_prior_session_signed_volume",
        "trade_orderflow_prior_session_volume",
        "trade_orderflow_prior_session_imbalance",
        *[f"trade_orderflow_prior_session_imbalance_rank{window}" for window in rank_windows],
    ]:
        out[column] = out["session_date"].map(daily[column])
    return out


def _add_trade_orderflow_opening_drive(
    df: pd.DataFrame,
    opening_cfg: dict,
    config: dict,
    tick_size: float,
) -> pd.DataFrame:
    out = df.sort_values("timestamp").copy()
    windows = [dict(item) for item in opening_cfg.get("windows", [])]
    if not windows:
        raise ValueError("data.trade_orderflow_features.opening_drive.windows must not be empty.")
    rank_windows = [int(value) for value in opening_cfg.get("volume_rank_windows", [42])]
    rank_min_periods_cfg = opening_cfg.get("volume_rank_min_periods")
    if any(window <= 0 for window in rank_windows):
        raise ValueError("data.trade_orderflow_features.opening_drive.volume_rank_windows must be positive.")

    bar_interval_raw = opening_cfg.get(
        "bar_interval_minutes",
        config.get("bar_interval_minutes", out.get("timeframe_minutes", 1)),
    )
    if isinstance(bar_interval_raw, pd.Series):
        non_null_intervals = bar_interval_raw.dropna()
        bar_interval_raw = float(non_null_intervals.iloc[0]) if not non_null_intervals.empty else 1.0
    bar_interval_minutes = float(bar_interval_raw)
    if bar_interval_minutes <= 0:
        raise ValueError("data.trade_orderflow_features.opening_drive.bar_interval_minutes must be positive.")

    session_start = parse_time(opening_cfg.get("rth_start", config.get("rth_start", "09:30:00")))
    group_cols = ["session_date"]
    for optional in ["symbol"]:
        if optional in out.columns:
            group_cols.append(optional)

    for label in [_opening_window_label(item) for item in windows]:
        for column in [
            f"trade_orderflow_opening_return_ticks_{label}",
            f"trade_orderflow_opening_imbalance_{label}",
            f"trade_orderflow_opening_abs_imbalance_{label}",
            f"trade_orderflow_opening_volume_{label}",
        ]:
            out[column] = np.nan
        for rank_window in rank_windows:
            out[f"trade_orderflow_opening_volume_rank{rank_window}_{label}"] = np.nan

    out["trade_orderflow_session_return_ticks"] = np.nan
    out["trade_orderflow_session_cum_delta_ratio"] = np.nan
    out["trade_orderflow_price_vs_vwap_ticks"] = np.nan

    session_records: dict[str, list[dict]] = {
        _opening_window_label(item): [] for item in windows
    }
    for group_key, group in out.groupby(group_cols, sort=True, dropna=False):
        group = group.sort_values("timestamp")
        if group.empty:
            continue
        open_price = _first_finite(group["open"])
        close = pd.to_numeric(group["close"], errors="coerce").astype(float)
        volume = pd.to_numeric(group["volume"], errors="coerce").astype(float)
        signed = pd.to_numeric(group["signed_volume"], errors="coerce").astype(float)
        cum_volume = volume.cumsum()
        cum_pv = (close * volume).cumsum()
        vwap = cum_pv / cum_volume.replace(0.0, np.nan)
        if np.isfinite(open_price) and tick_size > 0:
            out.loc[group.index, "trade_orderflow_session_return_ticks"] = (
                (close - open_price) / tick_size
            ).to_numpy(dtype=float)
        out.loc[group.index, "trade_orderflow_session_cum_delta_ratio"] = (
            signed.cumsum() / cum_volume.replace(0.0, np.nan)
        ).to_numpy(dtype=float)
        out.loc[group.index, "trade_orderflow_price_vs_vwap_ticks"] = (
            (close - vwap) / tick_size
        ).to_numpy(dtype=float)

        timestamp = pd.to_datetime(group["timestamp"])
        bar_close = timestamp + pd.to_timedelta(bar_interval_minutes, unit="m")
        reference = pd.Timestamp(group.iloc[0]["timestamp"])
        session_date = group.iloc[0]["session_date"]
        key_values = group_key if isinstance(group_key, tuple) else (group_key,)
        symbol_value = key_values[group_cols.index("symbol")] if "symbol" in group_cols else None

        for item in windows:
            label = _opening_window_label(item)
            minutes = int(item.get("minutes", str(label).rstrip("m")))
            bars = int(item.get("bars", max(1, round(minutes / bar_interval_minutes))))
            capture_ts = _local_session_timestamp_for_feature(session_date, session_start, reference) + pd.Timedelta(
                minutes=minutes
            )
            eligible = bar_close <= capture_ts
            if not eligible.any():
                continue
            capture_idx = group.index[eligible][-1]
            capture_close = bar_close.loc[capture_idx]
            if capture_close != capture_ts:
                continue
            return_col = f"trade_orderflow_return_ticks_{bars}"
            imbalance_col = f"trade_orderflow_imbalance_{bars}"
            volume_col = f"trade_orderflow_volume_{bars}"
            missing = [column for column in [return_col, imbalance_col, volume_col] if column not in out.columns]
            if missing:
                raise ValueError(
                    "trade_orderflow opening_drive requires rolling orderflow columns. "
                    f"Missing: {missing}."
                )
            return_value = _finite_float_value(out.loc[capture_idx, return_col])
            imbalance_value = _finite_float_value(out.loc[capture_idx, imbalance_col])
            volume_value = _finite_float_value(out.loc[capture_idx, volume_col])
            visible = group.index[bar_close >= capture_ts]
            out.loc[visible, f"trade_orderflow_opening_return_ticks_{label}"] = return_value
            out.loc[visible, f"trade_orderflow_opening_imbalance_{label}"] = imbalance_value
            out.loc[visible, f"trade_orderflow_opening_abs_imbalance_{label}"] = (
                abs(imbalance_value) if np.isfinite(imbalance_value) else np.nan
            )
            out.loc[visible, f"trade_orderflow_opening_volume_{label}"] = volume_value
            session_records[label].append(
                {
                    "session_date": pd.Timestamp(session_date),
                    "symbol": symbol_value,
                    "volume": volume_value,
                    "visible_index": visible,
                }
            )

    for label, records in session_records.items():
        if not records:
            continue
        frame = pd.DataFrame(
            {
                "session_date": [record["session_date"] for record in records],
                "symbol": [record["symbol"] for record in records],
                "volume": [record["volume"] for record in records],
            }
        )
        rank_group_cols = ["symbol"] if "symbol" in group_cols else []
        if rank_group_cols:
            rank_groups = frame.groupby(rank_group_cols, sort=False, dropna=False)
        else:
            rank_groups = [((), frame)]
        for _, rank_group in rank_groups:
            rank_group = rank_group.sort_values("session_date")
            for rank_window in rank_windows:
                min_periods = _same_clock_rank_min_periods(rank_min_periods_cfg, rank_window)
                ranks = _prior_window_rank_series(rank_group["volume"], rank_window, min_periods)
                for record_index, rank_value in zip(rank_group.index, ranks, strict=False):
                    out.loc[
                        records[int(record_index)]["visible_index"],
                        f"trade_orderflow_opening_volume_rank{rank_window}_{label}",
                    ] = rank_value
    return out


def _opening_window_label(item: dict) -> str:
    raw = str(item.get("label", f"{int(item.get('minutes', 30))}m")).lower()
    return "".join(ch for ch in raw if ch.isalnum())


def _first_finite(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    return float(finite.iloc[0]) if not finite.empty else np.nan


def _finite_float_value(value) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return np.nan
    return out if np.isfinite(out) else np.nan


def _local_session_timestamp_for_feature(session_date, session_time, reference: pd.Timestamp) -> pd.Timestamp:
    naive = pd.Timestamp.combine(pd.Timestamp(session_date).date(), session_time)
    if reference.tzinfo is None:
        return naive
    return naive.tz_localize(reference.tz)


def add_orderflow_recent_pocket_combo_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    feature_cfg = config.get("orderflow_recent_pocket_combo_features") or {}
    tick_size = float(feature_cfg.get("tick_size", config.get("tick_size", 0.25)))
    if tick_size <= 0:
        raise ValueError("data.orderflow_recent_pocket_combo_features.tick_size must be greater than 0.")
    required = {
        "timestamp",
        "session_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "signed_volume",
        "trade_orderflow_imbalance_15",
        "trade_orderflow_imbalance_30",
        "trade_orderflow_return_ticks_15",
        "trade_orderflow_return_ticks_30",
        "trade_orderflow_volume_15",
        "trade_orderflow_volume_30",
        "trade_orderflow_abs_imbalance_30",
    }
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(f"orderflow_recent_pocket_combo_features missing required columns: {missing}.")

    out = out.sort_values("timestamp").copy()
    session_keys = ["session_date"]
    if "session_label" in out.columns:
        session_keys.append("session_label")
    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    cumulative_pv = (typical * out["volume"]).groupby([out[key] for key in session_keys], sort=False).cumsum()
    cumulative_volume = out["volume"].groupby([out[key] for key in session_keys], sort=False).cumsum()
    out["of_combo_vwap"] = cumulative_pv / cumulative_volume.replace(0.0, np.nan)
    out["of_combo_price_vs_vwap_ticks"] = (out["close"] - out["of_combo_vwap"]) / tick_size
    out["of_combo_price_vs_vwap_ticks_rank42"] = _same_clock_prior_rank(
        out, "of_combo_price_vs_vwap_ticks", 42, 20
    )

    session_open = out.groupby("session_date", sort=False)["open"].transform("first")
    out["of_combo_session_return_ticks"] = (out["close"] - session_open) / tick_size
    out["of_combo_session_return_rank42"] = _same_clock_prior_rank(out, "of_combo_session_return_ticks", 42, 20)
    out["of_combo_imbalance_30_rank42"] = _same_clock_prior_rank(out, "trade_orderflow_imbalance_30", 42, 20)
    out["of_combo_abs_imbalance_30_rank42"] = _same_clock_prior_rank(
        out, "trade_orderflow_abs_imbalance_30", 42, 20
    )
    out["of_combo_volume_15_rank42"] = _same_clock_prior_rank(out, "trade_orderflow_volume_15", 42, 14)
    out["of_combo_volume_30_rank42"] = _same_clock_prior_rank(out, "trade_orderflow_volume_30", 42, 20)
    out["of_combo_sc_imbalance_15_z60"] = _same_clock_shifted_mean_zscore(
        out, "trade_orderflow_imbalance_15", 60, 30
    )
    out["of_combo_sc_imbalance_30_z60"] = _same_clock_shifted_mean_zscore(
        out, "trade_orderflow_imbalance_30", 60, 30
    )

    daily = out.groupby("session_date", sort=True).agg(
        open=("open", "first"),
        close=("close", "last"),
        volume=("volume", "sum"),
        signed=("signed_volume", "sum"),
    )
    shifted = daily[["signed", "volume"]].shift(1)
    daily["of_combo_inv2_signed"] = shifted["signed"].rolling(2, min_periods=2).sum()
    daily["of_combo_inv2_volume"] = shifted["volume"].rolling(2, min_periods=2).sum()
    daily["of_combo_inv2_imbalance"] = daily["of_combo_inv2_signed"] / daily[
        "of_combo_inv2_volume"
    ].replace(0.0, np.nan)
    daily_returns = ((daily["close"] - daily["open"]) / tick_size).shift(1)
    daily["of_combo_inv2_return_ticks"] = daily_returns.rolling(2, min_periods=2).sum()
    daily["of_combo_inv2_abs_imbalance"] = daily["of_combo_inv2_imbalance"].abs()
    daily["of_combo_inv2_imbalance_rank252"] = _prior_window_rank_series(
        daily["of_combo_inv2_imbalance"], 252, 84
    )
    daily["of_combo_inv2_abs_imbalance_rank252"] = _prior_window_rank_series(
        daily["of_combo_inv2_abs_imbalance"], 252, 84
    )
    session_map = out["session_date"].map
    for column in [
        "of_combo_inv2_imbalance",
        "of_combo_inv2_return_ticks",
        "of_combo_inv2_imbalance_rank252",
        "of_combo_inv2_abs_imbalance_rank252",
    ]:
        out[column] = session_map(daily[column])

    out["of_combo_signal_sc_short_1130_loose"] = (
        (-out["of_combo_sc_imbalance_15_z60"] <= 0.0625)
        & (-out["trade_orderflow_imbalance_15"] >= 0.045)
        & (-out["trade_orderflow_imbalance_30"] >= 0.03)
        & (-out["trade_orderflow_return_ticks_15"] >= 2.0)
        & (out["of_combo_volume_15_rank42"] >= 0.80)
    )
    out["of_combo_signal_multi_short_1130"] = (
        (out["of_combo_inv2_imbalance"] < 0.0)
        & ((1.0 - out["of_combo_inv2_imbalance_rank252"]) >= 0.90)
        & (out["of_combo_inv2_return_ticks"] < 0.0)
        & (out["of_combo_inv2_abs_imbalance_rank252"] >= 0.90)
    )
    out["of_combo_signal_late_vwap_short_1330"] = (
        (out["trade_orderflow_imbalance_30"] >= 0.06)
        & (out["of_combo_abs_imbalance_30_rank42"] >= 0.60)
        & (out["of_combo_price_vs_vwap_ticks"] >= 12.0)
        & (out["of_combo_price_vs_vwap_ticks_rank42"] >= 0.60)
        & (out["of_combo_volume_30_rank42"] >= 0.50)
    )
    out["of_combo_signal_late_flow_long_1500"] = (
        (out["trade_orderflow_imbalance_30"] >= 0.03)
        & (out["of_combo_imbalance_30_rank42"] >= 0.75)
        & (out["trade_orderflow_return_ticks_30"] >= 2.0)
        & (out["of_combo_session_return_ticks"] >= 8.0)
    )
    return out.replace([np.inf, -np.inf], np.nan)


def _same_clock_prior_rank(df: pd.DataFrame, column: str, window: int, min_periods: int) -> pd.Series:
    ordered = df.sort_values("timestamp")
    time_key = pd.to_datetime(ordered["timestamp"]).dt.strftime("%H:%M:%S")
    values = pd.to_numeric(ordered[column], errors="coerce")
    ranked = values.groupby(time_key, sort=False).transform(
        lambda series: _rank_current_against_prior_window(series, window, min_periods)
    )
    out = pd.Series(np.nan, index=df.index, dtype=float)
    out.loc[ordered.index] = ranked.to_numpy(dtype=float)
    return out


def _same_clock_shifted_mean_zscore(
    df: pd.DataFrame, column: str, window: int, min_periods: int
) -> pd.Series:
    ordered = df.sort_values("timestamp")
    time_key = pd.to_datetime(ordered["timestamp"]).dt.strftime("%H:%M:%S")
    values = pd.to_numeric(ordered[column], errors="coerce")

    def calculate(series: pd.Series) -> pd.Series:
        shifted = series.shift(1)
        mean = shifted.rolling(window, min_periods=min_periods).mean()
        std = shifted.rolling(window, min_periods=min_periods).std()
        return mean / std.replace(0.0, np.nan)

    zscore = values.groupby(time_key, sort=False).transform(calculate)
    out = pd.Series(np.nan, index=df.index, dtype=float)
    out.loc[ordered.index] = zscore.to_numpy(dtype=float)
    return out


def _prior_window_rank_series(values: pd.Series, window: int, min_periods: int) -> pd.Series:
    raw = values.to_numpy(dtype=float)
    out = np.full(len(raw), np.nan, dtype=float)
    for i, value in enumerate(raw):
        history = raw[max(0, i - window) : i]
        history = history[np.isfinite(history)]
        if len(history) < min_periods or not np.isfinite(value):
            continue
        out[i] = float((history <= value).mean())
    return pd.Series(out, index=values.index)


def _add_trade_orderflow_same_clock_ranks(df: pd.DataFrame, rank_cfg: dict) -> pd.DataFrame:
    out = df.copy()
    columns = [str(value) for value in rank_cfg.get("columns", [])]
    rank_windows = [int(value) for value in rank_cfg.get("rank_windows", [21, 63])]
    min_periods_cfg = rank_cfg.get("rank_min_periods")

    if not columns:
        raise ValueError("data.trade_orderflow_features.same_clock_ranks.columns must not be empty.")
    if not rank_windows or any(window <= 0 for window in rank_windows):
        raise ValueError("data.trade_orderflow_features.same_clock_ranks.rank_windows must contain positive integers.")
    if "timestamp" not in out.columns:
        raise ValueError("trade_orderflow same-clock ranks require a timestamp column.")
    missing = [column for column in columns if column not in out.columns]
    if missing:
        raise ValueError(f"trade_orderflow same-clock rank columns are missing: {missing}.")

    ordered = out.sort_values("timestamp").copy()
    time_key = pd.to_datetime(ordered["timestamp"]).dt.strftime("%H:%M:%S")
    group_keys = [time_key]
    for optional in ("symbol",):
        if optional in ordered.columns:
            group_keys.append(ordered[optional].astype(str))

    for column in columns:
        values = pd.to_numeric(ordered[column], errors="coerce")
        for window in rank_windows:
            min_periods = _same_clock_rank_min_periods(min_periods_cfg, window)
            rank_col = f"{column}_rank{window}"
            ranked = values.groupby(group_keys, sort=False).transform(
                lambda series: _rank_current_against_prior_window(series, window, min_periods)
            )
            out.loc[ordered.index, rank_col] = ranked.to_numpy(dtype=float)
    return out


def _same_clock_rank_min_periods(config_value, window: int) -> int:
    if isinstance(config_value, dict):
        value = config_value.get(str(window), config_value.get(window))
        if value is not None:
            return int(value)
    elif config_value is not None:
        return int(config_value)
    return max(5, window // 3)


def _rank_current_against_prior_window(values: pd.Series, window: int, min_periods: int) -> pd.Series:
    raw = values.to_numpy(dtype=float)
    out = np.full(len(raw), np.nan, dtype=float)
    for i, value in enumerate(raw):
        start = max(0, i - window)
        history = raw[start:i]
        history = history[np.isfinite(history)]
        if len(history) < min_periods or not np.isfinite(value):
            continue
        out[i] = float((history <= value).mean())
    return pd.Series(out, index=values.index)


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
    if (config.get("orderflow_recent_pocket_combo_features") or {}).get("enabled", False):
        _emit(status_callback, "Building recent-pocket aggregate orderflow combo features...")
        out = add_orderflow_recent_pocket_combo_features(out, config)
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
