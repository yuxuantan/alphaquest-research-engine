from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_UMCSENT_CACHE = "data/external/fred_umcsent_consumer_sentiment_1952_2026.csv"
DEFAULT_OUTPUT = "data/external/es_consumer_sentiment_features_20110103_20260609.csv"
UMCSENT_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=UMCSENT"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    sentiment_input: str | Path | None = None,
    sentiment_cache: str | Path = DEFAULT_UMCSENT_CACHE,
    availability_lag_days: int = 45,
    rank_window_months: int = 120,
    rank_min_periods: int = 36,
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

    sentiment = _load_sentiment(
        sentiment_input=sentiment_input,
        sentiment_cache=sentiment_cache,
    )
    sentiment = _add_sentiment_features(
        sentiment,
        rank_window_months=rank_window_months,
        rank_min_periods=rank_min_periods,
    )

    # FRED notes that UMCSENT is delayed by one month at the source.  A
    # 45-calendar-day lag avoids using preliminary/current-month values in an
    # intraday futures signal and is intentionally conservative.
    merged = pd.merge_asof(
        sessions.sort_values("available_observation_cutoff"),
        sentiment.sort_values("observation_date"),
        left_on="available_observation_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged = merged.drop(columns=["session_date_ts", "available_observation_cutoff"])

    columns = [
        "session_date",
        "observation_date",
        "consumer_sentiment",
        "sentiment_change_1m",
        "sentiment_change_3m",
        "sentiment_change_6m",
        "sentiment_ma_3",
        "sentiment_ma_12",
        "consumer_sentiment_rank_120m",
        "sentiment_change_1m_rank_120m",
        "sentiment_change_3m_rank_120m",
        "sentiment_change_6m_rank_120m",
        "sentiment_ma_3_rank_120m",
        "sentiment_ma_12_rank_120m",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_sentiment(
    *,
    sentiment_input: str | Path | None,
    sentiment_cache: str | Path,
) -> pd.DataFrame:
    if sentiment_input is not None:
        raw = pd.read_csv(sentiment_input)
    else:
        cache_path = Path(sentiment_cache)
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            raw = _read_csv_with_retries(UMCSENT_URL)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)

    column_map = {_normalize_column(column): column for column in raw.columns}
    date_col = _required(column_map, "observation date")
    value_col = _required(column_map, "umcsent")
    out = raw[[date_col, value_col]].copy()
    out.columns = ["observation_date", "consumer_sentiment"]
    out["observation_date"] = pd.to_datetime(out["observation_date"], errors="coerce")
    out["consumer_sentiment"] = pd.to_numeric(out["consumer_sentiment"], errors="coerce")
    return (
        out.dropna(subset=["observation_date", "consumer_sentiment"], how="any")
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _add_sentiment_features(
    sentiment: pd.DataFrame,
    *,
    rank_window_months: int,
    rank_min_periods: int,
) -> pd.DataFrame:
    out = sentiment.copy()
    out["sentiment_change_1m"] = out["consumer_sentiment"].diff()
    out["sentiment_change_3m"] = out["consumer_sentiment"] - out["consumer_sentiment"].shift(3)
    out["sentiment_change_6m"] = out["consumer_sentiment"] - out["consumer_sentiment"].shift(6)
    out["sentiment_ma_3"] = out["consumer_sentiment"].rolling(3, min_periods=2).mean()
    out["sentiment_ma_12"] = out["consumer_sentiment"].rolling(12, min_periods=6).mean()
    for column in [
        "consumer_sentiment",
        "sentiment_change_1m",
        "sentiment_change_3m",
        "sentiment_change_6m",
        "sentiment_ma_3",
        "sentiment_ma_12",
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
            request = Request(url)
            with urlopen(request, timeout=30) as response:
                return pd.read_csv(BytesIO(response.read()))
        except Exception as exc:  # pragma: no cover - exercised only on network failures.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download free UMCSENT CSV after {attempts} attempts: {url}") from last_error


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
        raise ValueError(f"UMCSENT input is missing required column: {key}")
    return column_map[key]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--sentiment-input", default=None)
    parser.add_argument("--sentiment-cache", default=DEFAULT_UMCSENT_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-days", type=int, default=45)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        sentiment_input=args.sentiment_input,
        sentiment_cache=args.sentiment_cache,
        availability_lag_days=args.availability_lag_days,
    )
    valid = features.dropna(
        subset=[
            "consumer_sentiment_rank_120m",
            "sentiment_change_3m_rank_120m",
            "sentiment_ma_12_rank_120m",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"availability_lag_days={args.availability_lag_days}")


if __name__ == "__main__":
    main()
