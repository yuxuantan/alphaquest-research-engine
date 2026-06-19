from __future__ import annotations

import math

import numpy as np
import pandas as pd


FOOTPRINT_FEATURE_COLUMNS = [
    "footprint_sell_imbalance_count",
    "footprint_buy_imbalance_count",
    "footprint_max_sell_imbalance_ratio",
    "footprint_max_buy_imbalance_ratio",
    "footprint_max_sell_imbalance_volume",
    "footprint_max_buy_imbalance_volume",
    "footprint_highest_sell_imbalance_price",
    "footprint_lowest_buy_imbalance_price",
    "footprint_sell_imbalance_below_close",
    "footprint_buy_imbalance_above_close",
    "footprint_absorption_long",
    "footprint_absorption_short",
]


def add_footprint_imbalance_features(
    bars: pd.DataFrame,
    price_volume: pd.DataFrame,
    *,
    tick_size: float = 0.25,
    imbalance_ratio: float = 3.0,
    min_level_volume: float = 10.0,
) -> pd.DataFrame:
    """Add minute-level footprint diagonal-imbalance features to OHLCV bars.

    `price_volume` must contain one row per timestamp/price bucket with:
    `timestamp`, `price`, `bid_volume`, and `ask_volume`.

    Bid volume at a price is interpreted as sell pressure at that price. A sell
    imbalance compares bid volume at price P to ask volume at P + one tick.
    Ask volume at a price is interpreted as buy pressure at that price. A buy
    imbalance compares ask volume at price P to bid volume at P - one tick.
    """

    _validate_params(tick_size, imbalance_ratio, min_level_volume)
    out = bars.copy()
    for column in FOOTPRINT_FEATURE_COLUMNS:
        out[column] = 0.0
    if out.empty or price_volume.empty:
        return out

    work = _normalise_price_volume(price_volume, tick_size)
    if work.empty:
        return out

    out_index = pd.Index(pd.to_datetime(out["timestamp"]), name="timestamp")
    close_by_timestamp = pd.Series(
        pd.to_numeric(out["close"], errors="coerce").to_numpy(dtype=float),
        index=out_index,
    )
    rows = []
    for timestamp, group in work.groupby("timestamp", sort=True):
        close = close_by_timestamp.get(timestamp)
        if close is None or not math.isfinite(float(close)):
            continue
        metrics = _minute_footprint_metrics(
            group,
            close=float(close),
            tick_size=tick_size,
            imbalance_ratio=imbalance_ratio,
            min_level_volume=min_level_volume,
        )
        metrics["timestamp"] = timestamp
        rows.append(metrics)
    if not rows:
        return out

    features = pd.DataFrame(rows).set_index("timestamp")
    aligned = features.reindex(out_index)
    for column in FOOTPRINT_FEATURE_COLUMNS:
        out[column] = aligned[column].fillna(0.0).to_numpy(dtype=float)
    return out


def price_volume_from_prints(
    prints: pd.DataFrame,
    *,
    timestamp_col: str = "timestamp",
    price_col: str = "close",
    tick_size: float = 0.25,
) -> pd.DataFrame:
    """Aggregate Sierra-like print records to timestamp/price bid-ask volume."""

    required = {timestamp_col, price_col, "volume", "bid_volume", "ask_volume"}
    missing = required - set(prints.columns)
    if missing:
        raise ValueError(f"footprint prints missing required column(s): {sorted(missing)}")
    _validate_params(tick_size, 3.0, 1.0)
    if prints.empty:
        return pd.DataFrame(columns=["timestamp", "price", "volume", "bid_volume", "ask_volume"])

    work = prints.copy()
    work["timestamp"] = pd.to_datetime(work[timestamp_col]).dt.floor("min")
    work["price"] = _round_to_tick(pd.to_numeric(work[price_col], errors="coerce"), tick_size)
    for column in ["volume", "bid_volume", "ask_volume"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["timestamp", "price", "volume", "bid_volume", "ask_volume"])
    work = work[(work["price"] > 0) & (work["volume"] > 0)]
    if work.empty:
        return pd.DataFrame(columns=["timestamp", "price", "volume", "bid_volume", "ask_volume"])
    return (
        work.groupby(["timestamp", "price"], sort=True, observed=True)
        .agg(
            volume=("volume", "sum"),
            bid_volume=("bid_volume", "sum"),
            ask_volume=("ask_volume", "sum"),
        )
        .reset_index()
    )


