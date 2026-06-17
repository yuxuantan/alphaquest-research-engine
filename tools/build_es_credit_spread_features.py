from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_credit_spread_features_20110103_20260609.csv"
DEFAULT_CACHE_DIR = "data/external"
FRED_SERIES = {
    "hy_oas": "BAMLH0A0HYM2",
    "ig_oas": "BAMLC0A0CM",
}


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    input_paths: dict[str, str | Path] | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    rank_min_periods: int = 60,
    availability_lag_bdays: int = 2,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["credit_asof_date"] = sessions["session_date_ts"] - BDay(int(availability_lag_bdays))

    frames = []
    for key, series_id in FRED_SERIES.items():
        input_path = (input_paths or {}).get(key)
        cache_path = Path(cache_dir) / f"fred_{series_id.lower()}.csv"
        frames.append(
            _load_fred_series(
                input_path=input_path,
                cache_path=cache_path,
                series_id=series_id,
                value_name=key,
            )
        )
    credit = frames[0]
    for frame in frames[1:]:
        credit = credit.merge(frame, on="observation_date", how="outer")
    value_columns = [column for column in credit.columns if column != "observation_date"]
    credit = credit.sort_values("observation_date", kind="mergesort")
    credit[value_columns] = credit[value_columns].ffill()
    credit = credit.dropna(subset=value_columns, how="any")

    credit["hy_ig_oas_diff"] = credit["hy_oas"] - credit["ig_oas"]
    credit["hy_oas_change_1d"] = credit["hy_oas"] - credit["hy_oas"].shift(1)
    credit["hy_oas_change_5d"] = credit["hy_oas"] - credit["hy_oas"].shift(5)
    credit["ig_oas_change_1d"] = credit["ig_oas"] - credit["ig_oas"].shift(1)
    credit["hy_ig_oas_diff_change_1d"] = credit["hy_ig_oas_diff"] - credit["hy_ig_oas_diff"].shift(1)
    for column in [
        "hy_oas",
        "ig_oas",
        "hy_ig_oas_diff",
        "hy_oas_change_1d",
        "hy_oas_change_5d",
        "ig_oas_change_1d",
        "hy_ig_oas_diff_change_1d",
    ]:
        credit[f"{column}_rank_252"] = _rolling_last_percentile(
            credit[column], 252, rank_min_periods
        )

    # FRED/ICE OAS observations are end-of-day credit market data with uncertain
    # publication timing for an intraday ES system. Use a conservative business-day
    # lag and an as-of join on credit_asof_date.
    merged = pd.merge_asof(
        sessions.sort_values("credit_asof_date"),
        credit.sort_values("observation_date"),
        left_on="credit_asof_date",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")

    columns = [
        "session_date",
        "credit_asof_date",
        "observation_date",
        "hy_oas",
        "ig_oas",
        "hy_ig_oas_diff",
        "hy_oas_change_1d",
        "hy_oas_change_5d",
        "ig_oas_change_1d",
        "hy_ig_oas_diff_change_1d",
        "hy_oas_rank_252",
        "ig_oas_rank_252",
        "hy_ig_oas_diff_rank_252",
        "hy_oas_change_1d_rank_252",
        "hy_oas_change_5d_rank_252",
        "ig_oas_change_1d_rank_252",
        "hy_ig_oas_diff_change_1d_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    for column in ["credit_asof_date", "observation_date"]:
        out[column] = pd.to_datetime(out[column]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_fred_series(
    *,
    input_path: str | Path | None,
    cache_path: str | Path,
    series_id: str,
    value_name: str,
) -> pd.DataFrame:
    if input_path is not None:
        raw = pd.read_csv(input_path)
    else:
        cache = Path(cache_path)
        if cache.exists():
            raw = pd.read_csv(cache)
        else:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            raw = pd.read_csv(url)
            cache.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache, index=False)
    date_col = "observation_date" if "observation_date" in raw.columns else "DATE"
    value_col = series_id if series_id in raw.columns else value_name
    if value_col not in raw.columns:
        raise ValueError(f"FRED input for {series_id} is missing value column {value_col}.")
    out = raw[[date_col, value_col]].copy()
    out.columns = ["observation_date", value_name]
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out[value_name] = pd.to_numeric(out[value_name].replace(".", pd.NA), errors="coerce")
    return (
        out.dropna(subset=[value_name])
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
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--availability-lag-bdays", type=int, default=2)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        availability_lag_bdays=args.availability_lag_bdays,
    )
    valid = features.dropna(subset=["hy_oas_rank_252", "hy_oas_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
