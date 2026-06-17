from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_lagged_realized_skewness_features_20110103_20260609.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = timestamps.dt.date.astype(str)

    daily_rows: list[dict] = []
    for session_date, group in bars.groupby("session_date", sort=True):
        closes = group["close"].astype(float)
        first_open = float(group["open"].iloc[0])
        prior_prices = closes.shift(1)
        prior_prices.iloc[0] = first_open
        returns = (closes / prior_prices).where(lambda values: values > 0).astype("float64")
        log_returns = returns.apply(lambda value: pd.NA if pd.isna(value) else math.log(value)).dropna()
        realized_var = float((log_returns**2).sum()) if len(log_returns) else float("nan")
        realized_skew = _realized_skew(log_returns)
        realized_kurt = _realized_kurtosis(log_returns)
        daily_rows.append(
            {
                "session_date": session_date,
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
                "rows": int(len(group)),
                "rth_return": float(group["close"].iloc[-1] / group["open"].iloc[0] - 1.0),
                "realized_variance": realized_var,
                "realized_skew": realized_skew,
                "realized_kurtosis": realized_kurt,
            }
        )

    daily = pd.DataFrame(daily_rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)

    # Every tradable feature is shifted one RTH session. A row for date D can only
    # contain state available after date D-1 has closed.
    daily["prior_close"] = daily["close"].shift(1)
    daily["prior_rth_return"] = daily["rth_return"].shift(1)
    daily["prior_realized_variance"] = daily["realized_variance"].shift(1)
    daily["prior_realized_skew_1d"] = daily["realized_skew"].shift(1)
    daily["prior_realized_kurtosis_1d"] = daily["realized_kurtosis"].shift(1)
    daily["realized_skew_3d_mean"] = daily["realized_skew"].rolling(3, min_periods=3).mean().shift(1)
    daily["realized_skew_5d_mean"] = daily["realized_skew"].rolling(5, min_periods=5).mean().shift(1)
    daily["realized_skew_10d_mean"] = daily["realized_skew"].rolling(10, min_periods=10).mean().shift(1)
    daily["realized_skew_5d_min"] = daily["realized_skew"].rolling(5, min_periods=5).min().shift(1)
    daily["realized_skew_5d_max"] = daily["realized_skew"].rolling(5, min_periods=5).max().shift(1)

    daily["skew1_rank_252"] = _rolling_last_percentile(daily["prior_realized_skew_1d"], 252, min_periods=60)
    daily["skew3_rank_252"] = _rolling_last_percentile(daily["realized_skew_3d_mean"], 252, min_periods=60)
    daily["skew5_rank_252"] = _rolling_last_percentile(daily["realized_skew_5d_mean"], 252, min_periods=60)
    daily["skew10_rank_252"] = _rolling_last_percentile(daily["realized_skew_10d_mean"], 252, min_periods=60)

    columns = [
        "session_date",
        "prior_close",
        "prior_rth_return",
        "prior_realized_variance",
        "prior_realized_skew_1d",
        "prior_realized_kurtosis_1d",
        "realized_skew_3d_mean",
        "realized_skew_5d_mean",
        "realized_skew_10d_mean",
        "realized_skew_5d_min",
        "realized_skew_5d_max",
        "skew1_rank_252",
        "skew3_rank_252",
        "skew5_rank_252",
        "skew10_rank_252",
    ]
    out = daily.loc[daily["session_date"] >= "2011-01-03", columns].copy()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _realized_skew(returns: pd.Series) -> float:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return float("nan")
    variance_sum = float((clean**2).sum())
    if variance_sum <= 0:
        return float("nan")
    return float((len(clean) ** 0.5) * (clean**3).sum() / (variance_sum ** 1.5))


def _realized_kurtosis(returns: pd.Series) -> float:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return float("nan")
    variance_sum = float((clean**2).sum())
    if variance_sum <= 0:
        return float("nan")
    return float(len(clean) * (clean**4).sum() / (variance_sum**2))


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
    valid = features.dropna(subset=["skew1_rank_252", "skew3_rank_252", "skew5_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
