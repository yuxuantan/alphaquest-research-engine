from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.build_sierra_footprint_feature_cache import aggregate_base_bars, _filter_periods  # noqa: E402
from tools.build_sierra_trade_orderflow_cache import (  # noqa: E402
    PRINT_COLUMNS,
    RTH_START_MINUTE,
    active_periods,
    datetime_to_scid_us,
    is_bar_like_contract,
    scid_us_to_new_york_datetime,
)
from tools.build_sierra_vap_profile_cache import value_area_positions  # noqa: E402


FEATURE_PREFIX = "intrabar"
SIDE_FEATURES = [
    "release_price",
    "release_offset_seconds",
    "delta",
    "delta_zone_low",
    "delta_zone_high",
    "session_open",
    "session_high",
    "session_low",
    "session_range_pct",
    "vap_poc",
    "vap_vah",
    "vap_val",
    "vap_poc_volume",
    "vap_lvn_inside_value_area_count",
    "vap_no_lvn_between_value_area",
    "vap_total_volume",
    "vap_price_levels",
]
FEATURE_COLUMNS = [f"{FEATURE_PREFIX}_{side}_{name}" for side in ["short", "long"] for name in SIDE_FEATURES]


@dataclass
class Setup:
    timestamp: pd.Timestamp
    delta: float
    zone_low: float
    zone_high: float


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
    preserve_base_timeframe = bool(args.preserve_base_timeframe)
    if args.bar_minutes > 1 and not preserve_base_timeframe and not _is_native_timeframe(base, args.bar_minutes):
        base = aggregate_base_bars(base, bar_minutes=args.bar_minutes)

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
        print(f"[{idx}/{len(periods)}] intrabar VAP absorption {symbol}: {path.name}", flush=True)
        prints = load_period_prints(
            path,
            start=period["start"],
            end=period["end"],
            tick_size=args.tick_size,
            batch_size=args.batch_size,
        )
        if prints.empty:
            period_reports.append({"symbol": symbol, "status": "empty_prints"})
            continue
        features = intrabar_vap_absorption_features(
            prints,
            bar_minutes=args.bar_minutes,
            tick_size=args.tick_size,
            delta_threshold=args.delta_threshold,
            release_seconds=args.release_seconds,
            value_area_fraction=args.value_area_fraction,
            lvn_poc_fraction=args.lvn_poc_fraction,
        )
        if not features.empty:
            feature_parts.append(features)
        period_reports.append(
            {
                "symbol": symbol,
                "status": "built",
                "prints": int(len(prints)),
                "feature_rows": int(len(features)),
                "short_releases": int(features[f"{FEATURE_PREFIX}_short_release_price"].notna().sum()),
                "long_releases": int(features[f"{FEATURE_PREFIX}_long_release_price"].notna().sum()),
            }
        )

    features = pd.concat(feature_parts, ignore_index=True) if feature_parts else empty_feature_frame()
    if not features.empty:
        features = features.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    out = base.merge(features, on="timestamp", how="left")
    for column in FEATURE_COLUMNS:
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
        "bar_minutes": args.bar_minutes,
        "preserve_base_timeframe": preserve_base_timeframe,
        "output_timeframe_minutes": _source_timeframe_minutes(out),
        "tick_size": args.tick_size,
        "delta_threshold": args.delta_threshold,
        "release_seconds": args.release_seconds,
        "value_area_fraction": args.value_area_fraction,
        "lvn_poc_fraction": args.lvn_poc_fraction,
        "duplicate_timestamps": int(out.duplicated("timestamp").sum()),
        "short_release_bars": int(out[f"{FEATURE_PREFIX}_short_release_price"].notna().sum()),
        "long_release_bars": int(out[f"{FEATURE_PREFIX}_long_release_price"].notna().sum()),
        "source_quality_label": (
            "Raw Sierra SCID-derived records with microsecond timestamps, price, volume, and bid/ask volume. "
            "This supports deterministic release-time research features, but is not MBO queue data."
        ),
        "periods": period_reports,
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["rows", "short_release_bars", "long_release_bars"]}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ES 3-minute intrabar PDH/PDL VAP absorption-sweep features from Sierra records."
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
        default=Path("data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"),
    )
    parser.add_argument("--root-symbol", default="ES")
    parser.add_argument("--output-parquet", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--bar-minutes", type=int, default=3)
    parser.add_argument(
        "--preserve-base-timeframe",
        action="store_true",
        help=(
            "Keep the base cache at its source timeframe and merge release features onto each "
            "bar_minutes anchor row. Use this when a 3-minute strategy still needs 1-minute detail_data."
        ),
    )
    parser.add_argument("--delta-threshold", type=float, default=300.0)
    parser.add_argument("--release-seconds", type=float, default=5.0)
    parser.add_argument("--value-area-fraction", type=float, default=0.70)
    parser.add_argument("--lvn-poc-fraction", type=float, default=0.10)
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    return parser.parse_args()


def load_period_prints(
    path: Path,
    *,
    start: datetime,
    end: datetime,
    tick_size: float,
    batch_size: int,
) -> pd.DataFrame:
    start_us = datetime_to_scid_us(start)
    end_us = datetime_to_scid_us(end) + 1
    parts = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=PRINT_COLUMNS):
        part = period_prints_from_batch(batch, start_us=start_us, end_us=end_us, tick_size=tick_size)
        if not part.empty:
            parts.append(part)
    if not parts:
        return empty_print_frame()
    out = pd.concat(parts, ignore_index=True)
    if not pd.Series(out["timestamp"]).is_monotonic_increasing:
        out = out.sort_values("timestamp")
    return out.reset_index(drop=True)


