"""Deterministic duplicate-edge review across definitions and ledger history."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from alphaquest.research.storage import campaign_definition_paths, load_storage_layout


_WORDS = re.compile(r"[a-z0-9]+")


def edge_fingerprint(value: dict[str, Any] | str) -> str:
    if isinstance(value, dict):
        selected = {
            key: _fingerprint_value(key, value.get(key))
            for key in ("market_behavior", "causal_mechanism", "signal_inputs", "market_context", "holding_period")
        }
        text = json.dumps(selected, sort_keys=True, separators=(",", ":"), default=str)
    else:
        text = " ".join(sorted(_tokens(value)))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def duplicate_matches(
    *,
    project_root: str | Path,
    campaign_id: str,
    title: str,
    hypothesis: str,
    expected_mechanism: str,
    fingerprint: dict[str, Any] | None = None,
    limit: int | None = None,
    minimum_similarity: float = 0.12,
) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    query_text = " ".join((title, hypothesis, expected_mechanism))
    query_tokens = _tokens(query_text)
    query_fp = edge_fingerprint(fingerprint or query_text)
    candidates: dict[str, dict[str, Any]] = {}
    for path in campaign_definition_paths(project_root=root, include_ledger=True):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(payload, dict):
            continue
        other_id = str(payload.get("campaign_id") or path.parent.name)
        if other_id == campaign_id:
            continue
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        other_text = " ".join(
            str(value or "")
            for value in (
                payload.get("title"),
                payload.get("hypothesis"),
                payload.get("expected_mechanism"),
                payload.get("edge_family"),
                source.get("hypothesis"),
                source.get("expected_mechanism"),
            )
        )
        stored_fp = payload.get("economic_edge_fingerprint")
        exact = edge_fingerprint(stored_fp if isinstance(stored_fp, dict) else other_text) == query_fp
        score = _jaccard(query_tokens, _tokens(other_text))
        candidates[other_id] = {
            "campaign_id": other_id,
            "title": payload.get("title") or other_id,
            "source": "definition",
            "path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
            "exact_fingerprint": exact,
            "similarity": round(score, 4),
            "verdict": payload.get("verdict"),
        }

    layout = load_storage_layout(root)
    for ledger in _ledger_paths(root, layout):
        try:
            with ledger.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except OSError:
            continue
        for row in rows:
            other_id = str(row.get("campaign_id") or row.get("strategy_id") or "").strip()
            if not other_id or other_id == campaign_id:
                continue
            other_text = " ".join(
                str(row.get(key) or "")
                for key in (
                    "campaign_id",
                    "title",
                    "edge_family",
                    "edge",
                    "hypothesis",
                    "expected_mechanism",
                    "variant_mechanic",
                    "parameter_space",
                    "timeframe",
                    "failure_reason",
                    "first_failed_stage",
                    "notes",
                    "result",
                )
            )
            score = _jaccard(query_tokens, _tokens(other_text))
            current = candidates.get(other_id)
            ledger_row = {
                "campaign_id": other_id,
                "title": row.get("title") or other_id,
                "source": "ledger" if current is None else "definition_and_ledger",
                "path": str(ledger.relative_to(root)) if ledger.is_relative_to(root) else str(ledger),
                "exact_fingerprint": bool(current and current["exact_fingerprint"]),
                "similarity": round(max(score, float(current["similarity"]) if current else 0.0), 4),
                "verdict": row.get("verdict") or row.get("result") or row.get("status"),
            }
            candidates[other_id] = {**(current or {}), **ledger_row}
    eligible = [
        item
        for item in candidates.values()
        if item["exact_fingerprint"] or float(item["similarity"]) >= float(minimum_similarity)
    ]
    ranked = sorted(
        eligible,
        key=lambda item: (not bool(item["exact_fingerprint"]), -float(item["similarity"]), item["campaign_id"]),
    )
    if limit is None:
        return ranked
    return ranked[: max(1, int(limit))]


def _ledger_paths(root: Path, layout: Any) -> tuple[Path, ...]:
    candidates = {
        root / "research_ledger.csv",
        root / "Start here" / "research_ledger.csv",
        layout.catalog_root / "research_ledger.csv",
        root / "research" / "research_ledger.csv",
    }
    candidates.update(root.glob("**/research_ledger.csv"))
    return tuple(sorted(path for path in candidates if path.is_file()))


def _tokens(value: str) -> set[str]:
    return {word for word in _WORDS.findall(value.lower()) if len(word) > 2}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _fingerprint_value(key: str, value: Any) -> Any:
    if key == "signal_inputs":
        if isinstance(value, str):
            parts = re.split(r"[,;|]", value)
        elif isinstance(value, list):
            parts = [str(item) for item in value]
        else:
            parts = [str(value or "")]
        return sorted(" ".join(_WORDS.findall(item.casefold())) for item in parts if item.strip())
    return " ".join(_WORDS.findall(str(value or "").casefold()))


__all__ = ["duplicate_matches", "edge_fingerprint"]
