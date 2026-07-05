from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_max_daily_return_features_20110103_20260612.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    rank_min_periods: int = 60,
) -> pd.DataFrame:
    bars = pd.read_parquet(
        bars_input,
        columns=["timestamp", "open", "high", "low", "close"],
    )
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    if bars["timestamp"].dt.tz is None:
        bars["timestamp"] = bars["timestamp"].dt.tz_localize("America/New_York")
    else:
        bars["timestamp"] = bars["timestamp"].dt.tz_convert("America/New_York")
    bars = bars[
        (bars["timestamp"].dt.time >= pd.Timestamp("09:30").time())
        & (bars["timestamp"].dt.time <= pd.Timestamp("15:59").time())
    ].copy()
    bars["session_date"] = bars["timestamp"].dt.date.astype(str)

    daily = (
        bars.sort_values("timestamp", kind="mergesort")
        .groupby("session_date", sort=True)
        .agg(
            session_open=("open", "first"),
            session_high=("high", "max"),
            session_low=("low", "min"),
            session_close=("close", "last"),
        )
        .reset_index()
    )
    daily["daily_return"] = daily["session_close"] / daily["session_open"] - 1.0
    daily["prior_close"] = daily["session_close"].shift(1)
    daily["prior_daily_return"] = daily["daily_return"].shift(1)

    for lookback in (5, 20, 63):
        daily[f"prior_max_return_{lookback}d"] = (
            daily["daily_return"].rolling(lookback, min_periods=lookback).max().shift(1)
        )
        daily[f"max_return_{lookback}d_rank_252"] = _rolling_last_percentile(
            daily[f"prior_max_return_{lookback}d"], 252, rank_min_periods
        )

    daily["prior_avg_top5_return_20d"] = (
        daily["daily_return"]
        .rolling(20, min_periods=20)
        .apply(lambda values: float(pd.Series(values).nlargest(5).mean()), raw=False)
        .shift(1)
    )
    daily["avg_top5_return_20d_rank_252"] = _rolling_last_percentile(
        daily["prior_avg_top5_return_20d"], 252, rank_min_periods
    )

    out = daily[
        [
            "session_date",
            "prior_close",
            "prior_daily_return",
            "prior_max_return_5d",
            "prior_max_return_20d",
            "prior_max_return_63d",
            "prior_avg_top5_return_20d",
            "max_return_5d_rank_252",
            "max_return_20d_rank_252",
            "max_return_63d_rank_252",
            "avg_top5_return_20d_rank_252",
        ]
    ].copy()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--rank-min-periods", type=int, default=60)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        rank_min_periods=args.rank_min_periods,
    )
    valid = features.dropna(subset=["max_return_20d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
