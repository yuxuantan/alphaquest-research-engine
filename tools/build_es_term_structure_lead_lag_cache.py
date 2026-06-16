from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from propstack.data.es_term_structure_lead_lag import (  # noqa: E402
    build_es_term_structure_lead_lag_frame,
    load_source_table,
    write_term_structure_cache,
)
from tools.build_sierra_trade_orderflow_cache import (  # noqa: E402
    aggregate_active_period,
    parquet_timestamp_bounds,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a front-vs-next-contract ES term-structure lead-lag cache."
    )
    parser.add_argument(
        "--front",
        default="data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet",
        help="Backtest-ready front-contract ES cache.",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw/ES/sierra-es-trades",
        help="Directory containing one Sierra Parquet file per ES contract.",
    )
    parser.add_argument(
        "--roll-calendar",
        default="data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv",
        help="Explicit ES roll calendar.",
    )
    parser.add_argument(
        "--out",
        default="data/cache/orderflow/es_term_structure_lead_lag_1m_20110311_20260316_full_rth_ny.parquet",
        help="Output parquet path.",
    )
    parser.add_argument("--csv-out", help="Optional output CSV path.")
    parser.add_argument(
        "--report-json",
        default="data/cache/orderflow/es_term_structure_lead_lag_1m_20110311_20260316_full_rth_ny.validation.json",
        help="Output validation/report JSON path.",
    )
    parser.add_argument("--windows", default="5,15,30,60", help="Comma-separated completed windows in minutes.")
    parser.add_argument("--batch-size", type=int, default=2_000_000)
    args = parser.parse_args()

    windows = [int(item.strip()) for item in args.windows.split(",") if item.strip()]
    front = load_source_table(args.front, "ES")
    raw_files = {path.stem.replace("-CME", ""): path for path in Path(args.raw_dir).glob("*.parquet")}
    pairs = _roll_pairs(Path(args.roll_calendar), raw_files)
    front_contracts = set(front["contract_symbol"].astype(str).unique())

    deferred_parts = []
    period_reports = []
    for pair in pairs:
        front_symbol = pair["front_symbol"]
        deferred_symbol = pair["deferred_symbol"]
        if front_symbol not in front_contracts:
            continue
        deferred_path = raw_files.get(deferred_symbol)
        if deferred_path is None:
            period_reports.append({**pair, "status": "missing_deferred_file"})
            continue
        file_start, file_end = parquet_timestamp_bounds(deferred_path)
        start = max(pair["start_utc"], file_start)
        end = min(pair["end_utc"], file_end)
        if start > end:
            period_reports.append({**pair, "status": "no_deferred_overlap"})
            continue
        print(f"Aggregate deferred {deferred_symbol} for front {front_symbol}: {start} to {end}", flush=True)
        deferred = aggregate_active_period(
            deferred_path,
            root_symbol="ES",
            symbol=deferred_symbol,
            start=start,
            end=end,
            batch_size=args.batch_size,
        )
        period_reports.append(
            {
                **pair,
                "status": "aggregated",
                "deferred_rows": int(len(deferred)),
                "first_deferred_timestamp": str(deferred["timestamp"].min()) if len(deferred) else None,
                "last_deferred_timestamp": str(deferred["timestamp"].max()) if len(deferred) else None,
            }
        )
        if not deferred.empty:
            deferred_parts.append(deferred)

    if not deferred_parts:
        raise SystemExit("No deferred contract bars were aggregated.")

    deferred_all = pd.concat(deferred_parts, ignore_index=True)
    raw_aligned = build_es_term_structure_lead_lag_frame(front, deferred_all, windows=windows)
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
        "dropped_sessions": int(len(dropped_sessions)),
        "dropped_sessions_by_reason": dropped_sessions["reason"].value_counts().to_dict()
        if not dropped_sessions.empty
        else {},
        "missing_deferred_files": [
            row["deferred_symbol"] for row in period_reports if row["status"] == "missing_deferred_file"
        ],
        "periods": period_reports,
        "validation": _validate_ready(ready),
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
    print(json.dumps({k: report[k] for k in ["rows", "sessions", "first_timestamp", "last_timestamp", "missing_deferred_files"]}, indent=2))
    return 0


def _roll_pairs(roll_calendar: Path, raw_files: dict[str, Path]) -> list[dict]:
    calendar = pd.read_csv(roll_calendar)
    starts_utc = pd.to_datetime(calendar["start_timestamp"], utc=True)
    starts_et = starts_utc.dt.tz_convert("America/New_York").dt.tz_localize(None)
    calendar = (
        calendar.assign(
            start_utc=starts_utc.dt.tz_localize(None),
            start_et=starts_et,
        )
        .sort_values("start_utc")
        .reset_index(drop=True)
    )
    calendar["end_utc"] = calendar["start_utc"].shift(-1)
    calendar["file_symbol"] = [
        _roll_contract_to_file_symbol(start, contract)
        for start, contract in zip(calendar["start_et"], calendar["contract_symbol"], strict=False)
    ]
    rows = []
    for idx in range(len(calendar) - 1):
        front_symbol = str(calendar.loc[idx, "file_symbol"])
        deferred_symbol = str(calendar.loc[idx + 1, "file_symbol"])
        if front_symbol not in raw_files:
            continue
        rows.append(
            {
                "front_symbol": front_symbol,
                "deferred_symbol": deferred_symbol,
                "start_utc": calendar.loc[idx, "start_utc"].to_pydatetime(),
                "end_utc": calendar.loc[idx, "end_utc"].to_pydatetime(),
            }
        )
    return rows


def _roll_contract_to_file_symbol(start_et: pd.Timestamp, contract: str) -> str:
    month = next(char for char in str(contract) if char in {"H", "M", "U", "Z"})
    year = start_et.year + 1 if month == "H" else start_et.year
    return f"ES{month}{year % 100:02d}"


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
    invalid_ohlc = int(
        (~(
            (df["high"] >= df["open"])
            & (df["high"] >= df["close"])
            & (df["low"] <= df["open"])
            & (df["low"] <= df["close"])
            & (df["deferred_high"] >= df["deferred_open"])
            & (df["deferred_high"] >= df["deferred_close"])
            & (df["deferred_low"] <= df["deferred_open"])
            & (df["deferred_low"] <= df["deferred_close"])
            & (df[["open", "high", "low", "close", "deferred_open", "deferred_high", "deferred_low", "deferred_close"]] > 0).all(axis=1)
            & (df["volume"] > 0)
            & (df["deferred_volume"] > 0)
        )).sum()
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


if __name__ == "__main__":
    raise SystemExit(main())