def period_prints_from_batch(batch, *, start_us: int, end_us: int, tick_size: float) -> pd.DataFrame:
    ts = batch.column(batch.schema.get_field_index("scid_datetime_us")).to_numpy(
        zero_copy_only=False
    ).astype(np.int64, copy=False)
    price = batch.column(batch.schema.get_field_index("close")).to_numpy(zero_copy_only=False)
    volume = batch.column(batch.schema.get_field_index("volume")).to_numpy(zero_copy_only=False)
    bid = batch.column(batch.schema.get_field_index("bid_volume")).to_numpy(zero_copy_only=False)
    ask = batch.column(batch.schema.get_field_index("ask_volume")).to_numpy(zero_copy_only=False)
    mask = (ts >= start_us) & (ts < end_us) & np.isfinite(price) & (price > 0) & (volume > 0)
    if not mask.any():
        return empty_print_frame()

    ts = ts[mask]
    price = np.round(price[mask].astype(np.float64, copy=False) / tick_size) * tick_size
    volume = volume[mask].astype(np.float64, copy=False)
    signed = ask[mask].astype(np.float64, copy=False) - bid[mask].astype(np.float64, copy=False)
    local_timestamp = scid_us_to_new_york_datetime(ts)
    minute_of_day = local_timestamp.hour * 60 + local_timestamp.minute
    rth_mask = (minute_of_day >= RTH_START_MINUTE) & (minute_of_day <= 15 * 60 + 59)
    if not rth_mask.any():
        return empty_print_frame()
    return pd.DataFrame(
        {
            "timestamp": local_timestamp[rth_mask],
            "price": price[rth_mask],
            "volume": volume[rth_mask],
            "signed_volume": signed[rth_mask],
        }
    )


