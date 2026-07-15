from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_SOURCE = Path(
    "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
)
DEFAULT_AUDIT = Path(
    "data/reports/data_quality/ES/"
    "sierra_scid_event_usability_0930_1100_20101214_20260610_by_date.csv"
)
DEFAULT_OUTPUT = Path(
    "data/cache/price_only/es_sierra_price_only_tpo_1m_20110815_20260609_0930_1100_ny.parquet"
)


def main() -> None:
    args = parse_args()
    audit = pd.read_csv(args.audit)
    required = {
        "session_date",
        "strategy_session_eligible",
        "raw_structure_pass",
        "current_filtered_cache_minutes",
    }
    missing = sorted(required - set(audit.columns))
    if missing:
        raise ValueError(f"Audit is missing required columns: {missing}")

    allowed = audit.loc[
        audit["strategy_session_eligible"].fillna(False).astype(bool)
        & audit["raw_structure_pass"].fillna(False).astype(bool)
        & audit["current_filtered_cache_minutes"].eq(90),
        "session_date",
    ].astype(str)
    allowed_dates = frozenset(allowed)

    columns = [
        "timestamp",
        "symbol",
        "contract_symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trades",
    ]
    source = pd.read_parquet(args.source, columns=columns)
    source["timestamp"] = pd.to_datetime(source["timestamp"])
    session_dates = source["timestamp"].dt.date.astype(str)
    times = source["timestamp"].dt.time
    morning = source.loc[
        session_dates.isin(allowed_dates)
        & (times >= pd.Timestamp("09:30:00").time())
        & (times < pd.Timestamp("11:00:00").time())
    ].copy()
    morning["session_date"] = morning["timestamp"].dt.date.astype(str)
    morning["is_rth"] = True
    morning["source_capability"] = "completed_bar_price_only"
    morning = morning.sort_values("timestamp", kind="mergesort").reset_index(drop=True)

    counts = morning.groupby("session_date", sort=True).size()
    invalid = counts[counts.ne(90)]
    if not invalid.empty:
        raise ValueError(f"Derived cache contains non-90-minute sessions: {invalid.to_dict()}")
    if morning["timestamp"].duplicated().any():
        raise ValueError("Derived cache contains duplicate timestamps")
    if not ((morning["high"] >= morning[["open", "close"]].max(axis=1)).all()):
        raise ValueError("Derived cache contains high/open-close inversions")
    if not ((morning["low"] <= morning[["open", "close"]].min(axis=1)).all()):
        raise ValueError("Derived cache contains low/open-close inversions")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    morning.to_parquet(args.output, index=False, compression="zstd")

    report = {
        "dataset_id": args.output.stem,
        "output": str(args.output),
        "source": str(args.source),
        "source_audit": str(args.audit),
        "rows": int(len(morning)),
        "sessions": int(morning["session_date"].nunique()),
        "first_timestamp": str(morning["timestamp"].min()),
        "last_timestamp": str(morning["timestamp"].max()),
        "session_window": "09:30:00-11:00:00 America/New_York, end exclusive",
        "session_gate": (
            "strategy_session_eligible AND raw_structure_pass AND "
            "current_filtered_cache_minutes == 90"
        ),
        "allowed_features": ["completed one-minute OHLC", "TPO/time-at-price", "opening range"],
        "prohibited_features": [
            "aggressor side",
            "bid/ask delta",
            "trade event size or count",
            "100ms sequencing",
            "volume profile",
        ],
        "known_limitations": [
            "Older sessions are internally screened, not independently event-verified.",
            "The cache retains volume/trades only for the loader contract; this campaign must not use them.",
            "Historical high-impact USD news windows are not supplied by this dataset.",
        ],
    }
    report_path = args.report or args.output.with_suffix(".validation.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the internally gated Sierra price-only TPO lane.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    main()
