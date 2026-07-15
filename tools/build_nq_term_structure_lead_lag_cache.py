from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alphaquest.data.es_term_structure_lead_lag import (  # noqa: E402
    build_es_term_structure_lead_lag_frame,
    load_source_table,
    write_term_structure_cache,
)


RTH_START = "09:30:00"
RTH_END = "15:59:00"
SOURCE_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "contract_symbol",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a front-vs-next-contract NQ term-structure lead-lag cache from Databento monthly files."
    )
    parser.add_argument(
        "--front",
        default="data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet",
        help="Backtest-ready explicit-roll front-contract NQ cache.",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/cache/databento/GLBX-20260601-RTF938NJSN",
        help="Directory containing monthly Databento all-contract OHLCV parquet files.",
    )
    parser.add_argument(
        "--roll-calendar",
        default="data/reference/NQ/roll_calendars/motivewave_rithmic_roll_calendar.csv",
        help="Explicit NQ roll calendar.",
    )
    parser.add_argument(
        "--out",
        default="data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.parquet",
        help="Output parquet path.",
    )
    parser.add_argument("--csv-out", help="Optional output CSV path.")
    parser.add_argument(
        "--report-json",
        default="data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.validation.json",
        help="Output validation/report JSON path.",
    )
    parser.add_argument("--windows", default="5,15,30,60", help="Comma-separated completed windows in minutes.")
    parser.add_argument("--rth-start", default=RTH_START)
    parser.add_argument("--rth-end", default=RTH_END)
    args = parser.parse_args()

    windows = [int(item.strip()) for item in args.windows.split(",") if item.strip()]
    roll_pairs = _roll_pairs(Path(args.roll_calendar))
    front = _filter_rth(load_source_table(args.front, "NQ"), args.rth_start, args.rth_end)
    front = _select_front_periods(front, roll_pairs)
    deferred_source = _load_deferred_source(Path(args.raw_dir), {row["deferred_symbol"] for row in roll_pairs})
    deferred = _select_deferred_periods(deferred_source, roll_pairs, args.rth_start, args.rth_end)

    if front.empty:
        raise SystemExit("No front-contract NQ bars remained after roll-calendar and RTH filtering.")
    if deferred.empty:
        raise SystemExit("No deferred-contract NQ bars remained after roll-calendar and RTH filtering.")

    raw_aligned = build_es_term_structure_lead_lag_frame(front, deferred, windows=windows, root_symbol="NQ")
    ready, dropped_sessions = _drop_incomplete_aligned_sessions(raw_aligned)
    write_term_structure_cache(ready, output_parquet=args.out, output_csv=args.csv_out)

    report = {
        "front_cache": args.front,
        "raw_dir": args.raw_dir,
        "roll_calendar": args.roll_calendar,
        "output_parquet": args.out,
        "output_csv": args.csv_out,
        "windows": windows,
        "rows_before_session_policy": int(len(raw_aligned)),
        "rows": int(len(ready)),
        "sessions": int(ready["timestamp"].dt.date.nunique()) if len(ready) else 0,
        "first_timestamp": str(ready["timestamp"].min()) if len(ready) else None,
        "last_timestamp": str(ready["timestamp"].max()) if len(ready) else None,
        "front_rows_after_rth_filter": int(len(front)),
        "deferred_rows_after_rth_filter": int(len(deferred)),
        "dropped_sessions": int(len(dropped_sessions)),
        "dropped_sessions_by_reason": dropped_sessions["reason"].value_counts().to_dict()
        if not dropped_sessions.empty
        else {},
        "validation": _validate_ready(ready),
        "periods": _period_report(front, deferred, roll_pairs),
        "lookahead_policy": {
            "front_contract_selection": "prebuilt explicit roll calendar active-contract cache",
            "deferred_contract_selection": "next explicit roll-calendar contract; no same-day volume choice",
            "feature_timing": "completed bars only; strategy entry modules signal at bar close for next-bar execution",
            "source_timezone": "America/New_York naive timestamps in output",
        },
    }
    report_path = Path(args.report_json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    print(
        json.dumps(
            {key: report[key] for key in ["rows", "sessions", "first_timestamp", "last_timestamp", "validation"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _roll_pairs(roll_calendar: Path) -> list[dict]:
    calendar = pd.read_csv(roll_calendar)
    starts = pd.to_datetime(calendar["start_timestamp"], utc=True)
    calendar = (
        calendar.assign(
            start_et=starts.dt.tz_convert("America/New_York").dt.tz_localize(None),
            contract_symbol=calendar["contract_symbol"].astype(str),
        )
        .sort_values("start_et")
        .reset_index(drop=True)
    )
    calendar["end_et"] = calendar["start_et"].shift(-1)
    rows = []
    for idx in range(len(calendar) - 1):
        rows.append(
            {
                "front_symbol": str(calendar.loc[idx, "contract_symbol"]),
                "deferred_symbol": str(calendar.loc[idx + 1, "contract_symbol"]),
                "start_et": calendar.loc[idx, "start_et"],
                "end_et": calendar.loc[idx, "end_et"],
            }
        )
    return rows


def _load_deferred_source(raw_dir: Path, needed_symbols: set[str]) -> pd.DataFrame:
    parts = []
    for path in sorted(raw_dir.glob("*.parquet")):
        df = pd.read_parquet(path, columns=SOURCE_COLUMNS)
        df = df[df["contract_symbol"].astype(str).isin(needed_symbols)].copy()
        if df.empty:
            continue
        df["timestamp"] = _parse_timestamp(df["timestamp"])
        df = df[~df["contract_symbol"].astype(str).str.contains("-", regex=False)]
        parts.append(df)
    if not parts:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    out = pd.concat(parts, ignore_index=True)
    return (
        out.drop_duplicates(subset=["timestamp", "contract_symbol"], keep="last")
        .sort_values(["timestamp", "contract_symbol"])
        .reset_index(drop=True)
    )


def _select_front_periods(front: pd.DataFrame, roll_pairs: list[dict]) -> pd.DataFrame:
    parts = []
    for row in roll_pairs:
        mask = (
            front["contract_symbol"].astype(str).eq(row["front_symbol"])
            & (front["timestamp"] >= row["start_et"])
            & (front["timestamp"] < row["end_et"])
        )
        period = front.loc[mask]
        if not period.empty:
            parts.append(period)
    if not parts:
        return front.iloc[:0].copy()
    return pd.concat(parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def _select_deferred_periods(
    source: pd.DataFrame,
    roll_pairs: list[dict],
    rth_start: str,
    rth_end: str,
) -> pd.DataFrame:
    source = _filter_rth(source, rth_start, rth_end)
    parts = []
    for row in roll_pairs:
        mask = (
            source["contract_symbol"].astype(str).eq(row["deferred_symbol"])
            & (source["timestamp"] >= row["start_et"])
            & (source["timestamp"] < row["end_et"])
        )
        period = source.loc[mask]
        if not period.empty:
            parts.append(period)
    if not parts:
        return source.iloc[:0].copy()
    return pd.concat(parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def _filter_rth(df: pd.DataFrame, rth_start: str, rth_end: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    start = pd.to_datetime(rth_start).time()
    end = pd.to_datetime(rth_end).time()
    out = df.copy()
    out["timestamp"] = _parse_timestamp(out["timestamp"])
    mask = (out["timestamp"].dt.time >= start) & (out["timestamp"].dt.time <= end)
    return out.loc[mask].sort_values("timestamp").reset_index(drop=True)


def _parse_timestamp(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values)
    if timestamps.dt.tz is not None:
        timestamps = timestamps.dt.tz_convert("America/New_York").dt.tz_localize(None)
    return timestamps


def _drop_incomplete_aligned_sessions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), pd.DataFrame()
    work = df.sort_values("timestamp").reset_index(drop=True).copy()
    work["_session_date"] = work["timestamp"].dt.date
    dropped = []
    keep_dates = []
    for session_date, group in work.groupby("_session_date", sort=True):
        minutes = pd.DatetimeIndex(group["timestamp"])
        expected = pd.date_range(minutes.min(), minutes.max(), freq="1min")
        missing = expected.difference(minutes)
        if len(group) == 390 and not len(missing):
            keep_dates.append(session_date)
            continue
        dropped.append(
            {
                "session_date": session_date.isoformat(),
                "rows": int(len(group)),
                "missing_minutes": int(len(missing)),
                "reason": "incomplete_front_deferred_alignment",
            }
        )
    ready = work[work["_session_date"].isin(keep_dates)].drop(columns=["_session_date"]).reset_index(drop=True)
    return ready, pd.DataFrame(dropped)


def _validate_ready(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"duplicate_timestamps": 0, "invalid_ohlc_rows": 0, "missing_session_segments": 0}
    price_columns = [
        "open",
        "high",
        "low",
        "close",
        "deferred_open",
        "deferred_high",
        "deferred_low",
        "deferred_close",
    ]
    invalid_ohlc = int(
        (
            ~(
                (df["high"] >= df["open"])
                & (df["high"] >= df["close"])
                & (df["low"] <= df["open"])
                & (df["low"] <= df["close"])
                & (df["deferred_high"] >= df["deferred_open"])
                & (df["deferred_high"] >= df["deferred_close"])
                & (df["deferred_low"] <= df["deferred_open"])
                & (df["deferred_low"] <= df["deferred_close"])
                & (df[price_columns] > 0).all(axis=1)
                & (df["volume"] > 0)
                & (df["deferred_volume"] > 0)
            )
        ).sum()
    )
    missing_segments = 0
    for _, group in df.assign(session_date=df["timestamp"].dt.date).groupby("session_date", sort=True):
        minutes = pd.DatetimeIndex(group["timestamp"])
        expected = pd.date_range(minutes.min(), minutes.max(), freq="1min")
        missing_segments += int(len(expected.difference(minutes)) > 0)
        if len(minutes) != 390:
            missing_segments += 1
    return {
        "duplicate_timestamps": int(df.duplicated(subset=["timestamp"]).sum()),
        "invalid_ohlc_rows": invalid_ohlc,
        "missing_session_segments": missing_segments,
        "front_contracts": int(df["contract_symbol"].nunique()),
        "deferred_contracts": int(df["deferred_contract_symbol"].nunique()),
    }


def _period_report(front: pd.DataFrame, deferred: pd.DataFrame, roll_pairs: list[dict]) -> list[dict]:
    rows = []
    for pair in roll_pairs:
        front_period = front[
            front["contract_symbol"].astype(str).eq(pair["front_symbol"])
            & (front["timestamp"] >= pair["start_et"])
            & (front["timestamp"] < pair["end_et"])
        ]
        deferred_period = deferred[
            deferred["contract_symbol"].astype(str).eq(pair["deferred_symbol"])
            & (deferred["timestamp"] >= pair["start_et"])
            & (deferred["timestamp"] < pair["end_et"])
        ]
        if front_period.empty and deferred_period.empty:
            status = "no_front_or_deferred_overlap"
        elif front_period.empty:
            status = "no_front_overlap"
        elif deferred_period.empty:
            status = "no_deferred_overlap"
        else:
            status = "selected"
        rows.append(
            {
                **pair,
                "status": status,
                "front_rows": int(len(front_period)),
                "deferred_rows": int(len(deferred_period)),
            }
        )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
