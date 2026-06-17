from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_SKEW_CACHE = "data/external/cboe_skew_history.csv"
DEFAULT_OUTPUT = "data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv"
DEFAULT_SKEW_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    skew_input: str | Path | None = None,
    skew_cache: str | Path = DEFAULT_SKEW_CACHE,
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

    skew = _load_skew_history(
        input_path=skew_input,
        cache_path=skew_cache,
        url=DEFAULT_SKEW_URL,
    )

    # Cboe SKEW is an end-of-day option-implied tail-risk index. Same-date
    # closes are unavailable to an intraday ES signal, so merge only the latest
    # Cboe observation strictly before the ES session date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        skew.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    merged["skew_change_1d"] = merged["skew_close"] - merged["skew_close"].shift(1)
    merged["skew_change_5d"] = merged["skew_close"] - merged["skew_close"].shift(5)
    merged["skew_5d_mean"] = merged["skew_close"].rolling(5, min_periods=3).mean()

    for column in [
        "skew_close",
        "skew_change_1d",
        "skew_change_5d",
        "skew_5d_mean",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "skew_close",
        "skew_change_1d",
        "skew_change_5d",
        "skew_5d_mean",
        "skew_close_rank_252",
        "skew_change_1d_rank_252",
        "skew_change_5d_rank_252",
        "skew_5d_mean_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_skew_history(
    *,
    input_path: str | Path | None,
    cache_path: str | Path,
    url: str,
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

    date_col = "DATE" if "DATE" in raw.columns else "observation_date"
    close_col = "SKEW" if "SKEW" in raw.columns else "skew_close"
    if close_col not in raw.columns:
        raise ValueError(f"Input is missing required SKEW column: {close_col}")
    out = raw[[date_col, close_col]].copy()
    out.columns = ["observation_date", "skew_close"]
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out["skew_close"] = pd.to_numeric(out["skew_close"], errors="coerce")
    return (
        out.dropna(subset=["skew_close"])
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
    parser.add_argument("--skew-input", default=None)
    parser.add_argument("--skew-cache", default=DEFAULT_SKEW_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        skew_input=args.skew_input,
        skew_cache=args.skew_cache,
    )
    valid = features.dropna(
        subset=[
            "skew_close_rank_252",
            "skew_change_1d_rank_252",
            "skew_5d_mean_rank_252",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
