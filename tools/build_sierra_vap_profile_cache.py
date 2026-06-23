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


PROFILE_COLUMNS = [
    "prior_vap_session_yyyymmdd",
    "prior_vap_poc",
    "prior_vap_vah",
    "prior_vap_val",
    "prior_vap_lvn_near_high",
    "prior_vap_lvn_near_low",
    "prior_vap_lvn_count",
    "prior_vap_total_volume",
    "prior_vap_price_levels",
]


def main() -> None:
    args = parse_args()
    base = pd.read_parquet(args.base_cache)
    base["timestamp"] = pd.to_datetime(base["timestamp"])
    if args.start_date:
        base = base[base["timestamp"] >= pd.Timestamp(args.start_date)].copy()
    if args.end_date:
        base = base[base["timestamp"] <= pd.Timestamp(args.end_date) + pd.Timedelta(days=1)].copy()
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

        print(f"[{idx}/{len(periods)}] VAP profile {symbol}: {path.name}", flush=True)
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
        price_volume["session_date"] = pd.to_datetime(price_volume["timestamp"]).dt.date
        session_price_volume = (
            price_volume.groupby(["session_date", "price"], sort=True, observed=True)
            .agg(volume=("volume", "sum"))
            .reset_index()
        )
        session_parts.append(session_price_volume)
        period_reports.append(
            {
                "symbol": symbol,
                "status": "built",
                "price_volume_rows": int(len(price_volume)),
                "session_price_rows": int(len(session_price_volume)),
                "sessions": int(session_price_volume["session_date"].nunique()),
            }
        )

    if not session_parts:
        raise SystemExit("No session price-volume rows were built.")

    session_price_volume = pd.concat(session_parts, ignore_index=True)
    session_price_volume = (
        session_price_volume.groupby(["session_date", "price"], sort=True, observed=True)
        .agg(volume=("volume", "sum"))
        .reset_index()
    )
    daily = session_daily_bounds(base)
    profiles = session_profiles_from_price_volume(
        session_price_volume,
        daily=daily,
        value_area_fraction=args.value_area_fraction,
        lvn_quantile=args.lvn_quantile,
    )
    out = merge_prior_profiles(base, profiles)
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
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()),
        "profile_sessions": int(len(profiles)),
        "bars_with_prior_profile": int(out["prior_vap_poc"].notna().sum()),
        "local_only": True,
        "source_quality_label": (
            "Sierra SCID-derived completed previous-session volume-at-price profile; "
            "not MBO/queue data and not vendor-equivalent print sequencing."
        ),
        "profile_columns": PROFILE_COLUMNS,
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
                "profile_sessions": report["profile_sessions"],
                "bars_with_prior_profile": report["bars_with_prior_profile"],
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build prior-session Sierra volume-at-price profile levels and merge them onto ES bars."
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
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--value-area-fraction", type=float, default=0.70)
    parser.add_argument("--lvn-quantile", type=float, default=0.20)
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    return parser.parse_args()


def session_daily_bounds(base: pd.DataFrame) -> pd.DataFrame:
    work = base.copy()
    work["session_date"] = pd.to_datetime(work["timestamp"]).dt.date
    return (
        work.groupby("session_date", sort=True, observed=True)
        .agg(session_high=("high", "max"), session_low=("low", "min"), bars=("timestamp", "count"))
        .reset_index()
    )


def session_profiles_from_price_volume(
    session_price_volume: pd.DataFrame,
    *,
    daily: pd.DataFrame,
    value_area_fraction: float = 0.70,
    lvn_quantile: float = 0.20,
) -> pd.DataFrame:
    if not 0 < value_area_fraction <= 1:
        raise ValueError("value_area_fraction must be in (0, 1].")
    if not 0 < lvn_quantile < 1:
        raise ValueError("lvn_quantile must be in (0, 1).")
    daily_by_session = daily.set_index("session_date")
    rows = []
    for session_date, group in session_price_volume.groupby("session_date", sort=True, observed=True):
        daily_row = daily_by_session.loc[session_date] if session_date in daily_by_session.index else None
        if daily_row is None:
            continue
        profile = compute_session_profile(
            group[["price", "volume"]],
            session_high=float(daily_row["session_high"]),
            session_low=float(daily_row["session_low"]),
            value_area_fraction=value_area_fraction,
            lvn_quantile=lvn_quantile,
        )
        if profile is None:
            continue
        profile["session_date"] = session_date
        profile["vap_session_yyyymmdd"] = int(pd.Timestamp(session_date).strftime("%Y%m%d"))
        rows.append(profile)
    if not rows:
        return pd.DataFrame(columns=["session_date"])
    return pd.DataFrame(rows).sort_values("session_date").reset_index(drop=True)


