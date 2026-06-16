from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_lagged_volatility_features_20110103_20260609.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = timestamps.dt.date.astype(str)

    daily = (
        bars.groupby("session_date", sort=True)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            rows=("close", "size"),
        )
        .reset_index()
    )
    daily["return"] = daily["close"].pct_change()
    daily["range_pct"] = (daily["high"] - daily["low"]) / daily["open"]
    daily["abs_return"] = daily["return"].abs()
    daily["downside_return_sq"] = daily["return"].where(daily["return"] < 0, 0.0) ** 2

    # All feature columns below are shifted to the next session.  A row dated
    # 2020-01-03 contains only information available after 2020-01-02 RTH.
    daily["prior_close"] = daily["close"].shift(1)
    daily["prior_rth_return"] = daily["return"].shift(1)
    daily["prior_range_pct"] = daily["range_pct"].shift(1)
    daily["realized_vol_5"] = daily["return"].rolling(5, min_periods=5).std(ddof=0).shift(1)
    daily["realized_vol_10"] = daily["return"].rolling(10, min_periods=10).std(ddof=0).shift(1)
    daily["realized_vol_20"] = daily["return"].rolling(20, min_periods=20).std(ddof=0).shift(1)
    daily["avg_range_pct_5"] = daily["range_pct"].rolling(5, min_periods=5).mean().shift(1)
    daily["avg_range_pct_10"] = daily["range_pct"].rolling(10, min_periods=10).mean().shift(1)
    daily["avg_abs_return_5"] = daily["abs_return"].rolling(5, min_periods=5).mean().shift(1)
    daily["downside_vol_20"] = (
        daily["downside_return_sq"].rolling(20, min_periods=20).mean().pow(0.5).shift(1)
    )
    daily["vol5_over_vol20"] = daily["realized_vol_5"] / daily["realized_vol_20"]

    daily["vol20_rank_252"] = _rolling_last_percentile(daily["realized_vol_20"], 252, min_periods=60)
    daily["range10_rank_252"] = _rolling_last_percentile(daily["avg_range_pct_10"], 252, min_periods=60)
    daily["absret5_rank_252"] = _rolling_last_percentile(daily["avg_abs_return_5"], 252, min_periods=60)
    daily["downside20_rank_252"] = _rolling_last_percentile(daily["downside_vol_20"], 252, min_periods=60)
    daily["vol_ratio_rank_252"] = _rolling_last_percentile(daily["vol5_over_vol20"], 252, min_periods=60)

    columns = [
        "session_date",
        "prior_close",
        "prior_rth_return",
        "prior_range_pct",
        "realized_vol_5",
        "realized_vol_10",
        "realized_vol_20",
        "avg_range_pct_5",
        "avg_range_pct_10",
        "avg_abs_return_5",
        "downside_vol_20",
        "vol5_over_vol20",
        "vol20_rank_252",
        "range10_rank_252",
        "absret5_rank_252",
        "downside20_rank_252",
        "vol_ratio_rank_252",
    ]
    out = daily.loc[daily["session_date"] >= "2011-01-03", columns].copy()
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
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.input, args.output)
    valid = features.dropna(subset=["vol20_rank_252", "range10_rank_252", "absret5_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
