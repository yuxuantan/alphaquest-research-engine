from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import databento as db
import numpy as np
import pandas as pd
import pyarrow.parquet as pq


SCID_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)
ET = "America/New_York"
WINDOW_START = "09:30:00"
WINDOW_END = "11:00:00"
FIRST_LAST_SPLIT = -1.9990015e37
BIG_TRADE_THRESHOLD = 200
BIG_TRADE_WINDOW_NS = 100_000_000
DELTA_THRESHOLD = 300

SCID_COLUMNS = [
    "scid_datetime_us",
    "open",
    "close",
    "num_trades",
    "volume",
    "bid_volume",
    "ask_volume",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Databento ES trades with Sierra SCID records after reconstructing "
            "Sierra unbundled trades."
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
        "--prior-audit",
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
            "databento_sierra_tick_comparison_0930_1100_20250714_20260610"
        ),
    )
    parser.add_argument("--start", default="2025-07-14")
    parser.add_argument("--end", default="2026-06-10")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prior = pd.read_csv(args.prior_audit, dtype={"session_date": "string", "contract": "string"})
    prior = prior[
        prior["strategy_session_eligible"].map(_as_bool)
        & prior["session_date"].between(args.start, args.end)
    ].copy()
    prior = prior.sort_values("session_date").reset_index(drop=True)
    if args.limit:
        prior = prior.head(args.limit)

    date_rows: list[dict[str, Any]] = []
    minute_rows: list[pd.DataFrame] = []
    mismatch_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(args.databento_zip) as archive:
        names = set(archive.namelist())
        metadata = json.loads(archive.read("metadata.json"))
        for position, audit_row in prior.iterrows():
            date = str(audit_row["session_date"])
            contract = str(audit_row["contract"])
            print(f"[{position + 1}/{len(prior)}] {date} {contract}", flush=True)
            try:
                result, minute_detail, mismatch_detail = compare_date(
                    archive=archive,
                    archive_names=names,
                    date=date,
                    sierra_contract=contract,
                    sierra_dir=args.sierra_dir,
                )
                result["prior_status"] = audit_row["status"]
                result["prior_reason"] = audit_row["reason"]
                result["prior_minute_parity_pass"] = _as_bool(audit_row["minute_parity_pass"])
                date_rows.append(result)
                if not minute_detail.empty:
                    minute_rows.append(minute_detail)
                mismatch_rows.extend(mismatch_detail)
            except Exception as exc:  # fail closed and retain the date in the report
                date_rows.append(
                    {
                        "session_date": date,
                        "sierra_contract": contract,
                        "databento_contract": databento_symbol(contract),
                        "comparison_status": "ERROR",
                        "error": f"{type(exc).__name__}: {exc}",
                        "prior_status": audit_row["status"],
                        "prior_reason": audit_row["reason"],
                        "prior_minute_parity_pass": _as_bool(audit_row["minute_parity_pass"]),
                    }
                )

    by_date = pd.DataFrame(date_rows).sort_values("session_date")
    by_date["failure_reason"] = by_date.apply(comparison_failure_reason, axis=1)
    by_date.to_csv(args.output_dir / "by_date.csv", index=False)
    if minute_rows:
        pd.concat(minute_rows, ignore_index=True).to_csv(
            args.output_dir / "minute_comparison.csv", index=False
        )
    pd.DataFrame(mismatch_rows).to_csv(args.output_dir / "event_mismatch_samples.csv", index=False)

    verified = by_date.loc[
        by_date["comparison_status"].eq("DATABENTO_EVENT_EQUIVALENT"), "session_date"
    ].astype(str)
    (args.output_dir / "databento_event_equivalent_dates.txt").write_text(
        "\n".join(verified) + ("\n" if len(verified) else ""), encoding="utf-8"
    )
    delta_verified = by_date.loc[
        by_date["payload_sequence_exact"].fillna(False)
        & by_date["timestamp_all_within_1ms"].fillna(False)
        & by_date["profile_volume_exact"].fillna(False)
        & by_date["profile_delta_1tick_exact"].fillna(False)
        & by_date["profile_delta_4tick_exact"].fillna(False)
        & by_date["delta_state_transition_sequence_exact"].fillna(False),
        "session_date",
    ].astype(str)
    (args.output_dir / "databento_profile_delta_equivalent_dates.txt").write_text(
        "\n".join(delta_verified) + ("\n" if len(delta_verified) else ""), encoding="utf-8"
    )
    by_date[~by_date["comparison_status"].eq("DATABENTO_EVENT_EQUIVALENT")].to_csv(
        args.output_dir / "not_event_equivalent_dates.csv", index=False
    )

    summary = build_summary(
        by_date=by_date,
        archive_path=args.databento_zip,
        sierra_dir=args.sierra_dir,
        prior_audit=args.prior_audit,
        metadata=metadata,
        start=args.start,
        end=args.end,
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(
        render_report(summary, by_date), encoding="utf-8"
    )
    print(f"Wrote {args.output_dir}", flush=True)


def compare_date(
    *,
    archive: zipfile.ZipFile,
    archive_names: set[str],
    date: str,
    sierra_contract: str,
    sierra_dir: Path,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    member = f"glbx-mdp3-{date.replace('-', '')}.trades.dbn.zst"
    if member not in archive_names:
        raise ValueError(f"Databento member absent: {member}")
    db_events, db_meta = load_databento_events(
        archive, member, date=date, contract=databento_symbol(sierra_contract)
    )
    sc_path = sierra_dir / f"{sierra_contract}-CME.parquet"
    sc_raw = load_sierra_window(sc_path, date)
    sc_events, marker_stats = reconstruct_sierra_events(sc_raw)

    db_payload = payload_array(db_events)
    sc_payload = payload_array(sc_events)
    row_count_equal = len(db_payload) == len(sc_payload)
    payload_sequence_exact = bool(row_count_equal and np.array_equal(db_payload, sc_payload))
    aligned = min(len(db_events), len(sc_events))
    timestamp_delta_ns = (
        sc_events["timestamp_ns"].to_numpy(dtype=np.int64)[:aligned]
        - db_events["timestamp_ns"].to_numpy(dtype=np.int64)[:aligned]
    )
    timestamp_all_within_1ms = bool(
        payload_sequence_exact
        and len(timestamp_delta_ns)
        and np.max(np.abs(timestamp_delta_ns)) <= 1_000_000
    )

    sc_big = strict_big_trade_events(sc_events)
    db_big = strict_big_trade_events(db_events)
    big_trade_exact = trigger_sequence_equal(sc_big, db_big)
    sc_delta = delta_state_transitions(sc_events)
    db_delta = delta_state_transitions(db_events)
    delta_transitions_exact = trigger_sequence_equal(sc_delta, db_delta)

    sc_minute = minute_aggregate(sc_events, "sc")
    db_minute = minute_aggregate(db_events, "db")
    minute = sc_minute.merge(db_minute, on="minute", how="outer")
    fields = ["open", "high", "low", "close", "volume", "buy_volume", "sell_volume", "signed_volume", "events"]
    for field in fields:
        minute[f"{field}_match"] = minute[f"{field}_sc"].eq(minute[f"{field}_db"])
    minute["session_date"] = date
    minute["contract"] = sierra_contract
    minute = minute[["session_date", "contract", "minute"] + [
        name for field in fields for name in (f"{field}_sc", f"{field}_db", f"{field}_match")
    ]]

    sc_profile = profile_aggregate(sc_events)
    db_profile = profile_aggregate(db_events)
    profile = sc_profile.join(db_profile, how="outer", lsuffix="_sc", rsuffix="_db").fillna(0)
    profile_volume_exact = bool(profile["volume_sc"].eq(profile["volume_db"]).all())
    profile_delta_1tick_exact = bool(profile["signed_volume_sc"].eq(profile["signed_volume_db"]).all())
    profile_delta_4tick_exact = bucket_delta_equal(sc_events, db_events)

    db_source_order_event_inversions = int(
        np.count_nonzero(np.diff(db_events["timestamp_ns"].to_numpy(dtype=np.int64)) < 0)
    )
    sc_source_order_event_inversions = int(
        np.count_nonzero(np.diff(sc_events["timestamp_ns"].to_numpy(dtype=np.int64)) < 0)
    )
    sc_side_bad = int((~sc_raw["side"].isin(["A", "B"])).sum())
    db_side_neutral = int((~db_events["side"].isin(["A", "B"])).sum())
    full_equivalent = bool(
        payload_sequence_exact
        and timestamp_all_within_1ms
        and big_trade_exact
        and delta_transitions_exact
        and profile_volume_exact
        and profile_delta_1tick_exact
        and profile_delta_4tick_exact
        and marker_stats["marker_valid"]
        and sc_side_bad == 0
        and db_side_neutral == 0
        and not db_meta["active_contract_partial"]
    )

    mismatch_detail = payload_mismatch_samples(
        date=date,
        sc=sc_events,
        db_events=db_events,
        limit=20,
    )
    result: dict[str, Any] = {
        "session_date": date,
        "sierra_contract": sierra_contract,
        "databento_contract": databento_symbol(sierra_contract),
        "comparison_status": (
            "DATABENTO_EVENT_EQUIVALENT" if full_equivalent else "NOT_EVENT_EQUIVALENT"
        ),
        "databento_active_contract_partial": db_meta["active_contract_partial"],
        "sierra_raw_rows": len(sc_raw),
        "sierra_reconstructed_events": len(sc_events),
        "databento_events": len(db_events),
        "sierra_unbundled_groups": marker_stats["first_markers"],
        "sierra_unbundled_component_rows": marker_stats["component_rows"],
        "sierra_marker_valid": marker_stats["marker_valid"],
        "sierra_num_trades_ne1": int(sc_raw["num_trades"].ne(1).sum()),
        "sierra_side_bad_rows": sc_side_bad,
        "databento_neutral_side_events": db_side_neutral,
        "payload_row_count_equal": row_count_equal,
        "payload_sequence_exact": payload_sequence_exact,
        "timestamp_all_within_1ms": timestamp_all_within_1ms,
        "timestamp_abs_delta_ns_max": int(np.max(np.abs(timestamp_delta_ns))) if len(timestamp_delta_ns) else None,
        "timestamp_delta_ns_median": float(np.median(timestamp_delta_ns)) if len(timestamp_delta_ns) else None,
        "sierra_source_order_event_inversions": sc_source_order_event_inversions,
        "databento_source_order_event_inversions": db_source_order_event_inversions,
        "minute_ohlcv_exact": all(
            bool(minute[f"{field}_match"].all()) for field in ["open", "high", "low", "close", "volume"]
        ),
        "minute_side_volume_exact": all(
            bool(minute[f"{field}_match"].all())
            for field in ["buy_volume", "sell_volume", "signed_volume"]
        ),
        "minute_event_count_exact": bool(minute["events_match"].all()),
        "profile_volume_exact": profile_volume_exact,
        "profile_delta_1tick_exact": profile_delta_1tick_exact,
        "profile_delta_4tick_exact": profile_delta_4tick_exact,
        "sierra_big_trade_triggers": len(sc_big),
        "databento_big_trade_triggers": len(db_big),
        "big_trade_trigger_sequence_exact": big_trade_exact,
        "sierra_delta_state_transitions": len(sc_delta),
        "databento_delta_state_transitions": len(db_delta),
        "delta_state_transition_sequence_exact": delta_transitions_exact,
        "sierra_volume": int(sc_events["size"].sum()),
        "databento_volume": int(db_events["size"].sum()),
        "sierra_signed_volume": int(sc_events["signed_size"].sum()),
        "databento_signed_volume": int(db_events["signed_size"].sum()),
    }
    return result, minute, mismatch_detail


def load_databento_events(
    archive: zipfile.ZipFile,
    member: str,
    *,
    date: str,
    contract: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    with tempfile.NamedTemporaryFile(suffix=".dbn.zst") as temp:
        with archive.open(member) as source:
            shutil.copyfileobj(source, temp)
        temp.flush()
        store = db.DBNStore.from_file(temp.name)
        partial = {str(value) for value in store.metadata.partial}
        frame = store.to_df().reset_index()
    timestamp = pd.to_datetime(frame["ts_event"], utc=True)
    start, end = utc_window(date)
    contract_mask = frame["symbol"].astype(str).eq(contract)
    frame = frame[contract_mask & timestamp.ge(start) & timestamp.lt(end)].copy()
    if frame.empty:
        raise ValueError(f"No Databento {contract} events in {date} morning window")
    frame["timestamp_ns"] = pd.to_datetime(frame["ts_event"], utc=True).astype("int64")
    frame["price"] = pd.to_numeric(frame["price"], errors="raise").astype(float)
    frame["size"] = pd.to_numeric(frame["size"], errors="raise").astype(np.int64)
    frame["side"] = frame["side"].astype(str)
    size = frame["size"].to_numpy(dtype=np.int64)
    side = frame["side"]
    frame["buy_volume"] = np.where(side.eq("B"), size, 0)
    frame["sell_volume"] = np.where(side.eq("A"), size, 0)
    frame["signed_size"] = frame["buy_volume"] - frame["sell_volume"]
    frame["source_ordinal"] = np.arange(len(frame), dtype=np.int64)
    return frame[
        ["timestamp_ns", "source_ordinal", "price", "size", "side", "buy_volume", "sell_volume", "signed_size"]
    ].reset_index(drop=True), {"active_contract_partial": contract in partial}


def load_sierra_window(path: Path, date: str) -> pd.DataFrame:
    if not path.exists():
        raise ValueError(f"Sierra contract file absent: {path}")
    start, end = utc_window(date)
    buffer_us = 1_000_000
    start_us = datetime_to_scid_us(start.to_pydatetime()) - buffer_us
    end_us = datetime_to_scid_us(end.to_pydatetime()) + buffer_us
    frame = pq.read_table(
        path,
        columns=SCID_COLUMNS,
        filters=[("scid_datetime_us", ">=", start_us), ("scid_datetime_us", "<", end_us)],
    ).to_pandas()
    if frame.empty:
        raise ValueError(f"No Sierra records in buffered window: {date} {path.name}")
    frame["side"] = np.select(
        [frame["ask_volume"].gt(0) & frame["bid_volume"].eq(0), frame["bid_volume"].gt(0) & frame["ask_volume"].eq(0)],
        ["B", "A"],
        default="N",
    )
    frame["source_ordinal"] = np.arange(len(frame), dtype=np.int64)
    return frame.reset_index(drop=True)


def reconstruct_sierra_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    marker_open = frame["open"].to_numpy(dtype=np.float64)
    first = (marker_open < -1e30) & (marker_open > FIRST_LAST_SPLIT)
    last = marker_open <= FIRST_LAST_SPLIT
    n = len(frame)
    depth_delta = np.zeros(n + 1, dtype=np.int32)
    depth_delta[np.flatnonzero(first)] += 1
    last_after = np.flatnonzero(last) + 1
    depth_delta[last_after[last_after <= n]] -= 1
    depth = np.cumsum(depth_delta[:-1])
    marker_valid = bool(first.sum() == last.sum() and (depth >= 0).all() and depth.max(initial=0) <= 1 and depth_delta.sum() == 0)
    starts = np.maximum.accumulate(np.where(first, np.arange(n), -1))
    group_id = np.where(depth > 0, starts, np.arange(n))
    working = frame.assign(group_id=group_id)
    events = (
        working.groupby(["group_id", "close", "side"], sort=False, as_index=False)
        .agg(
            first_scid_us=("scid_datetime_us", "first"),
            last_scid_us=("scid_datetime_us", "last"),
            size=("volume", "sum"),
            buy_volume=("ask_volume", "sum"),
            sell_volume=("bid_volume", "sum"),
            component_rows=("volume", "size"),
            first_source_ordinal=("source_ordinal", "first"),
        )
        .rename(columns={"close": "price"})
    )
    events["timestamp_ns"] = scid_us_to_unix_ns(events["first_scid_us"].to_numpy(dtype=np.int64))
    events["source_ordinal"] = events["first_source_ordinal"].astype(np.int64)
    events["size"] = events["size"].astype(np.int64)
    events["buy_volume"] = events["buy_volume"].astype(np.int64)
    events["sell_volume"] = events["sell_volume"].astype(np.int64)
    events["signed_size"] = events["buy_volume"] - events["sell_volume"]
    start_ns, end_ns = raw_utc_window_ns(frame)
    events = events[events["timestamp_ns"].ge(start_ns) & events["timestamp_ns"].lt(end_ns)].copy()
    events = events[
        ["timestamp_ns", "source_ordinal", "price", "size", "side", "buy_volume", "sell_volume", "signed_size", "component_rows"]
    ].reset_index(drop=True)
    return events, {
        "first_markers": int(first.sum()),
        "last_markers": int(last.sum()),
        "component_rows": int((depth > 0).sum()),
        "marker_valid": marker_valid,
    }


def raw_utc_window_ns(frame: pd.DataFrame) -> tuple[int, int]:
    raw_ns = scid_us_to_unix_ns(frame["scid_datetime_us"].to_numpy(dtype=np.int64))
    timestamps = pd.to_datetime(raw_ns, utc=True).tz_convert(ET)
    dates = pd.Series(timestamps.date)
    dominant = dates.value_counts().index[0]
    start = pd.Timestamp(f"{dominant} {WINDOW_START}", tz=ET).tz_convert("UTC")
    end = pd.Timestamp(f"{dominant} {WINDOW_END}", tz=ET).tz_convert("UTC")
    return int(start.value), int(end.value)


def strict_big_trade_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=["event_index", "price_ticks", "side_code"])
    timestamp = events["timestamp_ns"].to_numpy(dtype=np.int64)
    price_ticks = np.rint(events["price"].to_numpy(dtype=float) * 4).astype(np.int64)
    size = events["size"].to_numpy(dtype=np.int64)
    side = events["side"].map({"A": -1, "B": 1}).fillna(0).to_numpy(dtype=np.int8)
    rows: list[tuple[int, int, int]] = []
    anchor = 0
    total = int(size[0])
    qualified = total > BIG_TRADE_THRESHOLD
    if qualified:
        rows.append((0, int(price_ticks[0]), int(side[0])))
    for index in range(1, len(events)):
        matches = (
            timestamp[index] - timestamp[anchor] <= BIG_TRADE_WINDOW_NS
            and price_ticks[index] == price_ticks[anchor]
            and side[index] == side[anchor]
        )
        if matches:
            total += int(size[index])
            if not qualified and total > BIG_TRADE_THRESHOLD:
                rows.append((index, int(price_ticks[index]), int(side[index])))
                qualified = True
        else:
            anchor = index
            total = int(size[index])
            qualified = total > BIG_TRADE_THRESHOLD
            if qualified:
                rows.append((index, int(price_ticks[index]), int(side[index])))
    return pd.DataFrame(rows, columns=["event_index", "price_ticks", "side_code"])


def delta_state_transitions(events: pd.DataFrame) -> pd.DataFrame:
    timestamp = events["timestamp_ns"].to_numpy(dtype=np.int64)
    price_bucket = np.floor(events["price"].to_numpy(dtype=float)).astype(np.int64)
    signed = events["signed_size"].to_numpy(dtype=np.int64)
    bar_ns = (timestamp // 180_000_000_000) * 180_000_000_000
    cumulative: dict[tuple[int, int], int] = {}
    state: dict[tuple[int, int], int] = {}
    rows: list[tuple[int, int, int, int]] = []
    for index, (bar, bucket, value) in enumerate(zip(bar_ns, price_bucket, signed, strict=False)):
        key = (int(bar), int(bucket))
        total = cumulative.get(key, 0) + int(value)
        cumulative[key] = total
        new_state = 1 if total > DELTA_THRESHOLD else (-1 if total < -DELTA_THRESHOLD else 0)
        if new_state != state.get(key, 0):
            rows.append((index, key[0], key[1], new_state))
            state[key] = new_state
    return pd.DataFrame(rows, columns=["event_index", "bar_ns", "price_bucket", "state"])


def trigger_sequence_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return bool(left.shape == right.shape and np.array_equal(left.to_numpy(), right.to_numpy()))


def minute_aggregate(events: pd.DataFrame, suffix: str) -> pd.DataFrame:
    frame = events.copy()
    frame["minute"] = pd.to_datetime(frame["timestamp_ns"], utc=True).dt.floor("min")
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
    )
    return result.add_suffix(f"_{suffix}").reset_index()


def profile_aggregate(events: pd.DataFrame) -> pd.DataFrame:
    return events.groupby("price", sort=True).agg(
        volume=("size", "sum"), signed_volume=("signed_size", "sum")
    )


def bucket_delta_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    def aggregate(events: pd.DataFrame) -> pd.Series:
        bucket = np.floor(events["price"].to_numpy(dtype=float)).astype(np.int64)
        return events.assign(bucket=bucket).groupby("bucket")["signed_size"].sum()

    joined = aggregate(left).to_frame("left").join(aggregate(right).to_frame("right"), how="outer").fillna(0)
    return bool(joined["left"].eq(joined["right"]).all())


def payload_array(events: pd.DataFrame) -> np.ndarray:
    return np.column_stack(
        [
            np.rint(events["price"].to_numpy(dtype=float) * 4).astype(np.int64),
            events["size"].to_numpy(dtype=np.int64),
            events["side"].map({"A": -1, "B": 1}).fillna(0).to_numpy(dtype=np.int64),
        ]
    )


def payload_mismatch_samples(
    *,
    date: str,
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
        indexes.extend(range(aligned, min(max(len(sc_payload), len(db_payload)), aligned + limit - len(indexes))))
    rows = []
    for index in indexes:
        rows.append(
            {
                "session_date": date,
                "event_index": index,
                "sierra_price": sc.iloc[index]["price"] if index < len(sc) else None,
                "databento_price": db_events.iloc[index]["price"] if index < len(db_events) else None,
                "sierra_size": sc.iloc[index]["size"] if index < len(sc) else None,
                "databento_size": db_events.iloc[index]["size"] if index < len(db_events) else None,
                "sierra_side": sc.iloc[index]["side"] if index < len(sc) else None,
                "databento_side": db_events.iloc[index]["side"] if index < len(db_events) else None,
            }
        )
    return rows


def build_summary(
    *,
    by_date: pd.DataFrame,
    archive_path: Path,
    sierra_dir: Path,
    prior_audit: Path,
    metadata: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    def count_true(column: str) -> int:
        return int(by_date.get(column, pd.Series(dtype=bool)).fillna(False).astype(bool).sum())

    status_counts = by_date["comparison_status"].value_counts(dropna=False).to_dict()
    prior_cross = (
        by_date.groupby(["prior_status", "comparison_status"], dropna=False)
        .size()
        .rename("dates")
        .reset_index()
        .to_dict(orient="records")
    )
    return {
        "verdict": "NEEDS MANUAL REVIEW",
        "scope": {
            "window_et": f"{WINDOW_START}-{WINDOW_END}",
            "start_date": start,
            "end_date": end,
            "sessions_compared": len(by_date),
            "contract_policy": "Sierra/MotiveWave roll-calendar contract compared to the identical Databento contract",
        },
        "source": {
            "databento_archive": str(archive_path),
            "databento_archive_bytes": archive_path.stat().st_size,
            "databento_archive_sha256": sha256_file(archive_path),
            "databento_job_id": metadata.get("job_id"),
            "databento_query": metadata.get("query"),
            "sierra_dir": str(sierra_dir),
            "prior_audit": str(prior_audit),
            "prior_audit_sha256": sha256_file(prior_audit),
        },
        "normalization": {
            "sierra_unbundled_trade_policy": (
                "Collapse FIRST/LAST marker groups by price and aggressor side, summing component volume, "
                "while preserving first-appearance source order."
            ),
            "sierra_event_timestamp_policy": "Timestamp reconstructed event at the first SCID component timestamp.",
            "databento_timestamp": "ts_event",
            "timestamp_tolerance_ns": 1_000_000,
            "big_trade_rule": "strict same-price same-side uninterrupted anchor window <=100ms; total >200",
            "delta_rule": "developing 3-minute 1-point bucket state transitions at strict abs(delta)>300",
        },
        "outcome": {
            "status_counts": json_ready(status_counts),
            "payload_sequence_exact_dates": count_true("payload_sequence_exact"),
            "timestamp_all_within_1ms_dates": count_true("timestamp_all_within_1ms"),
            "minute_ohlcv_exact_dates": count_true("minute_ohlcv_exact"),
            "minute_side_volume_exact_dates": count_true("minute_side_volume_exact"),
            "profile_volume_exact_dates": count_true("profile_volume_exact"),
            "profile_delta_1tick_exact_dates": count_true("profile_delta_1tick_exact"),
            "profile_delta_4tick_exact_dates": count_true("profile_delta_4tick_exact"),
            "big_trade_trigger_sequence_exact_dates": count_true("big_trade_trigger_sequence_exact"),
            "delta_state_transition_sequence_exact_dates": count_true("delta_state_transition_sequence_exact"),
            "prior_status_cross_tab": json_ready(prior_cross),
        },
        "limitations": [
            "This validates only the compared 2025-07-14 through 2026-06-10 overlap and must not be extrapolated to older contracts.",
            "Sierra timestamps are microsecond fields derived from millisecond-quantized source times plus ordering increments; Databento ts_event remains the nanosecond reference.",
            "Databento trades are market-data trade messages, not CME MBO order-level executions.",
            "The comparison validates the specified 100ms and delta mechanics only when the reconstructed event trigger sequences agree.",
        ],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def render_report(summary: dict[str, Any], by_date: pd.DataFrame) -> str:
    outcome = summary["outcome"]
    sessions = summary["scope"]["sessions_compared"]
    equivalent = int(outcome["status_counts"].get("DATABENTO_EVENT_EQUIVALENT", 0))
    errors = int(outcome["status_counts"].get("ERROR", 0))
    prior_table = pd.DataFrame(outcome["prior_status_cross_tab"])
    prior_markdown = markdown_table(prior_table) if not prior_table.empty else "No rows."
    exceptions = by_date.loc[
        ~by_date["comparison_status"].eq("DATABENTO_EVENT_EQUIVALENT"),
        ["session_date", "prior_status", "failure_reason"],
    ]
    exception_markdown = markdown_table(exceptions) if not exceptions.empty else "No exceptions."
    return f"""# Databento versus Sierra ES tick comparison, 09:30-11:00 ET

**Verdict: {summary['verdict']}**

This audit treats the new Databento `trades` archive as the independent source of truth and compares the exact Sierra/MotiveWave-roll contract for every eligible session in the overlap. The comparison is event-sensitive: price, size, aggressor side, order, timestamp precision, volume/delta profiles, the strict 100ms big-trade trigger, and developing 3-minute delta-state transitions are tested.

## Outcome

- Eligible sessions compared: **{sessions}**
- `DATABENTO_EVENT_EQUIVALENT`: **{equivalent}**
- Comparison errors: **{errors}**
- Exact ordered event payload dates: **{outcome['payload_sequence_exact_dates']}**
- All event timestamps within 1ms of Databento `ts_event`: **{outcome['timestamp_all_within_1ms_dates']}**
- Exact minute OHLCV dates: **{outcome['minute_ohlcv_exact_dates']}**
- Exact minute aggressor-side volume dates: **{outcome['minute_side_volume_exact_dates']}**
- Exact final 1-tick delta-profile dates: **{outcome['profile_delta_1tick_exact_dates']}**
- Exact final 4-tick delta-profile dates: **{outcome['profile_delta_4tick_exact_dates']}**
- Exact strict `>200` / 100ms trigger sequence dates: **{outcome['big_trade_trigger_sequence_exact_dates']}**
- Exact developing `abs(delta)>300` transition sequence dates: **{outcome['delta_state_transition_sequence_exact_dates']}**

## Required Sierra normalization

Raw Sierra rows are not directly comparable with Databento rows because Sierra stores CME unbundled trades as FIRST/LAST-marked component records. A valid reconstruction must:

1. Preserve source-file row order.
2. Pair FIRST/LAST marker groups fail-closed.
3. Within each group, aggregate by exact trade price and aggressor side.
4. Sum component volume and retain first-appearance order.
5. Use the first component timestamp as the reconstructed event timestamp and preserve an explicit source ordinal.

Do not treat every component row as an independent Databento trade message, and do not discard the marker fields.

## Previous audit versus tick-reference result

{prior_markdown}

This table determines whether old minute-parity rejections were genuine Sierra defects or artifacts of the earlier reference/cache path. The new tick comparison takes precedence only inside this audited overlap.

## Exact exceptions

{exception_markdown}

Payload or side failures block every event-sensitive use. A `100ms_trigger_boundary_mismatch` date remains valid for profile and delta mechanics, but its Sierra timestamps cannot reproduce the Databento big-trade decision at one or more exact 100ms boundaries.

## Interpretation

`DATABENTO_EVENT_EQUIVALENT` requires exact ordered `(price, size, aggressor side)` events after reconstruction, every aligned Sierra timestamp within 1ms of Databento `ts_event`, exact profile volume and delta, and identical event-index sequences for both strategy triggers. This is sufficient for a Sierra-based replay of the specified mechanics on those dates, subject to the declared timestamp quantization.

It does not validate any earlier contract or date. Older sessions retain their previous classification until a tick source of truth is supplied for those dates.

## Artifacts

- `by_date.csv`: component-level result for every compared session
- `minute_comparison.csv`: minute OHLCV, side-volume and event-count comparison
- `event_mismatch_samples.csv`: first positional payload mismatches on failing dates
- `databento_event_equivalent_dates.txt`: exact allowlist for the newly verified lane
- `databento_profile_delta_equivalent_dates.txt`: component allowlist when the 100ms trigger is not used
- `not_event_equivalent_dates.csv`: exact exclusions and failure reasons
- `summary.json`: hashes, methodology, counts and limitations
"""


def databento_symbol(sierra_contract: str) -> str:
    if len(sierra_contract) != 5 or not sierra_contract.startswith("ES"):
        raise ValueError(f"Unexpected Sierra contract: {sierra_contract}")
    return f"{sierra_contract[:3]}{sierra_contract[-1]}"


def utc_window(date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(f"{date} {WINDOW_START}", tz=ET).tz_convert("UTC")
    end = pd.Timestamp(f"{date} {WINDOW_END}", tz=ET).tz_convert("UTC")
    return start, end


def datetime_to_scid_us(value: datetime) -> int:
    return int((value.astimezone(timezone.utc) - SCID_EPOCH).total_seconds() * 1_000_000)


def scid_us_to_unix_ns(values: np.ndarray) -> np.ndarray:
    offset_us = int((datetime(1970, 1, 1, tzinfo=timezone.utc) - SCID_EPOCH).total_seconds() * 1_000_000)
    return (values.astype(np.int64) - offset_us) * 1_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def comparison_failure_reason(row: pd.Series) -> str:
    if row.get("comparison_status") == "ERROR":
        return "comparison_error"
    if not _as_bool(row.get("payload_sequence_exact")):
        if int(row.get("databento_neutral_side_events", 0) or 0) > 0:
            return "aggressor_side_mismatch"
        return "event_payload_sequence_mismatch"
    if not _as_bool(row.get("timestamp_all_within_1ms")):
        return "timestamp_error_over_1ms"
    if not _as_bool(row.get("delta_state_transition_sequence_exact")):
        return "delta_transition_mismatch"
    if not _as_bool(row.get("big_trade_trigger_sequence_exact")):
        return "100ms_trigger_boundary_mismatch"
    if row.get("comparison_status") == "DATABENTO_EVENT_EQUIVALENT":
        return ""
    return "other_component_mismatch"


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if math.isnan(float(value)) else float(value)
    if pd.isna(value):
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
