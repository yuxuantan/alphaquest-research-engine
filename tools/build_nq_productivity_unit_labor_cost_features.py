from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_productivity_unit_labor_cost_features_20110103_20260612.csv"
DEFAULT_CACHE_DIR = "data/external/fred_productivity_unit_labor_cost"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

SERIES = {
    "OPHNFB": "productivity_index",
    "ULCNFB": "unit_labor_cost_index",
    "COMPRNFB": "real_hourly_comp_index",
}


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    availability_lag_days: int = 180,
    rank_window_quarters: int = 80,
    rank_min_periods: int = 24,
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

    quarterly = None
    for fred_id, column in SERIES.items():
        series = _load_or_fetch_fred_series(fred_id, cache_dir, column)
        quarterly = series if quarterly is None else quarterly.merge(
            series, on="observation_date", how="inner", validate="one_to_one"
        )
    assert quarterly is not None
    quarterly = quarterly.sort_values("observation_date", kind="mergesort").reset_index(drop=True)
    quarterly = _add_state_features(
        quarterly,
        rank_window_quarters=rank_window_quarters,
        rank_min_periods=rank_min_periods,
    )

    merged = pd.merge_asof(
        sessions.sort_values("observation_cutoff"),
        quarterly.sort_values("observation_date"),
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
        "productivity_index",
        "unit_labor_cost_index",
        "real_hourly_comp_index",
        "productivity_change_1q",
        "productivity_change_4q",
        "unit_labor_cost_change_1q",
        "unit_labor_cost_change_4q",
        "real_hourly_comp_change_4q",
        "productivity_minus_ulc_change_4q",
        "productivity_change_1q_rank_80q",
        "productivity_change_4q_rank_80q",
        "unit_labor_cost_change_1q_rank_80q",
        "unit_labor_cost_change_4q_rank_80q",
        "real_hourly_comp_change_4q_rank_80q",
        "productivity_minus_ulc_change_4q_rank_80q",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_or_fetch_fred_series(
    series_id: str,
    cache_dir: str | Path,
    column_name: str,
) -> pd.DataFrame:
    cache_path = Path(cache_dir) / f"fred_{series_id.lower()}_quarterly.csv"
    if cache_path.exists():
        raw = pd.read_csv(cache_path)
    else:
        raw = _read_csv_with_retries(FRED_URL.format(series_id=series_id))
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
    quarterly: pd.DataFrame,
    *,
    rank_window_quarters: int,
    rank_min_periods: int,
) -> pd.DataFrame:
    out = quarterly.copy()
    out["productivity_change_1q"] = out["productivity_index"].pct_change(1)
    out["productivity_change_4q"] = out["productivity_index"].pct_change(4)
    out["unit_labor_cost_change_1q"] = out["unit_labor_cost_index"].pct_change(1)
    out["unit_labor_cost_change_4q"] = out["unit_labor_cost_index"].pct_change(4)
    out["real_hourly_comp_change_4q"] = out["real_hourly_comp_index"].pct_change(4)
    out["productivity_minus_ulc_change_4q"] = (
        out["productivity_change_4q"] - out["unit_labor_cost_change_4q"]
    )
    for column in [
        "productivity_change_1q",
        "productivity_change_4q",
        "unit_labor_cost_change_1q",
        "unit_labor_cost_change_4q",
        "real_hourly_comp_change_4q",
        "productivity_minus_ulc_change_4q",
    ]:
        out[f"{column}_rank_80q"] = _rolling_last_percentile(
            out[column],
            rank_window_quarters,
            rank_min_periods,
        )
    return out


def _read_csv_with_retries(url: str, attempts: int = 4, sleep_seconds: float = 2.0) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return pd.read_csv(url)
        except Exception as exc:
            last_error = exc
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                return pd.read_csv(BytesIO(response.read()))
        except Exception as exc:  # pragma: no cover - network fallback.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download FRED CSV after {attempts} attempts: {url}") from last_error


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
    parser.add_argument("--availability-lag-days", type=int, default=180)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        availability_lag_days=args.availability_lag_days,
    )
    valid = features.dropna(
        subset=[
            "productivity_change_4q_rank_80q",
            "unit_labor_cost_change_4q_rank_80q",
            "productivity_minus_ulc_change_4q_rank_80q",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
