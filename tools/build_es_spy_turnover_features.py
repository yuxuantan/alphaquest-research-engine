from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_SPY_INPUT = "data/external/yahoo_sector_etfs/yahoo_spy_daily_1998-12-01_2026-06-10.csv"
DEFAULT_OUTPUT = "data/external/es_spy_turnover_attention_features_20110103_20260609.csv"


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
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

    daily = _load_yahoo_spy(spy_input)
    for lookback in (1, 3, 5):
        daily[f"spy_ret_{lookback}d"] = daily["spy"].pct_change(lookback)
    daily["spy_volume_median_20"] = daily["spy_volume"].rolling(20, min_periods=10).median()
    daily["spy_volume_median_63"] = daily["spy_volume"].rolling(63, min_periods=20).median()
    daily["spy_volume_ratio_20"] = daily["spy_volume"] / daily["spy_volume_median_20"]
    daily["spy_volume_ratio_63"] = daily["spy_volume"] / daily["spy_volume_median_63"]
    daily["spy_absret_volume_1d"] = daily["spy_ret_1d"].abs() * daily["spy_volume_ratio_20"]
    daily["spy_absret_volume_3d"] = daily["spy_ret_3d"].abs() * daily["spy_volume_ratio_63"]
    daily["spy_signed_pressure_1d"] = daily["spy_ret_1d"] * daily["spy_volume_ratio_20"]

    for column in (
        "spy_volume_ratio_20",
        "spy_volume_ratio_63",
        "spy_absret_volume_1d",
        "spy_absret_volume_3d",
        "spy_signed_pressure_1d",
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
    merged["availability_rule"] = "latest SPY daily close and volume strictly before ES session_date"
    out = merged[merged["session_date"] >= start_session].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "observation_date",
        "availability_rule",
        "spy",
        "spy_volume",
        "spy_ret_1d",
        "spy_ret_3d",
        "spy_ret_5d",
        "spy_volume_ratio_20",
        "spy_volume_ratio_63",
        "spy_absret_volume_1d",
        "spy_absret_volume_3d",
        "spy_signed_pressure_1d",
        "spy_volume_ratio_20_rank_252",
        "spy_volume_ratio_63_rank_252",
        "spy_absret_volume_1d_rank_252",
        "spy_absret_volume_3d_rank_252",
        "spy_signed_pressure_1d_rank_252",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_yahoo_spy(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing local Yahoo SPY CSV: {csv_path}. This builder does not download data.")
    raw = pd.read_csv(csv_path, parse_dates=["Date"])
    required = {"Adj Close", "Volume"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"{csv_path} is missing required columns: {sorted(missing)}.")
    out = raw[["Date", "Adj Close", "Volume"]].copy()
    out["spy"] = pd.to_numeric(out["Adj Close"], errors="coerce")
    out["spy_volume"] = pd.to_numeric(out["Volume"], errors="coerce")
    return (
        out.rename(columns={"Date": "observation_date"})[["observation_date", "spy", "spy_volume"]]
        .dropna(subset=["spy", "spy_volume"])
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
    parser.add_argument("--spy-input", default=DEFAULT_SPY_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.bars_input, args.spy_input, args.output)
    valid = features.dropna(
        subset=["spy_volume_ratio_20_rank_252", "spy_absret_volume_1d_rank_252"]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
