from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_HYG_INPUT = "data/external/yahoo_credit_etfs/yahoo_hyg_daily_20020726_20260610.csv"
DEFAULT_LQD_INPUT = "data/external/yahoo_credit_etfs/yahoo_lqd_daily_20020726_20260610.csv"
DEFAULT_SPY_INPUT = "data/external/yahoo_sector_etfs/yahoo_spy_daily_1998-12-01_2026-06-10.csv"
DEFAULT_OUTPUT = "data/external/es_credit_etf_risk_appetite_features_20110103_20260609.csv"


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    hyg_input: str | Path = DEFAULT_HYG_INPUT,
    lqd_input: str | Path = DEFAULT_LQD_INPUT,
    spy_input: str | Path = DEFAULT_SPY_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    rank_window: int = 252,
    rank_min_periods: int = 80,
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

    hyg = _load_yahoo_etf(hyg_input, "hyg")
    lqd = _load_yahoo_etf(lqd_input, "lqd")
    spy = _load_yahoo_etf(spy_input, "spy")
    daily = (
        hyg.merge(lqd, on="observation_date", how="inner")
        .merge(spy, on="observation_date", how="inner")
        .sort_values("observation_date", kind="mergesort")
        .reset_index(drop=True)
    )
    for symbol in ("hyg", "lqd", "spy"):
        for lookback in (1, 3, 5):
            daily[f"{symbol}_ret_{lookback}d"] = daily[symbol].pct_change(lookback)
    daily["hyg_lqd_excess_3d"] = daily["hyg_ret_3d"] - daily["lqd_ret_3d"]
    daily["hyg_spy_excess_1d"] = daily["hyg_ret_1d"] - daily["spy_ret_1d"]
    daily["hyg_spy_excess_3d"] = daily["hyg_ret_3d"] - daily["spy_ret_3d"]
    for column in (
        "hyg_ret_1d",
        "hyg_ret_3d",
        "hyg_ret_5d",
        "hyg_lqd_excess_3d",
        "hyg_spy_excess_1d",
        "hyg_spy_excess_3d",
    ):
        daily[f"{column}_rank_252"] = _rolling_last_percentile(
            daily[column], rank_window, rank_min_periods
        )

    merged = pd.merge_asof(
        sessions.sort_values("session_ts"),
        daily.sort_values("observation_date"),
        left_on="session_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_ts", kind="mergesort")
    merged["availability_rule"] = "latest ETF daily close strictly before ES session_date"
    out = merged[merged["session_date"] >= start_session].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "observation_date",
        "availability_rule",
        "hyg",
        "lqd",
        "spy",
        "hyg_ret_1d",
        "hyg_ret_3d",
        "hyg_ret_5d",
        "lqd_ret_1d",
        "spy_ret_1d",
        "hyg_lqd_excess_3d",
        "hyg_spy_excess_1d",
        "hyg_spy_excess_3d",
        "hyg_ret_1d_rank_252",
        "hyg_ret_3d_rank_252",
        "hyg_ret_5d_rank_252",
        "hyg_lqd_excess_3d_rank_252",
        "hyg_spy_excess_1d_rank_252",
        "hyg_spy_excess_3d_rank_252",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_yahoo_etf(path: str | Path, name: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing local Yahoo ETF CSV: {csv_path}. This builder does not download data.")
    raw = pd.read_csv(csv_path, parse_dates=["Date"])
    if "Adj Close" not in raw.columns:
        raise ValueError(f"{csv_path} is missing required column Adj Close.")
    out = raw[["Date", "Adj Close"]].copy()
    out[name] = pd.to_numeric(out["Adj Close"], errors="coerce")
    return (
        out.rename(columns={"Date": "observation_date"})[["observation_date", name]]
        .dropna(subset=[name])
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
    parser.add_argument("--hyg-input", default=DEFAULT_HYG_INPUT)
    parser.add_argument("--lqd-input", default=DEFAULT_LQD_INPUT)
    parser.add_argument("--spy-input", default=DEFAULT_SPY_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.bars_input, args.hyg_input, args.lqd_input, args.spy_input, args.output)
    valid = features.dropna(subset=["hyg_ret_1d_rank_252", "hyg_ret_3d_rank_252", "hyg_ret_5d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
