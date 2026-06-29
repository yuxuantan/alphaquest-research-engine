from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


LARGE200_COLUMNS = [
    "large200_record_volume",
    "large200_record_signed_volume",
    "large200_record_buy_volume",
    "large200_record_sell_volume",
    "large200_record_count",
    "large200_record_max_volume",
]


def main() -> None:
    args = parse_args()
    base = pd.read_parquet(args.opening_vap_cache)
    large = pd.read_parquet(args.large200_cache)
    base["timestamp"] = pd.to_datetime(base["timestamp"])
    large["timestamp"] = pd.to_datetime(large["timestamp"])

    keep = ["timestamp", *[column for column in LARGE200_COLUMNS if column in large.columns]]
    large = large[keep].drop_duplicates("timestamp", keep="last")
    merged = base.merge(large, on="timestamp", how="left", validate="one_to_one")
    for column in LARGE200_COLUMNS:
        if column not in merged.columns:
            merged[column] = 0.0
        merged[column] = merged[column].fillna(0.0)

    merged = merged.sort_values("timestamp").reset_index(drop=True)
    args.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(args.output_parquet, index=False, compression="zstd")

    large_mask = merged["large200_record_max_volume"] >= args.min_record_volume
    report = {
        "opening_vap_cache": str(args.opening_vap_cache),
        "large200_cache": str(args.large200_cache),
        "output_parquet": str(args.output_parquet),
        "rows": int(len(merged)),
        "first_timestamp": str(merged["timestamp"].min()),
        "last_timestamp": str(merged["timestamp"].max()),
        "duplicate_timestamps": int(merged.duplicated("timestamp").sum()),
        "min_record_volume": float(args.min_record_volume),
        "bars_with_large200_record": int(large_mask.sum()),
        "sessions_with_large200_record": int(
            merged.loc[large_mask, "session_date"].nunique()
            if "session_date" in merged.columns
            else merged.loc[large_mask, "timestamp"].dt.date.nunique()
        ),
        "local_only": True,
        "source_quality_label": (
            "Completed opening-window Sierra VAP levels merged with Sierra SCID large-record proxy. "
            "Large-record fields are bar aggregates, not vendor-equivalent MBO print sequencing."
        ),
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge completed opening VAP features with ES large-200 record proxy bars."
    )
    parser.add_argument(
        "--opening-vap-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_footprint_opening_vap_1m_20110103_20260609_rth_ny.parquet"),
    )
    parser.add_argument(
        "--large200-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_large200_record_proxy_1m_20120103_20260609_rth_ny.parquet"),
    )
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--min-record-volume", type=float, default=200.0)
    return parser.parse_args()


if __name__ == "__main__":
    main()
