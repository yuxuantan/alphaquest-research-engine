from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_IMPORT_ALL_CACHE = "data/external/fred_import_price_all_ir_1982_2026.csv"
DEFAULT_IMPORT_EXFUEL_CACHE = "data/external/fred_import_price_exfuel_irexfuels_2001_2026.csv"
DEFAULT_EXPORT_ALL_CACHE = "data/external/fred_export_price_all_iq_1983_2026.csv"
DEFAULT_OUTPUT = "data/external/es_import_export_price_pressure_features_20110103_20260609.csv"

FRED_CSV_URLS = {
    "import_all": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IR",
    "import_exfuel": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IREXFUELS",
    "export_all": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IQ",
}


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    import_all_input: str | Path | None = None,
    import_exfuel_input: str | Path | None = None,
    export_all_input: str | Path | None = None,
    import_all_cache: str | Path = DEFAULT_IMPORT_ALL_CACHE,
    import_exfuel_cache: str | Path = DEFAULT_IMPORT_EXFUEL_CACHE,
    export_all_cache: str | Path = DEFAULT_EXPORT_ALL_CACHE,
    availability_lag_calendar_days_after_month: int = 51,
    rank_min_periods: int = 36,
) -> pd.DataFrame:
    if availability_lag_calendar_days_after_month < 31:
        raise ValueError("availability_lag_calendar_days_after_month must be at least 31.")

    sessions = _load_sessions(bars_input)
    monthly = _load_monthly_indexes(
        import_all_input=import_all_input,
        import_exfuel_input=import_exfuel_input,
        export_all_input=export_all_input,
        import_all_cache=import_all_cache,
        import_exfuel_cache=import_exfuel_cache,
        export_all_cache=export_all_cache,
    )
    monthly = _add_monthly_features(monthly, rank_min_periods=rank_min_periods)
    monthly["availability_date"] = (
        pd.to_datetime(monthly["observation_date"])
        + pd.to_timedelta(availability_lag_calendar_days_after_month, unit="D")
    )

    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        monthly.sort_values("availability_date"),
        left_on="session_date_ts",
        right_on="availability_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")

    columns = [
        "session_date",
        "observation_date",
        "availability_date",
        "availability_lag_calendar_days_after_month",
        "import_all_index",
        "import_exfuel_index",
        "export_all_index",
        "import_all_mom1",
        "import_all_mom3",
        "import_exfuel_mom1",
        "import_exfuel_mom3",
        "export_all_mom1",
        "export_all_mom3",
        "core_vs_headline_mom3",
        "import_vs_export_mom3",
        "import_all_mom3_rank_120m",
        "import_exfuel_mom3_rank_120m",
        "export_all_mom3_rank_120m",
        "core_vs_headline_rank_120m",
        "import_vs_export_rank_120m",
    ]
    merged["availability_lag_calendar_days_after_month"] = availability_lag_calendar_days_after_month
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    for column in ["observation_date", "availability_date"]:
        out[column] = pd.to_datetime(out[column], errors="coerce").dt.date.astype(str)

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


def _load_monthly_indexes(
    *,
    import_all_input: str | Path | None,
    import_exfuel_input: str | Path | None,
    export_all_input: str | Path | None,
    import_all_cache: str | Path,
    import_exfuel_cache: str | Path,
    export_all_cache: str | Path,
) -> pd.DataFrame:
    frames = [
        _load_or_download_fred(
            input_path=import_all_input,
            cache_path=import_all_cache,
            url=FRED_CSV_URLS["import_all"],
            fred_id="IR",
            value_name="import_all_index",
        ),
        _load_or_download_fred(
            input_path=import_exfuel_input,
            cache_path=import_exfuel_cache,
            url=FRED_CSV_URLS["import_exfuel"],
            fred_id="IREXFUELS",
            value_name="import_exfuel_index",
        ),
        _load_or_download_fred(
            input_path=export_all_input,
            cache_path=export_all_cache,
            url=FRED_CSV_URLS["export_all"],
            fred_id="IQ",
            value_name="export_all_index",
        ),
    ]
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="observation_date", how="outer")
    return (
        out.sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _load_or_download_fred(
    *,
    input_path: str | Path | None,
    cache_path: str | Path,
    url: str,
    fred_id: str,
    value_name: str,
) -> pd.DataFrame:
    if input_path is not None:
        raw = pd.read_csv(input_path)
    else:
        cache = Path(cache_path)
        if cache.exists():
            raw = pd.read_csv(cache)
        else:
            raw = pd.read_csv(url)
            cache.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache, index=False)
    column_map = {str(column).strip().lower(): column for column in raw.columns}
    date_col = column_map.get("observation_date") or column_map.get("date")
    value_col = column_map.get(fred_id.lower()) or column_map.get(value_name.lower())
    if date_col is None or value_col is None:
        raise ValueError(f"Could not find observation_date and {fred_id} columns in FRED input.")
    out = raw.rename(columns={date_col: "observation_date", value_col: value_name}).copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"], errors="coerce")
    out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
    return (
        out[["observation_date", value_name]]
        .dropna(subset=["observation_date", value_name])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _add_monthly_features(monthly: pd.DataFrame, *, rank_min_periods: int) -> pd.DataFrame:
    out = monthly.copy()
    for column in ["import_all_index", "import_exfuel_index", "export_all_index"]:
        out[f"{column.removesuffix('_index')}_mom1"] = out[column] / out[column].shift(1) - 1.0
        out[f"{column.removesuffix('_index')}_mom3"] = out[column] / out[column].shift(3) - 1.0
    out["core_vs_headline_mom3"] = out["import_exfuel_mom3"] - out["import_all_mom3"]
    out["import_vs_export_mom3"] = out["import_all_mom3"] - out["export_all_mom3"]
    for column in [
        "import_all_mom3",
        "import_exfuel_mom3",
        "export_all_mom3",
        "core_vs_headline",
        "import_vs_export",
    ]:
        source = column if column.endswith("_mom3") else f"{column}_mom3"
        rank_name = f"{column}_rank_120m" if column.endswith("_mom3") else f"{column}_rank_120m"
        out[rank_name] = _rolling_last_percentile(out[source], 120, rank_min_periods)
    return out


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
    parser.add_argument("--import-all-input", default=None)
    parser.add_argument("--import-exfuel-input", default=None)
    parser.add_argument("--export-all-input", default=None)
    parser.add_argument("--import-all-cache", default=DEFAULT_IMPORT_ALL_CACHE)
    parser.add_argument("--import-exfuel-cache", default=DEFAULT_IMPORT_EXFUEL_CACHE)
    parser.add_argument("--export-all-cache", default=DEFAULT_EXPORT_ALL_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-calendar-days-after-month", type=int, default=51)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        import_all_input=args.import_all_input,
        import_exfuel_input=args.import_exfuel_input,
        export_all_input=args.export_all_input,
        import_all_cache=args.import_all_cache,
        import_exfuel_cache=args.import_exfuel_cache,
        export_all_cache=args.export_all_cache,
        availability_lag_calendar_days_after_month=args.availability_lag_calendar_days_after_month,
    )
    valid = features.dropna(subset=["import_all_mom3_rank_120m", "core_vs_headline_rank_120m"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(
        "observation_range="
        f"{features['observation_date'].min()}..{features['observation_date'].max()}"
    )


if __name__ == "__main__":
    main()