def intrabar_vap_absorption_features(
    prints: pd.DataFrame,
    *,
    bar_minutes: int,
    tick_size: float,
    delta_threshold: float,
    release_seconds: float,
    value_area_fraction: float,
    lvn_poc_fraction: float,
) -> pd.DataFrame:
    if prints.empty:
        return empty_feature_frame()
    work = prints.reset_index(drop=True).copy()
    if not pd.Series(work["timestamp"]).is_monotonic_increasing:
        work = work.sort_values("timestamp").reset_index(drop=True)
    work["timestamp"] = pd.to_datetime(work["timestamp"])
    work["bar_timestamp"] = _floor_to_rth_bar(work["timestamp"], bar_minutes)
    work["session_date"] = work["timestamp"].dt.date
    work["tick"] = np.round(pd.to_numeric(work["price"], errors="coerce") / tick_size).astype("Int64")
    rows_by_bar: dict[pd.Timestamp, dict] = {}

    for _, session in work.groupby("session_date", sort=True, observed=True):
        session_open = None
        session_high = -np.inf
        session_low = np.inf
        cum_volume: dict[float, float] = {}
        current_bar = None
        zone_delta: dict[int, float] = {}
        positive_setup: Setup | None = None
        negative_setup: Setup | None = None
        positive_release = None
        negative_release = None
        for row in session.itertuples(index=False):
            timestamp = pd.Timestamp(row.timestamp)
            bar_timestamp = pd.Timestamp(row.bar_timestamp)
            price = float(row.price)
            volume = float(row.volume)
            signed = float(row.signed_volume)
            tick = int(row.tick)
            if current_bar is None or bar_timestamp != current_bar:
                if current_bar is not None:
                    rows_by_bar[current_bar] = _feature_row(current_bar, positive_release, negative_release)
                current_bar = bar_timestamp
                zone_delta = {}
                positive_setup = None
                negative_setup = None
                positive_release = None
                negative_release = None

            if session_open is None:
                session_open = price
            session_high = max(session_high, price)
            session_low = min(session_low, price)
            cum_volume[price] = cum_volume.get(price, 0.0) + volume
            for zone_start in range(tick - 3, tick + 1):
                zone_delta[zone_start] = zone_delta.get(zone_start, 0.0) + signed

            if positive_setup is None:
                positive_setup = _setup_from_zone_delta(
                    zone_delta,
                    threshold=delta_threshold,
                    tick_size=tick_size,
                    timestamp=timestamp,
                    direction="positive",
                )
            if negative_setup is None:
                negative_setup = _setup_from_zone_delta(
                    zone_delta,
                    threshold=delta_threshold,
                    tick_size=tick_size,
                    timestamp=timestamp,
                    direction="negative",
                )

            if (
                positive_setup is not None
                and positive_release is None
                and timestamp >= positive_setup.timestamp + pd.Timedelta(seconds=release_seconds)
                and price < positive_setup.zone_low
            ):
                positive_release = _release_payload(
                    side="short",
                    bar_timestamp=current_bar,
                    timestamp=timestamp,
                    price=price,
                    setup=positive_setup,
                    session_open=session_open,
                    session_high=session_high,
                    session_low=session_low,
                    cum_volume=cum_volume,
                    value_area_fraction=value_area_fraction,
                    lvn_poc_fraction=lvn_poc_fraction,
                )
            if (
                negative_setup is not None
                and negative_release is None
                and timestamp >= negative_setup.timestamp + pd.Timedelta(seconds=release_seconds)
                and price > negative_setup.zone_high
            ):
                negative_release = _release_payload(
                    side="long",
                    bar_timestamp=current_bar,
                    timestamp=timestamp,
                    price=price,
                    setup=negative_setup,
                    session_open=session_open,
                    session_high=session_high,
                    session_low=session_low,
                    cum_volume=cum_volume,
                    value_area_fraction=value_area_fraction,
                    lvn_poc_fraction=lvn_poc_fraction,
                )
        if current_bar is not None:
            rows_by_bar[current_bar] = _feature_row(current_bar, positive_release, negative_release)

    if not rows_by_bar:
        return empty_feature_frame()
    return pd.DataFrame(rows_by_bar.values()).sort_values("timestamp").reset_index(drop=True)


def _setup_from_zone_delta(
    zone_delta: dict[int, float],
    *,
    threshold: float,
    tick_size: float,
    timestamp: pd.Timestamp,
    direction: str,
) -> Setup | None:
    if not zone_delta:
        return None
    if direction == "positive":
        zone_start, delta = max(zone_delta.items(), key=lambda item: item[1])
        if delta < threshold:
            return None
    else:
        zone_start, delta = min(zone_delta.items(), key=lambda item: item[1])
        if delta > -threshold:
            return None
    return Setup(
        timestamp=timestamp,
        delta=float(delta),
        zone_low=float(zone_start * tick_size),
        zone_high=float((zone_start + 3) * tick_size),
    )


def _release_payload(
    *,
    side: str,
    bar_timestamp: pd.Timestamp,
    timestamp: pd.Timestamp,
    price: float,
    setup: Setup,
    session_open: float,
    session_high: float,
    session_low: float,
    cum_volume: dict[float, float],
    value_area_fraction: float,
    lvn_poc_fraction: float,
) -> dict:
    profile = _profile_from_cum_volume(
        cum_volume,
        session_high=session_high,
        session_low=session_low,
        value_area_fraction=value_area_fraction,
        lvn_poc_fraction=lvn_poc_fraction,
    )
    return {
        "side": side,
        "release_price": float(price),
        "release_offset_seconds": float((timestamp - bar_timestamp).total_seconds()),
        "delta": float(setup.delta),
        "delta_zone_low": float(setup.zone_low),
        "delta_zone_high": float(setup.zone_high),
        "session_open": float(session_open),
        "session_high": float(session_high),
        "session_low": float(session_low),
        "session_range_pct": float((session_high - session_low) / session_open) if session_open else np.nan,
        **profile,
    }


