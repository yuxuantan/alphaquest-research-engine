"""Build causal rolling big-trade thresholds for adaptive Yush v02.

For every governed RTH session, this tool reproduces the strategy's declared
same-price, same-aggressor-side aggregation.  The threshold for a session is
the nearest-rank percentile of all non-zero aggregations observed in the
previous N completed eligible RTH sessions.  The current session is never
included.
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
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    BIG_TRADE_AGGREGATION_FIXED_CELL,
    BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
)


DEFAULT_DATASET_MANIFEST = Path(
    "research/datasets/" "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/" "dataset_manifest.json"
)
DEFAULT_OUTPUT = Path(
    "research/datasets/"
    "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02/"
    "big_trade_100ms_q995_prior20_context.parquet"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-manifest",
        type=Path,
        default=DEFAULT_DATASET_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lookback-sessions", type=int, default=20)
    parser.add_argument("--percentile", type=float, default=0.995)
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument(
        "--aggregation-mode",
        choices=(
            BIG_TRADE_AGGREGATION_FIXED_CELL,
            BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
        ),
        default=BIG_TRADE_AGGREGATION_FIXED_CELL,
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.lookback_sessions < 1:
        raise ValueError("lookback-sessions must be positive")
    if not 0.0 < args.percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    if args.tick_size <= 0:
        raise ValueError("tick-size must be positive")
    if args.workers < 1:
        raise ValueError("workers must be positive")

    manifest = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    event_source = manifest.get("event_source")
    if not isinstance(event_source, dict):
        raise ValueError("dataset manifest has no event_source mapping")
    execution = dict(event_source)
    execution["canonical_session_cache"] = False

    session_histograms: deque[np.ndarray] = deque()
    session_records: deque[dict[str, Any]] = deque()
    rolling_histogram = np.zeros(1, dtype=np.int64)
    rows: list[dict[str, Any]] = []
    processed = 0

    session_histogram_rows = _load_session_histograms(
        execution,
        tick_size=args.tick_size,
        interval_ms=100,
        aggregation_mode=args.aggregation_mode,
        workers=args.workers,
    )
    for session_date, contract_symbol, histogram, observation_count in session_histogram_rows:
        if observation_count <= 0:
            raise ValueError(f"session {session_date} has no non-zero A/B 100 ms aggregations")
        if len(session_histograms) == args.lookback_sessions:
            threshold = _nearest_rank_percentile_from_histogram(
                rolling_histogram,
                args.percentile,
            )
            first = session_records[0]
            last = session_records[-1]
            rows.append(
                {
                    "session_date": str(session_date),
                    "contract_symbol": contract_symbol,
                    "lookback_sessions": int(args.lookback_sessions),
                    "reference_percentile": float(args.percentile),
                    "percentile_method": "nearest_rank_higher",
                    "threshold_volume": int(threshold),
                    "reference_observation_count": int(rolling_histogram.sum()),
                    "reference_start_session": str(first["session_date"]),
                    "reference_end_session": str(last["session_date"]),
                    "reference_start_contract": str(first["contract_symbol"]),
                    "reference_end_contract": str(last["contract_symbol"]),
                    "aggregation_interval_ms": 100,
                    "aggregation_price_ticks": 1,
                    "aggregation_side_scope": "same_aggressor_side_A_or_B",
                    "aggregation_sequence_scope": args.aggregation_mode,
                }
            )

        rolling_histogram = _histogram_add(rolling_histogram, histogram)
        session_histograms.append(histogram)
        session_records.append(
            {
                "session_date": str(session_date),
                "contract_symbol": contract_symbol,
            }
        )
        if len(session_histograms) > args.lookback_sessions:
            rolling_histogram = _histogram_subtract(
                rolling_histogram,
                session_histograms.popleft(),
            )
            session_records.popleft()
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
    if output.empty:
        raise ValueError("big-trade context build produced no eligible rows")
    if output["session_date"].duplicated().any():
        raise ValueError("big-trade context contains duplicate session dates")
    output = output.sort_values("session_date", kind="mergesort").reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output, index=False)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "schema": "alphaquest.yush-big-trade-context/v1",
                "dataset_manifest": str(args.dataset_manifest),
                "output": str(args.output),
                "processed_sessions": processed,
                "rows": int(len(output)),
                "coverage_start": str(output["session_date"].min()),
                "coverage_end": str(output["session_date"].max()),
                "lookback_sessions": int(args.lookback_sessions),
                "percentile": float(args.percentile),
                "percentile_method": "nearest_rank_higher",
                "aggregation_mode": args.aggregation_mode,
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
    interval_ms: int,
    aggregation_mode: str,
    workers: int,
) -> list[tuple[str, str, np.ndarray, int]]:
    if workers == 1:
        return _session_histograms_for_bounds(
            execution,
            None,
            tick_size,
            interval_ms,
            aggregation_mode,
        )
    quality = pd.read_csv(Path(str(execution["quality_manifest"])))
    dates = pd.to_datetime(quality["session_date"], errors="raise")
    years = range(int(dates.dt.year.min()), int(dates.dt.year.max()) + 1)
    tasks = [
        (
            execution,
            {"start_date": f"{year}-01-01", "end_date": f"{year}-12-31"},
            tick_size,
            interval_ms,
            aggregation_mode,
        )
        for year in years
    ]
    rows: list[tuple[str, str, np.ndarray, int]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_session_histograms_for_bounds, *task): task[1]
            for task in tasks
        }
        for future in as_completed(futures):
            part = future.result()
            rows.extend(part)
            bounds = futures[future]
            print(
                json.dumps(
                    {
                        "histogram_range_complete": bounds,
                        "sessions": len(part),
                    },
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
    interval_ms: int,
    aggregation_mode: str,
) -> list[tuple[str, str, np.ndarray, int]]:
    rows: list[tuple[str, str, np.ndarray, int]] = []
    for session_date, events in iter_scid_record_execution_sessions(
        execution,
        date_bounds=date_bounds,
    ):
        histogram, observation_count = _session_volume_histogram(
            events,
            tick_size=tick_size,
            interval_ms=interval_ms,
            aggregation_mode=aggregation_mode,
        )
        rows.append(
            (
                str(session_date),
                str(events["contract_symbol"].iloc[0]),
                histogram,
                observation_count,
            )
        )
    return rows


def _session_volume_histogram(
    events: pd.DataFrame,
    *,
    tick_size: float,
    interval_ms: int,
    aggregation_mode: str = BIG_TRADE_AGGREGATION_FIXED_CELL,
) -> tuple[np.ndarray, int]:
    required = {"timestamp", "close", "volume", "side"}
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError("canonical event session is missing columns: " + ", ".join(missing))
    if aggregation_mode not in {
        BIG_TRADE_AGGREGATION_FIXED_CELL,
        BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE,
    }:
        raise ValueError(f"unsupported big-trade aggregation mode: {aggregation_mode!r}")
    side = events["side"].astype(str).to_numpy(copy=False)
    eligible = np.isin(side, ("A", "B"))
    if not np.any(eligible):
        return np.zeros(1, dtype=np.int64), 0
    timestamp_ns_all = pd.to_datetime(events["timestamp"], utc=True).astype("int64").to_numpy(
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
    price_tick_all = np.rint(
        events["close"].to_numpy(dtype=float, copy=False) / tick_size
    ).astype(np.int64)
    volume_all = events["volume"].to_numpy(dtype=np.int64, copy=False)
    if aggregation_mode == BIG_TRADE_AGGREGATION_MOTIVEWAVE_CONSECUTIVE:
        aggregated = _motivewave_consecutive_sizes(
            timestamp_ns_all,
            price_tick_all,
            side,
            volume_all,
            interval_ns=int(interval_ms) * 1_000_000,
        )
        if not len(aggregated):
            return np.zeros(1, dtype=np.int64), 0
        return np.bincount(aggregated), int(len(aggregated))
    timestamp_ns = timestamp_ns_all[eligible]
    bucket = np.floor_divide(timestamp_ns - open_ns, int(interval_ms) * 1_000_000)
    price_tick = price_tick_all[eligible]
    volume = volume_all[eligible]
    frame = pd.DataFrame(
        {
            "bucket": bucket,
            "price_tick": price_tick,
            "side": side[eligible],
            "volume": volume,
        }
    )
    aggregated = (
        frame.groupby(
            ["bucket", "price_tick", "side"],
            sort=False,
            observed=True,
        )["volume"]
        .sum()
        .to_numpy(dtype=np.int64, copy=False)
    )
    aggregated = aggregated[aggregated > 0]
    if not len(aggregated):
        return np.zeros(1, dtype=np.int64), 0
    return np.bincount(aggregated), int(len(aggregated))


def _motivewave_consecutive_sizes(
    timestamp_ns: np.ndarray,
    price_tick: np.ndarray,
    side: np.ndarray,
    volume: np.ndarray,
    *,
    interval_ns: int,
) -> np.ndarray:
    """Return consecutive same-price/side sequence sizes with a rolling time cap."""

    if interval_ns <= 0:
        raise ValueError("MotiveWave aggregation interval must be positive")
    count = len(timestamp_ns)
    if not (count == len(price_tick) == len(side) == len(volume)):
        raise ValueError("MotiveWave aggregation arrays must have equal length")
    if count == 0:
        return np.array([], dtype=np.int64)
    if np.any(np.diff(timestamp_ns) < 0):
        raise ValueError("MotiveWave aggregation timestamps must be monotonic")
    eligible = np.isin(side, ("A", "B"))
    matching_previous = np.zeros(count, dtype=bool)
    matching_previous[1:] = (
        eligible[1:]
        & eligible[:-1]
        & (side[1:] == side[:-1])
        & (price_tick[1:] == price_tick[:-1])
    )
    run_starts = np.flatnonzero(~matching_previous)
    run_ends = np.append(run_starts[1:], count)
    prefix = np.concatenate(([0], np.cumsum(volume, dtype=np.int64)))
    sizes: list[int] = []
    for start, end in zip(run_starts, run_ends, strict=True):
        if not eligible[start]:
            continue
        cursor = int(start)
        while cursor < int(end):
            boundary = int(
                np.searchsorted(
                    timestamp_ns,
                    timestamp_ns[cursor] + interval_ns,
                    side="right",
                )
            )
            boundary = min(boundary, int(end))
            sizes.append(int(prefix[boundary] - prefix[cursor]))
            cursor = boundary
    return np.asarray(sizes, dtype=np.int64)


def _nearest_rank_percentile_from_histogram(
    histogram: np.ndarray,
    percentile: float,
) -> int:
    count = int(histogram.sum())
    if count <= 0:
        raise ValueError("cannot calculate percentile from an empty histogram")
    rank = max(1, int(math.ceil(float(percentile) * count)))
    return int(np.searchsorted(np.cumsum(histogram), rank, side="left"))


def _histogram_add(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    size = max(len(left), len(right))
    out = np.zeros(size, dtype=np.int64)
    out[: len(left)] += left
    out[: len(right)] += right
    return out


def _histogram_subtract(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    out = left.copy()
    out[: len(right)] -= right
    if np.any(out < 0):
        raise AssertionError("rolling big-trade histogram became negative")
    return out


if __name__ == "__main__":
    main()
