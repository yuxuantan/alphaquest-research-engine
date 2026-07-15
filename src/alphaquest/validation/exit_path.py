"""Trade path audit helpers for validation artifacts.

The helpers in this module do not change backtest fill decisions. They inspect
the selected-trade path already exported for dashboard validation and add an
independent TP/SL first-touch audit when ordered tick/detail rows are present.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from alphaquest.validation.schema import EXIT_AUDIT_COLUMNS, normalize_columns


EXIT_AUDIT_BASE_COLUMNS = ["timestamp", "price"]


def enrich_exit_audits(
    trades: pd.DataFrame,
    exit_audits: pd.DataFrame | None = None,
    tick_windows: pd.DataFrame | None = None,
    *,
    tick_size: float | None = None,
) -> pd.DataFrame:
    if trades is None or trades.empty:
        return normalize_columns(pd.DataFrame(), EXIT_AUDIT_COLUMNS)
    audit_rows = exit_audits.copy() if exit_audits is not None else pd.DataFrame()
    tick_rows = tick_windows.copy() if tick_windows is not None else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        trade_id = _first_value(trade, "trade_id")
        existing = _row_for_trade(audit_rows, trade_id)
        ticks = _rows_for_trade(tick_rows, trade_id)
        computed = audit_trade_exit_path(trade, ticks, tick_size=tick_size, existing_audit=existing)
        merged = dict(existing)
        for key, value in computed.items():
            if key not in merged or not _is_missing(value):
                merged[key] = value
        rows.append(merged)
    return normalize_columns(pd.DataFrame(rows), EXIT_AUDIT_COLUMNS)


def audit_trade_exit_path(
    trade: pd.Series | dict[str, Any],
    ticks: pd.DataFrame | None = None,
    *,
    tick_size: float | None = None,
    existing_audit: pd.Series | dict[str, Any] | None = None,
) -> dict[str, Any]:
    trade_row = _as_series(trade)
    existing = _as_series(existing_audit)
    warnings = _warning_set(_first_value(existing, "warning_flags"))
    direction = _text_or_none(_first_value(trade_row, "direction", "side"))
    entry_time = _first_value(trade_row, "entry_time", "entry_timestamp")
    exit_time = _first_value(trade_row, "exit_time", "exit_timestamp")
    entry_price = _float_or_none(_first_value(trade_row, "entry_price"))
    stop_price = _float_or_none(_first_value(trade_row, "stop_price"))
    target_price = _float_or_none(_first_value(trade_row, "target_price"))
    exit_price = _float_or_none(_first_value(trade_row, "exit_price"))
    exit_reason = _text_or_none(_first_value(trade_row, "exit_reason"))
    engine_decision = _normal_exit_decision(exit_reason)
    path = trade_path_from_ticks(trade_row, ticks)

    if direction is None:
        warnings.append("missing_direction")
    if _to_utc_timestamp(entry_time) is None:
        warnings.append("missing_entry_time")
    if _is_missing(entry_price):
        warnings.append("missing_entry_price")
    if _is_missing(stop_price):
        warnings.append("missing_stop_price")
    if _is_missing(target_price):
        warnings.append("missing_target_price")
    if path.empty:
        warnings.append("no_tick_path")

    first_tp_time = None
    first_sl_time = None
    first_tp_price = None
    first_sl_price = None
    first_decision = None
    max_price = None
    min_price = None

    if not path.empty and direction is not None and stop_price is not None and target_price is not None:
        if exit_time is not None:
            exit_key = _to_utc_timestamp(exit_time)
            if exit_key is not None:
                timestamps = pd.to_datetime(path["timestamp"], errors="coerce", utc=True)
                if timestamps.notna().any():
                    if not bool((timestamps == exit_key).any()):
                        warnings.append("engine_exit_time_not_found_in_tick_window")
                    if not bool(timestamps.min() <= exit_key <= timestamps.max()):
                        warnings.append("engine_exit_time_outside_tick_window")
        for path_index, row in path.iterrows():
            price = _float_or_none(row.get("price"))
            timestamp = row.get("timestamp")
            if price is None:
                continue
            max_price = price if max_price is None else max(max_price, price)
            min_price = price if min_price is None else min(min_price, price)
            sl_hit, tp_hit = _price_touches_levels(direction, price, stop_price, target_price)
            if tp_hit and first_tp_time is None:
                first_tp_time = timestamp
                first_tp_price = price
            if sl_hit and first_sl_time is None:
                first_sl_time = timestamp
                first_sl_price = price
            if first_decision is None:
                if tp_hit and sl_hit:
                    first_decision = "ambiguous_same_tick"
                    warnings.append("same_tick_tp_sl_ambiguous")
                elif tp_hit:
                    first_decision = "target"
                    if path_index == path.index[0] and _is_through_target(direction, price, target_price, tick_size):
                        warnings.append("first_tick_through_target")
                elif sl_hit:
                    first_decision = "stop"
                    if path_index == path.index[0] and _is_through_stop(direction, price, stop_price, tick_size):
                        warnings.append("first_tick_through_stop")

    mfe_ticks = _mfe_ticks(direction, entry_price, max_price, min_price, tick_size)
    mae_ticks = _mae_ticks(direction, entry_price, max_price, min_price, tick_size)
    engine_matches = _engine_matches_path(engine_decision, first_decision)

    if engine_decision in {"target", "stop"}:
        if first_decision is None:
            warnings.append(f"engine_{engine_decision}_but_level_not_reached_in_tick_path")
        elif first_decision in {"target", "stop"} and first_decision != engine_decision:
            warnings.append(f"engine_{engine_decision}_but_tick_{first_decision}_first")
    elif _is_forced_flatten(exit_reason) and first_decision in {"target", "stop"}:
        warnings.append("forced_flatten_after_normal_exit_touch")

    existing_first_touch_exit = _text_or_none(_first_value(existing, "first_touch_exit_decision"))
    if _truthy(_first_value(existing, "same_bar_ambiguous")) and first_decision in {"target", "stop"}:
        warnings.append("same_bar_resolved_by_tick_path")

    return {
        "trade_id": _first_value(trade_row, "trade_id"),
        "entry_time": entry_time,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "exit_time": exit_time,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "first_touch_tp_time": first_tp_time,
        "first_touch_sl_time": first_sl_time,
        "first_touch_tp_price": first_tp_price,
        "first_touch_sl_price": first_sl_price,
        "first_touch_decision": first_decision,
        "first_touch_exit_decision": existing_first_touch_exit or first_decision,
        "mfe_ticks": mfe_ticks,
        "mae_ticks": mae_ticks,
        "max_favorable_excursion_ticks": mfe_ticks,
        "max_adverse_excursion_ticks": mae_ticks,
        "max_price_before_exit": max_price,
        "min_price_before_exit": min_price,
        "highest_price_before_exit": max_price,
        "lowest_price_before_exit": min_price,
        "tick_count_checked": int(len(path)),
        "path_source": "tick_window" if not path.empty else "none",
        "engine_exit_decision": engine_decision,
        "engine_exit_matches_path": engine_matches,
        "warning_flags": ";".join(dict.fromkeys(warnings)) if warnings else None,
    }


def trade_path_from_ticks(trade: pd.Series | dict[str, Any], ticks: pd.DataFrame | None) -> pd.DataFrame:
    if ticks is None or ticks.empty or "timestamp" not in ticks.columns:
        return pd.DataFrame(columns=EXIT_AUDIT_BASE_COLUMNS)
    trade_row = _as_series(trade)
    entry_time = _to_utc_timestamp(_first_value(trade_row, "entry_time", "entry_timestamp"))
    exit_time = _to_utc_timestamp(_first_value(trade_row, "exit_time", "exit_timestamp"))
    work = ticks.copy()
    work["_timestamp_utc"] = pd.to_datetime(work["timestamp"], errors="coerce", utc=True)
    work["price"] = _numeric_first_available(work, ["price", "close", "last", "price_level"])
    work["_row_order"] = range(len(work))
    work = work.dropna(subset=["_timestamp_utc", "price"])
    if entry_time is not None:
        work = work[work["_timestamp_utc"] >= entry_time]
    if exit_time is not None:
        work = work[work["_timestamp_utc"] <= exit_time]
    if work.empty:
        return pd.DataFrame(columns=EXIT_AUDIT_BASE_COLUMNS)
    work = work.sort_values(["_timestamp_utc", "_row_order"]).reset_index(drop=True)
    return work[["timestamp", "price"]]


def _as_series(value: pd.Series | dict[str, Any] | None) -> pd.Series:
    if value is None:
        return pd.Series(dtype="object")
    if isinstance(value, pd.Series):
        return value
    return pd.Series(dict(value))


def _row_for_trade(frame: pd.DataFrame, trade_id: Any) -> pd.Series:
    if frame is None or frame.empty or "trade_id" not in frame.columns:
        return pd.Series(dtype="object")
    rows = frame[frame["trade_id"] == trade_id]
    if rows.empty:
        rows = frame[frame["trade_id"].astype(str) == str(trade_id)]
    return pd.Series(dtype="object") if rows.empty else rows.iloc[0]


def _rows_for_trade(frame: pd.DataFrame, trade_id: Any) -> pd.DataFrame:
    if frame is None or frame.empty or "trade_id" not in frame.columns:
        return pd.DataFrame()
    rows = frame[frame["trade_id"] == trade_id]
    if rows.empty:
        rows = frame[frame["trade_id"].astype(str) == str(trade_id)]
    return rows.copy()


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
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, bool):
        return result
    return False


def _text_or_none(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    return float(value)


def _to_utc_timestamp(value: Any) -> pd.Timestamp | None:
    if _is_missing(value):
        return None
    try:
        timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(timestamp) else pd.Timestamp(timestamp)


def _numeric_first_available(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    output = pd.Series([pd.NA] * len(frame), index=frame.index, dtype="Float64")
    for column in columns:
        if column in frame.columns:
            output = output.fillna(pd.to_numeric(frame[column], errors="coerce"))
    return output


def _price_touches_levels(direction: str, price: float, stop_price: float, target_price: float) -> tuple[bool, bool]:
    side = str(direction).lower()
    if side == "long":
        return price <= stop_price, price >= target_price
    return price >= stop_price, price <= target_price


def _normal_exit_decision(exit_reason: str | None) -> str | None:
    if exit_reason is None:
        return None
    reason = str(exit_reason).lower()
    if reason in {"target", "tp", "take_profit"} or "target" in reason or "take_profit" in reason:
        return "target"
    if reason in {"stop", "sl", "stop_loss"} or "stop" in reason:
        return "stop"
    return None


def _is_forced_flatten(exit_reason: str | None) -> bool:
    if exit_reason is None:
        return False
    reason = str(exit_reason).lower()
    return "flatten" in reason or reason in {"eod", "end_of_day"}


def _engine_matches_path(engine_decision: str | None, path_decision: str | None) -> bool | None:
    if engine_decision not in {"target", "stop"}:
        return None
    if path_decision not in {"target", "stop"}:
        return False
    return engine_decision == path_decision


def _mfe_ticks(
    direction: str | None,
    entry_price: float | None,
    max_price: float | None,
    min_price: float | None,
    tick_size: float | None,
) -> float | None:
    if direction is None or entry_price is None or max_price is None or min_price is None or not tick_size:
        return None
    if str(direction).lower() == "long":
        return max(0.0, max_price - entry_price) / tick_size
    return max(0.0, entry_price - min_price) / tick_size


def _mae_ticks(
    direction: str | None,
    entry_price: float | None,
    max_price: float | None,
    min_price: float | None,
    tick_size: float | None,
) -> float | None:
    if direction is None or entry_price is None or max_price is None or min_price is None or not tick_size:
        return None
    if str(direction).lower() == "long":
        return max(0.0, entry_price - min_price) / tick_size
    return max(0.0, max_price - entry_price) / tick_size


def _is_through_target(direction: str, price: float, target_price: float, tick_size: float | None) -> bool:
    threshold = abs(float(tick_size or 0.0)) / 2.0
    if str(direction).lower() == "long":
        return price > target_price + threshold
    return price < target_price - threshold


def _is_through_stop(direction: str, price: float, stop_price: float, tick_size: float | None) -> bool:
    threshold = abs(float(tick_size or 0.0)) / 2.0
    if str(direction).lower() == "long":
        return price < stop_price - threshold
    return price > stop_price + threshold


def _warning_set(value: Any) -> list[str]:
    if _is_missing(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _truthy(value: Any) -> bool:
    if _is_missing(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "pass", "passed"}
    return bool(value)