def _profile_from_cum_volume(
    cum_volume: dict[float, float],
    *,
    session_high: float,
    session_low: float,
    value_area_fraction: float,
    lvn_poc_fraction: float,
) -> dict:
    prices = np.array(sorted(cum_volume), dtype=float)
    volumes = np.array([cum_volume[float(price)] for price in prices], dtype=float)
    mask = np.isfinite(prices) & np.isfinite(volumes) & (prices > 0) & (volumes > 0)
    prices = prices[mask]
    volumes = volumes[mask]
    if len(prices) == 0 or volumes.sum() <= 0:
        return _empty_profile()
    midpoint = (float(session_high) + float(session_low)) / 2.0
    poc_pos = max(range(len(prices)), key=lambda idx: (volumes[idx], -abs(prices[idx] - midpoint)))
    val_pos, vah_pos = value_area_positions(volumes, poc_pos, value_area_fraction)
    poc_volume = float(volumes[poc_pos])
    lvn_mask = volumes <= poc_volume * lvn_poc_fraction
    inside_va = (prices >= prices[val_pos]) & (prices <= prices[vah_pos]) & lvn_mask
    inside_count = int(inside_va.sum())
    return {
        "vap_poc": float(prices[poc_pos]),
        "vap_vah": float(prices[vah_pos]),
        "vap_val": float(prices[val_pos]),
        "vap_poc_volume": poc_volume,
        "vap_lvn_inside_value_area_count": inside_count,
        "vap_no_lvn_between_value_area": float(inside_count == 0),
        "vap_total_volume": float(volumes.sum()),
        "vap_price_levels": int(len(prices)),
    }


def _feature_row(bar_timestamp: pd.Timestamp, short_release: dict | None, long_release: dict | None) -> dict:
    row = {"timestamp": bar_timestamp}
    for side, release in [("short", short_release), ("long", long_release)]:
        for name in SIDE_FEATURES:
            row[f"{FEATURE_PREFIX}_{side}_{name}"] = np.nan
        if release is None:
            continue
        for name in SIDE_FEATURES:
            row[f"{FEATURE_PREFIX}_{side}_{name}"] = release.get(name, np.nan)
    return row


def _empty_profile() -> dict:
    return {
        "vap_poc": np.nan,
        "vap_vah": np.nan,
        "vap_val": np.nan,
        "vap_poc_volume": np.nan,
        "vap_lvn_inside_value_area_count": np.nan,
        "vap_no_lvn_between_value_area": np.nan,
        "vap_total_volume": np.nan,
        "vap_price_levels": np.nan,
    }


def _floor_to_rth_bar(timestamps: pd.Series, bar_minutes: int) -> pd.Series:
    minute_of_day = timestamps.dt.hour * 60 + timestamps.dt.minute
    bucket_minutes = ((minute_of_day - RTH_START_MINUTE) // bar_minutes) * bar_minutes + RTH_START_MINUTE
    return timestamps.dt.normalize() + pd.to_timedelta(bucket_minutes, unit="m")


def _is_native_timeframe(df: pd.DataFrame, minutes: int) -> bool:
    if "timeframe_minutes" not in df.columns:
        return False
    values = pd.to_numeric(df["timeframe_minutes"], errors="coerce").dropna().unique()
    return len(values) == 1 and float(values[0]) == float(minutes)


def _source_timeframe_minutes(df: pd.DataFrame) -> float | None:
    if "timeframe_minutes" not in df.columns:
        return None
    values = pd.to_numeric(df["timeframe_minutes"], errors="coerce").dropna().unique()
    if len(values) != 1:
        return None
    return float(values[0])


def empty_feature_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["timestamp", *FEATURE_COLUMNS])


def empty_print_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["timestamp", "price", "volume", "signed_volume"])


if __name__ == "__main__":
    main()
