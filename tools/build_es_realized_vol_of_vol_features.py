from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_realized_vol_of_vol_features_20110103_20260609.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "close"])
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
        n_returns = int(len(log_returns))
        realized_variance = float((log_returns**2).sum()) if n_returns else float("nan")
        realized_volatility = math.sqrt(realized_variance) if realized_variance >= 0 else float("nan")
        realized_quarticity = float((n_returns / 3.0) * (log_returns**4).sum()) if n_returns else float("nan")
        quarticity_ratio = (
            realized_quarticity / (realized_variance**2)
            if realized_variance and realized_variance > 0
            else float("nan")
        )
        rolling_volatility = (log_returns**2).rolling(30, min_periods=10).sum().apply(math.sqrt).dropna()
        intraday_vov = (
            float(rolling_volatility.std(ddof=0) / rolling_volatility.mean())
            if len(rolling_volatility) and rolling_volatility.mean() > 0
            else float("nan")
        )
        daily_rows.append(
            {
                "session_date": session_date,
                "rows": int(len(group)),
                "rth_return": float(group["close"].iloc[-1] / group["open"].iloc[0] - 1.0),
                "realized_variance": realized_variance,
                "realized_volatility": realized_volatility,
                "realized_quarticity": realized_quarticity,
                "quarticity_ratio": quarticity_ratio,
                "intraday_vov": intraday_vov,
            }
        )

    daily = pd.DataFrame(daily_rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)

    # Every tradable state is shifted one completed RTH session. A row for date D
    # can only contain information available after date D-1 has closed.
    daily["prior_rth_return"] = daily["rth_return"].shift(1)
    daily["prior_realized_variance"] = daily["realized_variance"].shift(1)
    daily["prior_realized_volatility"] = daily["realized_volatility"].shift(1)
    daily["prior_realized_quarticity_1d"] = daily["realized_quarticity"].shift(1)
    daily["prior_quarticity_ratio_1d"] = daily["quarticity_ratio"].shift(1)
    daily["prior_intraday_vov_1d"] = daily["intraday_vov"].shift(1)
    daily["intraday_vov_5d_mean"] = daily["intraday_vov"].rolling(5, min_periods=5).mean().shift(1)
    daily["intraday_vov_20d_mean"] = daily["intraday_vov"].rolling(20, min_periods=20).mean().shift(1)
    daily["quarticity_ratio_5d_mean"] = daily["quarticity_ratio"].rolling(5, min_periods=5).mean().shift(1)
    daily["quarticity_ratio_20d_mean"] = daily["quarticity_ratio"].rolling(20, min_periods=20).mean().shift(1)

    daily["intraday_vov1_rank_252"] = _rolling_last_percentile(
        daily["prior_intraday_vov_1d"], 252, min_periods=60
    )
    daily["quarticity_ratio1_rank_252"] = _rolling_last_percentile(
        daily["prior_quarticity_ratio_1d"], 252, min_periods=60
    )
    daily["intraday_vov5_rank_252"] = _rolling_last_percentile(
        daily["intraday_vov_5d_mean"], 252, min_periods=60
    )
    daily["intraday_vov20_rank_252"] = _rolling_last_percentile(
        daily["intraday_vov_20d_mean"], 252, min_periods=60
    )
    daily["quarticity_ratio20_rank_252"] = _rolling_last_percentile(
        daily["quarticity_ratio_20d_mean"], 252, min_periods=60
    )

    columns = [
        "session_date",
        "prior_rth_return",
        "prior_realized_variance",
        "prior_realized_volatility",
        "prior_realized_quarticity_1d",
        "prior_quarticity_ratio_1d",
        "prior_intraday_vov_1d",
        "intraday_vov_5d_mean",
        "intraday_vov_20d_mean",
        "quarticity_ratio_5d_mean",
        "quarticity_ratio_20d_mean",
        "intraday_vov1_rank_252",
        "quarticity_ratio1_rank_252",
        "intraday_vov5_rank_252",
        "intraday_vov20_rank_252",
        "quarticity_ratio20_rank_252",
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
    valid = features.dropna(subset=["intraday_vov1_rank_252", "intraday_vov5_rank_252", "intraday_vov20_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
