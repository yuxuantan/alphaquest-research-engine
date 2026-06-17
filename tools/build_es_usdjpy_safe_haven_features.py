from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_USDJPY_CACHE = "data/external/fred_dexjpus_usdjpy_1971_2026.csv"
DEFAULT_OUTPUT = "data/external/es_usdjpy_safe_haven_features_20110103_20260609.csv"
FRED_DEXJPUS_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXJPUS"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    usdjpy_input: str | Path | None = None,
    usdjpy_cache: str | Path = DEFAULT_USDJPY_CACHE,
    availability_lag_business_days: int = 1,
    rank_min_periods: int = 60,
) -> pd.DataFrame:
    if availability_lag_business_days < 0:
        raise ValueError("availability_lag_business_days must be non-negative.")

    sessions = _load_sessions(bars_input)
    usdjpy = _load_usdjpy(usdjpy_input=usdjpy_input, usdjpy_cache=usdjpy_cache)
    usdjpy = _add_usdjpy_features(usdjpy)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - BDay(availability_lag_business_days)
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff"),
        usdjpy.sort_values("observation_date"),
        left_on="availability_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")

    for column in [
        "usdjpy",
        "usdjpy_return_1d",
        "usdjpy_return_5d",
        "usdjpy_abs_return_1d",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    merged["availability_lag_business_days"] = availability_lag_business_days
    columns = [
        "session_date",
        "observation_date",
        "availability_cutoff",
        "availability_lag_business_days",
        "usdjpy",
        "usdjpy_return_1d",
        "usdjpy_return_5d",
        "usdjpy_abs_return_1d",
        "usdjpy_rank_252",
        "usdjpy_return_1d_rank_252",
        "usdjpy_return_5d_rank_252",
        "usdjpy_abs_return_1d_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    for column in ["observation_date", "availability_cutoff"]:
        out[column] = pd.to_datetime(out[column]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_sessions(bars_input: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    return sessions


def _load_usdjpy(
    *,
    usdjpy_input: str | Path | None,
    usdjpy_cache: str | Path,
) -> pd.DataFrame:
    if usdjpy_input is not None:
        raw = pd.read_csv(usdjpy_input)
    else:
        cache = Path(usdjpy_cache)
        if cache.exists():
            raw = pd.read_csv(cache)
        else:
            raw = _read_csv_with_retries(FRED_DEXJPUS_URL)
            cache.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache, index=False)

    column_map = {_normalize_column(column): column for column in raw.columns}
    date_col = _first_existing(column_map, ["observation date", "date"])
    value_col = _first_existing(column_map, ["dexjpus", "usdjpy", "value"])
    if date_col is None or value_col is None:
        raise ValueError("USD/JPY input must include DATE/observation_date and DEXJPUS columns.")

    out = raw.rename(columns={date_col: "observation_date", value_col: "usdjpy"}).copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"], errors="coerce")
    out["usdjpy"] = pd.to_numeric(out["usdjpy"], errors="coerce")
    return (
        out[["observation_date", "usdjpy"]]
        .dropna(subset=["observation_date", "usdjpy"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _read_csv_with_retries(url: str, attempts: int = 4, sleep_seconds: float = 2.0) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                return pd.read_csv(BytesIO(response.read()))
        except Exception as exc:  # pragma: no cover - exercised only on network failures.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download free FRED USD/JPY CSV after {attempts} attempts.") from last_error


def _add_usdjpy_features(usdjpy: pd.DataFrame) -> pd.DataFrame:
    out = usdjpy.copy()
    out["usdjpy_return_1d"] = out["usdjpy"].pct_change(fill_method=None)
    out["usdjpy_return_5d"] = out["usdjpy"] / out["usdjpy"].shift(5) - 1.0
    out["usdjpy_abs_return_1d"] = out["usdjpy_return_1d"].abs()
    return out


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _normalize_column(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _first_existing(column_map: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        if key in column_map:
            return column_map[key]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--usdjpy-input", default=None)
    parser.add_argument("--usdjpy-cache", default=DEFAULT_USDJPY_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-business-days", type=int, default=1)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        usdjpy_input=args.usdjpy_input,
        usdjpy_cache=args.usdjpy_cache,
        availability_lag_business_days=args.availability_lag_business_days,
    )
    valid = features.dropna(subset=["usdjpy_return_1d_rank_252", "usdjpy_return_5d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
