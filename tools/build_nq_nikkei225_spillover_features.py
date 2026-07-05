from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
import urllib.request

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_nikkei225_spillover_features_20110103_20260612.csv"
DEFAULT_FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NIKKEI225"


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    fred_input: str | Path | None = None,
    fred_url: str = DEFAULT_FRED_URL,
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
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])

    daily = _load_fred_nikkei(fred_input=fred_input, fred_url=fred_url)
    for lookback in (1, 3, 5):
        daily[f"nikkei_return_{lookback}d"] = daily["nikkei225"].pct_change(lookback)
    daily["nikkei_abs_return_1d"] = daily["nikkei_return_1d"].abs()

    rank_columns = [
        "nikkei_return_1d",
        "nikkei_return_3d",
        "nikkei_return_5d",
        "nikkei_abs_return_1d",
    ]
    for column in rank_columns:
        daily[f"{column}_rank_252"] = _rolling_last_percentile(
            daily[column], rank_window, rank_min_periods
        )

    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        daily.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged["nikkei_observation_lag_calendar_days"] = (
        merged["session_date_ts"] - merged["observation_date"]
    ).dt.days
    out = merged[merged["session_date"] >= start_session].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "observation_date",
        "nikkei_observation_lag_calendar_days",
        "nikkei225",
        "nikkei_return_1d",
        "nikkei_return_3d",
        "nikkei_return_5d",
        "nikkei_abs_return_1d",
        "nikkei_return_1d_rank_252",
        "nikkei_return_3d_rank_252",
        "nikkei_return_5d_rank_252",
        "nikkei_abs_return_1d_rank_252",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_fred_nikkei(
    *, fred_input: str | Path | None = None, fred_url: str = DEFAULT_FRED_URL
) -> pd.DataFrame:
    if fred_input is None:
        with urllib.request.urlopen(fred_url, timeout=30) as response:
            raw = response.read().decode("utf-8")
        frame = pd.read_csv(StringIO(raw), parse_dates=["observation_date"])
    else:
        frame = pd.read_csv(fred_input, parse_dates=["observation_date"])
    missing = {"observation_date", "NIKKEI225"}.difference(frame.columns)
    if missing:
        raise ValueError(f"Nikkei FRED input is missing columns: {sorted(missing)}.")
    frame["nikkei225"] = pd.to_numeric(frame["NIKKEI225"].replace(".", pd.NA), errors="coerce")
    return (
        frame[["observation_date", "nikkei225"]]
        .dropna(subset=["nikkei225"])
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
    parser.add_argument("--fred-input", default=None)
    parser.add_argument("--fred-url", default=DEFAULT_FRED_URL)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        fred_input=args.fred_input,
        fred_url=args.fred_url,
    )
    valid = features.dropna(subset=["nikkei_return_1d_rank_252", "nikkei_return_5d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
