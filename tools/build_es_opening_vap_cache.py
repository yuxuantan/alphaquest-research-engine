from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.build_sierra_footprint_feature_cache import (  # noqa: E402
    _filter_periods,
    aggregate_footprint_price_volume_period,
)
from tools.build_sierra_trade_orderflow_cache import active_periods, is_bar_like_contract  # noqa: E402
from tools.build_sierra_vap_profile_cache import compute_session_profile  # noqa: E402


def main() -> None:
    args = parse_args()
    base = pd.read_parquet(args.base_cache)
    base["timestamp"] = pd.to_datetime(base["timestamp"])
    if args.start_date:
        base = base[base["timestamp"] >= pd.Timestamp(args.start_date)].copy()
    if args.end_date:
        base = base[base["timestamp"] < pd.Timestamp(args.end_date) + pd.Timedelta(days=1)].copy()
    if base.empty:
        raise SystemExit("Base cache selection is empty.")

    files = {path.stem.replace("-CME", ""): path for path in args.raw_dir.glob("*.parquet")}
    periods = active_periods(args.roll_calendar, files, args.root_symbol)
    periods = _filter_periods(periods, base["timestamp"].min(), base["timestamp"].max())
    if not periods:
        raise SystemExit("No active raw Sierra periods overlap the selected base cache range.")

    session_parts = []
    period_reports = []
    for idx, period in enumerate(periods, start=1):
        symbol = period["symbol"]
        path = period["path"]
        if is_bar_like_contract(symbol, path):
            period_reports.append({"symbol": symbol, "status": "skipped_bar_like"})
            continue
        print(f"[{idx}/{len(periods)}] opening VAP {symbol}: {path.name}", flush=True)
        price_volume = aggregate_footprint_price_volume_period(
            path,
            start=period["start"],
            end=period["end"],
            tick_size=args.tick_size,
            batch_size=args.batch_size,
        )
        if price_volume.empty:
            period_reports.append({"symbol": symbol, "status": "empty_price_volume"})
            continue
        price_volume["timestamp"] = pd.to_datetime(price_volume["timestamp"])
        price_volume["session_date"] = price_volume["timestamp"].dt.date
        session_parts.append(price_volume)
        period_reports.append(
            {
                "symbol": symbol,
                "status": "built",
                "price_volume_rows": int(len(price_volume)),
                "sessions": int(price_volume["session_date"].nunique()),
            }
        )

    if not session_parts:
        raise SystemExit("No price-volume rows were built.")

    price_volume = pd.concat(session_parts, ignore_index=True)
    profiles = {}
    for window in args.window_minutes:
        profiles[window] = opening_profiles(
            price_volume,
            window_minutes=window,
            value_area_fraction=args.value_area_fraction,
            lvn_quantile=args.lvn_quantile,
        )

    out = merge_opening_profiles(base, profiles, tick_size=args.tick_size)
    out = out.sort_values("timestamp").reset_index(drop=True)
    args.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.output_parquet, index=False, compression="zstd")

    report = {
        "base_cache": str(args.base_cache),
        "raw_dir": str(args.raw_dir),
        "roll_calendar": str(args.roll_calendar),
        "output_parquet": str(args.output_parquet),
        "rows": int(len(out)),
        "first_timestamp": str(out["timestamp"].min()),
        "last_timestamp": str(out["timestamp"].max()),
        "tick_size": args.tick_size,
        "value_area_fraction": args.value_area_fraction,
        "lvn_quantile": args.lvn_quantile,
        "window_minutes": args.window_minutes,
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()),
        "local_only": True,
        "source_quality_label": (
            "Sierra SCID-derived opening-window volume-at-price levels. "
            "Each window is merged only after the corresponding opening window is complete; "
            "not MBO/queue data and not vendor-equivalent print sequencing."
        ),
        "profile_counts": {
            str(window): {
                "sessions": int(len(profile)),
                "bars_with_poc": int(out[f"opening{window}_vap_poc"].notna().sum()),
            }
            for window, profile in profiles.items()
        },
        "periods": period_reports,
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "duplicate_timestamps": report["duplicate_timestamps"],
                "profile_counts": report["profile_counts"],
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build completed opening-window Sierra VAP levels and merge them onto ES RTH bars."
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/ES/sierra-es-trades"))
    parser.add_argument(
        "--roll-calendar",
        type=Path,
        default=Path("data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv"),
    )
    parser.add_argument(
        "--base-cache",
        type=Path,
        default=Path("data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet"),
    )
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--window-minutes", type=int, nargs="+", default=[30, 60])
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--value-area-fraction", type=float, default=0.70)
    parser.add_argument("--lvn-quantile", type=float, default=0.20)
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    return parser.parse_args()


