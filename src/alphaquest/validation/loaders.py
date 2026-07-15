"""Read validation-dashboard artifacts from disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from alphaquest.validation.schema import (
    BAR_WINDOWS_FILENAME,
    CONDITION_SNAPSHOTS_FILENAME,
    EVENT_TRANSITIONS_FILENAME,
    EXIT_AUDITS_FILENAME,
    METADATA_FILENAME,
    TICK_WINDOWS_FILENAME,
    TRADES_FILENAME,
    VALIDATION_CHECKS_FILENAME,
    BAR_WINDOW_COLUMNS,
    CONDITION_SNAPSHOT_COLUMNS,
    EVENT_TRANSITION_COLUMNS,
    EXIT_AUDIT_COLUMNS,
    TICK_WINDOW_COLUMNS,
    TRADE_SUMMARY_COLUMNS,
    VALIDATION_CHECK_COLUMNS,
    empty_frame,
    normalize_columns,
)


@dataclass(frozen=True)
class ValidationRun:
    metadata: dict[str, Any]
    trades: pd.DataFrame
    condition_snapshots: pd.DataFrame
    bar_windows: pd.DataFrame
    tick_windows: pd.DataFrame
    event_transitions: pd.DataFrame
    exit_audits: pd.DataFrame
    validation_checks: pd.DataFrame


def read_metadata(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)
    if metadata_path.is_dir():
        metadata_path = metadata_path / METADATA_FILENAME
    with metadata_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_parquet_artifact(path: str | Path, columns: list[str] | None = None) -> pd.DataFrame:
    frame = pd.read_parquet(Path(path))
    if columns is not None:
        return normalize_columns(frame, columns)
    return frame


def _read_optional_artifact(run_dir: Path, filename: str, columns: list[str]) -> pd.DataFrame:
    artifact_path = run_dir / filename
    if not artifact_path.exists():
        return empty_frame(columns)
    return read_parquet_artifact(artifact_path, columns)


def load_validation_run(path: str | Path, *, include_tick_windows: bool = True) -> ValidationRun:
    run_dir = Path(path)
    metadata = read_metadata(run_dir)
    return ValidationRun(
        metadata=metadata,
        trades=_read_optional_artifact(run_dir, TRADES_FILENAME, TRADE_SUMMARY_COLUMNS),
        condition_snapshots=_read_optional_artifact(
            run_dir,
            CONDITION_SNAPSHOTS_FILENAME,
            CONDITION_SNAPSHOT_COLUMNS,
        ),
        bar_windows=_read_optional_artifact(run_dir, BAR_WINDOWS_FILENAME, BAR_WINDOW_COLUMNS),
        tick_windows=_read_optional_artifact(run_dir, TICK_WINDOWS_FILENAME, TICK_WINDOW_COLUMNS)
        if include_tick_windows
        else empty_frame(TICK_WINDOW_COLUMNS),
        event_transitions=_read_optional_artifact(
            run_dir,
            EVENT_TRANSITIONS_FILENAME,
            EVENT_TRANSITION_COLUMNS,
        ),
        exit_audits=_read_optional_artifact(run_dir, EXIT_AUDITS_FILENAME, EXIT_AUDIT_COLUMNS),
        validation_checks=_read_optional_artifact(run_dir, VALIDATION_CHECKS_FILENAME, VALIDATION_CHECK_COLUMNS),
    )


def load_tick_window_for_trade(path: str | Path, trade_id: str | int) -> pd.DataFrame:
    run_dir = Path(path)
    artifact_path = run_dir / TICK_WINDOWS_FILENAME
    if not artifact_path.exists():
        return empty_frame(TICK_WINDOW_COLUMNS)
    try:
        frame = pd.read_parquet(artifact_path, filters=[("trade_id", "=", trade_id)])
    except (TypeError, ValueError, OSError, ImportError):
        frame = pd.read_parquet(artifact_path)
        if "trade_id" in frame.columns:
            frame = frame[frame["trade_id"] == trade_id]
    return normalize_columns(frame, TICK_WINDOW_COLUMNS)
