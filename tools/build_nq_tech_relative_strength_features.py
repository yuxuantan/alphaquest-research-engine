from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_XLK_INPUT = "data/external/yahoo_sector_etfs/yahoo_xlk_daily_1998-12-01_2026-06-10.csv"
DEFAULT_SPY_INPUT = "data/external/yahoo_sector_etfs/yahoo_spy_daily_1998-12-01_2026-06-10.csv"
DEFAULT_OUTPUT = "data/external/nq_tech_relative_strength_features_20110103_20260612.csv"


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    xlk_input: str | Path = DEFAULT_XLK_INPUT,
    spy_input: str | Path = DEFAULT_SPY_INPUT,
    rank_window: int = 252,
    rank_min_periods: int = 80,
    availability_lag_bdays: int = 1,
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
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["availability_cutoff"] = sessions["session_date_ts"] - BDay(int(availability_lag_bdays))

    xlk = _load_yahoo_daily(xlk_input, "xlk")
    spy = _load_yahoo_daily(spy_input, "spy")
    daily = (
        xlk.merge(spy, on="observation_date", how="inner")
        .sort_values("observation_date", kind="mergesort")
        .reset_index(drop=True)
    )
    for symbol in ("xlk", "spy"):
        for lookback in (1, 5):
            daily[f"{symbol}_return_{lookback}d"] = daily[symbol].pct_change(lookback)
    daily["xlk_minus_spy_1d"] = daily["xlk_return_1d"] - daily["spy_return_1d"]
    daily["xlk_minus_spy_5d"] = daily["xlk_return_5d"] - daily["spy_return_5d"]
    daily["xlk_volume_median_20"] = daily["xlk_volume"].rolling(20, min_periods=10).median()
    daily["xlk_volume_ratio_20"] = daily["xlk_volume"] / daily["xlk_volume_median_20"]
    daily["xlk_attention_pressure_1d"] = daily["xlk_minus_spy_1d"] * daily["xlk_volume_ratio_20"]

    rank_columns = [
        "xlk_minus_spy_1d",
        "xlk_minus_spy_5d",
        "xlk_volume_ratio_20",
        "xlk_attention_pressure_1d",
    ]
    for column in rank_columns:
        daily[f"{column}_rank_252"] = _rolling_last_percentile(
            daily[column], rank_window, rank_min_periods
        )

    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff"),
        daily.sort_values("observation_date"),
        left_on="availability_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged["availability_lag_business_days"] = int(availability_lag_bdays)
    out = merged[merged["session_date"] >= start_session].copy()
    out["availability_cutoff"] = pd.to_datetime(out["availability_cutoff"]).dt.date.astype(str)
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "availability_cutoff",
        "observation_date",
        "availability_lag_business_days",
        "xlk",
        "spy",
        "xlk_volume",
        "xlk_return_1d",
        "spy_return_1d",
        "xlk_minus_spy_1d",
        "xlk_return_5d",
        "spy_return_5d",
        "xlk_minus_spy_5d",
        "xlk_volume_ratio_20",
        "xlk_attention_pressure_1d",
        "xlk_minus_spy_1d_rank_252",
        "xlk_minus_spy_5d_rank_252",
        "xlk_volume_ratio_20_rank_252",
        "xlk_attention_pressure_1d_rank_252",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_yahoo_daily(path: str | Path, symbol: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing local Yahoo {symbol.upper()} CSV: {csv_path}")
    raw = pd.read_csv(csv_path, parse_dates=["Date"])
    required = {"Adj Close", "Volume"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"{csv_path} is missing required columns: {sorted(missing)}.")
    out = raw[["Date", "Adj Close", "Volume"]].copy()
    out[symbol] = pd.to_numeric(out["Adj Close"], errors="coerce")
    out[f"{symbol}_volume"] = pd.to_numeric(out["Volume"], errors="coerce")
    return (
        out.rename(columns={"Date": "observation_date"})[
            ["observation_date", symbol, f"{symbol}_volume"]
        ]
        .dropna(subset=[symbol, f"{symbol}_volume"])
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
    parser.add_argument("--xlk-input", default=DEFAULT_XLK_INPUT)
    parser.add_argument("--spy-input", default=DEFAULT_SPY_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        xlk_input=args.xlk_input,
        spy_input=args.spy_input,
    )
    valid = features.dropna(subset=["xlk_minus_spy_1d_rank_252", "xlk_minus_spy_5d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