def _minute_footprint_metrics(
    group: pd.DataFrame,
    *,
    close: float,
    tick_size: float,
    imbalance_ratio: float,
    min_level_volume: float,
) -> dict:
    by_price = group.sort_values("price").set_index("price")
    bid = pd.to_numeric(by_price["bid_volume"], errors="coerce").fillna(0.0)
    ask = pd.to_numeric(by_price["ask_volume"], errors="coerce").fillna(0.0)
    ask_above = ask.reindex(bid.index + tick_size).fillna(0.0).to_numpy(dtype=float)
    bid_below = bid.reindex(ask.index - tick_size).fillna(0.0).to_numpy(dtype=float)
    bid_values = bid.to_numpy(dtype=float)
    ask_values = ask.to_numpy(dtype=float)

    sell_ratio = _safe_ratio(bid_values, ask_above)
    buy_ratio = _safe_ratio(ask_values, bid_below)
    # A diagonal imbalance needs an observed opposite-side comparison level.
    # Without this guard, every sufficiently large bid at the bar high and ask
    # at the bar low becomes an artificial infinite-ratio imbalance.
    sell_mask = (bid_values >= min_level_volume) & (ask_above > 0) & (sell_ratio >= imbalance_ratio)
    buy_mask = (ask_values >= min_level_volume) & (bid_below > 0) & (buy_ratio >= imbalance_ratio)

    prices = bid.index.to_numpy(dtype=float)
    sell_prices = prices[sell_mask]
    buy_prices = ask.index.to_numpy(dtype=float)[buy_mask]
    sell_volumes = bid_values[sell_mask]
    buy_volumes = ask_values[buy_mask]
    sell_ratios = sell_ratio[sell_mask]
    buy_ratios = buy_ratio[buy_mask]

    highest_sell_price = float(np.max(sell_prices)) if len(sell_prices) else np.nan
    lowest_buy_price = float(np.min(buy_prices)) if len(buy_prices) else np.nan
    sell_below_close = bool(len(sell_prices) and np.any(sell_prices < close))
    buy_above_close = bool(len(buy_prices) and np.any(buy_prices > close))

    return {
        "footprint_sell_imbalance_count": int(len(sell_prices)),
        "footprint_buy_imbalance_count": int(len(buy_prices)),
        "footprint_max_sell_imbalance_ratio": _finite_or_zero(np.max(sell_ratios) if len(sell_ratios) else 0.0),
        "footprint_max_buy_imbalance_ratio": _finite_or_zero(np.max(buy_ratios) if len(buy_ratios) else 0.0),
        "footprint_max_sell_imbalance_volume": float(np.max(sell_volumes)) if len(sell_volumes) else 0.0,
        "footprint_max_buy_imbalance_volume": float(np.max(buy_volumes)) if len(buy_volumes) else 0.0,
        "footprint_highest_sell_imbalance_price": _finite_or_zero(highest_sell_price),
        "footprint_lowest_buy_imbalance_price": _finite_or_zero(lowest_buy_price),
        "footprint_sell_imbalance_below_close": float(sell_below_close),
        "footprint_buy_imbalance_above_close": float(buy_above_close),
        "footprint_absorption_long": float(sell_below_close),
        "footprint_absorption_short": float(buy_above_close),
    }


def _normalise_price_volume(price_volume: pd.DataFrame, tick_size: float) -> pd.DataFrame:
    required = {"timestamp", "price", "bid_volume", "ask_volume"}
    missing = required - set(price_volume.columns)
    if missing:
        raise ValueError(f"footprint price volume missing required column(s): {sorted(missing)}")
    work = price_volume.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"]).dt.floor("min")
    work["price"] = _round_to_tick(pd.to_numeric(work["price"], errors="coerce"), tick_size)
    for column in ["bid_volume", "ask_volume"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["timestamp", "price", "bid_volume", "ask_volume"])
    return work[(work["price"] > 0) & ((work["bid_volume"] > 0) | (work["ask_volume"] > 0))]


def _safe_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    ratio = np.zeros(len(numerator), dtype=float)
    positive_denominator = denominator > 0
    ratio[positive_denominator] = numerator[positive_denominator] / denominator[positive_denominator]
    ratio[~positive_denominator & (numerator > 0)] = np.inf
    return ratio


def _round_to_tick(values: pd.Series, tick_size: float) -> pd.Series:
    return (values.astype(float) / tick_size).round() * tick_size


def _finite_or_zero(value: float) -> float:
    return float(value) if math.isfinite(float(value)) else 0.0


def _validate_params(tick_size: float, imbalance_ratio: float, min_level_volume: float) -> None:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive.")
    if imbalance_ratio <= 0:
        raise ValueError("imbalance_ratio must be positive.")
    if min_level_volume <= 0:
        raise ValueError("min_level_volume must be positive.")
