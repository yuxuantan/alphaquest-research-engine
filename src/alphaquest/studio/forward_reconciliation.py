"""Deterministic reconciliation for true-forward trade-journal attachments.

The parser is deliberately narrow. It derives only values that are explicit in
one CSV and returns blockers instead of guessing column meanings or silently
treating absent risk flags as false. A human still confirms the preview before
the immutable forward-incubation event is appended.
"""

from __future__ import annotations

import csv
from collections import Counter
import math
from pathlib import Path
from typing import Any


_TRADE_ID_COLUMNS = ("trade_id", "execution_id", "id")
_PNL_COLUMNS = ("net_pnl", "realized_pnl", "pnl", "profit_loss")
_PROP_BREACH_COLUMNS = ("prop_rule_breach", "account_rule_breach")
_FLATTEN_COLUMNS = ("forced_flatten_violation", "flatten_violation")
_TRUE = frozenset({"1", "true", "yes", "y"})
_FALSE = frozenset({"0", "false", "no", "n", ""})


def reconcile_forward_trade_csv(path: str | Path) -> dict[str, Any]:
    """Return an auditable calculation without mutating incubation evidence."""

    source = Path(path)
    blockers: list[str] = []
    warnings: list[str] = []
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = [str(value).strip() for value in (reader.fieldnames or [])]
            rows = [dict(row) for row in reader]
    except (OSError, UnicodeError, csv.Error) as exc:
        return _result(blockers=[f"CSV could not be parsed: {exc}"])

    if not columns:
        return _result(blockers=["CSV has no header row"])
    if not rows:
        return _result(columns=columns, blockers=["CSV contains no trade rows"])

    normalized = {column.casefold().strip(): column for column in columns}
    pnl_column = _first_column(normalized, _PNL_COLUMNS)
    trade_id_column = _first_column(normalized, _TRADE_ID_COLUMNS)
    prop_column = _first_column(normalized, _PROP_BREACH_COLUMNS)
    flatten_column = _first_column(normalized, _FLATTEN_COLUMNS)

    if pnl_column is None:
        blockers.append(
            "CSV must contain one explicit P&L column: " + ", ".join(_PNL_COLUMNS)
        )
    pnl_values: list[float] = []
    if pnl_column is not None:
        for index, row in enumerate(rows, start=2):
            raw = str(row.get(pnl_column) or "").strip().replace(",", "").replace("$", "")
            try:
                value = float(raw)
            except ValueError:
                blockers.append(f"row {index} has invalid {pnl_column}: {raw or 'blank'}")
                continue
            if not math.isfinite(value):
                blockers.append(f"row {index} has non-finite {pnl_column}")
                continue
            pnl_values.append(value)

    if trade_id_column is None:
        warnings.append("No trade identity column was found; duplicate rows cannot be detected")
    else:
        identities = [str(row.get(trade_id_column) or "").strip() for row in rows]
        if any(not value for value in identities):
            blockers.append(f"{trade_id_column} contains blank identities")
        duplicates = sorted(
            value for value, count in Counter(identities).items() if value and count > 1
        )
        if duplicates:
            blockers.append(
                f"{trade_id_column} contains {len(duplicates)} duplicate identity value(s)"
            )

    prop_breach = _aggregate_boolean(rows, prop_column, blockers)
    flatten_violation = _aggregate_boolean(rows, flatten_column, blockers)
    if prop_column is None:
        warnings.append("Prop-rule breach is not encoded in the CSV and must be confirmed manually")
    if flatten_column is None:
        warnings.append("Forced-flatten compliance is not encoded in the CSV and must be confirmed manually")

    return _result(
        columns=columns,
        row_count=len(rows),
        trade_count_delta=len(rows),
        net_pnl_delta=round(sum(pnl_values), 10) if len(pnl_values) == len(rows) else None,
        prop_rule_breach=prop_breach,
        forced_flatten_violation=flatten_violation,
        warnings=warnings,
        blockers=blockers,
    )


def _first_column(columns: dict[str, str], choices: tuple[str, ...]) -> str | None:
    return next((columns[name] for name in choices if name in columns), None)


def _aggregate_boolean(
    rows: list[dict[str, Any]],
    column: str | None,
    blockers: list[str],
) -> bool | None:
    if column is None:
        return None
    values: list[bool] = []
    for index, row in enumerate(rows, start=2):
        raw = str(row.get(column) or "").strip().casefold()
        if raw in _TRUE:
            values.append(True)
        elif raw in _FALSE:
            values.append(False)
        else:
            blockers.append(f"row {index} has invalid boolean {column}: {raw}")
    return any(values) if len(values) == len(rows) else None


def _result(
    *,
    columns: list[str] | None = None,
    row_count: int = 0,
    trade_count_delta: int | None = None,
    net_pnl_delta: float | None = None,
    prop_rule_breach: bool | None = None,
    forced_flatten_violation: bool | None = None,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    errors = list(blockers or [])
    return {
        "schema": "alphaquest.forward-journal-reconciliation/v1",
        "usable": not errors and trade_count_delta is not None and net_pnl_delta is not None,
        "columns": columns or [],
        "row_count": row_count,
        "trade_count_delta": trade_count_delta,
        "net_pnl_delta": net_pnl_delta,
        "prop_rule_breach": prop_rule_breach,
        "forced_flatten_violation": forced_flatten_violation,
        "warnings": list(warnings or []),
        "blockers": errors,
    }


__all__ = ["reconcile_forward_trade_csv"]
