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
from tools.build_sierra_vap_profile_cache import nearest_level, value_area_positions  # noqa: E402


DEVELOPING_VAP_PREFIX = "developing_vap"
DEVELOPING_VAP_COLUMNS = [
    f"{DEVELOPING_VAP_PREFIX}_session_yyyymmdd",
    f"{DEVELOPING_VAP_PREFIX}_poc",
    f"{DEVELOPING_VAP_PREFIX}_vah",
    f"{DEVELOPING_VAP_PREFIX}_val",
    f"{DEVELOPING_VAP_PREFIX}_lvn_near_close",
    f"{DEVELOPING_VAP_PREFIX}_lvn_near_high",
    f"{DEVELOPING_VAP_PREFIX}_lvn_near_low",
    f"{DEVELOPING_VAP_PREFIX}_lvn_count",
    f"{DEVELOPING_VAP_PREFIX}_total_volume",
    f"{DEVELOPING_VAP_PREFIX}_price_levels",
    f"{DEVELOPING_VAP_PREFIX}_bars",
]


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

    feature_parts = []
    period_reports = []
    for idx, period in enumerate(periods, start=1):
        symbol = period["symbol"]
        path = period["path"]
        if is_bar_like_contract(symbol, path):
            period_reports.append({"symbol": symbol, "status": "skipped_bar_like"})
            continue
        print(f"[{idx}/{len(periods)}] developing VAP {symbol}: {path.name}", flush=True)
        price_volume = aggregate_footprint_price_volume_period(
            path,
            start=period["start"],
            end=period["end"],
            tick_size=args.tick_size,
            batch_size=args.batch_size,
            bar_minutes=args.bar_minutes,
        )
        if price_volume.empty:
            period_reports.append({"symbol": symbol, "status": "empty_price_volume"})
            continue
        period_bars = base[base["contract_symbol"].astype(str) == symbol].copy()
        if period_bars.empty:
            period_reports.append(
                {
                    "symbol": symbol,
                    "status": "no_base_bars",
                    "price_volume_rows": int(len(price_volume)),
                }
            )
            continue
        features = developing_vap_features(
            period_bars,
            price_volume,
            min_bars=args.min_bars,
            value_area_fraction=args.value_area_fraction,
            lvn_quantile=args.lvn_quantile,
        )
        feature_parts.append(features)
        period_reports.append(
            {
                "symbol": symbol,
                "status": "built",
                "base_rows": int(len(period_bars)),
                "price_volume_rows": int(len(price_volume)),
                "feature_rows": int(len(features)),
                "bars_with_developing_vap": int(features[f"{DEVELOPING_VAP_PREFIX}_poc"].notna().sum()),
            }
        )

    features = pd.concat(feature_parts, ignore_index=True) if feature_parts else pd.DataFrame(columns=["timestamp"])
    if not features.empty:
        features = features.sort_values("timestamp").drop_duplicates("timestamp", keep="last")

    out = base.merge(features, on="timestamp", how="left")
    for column in DEVELOPING_VAP_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
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
        "bar_minutes": args.bar_minutes,
        "min_bars": args.min_bars,
        "value_area_fraction": args.value_area_fraction,
        "lvn_quantile": args.lvn_quantile,
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()),
        "bars_with_developing_vap": int(out[f"{DEVELOPING_VAP_PREFIX}_poc"].notna().sum()),
        "local_only": True,
        "source_quality_label": (
            "Sierra SCID-derived developing current-session volume-at-price levels. "
            "Each row uses only price-level bid/ask volume through that completed bar; "
            "not MBO/queue data and not vendor-equivalent print sequencing."
        ),
        "profile_columns": DEVELOPING_VAP_COLUMNS,
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
                "bars_with_developing_vap": report["bars_with_developing_vap"],
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Sierra current-session developing volume-at-price levels and merge them onto bars."
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
        default=Path("data/cache/orderflow/es_sierra_footprint_imbalance_3m_20101214_20260610_full_rth_ny.parquet"),
    )
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--bar-minutes", type=int, default=3)
    parser.add_argument("--min-bars", type=int, default=10)
    parser.add_argument("--value-area-fraction", type=float, default=0.70)
    parser.add_argument("--lvn-quantile", type=float, default=0.20)
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    return parser.parse_args()


