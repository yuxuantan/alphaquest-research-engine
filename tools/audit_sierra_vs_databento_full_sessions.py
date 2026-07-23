from __future__ import annotations

import argparse
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any
import zipfile

import databento as db
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from alphaquest.data.sierra_events import reconstruct_sierra_trade_events


ET = "America/New_York"
SCID_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)
SCID_COLUMNS = [
    "scid_datetime_us",
    "open",
    "close",
    "volume",
    "bid_volume",
    "ask_volume",
]
SEGMENTS = {
    "ETH": ("previous_session_date", "16:00:00", "session_date", "09:30:00"),
    "RTH": ("session_date", "09:30:00", "session_date", "16:00:00"),
}
BIG_TRADE_THRESHOLDS = (200,)
BIG_TRADE_WINDOWS_MS = (100,)
DELTA_BUCKET_TICKS = (1, 4)
DELTA_BAR_SECONDS = (60, 180, 300)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit reconstructed Sierra ES trade events against Databento across the "
            "full ETH and RTH causal session, including deterministic order-flow features."
        )
    )
    parser.add_argument(
        "--databento-zip",
        type=Path,
        default=Path("data/raw/ES/GLBX-20260713-S6XF67C8UA.zip"),
    )
    parser.add_argument(
        "--sierra-dir",
        type=Path,
        default=Path("data/raw/ES/sierra-es-trades"),
    )
    parser.add_argument(
        "--session-manifest",
        type=Path,
        default=Path(
            "data/reports/data_quality/ES/"
            "sierra_scid_event_usability_0930_1100_20101214_20260610_by_date.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/reports/data_quality/ES/"
            "databento_sierra_full_session_orderflow_20250714_20260610"
        ),
    )
    parser.add_argument("--start", default="2025-07-14")
    parser.add_argument("--end", default="2026-06-10")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--sample",
        choices=("head", "stratified"),
        default="head",
        help="Selection policy when --limit is supplied.",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Recompute only ERROR sessions in an existing output directory and merge them atomically.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = load_sessions(args.session_manifest, args.start, args.end)
    retry_dates: set[str] = set()
    if args.retry_errors:
        existing_path = args.output_dir / "by_session.csv"
        if not existing_path.is_file():
            raise FileNotFoundError(f"--retry-errors requires existing output: {existing_path}")
        existing = pd.read_csv(existing_path, dtype={"session_date": "string"})
        retry_dates = set(
            existing.loc[existing["comparison_status"].eq("ERROR"), "session_date"].astype(str)
        )
        if not retry_dates:
            raise ValueError("existing audit contains no ERROR sessions to retry")
        sessions = sessions[sessions["session_date"].isin(retry_dates)].reset_index(drop=True)
    if args.limit:
        sessions = select_limited_sessions(sessions, args.limit, args.sample)

    session_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    minute_rows: list[pd.DataFrame] = []
    mismatch_rows: list[dict[str, Any]] = []
    started = time.monotonic()
    with zipfile.ZipFile(args.databento_zip) as archive:
        names = set(archive.namelist())
        metadata = json.loads(archive.read("metadata.json"))
        cache = DatabentoDayCache(archive, names, max_days=3)
        for position, row in enumerate(sessions.itertuples(index=False), start=1):
            date = str(row.session_date)
            contract = str(row.contract)
            print(
                f"[{position}/{len(sessions)}] {date} {contract} "
                f"elapsed={time.monotonic() - started:.1f}s",
                flush=True,
            )
            try:
                session_result, per_segment, minutes, mismatches = compare_session(
                    cache=cache,
                    date=date,
                    sierra_contract=contract,
                    sierra_dir=args.sierra_dir,
                )
                session_rows.append(session_result)
                segment_rows.extend(per_segment)
                minute_rows.extend(minutes)
                mismatch_rows.extend(mismatches)
            except Exception as exc:
                session_rows.append(
                    {
                        "session_date": date,
                        "sierra_contract": contract,
                        "databento_contract": databento_symbol(contract),
                        "comparison_status": "ERROR",
                        "failure_reason": f"{type(exc).__name__}: {exc}",
                    }
                )

    by_session = pd.DataFrame(session_rows)
    by_segment = pd.DataFrame(segment_rows)
    minute_detail = pd.concat(minute_rows, ignore_index=True) if minute_rows else pd.DataFrame()
    mismatch_detail = pd.DataFrame(mismatch_rows)
    if args.retry_errors:
        by_session = merge_retried_rows(
            args.output_dir / "by_session.csv",
            by_session,
            retry_dates,
            dtype={"session_date": "string"},
        )
        by_segment = merge_retried_rows(
            args.output_dir / "by_segment.csv",
            by_segment,
            retry_dates,
            dtype={"session_date": "string"},
        )
        minute_detail = merge_retried_rows(
            args.output_dir / "minute_comparison.csv",
            minute_detail,
            retry_dates,
            dtype={"session_date": "string"},
        )
        mismatch_detail = merge_retried_rows(
            args.output_dir / "event_mismatch_samples.csv",
            mismatch_detail,
            retry_dates,
            dtype={"session_date": "string"},
        )
    by_session = by_session.sort_values("session_date")
    by_segment = by_segment.sort_values(["session_date", "segment"])
    by_session.to_csv(args.output_dir / "by_session.csv", index=False)
    by_segment.to_csv(args.output_dir / "by_segment.csv", index=False)
    minute_detail.to_csv(args.output_dir / "minute_comparison.csv", index=False)
    mismatch_detail.to_csv(args.output_dir / "event_mismatch_samples.csv", index=False)
    market_summary = session_market_summary(minute_detail)
    market_summary.to_csv(args.output_dir / "session_market_summary.csv", index=False)
    summary = build_summary(
        by_session=by_session,
        by_segment=by_segment,
        market_summary=market_summary,
        args=args,
        metadata=metadata,
        elapsed_seconds=time.monotonic() - started,
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(
        render_report(summary, by_session, by_segment), encoding="utf-8"
    )
    print(
        f"Wrote {args.output_dir} in {summary['runtime']['elapsed_seconds']:.1f}s "
        f"verdict={summary['verdict']}",
        flush=True,
    )


def load_sessions(path: Path, start: str, end: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"session_date": "string", "contract": "string"})
    required = {"session_date", "contract", "raw_structure_pass"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Session manifest is missing columns: {missing}")
    frame = frame[
        frame["session_date"].between(start, end)
        & frame["raw_structure_pass"].map(as_bool)
    ].copy()
    if frame.empty:
        raise ValueError("No structurally valid Sierra sessions in the requested overlap")
    return frame[["session_date", "contract"]].sort_values("session_date").reset_index(drop=True)


def select_limited_sessions(frame: pd.DataFrame, limit: int, sample: str) -> pd.DataFrame:
    if limit >= len(frame):
        return frame
    if sample == "head":
        return frame.head(limit).reset_index(drop=True)
    indexes = np.linspace(0, len(frame) - 1, num=limit, dtype=int)
    return frame.iloc[np.unique(indexes)].reset_index(drop=True)


class DatabentoDayCache:
    def __init__(
        self,
        archive: zipfile.ZipFile,
        names: set[str],
        *,
        max_days: int,
    ) -> None:
        self.archive = archive
        self.names = names
        self.max_days = max_days
        self.frames: OrderedDict[str, tuple[pd.DataFrame, set[str]]] = OrderedDict()

    def get(self, utc_date: str) -> tuple[pd.DataFrame, set[str]]:
        if utc_date in self.frames:
            self.frames.move_to_end(utc_date)
            return self.frames[utc_date]
        member = f"glbx-mdp3-{utc_date.replace('-', '')}.trades.dbn.zst"
        if member not in self.names:
            raise ValueError(f"Databento member absent: {member}")
        with tempfile.NamedTemporaryFile(suffix=".dbn.zst") as temp:
            with self.archive.open(member) as source:
                shutil.copyfileobj(source, temp)
            temp.flush()
            store = db.DBNStore.from_file(temp.name)
            partial = {str(value) for value in store.metadata.partial}
            frame = store.to_df().reset_index()
        frame["timestamp_ns"] = pd.to_datetime(frame["ts_event"], utc=True).astype("int64")
        frame["symbol"] = frame["symbol"].astype(str)
        self.frames[utc_date] = (frame, partial)
        self.frames.move_to_end(utc_date)
        while len(self.frames) > self.max_days:
            self.frames.popitem(last=False)
        return self.frames[utc_date]

    def window(
        self,
        *,
        start: pd.Timestamp,
        end: pd.Timestamp,
        contract: str,
    ) -> tuple[pd.DataFrame, bool]:
        parts = []
        partial = False
        day = start.tz_convert("UTC").normalize()
        final_day = (end - pd.Timedelta(nanoseconds=1)).tz_convert("UTC").normalize()
        while day <= final_day:
            frame, partial_symbols = self.get(str(day.date()))
            part = frame[
                frame["symbol"].eq(contract)
                & frame["timestamp_ns"].ge(start.value)
                & frame["timestamp_ns"].lt(end.value)
            ].copy()
            if not part.empty:
                parts.append(part)
            partial = partial or contract in partial_symbols
            day += pd.Timedelta(days=1)
        if not parts:
            raise ValueError(f"No Databento {contract} events from {start} to {end}")
        frame = pd.concat(parts, ignore_index=True)
        frame["price"] = pd.to_numeric(frame["price"], errors="raise").astype(float)
        frame["size"] = pd.to_numeric(frame["size"], errors="raise").astype(np.int64)
        frame["side"] = frame["side"].astype(str)
        size = frame["size"].to_numpy(dtype=np.int64)
        frame["buy_volume"] = np.where(frame["side"].eq("B"), size, 0)
        frame["sell_volume"] = np.where(frame["side"].eq("A"), size, 0)
        frame["signed_size"] = frame["buy_volume"] - frame["sell_volume"]
        frame["source_ordinal"] = np.arange(len(frame), dtype=np.int64)
        columns = [
            "timestamp_ns",
            "source_ordinal",
            "price",
            "size",
            "side",
            "buy_volume",
            "sell_volume",
            "signed_size",
        ]
        return frame[columns].reset_index(drop=True), partial


def merge_retried_rows(
    path: Path,
    replacement: pd.DataFrame,
    retry_dates: set[str],
    *,
    dtype: dict[str, str],
) -> pd.DataFrame:
    if not path.is_file():
        return replacement
    existing = pd.read_csv(path, dtype=dtype)
    retained = existing.loc[~existing["session_date"].astype(str).isin(retry_dates)].copy()
    if replacement.empty:
        return retained
    return pd.concat([retained, replacement], ignore_index=True)


def compare_session(
    *,
    cache: DatabentoDayCache,
    date: str,
    sierra_contract: str,
    sierra_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[pd.DataFrame], list[dict[str, Any]]]:
    session_start, session_end = full_session_window(date)
    databento_contract = databento_symbol(sierra_contract)
    db_events, db_partial = cache.window(
        start=session_start,
        end=session_end,
        contract=databento_contract,
    )
    sc_events, marker_stats = load_sierra_events(
        sierra_dir / f"{sierra_contract}-CME.parquet",
        start=session_start,
        end=session_end,
    )
    per_segment = []
    minute_frames = []
    mismatch_rows = []
    for segment in SEGMENTS:
        start, end = segment_window(date, segment)
        sc_part = filter_events(sc_events, start, end)
        db_part = filter_events(db_events, start, end)
        result, minute, mismatch = compare_event_frames(
            session_date=date,
            segment=segment,
            sierra_contract=sierra_contract,
            sc=sc_part,
            db_events=db_part,
        )
        per_segment.append(result)
        minute_frames.append(minute)
        mismatch_rows.extend(mismatch)
    full, _, full_mismatch = compare_event_frames(
        session_date=date,
        segment="FULL_SESSION",
        sierra_contract=sierra_contract,
        sc=sc_events,
        db_events=db_events,
    )
    mismatch_rows.extend(full_mismatch)
    all_segments_pass = all(
        row["comparison_status"]
        in {
            "DATABENTO_EVENT_EQUIVALENT",
            "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS",
        }
        for row in per_segment
    )
    full_acceptable = full["comparison_status"] in {
        "DATABENTO_EVENT_EQUIVALENT",
        "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS",
    }
    status = (
        (
            "DATABENTO_EVENT_EQUIVALENT"
            if full["comparison_status"] == "DATABENTO_EVENT_EQUIVALENT"
            and all(
                row["comparison_status"] == "DATABENTO_EVENT_EQUIVALENT"
                for row in per_segment
            )
            else "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS"
        )
        if full_acceptable
        and all_segments_pass
        and marker_stats["marker_valid"]
        and not db_partial
        else "NOT_EVENT_EQUIVALENT"
    )
    session_result = {
        **full,
        "comparison_status": status,
        "databento_active_contract_partial": db_partial,
        "sierra_marker_valid": marker_stats["marker_valid"],
        "eth_status": per_segment[0]["comparison_status"],
        "rth_status": per_segment[1]["comparison_status"],
    }
    session_result["failure_reason"] = comparison_failure_reason(session_result)
    return session_result, per_segment, minute_frames, mismatch_rows


def full_session_window(date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    day = pd.Timestamp(date)
    previous = day - pd.Timedelta(days=1)
    return (
        pd.Timestamp(f"{previous.date()} 16:00:00", tz=ET),
        pd.Timestamp(f"{day.date()} 16:00:00", tz=ET),
    )


def segment_window(date: str, segment: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    day = pd.Timestamp(date)
    if segment == "ETH":
        previous = day - pd.Timedelta(days=1)
        return (
            pd.Timestamp(f"{previous.date()} 16:00:00", tz=ET),
            pd.Timestamp(f"{day.date()} 09:30:00", tz=ET),
        )
    if segment == "RTH":
        return (
            pd.Timestamp(f"{day.date()} 09:30:00", tz=ET),
            pd.Timestamp(f"{day.date()} 16:00:00", tz=ET),
        )
    raise ValueError(f"Unknown segment: {segment}")


def load_sierra_events(
    path: Path,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Sierra contract file absent: {path}")
    buffer_us = 1_000_000
    start_us = datetime_to_scid_us(start.to_pydatetime()) - buffer_us
    end_us = datetime_to_scid_us(end.to_pydatetime()) + buffer_us
    raw = pq.read_table(
        path,
        columns=SCID_COLUMNS,
        filters=[
            ("scid_datetime_us", ">=", start_us),
            ("scid_datetime_us", "<", end_us),
        ],
    ).to_pandas()
    if raw.empty:
        raise ValueError(f"No Sierra records in {start} to {end}: {path.name}")
    raw["source_ordinal"] = np.arange(len(raw), dtype=np.int64)
    events, stats = reconstruct_sierra_trade_events(raw)
    events["timestamp_ns"] = scid_us_to_unix_ns(
        events["scid_datetime_us"].to_numpy(dtype=np.int64)
    )
    events = events[
        events["timestamp_ns"].ge(start.tz_convert("UTC").value)
        & events["timestamp_ns"].lt(end.tz_convert("UTC").value)
    ].copy()
    events = events.rename(columns={"volume": "size", "signed_volume": "signed_size"})
    return events[
        [
            "timestamp_ns",
            "source_ordinal",
            "price",
            "size",
            "side",
            "buy_volume",
            "sell_volume",
            "signed_size",
        ]
    ].reset_index(drop=True), stats


def filter_events(
    events: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    start_ns = start.tz_convert("UTC").value
    end_ns = end.tz_convert("UTC").value
    return events[
        events["timestamp_ns"].ge(start_ns) & events["timestamp_ns"].lt(end_ns)
    ].reset_index(drop=True)


def compare_event_frames(
    *,
    session_date: str,
    segment: str,
    sierra_contract: str,
    sc: pd.DataFrame,
    db_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    if sc.empty or db_events.empty:
        raise ValueError(
            f"{session_date} {segment} has empty source: Sierra={len(sc)} Databento={len(db_events)}"
        )
    sc_payload = payload_array(sc)
    db_payload = payload_array(db_events)
    row_count_equal = len(sc_payload) == len(db_payload)
    price_size_sequence_exact = bool(
        row_count_equal and np.array_equal(sc_payload[:, :2], db_payload[:, :2])
    )
    labeled_db = db_events["side"].isin(["A", "B"]).to_numpy()
    side_sequence_exact_where_databento_labeled = bool(
        row_count_equal
        and np.array_equal(sc_payload[labeled_db, 2], db_payload[labeled_db, 2])
    )
    payload_exact = bool(row_count_equal and np.array_equal(sc_payload, db_payload))
    aligned = min(len(sc), len(db_events))
    timestamp_delta = (
        sc["timestamp_ns"].to_numpy(dtype=np.int64)[:aligned]
        - db_events["timestamp_ns"].to_numpy(dtype=np.int64)[:aligned]
    )
    timestamps_within_1ms = bool(
        price_size_sequence_exact
        and side_sequence_exact_where_databento_labeled
        and len(timestamp_delta)
        and np.max(np.abs(timestamp_delta)) <= 1_000_000
    )

    feature_checks: dict[str, bool] = {}
    comparable_feature_checks: dict[str, bool] = {}
    if row_count_equal and price_size_sequence_exact:
        sc_comparable = sc.loc[labeled_db].reset_index(drop=True)
        db_comparable = db_events.loc[labeled_db].reset_index(drop=True)
    else:
        sc_comparable = sc.iloc[0:0].copy()
        db_comparable = db_events.iloc[0:0].copy()
    for ticks in DELTA_BUCKET_TICKS:
        feature_checks[f"profile_{ticks}tick_exact"] = profile_equal(sc, db_events, ticks=ticks)
        comparable_feature_checks[
            f"profile_{ticks}tick_reference_comparable_exact"
        ] = bool(
            len(sc_comparable)
            and profile_equal(sc_comparable, db_comparable, ticks=ticks)
        )
        for seconds in DELTA_BAR_SECONDS:
            feature_checks[f"bar_{seconds}s_delta_{ticks}tick_exact"] = bar_profile_equal(
                sc, db_events, ticks=ticks, seconds=seconds
            )
            comparable_feature_checks[
                f"bar_{seconds}s_delta_{ticks}tick_reference_comparable_exact"
            ] = bool(
                len(sc_comparable)
                and bar_profile_equal(
                    sc_comparable,
                    db_comparable,
                    ticks=ticks,
                    seconds=seconds,
                )
            )
    for threshold in BIG_TRADE_THRESHOLDS:
        for window_ms in BIG_TRADE_WINDOWS_MS:
            feature_checks[f"large_{threshold}_{window_ms}ms_exact"] = trigger_sequence_equal(
                big_trade_events(sc, threshold=threshold, window_ms=window_ms),
                big_trade_events(db_events, threshold=threshold, window_ms=window_ms),
            )
            comparable_feature_checks[
                f"large_{threshold}_{window_ms}ms_reference_comparable_exact"
            ] = bool(
                len(sc_comparable)
                and trigger_sequence_equal(
                    big_trade_events(
                        sc_comparable,
                        threshold=threshold,
                        window_ms=window_ms,
                    ),
                    big_trade_events(
                        db_comparable,
                        threshold=threshold,
                        window_ms=window_ms,
                    ),
                )
            )

    minute = minute_aggregate(sc, "sc").merge(
        minute_aggregate(db_events, "db"), on="minute", how="outer"
    )
    minute_fields = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "buy_volume",
        "sell_volume",
        "signed_volume",
        "events",
        "large10_volume",
        "large10_signed_volume",
        "large20_volume",
        "large20_signed_volume",
    ]
    for field in minute_fields:
        minute[f"{field}_match"] = minute[f"{field}_sc"].eq(minute[f"{field}_db"])
    minute["session_date"] = session_date
    minute["segment"] = segment
    minute["contract"] = sierra_contract
    minute = minute[
        ["session_date", "segment", "contract", "minute"]
        + [
            name
            for field in minute_fields
            for name in (f"{field}_sc", f"{field}_db", f"{field}_match")
        ]
    ]
    minute_all_exact = bool(
        all(minute[f"{field}_match"].fillna(False).all() for field in minute_fields)
    )
    neutral_sc = int((~sc["side"].isin(["A", "B"])).sum())
    neutral_db = int((~db_events["side"].isin(["A", "B"])).sum())
    full_equivalent = bool(
        payload_exact
        and timestamps_within_1ms
        and minute_all_exact
        and all(feature_checks.values())
        and neutral_sc == 0
        and neutral_db == 0
    )
    reference_gap_equivalent = bool(
        not full_equivalent
        and price_size_sequence_exact
        and side_sequence_exact_where_databento_labeled
        and timestamps_within_1ms
        and neutral_sc == 0
        and neutral_db > 0
        and all(comparable_feature_checks.values())
    )
    result: dict[str, Any] = {
        "session_date": session_date,
        "segment": segment,
        "sierra_contract": sierra_contract,
        "databento_contract": databento_symbol(sierra_contract),
        "comparison_status": (
            "DATABENTO_EVENT_EQUIVALENT"
            if full_equivalent
            else (
                "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS"
                if reference_gap_equivalent
                else "NOT_EVENT_EQUIVALENT"
            )
        ),
        "sierra_events": len(sc),
        "databento_events": len(db_events),
        "payload_row_count_equal": row_count_equal,
        "price_size_sequence_exact": price_size_sequence_exact,
        "side_sequence_exact_where_databento_labeled": (
            side_sequence_exact_where_databento_labeled
        ),
        "payload_sequence_exact": payload_exact,
        "timestamp_all_within_1ms": timestamps_within_1ms,
        "timestamp_abs_delta_ns_max": (
            int(np.max(np.abs(timestamp_delta))) if len(timestamp_delta) else None
        ),
        "minute_all_orderflow_exact": minute_all_exact,
        "sierra_neutral_side_events": neutral_sc,
        "databento_neutral_side_events": neutral_db,
        "sierra_volume": int(sc["size"].sum()),
        "databento_volume": int(db_events["size"].sum()),
        "sierra_signed_volume": int(sc["signed_size"].sum()),
        "databento_signed_volume": int(db_events["signed_size"].sum()),
        **feature_checks,
        **comparable_feature_checks,
    }
    result["failure_reason"] = comparison_failure_reason(result)
    mismatches = payload_mismatch_samples(
        session_date=session_date,
        segment=segment,
        sc=sc,
        db_events=db_events,
        limit=20,
    )
    return result, minute, mismatches


def payload_array(events: pd.DataFrame) -> np.ndarray:
    return np.column_stack(
        [
            np.rint(events["price"].to_numpy(dtype=float) * 4).astype(np.int64),
            events["size"].to_numpy(dtype=np.int64),
            events["side"].map({"A": -1, "B": 1}).fillna(0).to_numpy(dtype=np.int64),
        ]
    )


def minute_aggregate(events: pd.DataFrame, suffix: str) -> pd.DataFrame:
    frame = events.copy()
    frame["minute"] = pd.to_datetime(frame["timestamp_ns"], utc=True).dt.floor("min")
    size = frame["size"].to_numpy(dtype=np.int64)
    frame["large10_volume"] = np.where(size >= 10, size, 0)
    frame["large10_signed_volume"] = np.where(size >= 10, frame["signed_size"], 0)
    frame["large20_volume"] = np.where(size >= 20, size, 0)
    frame["large20_signed_volume"] = np.where(size >= 20, frame["signed_size"], 0)
    result = frame.groupby("minute", sort=True).agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        signed_volume=("signed_size", "sum"),
        events=("size", "size"),
        large10_volume=("large10_volume", "sum"),
        large10_signed_volume=("large10_signed_volume", "sum"),
        large20_volume=("large20_volume", "sum"),
        large20_signed_volume=("large20_signed_volume", "sum"),
    )
    return result.add_suffix(f"_{suffix}").reset_index()


def session_market_summary(minute_detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if minute_detail.empty:
        return pd.DataFrame(
            columns=[
                "session_date",
                "segment",
                "open_exact",
                "high_exact",
                "low_exact",
                "close_exact",
                "ohlc_exact",
                "volume_exact",
            ]
        )
    ordered = minute_detail.copy()
    ordered["minute"] = pd.to_datetime(ordered["minute"], utc=True)
    ordered = ordered.sort_values(["session_date", "segment", "minute"])
    for (session_date, segment), frame in ordered.groupby(
        ["session_date", "segment"], sort=True
    ):
        open_exact = frame["open_sc"].iloc[0] == frame["open_db"].iloc[0]
        high_exact = frame["high_sc"].max() == frame["high_db"].max()
        low_exact = frame["low_sc"].min() == frame["low_db"].min()
        close_exact = frame["close_sc"].iloc[-1] == frame["close_db"].iloc[-1]
        rows.append(
            {
                "session_date": session_date,
                "segment": segment,
                "open_exact": bool(open_exact),
                "high_exact": bool(high_exact),
                "low_exact": bool(low_exact),
                "close_exact": bool(close_exact),
                "ohlc_exact": bool(
                    open_exact and high_exact and low_exact and close_exact
                ),
                "volume_exact": bool(
                    frame["volume_sc"].sum() == frame["volume_db"].sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def profile_equal(left: pd.DataFrame, right: pd.DataFrame, *, ticks: int) -> bool:
    def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
        price_ticks = np.rint(frame["price"].to_numpy(dtype=float) * 4).astype(np.int64)
        bucket = np.floor_divide(price_ticks, ticks)
        return (
            frame.assign(bucket=bucket)
            .groupby("bucket", sort=True)
            .agg(volume=("size", "sum"), delta=("signed_size", "sum"))
        )

    joined = aggregate(left).join(
        aggregate(right), how="outer", lsuffix="_left", rsuffix="_right"
    ).fillna(0)
    return bool(
        joined["volume_left"].eq(joined["volume_right"]).all()
        and joined["delta_left"].eq(joined["delta_right"]).all()
    )


def bar_profile_equal(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    ticks: int,
    seconds: int,
) -> bool:
    def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
        price_ticks = np.rint(frame["price"].to_numpy(dtype=float) * 4).astype(np.int64)
        bucket = np.floor_divide(price_ticks, ticks)
        bar_ns = np.floor_divide(
            frame["timestamp_ns"].to_numpy(dtype=np.int64), seconds * 1_000_000_000
        )
        return (
            frame.assign(bucket=bucket, bar_ns=bar_ns)
            .groupby(["bar_ns", "bucket"], sort=True)
            .agg(volume=("size", "sum"), delta=("signed_size", "sum"))
        )

    joined = aggregate(left).join(
        aggregate(right), how="outer", lsuffix="_left", rsuffix="_right"
    ).fillna(0)
    return bool(
        joined["volume_left"].eq(joined["volume_right"]).all()
        and joined["delta_left"].eq(joined["delta_right"]).all()
    )


def big_trade_events(
    events: pd.DataFrame,
    *,
    threshold: int,
    window_ms: int,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=["event_index", "price_ticks", "side_code"])
    timestamp = events["timestamp_ns"].to_numpy(dtype=np.int64)
    price_ticks = np.rint(events["price"].to_numpy(dtype=float) * 4).astype(np.int64)
    size = events["size"].to_numpy(dtype=np.int64)
    side = events["side"].map({"A": -1, "B": 1}).fillna(0).to_numpy(dtype=np.int8)
    window_ns = window_ms * 1_000_000
    rows: list[tuple[int, int, int]] = []
    anchor = 0
    total = int(size[0])
    qualified = total > threshold
    if qualified:
        rows.append((0, int(price_ticks[0]), int(side[0])))
    for index in range(1, len(events)):
        matches = (
            timestamp[index] - timestamp[anchor] <= window_ns
            and price_ticks[index] == price_ticks[anchor]
            and side[index] == side[anchor]
        )
        if matches:
            total += int(size[index])
            if not qualified and total > threshold:
                rows.append((index, int(price_ticks[index]), int(side[index])))
                qualified = True
        else:
            anchor = index
            total = int(size[index])
            qualified = total > threshold
            if qualified:
                rows.append((index, int(price_ticks[index]), int(side[index])))
    return pd.DataFrame(rows, columns=["event_index", "price_ticks", "side_code"])


def trigger_sequence_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return bool(left.shape == right.shape and np.array_equal(left.to_numpy(), right.to_numpy()))


def payload_mismatch_samples(
    *,
    session_date: str,
    segment: str,
    sc: pd.DataFrame,
    db_events: pd.DataFrame,
    limit: int,
) -> list[dict[str, Any]]:
    sc_payload = payload_array(sc)
    db_payload = payload_array(db_events)
    aligned = min(len(sc_payload), len(db_payload))
    mismatch = np.flatnonzero(np.any(sc_payload[:aligned] != db_payload[:aligned], axis=1))
    indexes = list(mismatch[:limit])
    if len(sc_payload) != len(db_payload) and len(indexes) < limit:
        indexes.extend(
            range(
                aligned,
                min(
                    max(len(sc_payload), len(db_payload)),
                    aligned + limit - len(indexes),
                ),
            )
        )
    rows = []
    for index in indexes:
        rows.append(
            {
                "session_date": session_date,
                "segment": segment,
                "event_index": index,
                "sierra_timestamp_ns": (
                    int(sc.iloc[index]["timestamp_ns"]) if index < len(sc) else None
                ),
                "databento_timestamp_ns": (
                    int(db_events.iloc[index]["timestamp_ns"])
                    if index < len(db_events)
                    else None
                ),
                "sierra_price": sc.iloc[index]["price"] if index < len(sc) else None,
                "databento_price": (
                    db_events.iloc[index]["price"] if index < len(db_events) else None
                ),
                "sierra_size": sc.iloc[index]["size"] if index < len(sc) else None,
                "databento_size": (
                    db_events.iloc[index]["size"] if index < len(db_events) else None
                ),
                "sierra_side": sc.iloc[index]["side"] if index < len(sc) else None,
                "databento_side": (
                    db_events.iloc[index]["side"] if index < len(db_events) else None
                ),
            }
        )
    return rows


def comparison_failure_reason(row: dict[str, Any]) -> str:
    if row.get("comparison_status") == "ERROR":
        return str(row.get("failure_reason") or "comparison_error")
    if row.get("comparison_status") == "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS":
        return "databento_neutral_aggressor_side_reference_gap"
    if not as_bool(row.get("payload_sequence_exact")):
        if int(row.get("databento_neutral_side_events", 0) or 0) > 0:
            return "aggressor_side_mismatch"
        return "event_payload_sequence_mismatch"
    if not as_bool(row.get("timestamp_all_within_1ms")):
        return "timestamp_error_over_1ms"
    failed_features = sorted(
        key
        for key, value in row.items()
        if key.endswith("_exact") and not as_bool(value)
    )
    if failed_features:
        return "feature_mismatch:" + ",".join(failed_features)
    if row.get("comparison_status") == "DATABENTO_EVENT_EQUIVALENT":
        return ""
    return "other_component_mismatch"


def build_summary(
    *,
    by_session: pd.DataFrame,
    by_segment: pd.DataFrame,
    market_summary: pd.DataFrame,
    args: argparse.Namespace,
    metadata: dict[str, Any],
    elapsed_seconds: float,
) -> dict[str, Any]:
    equivalent = by_session["comparison_status"].eq("DATABENTO_EVENT_EQUIVALENT")
    reference_gap = by_session["comparison_status"].eq(
        "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS"
    )
    errors = by_session["comparison_status"].eq("ERROR")
    complete = args.limit is None
    all_pass = bool(len(by_session) and equivalent.all() and not errors.any())
    verdict = "PASS" if complete and all_pass else "NEEDS MANUAL REVIEW"
    return {
        "schema": "alphaquest.sierra-databento-full-session-audit/v1",
        "verdict": verdict,
        "scope": {
            "start_date": args.start,
            "end_date": args.end,
            "complete_requested_overlap": complete,
            "sessions_compared": len(by_session),
            "segments": {
                "ETH": "prior calendar date 16:00 to session date 09:30 America/New_York",
                "RTH": "session date 09:30 to 16:00 America/New_York",
            },
            "contract_policy": (
                "Sierra/MotiveWave-Rithmic roll-calendar contract compared to the "
                "identical Databento contract"
            ),
        },
        "source": {
            "databento_archive": str(args.databento_zip),
            "databento_archive_sha256": sha256_file(args.databento_zip),
            "databento_job_id": metadata.get("job_id"),
            "databento_query": metadata.get("query"),
            "sierra_dir": str(args.sierra_dir),
            "session_manifest": str(args.session_manifest),
            "session_manifest_sha256": sha256_file(args.session_manifest),
        },
        "normalization": {
            "ordered_payload": "exact (price_ticks, size, aggressor_side) after Sierra FIRST/LAST reconstruction",
            "timestamp_tolerance_ns": 1_000_000,
            "minute_features": [
                "OHLC",
                "volume",
                "buy_volume",
                "sell_volume",
                "signed_volume",
                "event_count",
                "large10 volume/delta",
                "large20 volume/delta",
            ],
            "profile_bucket_ticks": list(DELTA_BUCKET_TICKS),
            "profile_bar_seconds": list(DELTA_BAR_SECONDS),
            "large_trade_thresholds": list(BIG_TRADE_THRESHOLDS),
            "large_trade_windows_ms": list(BIG_TRADE_WINDOWS_MS),
            "deterministic_derivation_rule": (
                "Exact normalized ordered payloads imply equivalence for deterministic "
                "non-boundary-sensitive features computed from price, size, aggressor side, "
                "and source order. Time-window features must also respect Sierra's 1 ms "
                "timestamp uncertainty and are checked explicitly where supported."
            ),
        },
        "outcome": {
            "session_status_counts": json_ready(
                by_session["comparison_status"].value_counts(dropna=False).to_dict()
            ),
            "segment_status_counts": json_ready(
                by_segment.groupby(["segment", "comparison_status"]).size().to_dict()
                if not by_segment.empty
                else {}
            ),
            "sessions_event_equivalent": int(equivalent.sum()),
            "sessions_reference_gap_only": int(reference_gap.sum()),
            "sessions_not_equivalent": int(
                (~equivalent & ~reference_gap & ~errors).sum()
            ),
            "sessions_error": int(errors.sum()),
            "session_segments_market_ohlc_exact": int(
                market_summary.get("ohlc_exact", pd.Series(dtype=bool))
                .fillna(False)
                .sum()
            ),
            "session_segments_market_ohlc_compared": int(len(market_summary)),
            "session_segments_market_volume_exact": int(
                market_summary.get("volume_exact", pd.Series(dtype=bool))
                .fillna(False)
                .sum()
            ),
        },
        "historical_inference": {
            "directly_validated_period": f"{args.start} through {args.end}",
            "older_sierra_period": "2011 through the day before the Databento overlap",
            "status": "EXTRAPOLATED_NOT_CROSS_VENDOR_VALIDATED",
            "interpretation": (
                "A full-session overlap PASS validates the modern Sierra extraction and "
                "reconstruction semantics. It does not prove older source bytes; older sessions "
                "must also pass intrinsic structure, side, marker, timestamp-order, and continuity gates."
            ),
        },
        "runtime": {
            "processing_mode": "retry_errors" if args.retry_errors else "full_audit",
            "elapsed_seconds": float(elapsed_seconds),
            "seconds_per_session": (
                float(elapsed_seconds / len(by_session)) if len(by_session) else None
            ),
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def render_report(
    summary: dict[str, Any],
    by_session: pd.DataFrame,
    by_segment: pd.DataFrame,
) -> str:
    outcome = summary["outcome"]
    segment_exceptions = by_segment.loc[
        by_segment["comparison_status"].eq("NOT_EVENT_EQUIVALENT"),
        [
            "session_date",
            "segment",
            "sierra_contract",
            "comparison_status",
            "failure_reason",
        ],
    ].copy()
    errors = by_session.loc[
        by_session["comparison_status"].eq("ERROR"),
        ["session_date", "sierra_contract", "comparison_status", "failure_reason"],
    ].copy()
    if not errors.empty:
        errors.insert(1, "segment", "FULL_SESSION")
    exceptions = pd.concat([segment_exceptions, errors], ignore_index=True)
    if not exceptions.empty:
        exceptions = exceptions.sort_values(["session_date", "segment"])
    exception_text = markdown_table(exceptions) if not exceptions.empty else "No exceptions."
    return f"""# Sierra versus Databento full-session ES order-flow audit

**Verdict: {summary['verdict']}**

This audit compares the selected Sierra/MotiveWave-Rithmic ES contract with the
identical Databento contract across ETH (prior 16:00 through 09:30 ET) and RTH
(09:30 through 16:00 ET). It validates the canonical reconstructed event stream
and representative deterministic order-flow features, not only the strategy's
09:30-11:00 entry window.

## Outcome

- Sessions compared: **{summary['scope']['sessions_compared']}**
- Event-equivalent sessions: **{outcome['sessions_event_equivalent']}**
- Reference-gap-only sessions: **{outcome['sessions_reference_gap_only']}**
- Non-equivalent sessions: **{outcome['sessions_not_equivalent']}**
- Errors: **{outcome['sessions_error']}**
- Session-level ETH/RTH OHLC exact: **{outcome['session_segments_market_ohlc_exact']} / {outcome['session_segments_market_ohlc_compared']}**
- Session-level ETH/RTH volume exact: **{outcome['session_segments_market_volume_exact']} / {outcome['session_segments_market_ohlc_compared']}**
- Last processing pass: **{summary['runtime']['processing_mode']}**, **{summary['runtime']['elapsed_seconds']:.1f} seconds**

## Coverage

The fail-closed event criterion requires exact ordered price, size, and aggressor
side after Sierra FIRST/LAST reconstruction, timestamps within 1 ms of Databento,
exact minute OHLC and side-volume fields, exact 1-tick and 4-tick profiles, exact
60/180/300-second bucketed volume and delta, exact large-10/large-20 aggregates,
and the strategy's exact uninterrupted same-price/same-side `>200` / 100 ms
trigger sequence.

When the canonical ordered payload is exact, deterministic features based on
price, size, aggressor side, and source order inherit the same equivalence.
Timestamp-window features can still differ at a 1 ms boundary, so each new
boundary-sensitive feature needs an explicit concordance check.

## Exceptions

{exception_text}

## Historical interpretation

Only {summary['historical_inference']['directly_validated_period']} is directly
cross-vendor validated. Sierra history before the overlap remains
`EXTRAPOLATED_NOT_CROSS_VENDOR_VALIDATED`: a full modern overlap PASS gives strong
evidence for the reconstruction method, but it cannot prove that older files had
identical capture behavior. Older sessions therefore remain subject to intrinsic
marker, side, timestamp-order, continuity, and session-completeness gates.
"""


def databento_symbol(sierra_contract: str) -> str:
    if len(sierra_contract) != 5 or not sierra_contract.startswith("ES"):
        raise ValueError(f"Unexpected Sierra contract: {sierra_contract}")
    return f"{sierra_contract[:3]}{sierra_contract[-1]}"


def datetime_to_scid_us(value: datetime) -> int:
    return int((value.astimezone(timezone.utc) - SCID_EPOCH).total_seconds() * 1_000_000)


def scid_us_to_unix_ns(values: np.ndarray) -> np.ndarray:
    offset_us = int(
        (datetime(1970, 1, 1, tzinfo=timezone.utc) - SCID_EPOCH).total_seconds()
        * 1_000_000
    )
    return (values.astype(np.int64) - offset_us) * 1_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if math.isnan(float(value)) else float(value)
    if value is None or pd.isna(value):
        return None
    return value


def markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    rows = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for values in frame.itertuples(index=False, name=None):
        rows.append("| " + " | ".join(str(value) for value in values) + " |")
    return "\n".join(rows)


if __name__ == "__main__":
    main()
