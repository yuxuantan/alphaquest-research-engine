from __future__ import annotations

from pathlib import Path
import pandas as pd

from propstack.utils.reports import write_report_csv


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
    levels = _available_level_report(df)
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


def _available_level_report(df: pd.DataFrame) -> pd.DataFrame:
    aggregations = {}
    optional_columns = {
        "overnight_high": "overnight_high",
        "overnight_low": "overnight_low",
        "prev_rth_high": "previous_rth_high",
        "prev_rth_low": "previous_rth_low",
    }
    for source, output in optional_columns.items():
        if source in df.columns:
            aggregations[output] = (source, "first")

    sessions = pd.DataFrame(index=df["session_date"].drop_duplicates().sort_values())
    if not aggregations:
        for output in optional_columns.values():
            sessions[output] = pd.NA
        return sessions

    levels = df.groupby("session_date").agg(**aggregations)
    for output in optional_columns.values():
        if output not in levels.columns:
            levels[output] = pd.NA
    return levels


def save_pipeline_outputs(
    cleaned: pd.DataFrame,
    features: pd.DataFrame,
    quality_report: dict,
    missing_bars: pd.DataFrame,
    output_dir: str | Path,
    timezone: str | None = None,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_report_csv(cleaned, out / "cleaned_data.csv", timezone, index=False)
    write_report_csv(features, out / "features_data.csv", timezone, index=False)
    write_report_csv(pd.DataFrame([quality_report]), out / "data_quality_report.csv", timezone, index=False)
    write_report_csv(missing_bars, out / "missing_bars.csv", timezone, index=False)
    write_report_csv(tradingview_comparison_report(features), out / "tradingview_comparison.csv", timezone, index=False)
