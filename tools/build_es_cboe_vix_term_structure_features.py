from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv"
DEFAULT_CACHE_DIR = "data/external"
VIX_URLS = {
    "vix": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    "vix9d": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX9D_History.csv",
    "vix3m": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv",
    "vix6m": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX6M_History.csv",
}


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    input_paths: dict[str, str | Path] | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
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

    frames = []
    for key, url in VIX_URLS.items():
        input_path = (input_paths or {}).get(key)
        cache_path = Path(cache_dir) / f"cboe_{key}_history.csv"
        frames.append(
            _load_index_history(
                input_path=input_path,
                cache_path=cache_path,
                url=url,
                value_name=f"{key}_close",
            )
        )
    cboe = frames[0]
    for frame in frames[1:]:
        cboe = cboe.merge(frame, on="observation_date", how="outer")
    value_columns = [column for column in cboe.columns if column != "observation_date"]
    cboe = cboe.sort_values("observation_date", kind="mergesort")
    cboe[value_columns] = cboe[value_columns].ffill()
    cboe = cboe.dropna(subset=value_columns, how="any")

    # Cboe daily volatility-index closes are known after the U.S. options close.
    # Intraday ES signals use only the latest Cboe observation strictly before
    # the ES session date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        cboe.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    merged["vix_vix3m_ratio"] = merged["vix_close"] / merged["vix3m_close"].where(
        merged["vix3m_close"] > 0
    )
    merged["vix9d_vix_ratio"] = merged["vix9d_close"] / merged["vix_close"].where(
        merged["vix_close"] > 0
    )
    merged["vix3m_vix6m_ratio"] = merged["vix3m_close"] / merged["vix6m_close"].where(
        merged["vix6m_close"] > 0
    )
    merged["vix_vix3m_spread"] = merged["vix_close"] - merged["vix3m_close"]
    merged["vix_vix3m_ratio_change_1d"] = merged["vix_vix3m_ratio"] - merged["vix_vix3m_ratio"].shift(1)

    for column in [
        "vix_close",
        "vix_vix3m_ratio",
        "vix9d_vix_ratio",
        "vix3m_vix6m_ratio",
        "vix_vix3m_spread",
        "vix_vix3m_ratio_change_1d",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "vix_close",
        "vix9d_close",
        "vix3m_close",
        "vix6m_close",
        "vix_vix3m_ratio",
        "vix9d_vix_ratio",
        "vix3m_vix6m_ratio",
        "vix_vix3m_spread",
        "vix_vix3m_ratio_change_1d",
        "vix_close_rank_252",
        "vix_vix3m_ratio_rank_252",
        "vix9d_vix_ratio_rank_252",
        "vix3m_vix6m_ratio_rank_252",
        "vix_vix3m_spread_rank_252",
        "vix_vix3m_ratio_change_1d_rank_252",
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
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()
    features = build_features(args.bars_input, args.output, cache_dir=args.cache_dir)
    valid = features.dropna(
        subset=[
            "vix_vix3m_ratio_rank_252",
            "vix9d_vix_ratio_rank_252",
            "vix3m_vix6m_ratio_rank_252",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
