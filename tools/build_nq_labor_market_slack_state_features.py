from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import subprocess

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_labor_market_slack_state_features_20110103_20260612.csv"
DEFAULT_CACHE_DIR = "data/external/fred_labor_market_slack_state"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

SERIES = {
    "UNRATE": "unemployment_rate",
    "U6RATE": "underemployment_rate",
    "EMRATIO": "employment_population_ratio",
    "CIVPART": "participation_rate",
}


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    availability_lag_days: int = 45,
    rank_window_months: int = 120,
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
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["observation_cutoff"] = sessions["session_date_ts"] - pd.Timedelta(
        days=int(availability_lag_days)
    )

    monthly = None
    for fred_id, column in SERIES.items():
        series = _load_or_fetch_fred_series(fred_id, cache_dir, column)
        monthly = series if monthly is None else monthly.merge(
            series, on="observation_date", how="inner", validate="one_to_one"
        )
    assert monthly is not None
    monthly = monthly.sort_values("observation_date", kind="mergesort").reset_index(drop=True)
    monthly = _add_state_features(
        monthly,
        rank_window_months=rank_window_months,
        rank_min_periods=rank_min_periods,
    )

    merged = pd.merge_asof(
        sessions.sort_values("observation_cutoff"),
        monthly.sort_values("observation_date"),
        left_on="observation_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged["availability_lag_days"] = int(availability_lag_days)
    out = merged.loc[merged["session_date"] >= start_session].copy()
    out["observation_cutoff"] = pd.to_datetime(out["observation_cutoff"]).dt.date.astype(str)
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "observation_cutoff",
        "observation_date",
        "availability_lag_days",
        "unemployment_rate",
        "underemployment_rate",
        "employment_population_ratio",
        "participation_rate",
        "unemployment_rate_rank_120m",
        "underemployment_rate_rank_120m",
        "employment_population_ratio_rank_120m",
        "participation_rate_rank_120m",
        "participation_rate_change_3m",
        "participation_rate_change_3m_rank_120m",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_or_fetch_fred_series(series_id: str, cache_dir: str | Path, column_name: str) -> pd.DataFrame:
    cache_path = Path(cache_dir) / f"fred_{series_id.lower()}_monthly.csv"
    if cache_path.exists():
        raw = pd.read_csv(cache_path)
    else:
        raw = _read_fred_csv(FRED_URL.format(series_id=series_id))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(cache_path, index=False)
    if "observation_date" not in raw.columns or series_id not in raw.columns:
        raise ValueError(f"{cache_path} is missing required columns for {series_id}.")
    out = raw[["observation_date", series_id]].copy()
    out.columns = ["observation_date", column_name]
    out["observation_date"] = pd.to_datetime(out["observation_date"], errors="coerce")
    out[column_name] = pd.to_numeric(out[column_name], errors="coerce")
    return (
        out.dropna(subset=["observation_date", column_name])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _add_state_features(
    monthly: pd.DataFrame,
    *,
    rank_window_months: int,
    rank_min_periods: int,
) -> pd.DataFrame:
    out = monthly.copy()
    for column in [
        "unemployment_rate",
        "underemployment_rate",
        "employment_population_ratio",
        "participation_rate",
    ]:
        out[f"{column}_rank_120m"] = _rolling_last_percentile(
            out[column],
            rank_window_months,
            rank_min_periods,
        )
    out["participation_rate_change_3m"] = out["participation_rate"].diff(3)
    out["participation_rate_change_3m_rank_120m"] = _rolling_last_percentile(
        out["participation_rate_change_3m"],
        rank_window_months,
        rank_min_periods,
    )
    return out


def _read_fred_csv(url: str) -> pd.DataFrame:
    result = subprocess.run(
        ["curl", "-L", "--max-time", "30", "-sS", url],
        check=True,
        capture_output=True,
        text=True,
    )
    return pd.read_csv(BytesIO(result.stdout.encode("utf-8")))


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
    parser.add_argument("--availability-lag-days", type=int, default=45)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        availability_lag_days=args.availability_lag_days,
    )
    valid = features.dropna(
        subset=[
            "unemployment_rate_rank_120m",
            "underemployment_rate_rank_120m",
            "employment_population_ratio_rank_120m",
            "participation_rate_rank_120m",
            "participation_rate_change_3m_rank_120m",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