def opening_profiles(
    price_volume: pd.DataFrame,
    *,
    window_minutes: int,
    value_area_fraction: float,
    lvn_quantile: float,
) -> pd.DataFrame:
    if window_minutes <= 0:
        raise ValueError("window_minutes must be positive.")
    timestamps = pd.to_datetime(price_volume["timestamp"])
    minute_of_day = timestamps.dt.hour * 60 + timestamps.dt.minute
    start_minute = 9 * 60 + 30
    end_minute = start_minute + int(window_minutes)
    work = price_volume[(minute_of_day >= start_minute) & (minute_of_day < end_minute)].copy()
    if work.empty:
        return pd.DataFrame(columns=["session_date"])

    rows = []
    for session_date, group in work.groupby("session_date", sort=True, observed=True):
        by_price = (
            group.groupby("price", sort=True, observed=True)
            .agg(volume=("volume", "sum"))
            .reset_index()
        )
        if by_price.empty:
            continue
        profile = compute_session_profile(
            by_price,
            session_high=float(by_price["price"].max()),
            session_low=float(by_price["price"].min()),
            value_area_fraction=value_area_fraction,
            lvn_quantile=lvn_quantile,
        )
        if profile is None:
            continue
        profile["session_date"] = session_date
        profile["opening_vap_window_minutes"] = int(window_minutes)
        profile["opening_vap_session_yyyymmdd"] = int(pd.Timestamp(session_date).strftime("%Y%m%d"))
        rows.append(profile)
    if not rows:
        return pd.DataFrame(columns=["session_date"])
    return pd.DataFrame(rows).sort_values("session_date").reset_index(drop=True)


def merge_opening_profiles(
    base: pd.DataFrame,
    profiles_by_window: dict[int, pd.DataFrame],
    *,
    tick_size: float,
) -> pd.DataFrame:
    out = base.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    out["session_date"] = pd.to_datetime(out.get("session_date", out["timestamp"].dt.date)).dt.date
    for window, profiles in profiles_by_window.items():
        prefix = f"opening{window}_vap"
        columns = {
            "opening_vap_session_yyyymmdd": f"{prefix}_session_yyyymmdd",
            "vap_poc": f"{prefix}_poc",
            "vap_vah": f"{prefix}_vah",
            "vap_val": f"{prefix}_val",
            "vap_lvn_near_high": f"{prefix}_lvn_near_high",
            "vap_lvn_near_low": f"{prefix}_lvn_near_low",
            "vap_lvn_count": f"{prefix}_lvn_count",
            "vap_total_volume": f"{prefix}_total_volume",
            "vap_price_levels": f"{prefix}_price_levels",
            "opening_vap_window_minutes": f"{prefix}_window_minutes",
        }
        if profiles.empty:
            for output_column in columns.values():
                out[output_column] = np.nan
            continue
        merge_cols = ["session_date", *columns.keys()]
        renamed = profiles[merge_cols].rename(columns=columns)
        out = out.merge(renamed, on="session_date", how="left", validate="many_to_one")
        ready_time = (pd.Timestamp("09:30:00") + pd.Timedelta(minutes=int(window))).time()
        ready_mask = out["timestamp"].dt.time >= ready_time
        for output_column in columns.values():
            out.loc[~ready_mask, output_column] = np.nan
        out[f"{prefix}_tick_size"] = tick_size
    return out


if __name__ == "__main__":
    main()
