"""Build and write validation-dashboard artifacts.

These helpers operate on completed backtest outputs. They do not call strategy
modules or alter fill logic, so exported validation runs cannot change results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from propstack.utils.config import write_json
from propstack.validation.checks import run_validation_checks
from propstack.validation.exit_path import enrich_exit_audits
from propstack.validation.schema import (
    BAR_WINDOWS_FILENAME,
    CONDITION_SNAPSHOTS_FILENAME,
    EVENT_TRANSITIONS_FILENAME,
    EXIT_AUDITS_FILENAME,
    METADATA_FILENAME,
    TICK_WINDOWS_FILENAME,
    TRADES_FILENAME,
    VALIDATION_CHECKS_FILENAME,
    VALIDATION_SCHEMA_VERSION,
    BAR_WINDOW_COLUMNS,
    CONDITION_SNAPSHOT_COLUMNS,
    EVENT_TRANSITION_COLUMNS,
    EXIT_AUDIT_COLUMNS,
    TICK_WINDOW_COLUMNS,
    TRADE_SUMMARY_COLUMNS,
    ValidationMetadata,
    normalize_columns,
    records_to_frame,
)


def write_parquet_artifact(frame: pd.DataFrame, path: str | Path) -> None:
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(artifact_path, index=False)


def write_validation_run(
    output_dir: str | Path,
    metadata: ValidationMetadata | dict[str, Any],
    *,
    trades: Any = None,
    condition_snapshots: Any = None,
    bar_windows: Any = None,
    tick_windows: Any = None,
    event_transitions: Any = None,
    exit_audits: Any = None,
) -> dict[str, Any]:
    run_dir = Path(output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_record = _metadata_record(metadata)

    frames = {
        TRADES_FILENAME: records_to_frame(trades, TRADE_SUMMARY_COLUMNS),
        CONDITION_SNAPSHOTS_FILENAME: records_to_frame(
            condition_snapshots,
            CONDITION_SNAPSHOT_COLUMNS,
        ),
        BAR_WINDOWS_FILENAME: records_to_frame(bar_windows, BAR_WINDOW_COLUMNS),
        TICK_WINDOWS_FILENAME: records_to_frame(tick_windows, TICK_WINDOW_COLUMNS),
        EVENT_TRANSITIONS_FILENAME: records_to_frame(
            event_transitions,
            EVENT_TRANSITION_COLUMNS,
        ),
        EXIT_AUDITS_FILENAME: records_to_frame(exit_audits, EXIT_AUDIT_COLUMNS),
    }
    frames[EXIT_AUDITS_FILENAME] = enrich_exit_audits(
        frames[TRADES_FILENAME],
        frames[EXIT_AUDITS_FILENAME],
        frames[TICK_WINDOWS_FILENAME],
        tick_size=_float_or_none(metadata_record.get("tick_size")),
    )
    frames[VALIDATION_CHECKS_FILENAME] = run_validation_checks(
        frames[TRADES_FILENAME],
        frames[CONDITION_SNAPSHOTS_FILENAME],
        frames[BAR_WINDOWS_FILENAME],
        frames[TICK_WINDOWS_FILENAME],
        frames[EXIT_AUDITS_FILENAME],
        metadata_record,
    )

    for filename, frame in frames.items():
        write_parquet_artifact(frame, run_dir / filename)

    metadata_record["schema_version"] = VALIDATION_SCHEMA_VERSION
    metadata_record["created_at_utc"] = metadata_record.get("created_at_utc") or datetime.now(UTC).isoformat()
    metadata_record["artifact_files"] = {
        "trades": TRADES_FILENAME,
        "condition_snapshots": CONDITION_SNAPSHOTS_FILENAME,
        "bar_windows": BAR_WINDOWS_FILENAME,
        "tick_windows": TICK_WINDOWS_FILENAME,
        "event_transitions": EVENT_TRANSITIONS_FILENAME,
        "exit_audits": EXIT_AUDITS_FILENAME,
        "validation_checks": VALIDATION_CHECKS_FILENAME,
    }
    metadata_record["record_counts"] = {
        "trades": int(len(frames[TRADES_FILENAME])),
        "condition_snapshots": int(len(frames[CONDITION_SNAPSHOTS_FILENAME])),
        "bar_windows": int(len(frames[BAR_WINDOWS_FILENAME])),
        "tick_windows": int(len(frames[TICK_WINDOWS_FILENAME])),
        "event_transitions": int(len(frames[EVENT_TRANSITIONS_FILENAME])),
        "exit_audits": int(len(frames[EXIT_AUDITS_FILENAME])),
        "validation_checks": int(len(frames[VALIDATION_CHECKS_FILENAME])),
    }
    write_json(run_dir / METADATA_FILENAME, metadata_record)
    return metadata_record


def build_trade_summaries(
    trades: pd.DataFrame,
    metadata: ValidationMetadata | dict[str, Any] | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    metadata_record = _metadata_record(metadata, **overrides)
    tick_size = _float_or_none(metadata_record.get("tick_size"))
    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        direction = _text_or_none(_first_value(trade, "direction", "side"))
        entry_price = _float_or_none(_first_value(trade, "entry_price"))
        exit_price = _float_or_none(_first_value(trade, "exit_price"))
        rows.append(
            {
                "run_id": metadata_record.get("run_id") or _first_value(trade, "run_id"),
                "campaign_id": metadata_record.get("campaign_id") or _first_value(trade, "campaign_id"),
                "strategy_id": (
                    metadata_record.get("strategy_id")
                    or _first_value(trade, "strategy_id", "strategy_name")
                ),
                "variant_id": metadata_record.get("variant_id") or _first_value(trade, "variant_id"),
                "trade_id": _first_value(trade, "trade_id"),
                "symbol": metadata_record.get("symbol") or _first_value(trade, "symbol"),
                "contract": _first_value(trade, "contract", "contract_symbol"),
                "session_date": _text_or_none(_first_value(trade, "session_date")),
                "direction": direction,
                "entry_time": _first_value(trade, "entry_time", "entry_timestamp"),
                "entry_price": entry_price,
                "entry_order_type": _text_or_none(_first_value(trade, "entry_order_type", "entry_mode")),
                "stop_price": _float_or_none(_first_value(trade, "stop_price")),
                "target_price": _float_or_none(_first_value(trade, "target_price")),
                "exit_time": _first_value(trade, "exit_time", "exit_timestamp"),
                "exit_price": exit_price,
                "exit_reason": _text_or_none(_first_value(trade, "exit_reason")),
                "pnl_ticks": _pnl_ticks(
                    _first_value(trade, "pnl_ticks"),
                    entry_price,
                    exit_price,
                    direction,
                    tick_size,
                ),
                "pnl_usd": _float_or_none(_first_value(trade, "pnl_usd", "net_pnl", "pnl")),
                "r_multiple": _float_or_none(_first_value(trade, "r_multiple")),
                "bars_held": _bars_held(trade, metadata_record),
                "contracts": _int_or_none(_first_value(trade, "contracts", "quantity")),
                "fees": _float_or_none(_first_value(trade, "fees", "commission", "commission_cost")),
                "slippage": _float_or_none(_first_value(trade, "slippage", "slippage_cost")),
                "was_forced_flatten": _bool_or_none(
                    _first_value(trade, "was_forced_flatten", "forced_flatten"),
                ),
                "notes": _text_or_none(_first_value(trade, "notes")),
                "debug_flags": _debug_flags(trade),
            }
        )
    return normalize_columns(pd.DataFrame(rows), TRADE_SUMMARY_COLUMNS)


def build_condition_snapshots(
    trades: pd.DataFrame,
    metadata: ValidationMetadata | dict[str, Any] | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    _ = _metadata_record(metadata, **overrides)
    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        rows.append(
            {
                "trade_id": _first_value(trade, "trade_id"),
                "signal_time": _first_value(trade, "signal_time", "signal_timestamp"),
                "decision_bar_time": _first_value(trade, "decision_bar_time", "decision_timestamp", "timestamp"),
                "entry_execution_time": _first_value(
                    trade,
                    "entry_execution_time",
                    "intended_entry_timestamp",
                    "entry_timestamp",
                ),
                "entry_mode": _text_or_none(_first_value(trade, "entry_mode")),
                "swept_level_name": _text_or_none(
                    _first_value(trade, "swept_level_name", "market_level_type", "level_type"),
                ),
                "swept_level_price": _float_or_none(
                    _first_value(trade, "swept_level_price", "market_level_price", "level_price"),
                ),
                "sweep_time": _first_value(trade, "sweep_time", "sweep_timestamp"),
                "reclaim_time": _first_value(trade, "reclaim_time", "reclaim_timestamp"),
                "reclaim_window_bars": _int_or_none(_first_value(trade, "reclaim_window_bars")),
                "sweep_bar_open": _float_or_none(_first_value(trade, "sweep_bar_open")),
                "sweep_bar_high": _float_or_none(_first_value(trade, "sweep_bar_high")),
                "sweep_bar_low": _float_or_none(_first_value(trade, "sweep_bar_low")),
                "sweep_bar_close": _float_or_none(_first_value(trade, "sweep_bar_close")),
                "sweep_bar_volume": _float_or_none(_first_value(trade, "sweep_bar_volume")),
                "avg_volume_reference": _float_or_none(
                    _first_value(trade, "avg_volume_reference", "rolling_volume", "avg_volume"),
                ),
                "volume_filter_pass": _bool_or_none(_first_value(trade, "volume_filter_pass")),
                "delta_value": _float_or_none(
                    _first_value(trade, "delta_value", "signed_volume", "absorption_bucket_delta"),
                ),
                "delta_pct": _float_or_none(
                    _first_value(trade, "delta_pct", "delta_imbalance", "aoi_delta_imbalance"),
                ),
                "delta_filter_pass": _bool_or_none(_first_value(trade, "delta_filter_pass")),
                "bid_volume": _float_or_none(_first_value(trade, "bid_volume", "sell_volume")),
                "ask_volume": _float_or_none(_first_value(trade, "ask_volume", "buy_volume")),
                "total_volume": _float_or_none(_first_value(trade, "total_volume", "volume")),
                "cumulative_delta": _float_or_none(_first_value(trade, "cumulative_delta")),
                "imbalance_count": _float_or_none(
                    _first_value(
                        trade,
                        "imbalance_count",
                        "footprint_buy_imbalance_count",
                        "footprint_sell_imbalance_count",
                    )
                ),
                "stacked_imbalance_pass": _bool_or_none(_first_value(trade, "stacked_imbalance_pass")),
                "close_location_metric": _float_or_none(
                    _first_value(trade, "close_location_metric", "close_location"),
                ),
                "rth_filter_pass": _bool_or_none(_first_value(trade, "rth_filter_pass", "is_rth")),
                "no_trade_window_filter_pass": _bool_or_none(
                    _first_value(trade, "no_trade_window_filter_pass"),
                ),
                "max_trades_filter_pass": _bool_or_none(_first_value(trade, "max_trades_filter_pass")),
                "final_entry_pass": _bool_or_none(_first_value(trade, "final_entry_pass")),
                "reason_if_rejected": _text_or_none(_first_value(trade, "reason_if_rejected")),
                "entry_trigger_values": _text_or_none(_first_value(trade, "entry_trigger_values")),
                "filter_pass_values": _text_or_none(_first_value(trade, "filter_pass_values")),
                "raw_orderflow_values": _text_or_none(_first_value(trade, "raw_orderflow_values")),
                "signal_metadata": _text_or_none(_first_value(trade, "signal_metadata")),
                "signal_report_fields": _text_or_none(_first_value(trade, "signal_report_fields")),
                "decision_context": _text_or_none(_first_value(trade, "decision_context")),
                "stop_anchor_calculation": _text_or_none(_first_value(trade, "stop_anchor_calculation")),
                "target_calculation": _text_or_none(_first_value(trade, "target_calculation")),
            }
        )
    return normalize_columns(pd.DataFrame(rows), CONDITION_SNAPSHOT_COLUMNS)


def build_bar_window_rows(bars: pd.DataFrame, *, trade_id: str | int | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, bar in bars.iterrows():
        bid_volume = _first_value(bar, "bid_volume", "sell_volume")
        ask_volume = _first_value(bar, "ask_volume", "buy_volume")
        rows.append(
            {
                "trade_id": _first_value(bar, "trade_id") if trade_id is None else trade_id,
                "timestamp": _first_value(bar, "timestamp", "datetime"),
                "open": _float_or_none(_first_value(bar, "open")),
                "high": _float_or_none(_first_value(bar, "high")),
                "low": _float_or_none(_first_value(bar, "low")),
                "close": _float_or_none(_first_value(bar, "close")),
                "volume": _float_or_none(_first_value(bar, "volume")),
                "bid_volume": _float_or_none(bid_volume),
                "ask_volume": _float_or_none(ask_volume),
                "delta": _float_or_none(_first_value(bar, "delta", "signed_volume")),
                "cumulative_delta": _float_or_none(_first_value(bar, "cumulative_delta")),
                "is_rth": _bool_or_none(_first_value(bar, "is_rth")),
                "session_date": _text_or_none(_first_value(bar, "session_date")),
                "prev_rth_high": _float_or_none(_first_value(bar, "prev_rth_high", "previous_rth_high")),
                "prev_rth_low": _float_or_none(_first_value(bar, "prev_rth_low", "previous_rth_low")),
                "overnight_high": _float_or_none(_first_value(bar, "overnight_high")),
                "overnight_low": _float_or_none(_first_value(bar, "overnight_low")),
                "vwap": _float_or_none(_first_value(bar, "vwap", "session_vwap")),
                "profile_poc": _float_or_none(_first_value(bar, "profile_poc", "poc")),
                "profile_vah": _float_or_none(_first_value(bar, "profile_vah", "vah")),
                "profile_val": _float_or_none(_first_value(bar, "profile_val", "val")),
            }
        )
    return normalize_columns(pd.DataFrame(rows), BAR_WINDOW_COLUMNS)


def build_tick_window_rows(ticks: pd.DataFrame, *, trade_id: str | int | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, tick in ticks.iterrows():
        bid_volume = _first_value(tick, "bid_volume", "sell_volume")
        ask_volume = _first_value(tick, "ask_volume", "buy_volume")
        price = _float_or_none(_first_value(tick, "price", "close"))
        rows.append(
            {
                "trade_id": _first_value(tick, "trade_id") if trade_id is None else trade_id,
                "timestamp": _first_value(tick, "timestamp", "datetime"),
                "source_ordinal": _int_or_none(_first_value(tick, "source_ordinal")),
                "price": price,
                "volume": _float_or_none(_first_value(tick, "volume")),
                "bid_volume": _float_or_none(bid_volume),
                "ask_volume": _float_or_none(ask_volume),
                "aggressor_side": _text_or_none(_first_value(tick, "aggressor_side", "side")),
                "delta": _float_or_none(_first_value(tick, "delta", "signed_volume")),
                "price_level": _float_or_none(_first_value(tick, "price_level")) or price,
                "price_level_bid_volume": _float_or_none(
                    _first_value(tick, "price_level_bid_volume", "level_bid_volume", "sell_volume")
                ),
                "price_level_ask_volume": _float_or_none(
                    _first_value(tick, "price_level_ask_volume", "level_ask_volume", "buy_volume")
                ),
                "price_level_delta": _float_or_none(
                    _first_value(tick, "price_level_delta", "level_delta", "signed_volume")
                ),
            }
        )
    return normalize_columns(pd.DataFrame(rows), TICK_WINDOW_COLUMNS)


def build_exit_audits(
    trades: pd.DataFrame,
    metadata: ValidationMetadata | dict[str, Any] | None = None,
    **overrides: Any,
) -> pd.DataFrame:
    metadata_record = _metadata_record(metadata, **overrides)
    tick_size = _float_or_none(metadata_record.get("tick_size"))
    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        rows.append(
            {
                "trade_id": _first_value(trade, "trade_id"),
                "entry_time": _first_value(trade, "entry_time", "entry_timestamp"),
                "entry_price": _float_or_none(_first_value(trade, "entry_price")),
                "stop_price": _float_or_none(_first_value(trade, "stop_price")),
                "target_price": _float_or_none(_first_value(trade, "target_price")),
                "exit_time": _first_value(trade, "exit_time", "exit_timestamp"),
                "exit_price": _float_or_none(_first_value(trade, "exit_price")),
                "exit_reason": _text_or_none(_first_value(trade, "exit_reason")),
                "first_touch_tp_time": _first_value(trade, "first_touch_tp_time"),
                "first_touch_sl_time": _first_value(trade, "first_touch_sl_time"),
                "first_touch_tp_price": _float_or_none(_first_value(trade, "first_touch_tp_price")),
                "first_touch_sl_price": _float_or_none(_first_value(trade, "first_touch_sl_price")),
                "first_touch_decision": _text_or_none(_first_value(trade, "first_touch_decision")),
                "first_touch_exit_decision": _text_or_none(_first_value(trade, "first_touch_exit_decision")),
                "same_bar_ambiguous": _bool_or_none(_first_value(trade, "same_bar_ambiguous")),
                "ambiguity_resolution": _text_or_none(_first_value(trade, "ambiguity_resolution")),
                "forced_flatten_reason": _text_or_none(_first_value(trade, "forced_flatten_reason")),
                "exit_bar_timestamp": _first_value(trade, "exit_bar_timestamp"),
                "exit_bar_open": _float_or_none(_first_value(trade, "exit_bar_open")),
                "exit_bar_high": _float_or_none(_first_value(trade, "exit_bar_high")),
                "exit_bar_low": _float_or_none(_first_value(trade, "exit_bar_low")),
                "exit_bar_close": _float_or_none(_first_value(trade, "exit_bar_close")),
                "raw_exit_price": _float_or_none(_first_value(trade, "raw_exit_price")),
                "tp_hit_on_exit_bar": _bool_or_none(_first_value(trade, "tp_hit_on_exit_bar")),
                "sl_hit_on_exit_bar": _bool_or_none(_first_value(trade, "sl_hit_on_exit_bar")),
                "max_favorable_excursion_ticks": _excursion_ticks(
                    _first_value(trade, "max_favorable_excursion_ticks", "max_favorable_excursion"),
                    tick_size,
                ),
                "max_adverse_excursion_ticks": _excursion_ticks(
                    _first_value(trade, "max_adverse_excursion_ticks", "max_adverse_excursion"),
                    tick_size,
                ),
                "mfe_ticks": _ticks_or_point_excursion(
                    trade,
                    ["mfe_ticks", "max_favorable_excursion_ticks"],
                    "max_favorable_excursion",
                    tick_size,
                ),
                "mae_ticks": _ticks_or_point_excursion(
                    trade,
                    ["mae_ticks", "max_adverse_excursion_ticks"],
                    "max_adverse_excursion",
                    tick_size,
                ),
                "highest_price_before_exit": _float_or_none(
                    _first_value(trade, "highest_price_before_exit", "highest_price"),
                ),
                "lowest_price_before_exit": _float_or_none(
                    _first_value(trade, "lowest_price_before_exit", "lowest_price"),
                ),
                "max_price_before_exit": _float_or_none(
                    _first_value(trade, "max_price_before_exit", "highest_price_before_exit", "highest_price"),
                ),
                "min_price_before_exit": _float_or_none(
                    _first_value(trade, "min_price_before_exit", "lowest_price_before_exit", "lowest_price"),
                ),
                "tick_count_checked": _int_or_none(_first_value(trade, "tick_count_checked")),
                "path_source": _text_or_none(_first_value(trade, "path_source")),
                "engine_exit_decision": _text_or_none(_first_value(trade, "engine_exit_decision")),
                "engine_exit_matches_path": _bool_or_none(_first_value(trade, "engine_exit_matches_path")),
                "warning_flags": _text_or_none(_first_value(trade, "warning_flags")),
            }
        )
    return normalize_columns(pd.DataFrame(rows), EXIT_AUDIT_COLUMNS)


def _metadata_record(
    metadata: ValidationMetadata | dict[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    if metadata is None:
        record: dict[str, Any] = {}
    elif isinstance(metadata, ValidationMetadata):
        record = metadata.to_record()
    else:
        record = dict(metadata)
    record.update({key: value for key, value in overrides.items() if value is not None})
    return record


def _first_value(row: pd.Series, *columns: str) -> Any:
    for column in columns:
        if column in row.index:
            value = row[column]
            if not _is_missing(value):
                return value
    return None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text_or_none(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if _is_missing(value):
        return None
    return int(value)


def _bool_or_none(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _pnl_ticks(
    raw_pnl_ticks: Any,
    entry_price: float | None,
    exit_price: float | None,
    direction: str | None,
    tick_size: float | None,
) -> float | None:
    existing = _float_or_none(raw_pnl_ticks)
    if existing is not None:
        return existing
    if entry_price is None or exit_price is None or direction is None or not tick_size:
        return None
    side = direction.lower()
    point_pnl = exit_price - entry_price if side == "long" else entry_price - exit_price
    return point_pnl / tick_size


def _bars_held(trade: pd.Series, metadata: dict[str, Any]) -> float | None:
    existing = _float_or_none(_first_value(trade, "bars_held"))
    if existing is not None:
        return existing
    timeframe_minutes = _float_or_none(metadata.get("timeframe_minutes"))
    if not timeframe_minutes:
        return None
    entry_time = _first_value(trade, "entry_time", "entry_timestamp")
    exit_time = _first_value(trade, "exit_time", "exit_timestamp")
    if _is_missing(entry_time) or _is_missing(exit_time):
        return None
    entry_ts = pd.Timestamp(entry_time)
    exit_ts = pd.Timestamp(exit_time)
    if pd.isna(entry_ts) or pd.isna(exit_ts):
        return None
    return (exit_ts - entry_ts).total_seconds() / 60.0 / timeframe_minutes


def _excursion_ticks(value: Any, tick_size: float | None) -> float | None:
    numeric = _float_or_none(value)
    if numeric is None:
        return None
    if not tick_size:
        return numeric
    return numeric / tick_size


def _ticks_or_point_excursion(
    row: pd.Series,
    tick_columns: list[str],
    point_column: str,
    tick_size: float | None,
) -> float | None:
    existing = _float_or_none(_first_value(row, *tick_columns))
    if existing is not None:
        return existing
    return _excursion_ticks(_first_value(row, point_column), tick_size)


def _debug_flags(trade: pd.Series) -> str | None:
    explicit = _text_or_none(_first_value(trade, "debug_flags"))
    if explicit is not None:
        return explicit
    flags: list[str] = []
    for column in (
        "entry_mode",
        "signal_stop_price",
        "dynamic_stop_activated",
        "intrabar_source_quality_label",
        "intrabar_source_quality_is_execution_equivalent",
        "same_bar_ambiguous",
        "ambiguity_resolution",
    ):
        value = _first_value(trade, column)
        if not _is_missing(value):
            flags.append(f"{column}={value}")
    return ";".join(flags) if flags else None
