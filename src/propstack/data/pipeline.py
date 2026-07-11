from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.data.quality import save_pipeline_outputs
from propstack.data.scid_execution import load_scid_record_execution_data
from propstack.data.subset import apply_data_subset, load_bounds_with_warmup, subset_from_data_config
from propstack.data.timeframe import aggregate_timeframe, canonical_timeframe, parse_timeframe_minutes
from propstack.utils.reports import market_timezone


def prepare_data(
    data_config: dict,
    output_dir=None,
    subset_config: dict | None = None,
    timeframe=None,
    include_execution_data: bool = False,
    status_callback: Callable[[str], None] | None = None,
    show_progress: bool = False,
):
    timeframe = canonical_timeframe(timeframe or data_config.get("timeframe", "1m"))
    timeframe_minutes = parse_timeframe_minutes(timeframe)
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
    source_cleaned = cleaned
    _emit(status_callback, f"Aggregating strategy bars to timeframe: {timeframe}")
    strategy_bars = aggregate_timeframe(source_cleaned, data_config, timeframe)
    _emit(status_callback, f"Strategy timeframe contains {len(strategy_bars):,} bars.")
    _emit(status_callback, "Building feature columns...")
    features = build_features(strategy_bars, data_config, status_callback=status_callback)
    _emit(status_callback, f"Built feature columns for {len(features):,} bars.")
    execution_data = source_cleaned
    custom_execution_config = data_config.get("execution_data")
    if subset_config:
        _emit(status_callback, "Applying final data subset after warmup feature build...")
        cleaned = apply_data_subset(source_cleaned, subset_config)
        features = apply_data_subset(features, subset_config)
        execution_data = cleaned
        missing = _filter_missing_bars(missing, subset_config)
        quality_report = {
            **quality_report,
            "loaded_rows": quality_report["rows"],
            "rows": int(len(cleaned)),
            "strategy_rows": int(len(features)),
            "first_timestamp": str(cleaned["timestamp"].min()) if len(cleaned) else None,
            "last_timestamp": str(cleaned["timestamp"].max()) if len(cleaned) else None,
        }
        _emit(status_callback, f"Final subset contains {len(features):,} bars.")
    else:
        cleaned = source_cleaned
        quality_report = {
            **quality_report,
            "strategy_rows": int(len(features)),
        }
    if custom_execution_config and include_execution_data:
        execution_data = _load_custom_execution_data(custom_execution_config, subset_config or load_bounds)
    quality_report = {
        **quality_report,
        "timeframe": timeframe,
        "timeframe_minutes": timeframe_minutes,
        "source_timeframe": data_config.get("source_timeframe", "1m"),
    }
    if output_dir:
        _emit(status_callback, f"Writing validation CSVs to {output_dir}...")
        retention = data_config.get("artifact_retention") or {}
        save_pipeline_outputs(
            cleaned,
            features,
            quality_report,
            missing,
            output_dir,
            market_timezone(data_config),
            retain_full_frames=bool(retention.get("full_validation_frames", False)),
        )
        _emit(status_callback, "Validation CSVs written.")
    if include_execution_data:
        return features, quality_report, execution_data
    return features, quality_report


def _load_custom_execution_data(execution_config: dict, bounds: dict | None) -> pd.DataFrame:
    source = str(execution_config.get("source", "")).lower()
    if source in {"sierra_scid_records", "scid_records", "sierra_scid"}:
        return load_scid_record_execution_data(execution_config, date_bounds=bounds)
    raise ValueError(f"Unsupported data.execution_data.source: {execution_config.get('source')!r}")


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
