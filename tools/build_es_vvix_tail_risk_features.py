from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_VVIX_CACHE = "data/external/cboe_vvix_history.csv"
DEFAULT_VIX_CACHE = "data/external/cboe_vix_history.csv"
DEFAULT_OUTPUT = "data/external/es_vvix_tail_risk_features_20110103_20260609.csv"
DEFAULT_VVIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv"
DEFAULT_VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    vvix_input: str | Path | None = None,
    vix_input: str | Path | None = None,
    vvix_cache: str | Path = DEFAULT_VVIX_CACHE,
    vix_cache: str | Path = DEFAULT_VIX_CACHE,
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

    vvix = _load_index_history(
        input_path=vvix_input,
        cache_path=vvix_cache,
        url=DEFAULT_VVIX_URL,
        value_name="vvix_close",
        fallback_close_column="VVIX",
    )
    vix = _load_index_history(
        input_path=vix_input,
        cache_path=vix_cache,
        url=DEFAULT_VIX_URL,
        value_name="vix_close",
        fallback_close_column="VIXCLS",
    )
    cboe = pd.merge(vvix, vix, on="observation_date", how="outer").sort_values(
        "observation_date", kind="mergesort"
    )
    cboe[["vvix_close", "vix_close"]] = cboe[["vvix_close", "vix_close"]].ffill()
    cboe = cboe.dropna(subset=["vvix_close", "vix_close"], how="any")

    # Cboe daily closes are known only after that trading day's close.  ES
    # intraday sessions therefore use the latest Cboe observation strictly
    # before the ES session date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        cboe.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    merged["vvix_vix_ratio"] = merged["vvix_close"] / merged["vix_close"].where(
        merged["vix_close"] > 0
    )
    merged["vvix_change_1d"] = merged["vvix_close"] - merged["vvix_close"].shift(1)
    merged["vvix_change_5d"] = merged["vvix_close"] - merged["vvix_close"].shift(5)
    merged["vix_change_1d"] = merged["vix_close"] - merged["vix_close"].shift(1)

    for column in [
        "vvix_close",
        "vix_close",
        "vvix_vix_ratio",
        "vvix_change_1d",
        "vvix_change_5d",
        "vix_change_1d",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "vvix_close",
        "vix_close",
        "vvix_vix_ratio",
        "vvix_change_1d",
        "vvix_change_5d",
        "vix_change_1d",
        "vvix_close_rank_252",
        "vix_close_rank_252",
        "vvix_vix_ratio_rank_252",
        "vvix_change_1d_rank_252",
        "vvix_change_5d_rank_252",
        "vix_change_1d_rank_252",
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
    fallback_close_column: str,
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
    close_col = "CLOSE" if "CLOSE" in raw.columns else fallback_close_column
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
    parser.add_argument("--vvix-input", default=None)
    parser.add_argument("--vix-input", default=None)
    parser.add_argument("--vvix-cache", default=DEFAULT_VVIX_CACHE)
    parser.add_argument("--vix-cache", default=DEFAULT_VIX_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        vvix_input=args.vvix_input,
        vix_input=args.vix_input,
        vvix_cache=args.vvix_cache,
        vix_cache=args.vix_cache,
    )
    valid = features.dropna(
        subset=[
            "vvix_close_rank_252",
            "vvix_change_1d_rank_252",
            "vvix_vix_ratio_rank_252",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
