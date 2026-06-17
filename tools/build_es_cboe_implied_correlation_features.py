from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_COR1M_CACHE = "data/external/cboe_cor1m_history.csv"
DEFAULT_COR3M_CACHE = "data/external/cboe_cor3m_history.csv"
DEFAULT_OUTPUT = "data/external/es_cboe_implied_correlation_features_20110103_20260609.csv"
DEFAULT_COR1M_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/COR1M_History.csv"
DEFAULT_COR3M_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/COR3M_History.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    cor1m_input: str | Path | None = None,
    cor3m_input: str | Path | None = None,
    cor1m_cache: str | Path = DEFAULT_COR1M_CACHE,
    cor3m_cache: str | Path = DEFAULT_COR3M_CACHE,
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

    cor1m = _load_index_history(
        input_path=cor1m_input,
        cache_path=cor1m_cache,
        url=DEFAULT_COR1M_URL,
        value_name="cor1m_close",
    )
    cor3m = _load_index_history(
        input_path=cor3m_input,
        cache_path=cor3m_cache,
        url=DEFAULT_COR3M_URL,
        value_name="cor3m_close",
    )
    cboe = pd.merge(cor1m, cor3m, on="observation_date", how="outer").sort_values(
        "observation_date", kind="mergesort"
    )
    cboe[["cor1m_close", "cor3m_close"]] = cboe[["cor1m_close", "cor3m_close"]].ffill()
    cboe = cboe.dropna(subset=["cor1m_close", "cor3m_close"], how="any")

    # Cboe end-of-day implied-correlation values are unavailable to an intraday
    # ES signal on the same session date. Merge only the latest prior close.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        cboe.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    merged["cor3m_change_1d"] = merged["cor3m_close"] - merged["cor3m_close"].shift(1)
    merged["cor3m_change_5d"] = merged["cor3m_close"] - merged["cor3m_close"].shift(5)
    merged["cor1m_minus_cor3m"] = merged["cor1m_close"] - merged["cor3m_close"]

    for column in [
        "cor1m_close",
        "cor3m_close",
        "cor3m_change_1d",
        "cor3m_change_5d",
        "cor1m_minus_cor3m",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "cor1m_close",
        "cor3m_close",
        "cor3m_change_1d",
        "cor3m_change_5d",
        "cor1m_minus_cor3m",
        "cor1m_close_rank_252",
        "cor3m_close_rank_252",
        "cor3m_change_1d_rank_252",
        "cor3m_change_5d_rank_252",
        "cor1m_minus_cor3m_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_index_history(
    *,
    input_path: str | Path | None,
    cache_path: str | Path,
    url: str,
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

    date_col = "DATE" if "DATE" in raw.columns else "observation_date"
    close_col = "CLOSE" if "CLOSE" in raw.columns else value_name
    if close_col not in raw.columns:
        raise ValueError(f"Input is missing required close column: {close_col}")
    out = raw[[date_col, close_col]].copy()
    out.columns = ["observation_date", value_name]
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
    return (
        out.dropna(subset=[value_name])
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
    parser.add_argument("--cor1m-input", default=None)
    parser.add_argument("--cor3m-input", default=None)
    parser.add_argument("--cor1m-cache", default=DEFAULT_COR1M_CACHE)
    parser.add_argument("--cor3m-cache", default=DEFAULT_COR3M_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cor1m_input=args.cor1m_input,
        cor3m_input=args.cor3m_input,
        cor1m_cache=args.cor1m_cache,
        cor3m_cache=args.cor3m_cache,
    )
    valid = features.dropna(
        subset=[
            "cor3m_close_rank_252",
            "cor3m_change_1d_rank_252",
            "cor1m_minus_cor3m_rank_252",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
