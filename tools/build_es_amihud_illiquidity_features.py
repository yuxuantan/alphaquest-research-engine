from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_amihud_illiquidity_features_20110103_20260609.csv"
DEFAULT_POINT_VALUE = 50.0


def build_features(
    input_path: str | Path,
    output_path: str | Path,
    point_value: float = DEFAULT_POINT_VALUE,
) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close", "volume"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = timestamps.dt.date.astype(str)
    bars["notional_volume"] = bars["close"].astype(float) * bars["volume"].astype(float) * float(point_value)

    daily_rows: list[dict] = []
    for session_date, group in bars.groupby("session_date", sort=True):
        day_open = float(group["open"].iloc[0])
        day_close = float(group["close"].iloc[-1])
        volume = float(group["volume"].sum())
        dollar_volume = float(group["notional_volume"].sum())
        rth_return = day_close / day_open - 1.0 if day_open > 0 else float("nan")
        abs_return = abs(rth_return)
        amihud_illiq = abs_return / dollar_volume if dollar_volume > 0 else float("nan")
        daily_rows.append(
            {
                "session_date": session_date,
                "open": day_open,
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": day_close,
                "rows": int(len(group)),
                "volume": volume,
                "dollar_volume": dollar_volume,
                "rth_return": rth_return,
                "abs_rth_return": abs_return,
                "amihud_illiq": amihud_illiq,
                "price_impact_per_billion": amihud_illiq * 1_000_000_000.0,
            }
        )

    daily = pd.DataFrame(daily_rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)

    # Every tradable feature is shifted one completed RTH session. A signal on
    # date D can only use state known after date D-1 has closed.
    daily["prior_close"] = daily["close"].shift(1)
    daily["prior_rth_return"] = daily["rth_return"].shift(1)
    daily["prior_abs_rth_return"] = daily["abs_rth_return"].shift(1)
    daily["prior_dollar_volume"] = daily["dollar_volume"].shift(1)
    daily["prior_volume"] = daily["volume"].shift(1)
    daily["prior_amihud_illiq_1d"] = daily["amihud_illiq"].shift(1)
    daily["prior_price_impact_per_billion"] = daily["price_impact_per_billion"].shift(1)
    daily["amihud_illiq_3d_mean"] = daily["amihud_illiq"].rolling(3, min_periods=3).mean().shift(1)
    daily["amihud_illiq_5d_mean"] = daily["amihud_illiq"].rolling(5, min_periods=5).mean().shift(1)
    daily["amihud_illiq_20d_mean"] = daily["amihud_illiq"].rolling(20, min_periods=20).mean().shift(1)

    daily["illiq1_rank_252"] = _rolling_last_percentile(daily["prior_amihud_illiq_1d"], 252, min_periods=60)
    daily["illiq3_rank_252"] = _rolling_last_percentile(daily["amihud_illiq_3d_mean"], 252, min_periods=60)
    daily["illiq5_rank_252"] = _rolling_last_percentile(daily["amihud_illiq_5d_mean"], 252, min_periods=60)
    daily["illiq20_rank_252"] = _rolling_last_percentile(daily["amihud_illiq_20d_mean"], 252, min_periods=60)
    daily["dollar_volume1_rank_252"] = _rolling_last_percentile(daily["prior_dollar_volume"], 252, min_periods=60)

    columns = [
        "session_date",
        "prior_close",
        "prior_rth_return",
        "prior_abs_rth_return",
        "prior_volume",
        "prior_dollar_volume",
        "prior_amihud_illiq_1d",
        "prior_price_impact_per_billion",
        "amihud_illiq_3d_mean",
        "amihud_illiq_5d_mean",
        "amihud_illiq_20d_mean",
        "illiq1_rank_252",
        "illiq3_rank_252",
        "illiq5_rank_252",
        "illiq20_rank_252",
        "dollar_volume1_rank_252",
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
    parser.add_argument("--point-value", type=float, default=DEFAULT_POINT_VALUE)
    args = parser.parse_args()
    features = build_features(args.input, args.output, point_value=args.point_value)
    valid = features.dropna(subset=["illiq1_rank_252", "illiq5_rank_252", "illiq20_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