def compute_session_profile(
    price_volume: pd.DataFrame,
    *,
    session_high: float,
    session_low: float,
    value_area_fraction: float,
    lvn_quantile: float,
) -> dict | None:
    work = price_volume.copy()
    work["price"] = pd.to_numeric(work["price"], errors="coerce")
    work["volume"] = pd.to_numeric(work["volume"], errors="coerce")
    work = work.dropna(subset=["price", "volume"])
    work = work[(work["price"] > 0) & (work["volume"] > 0)]
    if work.empty:
        return None

    grouped = work.groupby("price", sort=True, observed=True)["volume"].sum()
    prices = grouped.index.to_numpy(dtype=float)
    volumes = grouped.to_numpy(dtype=float)
    total_volume = float(volumes.sum())
    if total_volume <= 0:
        return None

    midpoint = (float(session_high) + float(session_low)) / 2.0
    poc_pos = max(range(len(prices)), key=lambda idx: (volumes[idx], -abs(prices[idx] - midpoint)))
    val_pos, vah_pos = value_area_positions(volumes, poc_pos, value_area_fraction)
    lvn_threshold = float(np.quantile(volumes, lvn_quantile, method="nearest"))
    lvn_prices = prices[volumes <= lvn_threshold]
    return {
        "vap_poc": float(prices[poc_pos]),
        "vap_vah": float(prices[vah_pos]),
        "vap_val": float(prices[val_pos]),
        "vap_lvn_near_high": nearest_level(lvn_prices, float(session_high)),
        "vap_lvn_near_low": nearest_level(lvn_prices, float(session_low)),
        "vap_lvn_count": int(len(lvn_prices)),
        "vap_total_volume": total_volume,
        "vap_price_levels": int(len(prices)),
    }


def value_area_positions(volumes: np.ndarray, poc_pos: int, value_area_fraction: float) -> tuple[int, int]:
    left = right = int(poc_pos)
    included = float(volumes[poc_pos])
    target = float(volumes.sum()) * value_area_fraction
    while included < target and (left > 0 or right < len(volumes) - 1):
        left_volume = float(volumes[left - 1]) if left > 0 else -1.0
        right_volume = float(volumes[right + 1]) if right < len(volumes) - 1 else -1.0
        if left_volume > right_volume:
            left -= 1
            included += left_volume
        elif right_volume > left_volume:
            right += 1
            included += right_volume
        else:
            if left > 0:
                left -= 1
                included += left_volume
            if right < len(volumes) - 1 and included < target:
                right += 1
                included += right_volume
    return left, right


def nearest_level(levels: np.ndarray, reference: float) -> float:
    if len(levels) == 0 or not np.isfinite(reference):
        return float("nan")
    return float(levels[np.argmin(np.abs(levels - reference))])


def merge_prior_profiles(base: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    out = base.copy()
    out["session_date"] = pd.to_datetime(out["timestamp"]).dt.date
    if profiles.empty:
        for column in PROFILE_COLUMNS:
            out[column] = np.nan
        return out

    profile_cols = [
        "vap_session_yyyymmdd",
        "vap_poc",
        "vap_vah",
        "vap_val",
        "vap_lvn_near_high",
        "vap_lvn_near_low",
        "vap_lvn_count",
        "vap_total_volume",
        "vap_price_levels",
    ]
    prior = profiles[["session_date", *profile_cols]].sort_values("session_date").copy()
    shifted = prior[profile_cols].shift(1)
    shifted.columns = PROFILE_COLUMNS
    shifted["session_date"] = prior["session_date"].to_numpy()
    out = out.merge(shifted, on="session_date", how="left")
    return out


if __name__ == "__main__":
    main()
