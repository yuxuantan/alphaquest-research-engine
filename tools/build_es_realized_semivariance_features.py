from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_realized_semivariance_features_20110103_20260609.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = timestamps.dt.date.astype(str)

    daily_rows: list[dict] = []
    for session_date, group in bars.groupby("session_date", sort=True):
        closes = group["close"].astype(float)
        prior_prices = closes.shift(1)
        prior_prices.iloc[0] = float(group["open"].iloc[0])
        gross_returns = (closes / prior_prices).where(lambda values: values > 0).astype("float64")
        log_returns = gross_returns.apply(lambda value: pd.NA if pd.isna(value) else math.log(value)).dropna()
        positive = log_returns[log_returns > 0]
        negative = log_returns[log_returns < 0]
        realized_variance = float((log_returns**2).sum()) if len(log_returns) else float("nan")
        upside_semivariance = float((positive**2).sum()) if len(positive) else 0.0
        downside_semivariance = float((negative**2).sum()) if len(negative) else 0.0
        downside_share = (
            downside_semivariance / realized_variance if realized_variance and realized_variance > 0 else float("nan")
        )
        upside_share = upside_semivariance / realized_variance if realized_variance and realized_variance > 0 else float("nan")
        semivariance_balance = (
            (downside_semivariance - upside_semivariance) / realized_variance
            if realized_variance and realized_variance > 0
            else float("nan")
        )
        daily_rows.append(
            {
                "session_date": session_date,
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
                "rows": int(len(group)),
                "rth_return": float(group["close"].iloc[-1] / group["open"].iloc[0] - 1.0),
                "realized_variance": realized_variance,
                "realized_upside_semivariance": upside_semivariance,
                "realized_downside_semivariance": downside_semivariance,
                "realized_downside_share": downside_share,
                "realized_upside_share": upside_share,
                "realized_semivariance_balance": semivariance_balance,
            }
        )

    daily = pd.DataFrame(daily_rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)

    # Every tradable feature is shifted one completed RTH session. A row for
    # date D can only contain state available after date D-1 has closed.
    daily["prior_close"] = daily["close"].shift(1)
    daily["prior_rth_return"] = daily["rth_return"].shift(1)
    daily["prior_realized_variance"] = daily["realized_variance"].shift(1)
    daily["prior_downside_semivariance_1d"] = daily["realized_downside_semivariance"].shift(1)
    daily["prior_upside_semivariance_1d"] = daily["realized_upside_semivariance"].shift(1)
    daily["prior_downside_share_1d"] = daily["realized_downside_share"].shift(1)
    daily["prior_upside_share_1d"] = daily["realized_upside_share"].shift(1)
    daily["prior_semivariance_balance_1d"] = daily["realized_semivariance_balance"].shift(1)
    daily["downside_semivariance_3d_mean"] = (
        daily["realized_downside_semivariance"].rolling(3, min_periods=3).mean().shift(1)
    )
    daily["upside_semivariance_3d_mean"] = (
        daily["realized_upside_semivariance"].rolling(3, min_periods=3).mean().shift(1)
    )
    daily["semivariance_balance_5d_mean"] = (
        daily["realized_semivariance_balance"].rolling(5, min_periods=5).mean().shift(1)
    )

    daily["downside1_rank_252"] = _rolling_last_percentile(
        daily["prior_downside_semivariance_1d"], 252, min_periods=60
    )
    daily["upside1_rank_252"] = _rolling_last_percentile(daily["prior_upside_semivariance_1d"], 252, min_periods=60)
    daily["downside_share1_rank_252"] = _rolling_last_percentile(daily["prior_downside_share_1d"], 252, min_periods=60)
    daily["semivar_balance1_rank_252"] = _rolling_last_percentile(
        daily["prior_semivariance_balance_1d"], 252, min_periods=60
    )
    daily["downside3_rank_252"] = _rolling_last_percentile(
        daily["downside_semivariance_3d_mean"], 252, min_periods=60
    )
    daily["upside3_rank_252"] = _rolling_last_percentile(daily["upside_semivariance_3d_mean"], 252, min_periods=60)
    daily["semivar_balance5_rank_252"] = _rolling_last_percentile(
        daily["semivariance_balance_5d_mean"], 252, min_periods=60
    )

    columns = [
        "session_date",
        "prior_close",
        "prior_rth_return",
        "prior_realized_variance",
        "prior_downside_semivariance_1d",
        "prior_upside_semivariance_1d",
        "prior_downside_share_1d",
        "prior_upside_share_1d",
        "prior_semivariance_balance_1d",
        "downside_semivariance_3d_mean",
        "upside_semivariance_3d_mean",
        "semivariance_balance_5d_mean",
        "downside1_rank_252",
        "upside1_rank_252",
        "downside_share1_rank_252",
        "semivar_balance1_rank_252",
        "downside3_rank_252",
        "upside3_rank_252",
        "semivar_balance5_rank_252",
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
    valid = features.dropna(subset=["downside1_rank_252", "upside1_rank_252", "semivar_balance5_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
