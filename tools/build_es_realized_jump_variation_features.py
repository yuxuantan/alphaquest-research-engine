from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_realized_jump_variation_features_20110103_20260609.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = timestamps.dt.date.astype(str)

    daily_rows: list[dict] = []
    for session_date, group in bars.groupby("session_date", sort=True):
        log_returns = _session_log_returns(group)
        rv = float((log_returns**2).sum()) if len(log_returns) else float("nan")
        bv = _bipower_variation(log_returns)
        jump_var = max(rv - bv, 0.0) if math.isfinite(rv) and math.isfinite(bv) else float("nan")
        jump_share = jump_var / rv if math.isfinite(jump_var) and rv > 0 else float("nan")
        pos_jump, neg_jump, signed_jump_share = _signed_large_return_variation(log_returns)
        daily_rows.append(
            {
                "session_date": session_date,
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
                "rows": int(len(group)),
                "rth_return": float(group["close"].iloc[-1] / group["open"].iloc[0] - 1.0),
                "realized_variance": rv,
                "bipower_variation": bv,
                "jump_variation": jump_var,
                "jump_share": jump_share,
                "positive_jump_variation": pos_jump,
                "negative_jump_variation": neg_jump,
                "signed_jump_share": signed_jump_share,
            }
        )

    daily = pd.DataFrame(daily_rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)

    # Every tradable feature is shifted one RTH session. A row for date D can only
    # contain state available after date D-1 has closed.
    daily["prior_close"] = daily["close"].shift(1)
    daily["prior_rth_return"] = daily["rth_return"].shift(1)
    daily["prior_realized_variance"] = daily["realized_variance"].shift(1)
    daily["prior_bipower_variation"] = daily["bipower_variation"].shift(1)
    daily["prior_jump_variation"] = daily["jump_variation"].shift(1)
    daily["prior_jump_share"] = daily["jump_share"].shift(1)
    daily["prior_positive_jump_variation"] = daily["positive_jump_variation"].shift(1)
    daily["prior_negative_jump_variation"] = daily["negative_jump_variation"].shift(1)
    daily["prior_signed_jump_share"] = daily["signed_jump_share"].shift(1)
    daily["jump_variation_3d_mean"] = daily["jump_variation"].rolling(3, min_periods=3).mean().shift(1)
    daily["jump_share_3d_mean"] = daily["jump_share"].rolling(3, min_periods=3).mean().shift(1)
    daily["jump_share_5d_mean"] = daily["jump_share"].rolling(5, min_periods=5).mean().shift(1)
    daily["jump_variation_change_5d"] = daily["jump_variation"].diff(5).shift(1)

    daily["jump_var_rank_252"] = _rolling_last_percentile(daily["prior_jump_variation"], 252, min_periods=60)
    daily["jump_share_rank_252"] = _rolling_last_percentile(daily["prior_jump_share"], 252, min_periods=60)
    daily["jump_var3_rank_252"] = _rolling_last_percentile(daily["jump_variation_3d_mean"], 252, min_periods=60)
    daily["jump_share3_rank_252"] = _rolling_last_percentile(daily["jump_share_3d_mean"], 252, min_periods=60)
    daily["negative_jump_rank_252"] = _rolling_last_percentile(
        daily["prior_negative_jump_variation"], 252, min_periods=60
    )
    daily["positive_jump_rank_252"] = _rolling_last_percentile(
        daily["prior_positive_jump_variation"], 252, min_periods=60
    )
    daily["signed_jump_rank_252"] = _rolling_last_percentile(daily["prior_signed_jump_share"], 252, min_periods=60)
    daily["jump_change_rank_252"] = _rolling_last_percentile(
        daily["jump_variation_change_5d"], 252, min_periods=60
    )

    columns = [
        "session_date",
        "prior_close",
        "prior_rth_return",
        "prior_realized_variance",
        "prior_bipower_variation",
        "prior_jump_variation",
        "prior_jump_share",
        "prior_positive_jump_variation",
        "prior_negative_jump_variation",
        "prior_signed_jump_share",
        "jump_variation_3d_mean",
        "jump_share_3d_mean",
        "jump_share_5d_mean",
        "jump_variation_change_5d",
        "jump_var_rank_252",
        "jump_share_rank_252",
        "jump_var3_rank_252",
        "jump_share3_rank_252",
        "negative_jump_rank_252",
        "positive_jump_rank_252",
        "signed_jump_rank_252",
        "jump_change_rank_252",
    ]
    out = daily.loc[daily["session_date"] >= "2011-01-03", columns].copy()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _session_log_returns(group: pd.DataFrame) -> pd.Series:
    closes = group["close"].astype(float)
    prior_prices = closes.shift(1)
    prior_prices.iloc[0] = float(group["open"].iloc[0])
    ratios = closes / prior_prices
    ratios = ratios.where(ratios > 0)
    return ratios.apply(lambda value: pd.NA if pd.isna(value) else math.log(value)).dropna().astype(float)


def _bipower_variation(log_returns: pd.Series) -> float:
    clean = log_returns.dropna().astype(float)
    if len(clean) < 2:
        return float("nan")
    adjacent_abs = clean.abs() * clean.abs().shift(1)
    return float((math.pi / 2.0) * adjacent_abs.dropna().sum())


def _signed_large_return_variation(log_returns: pd.Series) -> tuple[float, float, float]:
    clean = log_returns.dropna().astype(float)
    if clean.empty:
        return float("nan"), float("nan"), float("nan")
    median_abs = float(clean.abs().median())
    if median_abs <= 0 or not math.isfinite(median_abs):
        return float("nan"), float("nan"), float("nan")
    large = clean[clean.abs() >= 3.0 * median_abs]
    if large.empty:
        return 0.0, 0.0, 0.0
    positive = float((large[large > 0] ** 2).sum())
    negative = float((large[large < 0] ** 2).sum())
    total = positive + negative
    signed_share = (positive - negative) / total if total > 0 else 0.0
    return positive, negative, signed_share


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.input, args.output)
    valid = features.dropna(subset=["jump_var_rank_252", "jump_share_rank_252", "signed_jump_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
