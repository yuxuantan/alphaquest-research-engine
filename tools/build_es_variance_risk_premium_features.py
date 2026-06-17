from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_VIX_CACHE = "data/external/cboe_vix_history.csv"
DEFAULT_OUTPUT = "data/external/es_variance_risk_premium_features_20110103_20260609.csv"
DEFAULT_VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    vix_input: str | Path | None = None,
    vix_cache: str | Path = DEFAULT_VIX_CACHE,
    rank_min_periods: int = 60,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp", "open", "close"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = timestamps.dt.date.astype(str)

    daily_rows: list[dict] = []
    for session_date, group in bars.groupby("session_date", sort=True):
        closes = group["close"].astype(float)
        first_open = float(group["open"].iloc[0])
        prior_prices = closes.shift(1)
        prior_prices.iloc[0] = first_open
        returns = (closes / prior_prices).where(lambda values: values > 0).astype("float64")
        log_returns = returns.apply(lambda value: pd.NA if pd.isna(value) else math.log(value)).dropna()
        realized_var = float((log_returns**2).sum()) if len(log_returns) else float("nan")
        daily_rows.append(
            {
                "session_date": session_date,
                "open": first_open,
                "close": float(group["close"].iloc[-1]),
                "rth_return": float(group["close"].iloc[-1] / first_open - 1.0),
                "realized_variance": realized_var,
            }
        )

    daily = pd.DataFrame(daily_rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)
    vix = _load_vix(vix_input=vix_input, vix_cache=vix_cache)
    daily = daily.merge(vix, on="session_date", how="left")

    # VIX close and ES realized variance are only tradable from the next RTH session.
    daily["prior_close"] = daily["close"].shift(1)
    daily["prior_rth_return"] = daily["rth_return"].shift(1)
    daily["prior_vix_close"] = daily["vix_close"].shift(1)
    daily["prior_vix_variance_ann"] = (daily["prior_vix_close"] / 100.0) ** 2
    daily["realized_var_5_ann"] = daily["realized_variance"].rolling(5, min_periods=5).mean().shift(1) * 252.0
    daily["realized_var_20_ann"] = daily["realized_variance"].rolling(20, min_periods=20).mean().shift(1) * 252.0
    daily["vrp_20"] = daily["prior_vix_variance_ann"] - daily["realized_var_20_ann"]
    daily["vrp_ratio_20"] = daily["prior_vix_variance_ann"] / daily["realized_var_20_ann"].where(
        daily["realized_var_20_ann"] > 0
    )
    daily["vrp_change_5"] = daily["vrp_20"] - daily["vrp_20"].shift(5)
    daily["vix_change_5"] = daily["prior_vix_close"] - daily["prior_vix_close"].shift(5)

    daily["vrp_rank_252"] = _rolling_last_percentile(daily["vrp_20"], 252, rank_min_periods)
    daily["vrp_ratio_rank_252"] = _rolling_last_percentile(daily["vrp_ratio_20"], 252, rank_min_periods)
    daily["vix_rank_252"] = _rolling_last_percentile(daily["prior_vix_close"], 252, rank_min_periods)
    daily["realized_var20_rank_252"] = _rolling_last_percentile(
        daily["realized_var_20_ann"], 252, rank_min_periods
    )
    daily["vrp_change_rank_252"] = _rolling_last_percentile(daily["vrp_change_5"], 252, rank_min_periods)

    columns = [
        "session_date",
        "prior_close",
        "prior_rth_return",
        "prior_vix_close",
        "prior_vix_variance_ann",
        "realized_var_5_ann",
        "realized_var_20_ann",
        "vrp_20",
        "vrp_ratio_20",
        "vrp_change_5",
        "vix_change_5",
        "vrp_rank_252",
        "vrp_ratio_rank_252",
        "vix_rank_252",
        "realized_var20_rank_252",
        "vrp_change_rank_252",
    ]
    out = daily.loc[daily["session_date"] >= "2011-01-03", columns].copy()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_vix(*, vix_input: str | Path | None, vix_cache: str | Path) -> pd.DataFrame:
    if vix_input is not None:
        raw = pd.read_csv(vix_input)
    else:
        cache_path = Path(vix_cache)
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            raw = pd.read_csv(DEFAULT_VIX_URL)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)

    date_col = "DATE" if "DATE" in raw.columns else "observation_date"
    close_col = "CLOSE" if "CLOSE" in raw.columns else "VIXCLS"
    vix = raw[[date_col, close_col]].copy()
    vix.columns = ["session_date", "vix_close"]
    vix["session_date"] = pd.to_datetime(vix["session_date"]).dt.date.astype(str)
    vix["vix_close"] = pd.to_numeric(vix["vix_close"], errors="coerce")
    return vix.dropna(subset=["vix_close"]).sort_values("session_date", kind="mergesort")


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
    parser.add_argument("--vix-input", default=None)
    parser.add_argument("--vix-cache", default=DEFAULT_VIX_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        vix_input=args.vix_input,
        vix_cache=args.vix_cache,
    )
    valid = features.dropna(subset=["vrp_rank_252", "vrp_ratio_rank_252", "vrp_change_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
