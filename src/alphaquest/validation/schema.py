"""Explicit schema for visual strategy-validation artifacts.

The validation artifacts are intentionally independent of the backtest engine.
They capture enough trade, signal, window, and exit-path data for a dashboard to
inspect a completed run without replaying strategy mechanics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

import pandas as pd

VALIDATION_SCHEMA_VERSION = "1.4"

METADATA_FILENAME = "metadata.json"
TRADES_FILENAME = "trades.parquet"
CONDITION_SNAPSHOTS_FILENAME = "condition_snapshots.parquet"
BAR_WINDOWS_FILENAME = "bar_windows.parquet"
TICK_WINDOWS_FILENAME = "tick_windows.parquet"
EVENT_TRANSITIONS_FILENAME = "event_transitions.parquet"
EXIT_AUDITS_FILENAME = "exit_audits.parquet"
MANUAL_REVIEW_FILENAME = "manual_review.parquet"
VALIDATION_CHECKS_FILENAME = "validation_checks.parquet"


@dataclass(frozen=True)
class ValidationMetadata:
    run_id: str
    campaign_id: str | None = None
    strategy_id: str | None = None
    variant_id: str | None = None
    symbol: str | None = None
    stage: str | None = None
    timezone: str | None = "America/New_York"
    tick_size: float | None = None
    tick_value: float | None = None
    timeframe: str | None = None
    timeframe_minutes: float | None = None
    source_run_dir: str | None = None
    source_trade_log: str | None = None
    config_hash: str | None = None
    input_data_hash: str | None = None
    strategy_implementation_version: int | None = None
    strategy_implementation_sha256: str | None = None
    strategy_certification_manifest_sha256: str | None = None
    validation_lane: str | None = None
    source_data_type: str | None = None
    source_data_path: str | None = None
    source_trade_count: int | None = None
    commission_per_contract: float | None = None
    slippage_ticks: float | None = None
    point_value: float | None = None
    forced_flatten_time: str | None = None
    notes: str | None = None
    schema_version: str = VALIDATION_SCHEMA_VERSION
    created_at_utc: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradeSummary:
    run_id: str
    trade_id: str | int
    symbol: str
    campaign_id: str | None = None
    strategy_id: str | None = None
    variant_id: str | None = None
    contract: str | None = None
    session_date: str | None = None
    direction: str | None = None
    entry_time: Any = None
    entry_price: float | None = None
    entry_order_type: str | None = None
    stop_price: float | None = None
    target_price: float | None = None
    exit_time: Any = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl_ticks: float | None = None
    pnl_usd: float | None = None
    r_multiple: float | None = None
    bars_held: float | None = None
    contracts: int | None = None
    fees: float | None = None
    slippage: float | None = None
    was_forced_flatten: bool | None = None
    notes: str | None = None
    debug_flags: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConditionSnapshot:
    trade_id: str | int
    signal_time: Any = None
    decision_bar_time: Any = None
    entry_execution_time: Any = None
    entry_mode: str | None = None
    swept_level_name: str | None = None
    swept_level_price: float | None = None
    sweep_time: Any = None
    reclaim_time: Any = None
    reclaim_window_bars: int | None = None
    sweep_bar_open: float | None = None
    sweep_bar_high: float | None = None
    sweep_bar_low: float | None = None
    sweep_bar_close: float | None = None
    sweep_bar_volume: float | None = None
    avg_volume_reference: float | None = None
    volume_filter_pass: bool | None = None
    delta_value: float | None = None
    delta_pct: float | None = None
    delta_filter_pass: bool | None = None
    bid_volume: float | None = None
    ask_volume: float | None = None
    total_volume: float | None = None
    cumulative_delta: float | None = None
    imbalance_count: float | None = None
    stacked_imbalance_pass: bool | None = None
    close_location_metric: float | None = None
    rth_filter_pass: bool | None = None
    no_trade_window_filter_pass: bool | None = None
    max_trades_filter_pass: bool | None = None
    final_entry_pass: bool | None = None
    reason_if_rejected: str | None = None
    entry_trigger_values: str | None = None
    filter_pass_values: str | None = None
    raw_orderflow_values: str | None = None
    signal_metadata: str | None = None
    signal_report_fields: str | None = None
    decision_context: str | None = None
    stop_anchor_calculation: str | None = None
    target_calculation: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BarWindowRow:
    trade_id: str | int
    timestamp: Any
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    bid_volume: float | None = None
    ask_volume: float | None = None
    delta: float | None = None
    cumulative_delta: float | None = None
    is_rth: bool | None = None
    session_date: str | None = None
    prev_rth_high: float | None = None
    prev_rth_low: float | None = None
    overnight_high: float | None = None
    overnight_low: float | None = None
    vwap: float | None = None
    profile_poc: float | None = None
    profile_vah: float | None = None
    profile_val: float | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TickWindowRow:
    trade_id: str | int
    timestamp: Any
    source_ordinal: int | None = None
    price: float | None = None
    volume: float | None = None
    bid_volume: float | None = None
    ask_volume: float | None = None
    aggressor_side: str | None = None
    delta: float | None = None
    price_level: float | None = None
    price_level_bid_volume: float | None = None
    price_level_ask_volume: float | None = None
    price_level_delta: float | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventTransition:
    """One causally ordered state transition from an event-replay run.

    ``state_json`` captures the resulting state while ``evidence_json`` records
    the event-local facts used to make the transition.  Both fields are JSON
    strings so the parquet contract remains stable across strategies.
    """

    trade_id: str | int | None = None
    session_date: str | None = None
    contract: str | None = None
    order_id: str | int | None = None
    timestamp: Any = None
    source_ordinal: int | None = None
    event_index: int | None = None
    transition: str | None = None
    direction: str | None = None
    price: float | None = None
    active_from_event_index: int | None = None
    stop_price: float | None = None
    target_price: float | None = None
    reason: str | None = None
    state_json: str | None = None
    evidence_json: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExitAudit:
    trade_id: str | int
    entry_time: Any = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    exit_time: Any = None
    exit_price: float | None = None
    exit_reason: str | None = None
    first_touch_tp_time: Any = None
    first_touch_sl_time: Any = None
    first_touch_tp_price: float | None = None
    first_touch_sl_price: float | None = None
    first_touch_decision: str | None = None
    first_touch_exit_decision: str | None = None
    same_bar_ambiguous: bool | None = None
    ambiguity_resolution: str | None = None
    forced_flatten_reason: str | None = None
    exit_bar_timestamp: Any = None
    exit_bar_open: float | None = None
    exit_bar_high: float | None = None
    exit_bar_low: float | None = None
    exit_bar_close: float | None = None
    raw_exit_price: float | None = None
    tp_hit_on_exit_bar: bool | None = None
    sl_hit_on_exit_bar: bool | None = None
    max_favorable_excursion_ticks: float | None = None
    max_adverse_excursion_ticks: float | None = None
    mfe_ticks: float | None = None
    mae_ticks: float | None = None
    highest_price_before_exit: float | None = None
    lowest_price_before_exit: float | None = None
    max_price_before_exit: float | None = None
    min_price_before_exit: float | None = None
    tick_count_checked: int | None = None
    path_source: str | None = None
    engine_exit_decision: str | None = None
    engine_exit_matches_path: bool | None = None
    warning_flags: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManualReviewAnnotation:
    trade_id: str | int
    reviewer_status: str | None = None
    reviewer_notes: str | None = None
    reviewed_at: Any = None
    dashboard_version: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    check_name: str
    category: str
    status: str
    severity: str
    description: str
    trade_id: str | int | None = None
    expected: str | None = None
    actual: str | None = None
    details: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


TRADE_SUMMARY_COLUMNS = [field.name for field in TradeSummary.__dataclass_fields__.values()]
CONDITION_SNAPSHOT_COLUMNS = [field.name for field in ConditionSnapshot.__dataclass_fields__.values()]
BAR_WINDOW_COLUMNS = [field.name for field in BarWindowRow.__dataclass_fields__.values()]
TICK_WINDOW_COLUMNS = [field.name for field in TickWindowRow.__dataclass_fields__.values()]
EVENT_TRANSITION_COLUMNS = [field.name for field in EventTransition.__dataclass_fields__.values()]
EXIT_AUDIT_COLUMNS = [field.name for field in ExitAudit.__dataclass_fields__.values()]
MANUAL_REVIEW_COLUMNS = [field.name for field in ManualReviewAnnotation.__dataclass_fields__.values()]
VALIDATION_CHECK_COLUMNS = [field.name for field in ValidationCheck.__dataclass_fields__.values()]


def record_to_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "to_record"):
        return record.to_record()
    if is_dataclass(record):
        return asdict(record)
    if isinstance(record, dict):
        return dict(record)
    raise TypeError(f"Unsupported validation record type: {type(record)!r}")


def records_to_frame(records: Any, columns: list[str]) -> pd.DataFrame:
    if records is None:
        return empty_frame(columns)
    if isinstance(records, pd.DataFrame):
        frame = records.copy()
    else:
        frame = pd.DataFrame([record_to_dict(record) for record in records])
    return normalize_columns(frame, columns)


def normalize_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    normalized = frame.copy()
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    return normalized[columns]


def empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)
