from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_cboe_vix_level_features_20110103_20260609.csv"
DEFAULT_CACHE_PATH = "data/external/cboe_vix_history.csv"
VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    vix_input: str | Path | None = None,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
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

    vix = _load_vix_history(vix_input=vix_input, cache_path=cache_path)
    vix["vix_change_1d"] = vix["vix_close"] - vix["vix_close"].shift(1)
    vix["vix_change_5d"] = vix["vix_close"] - vix["vix_close"].shift(5)
    vix["vix_5d_mean"] = vix["vix_close"].rolling(5, min_periods=5).mean()
    for column in ["vix_close", "vix_change_1d", "vix_change_5d", "vix_5d_mean"]:
        vix[f"{column}_rank_252"] = _rolling_last_percentile(vix[column], 252, rank_min_periods)

    # VIX daily closes are published after the U.S. options close. Intraday ES
    # signals can only use the latest VIX observation strictly before session_date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        vix.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    columns = [
        "session_date",
        "observation_date",
        "vix_close",
        "vix_change_1d",
        "vix_change_5d",
        "vix_5d_mean",
        "vix_close_rank_252",
        "vix_change_1d_rank_252",
        "vix_change_5d_rank_252",
        "vix_5d_mean_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_vix_history(
    *,
    vix_input: str | Path | None,
    cache_path: str | Path,
) -> pd.DataFrame:
    if vix_input is not None:
        raw = pd.read_csv(vix_input)
    else:
        cache = Path(cache_path)
        if cache.exists():
            raw = pd.read_csv(cache)
        else:
            raw = pd.read_csv(VIX_URL)
            cache.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache, index=False)
    date_col = "DATE" if "DATE" in raw.columns else "observation_date"
    close_col = "CLOSE" if "CLOSE" in raw.columns else "vix_close"
    if close_col not in raw.columns:
        raise ValueError(f"VIX input is missing required close column: {close_col}")
    out = raw[[date_col, close_col]].copy()
    out.columns = ["observation_date", "vix_close"]
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out["vix_close"] = pd.to_numeric(out["vix_close"], errors="coerce")
    return (
        out.dropna(subset=["vix_close"])
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
    parser.add_argument("--cache-path", default=DEFAULT_CACHE_PATH)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        vix_input=args.vix_input,
        cache_path=args.cache_path,
    )
    valid = features.dropna(subset=["vix_close_rank_252", "vix_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
