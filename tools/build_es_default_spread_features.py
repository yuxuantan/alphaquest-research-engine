from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_AAA_INPUT = "data/external/fred_default_spread/fred_daaa_aaa_corporate_yield.csv"
DEFAULT_BAA_INPUT = "data/external/fred_default_spread/fred_dbaa_baa_corporate_yield.csv"
DEFAULT_OUTPUT = "data/external/es_default_spread_features_20110103_20260609.csv"


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    aaa_input: str | Path = DEFAULT_AAA_INPUT,
    baa_input: str | Path = DEFAULT_BAA_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    availability_lag_bdays: int = 2,
    rank_window: int = 252,
    rank_min_periods: int = 60,
    start_session: str = "2011-01-03",
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": bars["timestamp"].dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["credit_asof_date"] = sessions["session_ts"] - BDay(int(availability_lag_bdays))

    aaa = _load_fred_series(aaa_input, "DAAA", "aaa_yield")
    baa = _load_fred_series(baa_input, "DBAA", "baa_yield")
    credit = aaa.merge(baa, on="observation_date", how="inner").sort_values(
        "observation_date", kind="mergesort"
    )
    credit["default_spread"] = credit["baa_yield"] - credit["aaa_yield"]
    credit["default_spread_change_1d"] = credit["default_spread"].diff(1)
    credit["default_spread_change_5d"] = credit["default_spread"].diff(5)
    for column in ("default_spread", "default_spread_change_1d", "default_spread_change_5d"):
        credit[f"{column}_rank_252"] = _rolling_last_percentile(
            credit[column], rank_window, rank_min_periods
        )

    merged = pd.merge_asof(
        sessions.sort_values("credit_asof_date"),
        credit.sort_values("observation_date"),
        left_on="credit_asof_date",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_ts", kind="mergesort")
    merged["availability_lag_business_days"] = int(availability_lag_bdays)
    out = merged[merged["session_date"] >= start_session].copy()
    for column in ("credit_asof_date", "observation_date"):
        out[column] = pd.to_datetime(out[column]).dt.date.astype(str)
    columns = [
        "session_date",
        "credit_asof_date",
        "observation_date",
        "availability_lag_business_days",
        "aaa_yield",
        "baa_yield",
        "default_spread",
        "default_spread_change_1d",
        "default_spread_change_5d",
        "default_spread_rank_252",
        "default_spread_change_1d_rank_252",
        "default_spread_change_5d_rank_252",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_fred_series(path: str | Path, source_column: str, target_column: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing local FRED CSV: {csv_path}. This builder does not download data.")
    raw = pd.read_csv(csv_path, parse_dates=["observation_date"])
    if source_column not in raw.columns:
        raise ValueError(f"{csv_path} is missing required column {source_column}.")
    out = raw[["observation_date", source_column]].copy()
    out[target_column] = pd.to_numeric(out[source_column], errors="coerce")
    return (
        out[["observation_date", target_column]]
        .dropna(subset=[target_column])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


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
    parser.add_argument("--aaa-input", default=DEFAULT_AAA_INPUT)
    parser.add_argument("--baa-input", default=DEFAULT_BAA_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-bdays", type=int, default=2)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.aaa_input,
        args.baa_input,
        args.output,
        availability_lag_bdays=args.availability_lag_bdays,
    )
    valid = features.dropna(subset=["default_spread_rank_252", "default_spread_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
