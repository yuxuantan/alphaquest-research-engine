from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


OVERNIGHT_COLUMNS = [
    "overnight_high",
    "overnight_low",
    "overnight_midpoint",
    "overnight_range_points",
    "overnight_return_points",
    "overnight_volume",
    "overnight_bars",
    "overnight_range_rank_252",
    "overnight_range_mean_252_prior",
    "overnight_range_median_252_prior",
]


def main() -> None:
    args = parse_args()
    base = pd.read_parquet(args.base_cache)
    base["timestamp"] = pd.to_datetime(base["timestamp"])
    if args.start_date:
        base = base[base["timestamp"] >= pd.Timestamp(args.start_date)].copy()
    if args.end_date:
        base = base[base["timestamp"] < pd.Timestamp(args.end_date) + pd.Timedelta(days=1)].copy()
    overnight = pd.read_csv(args.overnight_features)
    out, report = merge_completed_overnight_features(base, overnight)

    args.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.output_parquet, index=False, compression="zstd")

    report = {
        **report,
        "base_cache": str(args.base_cache),
        "overnight_features": str(args.overnight_features),
        "output_parquet": str(args.output_parquet),
        "local_only": True,
        "source_quality_label": (
            "Sierra RTH footprint/VAP cache merged with completed overnight range levels "
            "ending no later than 09:29 ET for the same RTH session."
        ),
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "bars_with_overnight_levels": report["bars_with_overnight_levels"],
                "sessions_with_overnight_features": report["sessions_with_overnight_features"],
                "missing_overnight_sessions": report["missing_overnight_sessions"],
                "bad_overnight_window_rows": report["bad_overnight_window_rows"],
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge completed ES overnight range features onto the Sierra footprint/VAP RTH cache."
    )
    parser.add_argument(
        "--base-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_footprint_vap_profile_1m_20101214_20260610_full_rth_ny.parquet"),
    )
    parser.add_argument(
        "--overnight-features",
        type=Path,
        default=Path("data/external/es_overnight_range_features_20110103_20260529.csv"),
    )
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def merge_completed_overnight_features(
    base: pd.DataFrame,
    overnight: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    if base.empty:
        out = base.copy()
        for column in OVERNIGHT_COLUMNS:
            out[column] = pd.NA
        return out, _report(out, overnight, missing_sessions=0, bad_windows=0)

    out = base.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    out["session_date"] = pd.to_datetime(out.get("session_date", out["timestamp"].dt.date)).dt.date

    required = {"session_date", "overnight_start", "overnight_end", *OVERNIGHT_COLUMNS}
    missing = required - set(overnight.columns)
    if missing:
        raise ValueError(f"Overnight feature file missing required columns: {sorted(missing)}")

    overnight_clean = overnight.copy()
    overnight_clean["session_date"] = pd.to_datetime(overnight_clean["session_date"]).dt.date
    overnight_clean["overnight_start"] = pd.to_datetime(overnight_clean["overnight_start"], utc=True)
    overnight_clean["overnight_end"] = pd.to_datetime(overnight_clean["overnight_end"], utc=True)
    for column in OVERNIGHT_COLUMNS:
        overnight_clean[column] = pd.to_numeric(overnight_clean[column], errors="coerce")

    bad_window_mask = _bad_overnight_window_mask(overnight_clean)
    join_columns = ["session_date", *OVERNIGHT_COLUMNS]
    merged = out.merge(overnight_clean[join_columns], on="session_date", how="left", validate="many_to_one")

    base_sessions = set(out["session_date"].dropna().unique())
    overnight_sessions = set(overnight_clean["session_date"].dropna().unique())
    missing_sessions = len(base_sessions - overnight_sessions)
    report = _report(
        merged,
        overnight_clean,
        missing_sessions=missing_sessions,
        bad_windows=int(bad_window_mask.sum()),
    )
    return merged, report


def _bad_overnight_window_mask(overnight: pd.DataFrame) -> pd.Series:
    local_end = overnight["overnight_end"].dt.tz_convert("America/New_York")
    session_dates = pd.to_datetime(overnight["session_date"]).dt.date
    return (local_end.dt.date != session_dates) | (local_end.dt.time > pd.Timestamp("09:29:59").time())


def _report(
    out: pd.DataFrame,
    overnight: pd.DataFrame,
    *,
    missing_sessions: int,
    bad_windows: int,
) -> dict:
    return {
        "rows": int(len(out)),
        "first_timestamp": str(out["timestamp"].min()) if "timestamp" in out and len(out) else None,
        "last_timestamp": str(out["timestamp"].max()) if "timestamp" in out and len(out) else None,
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()) if "timestamp" in out else 0,
        "bars_with_overnight_levels": int(out["overnight_high"].notna().sum()) if "overnight_high" in out else 0,
        "sessions_with_overnight_features": int(overnight["session_date"].nunique()) if "session_date" in overnight else 0,
        "missing_overnight_sessions": int(missing_sessions),
        "bad_overnight_window_rows": int(bad_windows),
        "overnight_columns": OVERNIGHT_COLUMNS,
    }


if __name__ == "__main__":
    main()
