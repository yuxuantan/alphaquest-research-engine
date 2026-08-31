"""Build causal rolling three-minute, four-tick delta thresholds for Yush v03.

Each observation is the absolute ask-minus-bid delta of one populated
three-minute RTH bar by MotiveWave-style fixed price interval.  A session's
threshold uses only the previous N completed eligible RTH sessions.
"""

from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alphaquest.data.scid_execution import iter_scid_record_execution_sessions


DEFAULT_DATASET_MANIFEST = Path(
    "research/datasets/"
    "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/"
    "dataset_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "research/datasets/"
    "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/"
    "bar_delta_3m_4tick_q90_prior20_context.parquet"
)
AGGREGATION_METHOD = "motivewave_fixed_tick_interval_floor"
DELTA_DEFINITION = "ask_volume_minus_bid_volume"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", type=Path, default=DEFAULT_DATASET_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lookback-sessions", type=int, default=20)
    parser.add_argument("--percentile", type=float, default=0.90)
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--bar-seconds", type=int, default=180)
    parser.add_argument("--price-bin-ticks", type=int, default=4)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.lookback_sessions < 1:
        raise ValueError("lookback-sessions must be positive")
    if not 0.0 < args.percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    if args.tick_size <= 0 or args.bar_seconds <= 0 or args.price_bin_ticks <= 0:
        raise ValueError("tick-size, bar-seconds, and price-bin-ticks must be positive")
    if args.workers < 1:
        raise ValueError("workers must be positive")

    manifest = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    event_source = manifest.get("event_source")
    if not isinstance(event_source, dict):
        raise ValueError("dataset manifest has no event_source mapping")
    execution = dict(event_source)
    execution["canonical_session_cache"] = False

    historical: deque[np.ndarray] = deque()
    records: deque[dict[str, str]] = deque()
    rolling = np.zeros(1, dtype=np.int64)
    rows: list[dict[str, Any]] = []
    processed = 0
    sessions = _load_session_histograms(
        execution,
        tick_size=args.tick_size,
        bar_seconds=args.bar_seconds,
        price_bin_ticks=args.price_bin_ticks,
        workers=args.workers,
    )
    for session_date, contract_symbol, histogram, observation_count in sessions:
        if observation_count <= 0:
            raise ValueError(f"session {session_date} has no populated bar-delta cells")
        if len(historical) == args.lookback_sessions:
            threshold = _nearest_rank_percentile_from_histogram(rolling, args.percentile)
            rows.append(
                {
                    "session_date": str(session_date),
                    "contract_symbol": contract_symbol,
                    "lookback_sessions": int(args.lookback_sessions),
                    "reference_percentile": float(args.percentile),
                    "percentile_method": "nearest_rank_higher",
                    "threshold_abs_delta": int(threshold),
                    "reference_observation_count": int(rolling.sum()),
                    "reference_start_session": records[0]["session_date"],
                    "reference_end_session": records[-1]["session_date"],
                    "reference_start_contract": records[0]["contract_symbol"],
                    "reference_end_contract": records[-1]["contract_symbol"],
                    "bar_seconds": int(args.bar_seconds),
                    "aggregation_price_ticks": int(args.price_bin_ticks),
                    "aggregation_method": AGGREGATION_METHOD,
                    "delta_definition": DELTA_DEFINITION,
                    "observation_scope": "completed_rth_3m_bar_by_populated_price_cell",
                }
            )
        rolling = _histogram_add(rolling, histogram)
        historical.append(histogram)
        records.append(
            {"session_date": str(session_date), "contract_symbol": contract_symbol}
        )
        if len(historical) > args.lookback_sessions:
            rolling = _histogram_subtract(rolling, historical.popleft())
            records.popleft()
        processed += 1
        if args.progress_every > 0 and processed % args.progress_every == 0:
            print(
                json.dumps(
                    {
                        "processed_sessions": processed,
                        "latest_session": str(session_date),
                        "context_rows": len(rows),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    output = pd.DataFrame.from_records(rows)
    if output.empty or output["session_date"].duplicated().any():
        raise ValueError("bar-delta context is empty or contains duplicate sessions")
    output = output.sort_values("session_date", kind="mergesort").reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output, index=False)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "schema": "alphaquest.yush-bar-delta-context/v1",
                "dataset_manifest": str(args.dataset_manifest),
                "output": str(args.output),
                "processed_sessions": processed,
                "rows": int(len(output)),
                "coverage_start": str(output["session_date"].min()),
                "coverage_end": str(output["session_date"].max()),
                "lookback_sessions": int(args.lookback_sessions),
                "percentile": float(args.percentile),
                "bar_seconds": int(args.bar_seconds),
                "price_bin_ticks": int(args.price_bin_ticks),
                "aggregation_method": AGGREGATION_METHOD,
                "sha256": digest,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _load_session_histograms(
    execution: dict[str, Any],
    *,
    tick_size: float,
    bar_seconds: int,
    price_bin_ticks: int,
    workers: int,
) -> list[tuple[str, str, np.ndarray, int]]:
    if workers == 1:
        return _session_histograms_for_bounds(
            execution, None, tick_size, bar_seconds, price_bin_ticks
        )
    quality = pd.read_csv(Path(str(execution["quality_manifest"])))
    dates = pd.to_datetime(quality["session_date"], errors="raise")
    tasks = [
        (
            execution,
            {"start_date": f"{year}-01-01", "end_date": f"{year}-12-31"},
            tick_size,
            bar_seconds,
            price_bin_ticks,
        )
        for year in range(int(dates.dt.year.min()), int(dates.dt.year.max()) + 1)
    ]
    rows: list[tuple[str, str, np.ndarray, int]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_session_histograms_for_bounds, *task): task[1] for task in tasks}
        for future in as_completed(futures):
            part = future.result()
            rows.extend(part)
            print(
                json.dumps(
                    {"histogram_range_complete": futures[future], "sessions": len(part)},
                    sort_keys=True,
                ),
                flush=True,
            )
    rows.sort(key=lambda item: item[0])
    return rows


def _session_histograms_for_bounds(
    execution: dict[str, Any],
    date_bounds: dict[str, str] | None,
    tick_size: float,
    bar_seconds: int,
    price_bin_ticks: int,
) -> list[tuple[str, str, np.ndarray, int]]:
    rows: list[tuple[str, str, np.ndarray, int]] = []
    for session_date, events in iter_scid_record_execution_sessions(
        execution, date_bounds=date_bounds
    ):
        histogram, observations = _session_bar_delta_histogram(
            events,
            tick_size=tick_size,
            bar_seconds=bar_seconds,
            price_bin_ticks=price_bin_ticks,
        )
        rows.append(
            (
                str(session_date),
                str(events["contract_symbol"].iloc[0]),
                histogram,
                observations,
            )
        )
    return rows


def _session_bar_delta_histogram(
    events: pd.DataFrame,
    *,
    tick_size: float,
    bar_seconds: int,
    price_bin_ticks: int,
) -> tuple[np.ndarray, int]:
    required = {"timestamp", "close", "signed_volume"}
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError("canonical event session is missing columns: " + ", ".join(missing))
    if events.empty:
        return np.zeros(1, dtype=np.int64), 0
    timestamp_ns = pd.to_datetime(events["timestamp"], utc=True).astype("int64").to_numpy(
        dtype=np.int64, copy=False
    )
    open_ns = (
        pd.Timestamp(events["timestamp"].iloc[0])
        .tz_convert("America/New_York")
        .normalize()
        .replace(hour=9, minute=30)
        .tz_convert("UTC")
        .value
    )
    bar = np.floor_divide(timestamp_ns - open_ns, int(bar_seconds) * 1_000_000_000)
    price_tick = np.rint(
        events["close"].to_numpy(dtype=float, copy=False) / tick_size
    ).astype(np.int64)
    price_cell = np.floor_divide(price_tick, int(price_bin_ticks)) * int(price_bin_ticks)
    signed = events["signed_volume"].to_numpy(dtype=np.int64, copy=False)
    aggregated = (
        pd.DataFrame({"bar": bar, "price_cell": price_cell, "signed": signed})
        .groupby(["bar", "price_cell"], sort=False, observed=True)["signed"]
        .sum()
        .abs()
        .to_numpy(dtype=np.int64, copy=False)
    )
    if not len(aggregated):
        return np.zeros(1, dtype=np.int64), 0
    return np.bincount(aggregated), int(len(aggregated))


def _nearest_rank_percentile_from_histogram(
    histogram: np.ndarray, percentile: float
) -> int:
    count = int(histogram.sum())
    if count <= 0:
        raise ValueError("cannot calculate percentile from an empty histogram")
    rank = max(1, int(math.ceil(float(percentile) * count)))
    return int(np.searchsorted(np.cumsum(histogram), rank, side="left"))


def _histogram_add(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    out = np.zeros(max(len(left), len(right)), dtype=np.int64)
    out[: len(left)] += left
    out[: len(right)] += right
    return out


def _histogram_subtract(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    out = left.copy()
    out[: len(right)] -= right
    if np.any(out < 0):
        raise AssertionError("rolling bar-delta histogram became negative")
    return out


if __name__ == "__main__":
    main()
