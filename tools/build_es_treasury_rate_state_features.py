from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_RATES_CACHE = "data/external/us_treasury_daily_yield_curve_rates_2010_2026.csv"
DEFAULT_OUTPUT = "data/external/es_treasury_rate_state_features_20110103_20260609.csv"
FRED_URLS = {
    "DGS10": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "DGS2": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2",
}
TREASURY_DAILY_RATES_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    rates_input: str | Path | None = None,
    rates_cache: str | Path = DEFAULT_RATES_CACHE,
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

    rates = _load_rates(rates_input=rates_input, rates_cache=rates_cache)
    rates = _add_rate_features(rates)

    # Treasury close/fixing values for session D are not assumed tradable during
    # that same RTH session.  Each ES session receives the latest Treasury row
    # whose observation_date is strictly before the ES session date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        rates.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    )
    merged = merged.drop(columns=["session_date_ts"])

    for column in [
        "dgs10",
        "dgs2",
        "curve_10y2y",
        "dgs10_change_1d",
        "dgs2_change_1d",
        "curve_change_1d",
        "dgs10_change_5d",
        "curve_change_5d",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "dgs10",
        "dgs2",
        "curve_10y2y",
        "dgs10_change_1d",
        "dgs2_change_1d",
        "curve_change_1d",
        "dgs10_change_5d",
        "curve_change_5d",
        "dgs10_rank_252",
        "dgs2_rank_252",
        "curve_10y2y_rank_252",
        "dgs10_change_1d_rank_252",
        "dgs2_change_1d_rank_252",
        "curve_change_1d_rank_252",
        "dgs10_change_5d_rank_252",
        "curve_change_5d_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_rates(*, rates_input: str | Path | None, rates_cache: str | Path) -> pd.DataFrame:
    if rates_input is not None:
        raw = pd.read_csv(rates_input)
    else:
        cache_path = Path(rates_cache)
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            try:
                raw = _download_treasury_daily_rates()
            except Exception:
                raw = _download_fred_rates()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)

    column_map = {_normalize_column(column): column for column in raw.columns}
    date_col = _first_existing(column_map, ["observation_date", "observation date", "date"])
    dgs10_col = _first_existing(column_map, ["dgs10", "10 yr", "10 year"])
    dgs2_col = _first_existing(column_map, ["dgs2", "2 yr", "2 year"])
    if date_col is None or dgs10_col is None or dgs2_col is None:
        raise ValueError("Rates input must include date, 10-year, and 2-year columns.")
    out = raw.rename(columns={date_col: "observation_date"}).copy()
    out["dgs10"] = pd.to_numeric(out[dgs10_col], errors="coerce")
    out["dgs2"] = pd.to_numeric(out[dgs2_col], errors="coerce")
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    return (
        out[["observation_date", "dgs10", "dgs2"]]
        .dropna(subset=["dgs10", "dgs2"], how="any")
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _download_treasury_daily_rates(start_year: int = 2010, end_year: int = 2026) -> pd.DataFrame:
    frames = []
    for year in range(start_year, end_year + 1):
        frame = _read_csv_with_retries(TREASURY_DAILY_RATES_URL.format(year=year))
        if frame.empty:
            continue
        frames.append(frame)
    if not frames:
        raise RuntimeError("No Treasury daily-rate rows downloaded.")
    raw = pd.concat(frames, ignore_index=True)
    return pd.DataFrame(
        {
            "observation_date": raw["Date"],
            "DGS10": pd.to_numeric(raw["10 Yr"], errors="coerce"),
            "DGS2": pd.to_numeric(raw["2 Yr"], errors="coerce"),
        }
    )


def _download_fred_rates() -> pd.DataFrame:
    frames = []
    for series_id, url in FRED_URLS.items():
        frame = _read_csv_with_retries(url)
        date_col = "observation_date" if "observation_date" in frame.columns else "DATE"
        value_col = series_id
        frame = frame[[date_col, value_col]].copy()
        frame.columns = ["observation_date", series_id]
        frames.append(frame)
    raw = frames[0]
    for frame in frames[1:]:
        raw = raw.merge(frame, on="observation_date", how="outer")
    return raw


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
    raise RuntimeError(f"Failed to download free rates CSV after {attempts} attempts: {url}") from last_error


def _normalize_column(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _first_existing(column_map: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        if key in column_map:
            return column_map[key]
    return None


def _add_rate_features(rates: pd.DataFrame) -> pd.DataFrame:
    out = rates.copy()
    out["curve_10y2y"] = out["dgs10"] - out["dgs2"]
    out["dgs10_change_1d"] = out["dgs10"].diff()
    out["dgs2_change_1d"] = out["dgs2"].diff()
    out["curve_change_1d"] = out["curve_10y2y"].diff()
    out["dgs10_change_5d"] = out["dgs10"] - out["dgs10"].shift(5)
    out["curve_change_5d"] = out["curve_10y2y"] - out["curve_10y2y"].shift(5)
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
    parser.add_argument("--rates-input", default=None)
    parser.add_argument("--rates-cache", default=DEFAULT_RATES_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        rates_input=args.rates_input,
        rates_cache=args.rates_cache,
    )
    valid = features.dropna(subset=["dgs10_change_1d_rank_252", "curve_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
