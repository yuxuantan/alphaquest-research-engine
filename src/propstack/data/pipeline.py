from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.data.quality import save_pipeline_outputs
from propstack.data.subset import apply_data_subset, load_bounds_with_warmup, subset_from_data_config
from propstack.utils.reports import market_timezone


def prepare_data(
    data_config: dict,
    output_dir=None,
    subset_config: dict | None = None,
    status_callback: Callable[[str], None] | None = None,
    show_progress: bool = False,
):
    subset_config = subset_config or subset_from_data_config(data_config)
    load_bounds = load_bounds_with_warmup(subset_config, data_config)
    _emit(status_callback, f"Using data subset: {subset_config or 'full source range'}")
    _emit(status_callback, f"Loading bounds with warmup: {load_bounds or 'full source range'}")
    cleaned, quality_report, missing = clean_data(
        data_config,
        date_bounds=load_bounds,
        status_callback=status_callback,
        show_progress=show_progress,
    )
    _emit(status_callback, "Building feature columns...")
    features = build_features(cleaned, data_config, status_callback=status_callback)
    _emit(status_callback, f"Built feature columns for {len(features):,} bars.")
    if subset_config:
        _emit(status_callback, "Applying final data subset after warmup feature build...")
        cleaned = apply_data_subset(cleaned, subset_config)
        features = apply_data_subset(features, subset_config)
        missing = _filter_missing_bars(missing, subset_config)
        quality_report = {
            **quality_report,
            "loaded_rows": quality_report["rows"],
            "rows": int(len(cleaned)),
            "first_timestamp": str(cleaned["timestamp"].min()) if len(cleaned) else None,
            "last_timestamp": str(cleaned["timestamp"].max()) if len(cleaned) else None,
        }
        _emit(status_callback, f"Final subset contains {len(features):,} bars.")
    if output_dir:
        _emit(status_callback, f"Writing validation CSVs to {output_dir}...")
        save_pipeline_outputs(cleaned, features, quality_report, missing, output_dir, market_timezone(data_config))
        _emit(status_callback, "Validation CSVs written.")
    return features, quality_report


def _filter_missing_bars(missing, subset_config: dict | None):
    if missing.empty or not subset_config:
        return missing
    filtered = missing
    if subset_config.get("start_date"):
        start_date = pd.Timestamp(subset_config["start_date"]).date()
        filtered = filtered[pd.to_datetime(filtered["session_date"]).dt.date >= start_date]
    if subset_config.get("end_date"):
        end_date = pd.Timestamp(subset_config["end_date"]).date()
        filtered = filtered[pd.to_datetime(filtered["session_date"]).dt.date <= end_date]
    return filtered.reset_index(drop=True)


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
