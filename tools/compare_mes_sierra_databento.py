from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


NS_PER_MS = 1_000_000
NS_PER_MINUTE = 60_000_000_000
PRICE_SCALE = 1_000_000_000
TICK_SIZE = 0.25


SIERRA_COLUMNS = [
    "Date",
    "Time",
    "Open",
    "High",
    "Low",
    "Last",
    "Volume",
    "NumberOfTrades",
    "BidVolume",
    "AskVolume",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Sierra Chart MESM6 trade export with Databento MES.FUT trades."
    )
    parser.add_argument(
        "--sierra",
        default="data/raw/MES-comparison/sierrachart-mes-trades/MESM26-CME.txt",
    )
    parser.add_argument(
        "--databento-dir",
        default="data/raw/MES-comparison/databento-mes-trades",
    )
    parser.add_argument("--contract", default="MESM6")
    parser.add_argument("--sierra-timezone", default="Asia/Singapore")
    parser.add_argument(
        "--out",
        default="data/reports/MES-comparison/sierra_vs_databento_trades",
    )
    parser.add_argument("--sierra-chunksize", type=int, default=1_000_000)
    parser.add_argument("--dbn-chunksize", type=int, default=2_000_000)
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Reuse existing minute aggregate CSVs in --out and rebuild comparison reports.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.compare_only:
        print("Loading existing minute aggregates...", flush=True)
        sierra_minute = read_minute_frame(out_dir / "sierra_minute_utc.csv")
        db_event_minute = read_minute_frame(out_dir / "databento_event_minute_utc.csv")
        db_recv_minute = read_minute_frame(out_dir / "databento_recv_minute_utc.csv")
        sierra_stats = aggregate_frame_stats(
            sierra_minute,
            timezone=args.sierra_timezone,
            source_rows_label="row_count",
        )
        db_stats = aggregate_frame_stats(
            db_event_minute,
            timezone=args.sierra_timezone,
            source_rows_label="contract_rows",
        )
        sierra_stats["from_existing_minute_aggregates"] = True
        db_stats["from_existing_minute_aggregates"] = True
    else:
        print("Aggregating Sierra text export...", flush=True)
        sierra_minute, sierra_stats = aggregate_sierra(
            Path(args.sierra),
            timezone=args.sierra_timezone,
            chunksize=args.sierra_chunksize,
            out_dir=out_dir,
        )
        write_minute_frame(sierra_minute, out_dir / "sierra_minute_utc.csv", args.sierra_timezone)

        print("Streaming Databento DBN trades...", flush=True)
        db_event_minute, db_recv_minute, db_stats = aggregate_databento(
            Path(args.databento_dir),
            contract=args.contract,
            chunksize=args.dbn_chunksize,
        )
        write_minute_frame(
            db_event_minute,
            out_dir / "databento_event_minute_utc.csv",
            args.sierra_timezone,
        )
        write_minute_frame(
            db_recv_minute,
            out_dir / "databento_recv_minute_utc.csv",
            args.sierra_timezone,
        )

    print("Building comparisons...", flush=True)
    event_summary = compare_minute_sources(
        sierra_minute,
        db_event_minute,
        out_dir,
        label="event",
        timezone=args.sierra_timezone,
    )
    recv_summary = compare_minute_sources(
        sierra_minute,
        db_recv_minute,
        out_dir,
        label="recv",
        timezone=args.sierra_timezone,
    )

    source_summary = pd.DataFrame(
        [
            flatten_source_summary("sierra", sierra_stats),
            flatten_source_summary("databento_mesm6", db_stats),
        ]
    )
    source_summary.to_csv(out_dir / "source_summary.csv", index=False)

    summary: dict[str, Any] = {
        "contract": args.contract,
        "sierra_path": str(args.sierra),
        "databento_dir": str(args.databento_dir),
        "sierra_timezone_assumption": args.sierra_timezone,
        "sierra": json_ready(sierra_stats),
        "databento": json_ready(db_stats),
        "minute_comparison_ts_event": json_ready(event_summary),
        "minute_comparison_ts_recv": json_ready(recv_summary),
        "report_files": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    write_json(out_dir / "summary.json", summary)
    print(f"Wrote comparison report to {out_dir}", flush=True)


def aggregate_sierra(
    path: Path,
    timezone: str,
    chunksize: int,
    out_dir: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    minute_parts: list[pd.DataFrame] = []
    wide_row_parts: list[pd.DataFrame] = []
    duplicate_row_parts: list[pd.DataFrame] = []

    stats: dict[str, Any] = {
        "row_count": 0,
        "parse_error_rows": 0,
        "total_volume": 0,
        "total_number_of_trades": 0,
        "total_bid_volume": 0,
        "total_ask_volume": 0,
        "rows_bid_plus_ask_ne_volume": 0,
        "volume_bid_plus_ask_minus_volume": 0,
        "invalid_ohlc_rows": 0,
        "tick_violation_rows": 0,
        "rows_where_high_low_exceeds_1_point": 0,
        "rows_where_high_low_exceeds_4_points": 0,
        "rows_where_high_low_exceeds_10_points": 0,
        "consecutive_exact_duplicate_rows": 0,
        "consecutive_same_timestamp_rows": 0,
        "timestamp_backwards_rows": 0,
        "min_timestamp_ns": None,
        "max_timestamp_ns": None,
    }
    previous_timestamp_ns: int | None = None
    previous_key: tuple[Any, ...] | None = None

    reader = pd.read_csv(
        path,
        chunksize=chunksize,
        skipinitialspace=True,
        dtype={
            "Date": "string",
            "Time": "string",
            "Open": "float64",
            "High": "float64",
            "Low": "float64",
            "Last": "float64",
            "Volume": "int64",
            "NumberOfTrades": "int64",
            "BidVolume": "int64",
            "AskVolume": "int64",
        },
    )

    for chunk_idx, raw in enumerate(reader, start=1):
        raw.columns = [col.strip() for col in raw.columns]
        missing = set(SIERRA_COLUMNS) - set(raw.columns)
        if missing:
            raise ValueError(f"Sierra file missing columns: {sorted(missing)}")

        raw["_line_number"] = np.arange(
            stats["row_count"] + 2,
            stats["row_count"] + len(raw) + 2,
            dtype=np.int64,
        )
        stats["row_count"] += int(len(raw))

        ts_text = raw["Date"].str.strip() + " " + raw["Time"].str.strip()
        timestamp_local = parse_sierra_timestamps(ts_text)
        parse_ok = timestamp_local.notna()
        stats["parse_error_rows"] += int((~parse_ok).sum())
        if not parse_ok.all():
            raw = raw.loc[parse_ok].copy()
            timestamp_local = timestamp_local.loc[parse_ok]

        timestamp_utc = timestamp_local.dt.tz_localize(timezone).dt.tz_convert("UTC")
        timestamp_ns = timestamp_utc.astype("int64")
        minute_ns = (timestamp_ns // NS_PER_MINUTE) * NS_PER_MINUTE

        open_px = raw["Open"].to_numpy(dtype=float)
        high_px = raw["High"].to_numpy(dtype=float)
        low_px = raw["Low"].to_numpy(dtype=float)
        close_px = raw["Last"].to_numpy(dtype=float)
        volume = raw["Volume"].to_numpy(dtype=np.int64)
        trades = raw["NumberOfTrades"].to_numpy(dtype=np.int64)
        bid_volume = raw["BidVolume"].to_numpy(dtype=np.int64)
        ask_volume = raw["AskVolume"].to_numpy(dtype=np.int64)

        stats["total_volume"] += int(volume.sum())
        stats["total_number_of_trades"] += int(trades.sum())
        stats["total_bid_volume"] += int(bid_volume.sum())
        stats["total_ask_volume"] += int(ask_volume.sum())
        side_delta = bid_volume + ask_volume - volume
        stats["rows_bid_plus_ask_ne_volume"] += int(np.count_nonzero(side_delta))
        stats["volume_bid_plus_ask_minus_volume"] += int(side_delta.sum())

        invalid_ohlc = (high_px < np.maximum(open_px, close_px)) | (
            low_px > np.minimum(open_px, close_px)
        )
        stats["invalid_ohlc_rows"] += int(np.count_nonzero(invalid_ohlc))

        prices = np.column_stack([open_px, high_px, low_px, close_px])
        tick_violations = np.abs((prices / TICK_SIZE).round() - (prices / TICK_SIZE)) > 1e-9
        stats["tick_violation_rows"] += int(np.count_nonzero(tick_violations.any(axis=1)))

        row_range = high_px - low_px
        stats["rows_where_high_low_exceeds_1_point"] += int(np.count_nonzero(row_range > 1.0))
        stats["rows_where_high_low_exceeds_4_points"] += int(np.count_nonzero(row_range > 4.0))
        stats["rows_where_high_low_exceeds_10_points"] += int(np.count_nonzero(row_range > 10.0))

        if len(timestamp_ns):
            ts_min = int(timestamp_ns.min())
            ts_max = int(timestamp_ns.max())
            stats["min_timestamp_ns"] = min_optional(stats["min_timestamp_ns"], ts_min)
            stats["max_timestamp_ns"] = max_optional(stats["max_timestamp_ns"], ts_max)

            ts_values = timestamp_ns.to_numpy(dtype=np.int64)
            stats["timestamp_backwards_rows"] += int(np.count_nonzero(np.diff(ts_values) < 0))
            stats["consecutive_same_timestamp_rows"] += int(np.count_nonzero(np.diff(ts_values) == 0))
            if previous_timestamp_ns is not None:
                if ts_values[0] < previous_timestamp_ns:
                    stats["timestamp_backwards_rows"] += 1
                if ts_values[0] == previous_timestamp_ns:
                    stats["consecutive_same_timestamp_rows"] += 1
            previous_timestamp_ns = int(ts_values[-1])

            key_frame = pd.DataFrame(
                {
                    "timestamp_ns": ts_values,
                    "open": open_px,
                    "high": high_px,
                    "low": low_px,
                    "close": close_px,
                    "volume": volume,
                    "trades": trades,
                    "bid_volume": bid_volume,
                    "ask_volume": ask_volume,
                }
            )
            duplicate_mask = key_frame.eq(key_frame.shift()).all(axis=1)
            if previous_key is not None:
                first_key = tuple(key_frame.iloc[0].tolist())
                if first_key == previous_key:
                    duplicate_mask.iloc[0] = True
            duplicate_count = int(duplicate_mask.sum())
            stats["consecutive_exact_duplicate_rows"] += duplicate_count
            if duplicate_count and len(duplicate_row_parts) < 10:
                duplicate_row_parts.append(
                    raw.loc[duplicate_mask.to_numpy()]
                    .head(25)
                    .assign(timestamp_utc=timestamp_utc.loc[duplicate_mask.to_numpy()].astype(str))
                )
            previous_key = tuple(key_frame.iloc[-1].tolist())

        minute_source = pd.DataFrame(
            {
                "minute_ns": minute_ns.to_numpy(dtype=np.int64),
                "open": open_px,
                "high": high_px,
                "low": low_px,
                "close": close_px,
                "volume": volume,
                "trade_count": trades,
                "bid_volume": bid_volume,
                "ask_volume": ask_volume,
                "source_rows": np.ones(len(raw), dtype=np.int64),
            }
        )
        minute_parts.append(partial_ohlcv_aggregate(minute_source, "minute_ns"))

        wide_rows = raw.assign(
            timestamp_utc=timestamp_utc.astype(str),
            high_low_range=row_range,
        ).nlargest(50, "high_low_range")
        wide_row_parts.append(wide_rows)

        if chunk_idx == 1 or chunk_idx % 10 == 0:
            print(
                f"  Sierra chunks {chunk_idx:,}: {stats['row_count']:,} rows",
                flush=True,
            )

    if wide_row_parts:
        pd.concat(wide_row_parts, ignore_index=True).nlargest(200, "high_low_range").to_csv(
            out_dir / "sierra_widest_rows_sample.csv",
            index=False,
        )
    if duplicate_row_parts:
        pd.concat(duplicate_row_parts, ignore_index=True).to_csv(
            out_dir / "sierra_consecutive_duplicate_rows_sample.csv",
            index=False,
        )

    minute = combine_ohlcv_partials(minute_parts, "minute_ns")
    stats["minute_rows"] = int(len(minute))
    add_timestamp_strings(stats, timezone)
    return minute, stats


def aggregate_databento(
    dbn_dir: Path,
    contract: str,
    chunksize: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    import databento as db

    event_parts: list[pd.DataFrame] = []
    recv_parts: list[pd.DataFrame] = []
    stats: dict[str, Any] = {
        "dbn_files": 0,
        "parent_query_rows": 0,
        "contract_rows": 0,
        "contract_volume": 0,
        "side_a_rows": 0,
        "side_b_rows": 0,
        "side_other_rows": 0,
        "side_a_volume": 0,
        "side_b_volume": 0,
        "side_other_volume": 0,
        "tick_violation_rows": 0,
        "action_counts": {},
        "contract_instrument_ids": [],
        "raw_symbols_in_metadata": [],
        "min_ts_event_ns": None,
        "max_ts_event_ns": None,
        "min_ts_recv_ns": None,
        "max_ts_recv_ns": None,
    }

    for path in sorted(dbn_dir.glob("*.dbn.zst")) + sorted(dbn_dir.glob("*.dbn")):
        store = db.DBNStore.from_file(path)
        mappings = store.metadata.mappings
        stats["raw_symbols_in_metadata"] = sorted(
            set(stats["raw_symbols_in_metadata"]) | set(mappings.keys())
        )
        intervals = mappings.get(contract)
        if not intervals:
            print(f"  Databento {path.name}: no {contract} mapping, skipped", flush=True)
            continue
        instrument_ids = sorted({int(interval["symbol"]) for interval in intervals})
        stats["contract_instrument_ids"] = sorted(
            set(stats["contract_instrument_ids"]) | set(instrument_ids)
        )
        instrument_id_array = np.asarray(instrument_ids, dtype=np.uint32)

        stats["dbn_files"] += 1
        file_parent_rows = 0
        file_contract_rows = 0
        for chunk_idx, records in enumerate(store.to_ndarray(count=chunksize), start=1):
            file_parent_rows += int(len(records))
            stats["parent_query_rows"] += int(len(records))
            if not len(records):
                continue

            actions, counts = np.unique(records["action"], return_counts=True)
            for action, count in zip(actions, counts):
                key = action.decode("ascii", errors="ignore")
                stats["action_counts"][key] = int(stats["action_counts"].get(key, 0)) + int(count)

            mask = np.isin(records["instrument_id"], instrument_id_array)
            if "action" in records.dtype.names:
                mask &= records["action"] == b"T"
            filtered = records[mask]
            if not len(filtered):
                continue

            file_contract_rows += int(len(filtered))
            stats["contract_rows"] += int(len(filtered))
            size = filtered["size"].astype(np.int64)
            price = filtered["price"].astype(np.float64) / PRICE_SCALE
            side = filtered["side"]
            side_a = side == b"A"
            side_b = side == b"B"
            side_other = ~(side_a | side_b)

            stats["contract_volume"] += int(size.sum())
            stats["side_a_rows"] += int(np.count_nonzero(side_a))
            stats["side_b_rows"] += int(np.count_nonzero(side_b))
            stats["side_other_rows"] += int(np.count_nonzero(side_other))
            stats["side_a_volume"] += int(size[side_a].sum())
            stats["side_b_volume"] += int(size[side_b].sum())
            stats["side_other_volume"] += int(size[side_other].sum())

            tick_violations = np.abs((price / TICK_SIZE).round() - (price / TICK_SIZE)) > 1e-9
            stats["tick_violation_rows"] += int(np.count_nonzero(tick_violations))

            ts_event = filtered["ts_event"].astype(np.int64)
            ts_recv = filtered["ts_recv"].astype(np.int64)
            stats["min_ts_event_ns"] = min_optional(stats["min_ts_event_ns"], int(ts_event.min()))
            stats["max_ts_event_ns"] = max_optional(stats["max_ts_event_ns"], int(ts_event.max()))
            stats["min_ts_recv_ns"] = min_optional(stats["min_ts_recv_ns"], int(ts_recv.min()))
            stats["max_ts_recv_ns"] = max_optional(stats["max_ts_recv_ns"], int(ts_recv.max()))

            event_parts.append(dbn_partial_aggregate(ts_event, price, size, side, "minute_ns"))
            recv_parts.append(dbn_partial_aggregate(ts_recv, price, size, side, "minute_ns"))

        print(
            f"  Databento {path.name}: {file_contract_rows:,} {contract} trades "
            f"from {file_parent_rows:,} parent rows",
            flush=True,
        )

    event_minute = combine_ohlcv_partials(event_parts, "minute_ns")
    recv_minute = combine_ohlcv_partials(recv_parts, "minute_ns")
    stats["event_minute_rows"] = int(len(event_minute))
    stats["recv_minute_rows"] = int(len(recv_minute))
    add_databento_timestamp_strings(stats)
    return event_minute, recv_minute, stats


def parse_sierra_timestamps(ts_text: pd.Series) -> pd.Series:
    timestamp_local = pd.to_datetime(
        ts_text,
        format="%Y/%m/%d %H:%M:%S.%f",
        errors="coerce",
    )
    missing = timestamp_local.isna()
    if missing.any():
        timestamp_local.loc[missing] = pd.to_datetime(
            ts_text.loc[missing],
            format="%Y/%m/%d %H:%M:%S",
            errors="coerce",
        )
    return timestamp_local


def partial_ohlcv_aggregate(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
    grouped = df.groupby(key_col, sort=True, as_index=False).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        trade_count=("trade_count", "sum"),
        bid_volume=("bid_volume", "sum"),
        ask_volume=("ask_volume", "sum"),
        source_rows=("source_rows", "sum"),
    )
    return grouped


def dbn_partial_aggregate(
    timestamp_ns: np.ndarray,
    price: np.ndarray,
    size: np.ndarray,
    side: np.ndarray,
    key_col: str,
) -> pd.DataFrame:
    minute_ns = (timestamp_ns // NS_PER_MINUTE) * NS_PER_MINUTE
    side_a = side == b"A"
    side_b = side == b"B"
    df = pd.DataFrame(
        {
            key_col: minute_ns.astype(np.int64),
            "timestamp_ns": timestamp_ns.astype(np.int64),
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": size,
            "trade_count": np.ones(len(size), dtype=np.int64),
            "bid_volume": np.zeros(len(size), dtype=np.int64),
            "ask_volume": np.zeros(len(size), dtype=np.int64),
            "side_a_volume": np.where(side_a, size, 0),
            "side_b_volume": np.where(side_b, size, 0),
            "side_other_volume": np.where(~(side_a | side_b), size, 0),
            "source_rows": np.ones(len(size), dtype=np.int64),
        }
    )
    df = df.sort_values([key_col, "timestamp_ns"], kind="mergesort")
    grouped = df.groupby(key_col, sort=True, as_index=False).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        trade_count=("trade_count", "sum"),
        bid_volume=("bid_volume", "sum"),
        ask_volume=("ask_volume", "sum"),
        side_a_volume=("side_a_volume", "sum"),
        side_b_volume=("side_b_volume", "sum"),
        side_other_volume=("side_other_volume", "sum"),
        source_rows=("source_rows", "sum"),
    )
    return grouped


def combine_ohlcv_partials(parts: list[pd.DataFrame], key_col: str) -> pd.DataFrame:
    if not parts:
        return pd.DataFrame(
            columns=[
                key_col,
                "open",
                "high",
                "low",
                "close",
                "volume",
                "trade_count",
                "bid_volume",
                "ask_volume",
                "source_rows",
            ]
        )
    combined = pd.concat(parts, ignore_index=True)
    aggregations: dict[str, tuple[str, str]] = {
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
        "volume": ("volume", "sum"),
        "trade_count": ("trade_count", "sum"),
        "bid_volume": ("bid_volume", "sum"),
        "ask_volume": ("ask_volume", "sum"),
        "source_rows": ("source_rows", "sum"),
    }
    for optional in ["side_a_volume", "side_b_volume", "side_other_volume"]:
        if optional in combined.columns:
            aggregations[optional] = (optional, "sum")
    return combined.groupby(key_col, sort=True, as_index=False).agg(**aggregations)


def compare_minute_sources(
    sierra: pd.DataFrame,
    databento: pd.DataFrame,
    out_dir: Path,
    label: str,
    timezone: str,
) -> dict[str, Any]:
    sierra = sierra.copy()
    databento = databento.copy()
    if sierra.empty or databento.empty:
        return {"empty": True}

    start_ns = max(int(sierra["minute_ns"].min()), int(databento["minute_ns"].min()))
    end_ns = min(int(sierra["minute_ns"].max()), int(databento["minute_ns"].max()))
    sierra = sierra[(sierra["minute_ns"] >= start_ns) & (sierra["minute_ns"] <= end_ns)]
    databento = databento[
        (databento["minute_ns"] >= start_ns) & (databento["minute_ns"] <= end_ns)
    ]

    merged = sierra.merge(
        databento,
        on="minute_ns",
        how="outer",
        indicator=True,
        suffixes=("_sierra", "_databento"),
    )
    merged = normalize_databento_side_columns(merged)
    both = merged[merged["_merge"] == "both"].copy()

    side_mapping = side_mapping_summary(both)
    selected = side_mapping.iloc[0].to_dict() if len(side_mapping) else {}
    if selected.get("mapping") == "databento_B_to_sierra_ask__databento_A_to_sierra_bid":
        both["ask_volume_databento_mapped"] = both["side_b_volume_databento"]
        both["bid_volume_databento_mapped"] = both["side_a_volume_databento"]
    else:
        both["ask_volume_databento_mapped"] = both["side_a_volume_databento"]
        both["bid_volume_databento_mapped"] = both["side_b_volume_databento"]

    for col in ["open", "high", "low", "close"]:
        both[f"{col}_diff"] = both[f"{col}_databento"] - both[f"{col}_sierra"]
        both[f"{col}_abs_diff"] = both[f"{col}_diff"].abs()
    both["volume_diff"] = both["volume_databento"] - both["volume_sierra"]
    both["abs_volume_diff"] = both["volume_diff"].abs()
    both["trade_count_diff"] = both["trade_count_databento"] - both["trade_count_sierra"]
    both["ask_volume_diff"] = both["ask_volume_databento_mapped"] - both["ask_volume_sierra"]
    both["bid_volume_diff"] = both["bid_volume_databento_mapped"] - both["bid_volume_sierra"]
    both["abs_side_volume_diff"] = both["ask_volume_diff"].abs() + both["bid_volume_diff"].abs()
    both["any_price_mismatch"] = (
        both[["open_abs_diff", "high_abs_diff", "low_abs_diff", "close_abs_diff"]] > 0
    ).any(axis=1)
    both["volume_mismatch"] = both["volume_diff"] != 0
    both["side_volume_mismatch"] = both["abs_side_volume_diff"] != 0

    comparison_out = add_time_columns(both, timezone)
    comparison_out.to_csv(out_dir / f"minute_comparison_{label}.csv", index=False)
    side_mapping.to_csv(out_dir / f"side_mapping_summary_{label}.csv", index=False)

    mismatch_sample = comparison_out[
        comparison_out["any_price_mismatch"]
        | comparison_out["volume_mismatch"]
        | comparison_out["side_volume_mismatch"]
    ].copy()
    mismatch_sample["max_price_abs_diff"] = mismatch_sample[
        ["open_abs_diff", "high_abs_diff", "low_abs_diff", "close_abs_diff"]
    ].max(axis=1)
    mismatch_sample.sort_values(
        ["abs_volume_diff", "abs_side_volume_diff", "max_price_abs_diff"],
        ascending=[False, False, False],
    ).head(5000).to_csv(out_dir / f"minute_mismatch_sample_{label}.csv", index=False)

    daily = daily_comparison(sierra, databento, selected.get("mapping"), timezone)
    daily.to_csv(out_dir / f"daily_comparison_{label}.csv", index=False)

    source_only = add_time_columns(
        merged[merged["_merge"] != "both"].copy(),
        timezone,
    )
    source_only.head(10000).to_csv(out_dir / f"source_only_minutes_sample_{label}.csv", index=False)

    summary = {
        "overlap_start_utc": ns_to_iso(start_ns),
        "overlap_end_utc": ns_to_iso(end_ns),
        "sierra_minutes_in_overlap": int(len(sierra)),
        "databento_minutes_in_overlap": int(len(databento)),
        "matched_minutes": int(len(both)),
        "minutes_only_in_sierra": int((merged["_merge"] == "left_only").sum()),
        "minutes_only_in_databento": int((merged["_merge"] == "right_only").sum()),
        "price_mismatch_minutes": int(both["any_price_mismatch"].sum()) if len(both) else 0,
        "volume_mismatch_minutes": int(both["volume_mismatch"].sum()) if len(both) else 0,
        "side_volume_mismatch_minutes": int(both["side_volume_mismatch"].sum()) if len(both) else 0,
        "total_sierra_volume_overlap": int(sierra["volume"].sum()),
        "total_databento_volume_overlap": int(databento["volume"].sum()),
        "total_volume_diff_databento_minus_sierra": int(databento["volume"].sum() - sierra["volume"].sum()),
        "total_abs_volume_diff_matched_minutes": int(both["abs_volume_diff"].sum()) if len(both) else 0,
        "selected_side_mapping": selected,
    }
    if len(both):
        summary.update(
            {
                "price_mismatch_rate_matched_minutes": float(both["any_price_mismatch"].mean()),
                "volume_mismatch_rate_matched_minutes": float(both["volume_mismatch"].mean()),
                "side_volume_mismatch_rate_matched_minutes": float(
                    both["side_volume_mismatch"].mean()
                ),
                "max_abs_open_diff": float(both["open_abs_diff"].max()),
                "max_abs_high_diff": float(both["high_abs_diff"].max()),
                "max_abs_low_diff": float(both["low_abs_diff"].max()),
                "max_abs_close_diff": float(both["close_abs_diff"].max()),
                "max_abs_volume_diff": int(both["abs_volume_diff"].max()),
            }
        )
    return summary


def side_mapping_summary(both: pd.DataFrame) -> pd.DataFrame:
    if both.empty:
        return pd.DataFrame()
    candidates = [
        (
            "databento_B_to_sierra_ask__databento_A_to_sierra_bid",
            "side_b_volume_databento",
            "side_a_volume_databento",
        ),
        (
            "databento_A_to_sierra_ask__databento_B_to_sierra_bid",
            "side_a_volume_databento",
            "side_b_volume_databento",
        ),
    ]
    rows = []
    for label, db_ask_col, db_bid_col in candidates:
        ask_diff = both[db_ask_col] - both["ask_volume_sierra"]
        bid_diff = both[db_bid_col] - both["bid_volume_sierra"]
        rows.append(
            {
                "mapping": label,
                "total_abs_side_volume_diff": int(ask_diff.abs().sum() + bid_diff.abs().sum()),
                "exact_side_match_minutes": int(((ask_diff == 0) & (bid_diff == 0)).sum()),
                "matched_minutes": int(len(both)),
                "ask_abs_diff": int(ask_diff.abs().sum()),
                "bid_abs_diff": int(bid_diff.abs().sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["total_abs_side_volume_diff", "exact_side_match_minutes"],
        ascending=[True, False],
    )


def daily_comparison(
    sierra: pd.DataFrame,
    databento: pd.DataFrame,
    selected_mapping: str | None,
    timezone: str,
) -> pd.DataFrame:
    sierra_daily = daily_from_minute(sierra, timezone)
    db_daily = daily_from_minute(databento, timezone)
    merged = sierra_daily.merge(
        db_daily,
        on="date_local",
        how="outer",
        indicator=True,
        suffixes=("_sierra", "_databento"),
    )
    merged = normalize_databento_side_columns(merged)
    if selected_mapping == "databento_B_to_sierra_ask__databento_A_to_sierra_bid":
        merged["ask_volume_databento_mapped"] = merged["side_b_volume_databento"]
        merged["bid_volume_databento_mapped"] = merged["side_a_volume_databento"]
    else:
        merged["ask_volume_databento_mapped"] = merged["side_a_volume_databento"]
        merged["bid_volume_databento_mapped"] = merged["side_b_volume_databento"]

    for col in ["volume", "trade_count", "ask_volume", "bid_volume"]:
        left = f"{col}_sierra"
        if col == "ask_volume":
            right_series = merged["ask_volume_databento_mapped"]
        elif col == "bid_volume":
            right_series = merged["bid_volume_databento_mapped"]
        else:
            right_series = merged[f"{col}_databento"]
        merged[f"{col}_diff"] = right_series.fillna(0) - merged[left].fillna(0)
    return merged


def normalize_databento_side_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["side_a_volume", "side_b_volume", "side_other_volume"]:
        suffixed = f"{col}_databento"
        if suffixed not in out.columns and col in out.columns:
            out[suffixed] = out[col]
    return out


def daily_from_minute(df: pd.DataFrame, timezone: str) -> pd.DataFrame:
    out = df.copy()
    out["date_local"] = pd.to_datetime(out["minute_ns"], unit="ns", utc=True).dt.tz_convert(
        timezone
    ).dt.date.astype(str)
    aggregations: dict[str, tuple[str, str]] = {
        "volume": ("volume", "sum"),
        "trade_count": ("trade_count", "sum"),
        "bid_volume": ("bid_volume", "sum"),
        "ask_volume": ("ask_volume", "sum"),
        "minutes": ("minute_ns", "size"),
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
    }
    for optional in ["side_a_volume", "side_b_volume", "side_other_volume"]:
        if optional in out.columns:
            aggregations[optional] = (optional, "sum")
    return out.groupby("date_local", as_index=False, sort=True).agg(**aggregations)


def add_time_columns(df: pd.DataFrame, timezone: str) -> pd.DataFrame:
    if df.empty or "minute_ns" not in df.columns:
        return df
    out = df.copy()
    ts = pd.to_datetime(out["minute_ns"], unit="ns", utc=True)
    out.insert(1, "timestamp_utc", ts.astype(str))
    out.insert(2, "timestamp_local", ts.dt.tz_convert(timezone).astype(str))
    return out


def write_minute_frame(df: pd.DataFrame, path: Path, timezone: str) -> None:
    add_time_columns(df, timezone).to_csv(path, index=False)


def read_minute_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df.drop(columns=[col for col in ["timestamp_utc", "timestamp_local"] if col in df.columns])


def aggregate_frame_stats(
    df: pd.DataFrame,
    timezone: str,
    source_rows_label: str,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "minute_rows": int(len(df)),
        "total_volume": int(df["volume"].sum()) if "volume" in df else 0,
        "total_trade_count": int(df["trade_count"].sum()) if "trade_count" in df else 0,
        "total_bid_volume": int(df["bid_volume"].sum()) if "bid_volume" in df else 0,
        "total_ask_volume": int(df["ask_volume"].sum()) if "ask_volume" in df else 0,
    }
    if "source_rows" in df:
        stats[source_rows_label] = int(df["source_rows"].sum())
    for col in ["side_a_volume", "side_b_volume", "side_other_volume"]:
        if col in df:
            stats[f"total_{col}"] = int(df[col].sum())
    if len(df):
        stats["min_timestamp_ns"] = int(df["minute_ns"].min())
        stats["max_timestamp_ns"] = int(df["minute_ns"].max())
        add_timestamp_strings(stats, timezone)
    return stats


def flatten_source_summary(source: str, stats: dict[str, Any]) -> dict[str, Any]:
    row = {"source": source}
    for key, value in stats.items():
        if isinstance(value, (list, dict)):
            row[key] = json.dumps(json_ready(value), sort_keys=True)
        else:
            row[key] = value
    return row


def min_optional(current: int | None, value: int) -> int:
    return value if current is None else min(current, value)


def max_optional(current: int | None, value: int) -> int:
    return value if current is None else max(current, value)


def add_timestamp_strings(stats: dict[str, Any], timezone: str) -> None:
    if stats.get("min_timestamp_ns") is not None:
        ts = pd.Timestamp(stats["min_timestamp_ns"], unit="ns", tz="UTC")
        stats["first_timestamp_utc"] = ts.isoformat()
        stats["first_timestamp_local"] = ts.tz_convert(timezone).isoformat()
    if stats.get("max_timestamp_ns") is not None:
        ts = pd.Timestamp(stats["max_timestamp_ns"], unit="ns", tz="UTC")
        stats["last_timestamp_utc"] = ts.isoformat()
        stats["last_timestamp_local"] = ts.tz_convert(timezone).isoformat()


def add_databento_timestamp_strings(stats: dict[str, Any]) -> None:
    for prefix in ["ts_event", "ts_recv"]:
        min_key = f"min_{prefix}_ns"
        max_key = f"max_{prefix}_ns"
        if stats.get(min_key) is not None:
            stats[f"first_{prefix}_utc"] = ns_to_iso(stats[min_key])
        if stats.get(max_key) is not None:
            stats[f"last_{prefix}_utc"] = ns_to_iso(stats[max_key])


def ns_to_iso(value: int) -> str:
    return pd.Timestamp(int(value), unit="ns", tz="UTC").isoformat()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
