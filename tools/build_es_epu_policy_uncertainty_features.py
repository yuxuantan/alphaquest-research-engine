from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_EPU_CACHE = "data/external/us_daily_epu_policy_uncertainty_1985_2026.csv"
DEFAULT_OUTPUT = "data/external/es_epu_policy_uncertainty_features_20110103_20260609.csv"
EPU_DAILY_URL = "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    epu_input: str | Path | None = None,
    epu_cache: str | Path = DEFAULT_EPU_CACHE,
    availability_lag_days: int = 30,
    rank_min_periods: int = 60,
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
    sessions["available_observation_cutoff"] = sessions["session_date_ts"] - pd.Timedelta(
        days=availability_lag_days
    )

    epu = _load_epu(epu_input=epu_input, epu_cache=epu_cache)
    epu = _add_epu_features(epu)

    # The Daily EPU page says the latest 30 days are revised as newspaper
    # coverage is updated.  To avoid real-time revision leakage, each ES
    # session uses only an EPU observation at least availability_lag_days old.
    merged = pd.merge_asof(
        sessions.sort_values("available_observation_cutoff"),
        epu.sort_values("observation_date"),
        left_on="available_observation_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged = merged.drop(columns=["session_date_ts", "available_observation_cutoff"])

    for column in [
        "epu_index",
        "epu_change_1d",
        "epu_change_5d",
        "epu_change_20d",
        "epu_ma_5",
        "epu_ma_20",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "epu_index",
        "epu_change_1d",
        "epu_change_5d",
        "epu_change_20d",
        "epu_ma_5",
        "epu_ma_20",
        "epu_index_rank_252",
        "epu_change_1d_rank_252",
        "epu_change_5d_rank_252",
        "epu_change_20d_rank_252",
        "epu_ma_5_rank_252",
        "epu_ma_20_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_epu(*, epu_input: str | Path | None, epu_cache: str | Path) -> pd.DataFrame:
    if epu_input is not None:
        raw = pd.read_csv(epu_input)
    else:
        cache_path = Path(epu_cache)
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            raw = _read_csv_with_retries(EPU_DAILY_URL)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)

    column_map = {_normalize_column(column): column for column in raw.columns}
    day_col = _required(column_map, "day")
    month_col = _required(column_map, "month")
    year_col = _required(column_map, "year")
    index_col = _required(column_map, "daily policy index")

    out = raw[[day_col, month_col, year_col, index_col]].copy()
    out.columns = ["day", "month", "year", "epu_index"]
    out["observation_date"] = pd.to_datetime(
        {
            "year": pd.to_numeric(out["year"], errors="coerce"),
            "month": pd.to_numeric(out["month"], errors="coerce"),
            "day": pd.to_numeric(out["day"], errors="coerce"),
        },
        errors="coerce",
    )
    out["epu_index"] = pd.to_numeric(out["epu_index"], errors="coerce")
    return (
        out[["observation_date", "epu_index"]]
        .dropna(subset=["observation_date", "epu_index"], how="any")
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _add_epu_features(epu: pd.DataFrame) -> pd.DataFrame:
    out = epu.copy()
    out["epu_change_1d"] = out["epu_index"].diff()
    out["epu_change_5d"] = out["epu_index"] - out["epu_index"].shift(5)
    out["epu_change_20d"] = out["epu_index"] - out["epu_index"].shift(20)
    out["epu_ma_5"] = out["epu_index"].rolling(5, min_periods=3).mean()
    out["epu_ma_20"] = out["epu_index"].rolling(20, min_periods=10).mean()
    return out


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
    raise RuntimeError(f"Failed to download free Daily EPU CSV after {attempts} attempts: {url}") from last_error


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _normalize_column(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _required(column_map: dict[str, str], key: str) -> str:
    if key not in column_map:
        raise ValueError(f"Daily EPU input is missing required column: {key}")
    return column_map[key]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--epu-input", default=None)
    parser.add_argument("--epu-cache", default=DEFAULT_EPU_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-days", type=int, default=30)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        epu_input=args.epu_input,
        epu_cache=args.epu_cache,
        availability_lag_days=args.availability_lag_days,
    )
    valid = features.dropna(
        subset=["epu_index_rank_252", "epu_change_1d_rank_252", "epu_change_5d_rank_252"]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"availability_lag_days={args.availability_lag_days}")


if __name__ == "__main__":
    main()
