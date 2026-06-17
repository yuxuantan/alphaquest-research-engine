from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_cboe_vxn_vix_dispersion_features_20110103_20260609.csv"
DEFAULT_VIX_CACHE_PATH = "data/external/cboe_vix_history.csv"
DEFAULT_VXN_CACHE_PATH = "data/external/cboe_vxn_history.csv"
VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
VXN_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    vix_input: str | Path | None = None,
    vxn_input: str | Path | None = None,
    vix_cache_path: str | Path = DEFAULT_VIX_CACHE_PATH,
    vxn_cache_path: str | Path = DEFAULT_VXN_CACHE_PATH,
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

    vix = _load_cboe_history(
        input_path=vix_input,
        cache_path=vix_cache_path,
        url=VIX_URL,
        value_name="vix_close",
    )
    vxn = _load_cboe_history(
        input_path=vxn_input,
        cache_path=vxn_cache_path,
        url=VXN_URL,
        value_name="vxn_close",
    )
    cboe = (
        pd.merge(vix, vxn, on="observation_date", how="inner")
        .sort_values("observation_date", kind="mergesort")
        .reset_index(drop=True)
    )
    cboe["vxn_minus_vix"] = cboe["vxn_close"] - cboe["vix_close"]
    cboe["vxn_vix_ratio"] = cboe["vxn_close"] / cboe["vix_close"]
    cboe["vxn_minus_vix_change_1d"] = cboe["vxn_minus_vix"] - cboe["vxn_minus_vix"].shift(1)
    cboe["vxn_vix_ratio_change_1d"] = cboe["vxn_vix_ratio"] - cboe["vxn_vix_ratio"].shift(1)
    cboe["vxn_minus_vix_5d_mean"] = cboe["vxn_minus_vix"].rolling(5, min_periods=5).mean()
    cboe["vxn_vix_ratio_5d_mean"] = cboe["vxn_vix_ratio"].rolling(5, min_periods=5).mean()

    rank_columns = [
        "vxn_minus_vix",
        "vxn_vix_ratio",
        "vxn_minus_vix_change_1d",
        "vxn_vix_ratio_change_1d",
        "vxn_minus_vix_5d_mean",
        "vxn_vix_ratio_5d_mean",
    ]
    for column in rank_columns:
        cboe[f"{column}_rank_252"] = _rolling_last_percentile(cboe[column], 252, rank_min_periods)

    # VIX and VXN are daily closing indexes. Intraday ES signals can only use
    # the latest completed Cboe observation strictly before the ES session date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        cboe.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    columns = [
        "session_date",
        "observation_date",
        "vix_close",
        "vxn_close",
        "vxn_minus_vix",
        "vxn_vix_ratio",
        "vxn_minus_vix_change_1d",
        "vxn_vix_ratio_change_1d",
        "vxn_minus_vix_5d_mean",
        "vxn_vix_ratio_5d_mean",
        "vxn_minus_vix_rank_252",
        "vxn_vix_ratio_rank_252",
        "vxn_minus_vix_change_1d_rank_252",
        "vxn_vix_ratio_change_1d_rank_252",
        "vxn_minus_vix_5d_mean_rank_252",
        "vxn_vix_ratio_5d_mean_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_cboe_history(
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
        raise ValueError(f"Cboe input is missing required close column: {close_col}")
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
    parser.add_argument("--vix-input")
    parser.add_argument("--vxn-input")
    parser.add_argument("--vix-cache-path", default=DEFAULT_VIX_CACHE_PATH)
    parser.add_argument("--vxn-cache-path", default=DEFAULT_VXN_CACHE_PATH)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        vix_input=args.vix_input,
        vxn_input=args.vxn_input,
        vix_cache_path=args.vix_cache_path,
        vxn_cache_path=args.vxn_cache_path,
    )
    valid = features.dropna(subset=["vxn_vix_ratio_rank_252", "vxn_vix_ratio_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
