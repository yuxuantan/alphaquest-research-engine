from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


FIRST_LAST_SPLIT = -1.9990015e37
SIERRA_TIMESTAMP_PRECISION_NS = 1_000_000
SIERRA_EVENT_PRICE_PATH_SEMANTICS = "sierra_unbundled_trade_event_v1"


def reconstruct_sierra_trade_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Collapse Sierra FIRST/LAST component records into canonical trade events.

    Source order is authoritative. The function intentionally does not sort by
    timestamp: equal/millisecond-quantized timestamps need their original row
    order for sequential 100 ms trigger logic.
    """

    required = {
        "scid_datetime_us",
        "open",
        "close",
        "volume",
        "bid_volume",
        "ask_volume",
        "source_ordinal",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Sierra event reconstruction is missing columns: {missing}")
    if frame.empty:
        return _empty_events(), _empty_stats()

    ordinal = pd.to_numeric(frame["source_ordinal"], errors="raise").to_numpy(dtype=np.int64)
    if np.any(np.diff(ordinal) <= 0):
        raise ValueError("Sierra source_ordinal must be strictly increasing; input must not be resorted.")
    scid_us = pd.to_numeric(frame["scid_datetime_us"], errors="raise").to_numpy(dtype=np.int64)
    if np.any(np.diff(scid_us) < 0):
        raise ValueError("Sierra source timestamps invert; refusing to reorder an ambiguous event stream.")

    side = np.select(
        [
            frame["ask_volume"].gt(0) & frame["bid_volume"].eq(0),
            frame["bid_volume"].gt(0) & frame["ask_volume"].eq(0),
        ],
        ["B", "A"],
        default="N",
    )
    if np.any(side == "N"):
        bad = int(np.count_nonzero(side == "N"))
        raise ValueError(f"Sierra contains {bad} records without an unambiguous aggressor side.")

    marker_open = pd.to_numeric(frame["open"], errors="raise").to_numpy(dtype=np.float64)
    first = (marker_open < -1e30) & (marker_open > FIRST_LAST_SPLIT)
    last = marker_open <= FIRST_LAST_SPLIT
    n = len(frame)
    depth_delta = np.zeros(n + 1, dtype=np.int32)
    depth_delta[np.flatnonzero(first)] += 1
    after_last = np.flatnonzero(last) + 1
    depth_delta[after_last[after_last <= n]] -= 1
    depth = np.cumsum(depth_delta[:-1])
    marker_valid = bool(
        first.sum() == last.sum()
        and (depth >= 0).all()
        and depth.max(initial=0) <= 1
        and depth_delta.sum() == 0
    )
    if not marker_valid:
        raise ValueError("Sierra FIRST/LAST unbundled-trade markers are unbalanced or nested.")

    starts = np.maximum.accumulate(np.where(first, np.arange(n), -1))
    group_id = np.where(depth > 0, starts, np.arange(n))
    working = frame.assign(group_id=group_id, side=side)
    events = (
        working.groupby(["group_id", "close", "side"], sort=False, as_index=False)
        .agg(
            scid_datetime_us=("scid_datetime_us", "first"),
            last_scid_datetime_us=("scid_datetime_us", "last"),
            volume=("volume", "sum"),
            buy_volume=("ask_volume", "sum"),
            sell_volume=("bid_volume", "sum"),
            component_rows=("volume", "size"),
            source_ordinal=("source_ordinal", "first"),
        )
        .rename(columns={"close": "price"})
    )
    events["volume"] = events["volume"].astype(np.int64)
    events["buy_volume"] = events["buy_volume"].astype(np.int64)
    events["sell_volume"] = events["sell_volume"].astype(np.int64)
    events["signed_volume"] = events["buy_volume"] - events["sell_volume"]
    events["timestamp_precision_ns"] = SIERRA_TIMESTAMP_PRECISION_NS
    events["timestamp_uncertainty_ns"] = SIERRA_TIMESTAMP_PRECISION_NS
    events["execution_granularity"] = "normalized_trade_event"
    events["price_path_semantics"] = SIERRA_EVENT_PRICE_PATH_SEMANTICS
    events = events[
        [
            "scid_datetime_us",
            "last_scid_datetime_us",
            "source_ordinal",
            "price",
            "volume",
            "side",
            "buy_volume",
            "sell_volume",
            "signed_volume",
            "component_rows",
            "timestamp_precision_ns",
            "timestamp_uncertainty_ns",
            "execution_granularity",
            "price_path_semantics",
        ]
    ].reset_index(drop=True)
    return events, {
        "raw_rows": int(n),
        "events": int(len(events)),
        "first_markers": int(first.sum()),
        "last_markers": int(last.sum()),
        "unbundled_component_rows": int((depth > 0).sum()),
        "marker_valid": marker_valid,
    }


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "scid_datetime_us",
            "last_scid_datetime_us",
            "source_ordinal",
            "price",
            "volume",
            "side",
            "buy_volume",
            "sell_volume",
            "signed_volume",
            "component_rows",
            "timestamp_precision_ns",
            "timestamp_uncertainty_ns",
            "execution_granularity",
            "price_path_semantics",
        ]
    )


def _empty_stats() -> dict[str, Any]:
    return {
        "raw_rows": 0,
        "events": 0,
        "first_markers": 0,
        "last_markers": 0,
        "unbundled_component_rows": 0,
        "marker_valid": True,
    }
