from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_fiscal_deficit_treasury_supply_features_20110103_20260612.csv"
DEFAULT_CACHE_DIR = "data/external/fred_fiscal_deficit_treasury_supply"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

SERIES = {
    "MTSDS133FMS": "fiscal_balance",
    "MTSR133FMS": "federal_receipts",
    "MTSO133FMS": "federal_outlays",
}


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    availability_lag_days: int = 60,
    rank_window_months: int = 120,
    rank_min_periods: int = 36,
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
        "fiscal_balance",
        "federal_receipts",
        "federal_outlays",
        "deficit",
        "deficit_3m_sum",
        "deficit_12m_sum",
        "balance_3m_sum",
        "receipts_yoy_growth",
        "outlays_yoy_growth",
        "fiscal_impulse_3m",
        "deficit_change_3m",
        "deficit_3m_sum_rank_120m",
        "deficit_12m_sum_rank_120m",
        "balance_3m_sum_rank_120m",
        "receipts_yoy_growth_rank_120m",
        "outlays_yoy_growth_rank_120m",
        "fiscal_impulse_3m_rank_120m",
        "deficit_change_3m_rank_120m",
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
    cache_path = Path(cache_dir) / f"fred_{series_id.lower()}_monthly.csv"
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
    monthly: pd.DataFrame,
    *,
    rank_window_months: int,
    rank_min_periods: int,
) -> pd.DataFrame:
    out = monthly.copy()
    # FRED's MTSDS133FMS is positive for surplus and negative for deficit.
    out["deficit"] = -out["fiscal_balance"]
    out["deficit_3m_sum"] = out["deficit"].rolling(3).sum()
    out["deficit_12m_sum"] = out["deficit"].rolling(12).sum()
    out["balance_3m_sum"] = out["fiscal_balance"].rolling(3).sum()
    out["receipts_yoy_growth"] = out["federal_receipts"] / out["federal_receipts"].shift(12) - 1.0
    out["outlays_yoy_growth"] = out["federal_outlays"] / out["federal_outlays"].shift(12) - 1.0
    out["fiscal_impulse_3m"] = out["federal_outlays"].pct_change(3) - out[
        "federal_receipts"
    ].pct_change(3)
    out["deficit_change_3m"] = out["deficit"].diff(3)
    for column in [
        "deficit_3m_sum",
        "deficit_12m_sum",
        "balance_3m_sum",
        "receipts_yoy_growth",
        "outlays_yoy_growth",
        "fiscal_impulse_3m",
        "deficit_change_3m",
    ]:
        out[f"{column}_rank_120m"] = _rolling_last_percentile(
            out[column],
            rank_window_months,
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
    parser.add_argument("--availability-lag-days", type=int, default=60)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        availability_lag_days=args.availability_lag_days,
    )
    valid = features.dropna(
        subset=[
            "deficit_3m_sum_rank_120m",
            "deficit_12m_sum_rank_120m",
            "receipts_yoy_growth_rank_120m",
            "fiscal_impulse_3m_rank_120m",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
