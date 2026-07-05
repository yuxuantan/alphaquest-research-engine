from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet"
DEFAULT_OUTPUT = "data/external/nq_asia_london_session_levels_20110103_20260529.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close", "volume"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize("America/New_York")
    else:
        timestamps = timestamps.dt.tz_convert("America/New_York")
    bars["timestamp"] = timestamps
    times = timestamps.dt.time
    rth_mask = (times >= pd.Timestamp("09:30").time()) & (times <= pd.Timestamp("15:59").time())
    rth_dates = {ts.date() for ts in timestamps[rth_mask]}

    evening = times >= pd.Timestamp("18:00").time()
    asia_morning = times <= pd.Timestamp("02:59").time()
    london_mask = (times >= pd.Timestamp("03:00").time()) & (times <= pd.Timestamp("09:29").time())
    session_dates = timestamps.dt.normalize()
    liquidity_session_dates = session_dates.where(~evening, session_dates + pd.Timedelta(days=1))

    work = bars.loc[evening | asia_morning | london_mask].copy()
    work["liquidity_session_date"] = liquidity_session_dates[evening | asia_morning | london_mask].dt.date
    work["session_segment"] = "asia"
    work.loc[london_mask[evening | asia_morning | london_mask].to_numpy(), "session_segment"] = "london"
    work = work[work["liquidity_session_date"].isin(rth_dates)].copy()

    grouped = (
        work.groupby(["liquidity_session_date", "session_segment"], sort=True)
        .agg(
            start=("timestamp", "first"),
            end=("timestamp", "last"),
            high=("high", "max"),
            low=("low", "min"),
            volume=("volume", "sum"),
            bars=("timestamp", "count"),
        )
        .reset_index()
    )
    pivot = grouped.pivot(index="liquidity_session_date", columns="session_segment")
    pivot.columns = [f"{segment}_{field}" for field, segment in pivot.columns]
    pivot = pivot.reset_index().rename(columns={"liquidity_session_date": "session_date"})
    pivot = pivot[(pivot["asia_bars"] >= 120) & (pivot["london_bars"] >= 180)].copy()
    pivot = pivot[(pivot["asia_high"] > pivot["asia_low"]) & (pivot["london_high"] > pivot["london_low"])].copy()
    pivot["asia_range_points"] = pivot["asia_high"] - pivot["asia_low"]
    pivot["london_range_points"] = pivot["london_high"] - pivot["london_low"]
    pivot["combined_high"] = pivot[["asia_high", "london_high"]].max(axis=1)
    pivot["combined_low"] = pivot[["asia_low", "london_low"]].min(axis=1)
    pivot["session_date"] = pd.to_datetime(pivot["session_date"]).dt.date.astype(str)
    for column in ["asia_start", "asia_end", "london_start", "london_end"]:
        pivot[column] = pd.to_datetime(pivot[column]).map(lambda value: value.isoformat())
    ordered = [
        "session_date",
        "asia_start",
        "asia_end",
        "asia_high",
        "asia_low",
        "asia_range_points",
        "asia_volume",
        "asia_bars",
        "london_start",
        "london_end",
        "london_high",
        "london_low",
        "london_range_points",
        "london_volume",
        "london_bars",
        "combined_high",
        "combined_low",
    ]
    features = pivot[ordered].sort_values("session_date", kind="mergesort").reset_index(drop=True)
    features = features[features["session_date"] >= "2011-01-03"].reset_index(drop=True)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    return features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.input, args.output)
    print(f"wrote {args.output}")
    print(f"rows={len(features)}")
    if not features.empty:
        print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
        print(f"min_asia_bars={features['asia_bars'].min()} min_london_bars={features['london_bars'].min()}")


if __name__ == "__main__":
    main()
