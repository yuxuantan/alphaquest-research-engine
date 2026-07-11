from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


PARITY_FIELDS = (
    "strategy_name",
    "level_type",
    "signal_timestamp",
    "entry_timestamp",
    "direction",
    "entry_price",
    "stop_price",
    "target_price",
    "contracts",
    "signal_flatten_time",
)


@dataclass(frozen=True)
class ParityMismatch:
    index: int
    field: str
    expected: Any
    actual: Any


def backtest_trade_intents(trades: pd.DataFrame) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    out = trades.copy()
    if "trade_id" in out.columns:
        out = out.sort_values("trade_id", kind="mergesort")
    return [_intent_from_row(row) for _, row in out.iterrows()]


def compare_trade_intents(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    *,
    price_tolerance: float = 1e-9,
) -> list[ParityMismatch]:
    mismatches: list[ParityMismatch] = []
    if len(expected) != len(actual):
        mismatches.append(ParityMismatch(-1, "length", len(expected), len(actual)))
        return mismatches
    for index, (left, right) in enumerate(zip(expected, actual), start=1):
        for field in PARITY_FIELDS:
            expected_value = _normal_value(left.get(field), field=field)
            actual_value = _normal_value(right.get(field), field=field)
            if field.endswith("_price"):
                if _price_differs(expected_value, actual_value, price_tolerance):
                    mismatches.append(ParityMismatch(index, field, expected_value, actual_value))
            elif expected_value != actual_value:
                mismatches.append(ParityMismatch(index, field, expected_value, actual_value))
    return mismatches


def assert_trade_intent_parity(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    *,
    price_tolerance: float = 1e-9,
) -> None:
    mismatches = compare_trade_intents(expected, actual, price_tolerance=price_tolerance)
    if mismatches:
        details = "; ".join(
            f"row={item.index} field={item.field} expected={item.expected!r} actual={item.actual!r}"
            for item in mismatches[:10]
        )
        raise AssertionError(f"trade-intent parity failed: {details}")


def _intent_from_row(row: pd.Series) -> dict[str, Any]:
    return {field: _normal_value(row.get(field), field=field) for field in PARITY_FIELDS}


def _normal_value(value: Any, *, field: str | None = None) -> Any:
    if value is None or pd.isna(value):
        return None
    if field and field.endswith("_timestamp"):
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware for parity comparison.")
        return timestamp.tz_convert("UTC").isoformat()
    if hasattr(value, "item"):
        return _normal_value(value.item(), field=field)
    return value


def _price_differs(left: Any, right: Any, tolerance: float) -> bool:
    if left is None or right is None:
        return left != right
    return abs(float(left) - float(right)) > tolerance
