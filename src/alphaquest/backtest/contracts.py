from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import pandas as pd

from alphaquest.backtest.sizing import tick_value_from_core


PRICE_COLUMNS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class ExecutionAssumptions:
    tick_size: float
    tick_value: float
    point_value: float | None
    commission_per_contract: float
    slippage_ticks: float
    tick_value_source: str
    commission_source: str
    slippage_source: str

    @classmethod
    def from_core_config(cls, core: dict[str, Any]) -> "ExecutionAssumptions":
        tick_size = _finite_number(core.get("tick_size", 0.25), "core.tick_size", positive=True)
        tick_value = _finite_number(
            tick_value_from_core(core, tick_size),
            "core.tick_value",
            positive=True,
        )
        point_value = None
        if core.get("point_value") is not None:
            point_value = _finite_number(core["point_value"], "core.point_value", positive=True)
        if point_value is not None and core.get("tick_value") is not None:
            implied_tick_value = point_value * tick_size
            if not math.isclose(tick_value, implied_tick_value, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(
                    "core.tick_value must equal core.point_value * core.tick_size when both are configured."
                )

        commission = _finite_number(
            core.get("commission_per_contract", 2.5),
            "core.commission_per_contract",
            minimum=0.0,
        )
        slippage = _finite_number(core.get("slippage_ticks", 1.0), "core.slippage_ticks", minimum=0.0)
        return cls(
            tick_size=tick_size,
            tick_value=tick_value,
            point_value=point_value,
            commission_per_contract=commission,
            slippage_ticks=slippage,
            tick_value_source=(
                "tick_value" if core.get("tick_value") is not None else "point_value" if point_value is not None else "legacy_default"
            ),
            commission_source="configured" if core.get("commission_per_contract") is not None else "legacy_default",
            slippage_source="configured" if core.get("slippage_ticks") is not None else "legacy_default",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "tick_size": self.tick_size,
            "tick_value": self.tick_value,
            "point_value": self.point_value,
            "commission_per_contract": self.commission_per_contract,
            "slippage_ticks": self.slippage_ticks,
            "commission_basis": "per_contract_per_side",
            "slippage_basis": "adverse_ticks_per_side",
            "tick_value_source": self.tick_value_source,
            "commission_source": self.commission_source,
            "slippage_source": self.slippage_source,
        }


def validate_market_data_contract(
    data: pd.DataFrame,
    *,
    label: str,
    require_session_date: bool,
    allow_duplicate_timestamps: bool = False,
) -> dict[str, Any]:
    required = {"timestamp", *PRICE_COLUMNS}
    if require_session_date:
        required.add("session_date")
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"{label} is missing required column(s): {missing}.")

    if data.empty:
        return {
            "rows": 0,
            "columns": list(data.columns),
            "start_timestamp": None,
            "end_timestamp": None,
            "timezone": None,
            "duplicate_timestamps": 0,
            "input_was_monotonic": True,
            "duplicate_timestamp_ordering": None,
        }

    timestamps = _validated_timestamps(data["timestamp"], label)
    utc_values = pd.Series([timestamp.tz_convert("UTC").value for timestamp in timestamps], index=data.index)
    duplicate_count = int(utc_values.duplicated(keep=False).sum())
    if duplicate_count and not allow_duplicate_timestamps:
        raise ValueError(f"{label} contains {duplicate_count} row(s) with duplicate timestamps.")

    numeric = {}
    for column in PRICE_COLUMNS:
        values = pd.to_numeric(data[column], errors="coerce")
        invalid = values.isna() | ~values.map(math.isfinite)
        if bool(invalid.any()):
            rows = [str(item) for item in data.index[invalid][:5]]
            raise ValueError(f"{label}.{column} contains non-finite values at row(s): {', '.join(rows)}.")
        numeric[column] = values.astype(float)

    prices = pd.DataFrame(numeric, index=data.index)
    invalid_ohlc = (
        (prices["high"] < prices[["open", "low", "close"]].max(axis=1))
        | (prices["low"] > prices[["open", "high", "close"]].min(axis=1))
    )
    if bool(invalid_ohlc.any()):
        rows = [str(item) for item in data.index[invalid_ohlc][:5]]
        raise ValueError(f"{label} contains invalid OHLC envelopes at row(s): {', '.join(rows)}.")

    if require_session_date and bool(data["session_date"].isna().any()):
        raise ValueError(f"{label}.session_date contains missing values.")

    timezone_names = sorted({str(timestamp.tzinfo) for timestamp in timestamps})
    return {
        "rows": int(len(data)),
        "columns": list(data.columns),
        "start_timestamp": min(timestamps).isoformat(),
        "end_timestamp": max(timestamps).isoformat(),
        "timezone": timezone_names[0] if len(timezone_names) == 1 else timezone_names,
        "duplicate_timestamps": duplicate_count,
        "input_was_monotonic": bool(utc_values.is_monotonic_increasing),
        "duplicate_timestamp_ordering": "stable_input_order" if duplicate_count else None,
    }


def _validated_timestamps(values: pd.Series, label: str) -> list[pd.Timestamp]:
    timestamps: list[pd.Timestamp] = []
    invalid_rows = []
    naive_rows = []
    for index, value in values.items():
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            invalid_rows.append(str(index))
            continue
        if pd.isna(timestamp):
            invalid_rows.append(str(index))
            continue
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            naive_rows.append(str(index))
            continue
        timestamps.append(timestamp)
    if invalid_rows:
        raise ValueError(f"{label}.timestamp contains invalid values at row(s): {', '.join(invalid_rows[:5])}.")
    if naive_rows:
        raise ValueError(f"{label}.timestamp must be timezone-aware at row(s): {', '.join(naive_rows[:5])}.")
    return timestamps


def _finite_number(
    value: object,
    label: str,
    *,
    positive: bool = False,
    minimum: float | None = None,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    if positive and number <= 0:
        raise ValueError(f"{label} must be greater than 0.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} must be at least {minimum:g}.")
    return number
