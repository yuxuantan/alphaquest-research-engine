from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_MONTHLY_FEATURE_INPUT = "data/external/chicagofed_cfnai_monthly_features_196703_202604.csv"
DEFAULT_OUTPUT = "data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv"


def build_features(
    bars_input: str | Path,
    monthly_feature_input: str | Path,
    output_path: str | Path,
    *,
    monthly_feature_cache: str | Path | None = None,
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

    monthly = pd.read_csv(monthly_feature_input)
    monthly = monthly.copy()
    monthly["eligible_date"] = pd.to_datetime(monthly["eligible_date"])
    monthly["obs_date"] = pd.to_datetime(monthly["obs_date"])
    monthly = monthly.sort_values("eligible_date", kind="mergesort").drop_duplicates(
        "eligible_date", keep="last"
    )

    if monthly_feature_cache is not None:
        cache_path = Path(monthly_feature_cache)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        monthly.to_csv(cache_path, index=False)

    # Each ES session receives the latest CFNAI observation whose conservative
    # eligible date is on or before the session. No same-month unreleased data is
    # assigned to earlier sessions.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        monthly,
        left_on="session_date_ts",
        right_on="eligible_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged = merged.drop(columns=["session_date_ts"])
    merged["obs_date"] = pd.to_datetime(merged["obs_date"]).dt.date.astype(str)
    merged["eligible_date"] = pd.to_datetime(merged["eligible_date"]).dt.date.astype(str)

    out = merged.loc[merged["session_date"] >= "2011-01-03"].copy()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--monthly-feature-input", default=DEFAULT_MONTHLY_FEATURE_INPUT)
    parser.add_argument("--monthly-feature-cache", default=None)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.monthly_feature_input,
        args.output,
        monthly_feature_cache=args.monthly_feature_cache,
    )
    valid = features.dropna(subset=["P_I", "EU_H", "CFNAI", "CFNAI_MA3", "DIFFUSION"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_activity_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
