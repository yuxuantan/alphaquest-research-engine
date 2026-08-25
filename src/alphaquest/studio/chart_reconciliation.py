"""Supplementary chart-export reconciliation for governed mechanics samples."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence


_ALIASES = {
    "trade_id": ("trade_id", "trade", "id"),
    "entry_time": ("entry_time", "entry_timestamp", "entry_datetime"),
    "exit_time": ("exit_time", "exit_timestamp", "exit_datetime"),
    "entry_price": ("entry_price", "entry_fill_price", "entry"),
    "exit_price": ("exit_price", "exit_fill_price", "exit"),
    "direction": ("direction", "side", "position"),
}


def reconcile_chart_export(
    path: str | Path,
    governed_trades: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source = Path(path)
    with source.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("chart reconciliation CSV must contain at least one data row")
    columns = {str(column).strip().casefold(): str(column) for column in rows[0]}
    mapped = {
        field: next((columns[name] for name in aliases if name in columns), None)
        for field, aliases in _ALIASES.items()
    }
    if not mapped["trade_id"]:
        raise ValueError("chart reconciliation CSV requires a trade_id column")
    external = {str(row[mapped["trade_id"]]).strip(): row for row in rows}
    if "" in external:
        raise ValueError("chart reconciliation CSV contains an empty trade_id")
    comparisons: list[dict[str, Any]] = []
    governed_ids: set[str] = set()
    for governed in governed_trades:
        trade_id = str(_mapping_value(governed, "trade_id") or "").strip()
        if not trade_id:
            continue
        governed_ids.add(trade_id)
        row = external.get(trade_id)
        mismatches: list[dict[str, Any]] = []
        compared: list[str] = []
        if row is None:
            mismatches.append({"field": "trade_id", "governed": trade_id, "external": None})
        else:
            for field in ("entry_time", "exit_time", "entry_price", "exit_price", "direction"):
                column = mapped[field]
                governed_value = _mapping_value(governed, field)
                if column is None or governed_value in {None, ""} or row.get(column) in {None, ""}:
                    continue
                compared.append(field)
                external_value = row[column]
                if not _equivalent(field, governed_value, external_value):
                    mismatches.append(
                        {"field": field, "governed": governed_value, "external": external_value}
                    )
        comparisons.append(
            {
                "trade_id": trade_id,
                "status": "MATCH" if row is not None and not mismatches and compared else "MISMATCH",
                "compared_fields": compared,
                "mismatches": mismatches,
            }
        )
    unmatched = sorted(set(external) - governed_ids)
    matched = sum(item["status"] == "MATCH" for item in comparisons)
    return {
        "schema": "alphaquest.chart-reconciliation/v1",
        "source_filename": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "status": "MATCH" if comparisons and matched == len(comparisons) and not unmatched else "NEEDS_REVIEW",
        "matched_trades": matched,
        "required_trades": len(comparisons),
        "unmatched_external_trade_ids": unmatched,
        "comparisons": comparisons,
        "approval_effect": "NONE",
        "note": (
            "This import accelerates comparison only. It cannot annotate samples, mark them Correct, "
            "or approve mechanics; the reviewer must inspect the hash-bound Studio evidence."
        ),
    }


def _equivalent(field: str, governed: Any, external: Any) -> bool:
    if field in {"entry_price", "exit_price"}:
        try:
            return abs(float(governed) - float(external)) <= 1e-9
        except (TypeError, ValueError):
            return False
    if field in {"entry_time", "exit_time"}:
        left = _timestamp(governed)
        right = _timestamp(external)
        return left is not None and right is not None and left == right
    return str(governed).strip().casefold() == str(external).strip().casefold()


def _mapping_value(value: Mapping[str, Any], field: str) -> Any:
    normalized = {str(key).strip().casefold(): item for key, item in value.items()}
    return next((normalized[name] for name in _ALIASES[field] if name in normalized), None)


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


__all__ = ["reconcile_chart_export"]