def developing_vap_features(
    bars: pd.DataFrame,
    price_volume: pd.DataFrame,
    *,
    min_bars: int,
    value_area_fraction: float,
    lvn_quantile: float,
    prefix: str = DEVELOPING_VAP_PREFIX,
) -> pd.DataFrame:
    if min_bars < 1:
        raise ValueError("min_bars must be positive.")
    if not 0 < value_area_fraction <= 1:
        raise ValueError("value_area_fraction must be in (0, 1].")
    if not 0 < lvn_quantile < 1:
        raise ValueError("lvn_quantile must be in (0, 1).")

    work_bars = bars.copy()
    work_bars["timestamp"] = pd.to_datetime(work_bars["timestamp"])
    if "session_date" in work_bars.columns:
        work_bars["session_date"] = pd.to_datetime(work_bars["session_date"]).dt.date
    else:
        work_bars["session_date"] = work_bars["timestamp"].dt.date
    work_bars = work_bars.sort_values("timestamp").reset_index(drop=True)

    work_pv = price_volume.copy()
    work_pv["timestamp"] = pd.to_datetime(work_pv["timestamp"])
    work_pv["session_date"] = work_pv["timestamp"].dt.date
    work_pv["price"] = pd.to_numeric(work_pv["price"], errors="coerce")
    work_pv["volume"] = pd.to_numeric(work_pv["volume"], errors="coerce")
    work_pv = work_pv.dropna(subset=["timestamp", "price", "volume"])
    work_pv = work_pv[(work_pv["price"] > 0) & (work_pv["volume"] > 0)]

    empty_row = {column: np.nan for column in _prefixed_columns(prefix)}
    rows = []
    for session_date, session_bars in work_bars.groupby("session_date", sort=True, observed=True):
        session_pv = work_pv[work_pv["session_date"] == session_date]
        by_timestamp = {
            timestamp: group[["price", "volume"]].to_numpy(dtype=float)
            for timestamp, group in session_pv.groupby("timestamp", sort=True, observed=True)
        }
        cum_volume: dict[float, float] = {}
        session_high = -np.inf
        session_low = np.inf
        bar_count = 0
        for _, bar in session_bars.iterrows():
            timestamp = pd.Timestamp(bar["timestamp"])
            bar_count += 1
            high = _finite_float(bar.get("high"))
            low = _finite_float(bar.get("low"))
            close = _finite_float(bar.get("close"))
            if high is not None:
                session_high = max(session_high, high)
            if low is not None:
                session_low = min(session_low, low)
            additions = by_timestamp.get(timestamp)
            if additions is not None:
                for price, volume in additions:
                    cum_volume[float(price)] = cum_volume.get(float(price), 0.0) + float(volume)

            output = {"timestamp": timestamp}
            if bar_count < min_bars or close is None or not cum_volume:
                output.update(empty_row)
            else:
                profile = compute_developing_profile(
                    cum_volume,
                    session_high=session_high,
                    session_low=session_low,
                    reference_price=close,
                    session_date=session_date,
                    bar_count=bar_count,
                    value_area_fraction=value_area_fraction,
                    lvn_quantile=lvn_quantile,
                    prefix=prefix,
                )
                output.update(profile if profile is not None else empty_row)
            rows.append(output)
    if not rows:
        return pd.DataFrame(columns=["timestamp", *_prefixed_columns(prefix)])
    return pd.DataFrame(rows)


def compute_developing_profile(
    cum_volume: dict[float, float],
    *,
    session_high: float,
    session_low: float,
    reference_price: float,
    session_date,
    bar_count: int,
    value_area_fraction: float,
    lvn_quantile: float,
    prefix: str = DEVELOPING_VAP_PREFIX,
) -> dict | None:
    if not np.isfinite(session_high) or not np.isfinite(session_low) or not cum_volume:
        return None
    prices = np.array(sorted(cum_volume), dtype=float)
    volumes = np.array([cum_volume[float(price)] for price in prices], dtype=float)
    mask = np.isfinite(prices) & np.isfinite(volumes) & (prices > 0) & (volumes > 0)
    prices = prices[mask]
    volumes = volumes[mask]
    total_volume = float(volumes.sum())
    if len(prices) == 0 or total_volume <= 0:
        return None

    midpoint = (float(session_high) + float(session_low)) / 2.0
    poc_pos = max(range(len(prices)), key=lambda idx: (volumes[idx], -abs(prices[idx] - midpoint)))
    val_pos, vah_pos = value_area_positions(volumes, poc_pos, value_area_fraction)
    lvn_threshold = float(np.quantile(volumes, lvn_quantile, method="nearest"))
    lvn_prices = prices[volumes <= lvn_threshold]
    return {
        f"{prefix}_session_yyyymmdd": int(pd.Timestamp(session_date).strftime("%Y%m%d")),
        f"{prefix}_poc": float(prices[poc_pos]),
        f"{prefix}_vah": float(prices[vah_pos]),
        f"{prefix}_val": float(prices[val_pos]),
        f"{prefix}_lvn_near_close": nearest_level(lvn_prices, float(reference_price)),
        f"{prefix}_lvn_near_high": nearest_level(lvn_prices, float(session_high)),
        f"{prefix}_lvn_near_low": nearest_level(lvn_prices, float(session_low)),
        f"{prefix}_lvn_count": int(len(lvn_prices)),
        f"{prefix}_total_volume": total_volume,
        f"{prefix}_price_levels": int(len(prices)),
        f"{prefix}_bars": int(bar_count),
    }


def _prefixed_columns(prefix: str) -> list[str]:
    return [column.replace(DEVELOPING_VAP_PREFIX, prefix, 1) for column in DEVELOPING_VAP_COLUMNS]


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


if __name__ == "__main__":
    main()
