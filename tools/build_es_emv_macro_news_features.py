from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_emv_macro_news_features_20110103_20260609.csv"
DEFAULT_CACHE_DIR = "data/external/fred_emv_macro_news"
FRED_SERIES = {
    "emv_macro_news": "EMVMACRONEWS",
    "emv_business": "EMVMACROBUS",
    "emv_labor": "EMVMACROLABORMKT",
    "emv_interest_rates": "EMVMACROINTEREST",
}


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    release_lag_days: int = 21,
    rank_min_periods: int = 36,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])

    monthly = _load_fred_series(cache_dir)
    monthly = _add_features(monthly, rank_min_periods=rank_min_periods)
    monthly["availability_date"] = (
        monthly["observation_date"] + pd.offsets.MonthEnd(0) + pd.Timedelta(days=release_lag_days)
    )

    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        monthly.sort_values("availability_date"),
        left_on="session_date_ts",
        right_on="availability_date",
        direction="backward",
        allow_exact_matches=True,
    ).drop(columns=["session_date_ts"])

    columns = [
        "session_date",
        "observation_date",
        "availability_date",
        "emv_macro_news",
        "emv_business",
        "emv_labor",
        "emv_interest_rates",
        "emv_macro_news_change_1m",
        "emv_macro_news_change_3m",
        "emv_interest_rates_change_1m",
        "emv_labor_change_1m",
        "emv_macro_news_rank_120m",
        "emv_macro_news_change_1m_rank_120m",
        "emv_macro_news_change_3m_rank_120m",
        "emv_interest_rates_rank_120m",
        "emv_interest_rates_change_1m_rank_120m",
        "emv_labor_rank_120m",
        "emv_labor_change_1m_rank_120m",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    out["availability_date"] = pd.to_datetime(out["availability_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_fred_series(cache_dir: str | Path) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for column, series_id in FRED_SERIES.items():
        cache_path = cache_dir / f"{series_id.lower()}.csv"
        if cache_path.exists():
            frame = pd.read_csv(cache_path)
        else:
            frame = _read_fred_csv(series_id)
            frame.to_csv(cache_path, index=False)
        date_col = "observation_date" if "observation_date" in frame.columns else "DATE"
        value_col = series_id if series_id in frame.columns else frame.columns[-1]
        frame = frame[[date_col, value_col]].copy()
        frame.columns = ["observation_date", column]
        frame["observation_date"] = pd.to_datetime(frame["observation_date"])
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frames.append(frame.dropna(subset=[column]))

    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="observation_date", how="outer")
    return (
        out.sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _read_fred_csv(series_id: str, attempts: int = 4, sleep_seconds: float = 2.0) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
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
        except Exception as exc:  # pragma: no cover - exercised only on network failures.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download FRED CSV for {series_id}") from last_error


def _add_features(monthly: pd.DataFrame, *, rank_min_periods: int) -> pd.DataFrame:
    out = monthly.copy()
    out["emv_macro_news_change_1m"] = out["emv_macro_news"].diff()
    out["emv_macro_news_change_3m"] = out["emv_macro_news"] - out["emv_macro_news"].shift(3)
    out["emv_interest_rates_change_1m"] = out["emv_interest_rates"].diff()
    out["emv_labor_change_1m"] = out["emv_labor"].diff()
    for column in [
        "emv_macro_news",
        "emv_macro_news_change_1m",
        "emv_macro_news_change_3m",
        "emv_interest_rates",
        "emv_interest_rates_change_1m",
        "emv_labor",
        "emv_labor_change_1m",
    ]:
        out[f"{column}_rank_120m"] = _rolling_last_percentile(
            out[column], 120, rank_min_periods
        )
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
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--release-lag-days", type=int, default=21)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        release_lag_days=args.release_lag_days,
    )
    valid = features.dropna(subset=["emv_macro_news_rank_120m"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
