from __future__ import annotations

from pathlib import Path
import pandas as pd


def tradingview_comparison_report(df: pd.DataFrame) -> pd.DataFrame:
    rth = df[df["is_rth"]].copy()
    if rth.empty:
        return pd.DataFrame()
    daily = rth.groupby("session_date").agg(
        rth_open=("open", "first"),
        rth_high=("high", "max"),
        rth_low=("low", "min"),
        rth_close=("close", "last"),
        total_rth_volume=("volume", "sum"),
        first_rth_timestamp=("timestamp", "first"),
        last_rth_timestamp=("timestamp", "last"),
    )
    levels = df.groupby("session_date").agg(
        overnight_high=("overnight_high", "first"),
        overnight_low=("overnight_low", "first"),
        previous_rth_high=("prev_rth_high", "first"),
        previous_rth_low=("prev_rth_low", "first"),
    )
    report = daily.join(levels, how="left").reset_index()
    ordered = [
        "session_date",
        "rth_open",
        "rth_high",
        "rth_low",
        "rth_close",
        "overnight_high",
        "overnight_low",
        "previous_rth_high",
        "previous_rth_low",
        "total_rth_volume",
        "first_rth_timestamp",
        "last_rth_timestamp",
    ]
    return report[ordered]


def save_pipeline_outputs(
    cleaned: pd.DataFrame,
    features: pd.DataFrame,
    quality_report: dict,
    missing_bars: pd.DataFrame,
    output_dir: str | Path,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(out / "cleaned_data.csv", index=False)
    features.to_csv(out / "features_data.csv", index=False)
    pd.DataFrame([quality_report]).to_csv(out / "data_quality_report.csv", index=False)
    missing_bars.to_csv(out / "missing_bars.csv", index=False)
    tradingview_comparison_report(features).to_csv(out / "tradingview_comparison.csv", index=False)
